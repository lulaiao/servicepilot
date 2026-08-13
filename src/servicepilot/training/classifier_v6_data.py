"""Train-only label-boundary examples for the residual v5 semantic errors."""

import hashlib
import json

from servicepilot.eval.models import Intent
from servicepilot.routing.structured_output import build_intent_prompt
from servicepilot.training.classifier_data import classifier_target_for_text
from servicepilot.training.classifier_v5_data import build_classifier_v5_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord

LABEL_BOUNDARY_RULES = (
    "Ending an order without requesting money back is cancel_order, not reschedule.",
    "A missing or wrong item remains missing_or_wrong_item when refund is its remedy.",
    "A duplicate charge remains duplicate_charge when refund is its remedy.",
    "partial_refund is primary only when the user directly requests a partial amount "
    "without a more specific incident.",
    "requested_amount is serialized as a JSON string when known and null otherwise.",
)

_CANCEL_WITHOUT_REFUND = (
    "停止订单 V6C001，款项暂时不用退回",
    "这笔交易不再继续，先不要办理任何退款",
    "关闭订单 V6C003，但无需返还支付金额",
    "我放弃继续购买，只撤单不退钱",
    "终止订单 V6C005，退款事项不在本次处理范围",
    "请让当前订单失效，已付费用保持原状",
    "不再配送订单 V6C007，也不申请资金返还",
    "结束交易即可，不要创建退款记录",
    "订单 V6C009 需要撤单，暂不处理款项",
    "我不要这笔订单了，但这次只做取消",
    "终止后续交付，不要求退回任何金额",
    "作废订单 V6C012，别把它改到其他时段",
)

_MISSING_ITEM_PRIMARY = (
    "订单 V6M001 少送一件商品，请按缺失商品退款12元",
    "包裹内容不全，需要针对漏发部分退款8元",
    "订单 V6M003 发错了商品，请按错发问题退款15元",
    "少收到已付款的餐品，核实后退款6元",
    "订单 V6M005 有一项未送达，请处理缺件并退款10元",
    "收到的型号不对，需要按错货退款18元",
    "订单 V6M007 漏了一件，申请对应商品退款9元",
    "配送内容与清单不符，请处理错发并退款20元",
    "订单 V6M009 少送配件，请按缺失项退款7元",
    "实际收到的商品错误，需要退款11元并登记错货",
    "订单 V6M011 缺少一份餐品，请退款5元",
    "包裹里装错商品，按错误商品退款16元",
)

_DUPLICATE_CHARGE_PRIMARY = (
    "订单 V6D001 被重复扣费，请核查并退款58元",
    "同一交易扣了两遍，需要退款23元处理多收款",
    "订单 V6D003 出现重复收费，请退款31元",
    "账单里有两笔相同扣款，核实后退我19元",
    "订单 V6D005 多扣了一次，请按重复扣款退款42元",
    "支付记录重复入账，需要退还多收金额17元",
    "订单 V6D007 被收取两次费用，请退款26元",
    "一笔购买产生重复扣费，请退我34元",
    "订单 V6D009 多出一笔相同收费，需要退款29元",
    "银行卡对同一订单扣了两次，请退我13元",
    "订单 V6D011 重复记账，请处理并退款37元",
    "相同消费被再次收费，需要退款21元处理多扣款",
)

_DIRECT_PARTIAL_REFUND = (
    "订单 V6P001 只申请部分退款12元，没有错发或重复扣款",
    "我希望保留其余商品，仅退款8元",
    "订单 V6P003 直接办理局部退款15元，不是整单退款",
    "请从本次支付中部分退我6元",
    "订单 V6P005 申请部分金额退款10元",
    "其余费用保留，只需要退款18元",
    "订单 V6P007 不是全额退，只退款9元",
    "请直接创建一笔部分退款20元",
    "订单 V6P009 仅退其中7元，订单其余部分不变",
    "我提出的是金额11元的局部退款",
    "订单 V6P011 保留大部分收费，只退款5元",
    "无需判断错货或重复收费，直接部分退款16元",
)


def build_classifier_v6_label_boundaries() -> tuple[SFTTrainingRecord, ...]:
    groups = (
        ("cancel_without_refund", Intent.CANCEL_ORDER, _CANCEL_WITHOUT_REFUND),
        ("missing_item_primary", Intent.MISSING_OR_WRONG_ITEM, _MISSING_ITEM_PRIMARY),
        ("duplicate_charge_primary", Intent.DUPLICATE_CHARGE, _DUPLICATE_CHARGE_PRIMARY),
        ("direct_partial_refund", Intent.PARTIAL_REFUND, _DIRECT_PARTIAL_REFUND),
    )
    records = []
    for category, intent, texts in groups:
        for index, value in enumerate(texts, start=1):
            prompt = build_intent_prompt(value)
            completion = json.dumps(
                classifier_target_for_text(intent, value).model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            digest = hashlib.sha256(
                f"v6:{category}:{index}\n{prompt}\n{completion}".encode()
            ).hexdigest()
            records.append(
                SFTTrainingRecord(
                    schema_version="servicepilot-classifier-sft-v6-label-boundary",
                    record_id=f"classifier-v6-{digest[:20]}",
                    source_record_id=f"v6-train-{category}-{index:02d}",
                    split=DataSplit.TRAIN,
                    messages=(
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": completion},
                    ),
                )
            )
    return tuple(records)


def build_classifier_v6_sft() -> tuple[SFTTrainingRecord, ...]:
    """Preserve v4 dev and all v5 train records, then append v6 train only."""

    return build_classifier_v5_sft() + build_classifier_v6_label_boundaries()
