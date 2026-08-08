# Phase 5 layered-memory acceptance

Date: 2026-08-08  
Status: **accepted and complete**

## Delivered

- A bounded, ordered and thread-safe recent-message window.
- Strongly typed working facts containing source, observation time, expiry,
  entity version, confidence and sensitivity metadata.
- Deterministic conflict resolution and an append-only conflict record.
- Deterministic factual summaries containing only valid, non-sensitive facts;
  summaries cannot authorize or override authoritative tool state.
- Purpose-bound long-term preferences/history requiring explicit consent,
  expiry and a non-sensitive payload.
- User view, item deletion, complete user deletion and consent revocation.
- A composed `LayeredMemory` service and deterministic no-memory ablation.

## Precedence and privacy policy

Fact precedence is tool > user > long-term > summary. Conflicting tool facts use
entity version and observation time. Expired facts are removed. Every conflict
records the selected and rejected fact IDs plus the reason.

Long-term writes fail closed without active matching consent. Consent is scoped
to a purpose and may expire or be revoked. Long-term storage rejects sensitive
field names and obvious phone, payment-card and email patterns. Deterministic
summaries omit facts marked sensitive.

## Acceptance tests

Tests directly cover:

- retention and reference resolution across 20 turns;
- recent-window truncation without losing typed working facts;
- old transaction-state expiry;
- a newer but wrong summary conflicting with real-time tool state;
- injected false long-term memory conflicting with a refund amount;
- summary leakage prevention for a phone number;
- consent requirement, purpose scope, expiry and revocation;
- viewing, item deletion and deletion of all four layers.

The complete project suite contains 85 passing tests after Phase 5.

## No-memory ablation

| Case | No-memory/recent-only | Layered memory |
| --- | ---: | ---: |
| Cross-20-turn order reference | fail | pass |
| Consented preference | fail | pass |
| Tool state over wrong summary | fail | pass |
| Expired-state abstention | pass | pass |
| Sensitive long-term rejection | pass | pass |
| Total | 2/5 | 5/5 |

This is a deterministic Memory capability metric, not end-to-end Agent task
success. Three cases are safety cases and have zero regressions.

## Reproduction and provenance

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase5_memory_eval.py \
  --code-revision 8c3d0dc \
  --output artifacts/reports/phase5_memory_eval.json

.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src/servicepilot
```

- Case SHA-256:
  `5b28690db77ff01fe9d4227200f958f2563c11a8618d68c18394bcf244d3e9c7`
- Report SHA-256:
  `25bdd39c63c5960f5e5d60dadaed98eb8266e19ba9a8dfc40d0281df450afb64`
- Manifest: `experiments/manifests/phase5_memory_eval.json`
- Decision: `docs/adr/0006-layered-memory-boundary.md`

## Known limits

- The adapter is process-local and not durable across service restarts.
- Sensitive-data detection is a deterministic fail-closed baseline for common
  identifiers, not a comprehensive DLP system.
- Turn and token savings from summaries are not claimed because no LLM context
  benchmark was run.
- A learned summarizer or vector memory remains unselected until it beats this
  baseline under fact precision, conflict safety, privacy and latency metrics.
