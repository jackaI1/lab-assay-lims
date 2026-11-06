# machine-health-monitor

I built a machine health monitor to learn how the underlying idea works. This is a learning project.

## Try the other faults

The scenario selector includes repeated conveyor faults, a stopped motor, old timestamps, a missing cycle time, an impossible cycle time, a frozen sample and bad sensor quality. Each scenario goes through the same OPC UA connection as normal readings. OPC UA is a protocol for exchanging machine data between equipment and software.

For a missing or stale reading, the history shows the rejection reason and the current condition becomes unknown. Restore normal operation to recover. For a stopped motor or repeated faults, availability and fault-rate alerts may take the full observation window to clear.

The service stores its history in `.build/health.sqlite3`, a local SQLite database. Use a separate file for another practice session:

```sh
uv run machine-health demo --db .build/practice.sqlite3 --port 8766 --opc-port 4841
```

The two port options change the dashboard and simulator addresses. The service runs in the foreground and closes both listeners when stopped. It does not install a background worker.

## Change the rules

```sh
cp config.example.json my-rules.json
uv run machine-health demo --config my-rules.json
```

The defaults use a 20-second window, a two-second target cycle, a three-second stale limit and one-second polling. An alert opens above 25% cycle-time drift, above five new faults per minute, or below 80% availability. A current fault code also opens an immediate alert. These short settings make the demonstration easy to try; I would choose an appropriate window and thresholds for a particular line.

## Read a separate source

I modelled the motor state, completed bottle count and fault meanings on my [PLC filling-line training bench](https://github.com/jackaI1/plc-filling-line). A PLC is the controller that reads machine inputs and decides which outputs should run. This project supplies its own OPC UA simulator; it does not run or connect to that bench's compiled controller. Cycle time and the cumulative fault counter are additional monitoring signals.

To read another compatible training server:

```sh
uv run machine-health monitor \
  --endpoint opc.tcp://127.0.0.1:4840/filling-line/ \
  --db .build/separate-source.sqlite3
```

Run that server separately first. Monitor mode has no fault-injection controls and never writes to machine tags. The dashboard remains local to this computer; the data source can be on a trusted network. [Design and source contract](docs/design.md) explains the exact tag types, timestamps, calculations, API and limitations. [Operating notes](docs/operations.md) covers a two-process demo, disconnect recovery, saved data and stopping the service.

## Design and limits

The Python collector uses `asyncua` to read the five OPC UA tags in one request. It checks values, source timestamps and status codes before accepting a complete sample. SQLite retains the original values, receive time, source time and rejection reasons. Only accepted samples contribute to the calculations. A counter reset excludes the affected interval instead of inventing production or faults.

FastAPI serves the dashboard and a small local API. The report includes the current condition, coverage, rule settings, incident history and recent rejection reasons. There are no email notifications, cloud services or physical PLC connections in the demo. This is a practice monitor, not a safety system, certified production tool or complete equipment-effectiveness calculation. The training source uses an unencrypted connection. Real equipment would need its own integration, validated limits, access controls and certificate security.

## Tests and limits

There are 6 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
