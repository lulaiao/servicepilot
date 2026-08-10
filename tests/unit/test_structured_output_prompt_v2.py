from servicepilot.routing.structured_output import build_intent_prompt, build_intent_prompt_v2


def test_prompt_v2_makes_semantic_precedence_and_slot_types_explicit() -> None:
    prompt = build_intent_prompt_v2("测试输入")

    assert "即使用户明确不退款" in prompt
    assert "订单继续有效" in prompt
    assert "不得覆盖具体问题标签" in prompt
    assert "绝不能输出JSON数字" in prompt
    assert prompt.endswith("用户输入：测试输入")


def test_prompt_v1_remains_unchanged_and_distinct() -> None:
    prompt = build_intent_prompt("测试输入")

    assert "即使用户明确不退款" not in prompt
    assert prompt != build_intent_prompt_v2("测试输入")
