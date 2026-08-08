# Data specification

## Synthetic business records

All user, order, merchant, payment, coupon, delivery, refund, and policy records
are synthetic. IDs carry a `synthetic-` prefix in generated datasets. The
canonical generator accepts an integer seed and order count and returns immutable
records; the same inputs must produce equal datasets.

Money uses `Decimal`, timestamps are timezone-aware UTC values, and enumerations
define all transactional states. Each mutable aggregate has a positive version
used for optimistic concurrency checks.

## Authoritative facts

- `Order` owns order status, paid amount, coupon reference, city, business type,
  creation time, policy version, and aggregate version.
- `PaymentRecord` records captured or reversed charges and may reference an
  original charge for duplicate-charge scenarios.
- `Refund` records amount, reason, status, policy version, evidence IDs, and
  creation time.
- `Coupon`, `Merchant`, and `Delivery` keep independent status and version data.
- `AuditEvent` records every preview, successful write, and rejected
  confirmation/version attempt.

Generated dialogue text or summaries will never override these records.

## Policy data

Natural-language policy sections live under `data/policies/` and use stable
evidence IDs. Equivalent deterministic assertions live in `PolicyEngine`.
Version `2026.1` is the Phase 1 synthetic policy version. A policy change must
preserve the old document/assertions for historical orders and introduce a new
version.

## Future split requirements

Phase 3 scenarios and Phase 8 trajectories must be divided by normalized
scenario family before paraphrase generation. Every split will have a SHA256
manifest containing generator version, seed, policy version, and record count.

## Phase 3 scenario and trajectory records

`ScenarioSpec` contains scenario ID, intent, initial order state, user utterance,
revealed slots, confirmation policy, allowed/forbidden actions, gold evidence,
fault plan and expected final state. The Phase 3 catalog is generated
deterministically in code and addressed by SHA256.

`Trajectory` contains ordered typed events, trace ID, detected intent tuple,
completion claim and final message. Tool events preserve arguments and the full
typed Gateway result. Generated JSONL is excluded from Git but reproducible from
the tracked catalog, code revision and manifest.

## Phase 8 canonical training record

`servicepilot-trajectory-v1` is the privacy-safe intermediate representation.
It contains redacted events, source provenance, authoritative outcome labels,
scenario-family and content hashes, split, and redaction count. Family splitting
precedes export; exact post-redaction duplicates are removed, and any family or
content overlap across train, development, and sealed test fails the export.
Model-specific SFT or preference records must be derived from this canonical
record and retain its `record_id` as provenance.
