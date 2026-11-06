# Controller identity and the flight boundary

I wanted to distinguish three questions: who connected, whether each message was authentic, and what the drone did after control disappeared.

## Identity and key delivery

`identity.py` creates an ephemeral P-256 certificate authority and issues a server identity plus two client identities. Only the controller certificate's SHA-256 fingerprint enters `controllers.json`; the other client demonstrates a valid but unauthorized identity. The CA key stays in memory and is discarded. Private leaf keys have mode 0600 inside a mode 0700 directory, which is ignored by git. Provisioning refuses to overwrite an existing directory. Certificates expire after two days and the CA after seven.

OpenSSL, through Python's `ssl` module, verifies the chain, validity period, intended certificate usage and server hostname. TLS 1.3 is the minimum. A connection with no client certificate fails during the handshake. A CA-issued but unlisted certificate fails before receiving a session key. The server reads the permission list on each new connection. Removing an identity prevents future sessions; this demo does not implement immediate certificate revocation for an already active session.

After mutual authentication, the server sends `ID01` followed by a fresh random 32-byte key inside TLS. Keys never appear in logs or files. Each session has a new key, so reconnecting cannot reset replay protection for an old key. Both directions carry a two-byte network-order length followed by exactly one MAVLink 2 packet, limited to 280 bytes. Pymavlink verifies signatures and tracks monotonically increasing signing timestamps. The sender uses the MAVLink epoch in 10-microsecond units. Link IDs separate controller and companion streams.

TLS already protects the transport. Keeping MAVLink signing inside it lets me exercise the actual signing parser, replay rejection and unsigned-message policy while using certificates for identity and encrypted key distribution. MAVLink signing by itself does not encrypt payloads or authenticate an X.509 certificate.

## Command permission

A single active session owns control. Messages must originate from system 255/component 190 and target vehicle 1/component 1. A valid ground-controller heartbeat is required before control messages and at least every 0.75 seconds. Other messages never extend the heartbeat deadline.

`Policy` accepts only:

- Ground-controller heartbeats.
- Local NED position targets, with position-only mask `0xDF8`, finite values, x/y within ±10 m and z between -5 and 0 m. NED means north/east/down, so negative z is above the origin.
- Ordinary arm/disarm, Offboard selection, and automatic Land selection, with exact parameter tuples.

A bad signature, replay, unsupported command, invalid target, expired heartbeat or malformed frame closes the whole session. No queued or cached flight target continues after that. A denied second connection does not cancel the current owner's session.

## PX4 and Gazebo

The simulator uses unmodified PX4 v1.16.0 and Gazebo's x500 quadcopter. Its onboard MAVLink channel listens on UDP 14580 and sends telemetry to the companion on 14540. The companion signs outbound vehicle packets using a separate, in-memory key. PX4 v1.16.0 does not verify that key. These signatures demonstrate packet generation, **not PX4-side enforcement**. The controller-to-companion signatures are actually verified and enforced.

The trust boundary therefore ends at the companion. Only the companion should reach the simulator's control ports. The default GCS port 18570 and other PX4 channels remain part of the trusted simulation environment. Publishing those ports to an untrusted network would bypass this design. The reference controller connects to localhost; this repository does not provide remote deployment or a public command service.

I configure `COM_OF_LOSS_T=1`, `COM_OBL_RC_ACT=4` (Land), `COM_FAIL_ACT_T=0`, and `COM_RC_IN_MODE=4` (no manual controller). `NAV_DLL_ACT=0` prevents the separate ground-station-loss rule from masking the Offboard-loss test. `COM_DISARM_LAND=1` makes the eventual disarm easy to observe. Preflight checks stay enabled and arming does not use the force-arm bypass.

The tests observe real heartbeat mode bits, armed state and local position. They do not infer landing from a gateway log or from a successful command write. Only heartbeat, position, command acknowledgment, status text, extended state and version telemetry are relayed. Unknown dialect messages are ignored so they cannot stop the useful telemetry stream. Vehicle telemetry is parsed on the trusted UDP side and signed by the companion before being returned over TLS. This proves it came through the companion, not that the original vehicle telemetry was cryptographically authenticated.

## Remaining limits

This is software-only. I have not tested physical hardware, radio interference, real flight stability, a Pixhawk, public-network denial of service, revocation infrastructure, secure key storage or an audited cryptographic deployment. The fixed position envelope is a command filter, not a geofence. TLS can still be disrupted; its intended outcome here is lost control followed by the simulator's own failsafe. The local demo puts all identities in one directory for convenience; real deployments would distribute only each party's own private key and certificate.

## References

- [PX4 v1.16 Offboard mode](https://docs.px4.io/v1.16/en/flight_modes_mc/offboard.html)
- [PX4 v1.16 Gazebo simulation](https://docs.px4.io/v1.16/en/sim_gazebo_gz/)
- [Pymavlink signing API](https://mavlink.io/en/mavgen_python/message_signing.html)
- [MAVLink signing specification](https://mavlink.io/en/guide/message_signing.html)
- [PX4 v1.16 startup parameters](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/ROMFS/px4fmu_common/init.d-posix/rcS)
