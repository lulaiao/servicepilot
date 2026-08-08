"""Deterministic query rewrite, multi-query expansion and RRF fusion."""

from collections import defaultdict
from datetime import datetime

from servicepilot.retrieval.lexical import BM25PolicyRetriever
from servicepilot.retrieval.models import RetrievalQuery, SearchHit

REWRITE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("退单", "不想要", "不能退"), "取消订单 自动取消 人工售后"),
    (("退钱", "返钱"), "退款 金额 实付金额"),
    (("红包", "返券", "券还能回来"), "优惠券 取消后恢复 有效期"),
    (("换个时间", "改时间", "改一次"), "修改预约 配送时间 改期"),
    (("反悔", "不退"), "不可退款 本地服务 改变主意"),
    (("晚了", "超时"), "配送延迟 配送异常 人工升级 补偿"),
    (("几天能到", "到账"), "退款审核 支付渠道 到账时间"),
)


class DeterministicQueryRewriter:
    def rewrite(self, query: RetrievalQuery) -> tuple[str, ...]:
        expansions = [query.text]
        for markers, canonical in REWRITE_RULES:
            if any(marker in query.text for marker in markers):
                expansions.append(f"{query.text} {canonical}")
        return tuple(dict.fromkeys(expansions))


class MultiQueryRRFRetriever:
    def __init__(
        self,
        retriever: BM25PolicyRetriever,
        rewriter: DeterministicQueryRewriter | None = None,
        *,
        rrf_constant: int = 60,
    ) -> None:
        self.retriever = retriever
        self.rewriter = rewriter or DeterministicQueryRewriter()
        self.rrf_constant = rrf_constant

    def search(
        self,
        query: RetrievalQuery,
        *,
        now: datetime,
        top_k: int = 3,
        candidate_k: int = 6,
    ) -> tuple[SearchHit, ...]:
        scores: dict[str, float] = defaultdict(float)
        documents: dict[str, str] = {}
        for rewritten in self.rewriter.rewrite(query):
            variant = query.model_copy(update={"text": rewritten})
            hits = self.retriever.search(
                variant,
                now=now,
                top_k=candidate_k,
                metadata_filter=True,
            )
            for hit in hits:
                scores[hit.evidence_id] += 1 / (self.rrf_constant + hit.rank)
                documents[hit.evidence_id] = hit.text
        ranked = sorted(scores, key=lambda item: (-scores[item], item))[:top_k]
        return tuple(
            SearchHit(
                evidence_id=evidence_id,
                score=round(scores[evidence_id], 8),
                rank=rank,
                text=documents[evidence_id],
            )
            for rank, evidence_id in enumerate(ranked, start=1)
        )
