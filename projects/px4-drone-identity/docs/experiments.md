# How I check the result

The Docker entry point starts the actual PX4 binary built with my C++ module, a headless Gazebo Harmonic world and its x500 multicopter. These are software-in-the-loop tests: the flight controller runs real control/navigation code while the aircraft and sensors are simulated.

`experiments.py` never substitutes a fake flight controller. It binds the companion's private UDP socket, waits for PX4 heartbeat, ground state and module status, provisions fresh certificates, then opens a real mutual TLS connection. It retries normal arming while PX4's estimator becomes ready. It does not use force arm or disable estimator health checks.

## Flight assertions

For each flight case, I require fresh PX4 telemetry showing armed motors, not landed and altitude above one metre. This precondition prevents a “failsafe passed” result from a drone that never flew. A normal two-metre takeoff goes through the signed controller and role allowlist.

For each failure, I record the command-forwarding count before injection and assert that it does not increase. I then require the expected `id_guard` value from the C++ module's uORB publication, a response within six seconds, AUTO_LAND mode while still armed, then ground contact, near-zero altitude and disarmed motors. The expected two-second silent-link timeout is inside that six-second test deadline, which also allows telemetry/scheduling delay. Failed state must stay latched through landing. I also try another signed arm command on the old session after the failsafe and assert it cannot be forwarded. Flight freshness checks cover heartbeat, position, ground state and module status individually. The healthy flight must keep status 10 throughout commanded landing.

The expired-certificate attempt happens while the valid pilot keeps sending heartbeats, so a silent-link timeout cannot masquerade as certificate rejection. Revocation changes the currently connected pilot's local denylist entry, and its very next frame must fail. Bad-signature and unsigned tests use arm commands and assert they are never forwarded. The replay test first accepts a heartbeat, then repeats the exact same bytes. For silent link, TLS stays connected and no more frames are sent, so the C++ watchdog must detect the loss independently of socket closure.

The observer case stays grounded, accepts a signed heartbeat/status request, denies arm, checks that no command was forwarded, and observes guard status 24 with motors still disarmed.

## Evidence files

| File | Contents |
| --- | --- |
| `experiments.jsonl` | One result per scenario, including airborne/landing/ground snapshots, expected watchdog reason, elapsed time and PASS/FAIL |
| `audit.jsonl` | Successful authentication, rejection reasons and connection closure; no keys or packet dumps |
| `px4.log` | Simulator output for diagnosing readiness, command refusal or navigation failures |
| `network.json` | Actual PX4 UDP listener binding, verified as loopback before flight |
| `resource.json` | Owned process group, PID/start time, command, private UDP port and scoped stop command |
| `cleanup.json` | Process-group liveness and port-release checks after stopping the simulator, including failure paths |

A failure writes the last observed telemetry and exits nonzero. The CI job always uploads the evidence and stops/removes its named container. Use an empty results directory to avoid mixing runs. Do not commit generated key stores, flight logs or local result bundles.

## Smaller tests

The Python suite checks certificate proof of possession, validity, wrong issuer, revocation, missing revocation storage, role restrictions, target/parameter checks, real MAVLink signatures and replay, real TLS handshakes, concurrent controller sends, UDP telemetry/command translation and process cleanup after an exception. A narrow UDP test peer supplies known telemetry; it does not count as a flight experiment. The C++ executable checks timeout boundaries, first-reason latching, refused reset while armed and recovery while disarmed against the exact header compiled into PX4.

The workflow runs both these tests and the real flight campaign on pull requests and on main. I use the published `flight-evidence` artifact to inspect measured flight times rather than hardcode them into documentation.

## Using the component commands

For experimenting inside an existing lab container or Linux environment with PX4 already running and the supplied startup configuration:

```sh
uv run drone-identity provision --store .state
uv run drone-identity gateway --store .state
# In a second terminal in that same network namespace:
uv run drone-identity controller status --identity observer --store .state --seconds 5
uv run drone-identity revoke pilot --store .state
```

The gateway uses TCP 8443 on loopback, receiver UDP 14540 and PX4 UDP 14580. One controller occupies a session. Closing it triggers the fail-closed policy; a fresh session can reset only after the drone is disarmed. The standalone command interface is for inspecting messages and ground operations. The automated experiments keep one session alive through the whole takeoff/landing sequence. Provisioning uses short-lived test certificates; regenerate an empty store when they expire.

## A measured run

In [this CI run](https://github.com/jackaI1/px4-drone-identity/actions/runs/42139765938), all eight experiments passed. Seven cases flew the Gazebo aircraft and finished on the ground with motors disarmed; the observer case stayed grounded. These are seconds from the failure injection to observing the expected module failsafe state, not the time to complete landing.

| Injection | Observed failsafe delay |
| --- | ---: |
| Silent link | 2.004 s |
| Expired certificate | 0.054 s |
| Revoked certificate | 0.052 s |
| Bad signature | 0.202 s |
| Replayed frame | 0.102 s |
| Unsigned frame | 0.251 s |

That run also verified `127.0.0.1:14580`, no remaining simulator process group, and release of UDP 14580. Its captured simulator log was 24,143 bytes and was not truncated. These measurements describe that run and machine; the test deadline is six seconds and subsequent runs record their own measurements.
