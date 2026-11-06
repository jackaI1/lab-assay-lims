"""Print the README result table directly from a generated report."""

import json
from pathlib import Path

report = json.loads(Path("reports/ketoprofen/fit.json").read_text())
print(f"Observations: {len(report['time'])}; bootstrap draws per fit: {report['bootstrap']}")
print("| Model | Held-out error (percentage points) | AICc |")
print("|---|---:|---:|")
for name, result in report["scopes"][1]["models"].items():
    print(f"| {name.replace('_', ' ')} | {result['heldout_rmse_pp']:.2f} | {result['aicc']:.2f} |")
