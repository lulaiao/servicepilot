# Resume evidence

Every statement below is bounded by its named dataset and implementation. It is
not a production-SLA claim.

## Supported statements

- Built a typed local-first after-sales Agent whose high-risk writes use
  preview-confirm-execute, idempotency keys, optimistic locking and immutable
  audit events. Evidence: [ADR 0001](adr/0001-core-stack.md), domain tests and
  transaction-service tests.
- Implemented an Agent Harness with runtime budgets, guardrails, tool-call
  interception, checkpoints, resumable evaluation and authoritative-state
  grading. Evidence: [harness design](harness_design.md), [ADR 0005](adr/0005-agent-harness-boundary.md)
  and the Phase 4B test suites.
- Achieved 36/36 task success, 100% final-state accuracy, zero policy violations
  and zero false-success on the deterministic Phase 3 catalog. Reproduce with
  `PYTHONPATH=src .venv/bin/python scripts/run_eval.py`; raw report:
  `artifacts/reports/phase3_report.json`.
- Built a four-case CPU demo covering a successful write, transient recovery
  without duplicate refund, refusal of high-risk confirmation, and deliberate
  false-success interception. Reproduce with `scripts/run_phase10_demo.py` and
  inspect `artifacts/demo/trace_viewer.html`.
- Evaluated model and system candidates with frozen protocols, hashes and sealed
  gates, rejecting regressions instead of tuning on test data. Evidence includes
  [ADR 0035](adr/0035-reject-multilabel-linear-head-v1.md),
  [ADR 0039](adr/0039-reject-multilabel-linear-head-v2.md) and
  [ADR 0041](adr/0041-reject-multilabel-structural-candidates.md).

## Claims that are not supported

- Do not claim the rejected multi-label heads improved end-to-end Agent quality.
- Do not describe synthetic development scores as production generalization.
- Do not claim PostgreSQL, paid APIs, real payments or real-user traffic.
- Do not quote latency without naming hardware, precision, dataset and whether
  model-loading time is included.

## Interview framing

The strongest result is not a single model score. It is an engineering process:
business invariants and deterministic Judges were established first; candidates
then faced identical budgets and frozen gates; two apparently excellent
synthetic-dev classifiers failed independent holdouts and were prevented from
reaching the Agent. That is concrete evidence that the Harness changes release
decisions rather than merely recording traces.
