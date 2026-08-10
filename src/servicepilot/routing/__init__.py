"""Stateful routing primitives."""

from servicepilot.routing.classifiers import IntentClassifier
from servicepilot.routing.action_evidence import (
    ActionEvidence,
    bind_evidence_backed_actions,
    extract_requested_action_evidence,
    extract_requested_actions,
)
from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    FactoredSlots,
    IssueType,
    RequestedAction,
    project_legacy_intent,
)
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.issue_evidence import (
    IssueEvidence,
    bind_rule_first_issue,
    extract_issue_evidence,
)
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
    "ActionEvidence",
    "bind_evidence_backed_actions",
    "DialogueState",
    "IntentResult",
    "IssueEvidence",
    "IntentClassifier",
    "extract_requested_action_evidence",
    "extract_requested_actions",
    "bind_rule_first_issue",
    "extract_issue_evidence",
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
