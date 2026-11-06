import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .compare import compare, markdown
from .extract import extract_pdf
from .validate import validate


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def download(source, directory):
    """Pin source bytes, reuse validated cache, replace only after validation."""
    url = source["url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".gov.bc.ca"):
        raise ValueError("Source URL must be HTTPS on gov.bc.ca")
    path = Path(directory) / f"{source['label']}.pdf"
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]:
        return path
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "fee-schedule-diff/0.1 (+https://github.com/jackaI1/fee-schedule-diff)",
            "Accept": "application/pdf",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(30_000_001)
            break
        except urllib.error.HTTPError as exc:
            # Do not retry a denial or an unavailable URL.
            if exc.code not in (502, 503, 504) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
        time.sleep(attempt + 1)
    if len(data) > 30_000_000 or not data.startswith(b"%PDF-"):
        raise ValueError("Source is not a supported-size PDF")
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(
            "Source checksum changed; inspect the edition before updating the manifest"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".part")
    try:
        temp.write_bytes(data)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare public BC MSC fixed-price fee rows")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Download checksum-pinned public editions")
    fetch.add_argument("--manifest", default="data/sources.json")
    fetch.add_argument("--directory", default="data/source")
    extract = sub.add_parser("extract", help="Extract a local text PDF with page evidence")
    extract.add_argument("pdf")
    extract.add_argument("--url", required=True, help="Public source PDF URL (no fragment)")
    extract.add_argument("--label", required=True)
    extract.add_argument("--out", required=True)
    diff = sub.add_parser("compare", help="Compare two extracted editions")
    diff.add_argument("old")
    diff.add_argument("new")
    diff.add_argument("--out", required=True)
    diff.add_argument("--markdown", required=True)
    diff.add_argument("--short", help="Optional short Markdown report")
    check = sub.add_parser("validate", help="Score against a separately hand-checked sample")
    check.add_argument("extractions", nargs="+")
    check.add_argument("--gold", default="tests/fixtures/gold.json")
    check.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            for source in read(args.manifest):
                print(download(source, args.directory))
        elif args.command == "extract":
            parsed = urlparse(args.url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
                raise ValueError("Provide a public HTTPS PDF URL without a fragment")
            result = extract_pdf(args.pdf, args.url, args.label)
            write(args.out, result)
            print(f"{len(result['items'])} accepted codes; {len(result['review'])} review entries")
        elif args.command == "compare":
            result = compare(read(args.old), read(args.new))
            write(args.out, result)
            Path(args.markdown).write_text(markdown(result))
            if args.short:
                Path(args.short).write_text(markdown(result, limit=12))
            print(json.dumps(result["counts"]))
        else:
            result = validate([read(p) for p in args.extractions], read(args.gold))
            write(args.out, result)
            print(json.dumps(result["metrics"], indent=2))
            return int(bool(result["errors"]))
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
