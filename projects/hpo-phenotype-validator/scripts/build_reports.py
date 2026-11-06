"""Regenerate the committed reports, or compare them without changing the checkout."""

import argparse
from html import escape
import json
from pathlib import Path
import sys
import tempfile

# Allow direct execution from a fresh checkout without installing the package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hpo_validator.cli import load_json, write_json  # noqa: E402
from hpo_validator.evaluation import evaluate, evaluation_markdown  # noqa: E402
from hpo_validator.export import to_phenopacket  # noqa: E402
from hpo_validator.mapping import Mapper  # noqa: E402
from hpo_validator.ontology import Ontology  # noqa: E402
from hpo_validator.reporting import html_document, validation_html  # noqa: E402
from hpo_validator.validation import validate_record  # noqa: E402


def build(destination: Path):
    ontology = Ontology.load(ROOT / "data/hp.obo", verify=True)
    mapper = Mapper(ontology)
    config = load_json(ROOT / "examples/report-config.json")
    result = evaluate(ROOT / "examples/phrases.csv", ontology, mapper)
    write_json(destination / "mapping.json", result)
    (destination / "README.md").write_text(evaluation_markdown(result), encoding="utf-8")
    (destination / "mapping.html").write_text(
        html_document(
            "Phrase mapping evaluation",
            "<p>Fictional examples only. Scores are lexical similarity, "
            "not clinical probabilities.</p><pre>" + escape(evaluation_markdown(result)) + "</pre>",
        ),
        encoding="utf-8",
    )
    for name, source in [("review", "needs-review.json"), ("accepted", "accepted.json")]:
        out = destination / name
        out.mkdir(exist_ok=True)
        report = validate_record(load_json(ROOT / "examples" / source), ontology, mapper)
        write_json(out / "validation.json", report)
        (out / "validation.html").write_text(validation_html(report), encoding="utf-8")
        if report["exportable"]:
            write_json(out / "phenopacket.json", to_phenopacket(report, config["created"]))
        else:
            (out / "phenopacket.json").unlink(missing_ok=True)
    stats = {
        "ontology_version": ontology.version,
        "terms": len(ontology.terms),
        "active_terms": sum(not t.obsolete for t in ontology.terms.values()),
        "obsolete_terms": sum(t.obsolete for t in ontology.terms.values()),
        "phenotype_terms": sum(
            not t.obsolete and ontology.is_phenotype(t.id) for t in ontology.terms.values()
        ),
        "eval": result["splits"]["eval"],
    }
    write_json(destination / "summary.json", stats)
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="hpo-report-check-") as directory:
            generated = Path(directory)
            build(generated)
            expected = {p.relative_to(generated) for p in generated.rglob("*") if p.is_file()}
            existing = {p.relative_to(args.out) for p in args.out.rglob("*") if p.is_file()}
            different = expected ^ existing
            different |= {
                p
                for p in expected & existing
                if (generated / p).read_bytes() != (args.out / p).read_bytes()
            }
            if different:
                print("Stale reports: " + ", ".join(map(str, sorted(different))), file=sys.stderr)
                return 1
        print("Committed reports reproduce exactly.")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        build(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
