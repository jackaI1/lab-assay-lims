"""Simulated RF spectrum analyzer and repeatable measurement report.

Frequencies are Hz, powers are dBm, and resolution bandwidth is Hz.
The model is illustrative, not a calibrated instrument or a time-domain FFT.
"""

import argparse
import json
import math
import socketserver
import threading
from pathlib import Path

import numpy as np
import pyvisa

from .instrument import Instrument, parse_values
from .scpi_server import Server


class SpectrumHandler(socketserver.StreamRequestHandler):
    def handle(self):
        settings = {
            "FREQ:STAR": 1e6,
            "FREQ:STOP": 10e6,
            "BAND:RES": 100e3,
            "SOUR:FREQ": 2e6,
            "SOUR:POW": -10.0,
        }
        error = "0,No error"
        trace = None
        for raw in self.rfile:
            command = raw.decode("ascii").strip().upper()
            response = None
            key, _, value = command.partition(" ")
            if key in settings and value:
                try:
                    number = float(value)
                    if not math.isfinite(number) or (key != "SOUR:POW" and number <= 0):
                        raise ValueError
                    settings[key] = number
                    trace = None
                except ValueError:
                    error = "-222,Invalid setting"
            elif command == "INIT":
                start, stop, rbw = (settings[k] for k in ("FREQ:STAR", "FREQ:STOP", "BAND:RES"))
                if stop <= start or rbw > stop - start:
                    error = "-222,Invalid sweep"
                    trace = None
                else:
                    frequency = np.linspace(start, stop, 2001)
                    # Noise density of -120 dBm/Hz integrated over the chosen RBW.
                    power = np.full(frequency.size, 10 ** ((-120 + 10 * np.log10(rbw)) / 10))
                    for multiplier, relative in ((1, 0), (2, -30), (3, -40), (2.7, -50)):
                        center = settings["SOUR:FREQ"] * multiplier
                        power += 10 ** ((settings["SOUR:POW"] + relative) / 10) * np.exp(
                            -4 * np.log(2) * ((frequency - center) / rbw) ** 2
                        )
                    trace = 10 * np.log10(power)
            elif command == "TRAC:DATA?":
                if trace is None:
                    error, response = "-221,No completed sweep", "ERROR"
                else:
                    response = ",".join(f"{p:.6f}" for p in trace)
            elif command == "SYST:ERR?":
                response, error = error, "0,No error"
            elif command == "*IDN?":
                response = "Lab Assay,Simulated RF analyzer,0,1"
            else:
                error = "-113,Undefined header"
                if command.endswith("?"):
                    response = "ERROR"
            if response is not None:
                self.wfile.write((response + "\n").encode("ascii"))
                self.wfile.flush()


class SpectrumAnalyzer(Instrument):
    def sweep(self, start, stop, rbw, source_frequency, source_power):
        values = (start, stop, rbw, source_frequency, source_power)
        if not all(math.isfinite(v) for v in values) or not (
            0 < start < stop and 0 < rbw <= stop - start and source_frequency > 0
        ):
            raise ValueError("invalid sweep or source settings")
        for key, value in zip(("FREQ:STAR", "FREQ:STOP", "BAND:RES", "SOUR:FREQ", "SOUR:POW"), values):
            self.write(f"{key} {value}")
        self.write("INIT")
        self.check_errors()
        powers = parse_values(self.query("TRAC:DATA?"))
        self.check_errors()
        if len(powers) < 3 or rbw < 2 * (stop - start) / (len(powers) - 1):
            raise ValueError("RBW must span at least two trace intervals")
        return np.linspace(start, stop, len(powers)), np.array(powers)


def analyze(frequencies, powers, rbw, spur_limit_dbc=-45):
    """Find strongest peak, harmonics and strongest remaining local peak.

    Harmonics are searched within one RBW of integer multiples of the peak;
    outside-span harmonics are reported as unavailable, never as passing.
    """
    peak_index = int(np.argmax(powers))
    peak_frequency, peak_power = float(frequencies[peak_index]), float(powers[peak_index])
    floor = float(np.median(powers))
    excluded = np.abs(frequencies - peak_frequency) <= rbw
    harmonics = []
    for order in (2, 3):
        target = peak_frequency * order
        if target - rbw < frequencies[0] or target + rbw > frequencies[-1]:
            harmonics.append({"order": order, "status": "outside sweep"})
            continue
        window = np.abs(frequencies - target) <= rbw
        excluded |= window
        indices = np.flatnonzero(window)
        index = int(indices[np.argmax(powers[indices])])
        harmonics.append(
            {
                "order": order,
                "frequency_hz": float(frequencies[index]),
                "power_dbm": float(powers[index]),
                "relative_dbc": float(powers[index] - peak_power),
            }
        )
    candidates = np.flatnonzero((powers[1:-1] > powers[:-2]) & (powers[1:-1] > powers[2:])) + 1
    candidates = candidates[~excluded[candidates]]
    if len(candidates):
        index = int(candidates[np.argmax(powers[candidates])])
        relative = float(powers[index] - peak_power)
        spur = {
            "frequency_hz": float(frequencies[index]),
            "power_dbm": float(powers[index]),
            "relative_dbc": relative,
            "limit_dbc": spur_limit_dbc,
            "pass": relative <= spur_limit_dbc,
        }
    else:
        spur = {"status": "no local peak found", "limit_dbc": spur_limit_dbc, "pass": None}
    return {
        "peak": {"frequency_hz": peak_frequency, "power_dbm": peak_power},
        "noise_floor_dbm": floor,
        "harmonics": harmonics,
        "spur": spur,
    }


def run(output, start=1e6, stop=10e6, rbw=100e3, source_frequency=2e6, source_power=-10, spur_limit_dbc=-45):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    server = Server(("127.0.0.1", 0), SpectrumHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    manager = None
    try:
        manager = pyvisa.ResourceManager("@py")
        with manager.open_resource(f"TCPIP::127.0.0.1::{server.server_address[1]}::SOCKET") as resource:
            frequencies, powers = SpectrumAnalyzer(resource).sweep(
                start, stop, rbw, source_frequency, source_power
            )
        report = {
            "instrument": "simulated",
            "settings": {
                "start_hz": start,
                "stop_hz": stop,
                "rbw_hz": rbw,
                "source_frequency_hz": source_frequency,
                "source_power_dbm": source_power,
            },
            "measurement": analyze(frequencies, powers, rbw, spur_limit_dbc),
        }
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        fig, ax = plt.subplots()
        ax.plot(frequencies / 1e6, powers)
        ax.set(xlabel="Frequency (MHz)", ylabel="Power (dBm)", title="Simulated spectrum")
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(out / "spectrum.png", dpi=150)
        plt.close(fig)
        return report
    finally:
        if manager is not None:
            manager.close()
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="spectrum-output")
    parser.add_argument("--start-hz", type=float, default=1e6)
    parser.add_argument("--stop-hz", type=float, default=10e6)
    parser.add_argument("--rbw-hz", type=float, default=100e3)
    parser.add_argument("--source-frequency-hz", type=float, default=2e6)
    parser.add_argument("--source-power-dbm", type=float, default=-10)
    parser.add_argument("--spur-limit-dbc", type=float, default=-45)
    args = parser.parse_args()
    report = run(
        args.output,
        args.start_hz,
        args.stop_hz,
        args.rbw_hz,
        args.source_frequency_hz,
        args.source_power_dbm,
        args.spur_limit_dbc,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
