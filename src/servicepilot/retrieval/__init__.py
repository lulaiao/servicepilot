"""Policy retrieval and evidence verification."""

from servicepilot.retrieval.dataset import (
    load_policy_corpus,
    load_retrieval_queries,
)
from servicepilot.retrieval.lexical import BM25PolicyRetriever
from servicepilot.retrieval.metrics import evaluate_retrieval
from servicepilot.retrieval.models import (
    EvidenceVerdict,
    PolicyDocument,
    RetrievalMetrics,
    RetrievalQuery,
    SearchHit,
)
from servicepilot.retrieval.verifier import EvidenceVerifier

__all__ = [
    "BM25PolicyRetriever",
    "EvidenceVerdict",
    "EvidenceVerifier",
    "PolicyDocument",
    "RetrievalMetrics",
    "RetrievalQuery",
    "SearchHit",
    "evaluate_retrieval",
    "load_policy_corpus",
    "load_retrieval_queries",
]
