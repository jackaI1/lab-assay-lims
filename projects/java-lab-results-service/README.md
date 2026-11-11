# java-lab-results-service

I built a small service for lab measurements because I wanted to learn how to keep a result and its corrections together. It records a measurement, checks that a correction is based on the latest version, and keeps the earlier values in a history. I can run the example below with invented data and see the full workflow without an AWS account.

The example patient and sample identifiers are invented.

## Try it locally

I use Docker with Compose to run the service and its database together. Install Docker Desktop or another running Docker engine with the Compose plugin. The walkthrough script also needs Python 3 and OpenSSL, which the setup script uses to generate local passwords.

```sh
./scripts/setup-demo.sh
docker compose up --build --wait
./scripts/demo.sh
```

The first build downloads dependencies and may take a few minutes. The script exercises recording, reading, correction, history, export and filtering, including requests that should be refused. The service listens at `http://127.0.0.1:8080`. Compose loads one synthetic glucose result with ID `11111111-1111-4111-8111-111111111111`.

To look at one kind of test for one invented patient, I ask the list endpoint for it. The `setup-demo.sh` script wrote the reader password into `.env`, so I read it from there:

```sh
READER_PASSWORD=$(grep '^READER_PASSWORD=' .env | cut -d= -f2-)
curl -u "reader:$READER_PASSWORD" 'http://127.0.0.1:8080/api/results?patientId=SYN-DEMO-002&test=POTASSIUM'
```

Both filters are optional. `test` accepts only `GLUCOSE`, `POTASSIUM` or `HEMOGLOBIN`; any other name returns `400`. The list is newest first and returns up to `limit` results (1 to 100, default 50).

To read older results, I add `offset` to skip that many rows. With pages of one, the second result is `limit=1&offset=1`, the third is `limit=1&offset=2`, and so on. I keep asking for the next page until one comes back shorter than `limit`; the service does not send a total count. A negative `offset` returns `400`. The demo script creates two or more results for `SYN-DEMO-PAGE`, so that patient is the one to page through.

```sh
curl -u "reader:$READER_PASSWORD" 'http://127.0.0.1:8080/api/results?patientId=SYN-DEMO-PAGE&limit=1&offset=1'
```

## Choose MySQL instead

I added a second database option so I can run the same measurement workflow where MySQL is already available. PostgreSQL remains the default. For a separate MySQL 8.4 demo, I use the same setup script and add an override file, which replaces the database container and selects the matching app settings:

```sh
./scripts/setup-demo.sh
docker compose -p lab-mysql -f compose.yaml -f compose.mysql.yaml up --build --wait
./scripts/demo.sh
```

Stop the PostgreSQL demo first if it uses port 8080. Both options load the same invented example and accept all the commands below. Each keeps its own database volume. To stop MySQL while keeping its records:

```sh
docker compose -p lab-mysql -f compose.yaml -f compose.mysql.yaml down
```

Add `-v` to that last command only when I want to erase the MySQL demo. Switching options selects a different database; it does not transfer existing records between databases.

## Choose SQL Server instead

I can also run the same workflow on Microsoft SQL Server. On a Linux x86-64 computer with a Docker engine and at least 2 GB available for the database, I use:

```sh
./scripts/setup-demo.sh
docker compose -p lab-sqlserver -f compose.yaml -f compose.sqlserver.yaml up --build --wait
./scripts/demo.sh
docker compose -p lab-sqlserver -f compose.yaml -f compose.sqlserver.yaml down
```

This disposable demo uses SQL Server's `master` database and administrator account for simplicity. The SQL Server image requires accepting Microsoft's license, which the Compose file does. Add `-v` to the final command only to erase the demo data. For an existing server, create a separate database and account, set `SPRING_PROFILES_ACTIVE=sqlserver`, and supply `DB_URL`, `DB_USER`, `DB_PASSWORD`, `READER_PASSWORD`, and `TECHNICIAN_PASSWORD`. Use a trusted TLS certificate instead of the demo's `trustServerCertificate` setting.

## Practice a cloud deployment

The sandbox uses LocalStack and Moto to test the cloud setup, with real app and
PostgreSQL containers and a local forwarding server. It does not run managed
AWS services. The [deployment guide](docs/aws-deployment.md) explains the
architecture, exact Linux commands, what is tested, and how I would move it to
an AWS staging account with HTTPS, a private database and stored passwords.

## What I accept

| Test name in a request | Measurement | Fixed unit | LOINC test code |
| --- | --- | --- | --- |
| `GLUCOSE` | Glucose in serum or plasma | mmol/L | 14749-6 |
| `POTASSIUM` | Potassium in serum or plasma | mmol/L | 2823-3 |
| `HEMOGLOBIN` | Hemoglobin in blood | g/dL | 718-7 |

LOINC provides standard identifiers for tests. The export uses UCUM, standard codes for measurement units. I keep each test and unit paired in the service rather than trusting a unit supplied by a caller.

Patient identifiers must start with `SYN-` and specimen identifiers with `LAB-`, followed by 1 to 32 uppercase letters, digits or hyphens. Values must be from 0 to 1,000,000 with up to four decimal places, and the observation time cannot be in the future. These are input and storage checks, not clinical reference ranges. Invalid input returns `400`, missing results return `404`, absent or incorrect credentials return `401`, and a reader trying to change data gets `403`.

## Stop or reset

```sh
docker compose down       # stop; keep the measurements
docker compose down -v    # stop and erase this demo's database
```

If port 8080 is occupied, use `APP_PORT=18080 docker compose up --build --wait`, then `APP_PORT=18080 ./scripts/demo.sh`. Use that port in the curl commands too. If the build cannot connect to Docker, start the Docker engine first. Keep `.env` while keeping the database volume: generating new database credentials does not change an existing database password.

## How I put it together

I use Java 21 and Spring Boot for the REST API, an interface built around HTTP requests. Spring Security checks the reader and technician roles on each request. PostgreSQL, MySQL or SQL Server stores the results. Flyway applies numbered SQL migrations, the files that create and update the database structure. Each database has its own SQL files.

`ResultService` uses plain JDBC, Java's database interface, with prepared statements that keep supplied values separate from SQL commands. HikariCP keeps up to five reusable database connections in a pool. Spring binds a pooled connection to each transaction; statements and result sets close after use, and the connection returns to the pool. A correction updates the current value only when the expected revision matches, then adds a complete audit snapshot in the same transaction. If storing the history fails, the value change rolls back. A database trigger rejects updates and deletes of history entries. HAPI FHIR serializes the current result as an R4 Observation with its test, quantity, subject and sample identifiers, timestamps and revision.

The `lab_result` table holds the latest measurement: its ID, invented patient and specimen IDs, test, decimal value, observation time, status, revision and last update time. `result_audit` holds the result ID and revision as a combined key, the account, reason, time and complete JSON snapshot. All three databases enforce value ranges and identifier formats and index recent results by patient and observation time. MySQL uses InnoDB tables for transactions, text UUIDs for IDs, UTC date/time columns with six decimal places, and native JSON snapshots; PostgreSQL keeps its native UUID, time-zone-aware timestamp and JSONB columns.

For an existing database, I create an empty `labresults` database and provide its address and credentials through environment variables. I leave the `demo` profile off so no example rows are inserted:

```sh
# Set DB_USER, DB_PASSWORD, READER_PASSWORD and TECHNICIAN_PASSWORD locally first.
SPRING_PROFILES_ACTIVE=mysql DB_URL=jdbc:mysql://localhost:3306/labresults ./mvnw spring-boot:run
# PostgreSQL: omit SPRING_PROFILES_ACTIVE and use DB_URL=jdbc:postgresql://localhost:5432/labresults
```

SQL Server uses `uniqueidentifier`, UTC `datetime2` and JSON-validated text. Its parameterized `revise_result` stored procedure checks the revision before updating; the service inserts the audit snapshot in the same transaction. A trigger blocks changes to history. Unlike PostgreSQL, SQL Server uses `OFFSET ... FETCH` for bounded lists and stores JSON as text.

The MySQL profile sets the connection time zone to UTC. I preserve instants when reading and writing timestamps, including when Java runs in a different time zone. The migration account needs table, index and trigger creation permissions for Flyway. MySQL 8.4 enables binary logging by default, so an administrator must also permit trigger creation: the local Compose demo and tests set `log_bin_trust_function_creators=1`. On an existing server I would ask its administrator to choose that setting or run the migrations with an appropriately privileged account, as described in [MySQL's trigger permissions](https://dev.mysql.com/doc/refman/8.4/en/create-trigger.html). A separate restricted runtime account would be a deployment improvement.

I explain the request flow and tradeoffs in [docs/design.md](docs/design.md). The extra synthetic migration runs only with the `demo` profile used by Compose. I keep that profile's database separate from databases created without demo data.

## Limits I would address before real use

This is a local demonstration with synthetic data, not a system for patient care. Identifier prefixes cannot guarantee that someone has avoided personal data. The two shared accounts identify demo roles rather than individual people. HTTP Basic sends credentials on each request, so I would require TLS and individual accounts from an identity provider before deployment. I would also need authorization by organization or patient, operational monitoring, backups and retention rules.

A database administrator can disable the audit trigger. The FHIR output is an R4 resource export, not a complete FHIR server or proof of conformance to a particular clinical profile. The list uses offset paging, so a very deep page can get slower on a large table. A new result inserted while I page can shift later rows by one.

## Tests

Run the quick test on your own computer first. It needs Java 21 and Maven, but no database or Docker:

```sh
./mvnw -Dtest=FhirExporterTest test
```

The full tests start a real PostgreSQL, MySQL or SQL Server container, so they need Docker. GitHub Actions runs them for each push. The workflow file is [java-lab-results-service-ci.yml](../../.github/workflows/java-lab-results-service-ci.yml), and its run history is on the repository's Actions page. Each database job then starts the Compose demo and runs the HTTP script.

The shared storage tests cover validation, the role checks, corrections, the stale-revision conflict, the concurrent correction race, history, the FHIR export, the patient and test filter, and paging through a patient's results without skipping or repeating any. The `FhirExporterTest` class checks the export without a database.

In the last CI run on this branch, each database job ran 29 tests: 25 storage tests against that database and 4 FHIR tests. All 29 passed in each of the PostgreSQL, MySQL and SQL Server jobs, with no failures or errors. The Compose demo HTTP script passed 17 checks in each job.

The project checks run from this directory through the path-filtered workflow `java-lab-results-service-ci.yml`.
