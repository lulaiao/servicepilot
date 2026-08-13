#!/usr/bin/env python3
"""Run deterministic tracked-file release checks and write a JSON manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from servicepilot.delivery.release_readiness import audit_release_readiness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase10_release_readiness_runtime.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    tracked = [
        value.decode("utf-8")
        for value in completed.stdout.split(b"\0")
        if value
    ]
    result = audit_release_readiness(root, tracked)
    payload = {
        "schema_version": "servicepilot-phase10-release-readiness-runtime-v1",
        "tracked_file_count": len(tracked),
        **result.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not result.local_readiness_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
