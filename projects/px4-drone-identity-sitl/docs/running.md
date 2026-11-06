# Run a virtual flight

I use Linux for PX4 and Gazebo. The quick identity tests also run on macOS. CI supplies the complete Linux environment and saves its evidence as an artifact.

## Use the same environment as CI

This container contains the PX4 simulation toolchain. Its digest pins the actual image instead of a moving `latest` tag. Docker must already be running. On an Intel/AMD Linux computer, from this repository:

```sh
docker run --rm --init -it --name px4-identity-demo \
  -v "$PWD:/work" -w /work \
  px4io/px4-dev-simulation-jammy@sha256:ba6f790b63f8fec427aaf174a7cb6a89950c69083653e7f67543f49b9ce20928 bash
```

Inside the container, install the Gazebo Harmonic libraries, build PX4 with its system Python, then use uv, a Python environment manager, to install Python 3.12 for the companion:

```sh
bash scripts/install_gazebo.sh
git clone --branch v1.16.0 --depth 1 https://github.com/PX4/PX4-Autopilot.git /tmp/PX4-Autopilot
git -C /tmp/PX4-Autopilot submodule update --init --recursive --depth 1 -- src/modules/mavlink/mavlink src/drivers/gps/devices src/lib/events/libevents src/modules/uxrce_dds_client/Micro-XRCE-DDS-Client src/lib/heatshrink/heatshrink Tools/simulation/gz
python3 -m pip install -r /tmp/PX4-Autopilot/Tools/setup/requirements.txt
make -C /tmp/PX4-Autopilot px4_sitl_default PX4_MAKE_ARGS=-j2
cmake --build /tmp/PX4-Autopilot/build/px4_sitl_default --target px4_gz_plugins --parallel 2
python3 -m pip install uv
uv venv --python 3.12 /tmp/identity-venv
. /tmp/identity-venv/bin/activate
uv pip install -e '.[test]'
python scripts/sitl_check.py --px4 /tmp/PX4-Autopilot
```

I fetch only the SITL dependencies; an unnecessary shallow NuttX checkout lacks the release tags used by PX4's version generator. NuttX is for hardware targets and is not used here.

For a native Ubuntu 22.04 installation, use [PX4's setup script](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/Tools/setup/ubuntu.sh) with `--no-nuttx`, then the build and test commands above. Expect a substantial first download and build. CI limits the build to two parallel jobs. On Apple Silicon, prefer the hosted CI run to emulating this amd64 image.

## Run the controller manually

After the build, start the simulator in its own terminal:

```sh
cd /tmp/PX4-Autopilot
HEADLESS=1 PX4_PARAM_COM_RC_IN_MODE=4 PX4_PARAM_COM_OF_LOSS_T=1 \
PX4_PARAM_COM_OBL_RC_ACT=4 PX4_PARAM_COM_FAIL_ACT_T=0 \
PX4_PARAM_NAV_DLL_ACT=0 PX4_PARAM_COM_DISARM_LAND=1 make px4_sitl gz_x500
```

From the project, with the Python environment activated:

```sh
drone-identity provision
drone-identity companion
```

In another terminal in the project, activate the same environment and run `drone-identity fly`. It connects using the provisioned certificate, sends signed heartbeats and position targets, waits for Offboard mode, arms, climbs above one metre, then requests Land and waits for disarm. A failed command or missing telemetry causes a nonzero error rather than a success message.

To deliberately lose the link, interrupt `drone-identity fly` while it is airborne. The companion stops forwarding targets. PX4 should land using its configured failsafe. The automated test checks this using telemetry rather than visual judgment. The simulator is headless by default; on a Linux desktop omit `HEADLESS=1` for the Gazebo window.

Stop the companion and the simulator with Ctrl+C. For the named disposable container, `docker stop px4-identity-demo` stops only that container; `--rm` removes it. Do not expose PX4 UDP ports to an untrusted network. Delete `.local/identity` to discard the demo's certificates, then reprovision when they expire. Do not commit that directory.

## Ports and owned resources

The companion binds TLS TCP 8443 and UDP 14540 to loopback. PX4 uses UDP 14580 for Offboard and 18570 for its ground-station channel. The automated runner refuses to start if these ports are occupied. It launches the compiled PX4 binary with `-d` to disable the interactive shell, starts one new process group, records its PID, start time and cleanup command in `artifacts/ownership.json`, and terminates that exact group in a `finally` block. It never kills a generic Node, browser or existing PX4 process. CI's job container is removed by GitHub after the job.
