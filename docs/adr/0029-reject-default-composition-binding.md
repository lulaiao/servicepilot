# ADR 0029: Reject composition binding as a default capability

- Status: Accepted
- Date: 2026-08-11

## Context

The evidence-gated composition binder passed a 120-case iterable adversarial contract and rescued one
reused-dev Agent failure. A separately authored 60-case functional holdout was then frozen at catalog
hash `9452c481e572eec612233ee5e947b15351d706cf61e901f13b31aec78cb55654`.

The holdout contains 10 independently phrased explicit pairs and 50 safety negatives spanning
negation, future conditions, historical requests, existing third intents, and unrelated upstream
model outputs. It was evaluated once without model inference.

## Result

The no-binding baseline and composition binder both achieved 83.33% contract success. Both had zero
false bindings, while both missed all 10 positive pairs. The binder changed no case, executed no
additional legitimate action, and caused no unexpected action.

False-success is `TBD` because this catalog tests binding state rather than executable Agent scenarios;
no proxy value is substituted.

## Decision

Reject composition binding as a default Agent capability. Keep the implementation, adversarial suite,
and replay tools behind an explicit experimental option. `RoutedRuleAgent` defaults to composition
binding disabled, and formal model evaluation requires `--enable-composition-binding` to opt in.

Do not add holdout phrases to the binder and do not rerun composition holdout v1.

## Consequences

- The production-oriented path retains the v5 model plus existing completion verifier and does not
  claim generalized composition rescue.
- The experiment still provides interview-relevant evidence of Guardrail ablation, negative-result
  handling, and holdout discipline.
- A successor should use a learned multi-label/compositional representation or a substantially
  different semantic detector, then validate on a newly authored holdout.
