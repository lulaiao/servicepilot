# Release checklist

This checklist separates verified repository readiness from external release
actions that still require an owner and hosting destination.

## Required local gates

- [ ] `make release-check PYTHON=.venv/bin/python`
- [ ] `python -m ruff check src tests scripts`
- [ ] `python -m mypy src`
- [ ] `python -m pytest -q`
- [ ] Build and validate the 12-entry evidence index.
- [ ] Run and audit the four-case CPU demo.
- [ ] Confirm a clean archived-source install under CPython 3.11.
- [ ] Confirm tracked files contain no credentials, generated traces or model weights.
- [ ] Confirm README, changelog, license and evidence links match the release revision.

## External gates

- [ ] Choose and record the public repository URL.
- [ ] Configure a monitored private vulnerability-reporting contact.
- [x] Add GitHub Actions configuration using the same quality commands.
- [ ] Observe the first GitHub-hosted Python 3.11/3.12 workflow passing.
- [ ] Configure default-branch protection to require both matrix checks.
- [ ] Choose a release tag only after the final revision passes all local gates.
- [ ] Attach or link immutable reports; do not claim unexecuted metrics.

The external items remain intentionally open because the current local
repository does not establish an owner account, hosting URL or release tag.

See `docs/github_publication.md` for the non-destructive first-push procedure
and post-push GitHub settings.

The `release-check` target validates tracked-file boundaries and package/license
metadata after running the complete quality suite. Its generated JSON is placed
under ignored `artifacts/reports/`; it performs no publication or network call.
