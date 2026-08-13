# ADR 0039: Reject multi-label linear head v2 after sealed evaluation

- Status: Accepted
- Date: 2026-08-13

## Context

Balanced v2 development data and raw mean pooling produced near-perfect synthetic dev metrics. ADR 0038
then froze 64 independently worded cases with every label combination equally represented. Runtime
checks verified the catalog, protocols, candidate decision, representation, seeds, and all four head
hashes. The fixed threshold remained 0.5.

## Result

No seed passed. Mean macro-F1 was 0.7152 and mean exact-set accuracy was 0.3086. Complaint escalation
false-positive rate averaged 0.6719, far above the frozen 0.05 limit. Complaint recall remained 0.8438,
partial-refund recall 0.9375, and delivery recall 0.9062, but precision fell to approximately 0.557,
0.551, and 0.686 respectively.

Failures occurred across every label set. In particular, every seed failed all eight delivery-plus-
complaint cases as an exact set, and seven of eight no-intent cases failed for every seed. Variation
between seeds was negligible.

## Decision

Reject the v2 linear head and forbid Agent integration. The sealed v2 holdout is consumed and cannot be
rerun, used for threshold tuning, or converted into training data.

Stop the frozen mean-pooling plus single-linear-head line rather than producing a v3 dataset around the
observed sealed failures. The next train/dev-only comparison should test a structurally different
method capable of modeling request scope, such as constrained generative multi-label output or a
cross-encoder classifier, against the existing deterministic/generative baseline. A new sealed version
is permitted only after a protocol is selected without reading v1 or v2 sealed examples.

## Rationale

Balancing prevalence changed v1's missed-label behavior into broad overprediction but did not yield
contextual generalization. The combination of high recall, poor precision, widespread exact-set
failure, and minimal seed variance indicates a representation/capacity mismatch, not a need for more
random seeds. Further threshold or template iteration after two sealed failures would overfit the
evaluation process.

## Consequences

- The project retains both sealed failures as evidence that harness gates prevented unsafe integration.
- Resume claims may describe the disciplined rejection and diagnosis, not claim improved Agent quality.
- Linear-head artifacts remain reproducibility evidence but are not deployable components.
