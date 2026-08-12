#!/usr/bin/env python3
"""Freeze multi-label holdout v2 against development data and consumed v1."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.eval.multilabel_holdout_v1 import MultiLabelHoldoutCase
from servicepilot.eval.multilabel_holdout_v2 import build_multilabel_holdout_v2
from servicepilot.training.multilabel_composition_v2_data import (
    MultiLabelCompositionV2Record,
)


def normalized(text: str) -> str:
    return "".join(character.lower() for character in text if not character.isspace())


def shingles(text: str, size: int = 5) -> set[str]:
    value = normalized(text)
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-data", type=Path, required=True)
    parser.add_argument("--consumed-holdout-v1", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    development = tuple(
        MultiLabelCompositionV2Record.model_validate_json(line)
        for line in args.development_data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    consumed_v1 = tuple(
        MultiLabelHoldoutCase.model_validate_json(line)
        for line in args.consumed_holdout_v1.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    cases = build_multilabel_holdout_v2()
    prior = tuple((item.record_id, item.text) for item in development) + tuple(
        (item.case_id, item.text) for item in consumed_v1
    )
    prior_texts = {normalized(text) for _, text in prior}
    exact_overlap = [case.case_id for case in cases if normalized(case.text) in prior_texts]
    prior_shingles = [(record_id, shingles(text)) for record_id, text in prior]
    nearest = []
    for case in cases:
        current = shingles(case.text)
        record_id, score = max(
            (
                (record_id, len(current & candidate) / len(current | candidate))
                for record_id, candidate in prior_shingles
            ),
            key=lambda pair: pair[1],
        )
        nearest.append({"case_id": case.case_id, "record_id": record_id, "score": score})
    max_similarity = max(item["score"] for item in nearest)
    if exact_overlap or max_similarity >= 0.8:
        raise RuntimeError(
            f"v2 holdout leakage gate failed: exact={exact_overlap}, max={max_similarity}"
        )
    decision = Path(protocol["candidate_decision"])
    if hashlib.sha256(decision.read_bytes()).hexdigest() != protocol["candidate_decision_sha256"]:
        raise RuntimeError("selected candidate decision hash mismatch")
    encoded = "".join(case.model_dump_json() + "\n" for case in cases).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v2-freeze",
        "provenance": "post_v2_selection_independent_manual_authoring",
        "code_revision_before_freeze": args.code_revision,
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "protocol": str(args.protocol),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "candidate_decision_sha256": protocol["candidate_decision_sha256"],
        "development_data_sha256": hashlib.sha256(args.development_data.read_bytes()).hexdigest(),
        "consumed_holdout_v1_sha256": hashlib.sha256(
            args.consumed_holdout_v1.read_bytes()
        ).hexdigest(),
        "case_count": len(cases),
        "category_counts": dict(sorted(Counter(case.category for case in cases).items())),
        "label_positive_counts": dict(
            sorted(Counter(label.value for case in cases for label in case.labels).items())
        ),
        "label_prevalence": {
            label: round(count / len(cases), 4)
            for label, count in sorted(
                Counter(label.value for case in cases for label in case.labels).items()
            )
        },
        "normalized_exact_overlap_count": len(exact_overlap),
        "max_prior_corpora_character_5gram_similarity": round(max_similarity, 4),
        "near_duplicate_threshold": 0.8,
        "model_inference_executed": False,
        "head_weights_accessed": False,
        "selection_or_tuning_allowed": False,
        "threshold": protocol["threshold"],
        "acceptance_gates": {
            "required_seed_pass_count": protocol["required_seed_pass_count"],
            **protocol["acceptance_gates"],
        },
        "rerun_allowed": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
