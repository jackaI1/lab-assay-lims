"""Local synthetic SCPI socket instruments for characterization exercises."""

import socketserver
import threading


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        voltage = 0.0
        error = "0,No error"
        for line in self.rfile:
            command = line.decode("ascii").strip()
            response = None
            if command.startswith("VOLT "):
                try:
                    voltage = float(command.split()[1])
                except ValueError:
                    error = "-222,Invalid voltage"
            elif command == "MEAS:VOLT?":
                response = str(voltage)
            elif command == "MEAS:POW?":
                response = "0.001"
            elif command == "WAV:DATA?":
                response = "0,0.5,1,0.5,0"
            elif command == "SYST:ERR?":
                response, error = error, "0,No error"
            elif command == "*IDN?":
                response = "Lab Assay,Synthetic,0,1"
            else:
                error = "-113,Undefined header"
                if command.endswith("?"):
                    response = "ERROR"
            if response is not None:
                self.wfile.write((response + "\n").encode("ascii"))
                self.wfile.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_server():
    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def characterize(resource, settings, lower_error, upper_error, output):
    from .instrument import PowerSupply, within

    supply = PowerSupply(resource)
    rows = []
    for value in settings:
        supply.set_voltage(value)
        measured = float(supply.query("MEAS:VOLT?"))
        supply.check_errors()
        rows.append(
            {
                "setting_v": value,
                "measured_v": measured,
                "pass": within(measured - value, lower_error, upper_error),
            }
        )
    import csv

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["setting_v", "measured_v", "pass"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    import argparse

    import pyvisa

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="sweep.csv")
    args = parser.parse_args()
    server, thread = start_server()
    manager = pyvisa.ResourceManager("@py")
    try:
        port = server.server_address[1]
        with manager.open_resource(f"TCPIP::127.0.0.1::{port}::SOCKET") as resource:
            print(characterize(resource, [0, 1, 2, 3], -0.05, 0.05, args.output))
    finally:
        manager.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
