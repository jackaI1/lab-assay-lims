#!/usr/bin/env python3
"""Own one PX4/Gazebo process group, run integration tests, and always stop it."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--px4", type=Path, required=True, help="PX4 v1.16.0 source checkout, already built")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
# Never attach to or stop an owner's pre-existing simulator.
for port in (14540, 14580, 18570):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", port))
env = os.environ | {"HEADLESS": "1", "PX4_SIM_MODEL": "gz_x500", "GZ_IP": "127.0.0.1",
    "PX4_PARAM_COM_RC_IN_MODE": "4", "PX4_PARAM_COM_OF_LOSS_T": "1",
    "PX4_PARAM_COM_OBL_RC_ACT": "4", "PX4_PARAM_COM_FAIL_ACT_T": "0",
    "PX4_PARAM_NAV_DLL_ACT": "0", "PX4_PARAM_COM_DISARM_LAND": "1"}
with (artifacts / "px4.log").open("w") as log:
    build = args.px4.resolve() / "build/px4_sitl_default"
    proc = subprocess.Popen([str(build / "bin/px4"), "-d"], cwd=build / "rootfs",
                            env=env, stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    ownership = {"owner": "scripts/sitl_check.py", "pid": proc.pid, "process_group": proc.pid,
                 "started_at_unix": time.time(), "ports_udp": [14540, 14580, 18570],
                 "cleanup": f"kill -TERM -- -{proc.pid}", "cleaned": False}
    (artifacts / "ownership.json").write_text(json.dumps(ownership, indent=2))
    status = 1
    try:
        # Readiness is proved by MAVLink telemetry in the tests, not by this delay.
        time.sleep(5)
        if proc.poll() is not None:
            raise RuntimeError("PX4 exited; inspect artifacts/px4.log")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-s", "-m", "sitl",
                                 "--junitxml=artifacts/sitl.xml"], cwd=root,
                                env=os.environ | {"RUN_SITL": "1", "SITL_ARTIFACTS": str(artifacts)}, timeout=240)
        status = result.returncode
    finally:
        # SIGINT lets PX4 stop Gazebo; the group belongs exclusively to this script.
        for sig, timeout in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 2)):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                continue
            # The launcher may have exited before its children. Check the group too.
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.5)
        ownership["cleaned"] = True
        try:
            os.killpg(proc.pid, 0)
            ownership["cleaned"] = False
        except ProcessLookupError:
            pass
        ownership["ports_still_in_use"] = []
        for port in (14540, 14580, 18570):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    ownership["ports_still_in_use"].append(port)
        ownership["cleaned"] = ownership["cleaned"] and not ownership["ports_still_in_use"]
        (artifacts / "ownership.json").write_text(json.dumps(ownership, indent=2))
        if not ownership["cleaned"]:
            status = 1
        if status:
            print("Last 45 PX4 log lines:")
            with (artifacts / "px4.log").open("rb") as diagnostic:
                diagnostic.seek(max(0, (artifacts / "px4.log").stat().st_size - 16000))
                lines = diagnostic.read(16000).decode(errors="replace").splitlines()
                print("\n".join(line[:300] for line in lines[-45:]))
sys.exit(status)
