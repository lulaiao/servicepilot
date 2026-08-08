from datetime import UTC, datetime
from pathlib import Path

from servicepilot.retrieval import (
    BM25PolicyRetriever,
    EvidenceVerifier,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
)

ROOT = Path(__file__).parents[2]
CORPUS_PATH = ROOT / "data/policies/phase6_corpus.jsonl"
QUERY_PATH = ROOT / "data/eval/phase6_retrieval_queries.jsonl"
NOW = datetime(2026, 8, 8, tzinfo=UTC)


def test_frozen_retrieval_data_loads_with_hard_negatives() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    queries = load_retrieval_queries(QUERY_PATH)

    assert len(corpus) == 10
    assert len(queries) == 12
    assert any(item.policy_version == "2025.4" for item in corpus)
    assert len({item.evidence_id for item in corpus}) == len(corpus)
    assert all(item.gold_evidence_ids for item in queries)


def test_metadata_filter_excludes_expired_and_wrong_city_documents() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    query = next(
        item for item in load_retrieval_queries(QUERY_PATH) if item.query_id == "q10"
    )

    hits = BM25PolicyRetriever(corpus).search(query, now=NOW, top_k=10)
    identifiers = {item.evidence_id for item in hits}

    assert "policy_cancel_2025_4_section_2" not in identifiers
    assert "policy_beijing_local_refund_2026_1_section_12" not in identifiers


def test_bm25_metrics_are_computed_from_ranked_evidence() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    queries = load_retrieval_queries(QUERY_PATH)
    retriever = BM25PolicyRetriever(corpus)
    results = {
        query.query_id: retriever.search(query, now=NOW, top_k=3)
        for query in queries
    }

    metrics = evaluate_retrieval(queries, results, top_k=3)

    assert metrics.query_count == 12
    assert 0 <= metrics.recall_at_k <= 1
    assert 0 <= metrics.mean_reciprocal_rank <= 1
    assert 0 <= metrics.ndcg_at_k <= 1
    assert 0 <= metrics.citation_accuracy_at_k <= 1


def test_evidence_verifier_rejects_expired_and_missing_required_sections() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    query = next(
        item for item in load_retrieval_queries(QUERY_PATH) if item.query_id == "q10"
    )
    verifier = EvidenceVerifier(corpus)

    verdict = verifier.verify(
        query,
        (
            "policy_cancel_2025_4_section_2",
            "policy_cancel_2026_1_section_2",
        ),
        required_evidence_ids=("policy_cancel_2026_1_section_2",),
        now=NOW,
    )

    assert verdict.sufficient is True
    assert verdict.applicable is False
    assert verdict.accepted_evidence_ids == ("policy_cancel_2026_1_section_2",)
    assert verdict.rejected_evidence_ids == ("policy_cancel_2025_4_section_2",)

    missing = verifier.verify(
        query,
        (),
        required_evidence_ids=("policy_cancel_2026_1_section_2",),
        now=NOW,
    )
    assert missing.sufficient is False
    assert missing.missing_required_ids == ("policy_cancel_2026_1_section_2",)
