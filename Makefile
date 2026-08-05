PYTHON ?= python3

.PHONY: smoke test lint audit

smoke:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

test:
	PYTHONPATH=src $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m mypy src

audit:
	./scripts/bootstrap.sh

