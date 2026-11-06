"""SCPI instrument verification with PyVISA resources."""

import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import pyvisa
from pyvisa.constants import StatusCode
from pyvisa.errors import VisaIOError


def parse_values(text):
    values = [float(x.strip()) for x in text.split(",")]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("non-finite or empty trace")
    return values


def within(value, lower, upper):
    return math.isfinite(value) and lower <= value <= upper


def retry(operation, retries=2):
    for attempt in range(retries + 1):
        try:
            return operation()
        except (TimeoutError, VisaIOError) as exc:
            if isinstance(exc, VisaIOError) and exc.error_code != StatusCode.error_timeout:
                raise
            if attempt == retries:
                raise
            time.sleep(0.01)


class Instrument:
    def __init__(self, resource, retries=2):
        self.resource = resource
        self.retries = retries
        self.resource.timeout = 1000
        self.resource.write_termination = "\n"
        self.resource.read_termination = "\n"

    def write(self, command):
        return retry(lambda: self.resource.write(command), self.retries)

    def query(self, command):
        return retry(lambda: self.resource.query(command), self.retries).strip()

    def check_errors(self):
        error = self.query("SYST:ERR?")
        if not error.startswith("0") and not error.startswith("+0"):
            raise RuntimeError(f"instrument error: {error}")


class Oscilloscope(Instrument):
    def waveform(self):
        return parse_values(self.query("WAV:DATA?"))


class OpticalSpectrumAnalyzer(Instrument):
    def capture(self, start, stop, resolution):
        self.write(f"SENS:WAV:STAR {start}")
        self.write(f"SENS:WAV:STOP {stop}")
        self.write(f"SENS:BAND:RES {resolution}")
        self.write("INIT")
        powers = parse_values(self.query("TRAC:DATA?"))
        if len(powers) < 3 or stop <= start:
            raise ValueError("invalid spectrum")
        wavelengths = [start + i * (stop - start) / (len(powers) - 1) for i in range(len(powers))]
        peaks = [
            i for i in range(1, len(powers) - 1) if powers[i] > powers[i - 1] and powers[i] > powers[i + 1]
        ]
        if len(peaks) < 2:
            raise ValueError("spectrum needs at least two peaks")
        peaks = sorted(peaks, key=lambda i: powers[i], reverse=True)[:2]
        peak = peaks[0]
        return {
            "wavelength_nm": wavelengths[peak],
            "power_dbm": powers[peak],
            "spacing_nm": abs(wavelengths[peaks[0]] - wavelengths[peaks[1]]),
            "trace": powers,
        }


class PowerSupply(Instrument):
    def set_voltage(self, voltage):
        self.write(f"VOLT {voltage}")


class OpticalPowerMeter(Instrument):
    def measure(self):
        return float(self.query("MEAS:POW?"))


def run_capture(repeats=3, output=None):
    if not 1 <= repeats <= 100:
        raise ValueError("repeats must be between 1 and 100")
    manager = pyvisa.ResourceManager(str(Path(__file__).with_name("instruments.yaml")) + "@sim")
    scope_resource = manager.open_resource("TCPIP::localhost::10001::SOCKET")
    osa_resource = manager.open_resource("TCPIP::localhost::10002::SOCKET")
    try:
        scope, osa = Oscilloscope(scope_resource), OpticalSpectrumAnalyzer(osa_resource)
        settings = {"start_nm": 1548, "stop_nm": 1552, "resolution_nm": 0.1}
        rows = []
        for i in range(repeats):
            spectrum = osa.capture(1548, 1552, 0.1)
            waveform = scope.waveform()
            scope.check_errors()
            osa.check_errors()
            checks = {
                "wavelength": within(spectrum["wavelength_nm"], 1549.9, 1550.1),
                "power": within(spectrum["power_dbm"], -11, -9),
                "spacing": within(spectrum["spacing_nm"], 0.9, 1.1),
            }
            rows.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "repeat": i + 1,
                    **settings,
                    **spectrum,
                    "waveform": waveform,
                    "checks": checks,
                    "pass": all(checks.values()),
                }
            )
        result = {"settings": settings, "captures": rows}
        if output:
            out = Path(output)
            out.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            (out / f"capture-{stamp}.json").write_text(json.dumps(result, indent=2))
            with (out / f"capture-{stamp}.csv").open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "repeat",
                        "start_nm",
                        "stop_nm",
                        "resolution_nm",
                        "wavelength_nm",
                        "power_dbm",
                        "spacing_nm",
                        "pass",
                    ],
                )
                writer.writeheader()
                writer.writerows({k: row[k] for k in writer.fieldnames} for row in rows)
        return result
    finally:
        scope_resource.close()
        osa_resource.close()
        manager.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", default="instrument-output")
    args = parser.parse_args()
    result = run_capture(args.repeats, args.output)
    print(json.dumps(result, indent=2))
    if not all(row["pass"] for row in result["captures"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
