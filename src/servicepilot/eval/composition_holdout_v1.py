"""Post-adversarial independently authored composition holdout fixtures."""

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class CompositionHoldoutCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    split: str = "sealed_test"
    category: str
    text: str
    model_primary: Intent
    model_secondary: tuple[Intent, ...] = ()
    should_bind: bool


_DELIVERY = (
    "约好的送达钟点过去很久",
    "餐品到现在仍未出现",
    "配送轨迹卡着不动",
    "预计抵达节点早已错过",
    "本次履约耗时超出承诺",
)
_ESCALATION = (
    "请安排真人客服跟进",
    "我要把问题升级给专员",
)


def build_composition_holdout_v1() -> tuple[CompositionHoldoutCase, ...]:
    cases: list[CompositionHoldoutCase] = []

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
            CompositionHoldoutCase(
                case_id=f"composition-holdout-v1-{category}-{index:02d}",
                category=category,
                text=text,
                model_primary=primary,
                model_secondary=secondary,
                should_bind=should_bind,
            )
        )

    for delivery in _DELIVERY:
        for escalation in _ESCALATION:
            add("explicit_pair", f"{delivery}；{escalation}", True)

    negated = (
        "真人客服这次不用介入",
        "先别升级给任何专员",
    )
    for delivery in _DELIVERY:
        for phrase in negated:
            add("negated_escalation", f"{delivery}，{phrase}", False)

    conditional = (
        "到今晚仍没结果的话，再安排真人客服跟进",
        "后面若继续拖延，届时再升级给专员",
    )
    for delivery in _DELIVERY:
        for phrase in conditional:
            add("conditional_future", f"{delivery}；{phrase}", False)

    historical = (
        "早些时候找过真人客服，现在只登记本次情况",
        "过去已经升级给专员，这回不要重复提交",
    )
    for delivery in _DELIVERY:
        for phrase in historical:
            add("historical_request", f"{delivery}。{phrase}", False)

    for delivery in _DELIVERY:
        for escalation in _ESCALATION:
            add(
                "existing_third_intent",
                f"{delivery}；{escalation}；同时部分退款11元",
                False,
                secondary=(Intent.PARTIAL_REFUND,),
            )

    unrelated = (
        Intent.OUT_OF_SCOPE,
        Intent.ORDER_QUERY,
    )
    for delivery in _DELIVERY:
        for primary in unrelated:
            add(
                "unrelated_model_output",
                f"{delivery}；请安排真人客服跟进",
                False,
                primary=primary,
            )
    return tuple(cases)
