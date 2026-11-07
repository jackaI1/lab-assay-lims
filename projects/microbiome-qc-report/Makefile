SHELL := /bin/bash
export OPENBLAS_NUM_THREADS := 1
export OMP_NUM_THREADS := 1
export VECLIB_MAXIMUM_THREADS := 1
DEPTH ?= 5000
PAIRS ?= 12000
OUT ?= results/demo
FIXTURE_OUT ?= results/fixture

.PHONY: prepare analyze demo test fixture-test
prepare:
	python scripts/prepare.py --pairs $(PAIRS)
analyze:
	Rscript scripts/pipeline.R data/raw/samples.tsv data/reference/rdp_train_set_18.fa.gz $(OUT) $(DEPTH)
	python scripts/report.py $(OUT) --provenance data/raw/provenance.json
demo: prepare analyze

test:
	python -m unittest discover -s tests -v
	Rscript tests/test_analysis.R

fixture-test: test
	python scripts/verify_fixture.py
	Rscript scripts/pipeline.R tests/fixture/samples.tsv tests/fixture/taxonomy.fa.gz $(FIXTURE_OUT) 800
	python scripts/report.py $(FIXTURE_OUT) --provenance tests/fixture/provenance.json --label 'Tiny public-read CI fixture; restricted taxonomy reference'
	python tests/check_run.py $(FIXTURE_OUT) --expect-shallow D8
