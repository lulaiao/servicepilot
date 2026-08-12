# ADR 0038: Freeze independent multi-label holdout v2

- Status: Accepted
- Date: 2026-08-12

## Context

ADR 0037 selected raw-text attention-masked mean pooling from the balanced synthetic v2 development
screen. External functional quality remains unproven, and the consumed v1 holdout cannot be reused.

## Decision

Freeze 64 manually authored Chinese requests with eight examples for each of the eight possible label
sets. Each label therefore has 32 positives and 32 negatives. Wording and scenarios were authored after
v2 candidate selection and differ from the templated development construction.

Check leakage against both the 640-record v2 development corpus and the consumed 80-record holdout v1.
Normalized exact overlap is zero and maximum character 5-gram Jaccard similarity is 0.0968, below the
unchanged 0.8 rejection threshold.

Retain the 0.5 threshold and original gates. All four selected raw-mean heads must pass. The evaluator
verifies catalog, protocol, candidate-decision, candidate-training-protocol, representation, seed, and
head hashes before inference. An existing output path forbids rerun.

## Consequences

The v2 holdout is sealed and unconsumed. Results remain `TBD` until the one-shot GPU command runs. A
failure rejects integration without tuning on this set. A pass authorizes an executable Agent ablation,
but is not itself an end-to-end Agent success claim.
