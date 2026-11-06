"""Fail CI if regeneration no longer supports the committed results."""

import json
import math
import sys
from pathlib import Path


def check(actual_dir, saved_dir=Path("reports")):
    actual_dir, saved_dir = Path(actual_dir), Path(saved_dir)
    actual = json.loads((actual_dir / "validation.json").read_text())
    saved = json.loads((saved_dir / "validation.json").read_text())
    assert actual == saved, "Injection evidence changed; inspect and regenerate documentation"
    sources = json.loads((actual_dir / "provenance.json").read_text())["sources"]
    assert sources == json.loads((saved_dir / "provenance.json").read_text())["sources"]
    for source in sources:
        name = Path(source["file"]).stem
        current = json.loads((actual_dir / (name + ".json")).read_text())
        expected = json.loads((saved_dir / (name + ".json")).read_text())
        assert current["status"] == expected["status"], name
        assert current["counts"] == expected["counts"], name
        assert math.isclose(current["score"], expected["score"], abs_tol=0.01), name
    print(
        f"Reproduced {len(sources)} session decisions and {len(actual['trials'])} injection trials"
    )


if __name__ == "__main__":
    check(sys.argv[1])
