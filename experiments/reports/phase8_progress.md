# Phase 8 progress: canonical privacy-safe trajectory data

Date: 2026-08-08  
Status: Phase 8A complete; Phase 8 overall in progress

## Completed

- Added versioned canonical trajectory, event, split, and Manifest contracts.
- Added recursive field-aware redaction for secrets and common contact PII.
- Added deterministic post-redaction content fingerprints and exact deduplication.
- Added seeded family-level train/dev/sealed assignment.
- Added audits that fail on cross-split family or exact-content overlap.
- Exported the 36 authoritative Phase 3 Harness trajectories to reproducible
  JSONL under `data/generated/`.

## First export

| Metric | Result |
| --- | ---: |
| Raw records | 36 |
| Records after deduplication | 36 |
| Train / dev / sealed | 24 / 6 / 6 |
| Train / dev / sealed families | 8 / 2 / 2 |
| Cross-split family overlap | 0 |
| Cross-split content overlap | 0 |
| Source values redacted | 0 |

The zero redaction count is expected for this synthetic catalog. Targeted tests
demonstrate recursive replacement of email, phone, Bearer, authorization, and
API-key values.

## Next gate

Phase 8B will mine provenance-linked hard negatives, add near-duplicate and
privacy audits, and derive SFT/preference exports. Dataset scale and class
balance must be reported rather than inferred from the 36-record baseline.

