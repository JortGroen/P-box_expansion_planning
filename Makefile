PYTHON ?= python

.PHONY: test run figures

test:
	$(PYTHON) -m pytest

run:
	$(PYTHON) -m src.runner configs/bootstrap_manifest.yaml --output-dir experiments/bootstrap

figures:
	$(PYTHON) -m paper.figures.build

