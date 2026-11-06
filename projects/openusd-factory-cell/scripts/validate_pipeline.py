"""Validate Azure YAML against Microsoft's full, pinned JSON schema."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import yaml
from jsonschema import Draft7Validator, ValidationError
from jsonschema.exceptions import best_match

SCHEMA_COMMIT = "e8090fd525cd6ba47d7685c698f3f51983e298c6"
SCHEMA_URL = f"https://raw.githubusercontent.com/microsoft/azure-pipelines-vscode/{SCHEMA_COMMIT}/service-schema.json"
SCHEMA_SHA256 = "f00a9630f6550204148634d9a13f634b5750a225559886effe09a751482f0459"


def load_schema():
    with urlopen(SCHEMA_URL, timeout=30) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SCHEMA_SHA256:
        raise ValueError("Microsoft schema checksum did not match")
    schema = json.loads(data)
    # The pinned VS Code schema lists v2 but omits its input definition.
    # Build only that missing definition from Microsoft's pinned task metadata.
    task_file = (
        Path(__file__).resolve().parents[1] / "schemas/PublishCodeCoverageResultsV2.task.json"
    )
    task = json.loads(task_file.read_text())
    inputs = task["inputs"]
    schema["definitions"]["task"]["anyOf"].append(
        {
            "type": "object",
            "properties": {
                "task": {"const": "PublishCodeCoverageResults@2"},
                "inputs": {
                    "type": "object",
                    "properties": {
                        item["name"]: {"type": "boolean" if item["type"] == "boolean" else "string"}
                        for item in inputs
                    },
                    "required": [item["name"] for item in inputs if item.get("required")],
                    "additionalProperties": False,
                },
            },
            "required": ["task", "inputs"],
        }
    )
    Draft7Validator.check_schema(schema)
    return schema


def validate_pipeline(document, schema):
    error = best_match(Draft7Validator(schema).iter_errors(document))
    if error:
        location = ".".join(str(part) for part in error.absolute_path) or "root"
        # jsonschema's default exception dumps the entire 1.6 MB task catalog.
        raise ValidationError(f"{location}: {error.message[:400]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", nargs="?", type=Path, default=Path("azure-pipelines.yml"))
    args = parser.parse_args()
    try:
        validate_pipeline(yaml.safe_load(args.pipeline.read_text()), load_schema())
    except (ValueError, OSError, ValidationError, yaml.YAMLError) as error:
        parser.exit(1, f"Pipeline schema check failed: {str(error)[:600]}\n")
    print(f"Valid Azure Pipelines YAML (Microsoft schema {SCHEMA_COMMIT[:7]})")


if __name__ == "__main__":
    main()
