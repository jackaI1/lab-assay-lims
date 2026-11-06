"""A printable, dependency-free summary backed by the adjacent JSON evidence."""

import json
from html import escape
from pathlib import Path

DESCRIPTIONS = {
    "flat": (
        "Flat sensors",
        "Little or no changing signal",
        "Check sensor contact; exclude affected sensors.",
    ),
    "noisy": (
        "Noisy sensors",
        "Unusually large or erratic signal",
        "Inspect contact and affected sensors.",
    ),
    "line": (
        "Electrical interference",
        "A strong repeating mains-frequency signal",
        "Check grounding and power sources.",
    ),
    "blink": (
        "Possible eye blinks",
        "Large slow changes at forehead sensors",
        "Inspect marked times before analysis.",
    ),
    "muscle": (
        "Possible muscle tension",
        "Extra fast activity in the signal",
        "Inspect marked times for tension or movement.",
    ),
}


def render_report(result):
    def e(value):
        return escape(str(value), quote=True)

    rows = []
    timeline = []
    for index, (kind, (title, meaning, action)) in enumerate(DESCRIPTIONS.items()):
        affected = sorted({c for w in result["windows"] for c in w["flags"][kind]})
        labels = ", ".join(affected) or "None flagged"
        if len(affected) == len(result["channels"]):
            labels = f"All {len(affected)} sensors"
        elif len(affected) > 6:
            labels = f"{len(affected)} sensors: " + ", ".join(affected[:4]) + "; full list in JSON"
        if kind == "blink" and any("not assessed" in r for r in result["reasons"]):
            labels = "Not assessed: forehead sensors absent"
        rows.append(
            f"<tr><th>{title}<small>{meaning}</small></th>"
            f"<td>{result['counts'][kind]} / {len(result['windows'])}</td>"
            f"<td>{e(labels)}</td><td>{action}</td></tr>"
        )
        timeline.append(f'<text x="0" y="{20 + index * 24}">{title}</text>')
        for w in result["windows"]:
            x = 175 + 520 * w["start"] / result["duration_seconds"]
            width = 520 * (w["stop"] - w["start"]) / result["duration_seconds"]
            color = "#b74c2d" if w["flags"][kind] else "#dce7df"
            timeline.append(
                f'<rect x="{x:.2f}" y="{7 + index * 24}" '
                f'width="{width:.2f}" height="17" fill="{color}"/>'
            )
    reasons = "".join(f"<li>{e(r)}</li>" for r in result["reasons"])
    next_step = {
        "usable": "Continue with a visual signal review before analysis.",
        "usable with caveats": "Review the flagged sensors and times before using this recording.",
        "not usable": "Do not use the full recording as-is. Inspect it and decide whether any part can be recovered.",
    }[result["status"]]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EEG quality | {e(result["session"])}</title><style>
*{{box-sizing:border-box}}body{{font:15px/1.45 system-ui,sans-serif;color:#20342f;background:#edf1ed;margin:0}}
main{{max-width:980px;margin:24px auto;padding:32px;background:white;border-top:8px solid #245447}}
h1{{font-size:28px;margin:6px 0}}h2{{font-size:17px;margin:20px 0 8px}}p{{margin:8px 0}}
.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:12px}}.decision{{background:#edf3ef;padding:16px;margin:16px 0}}
strong.score{{font-size:32px;margin-right:16px}}small{{display:block;font-weight:400;color:#52655e}}
table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{text-align:left;vertical-align:top;padding:8px 6px;border-bottom:1px solid #d4dfd7}}th{{width:25%}}
ul{{padding-left:20px;font-size:13px}}svg{{width:100%;height:auto;font:12px system-ui}}footer{{font-size:12px;border-top:1px solid #ccd8ce;margin-top:18px;padding-top:10px}}
@media (max-width:600px){{main{{margin:0;padding:18px}}table,tbody,tr,td,th{{display:block;width:100%}}thead{{display:none}}tr{{border-bottom:1px solid #ccd8ce;padding:10px 0}}td,th{{border:0;padding:4px}}td:nth-child(2)::before{{content:"Flagged windows: "}}td:nth-child(3)::before{{content:"Sensors: "}}svg{{min-height:140px}}}}
@media print{{@page{{size:A4;margin:12mm}}body{{background:white;font-size:12px}}main{{margin:0;padding:12px;max-width:none}}h1{{font-size:23px}}h2{{margin:12px 0 6px}}p{{margin:5px 0}}ul{{font-size:11px;margin:6px 0}}footer{{font-size:10px;margin-top:10px}}.decision{{padding:10px;margin:12px 0}}td,th{{padding:6px}}.decision{{break-inside:avoid}}}}
</style></head><body><main>
<div class="eyebrow">Recording quality check · research use</div>
<h1>{e(result["session"])}</h1>
<p>{result["duration_seconds"]:.1f} seconds · {len(result["channels"])} sensors · {result["sfreq"]:g} samples/second · {result["line_hz"]} Hz electrical check</p>
<div class="decision"><strong class="score">{result["score"]:g}/100</strong><b>{e(result["status"].capitalize())}</b><p>{next_step}</p></div>
<h2>Why this result?</h2><ul>{reasons}</ul>
<h2>What needs attention?</h2><table><thead><tr><th>Check</th><th>Flagged windows</th><th>Sensors</th><th>Suggested action</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<h2>When did it happen?</h2><p><small>Left to right: start to end ({result["duration_seconds"]:.1f} s). Rust blocks flag a time window; pale blocks cross no threshold.</small></p>
<svg viewBox="0 0 710 132" role="img" aria-label="Artifact screening timeline">{"".join(timeline)}</svg>
<footer><b>Not a diagnostic tool.</b> These rules flag suspicious signals, not confirmed causes or illness. Forehead sensors stand in for eye sensors; fast brain activity can resemble muscle tension.
The score is the percentage of unflagged channel-time multiplied by the percentage of time without interference flags. It is not a probability of correctness.
All sensors, times, values and thresholds are in the accompanying JSON. Original data are unchanged.</footer>
</main></body></html>"""


def save_report(result, prefix):
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    prefix.with_suffix(".html").write_text(render_report(result))
