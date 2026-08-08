"""Evaluation Harness with isolated deterministic trial environments."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.domain.models import (
    BusinessType,
    Coupon,
    CouponStatus,
    Delivery,
    DeliveryStatus,
    Merchant,
    MerchantStatus,
    Order,
    OrderStatus,
    PaymentRecord,
    PaymentStatus,
)
from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.domain.services import TransactionService
from servicepilot.eval.judge import DeterministicJudge
from servicepilot.eval.models import (
    EvalReport,
    JudgeResult,
    ScenarioSpec,
    Trajectory,
)
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.models import HarnessBudgets, HarnessRunConfig, HarnessSession
from servicepilot.harness.runtime import AgentRuntimeHarness
from servicepilot.mcp_gateway.faults import FaultPlan
from servicepilot.mcp_gateway.gateway import ReliableToolGateway
from servicepilot.mcp_servers.registry import ServiceRegistry
from servicepilot.policies.engine import PolicyEngine


@dataclass(frozen=True)
class TrialEnvironment:
    repository: InMemoryRepository
    gateway: ReliableToolGateway


class EvaluationHarness:
    def __init__(
        self,
        *,
        code_revision: str = "unknown",
        model_revision: str = "deterministic-rule",
        prompt_revision: str = "phase4-rule-v1",
        budgets: HarnessBudgets | None = None,
    ) -> None:
        self.code_revision = code_revision
        self.model_revision = model_revision
        self.prompt_revision = prompt_revision
        self.budgets = budgets or HarnessBudgets(timeout_seconds=0.1)
        self.sessions: dict[str, HarnessSession] = {}

    async def run_scenario(
        self,
        scenario: ScenarioSpec,
        agent: RuleBasedSingleAgent | None = None,
    ) -> tuple[Trajectory, JudgeResult, InMemoryRepository]:
        environment = build_trial_environment(scenario, self.budgets)
        config = HarnessRunConfig(
            code_revision=self.code_revision,
            scenario_sha256=hashlib.sha256(
                scenario.model_dump_json().encode()
            ).hexdigest(),
            model_revision=self.model_revision,
            prompt_revision=self.prompt_revision,
            budgets=self.budgets,
        )
        runtime = AgentRuntimeHarness()
        session = await runtime.run(
            scenario=scenario,
            agent=agent or RuleBasedSingleAgent(),
            simulator=FSMUserSimulator(scenario),
            gateway=environment.gateway,
            config=config,
        )
        self.sessions[session.session_id] = session
        if session.trajectory is None:
            raise RuntimeError(
                f"Harness stopped without trajectory: {session.termination_reason}"
            )
        result = DeterministicJudge().evaluate(
            scenario, session.trajectory, environment.repository
        )
        return session.trajectory, result, environment.repository

    async def run_suite(
        self,
        scenarios: tuple[ScenarioSpec, ...],
        agent_factory: Callable[[], RuleBasedSingleAgent] = RuleBasedSingleAgent,
    ) -> tuple[tuple[Trajectory, ...], tuple[JudgeResult, ...], EvalReport]:
        trajectories: list[Trajectory] = []
        results: list[JudgeResult] = []
        for scenario in scenarios:
            trajectory, result, _ = await self.run_scenario(
                scenario, agent=agent_factory()
            )
            trajectories.append(trajectory)
            results.append(result)
        return (
            tuple(trajectories),
            tuple(results),
            build_report(scenarios, results),
        )


def build_report(
    scenarios: tuple[ScenarioSpec, ...], results: list[JudgeResult]
) -> EvalReport:
    count = len(results)
    by_intent: dict[str, dict[str, float | int]] = {}
    results_by_id = {item.scenario_id: item for item in results}
    for scenario in scenarios:
        bucket = by_intent.setdefault(
            scenario.intent.value, {"count": 0, "success_count": 0}
        )
        bucket["count"] = int(bucket["count"]) + 1
        result = results_by_id[scenario.scenario_id]
        bucket["success_count"] = int(bucket["success_count"]) + int(
            result.task_success
        )
    for bucket in by_intent.values():
        bucket["success_rate"] = round(
            int(bucket["success_count"]) / int(bucket["count"]), 4
        )
    successes = sum(item.task_success for item in results)
    return EvalReport(
        scenario_count=count,
        task_success_count=successes,
        executable_task_success_rate=round(successes / count, 4),
        final_state_accuracy=round(
            sum(item.final_state_correct for item in results) / count, 4
        ),
        policy_violation_rate=round(
            sum(not item.policy_compliant for item in results) / count, 4
        ),
        false_success_rate=round(
            sum(item.false_success for item in results) / count, 4
        ),
        average_turns=round(sum(item.turns for item in results) / count, 3),
        average_tool_calls=round(
            sum(item.tool_calls for item in results) / count, 3
        ),
        by_intent=by_intent,
        failures=tuple(item for item in results if not item.task_success),
    )


def seed_repository(scenario: ScenarioSpec) -> InMemoryRepository:
    repository = InMemoryRepository()
    created_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    order = Order(
        order_id=scenario.order_id,
        user_id=scenario.user_id,
        merchant_id=f"merchant-{scenario.scenario_id}",
        status=scenario.initial_order_status,
        paid_amount=Decimal("58.00"),
        coupon_id=f"coupon-{scenario.scenario_id}",
        city="Shanghai",
        business_type=BusinessType.FOOD_DELIVERY,
        created_at=created_at,
        policy_version="2026.1",
    )
    repository.add_order(order)
    repository.add_coupon(
        Coupon(
            coupon_id=order.coupon_id or "",
            user_id=order.user_id,
            status=CouponStatus.USED,
            order_id=order.order_id,
        )
    )
    repository.add_payment(
        PaymentRecord(
            payment_id=f"payment-{scenario.scenario_id}",
            order_id=order.order_id,
            amount=order.paid_amount,
            status=PaymentStatus.CAPTURED,
            charged_at=created_at,
        )
    )
    repository.add_merchant(
        Merchant(order.merchant_id, MerchantStatus.OPEN, order.city)
    )
    repository.add_delivery(
        Delivery(
            order.order_id,
            (
                DeliveryStatus.DELAYED
                if scenario.initial_order_status is OrderStatus.PICKED_UP
                else DeliveryStatus.UNASSIGNED
            ),
            created_at,
        )
    )
    return repository


def build_trial_environment(
    scenario: ScenarioSpec, budgets: HarnessBudgets
) -> TrialEnvironment:
    repository = seed_repository(scenario)
    policies = PolicyEngine.default()
    registry = ServiceRegistry(
        repository, TransactionService(repository, policies), policies
    )
    gateway = ReliableToolGateway(
        registry,
        timeout_seconds=budgets.timeout_seconds,
        max_retries=budgets.max_retries,
        tool_budget=budgets.max_tool_calls,
        faults=FaultPlan(
            {tool: list(faults) for tool, faults in scenario.faults.items()}
        ),
        backoff=lambda _: None,
    )
    return TrialEnvironment(repository=repository, gateway=gateway)
