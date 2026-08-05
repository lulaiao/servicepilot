# Phase 3 scenario manifest

- Generator: `servicepilot.eval.catalog.build_phase3_scenarios`
- Code baseline before Phase 3 commit: `03d9ca0`
- Seed: `20260805`
- Scenario count: `36`
- Intent classes: `12`
- Variants per intent: `3`
- Scenario SHA256:
  `ea33cccc96eec2a877f204c00441ad73a6b8545784f39e98cdd55a8081e2cead`
- Judge: deterministic authoritative-state Judge
- Raw trace path: `artifacts/traces/phase3_trajectories.jsonl`
- Raw report path: `artifacts/reports/phase3_report.json`
- Raw manifest path: `artifacts/reports/phase3_manifest.json`

Raw artifacts are deliberately excluded from Git because they are generated.
The command below reproduces all three files:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_eval.py
```

