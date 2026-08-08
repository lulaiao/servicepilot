# ADR 0009: Version trajectory data before training exports

- Status: Accepted for Phase 8A
- Date: 2026-08-08

## Context

Post-training experiments are only defensible if every example can be traced to
an executable outcome and if paraphrases cannot leak across train, development,
and sealed-test splits. Raw Harness trajectories also contain nested tool
arguments and results, so privacy filtering must happen before any training
format export.

## Decision

Adopt `servicepilot-trajectory-v1` as the canonical intermediate record. It
stores redacted typed events, source scenario and trace identifiers, outcome
labels, family and content hashes, split, schema version, and redaction count.
SFT or preference-specific formats must be derived from this record rather than
directly from raw traces.

Split by hashed intent family before export. All three paraphrase/fault variants
of an intent remain in one split. Deduplicate by normalized post-redaction
content hash, then reject any family or content hash appearing in multiple
splits. Recursively redact declared secret keys, Bearer values, email addresses,
and mainland-China mobile numbers without adding a network dependency.

## Evidence

Revision `a1d452e` exports 36 real deterministic Harness trajectories into
24 train, 6 development, and 6 sealed-test records. The twelve families split
8/2/2; cross-split family and content overlap are both zero. No value in the
synthetic source required redaction, while targeted recursive-redaction tests
cover all declared patterns.

## Limitations and next gate

Intent-level families are intentionally conservative but leave only twelve
groups. Phase 8B must add provenance-preserving hard negatives, explicit
near-duplicate checks, privacy scanning of generated outputs, and separate SFT
and preference exports before Phase 8 can be accepted.

