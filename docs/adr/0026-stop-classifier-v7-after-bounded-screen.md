# ADR 0026: Stop classifier v7 after bounded screening

- Status: Accepted
- Date: 2026-08-11

## Context

Classifier v7 added 24 train-only examples for lifecycle-stop language, discount-entitlement
restoration, and string-valued amount output. It deliberately used v5 rather than the rejected v6
dataset and loaded zero sealed records. A single predeclared seed ran for 10 optimizer steps, with
checkpoints at steps 5 and 10.

Both checkpoints were evaluated on the unchanged 36-case v4 executable dev catalog under the same
model revision, Harness, tool budget, deterministic Judge, and BF16 runtime.

## Evidence

Both v7 checkpoints produced:

- 35/36 executable task success (97.22%);
- 100% Schema-valid output;
- 0 unauthorized actions, incorrect committed writes, false success, and Guardrail harm;
- primary Macro-F1 0.8256;
- one incomplete delivery-delay plus complaint scenario.

Checkpoint-10 had lower dev loss than checkpoint-5 (0.5840 versus 0.7705) and lower observed P95
scenario latency (3.3517 versus 4.0429 seconds), but no quality improvement.

Compared with v5 checkpoint-10, v7 fixed the reused-dev cancellation boundary and removed its
high-risk task failure, but regressed one multi-intent case. Total Agent success remained 35/36 and
Macro-F1 fell from 0.8339 to 0.8256. This triggers the protocol's frozen
`macro_f1_below_v5_checkpoint10` termination condition.

## Decision

Stop v7 after the bounded seed. Do not launch the remaining three formal seeds and do not evaluate
v7 on any sealed catalog. Retain v5 checkpoint-10 as the development baseline. V7 checkpoint-10 is
recorded only as a diagnostic artifact, not as a selected candidate.

The result indicates interference between narrowly targeted remediation and multi-intent
completeness. The next design step should address compositional intent representation or loss
balancing on train/dev data, rather than add another set of surface paraphrases.

## Consequences

- The consumed Agent sealed v1 remains untouched.
- No quality claim is derived from lower loss alone.
- Resources are not spent on a four-seed run after a frozen termination condition has fired.
- Any successor requires a new version and, after dev selection, a newly authored holdout.
