# Repository instructions

- Read `IMPLEMENTATION_PLAN.md` and the relevant tests before changing code.
- Do not advance to a later phase until the current phase acceptance gate passes.
- Never call paid model APIs or download large model weights without explicit approval.
- All business data must be synthetic; never commit secrets or personal data.
- Business writes must go through typed MCP boundaries and must implement preview,
  confirmation, idempotency, version checks, and audit records.
- Deterministic final-state and policy assertions are the primary source of truth.
- Add tests before implementing business write behavior.
- Do not weaken or delete tests to make a change pass.
- Keep `IMPLEMENTATION_PLAN.md` and `CHANGELOG.md` current.
- Record unexecuted metrics as `TBD`; never invent results.
- Do not promote a technology or model from candidate to selected without an ADR,
  credible alternatives, primary-source license/compatibility evidence, and a
  reproducible ServicePilot-specific comparison.
- Never use generic leaderboard results as proof of performance on this project.
