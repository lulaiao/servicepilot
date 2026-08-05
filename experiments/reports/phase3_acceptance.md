# Phase 3 acceptance report

Date: 2026-08-05  
Phase 2 commit: `03d9ca0`  
Runtime: CPython 3.11.15, project-private `.venv`

## Delivered

- Immutable scenario, trace, Judge result and aggregate report schemas.
- Deterministic FSM user with progressive order/slot disclosure and refusal.
- Rule-based single Agent using only user messages and the reliable Gateway.
- Twelve intent classes with three variants each: 36 executable scenarios.
- Multi-intent delivery-delay plus complaint execution.
- Transient-fault variants that recover within the same tool result.
- Deterministic final-state, policy evidence, action-sequence and false-success
  assertions.
- Reproducible JSONL trajectories, report and SHA256 manifest.

## Measured fixed-catalog result

| Metric | Result |
| --- | ---: |
| Scenarios | 36 |
| Executable task success | 36/36 (100%) |
| Final-state accuracy | 100% |
| Policy violation rate | 0% |
| False-success rate | 0% |
| Average dialogue turns | 5.833 |
| Average tool calls | 1.556 |

Every intent class has 3/3 successes. These results describe the fixed
deterministic development catalog only. They are integration evidence, not an
unseen-language or model-generalization claim.

## Reproduction

```text
PYTHONPATH=src .venv/bin/python scripts/run_eval.py

scenario_sha256 =
ea33cccc96eec2a877f204c00441ad73a6b8545784f39e98cdd55a8081e2cead

raw trajectories = 36 JSONL records, approximately 103 KB
```

The test suite separately injects an impossible expected final state while an
Agent trajectory claims success and verifies that the Judge emits
`FALSE_SUCCESS`.

## Known limitations and Phase 4 risks

- Intent rules use explicit Chinese keywords and are expected to fail on unseen
  paraphrases, ambiguous references and implicit goals.
- The catalog was designed with the baseline and is not a sealed test set.
- Multi-intent coverage currently exercises one two-intent combination.
- User impatience and mid-conversation goal changes are not yet represented.
- Token counts are unavailable because no language model is used.
- The rule Agent is single-role; no dynamic rerouting comparison exists yet.
- Phase 4 must freeze leakage-resistant train/dev/sealed-test scenario families
  before model selection or single-vs-multi-Agent claims.

## Gate result

Phase 3 acceptance criteria pass: more than 30 scenarios execute end to end,
success is determined from final state, raw trajectories are reproducible, and
false-success is detected. Phase 4 must not start until this report and commit
are reviewed.
