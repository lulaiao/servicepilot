# Phase 8 acceptance: privacy-safe trajectory training views

Date: 2026-08-08  
Status: Accepted

## Accepted data flow

Raw executable Harness trajectories first become versioned
`servicepilot-trajectory-v1` records. Redaction occurs recursively before
content hashing, deduplication, splitting, or model-specific export. Intent
families are assigned to train, development, or sealed test as indivisible
groups, and exact or near-duplicate cross-split records fail the pipeline.

SFT and preference views are derived only from canonical records and retain
their `source_record_id`. Hard negatives pair a true tool decision with a
declared confusable tool that is absent from the gold trajectory. No rejected
action is executed against the business system.

## Results

| Artifact or audit | Result |
| --- | ---: |
| Canonical trajectories | 36 |
| Train / dev / sealed | 24 / 6 / 6 |
| Values redacted | 73 |
| Exact duplicates removed | 0 |
| Cross-split family overlap | 0 |
| Cross-split exact-content overlap | 0 |
| Cross-split near duplicates at 0.9 | 0 |
| SFT records | 36 |
| Preference records | 56 |
| Export privacy violations | 0 |
| Missing source provenance | 0 |
| Chosen equals rejected | 0 |

The 73 redactions are transactional confirmation tokens and idempotency keys.
The privacy gate initially rejected four token substrings that resembled mobile
numbers; this exposed that composite keys such as `confirmation_token` were not
covered. The canonical dataset was regenerated after expanding the key policy.

## Reproducibility

- Code revision: `c68433a0a1ad8579d9acc109a865873f2d980075`
- Canonical SHA-256:
  `ea1b1184515eace7736080a7fdd653e6e198e54e18f566ff36873d15fa45d244`
- SFT SHA-256:
  `4d116d16826e41a78071ad983a94cabaebab58bb2b5a1a940153072ea3ea94dc`
- Preference SHA-256:
  `0e4699977c44b9907dff3455472115498e210945b582fc09d1ec0f39c9c721bd`
- Tracked Manifest:
  `experiments/manifests/phase8_trajectory_dataset_v1.json`

## Limitations

- The dataset contains only 36 deterministic trajectories and must not be
  described as sufficient for model training quality.
- Hard negatives cover tool confusion, not natural-language reasoning errors.
- Preference labels are rule-derived rather than human annotated.
- Tool distributions are imbalanced; for example, `cancel_order` appears 18
  times as the rejected tool. Phase 9 must report per-tool sampling and avoid
  silently balancing sealed-test data.

