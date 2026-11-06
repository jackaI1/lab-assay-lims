"""Copy generated results into README so its measurements have one source."""

import json
from pathlib import Path

from image_qc.report import acc, summary_table

metrics = json.loads(Path("reports/metrics.json").read_text())
d = metrics["dataset"]
block = (
    f"I evaluated {metrics['overall']['n']} photo versions from {d['split_counts']['test']} "
    f"held-out lesions, using {d['sources']} source images in total. "
    f"Without a gate, the baseline lesion accuracy was {acc(metrics['overall'])}; "
    f"on clean held-out images it was {acc(metrics['clean_baseline'])}.\n\n"
    + summary_table(metrics)
    + "\n\nThese numbers come from `uv run image-qc reproduce` and "
    "`uv run python scripts/update_readme.py`; the full counts are in "
    "[metrics.json](reports/metrics.json)."
)
p = Path("README.md")
text = p.read_text()
start, end = "<!-- BEGIN GENERATED RESULTS -->", "<!-- END GENERATED RESULTS -->"
p.write_text(text.split(start)[0] + start + "\n\n" + block + "\n\n" + end + text.split(end)[1])
