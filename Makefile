PYTHON ?= python3

.PHONY: smoke test lint quality release-check audit

smoke:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

test:
	PYTHONPATH=src $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m mypy src

quality: lint test

release-check: quality
	PYTHONPATH=src $(PYTHON) scripts/run_phase10_release_readiness.py

audit:
	./scripts/bootstrap.sh
