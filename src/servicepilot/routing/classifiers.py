"""Classifier contract used by routed Agents."""

from typing import Protocol

from servicepilot.routing.models import IntentResult


class IntentClassifier(Protocol):
    def classify(self, text: str) -> IntentResult: ...
