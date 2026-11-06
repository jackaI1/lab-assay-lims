"""Print the saved report figures without dumping source text or the review queue."""

import json
from pathlib import Path

comparison = json.loads(Path("reports/comparison.json").read_text())
accuracy = json.loads(Path("reports/accuracy.json").read_text())
print(
    json.dumps(
        {
            "editions": {
                side: {"label": comparison[side]["label"], "pages": comparison[side]["pages"]}
                for side in ("old", "new")
            },
            "accepted_codes": comparison["accepted"],
            "changed_codes": len(comparison["changes"]),
            "changes": comparison["counts"],
            "review_entries": comparison["review_counts"],
            "unresolved_codes": len(comparison["blocked_codes"]),
            "accuracy": accuracy["metrics"],
        },
        indent=2,
    )
)
