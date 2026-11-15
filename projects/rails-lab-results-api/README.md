# rails-lab-results-api

I built a small web service that stores lab results, refuses bad entries and keeps a permanent history of every correction, because I wanted to learn Ruby on Rails by rebuilding the rules I already have in my Java lab results service. Rails is a framework for building web services in the Ruby language. Running both side by side lets me compare how each one handles the same job: the [Java service](../java-lab-results-service/) is the original.

Here a "revision" is a version number: each correction must name the version it is changing, so a correction based on an old copy is turned away instead of overwriting newer work. Every saved change adds a line to an audit table (a history log) that cannot be edited or deleted. The sample IDs and values are invented.

## Start it

I use Ruby 3.4 (pinned in `.ruby-version`) and Bundler. The app uses SQLite, so there is no database server to install.

```sh
cd projects/rails-lab-results-api
bundle install
bin/rails db:prepare
bin/rails server -p 3000
```

Then, in another terminal, I can create a result and correct it:

```sh
curl -X POST localhost:3000/api/lab_results -H 'Content-Type: application/json' \
  -d '{"lab_result":{"sample_id":"S-1","assay":"ELISA","analyte":"IL-6","value":7,"unit":"ng/mL"}}'

# Correct revision 1 to 8. A correction must name the revision it is based on.
curl -X PATCH localhost:3000/api/lab_results/1 -H 'Content-Type: application/json' \
  -d '{"revision":1,"lab_result":{"value":8}}'

# Sending the same correction again, still based on revision 1, gets a 409 that reports revision 2.
# The history of the result shows each saved change:
curl localhost:3000/api/lab_results/1/audit_events
```

Stop the server with Ctrl+C.

## What the API does

| Request | What happens |
| --- | --- |
| `POST /api/lab_results` | Saves a new result at revision 1. Invalid input gets a 422 with the reason for each field. |
| `GET /api/lab_results` | Lists results. Add `?sample_id=S-1` to filter. |
| `GET /api/lab_results/:id` | Shows one result, or 404 if it does not exist. |
| `PATCH /api/lab_results/:id` | Applies a correction. Send the `revision` you are correcting; if someone changed it first, the answer is 409. |
| `GET /api/lab_results/:id/audit_events` | Shows the history: what was entered, and before and after values for each correction. |

The rules for a value: it is a number from 0 up to one million, the unit must be one of `ng/mL`, `ug/mL`, `mg/L`, `pg/mL` or `mmol/L`, and the sample ID may use letters, digits, `-` and `_`.

## How it works

Rails is a web framework: it turns a web request into a Ruby method call and turns the answer back into JSON. ActiveRecord is the part that maps a Ruby object to a database table.

- `app/models/lab_result.rb` holds the rules and the revision check. A correction runs inside a database transaction. It locks the row, compares the revision, saves the change, and writes one audit event. If any step fails, all of them are undone.
- `app/models/audit_event.rb` is the history. Rails will not update or destroy a saved row, and the database has triggers that reject any `UPDATE` or `DELETE` on the table even if something bypasses Rails.
- `app/controllers/api/lab_results_controller.rb` is the thin layer that reads the request and returns JSON.
- `db/migrate/` holds the two migrations that create the tables and triggers. `db/structure.sql` is the schema, including the triggers.

## Tests

I wrote RSpec tests in two kinds. Model specs check the rules, the revision conflict, the rollback after a failed correction, and that the audit table refuses changes. Request specs send real HTTP-style requests through the controllers and check the status codes and JSON.

```sh
bundle exec rspec
```

GitHub Actions runs these tests on every change to this folder, using the Ruby version in `.ruby-version`. The workflow file is `.github/workflows/rails-lab-results-api-ci.yml` in the repository root.

## Limits

This is a teaching copy, not a validated system. It has no login, so anyone who can reach the server can change a result. The audit trail is not signed and the database is a local file. I would add authentication and a proper database before using it for real samples.
