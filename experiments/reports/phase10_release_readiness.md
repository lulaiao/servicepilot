# Phase 10 release-readiness review

Date: 2026-08-13  
Status: **local gates accepted; external publication gates open**

## Accepted local gates

| Gate | Result |
| --- | ---: |
| Ruff over `src`, `tests`, `scripts` | pass |
| Strict MyPy | 111 source files passed |
| Full deterministic suite | 269 tests passed |
| Wheel build without dependency resolution | pass |
| Apache-2.0 text included in wheel | pass |
| Tracked private-key/access-key signature scan | no match |
| Tracked `.env`, private-key and model-weight filename scan | no match |

The RC locally built `servicepilot-0.1.0rc1-py3-none-any.whl` had SHA256
`2673612699f5b6f79800a5c6c4d067d3b08df441f257208e9423e73e60006b47`.
It is a disposable verification artifact under `/tmp`, not a published release.
The `v0.1.0-rc1` candidate uses PEP 440 package version `0.1.0rc1`; wheel
METADATA, runtime health and package `__version__` share one version source.

The repository now contains the Apache-2.0 license text, contribution guidance,
a security policy and an explicit release checklist. Package classifiers mark
the project as Alpha; this is consistent with an unreleased research system.
The tracked-file and metadata checks are automated by
`scripts/run_phase10_release_readiness.py`; the command exits nonzero on a local
gate failure and never authorizes publication.

The latest verified GitHub-hosted quality workflow, run
[`31664789064`](https://github.com/lulaiao/servicepilot/actions/runs/31664789064),
passed on exact revision `afd90427ca09d6a1248105d88841e60c54d81752` for both
Python 3.11 and Python 3.12. Dependabot configuration was also observed running;
its open MyPy 2.x range-expansion PR remains unmerged pending compatibility review.

## Deliberately open external gates

- The public repository is live at `https://github.com/lulaiao/servicepilot`.
- GitHub private vulnerability reporting is enabled.
- Active Ruleset `Protect main` blocks deletion and force pushes, requires PRs,
  linear history, strict up-to-date branches, and Python 3.11/3.12 checks.
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
