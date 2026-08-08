"""Typed policy retrieval contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


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
    required_evidence_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    contradictory_evidence_ids: tuple[str, ...] = ()
    policy_version: str
    business_type: str
    order_status: str
    city: str

    @model_validator(mode="after")
    def validate_evidence_labels(self) -> "RetrievalQuery":
        required = set(self.required_evidence_ids or self.gold_evidence_ids)
        supporting = set(self.supporting_evidence_ids)
        contradictory = set(self.contradictory_evidence_ids)
        if required != set(self.gold_evidence_ids):
            raise ValueError("required evidence must equal gold evidence")
        if required & supporting or required & contradictory or supporting & contradictory:
            raise ValueError("required, supporting and contradictory evidence must be disjoint")
        return self


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
