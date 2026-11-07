"""Reject invalid pipeline structure using the actual Microsoft schema."""

import copy
import importlib.util
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "validate_pipeline", ROOT / "scripts/validate_pipeline.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture(scope="module")
def schema():
    return validator.load_schema()


@pytest.fixture
def pipeline():
    return yaml.safe_load((ROOT / "azure-pipelines.yml").read_text())


def test_real_pipeline_matches_microsoft_schema(pipeline, schema):
    validator.validate_pipeline(pipeline, schema)


@pytest.mark.parametrize(
    "mutation", ["root_typo", "step_typo", "bad_matrix", "bad_task", "bad_coverage_input"]
)
def test_schema_rejects_broken_pipeline(pipeline, schema, mutation):
    broken = copy.deepcopy(pipeline)
    if mutation == "root_typo":
        broken["triger"] = broken.pop("trigger")
    elif mutation == "step_typo":
        broken["jobs"][0]["steps"][1]["scriptt"] = "python -m pytest"
    elif mutation == "bad_matrix":
        broken["jobs"][0]["strategy"]["matrix"] = ["3.11", "3.12"]
    elif mutation == "bad_coverage_input":
        broken["jobs"][0]["steps"][7]["inputs"]["summaryFileLocaton"] = "reports/coverage.xml"
    else:
        broken["jobs"][0]["steps"][1]["task"] = "UsePythonVersion@999"
    with pytest.raises(ValidationError):
        validator.validate_pipeline(broken, schema)
