"""Standalone human review report with inline images and auditable outputs."""

import base64
import csv
import html
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from skimage.segmentation import find_boundaries

from .metrics import match_instances
from .segment import normalize


def overlay(image, truth, pred=None, merge_ids=()):
    rgb = np.repeat((normalize(image) * 190).astype(np.uint8)[:, :, None], 3, axis=2)
    if pred is None:
        rgb[find_boundaries(truth, mode="inner")] = (255, 180, 40)
    else:
        pairs, t_ids, p_ids = match_instances(truth, pred, 0.5)
        matched_t, matched_p = {t for t, _ in pairs}, {p for _, p in pairs}
        for ids, labels, color in (
            (matched_p, pred, (50, 240, 100)),
            (set(p_ids) - matched_p, pred, (255, 60, 210)),
            (set(t_ids) - matched_t, truth, (255, 180, 40)),
        ):
            rgb[find_boundaries(labels, mode="inner") & np.isin(labels, list(ids))] = (
                color
            )
    output = Image.fromarray(rgb)
    draw = ImageDraw.Draw(output)
    for label in merge_ids:
        ys, xs = np.where(pred == label)
        if len(ys):
            draw.rectangle(
                (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                outline=(40, 220, 255),
                width=2,
            )
            draw.text((int(xs.min()), int(ys.min())), str(label), fill=(40, 220, 255))
    return output


def write_report(output, run, images):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "overlays").mkdir(exist_ok=True)
    (output / "labels").mkdir(exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(run, indent=2, allow_nan=False) + "\n"
    )
    flattened = []
    for row in run["rows"]:
        fields = {k: v for k, v in row.items() if k not in ("metrics", "qc")}
        fields.update(
            {
                "focus_score": row["qc"]["focus_score"],
                "focus_flag": row["qc"]["focus_flag"],
                "merge_ids": ";".join(map(str, row["qc"]["merge_ids"])),
            }
        )
        for threshold, metrics in row["metrics"].items():
            fields.update(
                {f"{k}@{threshold}": metrics[k] for k in ("tp", "fp", "fn", "f1")}
            )
        flattened.append(fields)
    with (output / "per_image.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(flattened[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(flattened)
    cards = []
    gallery = [
        "# Image-by-image nuclei review\n\nGreen: matched prediction. Pink: extra or poorly overlapping prediction. Orange: missed reference. Blue box: possible merge. Matching uses IoU 0.5. Review flags are heuristics, not diagnoses.\n\n[Full results](results.json) | [Per-image CSV](per_image.csv) | Download index.html for the standalone offline report.\n"
    ]
    rows_by_image = {}
    for row in run["rows"]:
        rows_by_image.setdefault(row["image"], []).append(row)
    for stem, image, truth, predictions in images:
        gallery.append(f"\n## {stem}\n\n![Reference](overlays/{stem}-reference.png)\n")
        np.savez_compressed(
            output / "labels" / f"{stem}.npz", truth=truth, **predictions
        )
        panels = [("Reference", overlay(image, truth))]
        descriptions = []
        flagged = False
        for row in rows_by_image[stem]:
            qc = row["qc"]
            gallery.append(
                f"\n**{row['method']}**: reference {row['true_count']}; counted {row['pred_count']}; "
                f"error {row['count_error']:+d}; F1 at 0.5 {row['f1']:.3f}; "
                f"extra {row['fp']}; missed {row['fn']}; focus review {qc['focus_flag']}; "
                f"possible merge IDs {qc['merge_ids']}.\n\n![{row['method']} errors](overlays/{stem}-{row['method']}.png)\n"
            )
            flagged |= qc["focus_flag"] or bool(qc["merge_ids"])
            panels.append(
                (
                    row["method"],
                    overlay(image, truth, predictions[row["method"]], qc["merge_ids"]),
                )
            )
            scores = ", ".join(
                f"F1 at {threshold}: {m['f1']:.3f}"
                for threshold, m in row["metrics"].items()
            )
            descriptions.append(
                f"<p><b>{html.escape(row['method'])}</b>: {row['pred_count']} counted; reference {row['true_count']}; "
                f"signed error {row['count_error']:+d}. Matched {row['tp']}; Extra {row['fp']}; Missed {row['fn']}. {scores}.<br>"
                f"Focus score {qc['focus_score']:.6f}: {'REVIEW' if qc['focus_flag'] else 'within training range'}. "
                f"Possible merge IDs: {html.escape(str(qc['merge_ids']))}.</p>"
            )
        figures = []
        for title, panel in panels:
            buffer = io.BytesIO()
            panel.convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(
                buffer, format="PNG", optimize=True
            )
            filename = f"{stem}-{title.lower()}.png"
            (output / "overlays" / filename).write_bytes(buffer.getvalue())
            encoded = base64.b64encode(buffer.getvalue()).decode()
            figures.append(
                f'<figure><figcaption>{html.escape(title)}</figcaption><a href="#" onclick="this.href=this.querySelector(\'img\').src" download="{filename}"><img alt="{html.escape(title)} annotation overlay for {html.escape(stem)}" src="data:image/png;base64,{encoded}"></a></figure>'
            )
        worst = min(row["f1"] for row in rows_by_image[stem])
        cards.append(
            (
                worst,
                f'<article data-flag="{str(bool(flagged)).lower()}"><h2>{html.escape(stem)}</h2>{"".join(descriptions)}<div class="panels">{"".join(figures)}</div></article>',
            )
        )
    summary = "".join(
        f'<tr><td>{html.escape(method)}</td><td>{s["images"]}</td><td>{s["count_mae"]:.2f}</td>'
        + "".join(f'<td>{m["micro_f1"]:.3f}</td>' for m in s["metrics"].values())
        + "</tr>"
        for method, s in run["summary"].items()
    )
    thresholds = (
        list(next(iter(run["summary"].values()))["metrics"]) if run["summary"] else []
    )
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nuclei count review</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#172b35;background:#f4f6f3;max-width:1600px;margin:auto;padding:24px}
h1{font-size:36px}h2{font-size:18px;overflow-wrap:anywhere}article{background:white;padding:20px;margin:24px 0;border:1px solid #bac9c4;border-radius:8px}.panels{display:flex;gap:12px;flex-wrap:wrap}figure{margin:0;flex:1;min-width:280px}img{width:100%;height:auto;background:#111}figcaption{font-weight:bold}td,th{padding:10px;text-align:left;border-bottom:1px solid #bac9c4}label{display:block;margin:20px 0}summary,button{cursor:pointer}a{color:#155e57}p{max-width:1100px}</style>
<h1>Count the nuclei. Review the mistakes.</h1>
<p>DATASET_DESCRIPTION Nuclei are a proxy for cells, not whole-cell measurements. No test annotations set parameters. Cellpose pretraining independence is unknown.</p>
<p><b>Overlay key at IoU 0.5:</b> green = matched prediction; pink = extra or poorly overlapping prediction; orange = missed reference nucleus; blue boxes and numbers = possible merged predictions. IoU measures overlap; F1 balances missed and extra detections. The reference panel shows all annotation boundaries in orange. Poor overlap can create both an extra and a miss.</p>
<p>Review warnings are prompts to inspect an image, not diagnoses. Focus is a normalized edge score compared with a training cutoff. Large objects or separated interior peaks suggest possible merges. Treatment effects can trigger these rules. The source has no focus labels, so focus sensitivity/specificity are unknown.</p>
<table><thead><tr><th>Method</th><th>Images</th><th>Mean absolute count error</th>"""
    dataset = run["provenance"].get("dataset", "Supplied images")
    description = (
        html.escape(dataset)
        + ". Full images are held out using the supplied split lists."
    )
    if run["provenance"].get("sources") and dataset == "BBBC039v1":
        description = "BBBC039v1 fluorescence microscopy. Full images are held out using the publisher's test list."
    document = document.replace("DATASET_DESCRIPTION", description)
    document += (
        "".join(f"<th>Micro F1 @ {t}</th>" for t in thresholds)
        + f"</tr></thead><tbody>{summary}</tbody></table>"
    )
    document += '<p>Images appear with the lowest F1 first. Click an overlay to save its full resolution PNG. All images are embedded; this file works offline.</p><label><input id="flags" type="checkbox"> Show only images with review warnings</label>'
    document += "".join(card for _, card in sorted(cards, key=lambda pair: pair[0]))
    document += (
        '<details><summary>Run settings and provenance</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'
        + html.escape(json.dumps(run["provenance"], indent=2))
        + "</pre></details>"
    )
    document += """<script>document.getElementById('flags').addEventListener('change',function(){document.querySelectorAll('article').forEach(a=>a.hidden=this.checked&&a.dataset.flag!=='true')})</script></html>"""
    (output / "index.html").write_text(document)
    (output / "gallery.md").write_text("\n".join(gallery))
