# ADR 0037: Select raw mean pooling as the v2 development candidate

- Status: Accepted as a development candidate only
- Date: 2026-08-12

## Context

ADR 0036 froze a balanced train/dev dataset and isolated representation choice while keeping the model,
Adapter, linear head, optimizer, four seeds, threshold, and acceptance gates fixed. No sealed data was
present or accessed.

## Result

Both declared representations passed all gates for all four seeds. Raw-text attention-masked mean
pooling achieved mean macro-F1 0.9974, exact-set accuracy 0.9922, and complaint false-positive rate
0.0. Task-instruction last-token pooling achieved 0.9437, 0.8438, and 0.0156 respectively.

Raw mean representation extraction took 9.5729 seconds. Instruction last-token extraction took 16.1153
seconds, a 68.34% increase. Every seed within a representation produced the same aggregate metrics,
consistent with a stable convex linear-head fit on fixed features.

## Decision

Select raw-text attention-masked mean pooling as the only v2 candidate. Reject instruction last-token
pooling because it is slower and worse on every ordered quality criterion. Retain all four selected head
hashes for the next gate.

This is a synthetic development selection only. Do not integrate the head into the Agent or describe
the near-perfect score as external generalization.

## Rationale

- The simpler representation wins under the predeclared ordering and has materially lower latency.
- Explicit task instructions did not improve scope reasoning in last-token features, so their extra
  tokens and cost are unjustified.
- The balanced v2 data fixed the obvious v1 prevalence failure, but its repeated synthetic construction
  can still support template shortcuts. Only independent language can test that risk.

## Consequences

The next gate is a newly authored multi-label holdout v2, frozen after this selection and before model
inference. It must avoid text and template reuse from both v2 development data and consumed holdout v1.
The v1 holdout remains immutable failure evidence and cannot be used for v2 tuning or selection.
