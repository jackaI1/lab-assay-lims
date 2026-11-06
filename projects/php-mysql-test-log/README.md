# php-mysql-test-log

I built a small test log to learn how the underlying idea works. This is a learning project.

## Try it

I use Docker, which packages the app and its database so they run together. Install Docker Desktop, or Docker with Colima on a Mac, and start its engine. Then run:

```sh
docker compose up --build -d app
```

Open **http://localhost:8088**. Enter a sample name, such as `Coating A`, and a measurement such as resistance: reading `101.2`, unit `ohm`, lower limit `95`, upper limit `105`. Use **Add measurement** for more readings, then **Save test run**. Select a saved run to see its readings and limits. The filter shows passing or failing runs.

To try a deliberately failing example without typing it in:

Reload the page and open `Coating A, rinse check`. Its thickness reading of 12.4 is above the upper limit of 12. The resistance reading passes, but the whole run fails.

```sh
docker compose down   # stops the app and database; keeps saved readings
```

I keep this as a local notebook. It has no sign-in or access controls, so I bind the web port to this computer only and use synthetic examples when sharing it. This is not a shared lab record system or a calibrated instrument.

## What gets saved

Each run has a sample name, optional notes, a recorded time in UTC, and 1 to 100 measurements. Each measurement has a name, unit, reading, lower limit and upper limit. A measurement name can appear only once per run.

I accept decimal values with up to 12 whole digits and 6 decimal places. I reject missing fields, reversed limits, duplicate names, non-numeric readings and requests over 256 KiB. A failed save leaves no partial run. Notes and sample names display as text, including characters such as `<` and `>`.

Runs are read-only after saving. If I need to repeat or correct a test, I record another run and explain it in the notes. I have not added editing, deletion, user accounts or an audit trail.

## How I put it together

PHP handles the web requests and the results page. MySQL stores two linked tables: one for runs and one for their measurements. PDO, PHP's database interface, uses prepared statements that send values separately from SQL commands. I disable simulated prepares so MySQL prepares the statements itself.

I save each run and all its measurements in a transaction, which either saves everything or saves nothing. MySQL's exact decimal columns and comparisons decide pass/fail without rounding through floating-point arithmetic. I store the limits with each reading so later tests cannot change what an earlier result meant.

The migration in `migrations/` creates the tables. Migrations are numbered database setup steps; the runner remembers which ones have finished and serializes simultaneous starts. The app runs them at startup. The saved data lives in Docker's `readings` volume, outside the app container.

For a host PHP 8.4+ installation, I can also run `composer install`, set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD`, run `php bin/migrate.php`, then `php -S 127.0.0.1:8088 -t public public/router.php`. This needs a running MySQL 8.4 database and PHP's `pdo_mysql` and `mbstring` extensions. Docker supplies those in the quick start.

## Tests and limits

I kept 4 files of test code and supporting test helpers in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `php-mysql-test-log-ci.yml`. Their commands use this folder and their triggers use its paths.
