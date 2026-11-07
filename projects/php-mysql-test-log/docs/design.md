# Storage and API notes

## Requests

`POST /api/runs` accepts `application/json`, optionally with a charset. The body contains `sample` (1 to 120 characters), optional `notes` (up to 2000 characters), and a `measurements` array (1 to 100 entries). Each entry contains `name` (1 to 80 characters), `unit` (1 to 24 characters), and `value`, `lower_limit`, `upper_limit` as decimals. Text is trimmed; disallowed control characters are rejected. Decimal strings are preferred. Exponents, booleans, NaN, more than six fractional digits and numbers outside DECIMAL(18,6) are rejected. Unit labels are stored as supplied; there is no unit conversion.

Use unique measurement names within each run, ignoring letter case. Leading and trailing spaces are removed. MySQL also enforces a unique `(run_id, name)` key with binary comparison. Validation deliberately applies the stricter case-insensitive rule.

A successful save returns the complete run, status 201 and a `Location` header. Each reading has a boolean `passed` field, and a run's `passed` field is true only if every reading passes. Decimal values return as strings, and timestamps are UTC. List responses have `runs`, `page` and `has_more`. Lists contain summaries; use the detail endpoint for measurements. Pages have 20 entries in descending ID order. New entries can shift later pages; this is not a snapshot export.

Responses use 400 for malformed JSON, 404 for missing records or routes, 405 for unsupported methods (with `Allow`), 413 for oversized requests, 415 for the wrong content type, 422 for field errors and 503 when storage is unavailable. A 422 response includes a `fields` object whose keys identify the invalid inputs. Database details and SQL are never sent to the caller.

The API does not enable cross-origin requests, and writes require JSON. The results page escapes stored text, uses a restrictive content security policy and offers readable results without JavaScript. JavaScript is needed for the entry form. It builds the same JSON request as an instrument importer would.

## Database changes

`bin/migrate.php` takes a MySQL advisory lock, creates a migration-history table and applies numbered SQL files. MySQL commits table-definition changes immediately, so each migration must be safe to retry after an interruption. The initial migration uses `CREATE TABLE IF NOT EXISTS`. A future schema change should be a new file, not an edit to an applied migration. Migration access needs table-creation privileges.

The application never updates or deletes saved runs through HTTP. Each save opens a transaction, inserts the parent run, inserts its readings with native prepared statements, then commits. Any insert failure rolls everything back. Database foreign keys, uniqueness and a check on ordered limits complement request validation. Limits are copied into each saved reading rather than pointing at a mutable specification.

## Running and stopping

`docker compose up --build -d app` starts the local app on loopback port 8088 and a MySQL service with no published port. Override the web port with `APP_PORT=8090 docker compose up --build -d app`. The credentials in compose are public local-demo values, not credentials for another service. Use environment variables and separate credentials for another installation; never commit them.

`docker compose down` stops the notebook and keeps its named volume. Only `docker compose down --volumes` erases notebook readings. Back up data before deliberately erasing it. `bin/test-container.sh` uses a unique compose project with a separate temporary MySQL database, and an exit trap removes that project's containers and volumes even after a failure. The HTTP test server uses a process handle with teardown and shutdown cleanup. No browser is needed to run the tests.

This is a single-user local notebook. There is no authentication, authorization, network deployment, request deduplication, durable audit history, correction workflow or instrument calibration. A network failure after saving can leave the client unsure whether it saved; the form tells the user to check saved runs before retrying.
