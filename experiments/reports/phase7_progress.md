# Phase 7 progress: least-privilege deterministic Monitor

Date: 2026-08-08  
Status: Phase 7A complete; Phase 7 overall in progress

## Completed

- Added typed observations, findings, severity and recommendation models.
- Implemented thirteen deterministic fault rules with an explicit three-scope
  permission check.
- Added synchronous evaluation and a bounded asynchronous queue with identical
  rule semantics.
- Added a read-only adapter from `HarnessSession`, `Trajectory`, and
  `JudgeResult`; raw arguments and Repository state are not exposed.
- Added isolated fault, clean-control, missing-permission, async-queue, and real
  Harness projection tests.

## Calibration

The frozen calibration has 26 cases: thirteen single-fault positives and
thirteen clean controls.

| Metric | Result |
| --- | ---: |
| Fault classes | 13 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| Harmful intervention rate | 0.0000 |
| False positives | 0 |
| False negatives | 0 |

Code revision: `657d314d9d91396d5331b102c917067200ef0bdc`  
Raw report SHA-256:
`047bc686eac14805911456eb26ee97eea06d381f719cbdd685e21aed948776b6`

## Interpretation and limitations

This calibration verifies rule wiring against isolated gold labels. It does
not estimate performance on naturally distributed or correlated failures. The
Monitor remains advisory, and the reported harmful-intervention rate concerns
recommendations on these clean controls, not production traffic.

## Next gate

Phase 7B will create a reproducible generator and manifest for at least 1,000
executable trajectories. It will include clean runs, all fault classes,
multi-fault combinations, sync/async parity, recovery-state assertions,
latency/backpressure metrics, and no-Monitor ablation. Phase 7 is not accepted
until that gate passes.

