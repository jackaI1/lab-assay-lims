# What the tests prove

I separate quick protocol checks from tests that need the actual flight software. `python -m pytest -q` runs the quick tests and explicitly skips the two simulator cases unless `RUN_SITL=1`. Use `scripts/sitl_check.py` to start the simulator and run those cases with cleanup.

## Protocol and permission tests

The local suite includes real OpenSSL mutual-TLS connections and real pymavlink packets. Its vehicle sink captures forwarded bytes so I can prove that rejected traffic never reaches the flight link. It covers permission-list rejection even with a CA-issued certificate, missing certificates, foreign trust roots, strict signing, wrong keys, modified signatures, unsigned packets, MAVLink 1, malformed packets, replay, source/target checks, command restrictions, invalid coordinates, heartbeat timeout, exclusive ownership, and fresh keys after reconnecting.

The protocol tests use an in-process vehicle sink. They prove gateway behavior, not PX4 flight behavior.

## Actual Gazebo flight tests

The `gazebo` CI job builds PX4 v1.16.0, including its Gazebo bridge, then launches `gz_x500` with physics and the real PX4 estimator/controller. Both parameterized tests:

1. Try an unlisted but correctly issued controller certificate and verify zero forwarded commands.
2. Connect the approved controller over mutual TLS and stream signed position targets at 10 Hz.
3. Observe actual Offboard mode, an armed vehicle, and more than one metre altitude.
4. Verify an unlisted connection cannot steal the active session.
5. Stop valid traffic. One case simulates a silent link; the other sends a packet signed with the wrong key.
6. Observe the companion revoke control, then independently read PX4 telemetry until it reports automatic Land and subsequently disarms.
7. Assert no further messages were forwarded after revocation, and Land mode appeared within ten seconds.

No test forces arming, fabricates a PX4 heartbeat, or passes because Gazebo is unavailable. Integration cases fail if the simulator, estimator, arm command, flight, failsafe or cleanup fails.

`artifacts/link-loss.json` and `artifacts/bad-signature.json` record measured altitude and time to Land mode. `sitl.xml` records assertions; `px4.log` is the simulator's output; `ownership.json` records cleanup. These are generated evidence, so I keep them in CI artifacts rather than committing a changing local result as if it were permanent.

## Recorded result

[CI run 42129280879](https://github.com/jackaI1/px4-drone-identity-sitl/actions/runs/42129280879) passed 35 protocol tests and both real Gazebo flight tests on 5 November 2026. Link loss was injected at 1.015 m, with Land mode observed after 1.393 s; the wrong-key case was injected at 1.027 m, with Land mode after 1.267 s. Both subsequently landed and disarmed. The unlisted certificate attempts were rejected before flight and during the approved session.

The cleanup record reports `cleaned: true` and an empty `ports_still_in_use` list for UDP 14540, 14580 and 18570. The daemon-mode PX4 log was 3,549 bytes. I use compile-only targets to build PX4, then launch its binary with `-d` inside the runner's owned process group. This avoids the interactive shell's repeated prompts when CI has no terminal.
