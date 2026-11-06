"""Compare only resolved codes; uncertainty in either edition suppresses a claim."""

from collections import Counter
from decimal import Decimal


def compare(old, new):
    blocked = set(old["blocked_codes"]) | set(new["blocked_codes"])
    before = {r["code"]: r for r in old["items"] if r["code"] not in blocked}
    after = {r["code"]: r for r in new["items"] if r["code"] not in blocked}
    changes = []
    for code in sorted(before.keys() | after.keys()):
        a, b = before.get(code), after.get(code)
        kinds = []
        if a is None:
            kinds = ["added"]
        elif b is None:
            kinds = ["removed"]
        else:
            if Decimal(a["fee"]) != Decimal(b["fee"]):
                kinds.append("fee")
            if a["description"] != b["description"]:
                kinds.append("description")
            if a["prefix"] != b["prefix"]:
                kinds.append("prefix")
        if kinds:
            changes.append({"code": code, "kinds": kinds, "before": a, "after": b})
    counts = Counter(kind for change in changes for kind in change["kinds"])
    return {
        "schema_version": 1,
        "old": old["source"],
        "new": new["source"],
        "counts": {
            kind: counts[kind] for kind in ("added", "removed", "fee", "description", "prefix")
        },
        "accepted": {"old": len(old["items"]), "new": len(new["items"])},
        "review_counts": {"old": len(old["review"]), "new": len(new["review"])},
        "blocked_codes": sorted(blocked),
        "changes": changes,
        "review": {"old": old["review"], "new": new["review"]},
    }


def escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;")


def markdown(result, limit=None):
    counts = result["counts"]
    lines = [
        "# MSC edition comparison",
        "",
        f"[{result['old']['label']}]({result['old']['url']}) to "
        f"[{result['new']['label']}]({result['new']['url']})",
        "",
        "These are differences in confidently extracted fixed-price rows. "
        "They are not a complete list of policy or billing changes.",
        "",
        "| Added | Removed | Fee changed | Description changed | Prefix changed |",
        "| --- | --- | --- | --- | --- |",
        "| " + " | ".join(str(v) for v in counts.values()) + " |",
        "",
        f"Accepted codes: {result['accepted']['old']} old, {result['accepted']['new']} new. "
        f"Review entries: {result['review_counts']['old']} old, "
        f"{result['review_counts']['new']} new. "
        f"{len(result['blocked_codes'])} unresolved codes are excluded in both editions.",
        "",
        "Added/removed means present only in the resolved extraction of that edition. "
        "Check the PDF and review queue before treating it as an official addition or deletion. "
        "Links use physical PDF page numbers, not the printed section numbers.",
        "",
        "| Code | Change | Before | After |",
        "| --- | --- | --- | --- |",
    ]
    for change in result["changes"][:limit]:
        cells = []
        for side in ("before", "after"):
            row = change[side]
            cells.append(
                "Absent from resolved rows"
                if row is None
                else f"{escape(row['prefix'] + row['code'])}: {escape(row['description'])}; "
                f"${row['fee']} ([PDF p. {row['page']}]({row['url']}))"
            )
        lines.append(
            f"| {change['code']} | {', '.join(change['kinds'])} | " + " | ".join(cells) + " |"
        )
    if limit is not None and len(result["changes"]) > limit:
        lines.extend(
            [
                "",
                f"Showing {limit} of {len(result['changes'])} changed codes. "
                "See [full report](comparison.md) and [machine-readable report](comparison.json).",
            ]
        )
    lines.extend(
        [
            "",
            "## Review queue",
            "",
            "The JSON report includes every flagged block, its reason, raw text and PDF link. "
            "Examples below are deliberately unresolved.",
            "",
            "| Edition | Code | Reason | Source |",
            "| --- | --- | --- | --- |",
        ]
    )
    for edition in ("old", "new"):
        for row in result["review"][edition][:5]:
            lines.append(
                f"| {escape(result[edition]['label'])} | {row.get('code', '?')} | "
                f"{escape(row['reason'])} | [PDF p. {row['page']}]({row['url']}) |"
            )
    return "\n".join(lines) + "\n"
