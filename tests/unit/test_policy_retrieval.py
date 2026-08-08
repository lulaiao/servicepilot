from datetime import UTC, datetime
from pathlib import Path

import pytest

from servicepilot.retrieval import (
    BM25PolicyRetriever,
    DeterministicQueryRewriter,
    EvidenceVerifier,
    MultiQueryRRFRetriever,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
    rank_by_cross_encoder,
    reciprocal_rank_fusion,
)
from servicepilot.retrieval.lexical import is_applicable
from servicepilot.retrieval.models import SearchHit

ROOT = Path(__file__).parents[2]
CORPUS_PATH = ROOT / "data/policies/phase6_corpus.jsonl"
QUERY_PATH = ROOT / "data/eval/phase6_retrieval_queries.jsonl"
HARD_CORPUS_PATH = ROOT / "data/policies/phase6_hard_negatives.jsonl"
HARD_QUERY_PATH = ROOT / "data/eval/phase6_retrieval_queries_hard.jsonl"
DIAGNOSTIC_QUERY_PATH = ROOT / "data/eval/phase6_reranker_diagnostic_queries.jsonl"
SEALED_QUERY_PATH = ROOT / "data/eval/phase6_retrieval_sealed.jsonl"
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
    query = next(item for item in load_retrieval_queries(QUERY_PATH) if item.query_id == "q10")

    hits = BM25PolicyRetriever(corpus).search(query, now=NOW, top_k=10)
    identifiers = {item.evidence_id for item in hits}

    assert "policy_cancel_2025_4_section_2" not in identifiers
    assert "policy_beijing_local_refund_2026_1_section_12" not in identifiers


def test_metadata_filter_normalizes_domain_enum_casing() -> None:
    corpus = load_policy_corpus(CORPUS_PATH) + load_policy_corpus(HARD_CORPUS_PATH)
    query = load_retrieval_queries(QUERY_PATH)[0].model_copy(
        update={"order_status": "ACCEPTED", "business_type": "FOOD_DELIVERY"}
    )

    hits = BM25PolicyRetriever(corpus).search(query, now=NOW, top_k=10)

    assert "policy_cancel_2026_1_section_2" in {item.evidence_id for item in hits}


def test_bm25_metrics_are_computed_from_ranked_evidence() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    queries = load_retrieval_queries(QUERY_PATH)
    retriever = BM25PolicyRetriever(corpus)
    results = {query.query_id: retriever.search(query, now=NOW, top_k=3) for query in queries}

    metrics = evaluate_retrieval(queries, results, top_k=3)

    assert metrics.query_count == 12
    assert 0 <= metrics.recall_at_k <= 1
    assert 0 <= metrics.mean_reciprocal_rank <= 1
    assert 0 <= metrics.ndcg_at_k <= 1
    assert 0 <= metrics.citation_accuracy_at_k <= 1


def test_evidence_verifier_rejects_expired_and_missing_required_sections() -> None:
    corpus = load_policy_corpus(CORPUS_PATH)
    query = next(item for item in load_retrieval_queries(QUERY_PATH) if item.query_id == "q10")
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


def test_harder_dataset_adds_multi_evidence_and_active_hard_negatives() -> None:
    corpus = load_policy_corpus(HARD_CORPUS_PATH)
    queries = load_retrieval_queries(HARD_QUERY_PATH)

    assert len(corpus) == 6
    assert len(queries) == 12
    assert sum(len(item.gold_evidence_ids) > 1 for item in queries) == 6
    assert all(item.policy_version == "2026.1" for item in corpus)


def test_diagnostic_dataset_has_reviewable_disjoint_evidence_labels() -> None:
    queries = load_retrieval_queries(DIAGNOSTIC_QUERY_PATH)

    assert len(queries) == 120
    assert len({item.text for item in queries}) == 120
    assert all(item.required_evidence_ids == item.gold_evidence_ids for item in queries)
    assert all(
        not (
            set(item.required_evidence_ids) & set(item.supporting_evidence_ids)
            or set(item.required_evidence_ids) & set(item.contradictory_evidence_ids)
            or set(item.supporting_evidence_ids) & set(item.contradictory_evidence_ids)
        )
        for item in queries
    )


def test_sealed_retrieval_set_is_unique_and_required_evidence_is_applicable() -> None:
    corpus = load_policy_corpus(CORPUS_PATH) + load_policy_corpus(HARD_CORPUS_PATH)
    documents = {item.evidence_id: item for item in corpus}
    queries = load_retrieval_queries(SEALED_QUERY_PATH)

    assert len(queries) == 36
    assert len({item.text for item in queries}) == 36
    for query in queries:
        assert query.required_evidence_ids == query.gold_evidence_ids
        assert all(
            is_applicable(documents[evidence_id], query, NOW)
            for evidence_id in query.required_evidence_ids
        )


def test_query_rewrite_expands_colloquial_terms_deterministically() -> None:
    query = next(item for item in load_retrieval_queries(HARD_QUERY_PATH) if item.query_id == "q15")

    variants = DeterministicQueryRewriter().rewrite(query)

    assert variants[0] == query.text
    assert any("优惠券" in item and "恢复" in item for item in variants[1:])
    assert variants == DeterministicQueryRewriter().rewrite(query)


def test_multi_query_rrf_returns_unique_metadata_applicable_evidence() -> None:
    corpus = load_policy_corpus(CORPUS_PATH) + load_policy_corpus(HARD_CORPUS_PATH)
    query = next(item for item in load_retrieval_queries(HARD_QUERY_PATH) if item.query_id == "q18")
    retriever = MultiQueryRRFRetriever(BM25PolicyRetriever(corpus))

    hits = retriever.search(query, now=NOW, top_k=3)

    identifiers = [item.evidence_id for item in hits]
    assert len(identifiers) == len(set(identifiers))
    assert "policy_beijing_local_refund_2026_1_section_12" in identifiers
    assert "policy_shanghai_local_cancel_2026_1_section_19" not in identifiers


def test_hybrid_rrf_fuses_unique_results_without_gold_labels() -> None:
    query = load_retrieval_queries(HARD_QUERY_PATH)[0]
    corpus = load_policy_corpus(CORPUS_PATH) + load_policy_corpus(HARD_CORPUS_PATH)
    lexical = BM25PolicyRetriever(corpus).search(query, now=NOW, top_k=3)
    reversed_hits = tuple(
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(reversed(lexical), start=1)
    )

    fused = reciprocal_rank_fusion((lexical, reversed_hits), top_k=3)

    assert len(fused) == len({item.evidence_id for item in fused})
    assert [item.rank for item in fused] == [1, 2, 3]
    assert {item.evidence_id for item in fused} == {item.evidence_id for item in lexical}


def test_cross_encoder_ranking_is_deterministic_and_validated() -> None:
    candidates = (
        SearchHit(evidence_id="b", score=0.9, rank=1, text="B"),
        SearchHit(evidence_id="a", score=0.8, rank=2, text="A"),
    )

    ranked = rank_by_cross_encoder(candidates, (0.5, 0.5), top_k=2)

    assert [item.evidence_id for item in ranked] == ["a", "b"]
    assert [item.rank for item in ranked] == [1, 2]
    with pytest.raises(ValueError, match="counts"):
        rank_by_cross_encoder(candidates, (0.5,), top_k=2)
