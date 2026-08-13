# ServicePilot

ServicePilot is a reproducible, local-first after-sales agent for food delivery
and local services. It is designed around executable business state, policy
evidence, reliable MCP tool boundaries, stateful routing, layered memory, and
deterministic evaluation.

The repository is in **Phase 10 delivery** after completing the deterministic
domain, MCP/Gateway, executable Agent Harness, layered memory, retrieval,
monitoring, trajectory-data and bounded local-model research phases. The
supported demo needs no model weights, paid API, network, Docker or GPU.

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

Run the 36-scenario deterministic evaluation:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_eval.py
```

Run the four portfolio demos and build a self-contained HTML Trace Viewer:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase10_demo.py \
  --code-revision "$(git rev-parse --short HEAD)"
```

Open `artifacts/demo/trace_viewer.html` locally. The demo includes a successful
transaction, transient-fault recovery, rejected high-risk confirmation, and an
intentional false-success claim caught by the authoritative-state Judge.

Docker is optional until the persistence phase. The current host cannot access
the Docker daemon as the active user; see
[`docs/feasibility_audit.md`](docs/feasibility_audit.md).

## Project status

See [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for gated phases,
[`docs/architecture.md`](docs/architecture.md) for system boundaries,
[`docs/evidence_index.md`](docs/evidence_index.md) for the report and ablation index,
[`docs/resume_evidence.md`](docs/resume_evidence.md) for claim-to-evidence links,
and [`docs/adr/`](docs/adr/) for technology and model decisions. Failed model
experiments are retained rather than hidden; unsupported metrics remain `TBD`.
