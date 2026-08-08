"""Deterministic evidence existence, applicability and sufficiency checks."""

from datetime import datetime

from servicepilot.retrieval.lexical import is_applicable
from servicepilot.retrieval.models import (
    EvidenceVerdict,
    PolicyDocument,
    RetrievalQuery,
)


class EvidenceVerifier:
    def __init__(self, documents: tuple[PolicyDocument, ...]) -> None:
        self.documents = {item.evidence_id: item for item in documents}

    def verify(
        self,
        query: RetrievalQuery,
        cited_evidence_ids: tuple[str, ...],
        *,
        required_evidence_ids: tuple[str, ...],
        now: datetime,
    ) -> EvidenceVerdict:
        accepted: list[str] = []
        rejected: list[str] = []
        for evidence_id in cited_evidence_ids:
            document = self.documents.get(evidence_id)
            if document is None or not self._applicable(document, query, now):
                rejected.append(evidence_id)
            else:
                accepted.append(evidence_id)
        missing = tuple(sorted(set(required_evidence_ids) - set(accepted)))
        return EvidenceVerdict(
            sufficient=not missing,
            applicable=not rejected and bool(accepted),
            accepted_evidence_ids=tuple(accepted),
            rejected_evidence_ids=tuple(rejected),
            missing_required_ids=missing,
        )

    @staticmethod
    def _applicable(document: PolicyDocument, query: RetrievalQuery, now: datetime) -> bool:
        return is_applicable(document, query, now)
