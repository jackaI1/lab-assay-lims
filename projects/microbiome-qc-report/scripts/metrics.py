#!/usr/bin/env python3
"""Print README result numbers directly from the saved run summaries."""
import json
from pathlib import Path

main=json.loads(Path('reports/demo/summary.json').read_text())
fixture=json.loads(Path('reports/fixture/summary.json').read_text())
print(f"The saved public run processed {main['raw_pairs']:,} raw read pairs, retained "
      f"{main['nonchimeric_pairs']:,} non-chimeric pairs and inferred {main['asvs']} variants. "
      f"{main['eligible_samples']} biological samples qualified for comparison at "
      f"{main['depth']:,} pairs per sample. The saved CI fixture processed "
      f"{fixture['raw_pairs']:,} raw pairs and excluded {fixture['too_shallow_samples']} "
      "deliberately shallow technical subset. These numbers come from `python scripts/metrics.py`; "
      "the summaries and supporting tables are committed with the reports.")
