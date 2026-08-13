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
`7e86dc0f7e59bdab1aa887cae56eba2c2425629898cf73bbe9a9abf926e180c2`.
It is a disposable verification artifact under `/tmp`, not a published release.

The repository now contains the Apache-2.0 license text, contribution guidance,
a security policy and an explicit release checklist. Package classifiers mark
the project as Alpha; this is consistent with an unreleased research system.
The tracked-file and metadata checks are automated by
`scripts/run_phase10_release_readiness.py`; the command exits nonzero on a local
gate failure and never authorizes publication.

The first GitHub-hosted quality workflow, run
[`31664664535`](https://github.com/lulaiao/servicepilot/actions/runs/31664664535),
passed on exact revision `ade76451015ae29ebb8bbd3c4b5f1deac7d64255` for both
Python 3.11 and Python 3.12. Dependabot configuration was also observed running.

## Deliberately open external gates

- The public repository is live at `https://github.com/lulaiao/servicepilot`.
- The repository files point to GitHub's private advisory form; private
  vulnerability reporting still must be enabled in GitHub settings.
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
