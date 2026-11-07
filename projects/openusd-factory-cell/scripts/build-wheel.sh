#!/usr/bin/env bash
set -euo pipefail
wheel_dir="${1:-dist}"
mkdir -p "$wheel_dir"
wheel_dir="$(cd "$wheel_dir" && pwd)"
python -m build --wheel --outdir "$wheel_dir"
# Install outside the checkout: an editable install can hide missing wheel files.
smoke_dir="$(mktemp -d)"
trap 'rm -rf "$smoke_dir"' EXIT
python -m venv "$smoke_dir/venv"
"$smoke_dir/venv/bin/python" -m pip install "$wheel_dir"/openusd_factory_cell-*.whl
cp examples/cell.json "$smoke_dir/layout.json"
(
  cd "$smoke_dir"
  "$smoke_dir/venv/bin/factory-cell" layout.json cell.usda
  "$smoke_dir/venv/bin/python" -c \
    'from pxr import Usd; s=Usd.Stage.Open("cell.usda"); assert s.GetDefaultPrim().GetName() == "FactoryCell"; assert len(s.GetDefaultPrim().GetChildren()) == 3'
  "$smoke_dir/venv/bin/factory-cell" generate --output animated --fixture nest --seconds 12 --fps 30
  "$smoke_dir/venv/bin/factory-cell" validate animated/cell.usda
  "$smoke_dir/venv/bin/python" -c \
    'from factory_cell import validate_stage; r=validate_stage("animated/cell.usda"); assert r.valid; assert r.summary["part_samples"] == 361'
)
