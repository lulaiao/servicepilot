# Phase 9 classifier v3 leakage-gate incident

## Outcome

Classifier dataset v3 was **not frozen** and must not be trained. The new exact-content
audit rejected its historical base source before output publication.

## Evidence

- Historical base view: 942 records with 39 prompt texts present in more than one split.
- New contract Hard Negatives: 72 records with 9 prompt texts present in both train and
  dev because the source language templates were reused across split-owned scenario
  families.
- Combined candidate: 48 cross-split prompt overlaps.
- The rejected generated JSONL and its preliminary passing Manifest were deleted.
- Hard Eval v2 was not read while constructing or auditing this candidate.

The old family-ID isolation check was insufficient: different scenario families could
share exactly the same user utterance. Fault profile, order state, or requested amount
often differed only in hidden scenario state and therefore did not create a distinct
classifier input.

## Consequence

Historical SFT v3 dev/sealed results cannot be treated as clean language-generalization
evidence. This is an additional explanation for the saturated 94.44% score. The
independently authored Hard Eval v2 remains the authoritative one-shot generalization
evidence because its freeze gate found zero exact or near-duplicate training utterances.

## Required remediation

The next dataset cannot be produced by repartitioning the existing 942-record base.
It requires independently authored, split-owned utterance families before scenario
expansion. Exact normalized content and near-duplicate checks must run before export,
with sealed content excluded from training-time authoring and diagnosis.
