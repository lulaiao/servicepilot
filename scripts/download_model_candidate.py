#!/usr/bin/env python3
"""Resolve an immutable Hugging Face revision and cache a model candidate."""

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument(
        "--ignore-pattern",
        action="append",
        default=[],
        help="Repeatable Hugging Face snapshot ignore pattern.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from huggingface_hub import HfApi, snapshot_download

    info = HfApi().model_info(args.repo_id, revision=args.revision)
    resolved_revision = info.sha
    if not resolved_revision:
        raise SystemExit("Hugging Face did not return an immutable revision")
    snapshot = snapshot_download(
        repo_id=args.repo_id,
        revision=resolved_revision,
        cache_dir=args.cache_dir,
        ignore_patterns=args.ignore_pattern or None,
    )
    manifest = {
        "repo_id": args.repo_id,
        "requested_revision": args.revision,
        "resolved_revision": resolved_revision,
        "snapshot_path": snapshot,
        "license": info.card_data.get("license") if info.card_data else None,
        "ignore_patterns": args.ignore_pattern,
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
