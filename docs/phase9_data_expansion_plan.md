# Phase 9 data expansion plan

## Target

Produce at least 600 train, 120 development, and 120 sealed-test executable SFT
records. Use at least 200/40/40 semantic scenario families and no more than three
language variants per family. This exceeds the 500/100/100 readiness gate while
keeping paraphrase count from masquerading as scenario diversity.

## Family identity

Add an explicit immutable `family_id` to the scenario contract. It is derived
from the semantic task specification, not the utterance:

- primary and secondary intents;
- initial order/payment/coupon/delivery state;
- policy version, business type, city, and time regime;
- amount bucket and boundary condition;
- confirmation acceptance/refusal;
- fault and recovery plan;
- expected final state and forbidden actions.

Language variants inherit the family ID. Split families before generating any
paraphrases. The existing intent-only hash is retained only for the 36-record
baseline and is too coarse for the expanded dataset.

## Construction order

1. Independently author 40 sealed semantic families and freeze their manifest,
   expected states, evidence IDs, and hashes before train/dev generation.
2. Generate 240 train/dev families with deterministic constrained sampling over
   the dimensions above. Use pairwise/targeted coverage instead of the full
   Cartesian product.
3. Create up to three language variants only after family assignment. Templates
   are the baseline; optional local-model paraphrases must retain provenance and
   pass slot/intent consistency checks. No sealed prompt or utterance may be
   supplied to the paraphraser used for train/dev.
4. Execute every scenario through Harness, Gateway, business Repository, and
   deterministic Judge. Failed generation attempts are retained in an audit
   log but excluded from training views.
5. Mine preference negatives from actual decision points. Counterfactual tools
   are never executed, must be absent from the gold trajectory, and keep source
   family/record provenance.

## Coverage priorities

- refund amount at zero, below/at/above paid amount and cumulative-refund limit;
- legal and illegal transitions for accepted, picked-up, delivered, cancelled,
  and refunded orders;
- confirmation accept, reject, expired token, stale version, and repeated
  idempotency key;
- timeout, transient failure, empty/partial result, lost response, and recovery;
- current, expired, contradictory, wrong-city, and wrong-business policy;
- single intent, compatible multi-intent, goal change, missing slots, domain
  refusal, and Prompt Injection;
- memory conflict, stale summary, retrieval evidence missing, and handoff.

## Admission gates

Every admitted record must have schema-valid redacted data, authoritative Judge
success for its declared expected outcome, zero unexplained false-success,
complete provenance, and no privacy violation. Dataset-level gates require:

- zero exact family/content leakage across splits;
- zero cross-split near duplicates at the frozen threshold;
- per-dimension distribution and missing-cell reports;
- no single language template or tool label dominating through duplication;
- fixed generator revision, seed, policy revision, raw hashes, and failure log;
- sealed data never used for template, threshold, reward, or checkpoint choices.

Repeated copies and simple oversampling do not count toward readiness. Sampling
weights may be used only inside the train loader and must be reported separately
from unique record counts.

## Current progress

The first sealed catalog freezes 40 independently reserved families before
train/dev generation. All 40 canonical scenarios pass the authoritative Judge.
The first constrained train/dev batch adds 60 non-overlapping families: 49
train and 11 development. Three post-split utterance variants per family produce
300/300 successful executable trajectories: 147 train, 33 development, and 120
sealed. Exact, family, and near-duplicate cross-split overlap and privacy
violations are all zero.

The sealed record/family target is reached. Train and development remain below
the semantic-family target by 151 and 29 families respectively. More paraphrase
variants of the current families will not close that gap and must not be counted
as the solution.
