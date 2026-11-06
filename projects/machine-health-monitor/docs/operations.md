# Running and stopping the monitor

## A separate source and observer

No account or hardware is needed. In one terminal, run the demo source and its dashboard:

```sh
uv run machine-health demo --port 8765 --opc-port 4840 --db .build/source.sqlite3
```

In another terminal, run an independent read-only observer:

```sh
uv run machine-health monitor --endpoint opc.tcp://127.0.0.1:4840/filling-line/ \
  --port 8766 --db .build/observer.sqlite3
```

Open http://127.0.0.1:8765 to change scenarios and http://127.0.0.1:8766 to see the independent observer. Monitor mode does not expose source controls. Stop the first process with Ctrl+C to break the OPC UA connection. The observer becomes unknown, retains rejected attempts and opens one connection incident. Restart the first command to recover. A fresh source restarts its counters; the observer excludes the reset interval and resumes on following intervals.

## Ownership and shutdown

Each command stays in its terminal. Ctrl+C cancels the collector, closes its OPC UA session, cancels the publisher, closes the simulator listener if present, shuts down HTTP and closes SQLite. The demo uses ports 8765 and 4840 by default. The second observer uses 8766 only. If a port is occupied, choose a new port instead of stopping an unrelated process.

To inspect a listener you started:

```sh
lsof -nP -iTCP:8765 -sTCP:LISTEN
lsof -nP -iTCP:4840 -sTCP:LISTEN
```

After Ctrl+C neither should show that process. The automated browser test records its child PID, start time, ports and scoped shutdown command, then waits for exit and checks that its two ports are closed in `finally`. It closes its page, context and browser on both success and failure. Network tests use server/session context managers, not detached services.

## Saved evidence

The database contains `readings` and `alerts` tables. Keep one database per source so counter and timestamp histories do not get mixed. Restart with the same database to retain acknowledgements and deduplication. Copy or archive the database only after stopping the service, or use SQLite's backup interface while it is running. The report is a current-window summary with bounded recent history, not a full database backup.

Do not commit the database, local reports, credentials or machine identifiers. The repository ignores the default data directory and SQLite database files. For a fresh exercise, use a new `--db` path instead of deleting history.

## Practical boundaries

The source and UI are local training fixtures. OPC UA uses NoSecurity and no credentials. The collector does not currently configure certificate authentication, encryption, alarms-and-conditions subscriptions or arbitrary NodeId mapping. Use an isolated trusted training network, not an exposed endpoint or production line. Real integration needs a secured adapter and a validated signal contract. No third-party account, secret placeholder or paid service is needed.

Polling runs every second by default with a two-second request timeout, then retries. The 20-second window is intentionally short. A single late or incoherent frame is retained rather than interpolated. Validate longer windows and alarm thresholds for the actual operating pattern before treating the report as maintenance evidence.
