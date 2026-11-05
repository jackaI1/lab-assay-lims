"""Reproduce the standard-only subset from ELISAtools, excluding all sample wells."""

import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen

COMMIT = "d28128c9c29c52a9e52c7896e500010536cdcd0b"
BASE = f"https://raw.githubusercontent.com/cran/ELISAtools/{COMMIT}/inst/extdata/"
OUT = Path(__file__).resolve().parents[1] / "data" / "public"


def main():
    content = urlopen(BASE + "Assay_2.txt", timeout=30).read()
    rows = list(csv.reader(io.StringIO(content.decode("latin1")), delimiter="\t"))
    header = next(i for i, row in enumerate(rows) if len(row) > 2 and row[2] == "A1")
    readings = [r for r in rows[header + 1 :] if len(r) > 2 and r[1].strip() and r[2].strip()][:2]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["well", "concentration", "signal_450", "reference_620", "signal"])
    for letter, concentration in zip("ABCDEFGH", [3000, 1500, 750, 375, 187.5, 93.8, 46.9, 0], strict=True):
        for column in [1, 2, 3]:
            well = f"{letter}{column}"
            index = rows[header].index(well)
            raw, reference = [float(r[index]) for r in readings]
            writer.writerow([well, concentration, raw, reference, round(raw - reference, 7)])
    OUT.mkdir(exist_ok=True, parents=True)
    derived = output.getvalue().encode()
    (OUT / "elisatools-standards.csv").write_bytes(derived)
    provenance = dict(
        source=BASE + "Assay_2.txt",
        annotation=BASE + "AnExp_2plate.txt",
        concentrations=BASE + "stdConc.txt",
        commit=COMMIT,
        source_sha256=hashlib.sha256(content).hexdigest(),
        subset_sha256=hashlib.sha256(derived).hexdigest(),
        transformation="First plate; A1:H3 only (24 standard wells); signal = 450 nm minus 620 nm. No sample wells retained.",
        units="Concentration units not specified in source; retained as source units.",
        license="MIT; Copyright 2019 Feng Feng. See LICENSE-ELISAtools.txt.",
        limitation="Calibration-only data; no independent positive/negative controls and no unknown ground truth.",
    )
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Wrote 24 public standard readings and provenance.")


if __name__ == "__main__":
    main()
