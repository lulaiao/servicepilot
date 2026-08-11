#!/usr/bin/env python3
"""Freeze composition holdout v1 without evaluating the binder."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.eval.composition_holdout_v1 import build_composition_holdout_v1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    cases = build_composition_holdout_v1()
    encoded = "".join(item.model_dump_json() + "\n" for item in cases).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-composition-holdout-v1-freeze",
        "provenance": "post_adversarial_independent_authoring",
        "code_revision_before_freeze": args.code_revision,
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "case_count": len(cases),
        "category_counts": dict(sorted(Counter(item.category for item in cases).items())),
        "positive_count": sum(item.should_bind for item in cases),
        "negative_count": sum(not item.should_bind for item in cases),
        "binder_evaluated": False,
        "selection_or_tuning_allowed": False,
        "rerun_allowed": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
