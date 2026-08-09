"""Shared-policy multi-role baseline driven by the stateful router."""

from typing import Any

from servicepilot.agents.completion import OutputCompletionVerifier
from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval.models import Intent, TraceEvent, TraceRole
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.mcp_gateway.gateway import ReliableToolGateway, ToolResult
from servicepilot.routing.classifiers import IntentClassifier
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.models import DialogueState, ToolObservation
from servicepilot.routing.router import ROLE_INSTRUCTIONS, StatefulRouter


class RoutedRuleAgent(RuleBasedSingleAgent):
    """Use one deterministic policy with explicit role-specific routing."""

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        *,
        observation_rerouting: bool = True,
    ) -> None:
        self.classifier = classifier or RuleIntentClassifier()
        self.safety_classifier = RuleIntentClassifier()
        self.router = StatefulRouter()
        self.state: DialogueState | None = None
        self.observation_rerouting = observation_rerouting
        self.safety_override_count = 0
        self.completion_verifier = OutputCompletionVerifier()
        self.completion_required_intents: tuple[Intent, ...] = ()

    async def run(
        self,
        scenario: Any,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
    ) -> Any:
        trajectory = await super().run(scenario, simulator, gateway)
        decision = self.completion_verifier.verify(
            self.completion_required_intents, trajectory.events
        )
        if trajectory.claimed_success and not decision.allowed:
            return trajectory.model_copy(
                update={
                    "claimed_success": False,
                    "final_message": "处理未完成，缺少必要的成功工具证据。",
                }
            )
        return trajectory

    def detect_intents(self, text: str) -> tuple[Intent, ...]:
        intent = self.classifier.classify(text)
        safety = self.safety_classifier.classify(text)
        self.completion_required_intents = (
            safety.primary_intent,
            *safety.secondary_intents,
        )
        # A narrow deterministic guardrail protects conjunctions and prompt
        # injection. It does not replace ordinary learned single-intent routing.
        if safety.injection_detected or safety.secondary_intents:
            intent = safety
            self.safety_override_count += 1
        self.state = DialogueState(intent=intent)
        return (intent.primary_intent, *intent.secondary_intents)

    async def _execute_intent(
        self,
        intent: Intent,
        order_id: str,
        user_text: str,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
        trace_id: str,
        events: list[TraceEvent],
    ) -> bool:
        state = self._require_state()
        slots = {**state.confirmed_slots, "order_id": order_id}
        self.state = state.model_copy(
            update={
                "confirmed_slots": slots,
                "intent": state.intent.model_copy(
                    update={"needs_clarification": False}
                ),
            }
        )
        return await super()._execute_intent(
            intent,
            order_id,
            user_text,
            simulator,
            gateway,
            trace_id,
            events,
        )

    async def _call(
        self,
        gateway: ReliableToolGateway,
        trace_id: str,
        events: list[TraceEvent],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        state = self._require_state()
        self.state = state.model_copy(update={"pending_action": tool_name})
        decision = self.router.route(self.state)
        self._event(
            events,
            TraceRole.ASSISTANT,
            "route",
            f"{decision.role.value}: {decision.reason}; "
            f"instruction={ROLE_INSTRUCTIONS[decision.role]}",
        )
        result = await super()._call(
            gateway, trace_id, events, tool_name, arguments
        )
        state = self._require_state()
        if result.ok:
            completed = (*state.completed_tools, tool_name)
            failed = state.failed_tools
        else:
            completed = state.completed_tools
            failed = (
                *state.failed_tools,
                ToolObservation(
                    tool_name=tool_name,
                    ok=False,
                    error_code=result.error.code if result.error else None,
                ),
            )
        self.state = state.model_copy(
            update={
                "turn": state.turn + 1,
                "completed_tools": completed,
                "failed_tools": failed,
                "pending_action": None,
                "tool_budget_remaining": state.tool_budget_remaining - 1,
            }
        )
        if self.observation_rerouting:
            observation_route = self.router.route(self.state)
            self._event(
                events,
                TraceRole.ASSISTANT,
                "reroute_after_observation",
                f"{observation_route.role.value}: {observation_route.reason}",
            )
        return result

    def _require_state(self) -> DialogueState:
        if self.state is None:
            raise RuntimeError("routing state has not been initialized")
        return self.state
