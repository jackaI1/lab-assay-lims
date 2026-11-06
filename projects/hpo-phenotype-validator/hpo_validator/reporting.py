"""Self-contained, escaped HTML reports with no external assets or scripts."""

from html import escape
import json


def html_document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(title)}</title><style>
body{{font:17px/1.6 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;
color:#172b35;background:#fbfcfa}}h1,h2{{line-height:1.2}}h1{{color:#205e54}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;text-align:left;
border-bottom:1px solid #c8d8d1;vertical-align:top;overflow-wrap:anywhere}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf3ef;padding:16px}}
a{{color:#205e54}}.scroll{{overflow-x:auto}}small{{color:#465c65}}
</style><main><h1>{escape(title)}</h1>{body}</main></html>\n"""


def validation_html(report: dict) -> str:
    status = "Ready to export" if report["exportable"] else "Review required; export blocked"
    rows = []
    for row in report["rows"]:
        result = row["resolution"]
        item = row["input"]
        suggestions = result.get("candidates", result.get("suggestions", []))
        cells = [
            str(row["index"]),
            item.get("id", item.get("text", "")),
            "Excluded" if item.get("excluded") else "Present",
            result["status"],
            result["id"] or "Unmapped",
            json.dumps(suggestions, ensure_ascii=False),
        ]
        rows.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in cells) + "</tr>")
    return html_document(
        f"Fictional subject: {report['subject_id']}",
        f"""
<p><strong>{status}</strong>. This is a fictional example, not medical advice.</p>
<p>HPO version: {escape(report["ontology_version"])}. Confidence scores describe lexical
similarity, not clinical probability. Only unique exact labels and exact synonyms map automatically.</p>
<p>Unresolved rows: {len(report["review_rows"])}; contradictions: {len(report["contradictions"])};
redundant pairs: {len(report["redundant_pairs"])}; duplicate rows: {len(report["duplicates"])}.</p>
<h2>Every input row</h2><div class="scroll"><table><thead><tr>
<th>Row (zero-based)</th><th>Input</th><th>Assertion</th><th>Decision</th><th>Accepted ID</th>
<th>Suggestions</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<h2>Contradictions and redundant pairs</h2>
<pre>{
            escape(
                json.dumps(
                    {
                        "contradictions": report["contradictions"],
                        "redundant_pairs": report["redundant_pairs"],
                    },
                    indent=2,
                )
            )
        }</pre>
<h2>Cleaned features</h2><p>These are provisional while review is required. Correct the source
JSON and rerun to export; the tool does not choose between conflicting assertions.</p>
<pre>{escape(json.dumps(report["cleaned"], indent=2, ensure_ascii=False))}</pre>
<h2>Audit trail</h2><p>Includes replacement paths, review rows and ontology checksum.</p>
<pre>{escape(json.dumps(report, indent=2, ensure_ascii=False))}</pre>""",
    )
