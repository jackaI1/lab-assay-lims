# What this lab protects, and what it does not

I use this lab to test controller identity and loss of an accepted controller while a virtual drone is airborne. All identities, keys and flights are disposable test material. There is no real aircraft, secure element, secure boot chain or production CA.

## Trusted boundary

I trust the container, its operating system, the local CA and revocation files, both Python processes, PX4 and Gazebo. An attacker outside that boundary may connect to the gateway, possess an observer certificate, replay an old frame or TLS session's payload, change a MAVLink signature, or interrupt the accepted link. The gateway binds loopback by default. An attacker would need access to that network namespace or an explicitly added transport to reach it; Docker publishes no ports in the documented run.

I want three properties:

- Only a currently valid, CA-issued client with proof of its private key can establish a session.
- That client's role limits what the gateway forwards. A signature cannot turn an observer into a pilot or authorize an internal watchdog command.
- A failed accepted link eventually requests landing, even if Python freezes or disappears, because the timer lives in PX4.

## Deliberate availability tradeoff

For this experiment I choose fail-closed behavior: a failed TLS identity attempt, revoked/expired live identity, malformed signed frame or denied command requests landing. A client able to reach the gateway can therefore cause denial of service. Production policy might instead isolate failed unauthenticated peers and keep the current healthy pilot. I would need to test that different policy separately. A rejected additional client does not acquire the active session or its key.

The worker count, frame size, socket timeouts and status-message buffers are bounded, but this is not a hardened network service or a claim of resistance to sustained resource-exhaustion attacks. The revocation tool assumes one local administrator.

## Limits of the cryptography

Certificate signatures use Ed25519. MAVLink 2 signing uses a symmetric 32-byte key and a truncated SHA-256 authenticator, not asymmetric certificate signatures. TLS 1.3 carries that key confidentially after mutual authentication. Fresh session keys prevent old-session frames from validating; pymavlink timestamps reject replay within a session. This does not protect against a controller that already knows the current shared key and deliberately creates fresh, valid pilot commands.

The file-backed key store offers an interface shaped like a secure element, not its physical protection. Root or another process with access to its files/RAM can steal keys. Test CA keys are generated at runtime and kept separate from committed code. There is no encrypted-at-rest key storage, hardware attestation, rollback protection, reliable external clock or protection against CA compromise. Local clock correctness matters for certificate validity.

The local revocation list is trusted storage, not a signed network-distributed CRL. The gateway checks revocation and expiry again on each frame; TLS alone would not expire an already established session immediately. The automated expired-certificate flight uses a new connection with an already expired certificate, while the smaller tests also check expiry after a session starts.

## Flight boundary

The MAVLink signature terminates at the gateway. The private PX4 link is unsigned, and USER_1 status messages trust their local source. A process that can send directly to UDP 14580 can bypass authentication or reset a disarmed watchdog. The container network and process boundary is part of this design. Publishing the private port, adding another PX4 MAVLink instance or using host networking invalidates this assumption.

The pilot intentionally has arm/disarm authority. Parameter validation constrains this lab's commands; it is not a general flight-safety guarantee. A PX4 landing request still depends on a working estimator, navigator, actuator simulation and sufficient altitude. Sensor failures, wind, GPS spoofing, malicious PX4 firmware, physical attacks and real aircraft certification are outside these experiments. I assert the observed landing response in the supplied world, rather than claim this always guarantees a safe outcome.
