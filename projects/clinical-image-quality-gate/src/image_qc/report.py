"""Readable Markdown evidence and a standalone HTML copy with embedded examples."""

import base64
import html
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .images import STRENGTHS, degrade, load_image
from .models import quality_decision


def percent(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def count_rate(r):
    return f"{r['n']}/{r['total']} ({percent(r['rate'])})"


def acc(r):
    return f"{r['correct']}/{r['n']} ({percent(r['accuracy'])})"


def summary_table(metrics):
    lines = [
        "| Gate | Damaged rejected | Acceptable retained | Photos accepted | "
        "Lesion accuracy: accepted | Lesion accuracy: rejected |",
        "|---|---|---|---|---|---|",
    ]
    for method in ("rules", "learned"):
        m = metrics[method]
        lines.append(
            f"| {method} | {count_rate(m['bad_rejected'])} | "
            f"{count_rate(m['acceptable_retained'])} | {count_rate(m['coverage'])} | "
            f"{acc(m['accepted'])} | {acc(m['rejected'])} |"
        )
    return "\n".join(lines)


def example_sheet(record, image_dir, bundle):
    image = load_image(Path(image_dir) / (record["isic_id"] + ".jpg"))
    sheet = Image.new("RGB", (896, 5 * 264), (247, 245, 239))
    draw = ImageDraw.Draw(sheet)
    for row, kind in enumerate(STRENGTHS):
        for col, strength in enumerate((0, 1, 2, 3)):
            variant = "clean" if strength == 0 else kind
            damaged = degrade(image, variant, strength, seed=int(record["isic_id"][5:]))
            d = quality_decision(damaged, bundle)
            sheet.paste(damaged.resize((208, 208)), (col * 224 + 8, row * 264 + 8))
            label = "acceptable" if strength < 2 else "damaged"
            draw.text(
                (col * 224 + 8, row * 264 + 220),
                f"{variant} {strength} / {label}",
                fill=(30, 30, 30),
            )
            draw.text(
                (col * 224 + 8, row * 264 + 237),
                "learned: " + d["decision"],
                fill=(20, 75, 60) if d["decision"] == "accept" else (150, 45, 35),
            )
    return sheet


def write_report(metrics, rows, records, image_dir, output, bundle):
    output = Path(output)
    d = metrics["dataset"]
    md = [
        "# Photo quality gate: saved experiment",
        "",
        "Not a diagnostic tool. This is a synthetic-damage research demonstration.",
        "",
        "## What was tested",
        "",
        f"The frozen sample has {d['sources']} unique lesions, balanced between nevus "
        "and melanoma. Each source appears once. "
        f"The source split is {d['split_counts']['train']} training, "
        f"{d['split_counts']['validation']} validation and {d['split_counts']['test']} test. "
        f"Each held-out source has {d['variants_per_source']} versions, giving "
        f"{metrics['overall']['n']} held-out photo versions. "
        "These versions are correlated; they are not independent patients.",
        "",
        "Clean and strength 1 are operationally labelled acceptable; strengths 2 and 3 "
        "are labelled damaged. These are chosen benchmark labels, not clinical ratings. "
        "Original images may already contain quality defects. Transformations run after "
        "resizing the complete image to a square analysis grid.",
        "",
        "## Gate comparison",
        "",
        summary_table(metrics),
        "",
        f"Without a gate the lesion baseline gets {acc(metrics['overall'])} across all "
        f"versions; on clean test images it gets {acc(metrics['clean_baseline'])}. "
        "The public baseline is the logistic classifier in this repository, trained from "
        "scratch on clean training sources using colour histograms and a small spatial "
        "colour grid. It is not an externally pretrained or clinically validated model.",
        "",
        "Rejection means abstention in the check command. Rejected-image lesion scores "
        "are computed only inside this benchmark, to measure what the gate discards.",
        "",
        "## Detection at each known strength",
        "",
        "Cells show rejected / total. For clean and strength 1 this is false rejection. "
        "For strengths 2 and 3 it is detection of operationally unacceptable damage.",
        "",
        "| Damage | Strength | Synthetic setting | Rules rejection | Learned rejection | "
        "Ungated lesion accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for r in metrics["by_degradation"]:
        setting = (
            "unchanged" if r["kind"] == "clean" else str(STRENGTHS[r["kind"]][r["strength"] - 1])
        )
        md.append(
            f"| {r['kind']} | {r['strength']} | {setting} | {count_rate(r['rules'])} | "
            f"{count_rate(r['learned'])} | {acc(r['baseline'])} |"
        )
    md += [
        "",
        "Blur settings are Gaussian radii in analysis pixels. Dark/bright settings "
        "multiply RGB values, not physical exposure stops. Framing settings shift that "
        "fraction of the original field off the canvas and pad black. Hair settings are "
        "line counts, with line widths equal to strength in analysis pixels.",
        "",
        "## Selection bias and uncertainty",
        "",
        "| Gate | Source diagnosis | Accepted lesion accuracy | Rejected lesion accuracy |",
        "|---|---|---|---|",
    ]
    for method in ("rules", "learned"):
        for label, name in (("0", "nevus"), ("1", "melanoma")):
            c = metrics[method]["by_class"][label]
            md.append(f"| {method} | {name} | {acc(c['accepted'])} | {acc(c['rejected'])} |")
    md.append("")
    for method in ("rules", "learned"):
        b = metrics[method]["bootstrap"]
        ci = b["accepted_minus_rejected_ci95"]
        if ci:
            md += [
                "",
                f"{method}: the accepted-minus-rejected accuracy difference has a "
                f"95% source-bootstrap interval of {100 * ci[0]:.1f} to {100 * ci[1]:.1f} "
                f"percentage points ({b['valid_repeats']}/{b['repeats']} valid resamples).",
                "",
            ]
    md += [
        "",
        "The bootstrap resamples lesions and keeps all their versions together. "
        "It describes this small fixed experiment, not a clinical population. Accepted "
        "and rejected groups differ in damage and class mix, so the accuracy difference "
        "does not establish a causal benefit. The threshold curve in metrics.json shows "
        "the trade-off between keeping images and selective accuracy, including empty groups.",
        "",
        "## Example images",
        "",
        "These are the first held-out IDs alphabetically in each class, selected without "
        "looking at scores. Each row repeats the original and shows increasing damage. "
        "Captions include the operational label and the learned gate's actual decision.",
        "",
    ]
    images = []
    ids = {r["isic_id"] for r in rows}
    for label in (0, 1):
        record = sorted(
            (r for r in records if r["isic_id"] in ids and r["label"] == label),
            key=lambda r: r["isic_id"],
        )[0]
        sheet = example_sheet(record, image_dir, bundle)
        name = f"examples-{label}.jpg"
        sheet.save(output / name, quality=90)
        bio = io.BytesIO()
        sheet.save(bio, format="JPEG", quality=90)
        caption = (
            f"{record['isic_id']}: {record['diagnosis']}. "
            f"Attribution: {record['attribution']}. CC BY-NC 4.0. "
            "Resized and synthetically modified here."
        )
        md += [
            f"![{caption}]({name})",
            "",
            f"{caption} [Source]({record['source']}) · [Licence]({record['license_url']})",
            "",
        ]
        images.append((caption, base64.b64encode(bio.getvalue()).decode()))
    md += [
        "## Reproduce and inspect",
        "",
        "```sh",
        "uv sync --frozen",
        "uv run image-qc reproduce --output reports",
        "uv run pytest -q",
        "```",
        "",
        "See predictions.csv for each test decision and raw measurement; models.json "
        "for coefficients and validation thresholds; splits.json for source partitions; "
        "metrics.json for unrounded counts, rates and uncertainty. All images are "
        "checksum-verified against data/manifest.json. The manifest preserves per-image "
        "licence, attribution and source URLs without demographic fields.",
        "",
        "## Limits",
        "",
        "This is a small, deliberately balanced, deterministic "
        "convenience sample from the HAM10000 archive collection, not a random "
        "population sample. Lesion IDs and exact image hashes are disjoint; patient "
        "independence and near-duplicate independence are not established. The experiment "
        "uses isolated synthetic corruptions, not mixed artifacts or real capture failures. "
        "Black-padded framing is easy to detect and does not measure true lesion coverage. "
        "The coverage check measures nonblack field area, not a medical segmentation mask. "
        "The hair response is a thin-dark-line proxy. Neither gate checks diagnosis, "
        "skin tone fairness, device shift or clinical adequacy. The baseline can be wrong "
        "on accepted photos. A positive result here does not make a photo safe to analyse.",
        "",
        "## Source",
        "",
        "Tschandl, P., Rosendahl, C. & Kittler, H. The HAM10000 dataset, "
        "a large collection of multi-source dermatoscopic images of common pigmented "
        "skin lesions. Scientific Data (2018). https://doi.org/10.1038/sdata.2018.161. "
        "Images from https://api.isic-archive.com/api/v2/collections/212/ under "
        "https://creativecommons.org/licenses/by-nc/4.0/. All displayed examples are "
        "noncommercial adaptations; the image licence is separate from the code licence.",
        "",
    ]
    markdown = "\n".join(md)
    (output / "REPORT.md").write_text(markdown)
    (output / "summary.md").write_text(summary_table(metrics) + "\n")
    # Self-contained: every image is embedded, no CDN, scripts or network requests.
    embedded = "".join(
        f'<figure><img alt="{html.escape(c)}" '
        f'src="data:image/jpeg;base64,{b}"><figcaption>{html.escape(c)}'
        "</figcaption></figure>"
        for c, b in images
    )
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Photo quality gate experiment</title><style>"
        "body{max-width:1000px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui;"
        "color:#182d28;background:#faf9f5}pre{white-space:pre-wrap;overflow-wrap:anywhere;"
        "font:14px/1.65 ui-monospace,monospace}img{width:100%;height:auto}"
        "figure{margin:28px 0}figcaption{font-size:14px}h1{line-height:1.15}"
        "</style><body><h1>Photo quality gate experiment</h1>"
        "<p>Not a diagnostic tool. Saved results and examples; no installation needed.</p>"
        "<pre>"
        + html.escape(markdown.split("## Example images")[0])
        + "</pre>"
        + embedded
        + "<pre>"
        + html.escape(markdown.split("## Reproduce and inspect")[1])
        + "</pre></body></html>"
    )
    (output / "index.html").write_text(page)
    (output / "run.json").write_text(
        json.dumps(
            {
                "command": "uv run image-qc reproduce",
                "seed": d["seed"],
                "manifest_sha256": d["manifest_sha256"],
            },
            indent=2,
        )
        + "\n"
    )
