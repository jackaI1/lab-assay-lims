from pathlib import Path
import pytest
from hpo_validator.ontology import Ontology


@pytest.fixture
def ontology():
    return Ontology.load(Path("tests/fixtures/mini.obo"))
