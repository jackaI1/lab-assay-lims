# Lab assay notebook

I built a small notebook for plate-based assays because I wanted one place to connect a sample's identity to its plate-reader result. A spreadsheet can hold the numbers, but it is easy to lose which reagent lot I used, where a sample went, or which file produced the final concentration.

I register samples and reagent lots, assign the wells on a plate, and import the reader's measurements. The notebook subtracts the background, uses known standards to estimate sample concentrations, and highlights results that need another look. It also generates Python instructions for an Opentrons OT-2 liquid-handling robot.

**Try it locally:** run the commands below, open the page, and click **Open synthetic demo**. The demo has two samples with known answers, 7 and 12 ng/mL. I can inspect each well, compare the recovered concentrations, download the results, and prepare a robot plan without an instrument or an account.

![Plate map, fitted standard curve and recovered synthetic sample concentrations](docs/plate-review.png)

## Run it

I use Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/) to install the pinned dependencies.

```sh
git clone https://github.com/jackaI1/lab-assay-lims.git
cd lab-assay-lims
uv sync --locked --extra dev --extra robot
uv run uvicorn lab_assay.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Stop the server with Ctrl+C. My records stay in `assays.sqlite`; I can choose another file with the `LIMS_DB` environment variable. This is a local research demonstration with no login, so I keep it bound to this computer.

## Follow an experiment

1. **Register the materials.** Add a sample ID and description, then a reagent lot with an expiry date.
2. **Save the plate map.** Give the plate a name and concentration unit. Assign wells to blanks, known standards, controls, or registered samples. A sample's dilution factor corrects the concentration back to the original sample.
3. **Import a reader file.** Use CSV or XLSX with `well,signal` columns, or a full 8-by-12 matrix. The file must match the saved map exactly. I provide an [example CSV](data/synthetic-reader.csv) and [map](data/synthetic-map.json).
4. **Calculate and review.** Choose a straight-line or curved standard response. Review the curve, repeated-well variation and control separation. An out-of-range sample stays unreported instead of getting a guessed concentration.
5. **Save the evidence.** Download the results CSV and keep the original import and saved analysis. The history records every registration, import, analysis and protocol generation.

I made saved records immutable: a correction gets a new ID or plate name rather than overwriting an earlier result. Each saved change and its audit entry are written in the same database transaction. The API reference is at `/docs` while the app is running.

## Prepare an OT-2 plan

On the page, I choose **Serial dilution** or **Plate transfers**, enter volumes, and download `assay-protocol.py`. A serial dilution progressively reduces concentration along one row. A transfer plan moves declared volumes from a source plate into an empty destination plate, using a fresh tip for each move.

```sh
uv run opentrons_simulate assay-protocol.py
```

The generator checks pipette limits, well capacity, tip count and source depletion before producing a file. The exported plan lists the deck positions, stock and diluent amounts, and expected final volumes. The web page does **not** run simulation itself; I run the command on the exact exported file. Both protocol types are exercised with the real simulator in the test suite and CI.

I have tested the instructions in software, not on a physical robot. Liquid heights, reservoir dead volume, labware, mixing and calibration still need a bench check. Preparation plans are linked to a plate for traceability, but I do not infer their transfers from the analytical plate map.

## Data and calculations

My default plate is **synthetic**, generated with seed 2026 and known sample concentrations. It includes triplicate standards, blanks, independent controls and diluted samples. The generator can also produce deliberately noisy controls. I use it to test whether the fitted curve recovers the known concentrations within 4%.

I also included 24 public, measured calibration wells from Feng Feng's MIT-licensed **ELISAtools** example. I retained only standards, subtracted the 620 nm reference from the 450 nm signal, and recorded the source commit and file hashes. The public example lacks independent controls and known unknown-sample answers, so I use it to test calibration, not to claim a validated complete assay. [Data provenance and reuse terms](data/README.md).

For a curved response I use a **four-parameter logistic curve (4PL)**: a smooth response with two plateaus, a midpoint and a slope. I support increasing and decreasing responses. **CV%** measures variation between repeated wells, and **Z-prime** measures how clearly positive and negative controls separate. The default review limits are R² ≥ 0.98 for curve fit, CV ≤ 20%, and Z-prime ≥ 0.5. These are demonstration limits, not a validated laboratory acceptance procedure. [Equations, import formats and failure rules](docs/assay-method.md).

## Inside the project

- `lab_assay/store.py` keeps related samples, lots, wells, imports, results and audit events in SQLite.
- `lab_assay/app.py` serves the page and FastAPI endpoints, with input validation and download routes.
- `lab_assay/importers.py` reads normalized reader exports; `analysis.py` fits curves and calculates results.
- `lab_assay/protocols.py` produces standalone Opentrons API v2 instructions and volume plans.
- `lab_assay/static/` contains the page, forms, plate map and curve plot. [API walkthrough](docs/api-example.md).

The audit trail is append-only at the database level, with original import bytes and SHA-256 fingerprints retained. It is not a regulated LIMS: there are no authenticated signatures, access roles, inventory consumption records or protection against a database administrator changing the schema. Each plate references one reagent lot. I also do not estimate concentration uncertainty or support kinetic/multi-wavelength vendor exports directly.

## Checks I run

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
# Optional real-browser workflow, with its own temporary server and cleanup:
uv sync --locked --extra dev --extra robot --extra browser
uv run playwright install chromium
uv run python scripts/browser_check.py
```

My local run passes **51 tests**, including four real Opentrons simulator runs. The seeded curve recovers 6.9989 and 12.0007 ng/mL for the 7 and 12 ng/mL samples, with Z-prime 0.9894. GitHub Actions runs the same unit and API tests on Python 3.11 and 3.12, plus the browser workflow. Tests cover concentration recovery, public calibration, malformed CSV/XLSX files, invalid record links, immutable history, expired lots, failing controls and impossible liquid transfers. The browser check registers materials, saves a map, imports a plate, calculates results, downloads files and checks desktop/mobile layouts. It closes its browser and temporary server in a `finally` block and checks that the port is closed.
