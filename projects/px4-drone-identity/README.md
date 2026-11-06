# px4-drone-identity

I built a simulated drone with a controller identity check to learn how the underlying idea works. This is a learning project.

## Run it

I use Docker, which packages the simulator and its dependencies together. Allow roughly 15 GB of disk space and at least 6 GB of available memory for the first build. The tested environment is Linux on an x86-64 processor; Docker Desktop on another platform may need emulation.

```sh
docker build -f docker/Dockerfile -t px4-identity .
mkdir -p results/run-1
docker run --rm --init --shm-size=256m \
  -v "$PWD/results/run-1:/results" px4-identity
```

The first build downloads and compiles PX4, the flight-controller software, and Gazebo, the virtual world. There is no graphical window. The command runs eight experiments and prints a PASS or exits with an error. Use a fresh results directory each time.

I look at `results/run-1/experiments.jsonl` for the measured results. Each line records one experiment, the observed flight state and, for a failed link, how long the landing response took. `audit.jsonl` explains authentication failures. `resource.json` records the simulator process I started, and `cleanup.json` checks that its process group and private UDP port were released. The container is removed when the command ends.

To try just one experiment:

```sh
mkdir -p results/replay
docker run --rm --init --shm-size=256m \
  -v "$PWD/results/replay:/results" px4-identity \
  experiments --output /results --scenario replayed_frame
```

## How I put it together

The controller and vehicle get separate Ed25519 certificates from a local certificate authority, my test identity issuer. Mutual TLS means both ends prove they own the private key for an accepted certificate. Inside that encrypted connection, the companion supplies a fresh key for signing MAVLink 2, the message format used to talk to the drone. MAVLink signing uses a shared secret and SHA-256; it is separate from the Ed25519 certificate signatures.

My Python gateway checks the certificate again on every frame, rejects invalid signatures and old timestamps, and allows commands according to the certificate's role. A pilot can arm, disarm, take off within a 1-5 metre height limit, and land. An observer can ask for status through signed heartbeats. Everything else is rejected, including changes to parameters and the watchdog's internal control commands.

The companion sends accepted commands over a private connection inside the container. My C++ `identity_guard` module receives the accepted-link status through uORB, PX4's internal message bus. It publishes its own status on that bus and requests landing if a heartbeat is late or authentication fails. The experiment observes that published status through PX4's existing telemetry stream.

I kept the internal PX4 connection private and publish no container ports. This release uses PX4 v1.16.0 with the gateway as the signing boundary; the internal PX4 link is unsigned. Someone who controls the container could bypass it. I also deliberately make authentication failures request landing, which means an attacker who can reach the gateway can interrupt a flight. [My threat model](docs/threat-model.md) explains that availability tradeoff and the other limits.

## Working on it

The smaller tests run without Docker or a simulator:

```sh
uv venv --python 3.12
uv pip install -e '.[test]'
uv run pytest -q
uv run ruff check src tests
c++ -std=c++14 -Wall -Wextra -Werror -Wfloat-equal -I px4/identity_guard \
  tests/guard_test.cpp -o /tmp/identity-guard-test
/tmp/identity-guard-test
rm /tmp/identity-guard-test
```

[Architecture and protocol details](docs/architecture.md) cover the software key-store interface, role rules and watchdog states. [Experiment notes](docs/experiments.md) explain the assertions, result files and how I investigate a failed run. The CLI also supports generating disposable identities, revoking them and operating a gateway against a running lab instance; `uv run drone-identity --help` lists the commands.

## Tests and limits

There are 8 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `px4-drone-identity-ci.yml`.
