# Data and analysis design

## Path through the service

The demo publishes five read-only OPC UA variables. The collector resolves the namespace URI, then reads all five DataValues in one request. A DataValue carries the value, a source timestamp and a quality status. A frame is accepted only if every tag passes validation and all source timestamps agree within one millisecond. A publish/read race can produce an incoherent frame; it is retained and rejected, then the next poll can recover.

The complete frame goes into SQLite before rule evaluation in the same transaction. Rejected frames retain receive time, available source time, original values and a list of reasons. Nonfinite input values are retained as text so the API remains valid JSON. Unsupported OPC UA value types are retained with their type name and a readable representation limited to 512 characters. A source timestamp identifies a sample. An unchanged motor or cycle count with a fresh timestamp is valid; a replay of an accepted timestamp is a duplicate. Older timestamps are out of order. Future timestamps beyond one second and timestamps older than the stale limit are rejected. The duplicate watermark survives restart in SQLite.

The `Monitor` owns the connection and is used serially on the application event loop. There is one collector and one web worker. Do not run multiple workers against the same database. No application-controlled input becomes SQL text; queries use bound parameters.

## Source contract

Namespace URI: `urn:jacklai:filling-line` (override with `--namespace`). String NodeIds in that namespace:

| NodeId | OPC UA type | Accepted range | Meaning |
| --- | --- | --- | --- |
| `cycle_count` | UInt32 | 0 to 4294967295 | Cumulative completed bottles |
| `cycle_time` | Double | 0.05 to 120 seconds | Last completed cycle duration |
| `motor_running` | Boolean | true or false | Conveyor motor state |
| `fault_code` | UInt16 | 0 to 5 | Current simulated fault |
| `fault_count` | UInt32 | 0 to 4294967295 | Cumulative fault events |

Fault codes: 0 none, 1 low tank, 2 conveyor timeout, 3 guard open, 4 emergency stop, 5 fill position did not clear. These are the conceptual fault meanings in the training bench, not a claim of a direct wire-level mapping to its ladder program. The simulated repeated-fault scenario adds one fault event per publication to make the rising rate visible.

All five tags must publish a fresh common source timestamp, even if their values have not changed. A source that timestamps only changed tags needs an adapter or a snapshot envelope; it cannot be connected unchanged. Missing nodes and bad quality become visible rejected samples. Missing namespace or network errors become connection incidents. The collector reuses its session, disconnects on failure and retries after the poll interval. It never sends control writes.

## Calculations

Use accepted frames inside the configured rolling source-time window. For each adjacent pair, use the earlier frame's motor and fault state for the elapsed interval. Exclude an interval if a rejection occurred between its endpoints, the gap exceeds 2.5 polling periods, or either cumulative counter decreased. After a counter reset the next normal interval can contribute again. No interval is extrapolated beyond the latest sample.

- Observed time = sum of these usable intervals.
- Running time = usable interval time whose earlier motor state is on and fault code is zero.
- Availability = running time / observed time.
- Performance = target cycle seconds × completed-cycle increments in running intervals / running time, capped at 100%.
- Fault rate = fault-count increments / observed time × 60, in events per minute.
- Cycle-time drift = average accepted cycle time / configured target cycle time − 1.
- Coverage = observed time / full configured window.

Time-based measures are unknown without a usable interval; drift needs one accepted sample. Short startup windows are noisy and have low coverage. Performance measures counts rather than trusting the reported cycle-time tag, so discrepancies between the two remain visible. This is not OEE: no product quality/yield signal or planned-production schedule is supplied. Polling can miss short transients, and counter increments cannot locate a fault exactly within an interval.

Rules use strict comparisons, so exactly 25% drift does not fire with a 25% threshold. Rules evaluate on accepted frames. Current faults fire immediately. Missing/bad samples open data-quality alerts and freeze machine-performance incidents until usable evidence is available. Unknown rate or availability does not clear an existing incident. A returned OPC UA response clears a connection incident even if its payload then opens data-quality concerns.

## Incident lifecycle

A partial unique index permits at most one uncleared incident per rule. A firing observation increments its occurrence count and last-seen time. Acknowledgement changes active to acknowledged and records the time. Further firing observations preserve that acknowledgement. A recovery changes either open state to cleared, keeping its review timestamp. A later fault opens a new incident. All open incidents remain visible regardless of the limit on cleared history.

## HTTP API

The dashboard binds to 127.0.0.1. Host validation and same-origin write checks guard local browser actions. There is no cross-origin access configuration and no remote authentication layer.

| Request | Result |
| --- | --- |
| `GET /api/status` | Current condition, latest sample, metrics, config, all open and latest 100 cleared incidents |
| `GET /api/readings?limit=100` | Latest readings including raw values and reasons; limit 1 to 500 |
| `POST /api/alerts/{id}/ack` | Acknowledge an active incident; 409 for missing or non-active |
| `POST /api/scenario` with `{"scenario":"slow"}` | Demo-only source injection; 403 in monitor mode, 422 for invalid scenario |
| `GET /api/report` | Downloadable plain text report, including latest 500 samples' rejection reasons |

The dashboard fetches once per second without overlapping refreshes. It renders data as text, leaves gaps in the trend for rejected samples, and marks the condition and measures unknown on HTTP failure. SQLite preserves the full local history; API and report history are explicitly bounded. No automatic pruning or export of the full database is performed.

## References

I followed the upstream [asyncua client example](https://opcua-asyncio.readthedocs.io/en/latest/usage/get-started/minimal-client.html), [server example](https://opcua-asyncio.readthedocs.io/en/latest/usage/get-started/minimal-server.html) and [DataValue API](https://opcua-asyncio.readthedocs.io/en/latest/api/asyncua.common.html). The [training bench](https://github.com/jackaI1/plc-filling-line) supplies the signal context; this monitor is an independent simulation.
