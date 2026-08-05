# Changelog

## Unreleased

### Added

- Phase 0 host feasibility audit and core-stack ADR.
- Gated implementation plan and repository contribution constraints.
- Initial configuration, packaging, Docker Compose placeholder, and module
  boundaries.
- Dependency-free package health check and smoke test.
- Evidence-based technology selection governance, explicit decision matrix, and
  a role-specific model selection protocol.
- Clarified that Qwen model names from the brief are provisional candidates,
  not accepted choices.

### Verification

- `make smoke`: passed (1 test) with the host's dependency-free Python 3.8
  bootstrap runtime.
- `PYTHONPATH=src python3 -m compileall -q src tests`: passed.
