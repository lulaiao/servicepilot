"""Deterministic train/dev adversarial cases for compositional intent binding."""

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class CompositionAdversarialCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    text: str
    model_primary: Intent
    model_secondary: tuple[Intent, ...] = ()
    should_bind: bool


_DELIVERY = (
    "配送已经超时",
    "送达明显逾期",
    "履约超过约定时间",
    "运输进度长期停滞",
    "物流迟迟没有完成",
    "骑手晚于预计节点",
    "商品至今没有送到",
    "配送过程发生延误",
)
_ESCALATION = (
    "请转人工处理",
    "我要提交正式投诉",
    "请让客服专员介入",
    "同时创建升级工单",
)
_NEGATED = (
    "但不要转人工处理",
    "无需提交正式投诉",
    "不创建任何升级工单",
)
_CONDITIONAL = (
    "如果明天仍未解决再转人工处理",
    "若之后继续延误才提交正式投诉",
    "要是再次发生问题再创建升级工单",
)
_HISTORICAL = (
    "上次也要求过人工投诉，现在只查询状态",
    "此前已经转过人工，本次不要再次升级",
)


def build_composition_adversarial_v1() -> tuple[CompositionAdversarialCase, ...]:
    cases: list[CompositionAdversarialCase] = []

    def add(
        category: str,
        text: str,
        should_bind: bool,
        *,
        primary: Intent = Intent.DELIVERY_DELAY,
        secondary: tuple[Intent, ...] = (),
    ) -> None:
        index = sum(item.category == category for item in cases) + 1
        cases.append(
            CompositionAdversarialCase(
                case_id=f"composition-adv-v1-{category}-{index:03d}",
                category=category,
                text=text,
                model_primary=primary,
                model_secondary=secondary,
                should_bind=should_bind,
            )
        )

    for delivery in _DELIVERY:
        for escalation in _ESCALATION:
            add("explicit_pair", f"{delivery}，{escalation}", True)
        for negated in _NEGATED:
            add("negated_escalation", f"{delivery}，{negated}", False)
        for conditional in _CONDITIONAL:
            add("conditional_future", f"{delivery}；{conditional}", False)
        for historical in _HISTORICAL:
            add("historical_request", f"{delivery}。{historical}", False)
        add("delivery_only", f"{delivery}，只登记配送问题", False)
        add(
            "three_intent",
            f"{delivery}，请转人工处理，另外申请部分退款12元",
            False,
            secondary=(Intent.PARTIAL_REFUND,),
        )
    for escalation in _ESCALATION:
        add(
            "escalation_only",
            f"服务体验很差，{escalation}",
            False,
            primary=Intent.COMPLAINT_ESCALATION,
        )
        add(
            "unrelated_model_output",
            f"配送已经超时，{escalation}",
            False,
            primary=Intent.OUT_OF_SCOPE,
        )
    return tuple(cases)
