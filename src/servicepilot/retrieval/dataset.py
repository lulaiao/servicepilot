"""Frozen corpus and retrieval-query loaders."""

from pathlib import Path

from servicepilot.retrieval.models import PolicyDocument, RetrievalQuery


def load_policy_corpus(path: Path) -> tuple[PolicyDocument, ...]:
    return tuple(
        PolicyDocument.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def load_retrieval_queries(path: Path) -> tuple[RetrievalQuery, ...]:
    return tuple(
        RetrievalQuery.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
