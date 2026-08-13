# Evidence index

Generated from `experiments/configs/phase10_evidence_catalog.json`.
Metrics apply only to the scope shown; rejected work is intentionally retained.

| Capability | Decision | Scope | Evidence |
| --- | --- | --- | --- |
| Deterministic domain and transactional invariants | `accepted` | In-memory repository and synthetic deterministic tests | [`phase1_acceptance.md`](../experiments/reports/phase1_acceptance.md), [`0001-core-stack.md`](../docs/adr/0001-core-stack.md) |
| MCP services and reliable tool Gateway | `accepted` | Contract tests with pinned MCP SDK and deterministic faults | [`phase2_acceptance.md`](../experiments/reports/phase2_acceptance.md), [`0003-mcp-sdk-and-gateway.md`](../docs/adr/0003-mcp-sdk-and-gateway.md) |
| Executable Agent loop with authoritative-state Judge | `accepted` | 36 synthetic deterministic scenarios | [`phase3_acceptance.md`](../experiments/reports/phase3_acceptance.md), [`phase3_scenarios.md`](../experiments/manifests/phase3_scenarios.md) |
| Rule Agent versus Qwen2.5-7B executable comparison | `accepted_rule_baseline` | Same 36 scenarios and tool budgets; learned extractor rejected | [`phase4_agent_e2e_comparison.md`](../experiments/reports/phase4_agent_e2e_comparison.md), [`phase4_agent_e2e.json`](../experiments/manifests/phase4_agent_e2e.json) |
| Agent Harness, checkpoints, guardrails, budgets and ablations | `accepted` | Deterministic catalog and injected lost-response recovery | [`phase4b_harness_progress.md`](../experiments/reports/phase4b_harness_progress.md), [`phase4b_harness_ablations.json`](../experiments/manifests/phase4b_harness_ablations.json), [`phase4b_resilience_acceptance.json`](../experiments/manifests/phase4b_resilience_acceptance.json) |
| Layered memory with privacy and stale-state controls | `accepted` | Deterministic long-horizon and conflict fixtures | [`phase5_acceptance.md`](../experiments/reports/phase5_acceptance.md), [`phase5_memory_eval.json`](../experiments/manifests/phase5_memory_eval.json), [`0006-layered-memory-boundary.md`](../docs/adr/0006-layered-memory-boundary.md) |
| Policy retrieval component selection and transactional gating | `accepted_bounded` | Frozen policy corpus and sealed retrieval set | [`phase6_acceptance.md`](../experiments/reports/phase6_acceptance.md), [`phase6_sealed_and_transactional.json`](../experiments/manifests/phase6_sealed_and_transactional.json), [`0007-phase6-retrieval-components.md`](../docs/adr/0007-phase6-retrieval-components.md) |
| Least-privilege synchronous/asynchronous Monitor | `accepted_bounded` | 13 deterministic fault classes and 1008 executable trajectories | [`phase7_acceptance.md`](../experiments/reports/phase7_acceptance.md), [`phase7_executable_monitor.json`](../experiments/manifests/phase7_executable_monitor.json), [`0008-phase7-monitor-boundary.md`](../docs/adr/0008-phase7-monitor-boundary.md) |
| Versioned trajectory dataset, redaction, deduplication and leakage gates | `accepted` | Synthetic executable trajectories only | [`phase8_acceptance.md`](../experiments/reports/phase8_acceptance.md), [`phase8_trajectory_dataset_v1.json`](../experiments/manifests/phase8_trajectory_dataset_v1.json), [`0009-phase8-trajectory-data-boundary.md`](../docs/adr/0009-phase8-trajectory-data-boundary.md) |
| LoRA, bounded GRPO and multi-label enhancement research | `stopped_after_rejection` | Local synthetic train/dev plus independently frozen holdouts | [`phase9_progress.md`](../experiments/reports/phase9_progress.md), [`0021-stop-outcome-grpo-after-screen.md`](../docs/adr/0021-stop-outcome-grpo-after-screen.md), [`0035-reject-multilabel-linear-head-v1.md`](../docs/adr/0035-reject-multilabel-linear-head-v1.md), [`0039-reject-multilabel-linear-head-v2.md`](../docs/adr/0039-reject-multilabel-linear-head-v2.md), [`0041-reject-multilabel-structural-candidates.md`](../docs/adr/0041-reject-multilabel-structural-candidates.md) |
| CPU portfolio demo and self-contained Trace Viewer | `accepted` | Four deterministic demonstrations, including intentional false-success interception | [`demo.md`](../docs/demo.md), [`phase10_demo_v1.json`](../experiments/manifests/phase10_demo_v1.json) |
| Clean archived-source installation and quick-start verification | `accepted` | Fresh CPython 3.11 venv; CPU-only install, lint, tests, demo and evidence validation | [`phase10_clean_environment_acceptance.md`](../experiments/reports/phase10_clean_environment_acceptance.md), [`phase10_clean_environment.json`](../experiments/manifests/phase10_clean_environment.json) |
| Local package and open-source handoff readiness | `accepted_local_only` | Quality gates, wheel metadata, license inclusion and bounded tracked-file scans | [`phase10_release_readiness.md`](../experiments/reports/phase10_release_readiness.md), [`phase10_release_readiness.json`](../experiments/manifests/phase10_release_readiness.json), [`release_checklist.md`](../docs/release_checklist.md) |

## Reproduction commands

### Deterministic domain and transactional invariants

`PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_transaction_services.py tests/unit/test_state_machine.py`

### MCP services and reliable tool Gateway

`PYTHONPATH=src .venv/bin/python -m pytest -q tests/contract`

### Executable Agent loop with authoritative-state Judge

`PYTHONPATH=src .venv/bin/python scripts/run_eval.py`

### Rule Agent versus Qwen2.5-7B executable comparison

`See commands and fixed model revision in the comparison report`

### Agent Harness, checkpoints, guardrails, budgets and ablations

`PYTHONPATH=src .venv/bin/python scripts/run_phase4b_resilience_acceptance.py --code-revision local`

### Layered memory with privacy and stale-state controls

`PYTHONPATH=src .venv/bin/python scripts/run_phase5_memory_eval.py`

### Policy retrieval component selection and transactional gating

`See offline model paths and commands in phase6_acceptance.md`

### Least-privilege synchronous/asynchronous Monitor

`PYTHONPATH=src .venv/bin/python scripts/run_phase7_executable_monitor_eval.py`

### Versioned trajectory dataset, redaction, deduplication and leakage gates

`See deterministic export and audit commands in phase8_acceptance.md`

### LoRA, bounded GRPO and multi-label enhancement research

`Use individual frozen protocols; consumed sealed evaluations must not be rerun`

### CPU portfolio demo and self-contained Trace Viewer

`PYTHONPATH=src .venv/bin/python scripts/run_phase10_demo.py --code-revision local`

### Clean archived-source installation and quick-start verification

`Follow the isolation contract and commands in phase10_clean_environment_acceptance.md`

### Local package and open-source handoff readiness

`Run the local commands in phase10_release_readiness.md; external gates require owner decisions`
