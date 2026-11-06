import json
from pathlib import Path

import pytest

from fee_schedule_diff.extract import assemble

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sampled_editions():
    sources = json.loads(Path("data/sources.json").read_text())
    editions = []
    for source in sources:
        pages = [
            json.loads(p.read_text()) for p in sorted(FIXTURES.glob(f"{source['label']}-p*.json"))
        ]
        editions.append(assemble(((p["page"], p["words"]) for p in pages), source))
    return editions
