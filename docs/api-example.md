# A reproducible API run

Start the service as described in the README. These commands create only synthetic records:

```sh
curl -X POST http://127.0.0.1:8000/api/demo
curl http://127.0.0.1:8000/api/plates
curl http://127.0.0.1:8000/api/audit
```

The first response supplies `plate_id` and `analysis_id`. Read a saved result at `/api/analyses/{analysis_id}` or download `/api/analyses/{analysis_id}/csv`. Read `/api/plates/{plate_id}` for well assignments, imports and analysis IDs. The original bytes are available at `/api/imports/{import_id}/file`.

To create your own records, `POST /api/samples` with `id,description`, `POST /api/lots` with `id,reagent,expires_on`, and `POST /api/plates` with `name,lot_id,unit,wells`. A well has `well,role`; standards also have `concentration`, and samples have `sample_id,dilution_factor`. Dates use ISO `YYYY-MM-DD`. See the interactive `/docs` page for all schemas.

```sh
curl -X POST http://127.0.0.1:8000/api/plates/1/protocols \
  -H 'Content-Type: application/json' \
  -d '{"kind":"serial","steps":8,"factor":2,"final_volume":80,"row":"A"}'
```

The protocol response contains a record ID, Python source and volume plan. Download `/api/protocols/{id}/file`, then run `uv run opentrons_simulate assay-protocol.py`. A transfer request uses `kind: "transfer"`, `moves: [{"source":"A1","destination":"B1","volume":50}]`, and `source_volumes: {"A1":150}`.

Writes default to actor `local-user`. An `X-Actor` header can label an experimenter, but it is a self-declared label, not authentication. The service restricts Host and browser Origin headers for local use. It provides no remote deployment or user-access security guarantee.

For an offline seeded database and files:

```sh
uv run python -m lab_assay.demo --db demo.sqlite --export demo-output
LIMS_DB=demo.sqlite uv run uvicorn lab_assay.app:app --host 127.0.0.1
```

Each record is immutable. Use a new ID for a corrected record. Back up the SQLite file while the app is stopped, or use SQLite's online backup API. No real biological or personal records are included in this repository.
