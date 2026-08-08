"""Policy retrieval and evidence verification."""

from servicepilot.retrieval.dataset import (
    load_policy_corpus,
    load_retrieval_queries,
)
from servicepilot.retrieval.hybrid import reciprocal_rank_fusion
from servicepilot.retrieval.lexical import BM25PolicyRetriever
from servicepilot.retrieval.metrics import evaluate_retrieval
from servicepilot.retrieval.models import (
    EvidenceVerdict,
    PolicyDocument,
    RetrievalMetrics,
    RetrievalQuery,
    SearchHit,
)
from servicepilot.retrieval.reranker import rank_by_cross_encoder
from servicepilot.retrieval.rewrite import (
    DeterministicQueryRewriter,
    MultiQueryRRFRetriever,
)
from servicepilot.retrieval.verifier import EvidenceVerifier

__all__ = [
    "BM25PolicyRetriever",
    "EvidenceVerdict",
    "EvidenceVerifier",
    "DeterministicQueryRewriter",
    "MultiQueryRRFRetriever",
    "PolicyDocument",
    "RetrievalMetrics",
    "RetrievalQuery",
    "SearchHit",
    "evaluate_retrieval",
    "load_policy_corpus",
    "load_retrieval_queries",
    "reciprocal_rank_fusion",
    "rank_by_cross_encoder",
]
