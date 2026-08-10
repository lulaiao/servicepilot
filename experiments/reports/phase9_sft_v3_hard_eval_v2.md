# Phase 9 SFT v3 — Hard Eval v2 one-shot report

## Decision

The selected SFT v3 checkpoint remains a useful learned baseline, but it is not a
safety-qualified release candidate. Hard Eval v2 is now diagnosis-only and must not be
used for prompt tuning, training-example selection, threshold tuning, or checkpoint
selection.

The earlier 94.44% result was optimistic for generalization. On 240 independently
authored compositional cases, learned-Agent task success was 82.92%. This is still a
22.50 percentage-point improvement over the identical rule-Agent Harness baseline,
which scored 60.42%.

## Frozen evidence

- Catalog: 240 cases, 20 per intent, with zero exact or near-duplicate training
  utterances.
- Catalog SHA-256: `8c408b74fdcf6c3441507b3e6856c970e39bf152ec0b067f445eaf34d845583a`.
- Gold-intent workflow executability: 240/240.
- Model: Qwen2.5-7B-Instruct revision
  `a09a35458c702b33eeacc393d103063234e8bc28` with seed-20260808 SFT v3
  checkpoint-100.
- Raw report SHA-256:
  `66744029c849da3790e2bd4f138bad6b1a4e1028ae97dbc1e6c7fba0ccbca11f`.
- Raw trace SHA-256:
  `cb9a214026f6577417fbe3ae15b7aaacd136d4dc867e06df4c6570e1205a68f6`.

## Results

| Metric | Rule Agent | SFT v3 Agent |
|---|---:|---:|
| Executable task success | 60.42% | 82.92% |
| Final-state accuracy | 62.92% | 83.75% |
| Policy-violation rate | 26.67% | 8.75% |
| False-success rate | 7.08% | 3.75% |

The learned classifier's raw primary-intent accuracy was 85.42%, Macro-F1 was 85.08%,
and schema validity was 99.58%. The Harness recorded 17 deterministic safety overrides
and 25 tool-alignment overrides. These are intervention counts, not proven rescue
counts, so they must not be presented as model-owned successes.

The high-risk subset contained 120 cases. Its task-failure rate and unsafe-error rate
were both 16.67%, which fails the release safety gate. Ten cases terminated with Agent
runtime errors. Mean inference latency was 2.1752 seconds, P95 was 2.6630 seconds, and
peak allocated VRAM was 14,627.6 MiB on an RTX A6000.

## Failure concentration

- Complaint escalation was weakest: 60% task success and 0.6316 raw F1.
- Partial refund and multi-intent each achieved 70% task success.
- Missing/wrong item achieved 75%; order query, full refund, and reschedule achieved
  80% each.
- Duplicate charge, delivery delay, and out-of-scope achieved 100% end-to-end success,
  though some of these results include deterministic interventions.
- Dominant Judge failures were missing required actions (29), handoff-count mismatch
  (17), missing gold evidence (11), runtime errors (10), and false success (9).
- Nine of the ten runtime errors were confirmation-state incompatibilities; one was a
  wrong reschedule action on a cancellation scenario.

## Next development gate

Remediation must use training/development data only. The next implementation should:

1. replace unconstrained JSON generation with schema-constrained decoding or a strict
   repair-and-reject boundary;
2. validate predicted intent and required scenario slots before dispatch, returning a
   clarification or safe refusal instead of raising a runtime exception;
3. create development-only hard negatives for complaint escalation versus
   out-of-scope, full versus partial refund, and multi-intent conjunctions;
4. report raw-model, guardrail intervention, guardrail rescue/harm, and final-system
   metrics separately;
5. freeze a new independent Hard Eval v3 only after all remediation choices are fixed.

Hard Eval v2 must not be rerun as evidence for the remediated candidate.
