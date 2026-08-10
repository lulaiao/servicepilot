"""Stateful routing primitives."""

from servicepilot.routing.classifiers import IntentClassifier
from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    FactoredSlots,
    IssueType,
    RequestedAction,
    project_legacy_intent,
)
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.models import (
    AgentRole,
    DialogueState,
    IntentResult,
    RouteDecision,
)
from servicepilot.routing.router import StatefulRouter
from servicepilot.routing.structured_output import (
    build_factored_intent_prompt,
    parse_factored_intent_output,
)

__all__ = [
    "AgentRole",
    "DialogueState",
    "IntentResult",
    "IntentClassifier",
    "FactoredIntentResult",
    "FactoredSlots",
    "IssueType",
    "RequestedAction",
    "project_legacy_intent",
    "RouteDecision",
    "RuleIntentClassifier",
    "StatefulRouter",
    "build_factored_intent_prompt",
    "parse_factored_intent_output",
]
