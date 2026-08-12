"""Balanced family-split train/dev data for compositional intent v2."""

import hashlib
import json
from itertools import product
from typing import Literal

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class MultiLabelCompositionV2Record(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "servicepilot-multilabel-composition-v2"
    record_id: str
    family_id: str
    split: Literal["train", "dev"]
    category: str
    text: str
    labels: tuple[Intent, ...]
    semantic_signature_sha256: str


D = Intent.DELIVERY_DELAY
C = Intent.COMPLAINT_ESCALATION
R = Intent.PARTIAL_REFUND
LABELS = (D, C, R)

_DELIVERY_POSITIVE = (
    "交付时间已经超出页面给出的区间",
    "运输进度多次停留在同一节点",
    "约定的收货日期已过但商品未到",
    "配送任务超过预计时长仍未结束",
    "订单没有在承诺时段内送达",
    "物流状态很久没有产生新记录",
    "骑手未能按最初预计时间抵达",
    "货物仍滞留途中并已发生晚点",
)
_COMPLAINT_POSITIVE = (
    "请由人工服务团队正式受理",
    "我要建立一条服务申诉记录",
    "安排有权限的客服人员继续调查",
    "把处理过程上报给值班负责人",
    "请让真人坐席接管后续沟通",
    "登记服务问题并交专人答复",
    "需要人工团队复核本次处理",
    "请创建升级事项并安排回访",
)
_REFUND_POSITIVE = (
    "申请返还其中六元费用",
    "只退回缺失商品对应的价款",
    "请做一笔部分金额退款",
    "把本次配送费单独退还",
    "我要求退回部分货款而非整单",
    "返还损坏那一项的金额即可",
    "请退还八元差价",
    "仅对其中一件商品办理退款",
)
_DELIVERY_CONTRAST = (
    "订单其实按期交付，不要登记延误",
    "上次发生过晚点，这次已经准时收到",
    "若明天还没收到再查询延迟，现在先不处理",
    "我问的是配送规则，并非反馈当前订单晚到",
)
_COMPLAINT_CONTRAST = (
    "不要转人工，也不要建立申诉记录",
    "此前找过客服，这次无需再次升级",
    "如果后续仍无结果再找专人，目前不执行",
    "只是询问投诉流程，并没有要求现在提交",
)
_REFUND_CONTRAST = (
    "不要退款，本次只需要解释费用",
    "之前退过差价，这次没有新的退款诉求",
    "若商品损坏再考虑退款，目前不执行",
    "只是询问退款规则，并非现在申请退款",
)
_CONTEXT_SUBJECTS = (
    "这份生鲜订单",
    "本次午餐订单",
    "寄往公司的文件",
    "家用电器包裹",
    "晚间商超订单",
    "送往学校的用品",
    "本周购买的药品",
    "需要签收的礼物",
)
_CONTEXT_TIMES = (
    "工作日上午",
    "周末傍晚",
    "昨天夜间",
    "今天午后",
    "本周约定日期",
)
_WRAPPERS = (
    "{body}",
    "关于订单 V2-{number:03d}，我的当前诉求是：{body}",
)


def _clause(label: Intent, positive: bool, index: int) -> str:
    if label == D:
        values = _DELIVERY_POSITIVE if positive else _DELIVERY_CONTRAST
    elif label == C:
        values = _COMPLAINT_POSITIVE if positive else _COMPLAINT_CONTRAST
    else:
        values = _REFUND_POSITIVE if positive else _REFUND_CONTRAST
    return values[index % len(values)]


def build_multilabel_composition_v2() -> tuple[MultiLabelCompositionV2Record, ...]:
    records = []
    family_number = 0
    for bits in product((False, True), repeat=3):
        labels = tuple(label for label, positive in zip(LABELS, bits, strict=True) if positive)
        signature_name = "".join("1" if value else "0" for value in bits)
        category = f"label_set_{signature_name}"
        for category_index in range(1, 41):
            family_number += 1
            clauses = [
                _clause(label, positive, category_index + offset)
                for offset, (label, positive) in enumerate(zip(LABELS, bits, strict=True))
            ]
            rotations = category_index % len(clauses)
            clauses = clauses[rotations:] + clauses[:rotations]
            context = (
                f"{_CONTEXT_SUBJECTS[(category_index - 1) % len(_CONTEXT_SUBJECTS)]}"
                f"原定在{_CONTEXT_TIMES[(category_index - 1) // len(_CONTEXT_SUBJECTS)]}处理"
            )
            body = f"{context}；" + "；".join(clauses)
            split: Literal["train", "dev"] = "dev" if category_index % 5 == 0 else "train"
            family_id = f"multilabel-v2-{signature_name}-{category_index:02d}"
            semantic_signature = hashlib.sha256(
                json.dumps(
                    {
                        "label_set": signature_name,
                        "family_index": category_index,
                        "scope_pattern": category_index % 4,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            for variant, wrapper in enumerate(_WRAPPERS, start=1):
                text = wrapper.format(body=body, number=family_number)
                digest = hashlib.sha256(f"{family_id}:{variant}:{text}".encode()).hexdigest()
                records.append(
                    MultiLabelCompositionV2Record(
                        record_id=f"multilabel-v2-{digest[:20]}",
                        family_id=family_id,
                        split=split,
                        category=category,
                        text=text,
                        labels=labels,
                        semantic_signature_sha256=semantic_signature,
                    )
                )
    return tuple(records)
