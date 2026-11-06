"""Layout-aware extraction for the single-column MSC fee tables, not billing advice."""

import hashlib
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

CODE = re.compile(r"^(?P<prefix>[A-Z]{0,3})(?P<code>\d{5})(?P<marker>\*?)$")
MONEY = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d.%])")
LEADER = re.compile(r"\.{3,}")


def normalize(text):
    """Ignore PDF whitespace and leader dots, preserving wording and punctuation."""
    return " ".join(LEADER.sub(" ", text).split())


def page_lines(words):
    """Group words into baselines; only the main body (not page headers/footers)."""
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not 30 < word["top"] < 745:
            continue
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def parse_page(words, page, url):
    lines = page_lines(words)
    starts = [
        (i, CODE.fullmatch(line[0]["text"]))
        for i, line in enumerate(lines)
        if line[0]["x0"] < 110 and CODE.fullmatch(line[0]["text"])
    ]
    items, review = [], []
    if not lines:
        review.append(
            {
                "page": page,
                "url": f"{url}#page={page}",
                "raw": "",
                "reason": "no extractable body text; inspect scanned or blank page",
            }
        )
    for pos, (start, match) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        block = lines[start:end]
        evidence = {
            "code": match["code"],
            "prefix": match["prefix"],
            "page": page,
            "url": f"{url}#page={page}",
            "raw": "\n".join(" ".join(w["text"] for w in line) for line in block),
        }
        # A priced table row must have leader dots and exactly one monetary value
        # in the block before notes/headings. Never interpret anesthesia units as dollars.
        row_lines = []
        for i, line in enumerate(block):
            text = " ".join(w["text"] for w in line)
            if i and (
                re.match(r"^(?:Notes?:|[ivx]+\)|[a-z]\))", text, re.I)
                or line[0]["x0"] < (block[0][1]["x0"] if len(block[0]) > 1 else 126) - 8
            ):
                break
            row_lines.append(line)
        priced = [
            (i, w, MONEY.fullmatch(w["text"]))
            for i, line in enumerate(row_lines)
            for w in line
            if MONEY.fullmatch(w["text"]) and w["x0"] > 430
        ]
        reason = None
        if match["marker"]:
            reason = "asterisk-qualified code requires review"
        elif len(priced) != 1:
            reason = "no single fixed monetary fee" if not priced else "multiple monetary fees"
        else:
            price_line, price_word, _ = priced[0]
            before = " ".join(
                w["text"]
                for line in row_lines[: price_line + 1]
                for w in line
                if w is not price_word
            )
            if not LEADER.search(before):
                reason = "fee without table leader dots"
            elif re.search(r"%\s+of\s+[^.]{0,60}\b(?:fee|rate)\b", before, re.I):
                reason = "percentage or conditional fee"
            else:
                # Keep wrapped text after the fee only when it directly continues the row.
                used = row_lines[: price_line + 1]
                for line in row_lines[price_line + 1 :]:
                    text = " ".join(w["text"] for w in line)
                    gap = line[0]["top"] - used[-1][0]["top"]
                    if gap > 15 or LEADER.search(text) or MONEY.search(text):
                        break
                    used.append(line)
                description = normalize(
                    " ".join(
                        w["text"]
                        for i, line in enumerate(used)
                        for j, w in enumerate(line)
                        if not (i == 0 and j == 0) and w is not price_word and w["x0"] < 530
                    )
                )
                if not description or len(description) < 3:
                    reason = "missing description"
                else:
                    items.append(
                        {
                            **evidence,
                            "description": description,
                            "fee": price_word["text"].replace(",", ""),
                        }
                    )
        if reason:
            review.append({**evidence, "reason": reason})
    return items, review


def assemble(pages, source):
    items, review = [], []
    for number, words in pages:
        accepted, flagged = parse_page(words, number, source["url"])
        items.extend(accepted)
        review.extend(flagged)
    by_code = defaultdict(list)
    for item in items:
        by_code[item["code"]].append(item)
    accepted = []
    for code, rows in sorted(by_code.items()):
        variants = {(r["prefix"], r["description"], r["fee"]) for r in rows}
        if len(variants) > 1:
            review.extend({**r, "reason": "conflicting duplicate code"} for r in rows)
        else:
            accepted.append({**rows[0], "occurrences": [r["page"] for r in rows]})
    blocked = {r["code"] for r in review if r.get("code")}
    return {
        "schema_version": 1,
        "source": source,
        "rows": items,
        "items": [r for r in accepted if r["code"] not in blocked],
        "review": review,
        "blocked_codes": sorted(blocked),
    }


def extract_pdf(path, url, label):
    path = Path(path)
    source = {"label": label, "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    with pdfplumber.open(path) as pdf:
        source["pages"] = len(pdf.pages)

        def pages():
            for number, page in enumerate(pdf.pages, 1):
                words = page.extract_words(x_tolerance=2, y_tolerance=3)
                yield number, words
                page.close()  # Release character/layout caches during full-edition runs.

        result = assemble(pages(), source)
    if not result["items"]:
        raise ValueError("No confident fee rows found; image-only or unsupported PDF layout")
    return result
