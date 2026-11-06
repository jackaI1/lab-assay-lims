.PHONY: setup test demo report check
setup:
	uv sync --frozen --extra test
	Rscript analysis/install.R

demo:
	uv run clinical-pipeline demo --output build/demo

test:
	uv run pytest -q
	Rscript analysis/test.R

report:
	Rscript analysis/render.R build/demo/output/sdtm build/analysis

check: test report
	uv run python scripts/check_artifacts.py build
