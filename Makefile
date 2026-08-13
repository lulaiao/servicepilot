PYTHON ?= python3

.PHONY: smoke test lint quality audit

smoke:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

test:
	PYTHONPATH=src $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m mypy src

quality: lint test

audit:
	./scripts/bootstrap.sh
