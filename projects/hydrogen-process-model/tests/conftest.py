from pathlib import Path

import pytest

from process_model.cost import Assumptions

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def assumptions() -> Assumptions:
    return Assumptions.from_toml(PROJECT / "data" / "assumptions.toml")
