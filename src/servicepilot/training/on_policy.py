"""Executable on-policy reward adapter for the deployed intent classifier."""

import asyncio
import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.models import Intent, ScenarioSpec
from servicepilot.eval.runner import run_scenario
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.models import IntentResult
from servicepilot.routing.structured_output import build_intent_prompt, parse_intent_output
from servicepilot.training.classifier_data import classifier_target
from servicepilot.training.reward import OutcomeRewardSignals, RewardResult, outcome_reward

_HIGH_RISK_INTENTS = frozenset(
    {
        Intent.CANCEL_ORDER,
        Intent.FULL_REFUND,
        Intent.PARTIAL_REFUND,
        Intent.MISSING_OR_WRONG_ITEM,
        Intent.DUPLICATE_CHARGE,
        Intent.RESCHEDULE,
    }
)


class OnPolicyRewardEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    completion: str
    parsed: bool
    reward: RewardResult
    task_success: bool = False
    final_state_correct: bool = False
    policy_compliant: bool = False
    false_success: bool = False
    tool_sequence_valid: bool = False
    guardrail_rescue: bool = False
    runtime_error: str | None = None


class _FixedIntentClassifier:
    def __init__(self, result: IntentResult) -> None:
        self.result = result

    def classify(self, text: str) -> IntentResult:
        del text
        return self.result


def classifier_grpo_examples(scenarios: tuple[ScenarioSpec, ...]) -> tuple[dict[str, Any], ...]:
    """Build prompts whose generated object is the actually deployed classifier output."""

    return tuple(
        {
            "prompt": [{"role": "user", "content": build_intent_prompt(scenario.user_utterance)}],
            "scenario_id": scenario.scenario_id,
        }
        for scenario in model_owned_scenarios(scenarios)
    )


def model_owned_scenarios(scenarios: tuple[ScenarioSpec, ...]) -> tuple[ScenarioSpec, ...]:
    """Exclude inputs whose classification is always owned by a deterministic guardrail."""

    guardrail = RuleIntentClassifier()
    return tuple(
        scenario
        for scenario in scenarios
        if not (
            (result := guardrail.classify(scenario.user_utterance)).injection_detected
            or result.secondary_intents
        )
    )


def gold_completion(scenario: ScenarioSpec) -> str:
    return json.dumps(
        classifier_target(scenario).model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )


class ExecutableClassifierReward:
    """Execute sampled classifier JSON through the real Agent, tools, and Judge."""

    def __init__(self, scenarios: tuple[ScenarioSpec, ...]) -> None:
        self.scenarios = {item.scenario_id: item for item in scenarios}
        self.evidence: list[OnPolicyRewardEvidence] = []

    async def score_async(self, completion: str, scenario_id: str) -> OnPolicyRewardEvidence:
        scenario = self.scenarios[scenario_id]
        try:
            parsed = parse_intent_output(completion)
        except (ValueError, json.JSONDecodeError):
            evidence = OnPolicyRewardEvidence(
                scenario_id=scenario_id,
                completion=completion,
                parsed=False,
                reward=outcome_reward(
                    OutcomeRewardSignals(
                        task_success=False,
                        final_state_correct=False,
                        policy_compliant=False,
                        false_success=False,
                        unsafe_high_risk_error=False,
                        schema_valid=False,
                    )
                ),
            )
            self.evidence.append(evidence)
            return evidence
        try:
            _, judge, _ = await run_scenario(
                scenario,
                agent=RoutedRuleAgent(classifier=_FixedIntentClassifier(parsed)),
            )
        except Exception as exc:
            evidence = OnPolicyRewardEvidence(
                scenario_id=scenario_id,
                completion=completion,
                parsed=True,
                reward=RewardResult(
                    total=-1.25,
                    components={"runtime_error": -1.25},
                    hard_gate="runtime_error",
                ),
                runtime_error=f"{type(exc).__name__}: {exc}",
            )
            self.evidence.append(evidence)
            return evidence
        unsafe = scenario.intent in _HIGH_RISK_INTENTS and (
            not judge.policy_compliant or not judge.tool_sequence_valid or judge.false_success
        )
        expected = classifier_target(scenario)
        contract_mismatch = (
            parsed.primary_intent is not expected.primary_intent
            or parsed.secondary_intents != expected.secondary_intents
            or parsed.injection_detected != expected.injection_detected
        )
        guardrail_rescue = (contract_mismatch) and (
            expected.risk_level.value == "high"
            or bool(expected.secondary_intents)
            or expected.injection_detected
        )
        reward = outcome_reward(
            OutcomeRewardSignals(
                task_success=judge.task_success,
                final_state_correct=judge.final_state_correct,
                policy_compliant=judge.policy_compliant,
                false_success=judge.false_success,
                unsafe_high_risk_error=unsafe,
                schema_valid=True,
            )
        )
        if guardrail_rescue:
            reward = RewardResult(
                total=-0.75,
                components={"guardrail_rescue": -0.75},
                hard_gate="guardrail_rescue",
            )
        elif contract_mismatch:
            reward = RewardResult(
                total=-0.5,
                components={"classifier_contract_mismatch": -0.5},
                hard_gate="classifier_contract_mismatch",
            )
        evidence = OnPolicyRewardEvidence(
            scenario_id=scenario_id,
            completion=completion,
            parsed=True,
            reward=reward,
            task_success=judge.task_success,
            final_state_correct=judge.final_state_correct,
            policy_compliant=judge.policy_compliant,
            false_success=judge.false_success,
            tool_sequence_valid=judge.tool_sequence_valid,
            guardrail_rescue=guardrail_rescue,
        )
        self.evidence.append(evidence)
        return evidence

    def score(self, completion: str, scenario_id: str) -> OnPolicyRewardEvidence:
        return asyncio.run(self.score_async(completion, scenario_id))

    def __call__(
        self,
        prompts: list[Any],
        completions: list[Any],
        scenario_id: list[str],
        **kwargs: Any,
    ) -> list[float]:
        del prompts, kwargs
        rewards = []
        for completion, current_scenario_id in zip(completions, scenario_id, strict=True):
            if isinstance(completion, list):
                completion = completion[0]["content"]
            evidence = self.score(str(completion), current_scenario_id)
            rewards.append(evidence.reward.total)
        return rewards
