#!/usr/bin/env python3
"""Validate curated evidence and render human/machine-readable indexes."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    ids = [item["id"] for item in catalog["entries"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate evidence catalog ID")
    resolved = []
    for entry in catalog["entries"]:
        files = []
        for value in entry["evidence"]:
            path = Path(value)
            if not path.is_file():
                raise FileNotFoundError(f"missing evidence: {path}")
            files.append({"path": value, "sha256": sha256(path)})
        resolved.append({**entry, "resolved_evidence": files})

    lines = [
        "# Evidence index",
        "",
        "Generated from `experiments/configs/phase10_evidence_catalog.json`.",
        "Metrics apply only to the scope shown; rejected work is intentionally retained.",
        "",
        "| Capability | Decision | Scope | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for entry in resolved:
        links = ", ".join(
            f"[`{Path(item['path']).name}`](../{item['path']})"
            for item in entry["resolved_evidence"]
        )
        lines.append(
            f"| {entry['capability']} | `{entry['status']}` | {entry['scope']} | {links} |"
        )
    lines.extend(["", "## Reproduction commands", ""])
    for entry in resolved:
        lines.extend([f"### {entry['capability']}", "", f"`{entry['reproduce']}`", ""])
    markdown = "\n".join(lines).rstrip() + "\n"
    manifest = {
        "schema_version": "servicepilot-phase10-evidence-index-v1",
        "catalog": str(args.catalog),
        "catalog_sha256": sha256(args.catalog),
        "entry_count": len(resolved),
        "entries": resolved,
        "all_evidence_present": True,
    }
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(markdown, encoding="utf-8")
    manifest["markdown_output"] = str(args.markdown_output)
    manifest["markdown_sha256"] = sha256(args.markdown_output)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "entry_count": len(resolved),
                "all_evidence_present": True,
                "markdown_sha256": manifest["markdown_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
