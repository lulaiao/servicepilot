"""Typed in-process implementation behind every MCP tool."""

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from servicepilot.domain.errors import IdempotencyConflictError, NotFoundError
from servicepilot.domain.models import AuditEvent, DeliveryIssue, HandoffTicket
from servicepilot.domain.repositories import DomainRepository
from servicepilot.domain.services import TransactionService
from servicepilot.mcp_servers.schemas import (
    CancelOrderRequest,
    CouponEligibilityRequest,
    CreateHandoffTicketRequest,
    CreateRefundRequest,
    GetCouponStatusRequest,
    GetDeliveryStatusRequest,
    GetMerchantStatusRequest,
    GetOrderRequest,
    GetPaymentRecordsRequest,
    GetPolicySectionRequest,
    GetRefundStatusRequest,
    ListRecentOrdersRequest,
    PreviewCancelRequest,
    PreviewRescheduleRequest,
    RefundEligibilityRequest,
    ReportDeliveryIssueRequest,
    RescheduleOrderRequest,
    RestoreCouponRequest,
    SearchPolicyRequest,
    ToolRequest,
    VerifyPolicyRequest,
)
from servicepilot.policies.engine import PolicyEngine

Handler = Callable[[Any], Any]


class UnknownToolError(Exception):
    pass


class ServiceRegistry:
    """Validate requests before dispatching to deterministic domain services."""

    def __init__(
        self,
        repository: DomainRepository,
        transactions: TransactionService,
        policies: PolicyEngine,
    ) -> None:
        self.repository = repository
        self.transactions = transactions
        self.policies = policies
        self._handlers: dict[str, tuple[type[ToolRequest], Handler]] = {
            "get_order": (GetOrderRequest, self._get_order),
            "list_recent_orders": (
                ListRecentOrdersRequest,
                self._list_recent_orders,
            ),
            "preview_cancel": (PreviewCancelRequest, self._preview_cancel),
            "cancel_order": (CancelOrderRequest, self._cancel_order),
            "preview_reschedule": (
                PreviewRescheduleRequest,
                self._preview_reschedule,
            ),
            "reschedule_order": (RescheduleOrderRequest, self._reschedule_order),
            "get_payment_records": (
                GetPaymentRecordsRequest,
                self._get_payment_records,
            ),
            "check_refund_eligibility": (
                RefundEligibilityRequest,
                self._check_refund,
            ),
            "preview_refund": (RefundEligibilityRequest, self._preview_refund),
            "create_refund_request": (
                CreateRefundRequest,
                self._create_refund,
            ),
            "get_refund_status": (
                GetRefundStatusRequest,
                self._get_refund,
            ),
            "get_coupon_status": (
                GetCouponStatusRequest,
                self._get_coupon,
            ),
            "check_coupon_restore_eligibility": (
                CouponEligibilityRequest,
                self._check_coupon,
            ),
            "preview_coupon_restore": (
                CouponEligibilityRequest,
                self._preview_coupon,
            ),
            "restore_coupon": (RestoreCouponRequest, self._restore_coupon),
            "search_policy": (SearchPolicyRequest, self._search_policy),
            "get_policy_section": (
                GetPolicySectionRequest,
                self._get_policy_section,
            ),
            "verify_policy_applicability": (
                VerifyPolicyRequest,
                self._verify_policy,
            ),
            "get_merchant_status": (
                GetMerchantStatusRequest,
                self._get_merchant,
            ),
            "get_delivery_status": (
                GetDeliveryStatusRequest,
                self._get_delivery,
            ),
            "report_delivery_issue": (
                ReportDeliveryIssueRequest,
                self._report_delivery_issue,
            ),
            "create_handoff_ticket": (
                CreateHandoffTicketRequest,
                self._create_handoff,
            ),
        }
        self._policy_sections = {
            "policy_cancel_2026_1_section_2": "CREATED, PAID or ACCEPTED orders may be cancelled.",
            "policy_partial_refund_2026_1_section_3": (
                "Delivered-order refunds must be positive and not exceed paid amount."
            ),
            "policy_coupon_restore_2026_1_section_5": (
                "A used coupon may be restored after cancellation."
            ),
            "policy_reschedule_2026_1_section_6": (
                "PAID, ACCEPTED or PREPARING orders may be rescheduled."
            ),
            "policy_refund_exception_2026_1_section_8": (
                "Non-refundable local services reject changed-mind refunds."
            ),
        }

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(self._handlers)

    def request_model(self, name: str) -> type[ToolRequest]:
        try:
            return self._handlers[name][0]
        except KeyError as exc:
            raise UnknownToolError(name) from exc

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            model, handler = self._handlers[name]
        except KeyError as exc:
            raise UnknownToolError(name) from exc
        request = model.model_validate(arguments)
        return self._serialize(handler(request))

    def _get_order(self, request: GetOrderRequest) -> Any:
        return self.repository.get_order(request.order_id)

    def _list_recent_orders(self, request: ListRecentOrdersRequest) -> Any:
        return self.repository.list_orders(request.user_id)[: request.limit]

    def _preview_cancel(self, request: PreviewCancelRequest) -> Any:
        return self.transactions.preview_cancel(request.order_id)

    def _cancel_order(self, request: CancelOrderRequest) -> Any:
        return self.transactions.execute_cancel(
            request.order_id,
            request.confirmation_token,
            request.idempotency_key,
            request.expected_version,
        )

    def _preview_reschedule(self, request: PreviewRescheduleRequest) -> Any:
        return self.transactions.preview_reschedule(
            request.order_id, request.new_time
        )

    def _reschedule_order(self, request: RescheduleOrderRequest) -> Any:
        return self.transactions.execute_reschedule(
            request.order_id,
            request.new_time,
            request.confirmation_token,
            request.idempotency_key,
            request.expected_version,
        )

    def _get_payment_records(self, request: GetPaymentRecordsRequest) -> Any:
        return self.repository.list_payments(request.order_id)

    def _check_refund(self, request: RefundEligibilityRequest) -> Any:
        order = self.repository.get_order(request.order_id)
        return self.policies.check_refund(
            order, request.reason, request.requested_amount
        )

    def _preview_refund(self, request: RefundEligibilityRequest) -> Any:
        return self.transactions.preview_refund(
            request.order_id, request.reason, request.requested_amount
        )

    def _create_refund(self, request: CreateRefundRequest) -> Any:
        return self.transactions.execute_refund(
            request.order_id,
            request.reason,
            request.requested_amount,
            request.confirmation_token,
            request.idempotency_key,
            request.expected_version,
        )

    def _get_refund(self, request: GetRefundStatusRequest) -> Any:
        return self.repository.get_refund(request.refund_id)

    def _get_coupon(self, request: GetCouponStatusRequest) -> Any:
        coupon = self.repository.get_coupon(request.coupon_id)
        if coupon.user_id != request.user_id:
            raise NotFoundError("coupon not found for user")
        return coupon

    def _check_coupon(self, request: CouponEligibilityRequest) -> Any:
        return self.policies.check_coupon_restore(
            self.repository.get_order(request.order_id)
        )

    def _preview_coupon(self, request: CouponEligibilityRequest) -> Any:
        return self.transactions.preview_coupon_restore(request.order_id)

    def _restore_coupon(self, request: RestoreCouponRequest) -> Any:
        return self.transactions.execute_coupon_restore(
            request.order_id,
            request.confirmation_token,
            request.idempotency_key,
            request.expected_order_version,
        )

    def _search_policy(self, request: SearchPolicyRequest) -> Any:
        terms = set(request.query.lower().split())
        scored = sorted(
            (
                (
                    sum(term in text.lower() or term in evidence_id.lower() for term in terms),
                    evidence_id,
                    text,
                )
                for evidence_id, text in self._policy_sections.items()
            ),
            reverse=True,
        )
        return [
            {"evidence_id": evidence_id, "text": text, "policy_version": "2026.1"}
            for score, evidence_id, text in scored
            if score > 0
        ][: request.top_k]

    def _get_policy_section(self, request: GetPolicySectionRequest) -> Any:
        try:
            text = self._policy_sections[request.evidence_id]
        except KeyError as exc:
            raise NotFoundError("policy evidence not found") from exc
        return {
            "evidence_id": request.evidence_id,
            "text": text,
            "policy_version": "2026.1",
        }

    def _verify_policy(self, request: VerifyPolicyRequest) -> Any:
        order = self.repository.get_order(request.order_id)
        known = set(self._policy_sections)
        supplied = set(request.evidence_ids)
        return {
            "applicable": supplied <= known and order.policy_version == "2026.1",
            "unknown_evidence_ids": sorted(supplied - known),
            "policy_version": order.policy_version,
        }

    def _get_merchant(self, request: GetMerchantStatusRequest) -> Any:
        return self.repository.get_merchant(request.merchant_id)

    def _get_delivery(self, request: GetDeliveryStatusRequest) -> Any:
        return self.repository.get_delivery(request.order_id)

    def _report_delivery_issue(self, request: ReportDeliveryIssueRequest) -> Any:
        payload = {
            "order_id": request.order_id,
            "issue_type": request.issue_type,
        }
        with self.repository.transaction():
            self.repository.get_order(request.order_id)
            previous = self._simple_idempotency(
                "report_delivery_issue", request.idempotency_key, payload
            )
            if previous is not None:
                return previous
            issue = DeliveryIssue(
                f"issue-{uuid4().hex}",
                request.order_id,
                request.issue_type,
                "OPEN",
                datetime.now(UTC),
            )
            self.repository.add_delivery_issue(issue)
            self._save_simple_idempotency(
                "report_delivery_issue", request.idempotency_key, payload, issue
            )
            self._audit_write(
                "report_delivery_issue",
                request.order_id,
                request.idempotency_key,
            )
            return issue

    def _create_handoff(self, request: CreateHandoffTicketRequest) -> Any:
        payload = {
            "order_id": request.order_id,
            "context": request.context,
            "reason": request.reason,
        }
        with self.repository.transaction():
            self.repository.get_order(request.order_id)
            previous = self._simple_idempotency(
                "create_handoff_ticket", request.idempotency_key, payload
            )
            if previous is not None:
                return previous
            ticket = HandoffTicket(
                f"ticket-{uuid4().hex}",
                request.order_id,
                request.reason,
                request.context,
                "OPEN",
                datetime.now(UTC),
            )
            self.repository.add_handoff_ticket(ticket)
            self._save_simple_idempotency(
                "create_handoff_ticket", request.idempotency_key, payload, ticket
            )
            self._audit_write(
                "create_handoff_ticket",
                request.order_id,
                request.idempotency_key,
            )
            return ticket

    def _simple_idempotency(
        self, action: str, key: str, payload: dict[str, str]
    ) -> Any | None:
        previous = self.repository.get_idempotent_result(action, key)
        if previous is None:
            return None
        fingerprint, result = previous
        if fingerprint != self._hash(payload):
            raise IdempotencyConflictError("idempotency key payload mismatch")
        return result

    def _save_simple_idempotency(
        self, action: str, key: str, payload: dict[str, str], result: Any
    ) -> None:
        self.repository.save_idempotent_result(
            action, key, self._hash(payload), result
        )

    def _audit_write(
        self, action: str, target_id: str, idempotency_key: str
    ) -> None:
        self.repository.add_audit_event(
            AuditEvent(
                event_id=f"audit-{uuid4().hex}",
                trace_id=f"trace-{uuid4().hex}",
                action=action,
                target_id=target_id,
                outcome="succeeded",
                idempotency_key=idempotency_key,
                entity_version=None,
                occurred_at=datetime.now(UTC),
                detail="",
            )
        )

    @staticmethod
    def _hash(payload: dict[str, str]) -> str:
        return sha256(dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _serialize(value: Any) -> dict[str, Any]:
        if isinstance(value, BaseModel):
            serialized = value.model_dump(mode="json")
        else:
            serialized = TypeAdapter(Any).dump_python(value, mode="json")
        if isinstance(serialized, dict):
            return serialized
        return {"items": serialized}
