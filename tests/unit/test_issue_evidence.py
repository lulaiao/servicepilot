from servicepilot.routing.factored_intent import FactoredIntentResult, IssueType
from servicepilot.routing.issue_evidence import bind_rule_first_issue, extract_issue_evidence
from servicepilot.routing.models import RiskLevel
from servicepilot.training.factored_classifier_catalog import build_factored_classifier_sft


def test_rule_first_issue_matches_every_factored_catalog_target() -> None:
    for record in build_factored_classifier_sft():
        text = record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]
        target = FactoredIntentResult.model_validate_json(record.messages[1]["content"])
        evidence = extract_issue_evidence(text)

        assert evidence is not None, record.source_record_id
        assert evidence.issue_type is target.issue_type, record.source_record_id


def test_ambiguous_domain_issue_abstains_for_model_fallback() -> None:
    assert extract_issue_evidence("订单里的商品有问题，请帮我看看") is None


def test_no_domain_signal_is_out_of_scope() -> None:
    evidence = extract_issue_evidence("给我制定一份旅行计划")

    assert evidence is not None
    assert evidence.issue_type is IssueType.OUT_OF_SCOPE
    assert evidence.reason == "no_service_domain_signal"


def test_binding_preserves_model_issue_on_abstention() -> None:
    generated = FactoredIntentResult(
        issue_type=IssueType.MISSING_OR_WRONG_ITEM,
        risk_level=RiskLevel.MEDIUM,
        confidence=0.6,
        needs_clarification=True,
    )

    bound = bind_rule_first_issue(generated, "订单里的商品有问题，请帮我看看")

    assert bound.issue_type is IssueType.MISSING_OR_WRONG_ITEM
