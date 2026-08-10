from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.eval.simulator import FSMUserSimulator, UserState


def test_user_reveals_order_only_after_question() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.ORDER_QUERY)
    simulator = FSMUserSimulator(scenario)

    assert simulator.start() == scenario.user_utterance
    assert scenario.order_id in simulator.answer_order_question()
    assert simulator.state is UserState.ORDER_REVEALED


def test_user_rejects_unexplained_confirmation() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.CANCEL_ORDER)
    simulator = FSMUserSimulator(scenario)
    simulator.start()
    simulator.answer_order_question()

    response = simulator.answer_confirmation("")

    assert "不同意" in response
    assert simulator.state is UserState.REFUSED


def test_user_can_confirm_two_independently_previewed_writes() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.CANCEL_ORDER)
    simulator = FSMUserSimulator(scenario)
    simulator.start()
    simulator.answer_order_question()

    assert simulator.answer_confirmation("第一次写入影响说明") == "我确认执行"
    assert simulator.answer_confirmation("第二次写入影响说明") == "我确认执行"
    assert simulator.state is UserState.CONFIRMED
