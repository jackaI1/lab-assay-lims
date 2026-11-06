import json
from collections import Counter
from pathlib import Path

from fee_schedule_diff.compare import markdown


def test_saved_reports_share_counts_and_evidence():
    result = json.loads(Path("reports/comparison.json").read_text())
    assert len({r["code"] for r in result["changes"]}) == len(result["changes"])
    counts = Counter(kind for r in result["changes"] for kind in r["kinds"])
    assert dict(counts) == {k: v for k, v in result["counts"].items() if v}
    for change in result["changes"]:
        assert change["code"] not in result["blocked_codes"]
        for side, source in (("before", "old"), ("after", "new")):
            row = change[side]
            if row:
                assert row["url"] == result[source]["url"] + f"#page={row['page']}"
                assert 1 <= row["page"] <= result[source]["pages"]
    assert Path("reports/comparison.md").read_text() == markdown(result)
    assert Path("reports/summary.md").read_text() == markdown(result, limit=12)


def test_original_pdf_snapshots_match_public_source_fingerprints():
    import hashlib

    for source in json.loads(Path("data/sources.json").read_text()):
        path = Path("data/snapshots") / f"{source['label']}.pdf"
        assert path.read_bytes().startswith(b"%PDF-")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
