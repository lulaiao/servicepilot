"""Family-split train/dev data for a supervised compositional intent pilot."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class MultiLabelCompositionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "servicepilot-multilabel-composition-v1"
    record_id: str
    family_id: str
    split: Literal["train", "dev"]
    category: str
    text: str
    labels: tuple[Intent, ...]
    semantic_signature_sha256: str


_DELIVERY = (
    "配送超过预计时间",
    "送达进度长时间停住",
    "履约节点已经逾期",
    "运输状态迟迟未完成",
    "骑手晚于承诺时刻",
    "物流轨迹持续没有更新",
    "商品没有按时送到",
    "配送耗时明显过长",
    "预计抵达时间已经过去",
    "订单仍滞留在运输途中",
    "承诺的交付节点已错过",
    "履约过程发生严重延误",
    "送达时间比约定晚很多",
    "配送任务一直没有结束",
    "物流进展停滞了很久",
    "订单迟迟没有完成交付",
    "运输用时超出正常范围",
    "商品到现在依然没有送达",
    "骑手进度超过预计节点",
    "配送链路出现长时间迟滞",
)
_ESCALATION_ACTION = (
    "转交人工客服处理",
    "创建正式投诉工单",
    "安排客服专员继续跟进",
    "把问题升级给人工团队",
    "登记投诉并让真人介入",
    "建立升级工单交给专员",
    "让人工坐席接手这个问题",
    "提交服务投诉并升级",
    "转给客服主管进一步处理",
    "让人工团队介入解决",
)
_ESCALATION = tuple(f"请{action}" for action in _ESCALATION_ACTION)
_VARIANTS = (
    "{body}",
    "订单 ML{index:03d}：{body}",
    "请按以下诉求处理——{body}",
)


def _signature(category: str, index: int, labels: tuple[Intent, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            {"category": category, "family_index": index, "labels": [x.value for x in labels]},
            sort_keys=True,
        ).encode()
    ).hexdigest()


def build_multilabel_composition_v1() -> tuple[MultiLabelCompositionRecord, ...]:
    families: list[tuple[str, str, tuple[Intent, ...]]] = []
    both = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)
    triple = (*both, Intent.PARTIAL_REFUND)

    for index in range(20):
        families.append(("explicit_pair", f"{_DELIVERY[index]}，{_ESCALATION[index % 10]}", both))
    for index in range(10):
        families.append(
            (
                "three_intent",
                f"{_DELIVERY[index + 5]}，{_ESCALATION[(index + 3) % 10]}，"
                f"另外部分退款{index + 7}元",
                triple,
            )
        )
    for index in range(10):
        families.append(
            (
                "delivery_only",
                f"{_DELIVERY[index + 10]}，本次只记录配送异常",
                (Intent.DELIVERY_DELAY,),
            )
        )
        families.append(
            (
                "negated_escalation",
                f"{_DELIVERY[index]}，但不要{_ESCALATION_ACTION[index % 10]}",
                (Intent.DELIVERY_DELAY,),
            )
        )
        families.append(
            (
                "conditional_future",
                f"{_DELIVERY[index]}，如果明天还没解决再{_ESCALATION_ACTION[(index + 2) % 10]}",
                (Intent.DELIVERY_DELAY,),
            )
        )
        families.append(
            (
                "historical_request",
                f"{_DELIVERY[index]}；之前已经"
                f"{_ESCALATION_ACTION[(index + 5) % 10]}，现在不要重复操作",
                (Intent.DELIVERY_DELAY,),
            )
        )
    for index in range(5):
        families.append(
            (
                "escalation_only",
                f"服务处理没有结果，{_ESCALATION[index + 1]}",
                (Intent.COMPLAINT_ESCALATION,),
            )
        )
        families.append(("unrelated", f"请解释第{index + 1}种统计学方法，不要操作订单", ()))

    category_seen: dict[str, int] = {}
    records = []
    for family_number, (category, body, labels) in enumerate(families, start=1):
        category_seen[category] = category_seen.get(category, 0) + 1
        category_index = category_seen[category]
        split: Literal["train", "dev"] = "dev" if category_index % 5 == 0 else "train"
        family_id = f"multilabel-v1-{category}-{category_index:02d}"
        signature = _signature(category, category_index, labels)
        for variant, template in enumerate(_VARIANTS, start=1):
            text = template.format(body=body, index=family_number)
            digest = hashlib.sha256(f"{family_id}:{variant}:{text}".encode()).hexdigest()
            records.append(
                MultiLabelCompositionRecord(
                    record_id=f"multilabel-v1-{digest[:20]}",
                    family_id=family_id,
                    split=split,
                    category=category,
                    text=text,
                    labels=labels,
                    semantic_signature_sha256=signature,
                )
            )
    return tuple(records)
