#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports
# Parallel jobs have separate workspaces, so their reports cannot overwrite each other.
python -m pytest --junitxml=reports/junit.xml \
  --cov=factory_cell --cov-branch --cov-report=term-missing \
  --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov
