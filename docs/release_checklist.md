# Release checklist

This checklist separates verified repository readiness from external release
actions that still require repository-owner settings or an explicit release decision.

## Required local gates

- [x] `make release-check PYTHON=.venv/bin/python`
- [x] `python -m ruff check src tests scripts`
- [x] `python -m mypy src`
- [x] `python -m pytest -q`
- [x] Build and validate the 13-entry evidence index.
- [x] Run and audit the four-case CPU demo.
- [x] Confirm a clean archived-source install under CPython 3.11.
- [x] Confirm tracked files contain no credentials, generated traces or model weights.
- [x] Confirm README, changelog, license and evidence links match the release revision.

## External gates

- [x] Choose and record the public repository URL.
- [x] Configure the GitHub private vulnerability-reporting path in repository files.
- [x] Enable private vulnerability reporting in GitHub repository settings.
- [x] Add GitHub Actions configuration using the same quality commands.
- [x] Observe the first GitHub-hosted Python 3.11/3.12 workflow passing.
- [x] Configure default-branch protection to require both matrix checks.
- [x] Choose `v0.1.0-rc1` as the candidate tag after protected RC CI passed.
- [x] Attach or link immutable reports; do not claim unexecuted metrics.
- [ ] Merge the evidence-finalization PR after both protected checks pass.
- [ ] Create annotated tag `v0.1.0-rc1` on the finalized merge revision.
- [ ] Create a GitHub prerelease without publishing to PyPI.

The remaining external items are intentionally open because branch protection,
private vulnerability reporting and release creation require repository-owner
settings or an explicit publication decision.

See `docs/github_publication.md` for the non-destructive first-push procedure
and post-push GitHub settings.

The `release-check` target validates tracked-file boundaries and package/license
metadata after running the complete quality suite. Its generated JSON is placed
under ignored `artifacts/reports/`; it performs no publication or network call.
