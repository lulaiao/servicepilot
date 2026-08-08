"""Dependency-free BM25 lexical baseline with metadata filtering."""

import math
import re
from collections import Counter
from datetime import datetime

from servicepilot.retrieval.models import PolicyDocument, RetrievalQuery, SearchHit


def tokenize(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_]+", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(run)
        chinese.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tuple(latin + chinese)


class BM25PolicyRetriever:
    def __init__(
        self,
        documents: tuple[PolicyDocument, ...],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.documents = documents
        self.k1 = k1
        self.b = b
        self._tokens = {item.evidence_id: tokenize(item.text) for item in documents}
        self._average_length = sum(map(len, self._tokens.values())) / len(documents)
        self._document_frequency = Counter(
            token for tokens in self._tokens.values() for token in set(tokens)
        )

    def search(
        self,
        query: RetrievalQuery,
        *,
        now: datetime,
        top_k: int = 3,
        metadata_filter: bool = True,
    ) -> tuple[SearchHit, ...]:
        query_tokens = tokenize(query.text)
        scored: list[tuple[float, PolicyDocument]] = []
        for document in self.documents:
            if metadata_filter and not is_applicable(document, query, now):
                continue
            score = self._score(query_tokens, document)
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
        return tuple(
            SearchHit(
                evidence_id=document.evidence_id,
                score=round(score, 6),
                rank=rank,
                text=document.text,
            )
            for rank, (score, document) in enumerate(scored[:top_k], start=1)
        )

    def _score(
        self, query_tokens: tuple[str, ...], document: PolicyDocument
    ) -> float:
        tokens = self._tokens[document.evidence_id]
        frequencies = Counter(tokens)
        score = 0.0
        document_count = len(self.documents)
        for token in set(query_tokens):
            frequency = frequencies[token]
            if frequency == 0:
                continue
            document_frequency = self._document_frequency[token]
            inverse_document_frequency = math.log(
                1
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            denominator = frequency + self.k1 * (
                1 - self.b + self.b * len(tokens) / self._average_length
            )
            score += (
                inverse_document_frequency
                * frequency
                * (self.k1 + 1)
                / denominator
            )
        return score



def is_applicable(
    document: PolicyDocument, query: RetrievalQuery, now: datetime
) -> bool:
    return (
        document.policy_version == query.policy_version
        and document.active_at(now)
        and (
            not document.business_types
            or query.business_type in document.business_types
        )
        and (
            not document.order_statuses
            or query.order_status in document.order_statuses
        )
        and (not document.cities or query.city in document.cities)
    )
