# ServicePilot

ServicePilot is a reproducible, local-first after-sales agent for food delivery
and local services. It is designed around executable business state, policy
evidence, reliable MCP tool boundaries, stateful routing, layered memory, and
deterministic evaluation.

The repository has completed **Phase 3**: a deterministic FSM user simulator,
rule-based single Agent, 36 executable scenarios, unified JSONL trajectories and
an authoritative-state Judge now run through the reliable MCP/Gateway boundary.
No model weights or paid APIs are required.

## Quick start

The target runtime is Python 3.11. The Phase 0 smoke test also runs with the
server's current Python 3.8 because it uses only the standard library:

```bash
make smoke
```

When Python 3.11 is available:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Phase 2 uses the project-private environment with the pinned MCP v2 SDK:

```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests
PYTHONPATH=src .venv/bin/python -m mypy src
```

Run the Phase 3 evaluation and regenerate raw evidence:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_eval.py
```

Docker is optional until the persistence phase. The current host cannot access
the Docker daemon as the active user; see
[`docs/feasibility_audit.md`](docs/feasibility_audit.md).

## Project status

See [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for gated phases and
[`CHANGELOG.md`](CHANGELOG.md) for completed work. Experimental numbers remain
`TBD` until produced by fixed, reproducible evaluation runs.
