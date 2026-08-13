# Contributing

ServicePilot treats reproducibility and business-state safety as release
requirements. Keep changes scoped and preserve existing evidence artifacts.

## Local verification

Use CPython 3.11 and install the development extras:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make quality
```

Changes to metrics, models, datasets or prompts must also include the command,
fixed configuration or revision, data manifest, raw report, and an ADR when a
selection decision changes. Never fill an unexecuted metric with an estimate.

## Pull-request expectations

- Add deterministic tests for changed behavior and failure paths.
- Do not bypass domain services when implementing write tools.
- Preserve preview/confirmation/idempotency/version checks for risky writes.
- Do not inspect or tune against sealed evaluation data after it is consumed.
- Do not commit credentials, personal data, model weights or generated traces.
- Update documentation and the evidence index when a supported claim changes.

See `AGENTS.md` for repository-specific engineering rules and
`docs/evaluation_protocol.md` for evaluation constraints.
