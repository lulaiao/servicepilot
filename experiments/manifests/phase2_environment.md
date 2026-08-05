# Phase 2 environment manifest

- Python: 3.11.15
- Environment: project-private `.venv` (not committed)
- MCP Python SDK: 2.0.0
- MCP types: 2.0.0
- Pydantic: 2.13.4
- FastAPI: 0.141.1
- Starlette: 1.3.1
- pytest: 9.1.1
- pytest-asyncio: 1.4.0
- Ruff: 0.16.1
- MyPy: 1.20.2
- SDK license: MIT
- Network services used by tests: none
- Docker/GPU required: no

The exact direct SDK pin is stored in `pyproject.toml`. A later release build
must generate a hash-pinned lock file after the API dependency set is finalized.
