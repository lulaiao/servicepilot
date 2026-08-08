"""Transactional Agent gated by authoritative retrieved policy evidence."""

from collections.abc import Mapping
from typing import Protocol

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval.models import ScenarioSpec, TraceEvent, TraceRole, Trajectory
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.mcp_gateway.gateway import ReliableToolGateway


class PolicyEvidenceProvider(Protocol):
    def retrieve(self, scenario: ScenarioSpec) -> tuple[str, ...]: ...


class StaticPolicyEvidenceProvider:
    """Immutable adapter for revision-pinned offline retrieval outputs."""

    def __init__(self, evidence_by_scenario: Mapping[str, tuple[str, ...]]) -> None:
        self._evidence = dict(evidence_by_scenario)

    def retrieve(self, scenario: ScenarioSpec) -> tuple[str, ...]:
        return self._evidence.get(scenario.scenario_id, ())


class RetrievalGatedTransactionalAgent(RuleBasedSingleAgent):
    """Require complete retrieved evidence before policy-sensitive actions."""

    def __init__(self, evidence_provider: PolicyEvidenceProvider) -> None:
        self.evidence_provider = evidence_provider

    async def run(
        self,
        scenario: ScenarioSpec,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
    ) -> Trajectory:
        if not scenario.gold_evidence_ids:
            return await super().run(scenario, simulator, gateway)
        evidence_ids = self.evidence_provider.retrieve(scenario)
        required = set(scenario.gold_evidence_ids)
        if not required <= set(evidence_ids):
            return self._blocked_trajectory(scenario, simulator, evidence_ids)
        trajectory = await super().run(scenario, simulator, gateway)
        evidence_event = TraceEvent(
            step=len(trajectory.events),
            role=TraceRole.TOOL,
            kind="tool_result",
            content="检索到适用政策证据并通过交易前门控。",
            tool_name="search_policy",
            arguments={"query": scenario.user_utterance, "top_k": 3},
            result={"ok": True, "data": {"evidence_ids": list(evidence_ids)}},
        )
        return trajectory.model_copy(update={"events": (*trajectory.events, evidence_event)})

    def _blocked_trajectory(
        self,
        scenario: ScenarioSpec,
        simulator: FSMUserSimulator,
        evidence_ids: tuple[str, ...],
    ) -> Trajectory:
        events: list[TraceEvent] = []
        user_text = simulator.start()
        self._event(events, TraceRole.USER, "message", user_text)
        self._event(
            events,
            TraceRole.TOOL,
            "tool_result",
            "政策证据不完整，禁止进入交易写入流程。",
            "search_policy",
            {"query": user_text, "top_k": 3},
            {"ok": True, "data": {"evidence_ids": list(evidence_ids)}},
        )
        message = "缺少完成该操作所需的权威政策证据，已停止且未执行写操作。"
        self._event(events, TraceRole.ASSISTANT, "final", message)
        simulator.finish()
        return self._trajectory(
            scenario,
            f"trajectory-{scenario.scenario_id}",
            events,
            False,
            message,
            self.detect_intents(user_text),
        )
