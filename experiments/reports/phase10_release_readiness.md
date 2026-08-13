# Phase 10 release-readiness review

Date: 2026-08-13  
Status: **local gates accepted; external publication gates open**

## Accepted local gates

| Gate | Result |
| --- | ---: |
| Ruff over `src`, `tests`, `scripts` | pass |
| Strict MyPy | 110 source files passed |
| Full deterministic suite | 268 tests passed |
| Wheel build without dependency resolution | pass |
| Apache-2.0 text included in wheel | pass |
| Tracked private-key/access-key signature scan | no match |
| Tracked `.env`, private-key and model-weight filename scan | no match |

The locally built `servicepilot-0.1.0-py3-none-any.whl` had SHA256
`1e5922e14ec34e814a6dc82a8422cced8cf76ec3f6fce3a3a2c3324a2ff0edc1`.
It is a disposable verification artifact under `/tmp`, not a published release.

The repository now contains the Apache-2.0 license text, contribution guidance,
a security policy and an explicit release checklist. Package classifiers mark
the project as Alpha; this is consistent with an unreleased research system.
The tracked-file and metadata checks are automated by
`scripts/run_phase10_release_readiness.py`; the command exits nonzero on a local
gate failure and never authorizes publication.

## Deliberately open external gates

- Public repository URL and hosting owner are not yet selected.
- A monitored private vulnerability-reporting contact is not yet configured.
- GitHub Actions is configured locally, but no hosted run exists before the
  first push.
- No release tag or package publication is authorized.

These values were not invented in package metadata. They require the owner to
choose a hosting identity and communication channel. Local readiness does not
mean the software is approved for real payment or personal-data workloads.

## Reproduction

```bash
make release-check PYTHON=.venv/bin/python
mkdir -p /tmp/servicepilot-dist-check
.venv/bin/python -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/servicepilot-dist-check .
unzip -l /tmp/servicepilot-dist-check/servicepilot-0.1.0-py3-none-any.whl
```

See `docs/release_checklist.md` for the final owner-operated publication gates.
