"""Deterministic finite-state user simulator."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from servicepilot.eval.models import ScenarioSpec


class UserState(StrEnum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ORDER_REVEALED = "ORDER_REVEALED"
    CONFIRMED = "CONFIRMED"
    REFUSED = "REFUSED"
    DONE = "DONE"


class FSMUserSimulator:
    def __init__(self, scenario: ScenarioSpec) -> None:
        self.scenario = scenario
        self.state = UserState.NEW

    def start(self) -> str:
        if self.state is not UserState.NEW:
            raise RuntimeError("simulator already started")
        self.state = UserState.ACTIVE
        return self.scenario.user_utterance

    def answer_order_question(self) -> str:
        if self.state is not UserState.ACTIVE:
            raise RuntimeError("order question is invalid in current state")
        if not self.scenario.reveal_order_id_on_question:
            return "我暂时找不到订单号"
        self.state = UserState.ORDER_REVEALED
        return f"订单号是 {self.scenario.order_id}"

    def answer_confirmation(self, explanation: str) -> str:
        if self.state not in {UserState.ORDER_REVEALED, UserState.ACTIVE}:
            raise RuntimeError("confirmation is invalid in current state")
        if not explanation.strip():
            self.state = UserState.REFUSED
            return "你没有解释影响，我不同意"
        if self.scenario.accept_confirmation:
            self.state = UserState.CONFIRMED
            return "我确认执行"
        self.state = UserState.REFUSED
        return "我不同意执行"

    def refund_details(self) -> tuple[str, Decimal]:
        if self.scenario.reason is None or self.scenario.requested_amount is None:
            raise RuntimeError("scenario has no refund details")
        return self.scenario.reason, self.scenario.requested_amount

    def reschedule_time(self) -> datetime:
        if self.scenario.new_time is None:
            raise RuntimeError("scenario has no reschedule time")
        return self.scenario.new_time

    def finish(self) -> None:
        self.state = UserState.DONE
