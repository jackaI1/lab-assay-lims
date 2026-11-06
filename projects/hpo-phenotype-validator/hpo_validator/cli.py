"""Command-line interface; exit 0 accepted, 2 review needed, 1 invalid input or IO error."""

import argparse
import json
from pathlib import Path
import sys

from .export import to_phenopacket
from .ontology import Ontology
from .reporting import validation_html
from .validation import validate_record

CHECKOUT_ONTOLOGY = Path(__file__).resolve().parents[1] / "data" / "hp.obo"
DEFAULT_ONTOLOGY = (
    CHECKOUT_ONTOLOGY
    if CHECKOUT_ONTOLOGY.is_file()
    else Path(__file__).resolve().parent / "data" / "hp.obo"
)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate fictional HPO lists offline")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Write an audit report and, if safe, a Phenopacket")
    validate.add_argument("input", type=Path)
    validate.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    validate.add_argument("--out", type=Path, required=True, help="New or empty output directory")
    args = parser.parse_args(argv)
    try:
        if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
            raise ValueError("Output directory must be new or empty; existing files are preserved")
        ontology = Ontology.load(args.ontology, verify=args.ontology.resolve() == DEFAULT_ONTOLOGY)
        report = validate_record(load_json(args.input), ontology)
        packet = to_phenopacket(report) if report["exportable"] else None
        args.out.mkdir(parents=True, exist_ok=True)
        write_json(args.out / "validation.json", report)
        (args.out / "validation.html").write_text(validation_html(report), encoding="utf-8")
        if packet is not None:
            write_json(args.out / "phenopacket.json", packet)
        print(
            f"{'Accepted' if report['exportable'] else 'Review required'}: "
            f"{len(report['cleaned'])} cleaned features; {len(report['review_rows'])} review rows; "
            f"{len(report['contradictions'])} contradictions. Reports: {args.out}"
        )
        return 0 if report["exportable"] else 2
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
