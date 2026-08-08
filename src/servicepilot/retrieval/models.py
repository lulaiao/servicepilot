"""Typed policy retrieval contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PolicyDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    text: str
    policy_version: str
    effective_from: datetime
    effective_until: datetime | None
    business_types: tuple[str, ...]
    order_statuses: tuple[str, ...]
    cities: tuple[str, ...]

    def active_at(self, now: datetime) -> bool:
        return self.effective_from <= now and (
            self.effective_until is None or now < self.effective_until
        )


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: str
    text: str
    gold_evidence_ids: tuple[str, ...]
    policy_version: str
    business_type: str
    order_status: str
    city: str


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    score: float
    rank: int
    text: str


class RetrievalMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_count: int
    recall_at_k: float
    mean_reciprocal_rank: float
    ndcg_at_k: float
    citation_accuracy_at_k: float


class EvidenceVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    sufficient: bool
    applicable: bool
    accepted_evidence_ids: tuple[str, ...]
    rejected_evidence_ids: tuple[str, ...]
    missing_required_ids: tuple[str, ...]
