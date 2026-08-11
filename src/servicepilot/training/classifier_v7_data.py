"""Train-only remediation for post-sealed failure classes; no sealed text reuse."""

import hashlib
import json

from servicepilot.eval.models import Intent
from servicepilot.routing.structured_output import build_intent_prompt
from servicepilot.training.classifier_data import classifier_target_for_text
from servicepilot.training.classifier_v5_data import build_classifier_v5_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


REMEDIATION_RATIONALE = (
    "Use the selected v5 dataset rather than the rejected v6 continuation.",
    "Cover lifecycle-stop semantics without copying a consumed holdout utterance.",
    "Distinguish restoration of discount entitlement from cancelling an order.",
    "Reinforce requested_amount as a JSON string across incident classes.",
)

_LIFECYCLE_STOP = (
    "中止订单 V7C101 的后续交付，支付处理留到以后",
    "让这次履约到此为止，本次不处理资金返还",
    "订单 V7C103 不必再往下执行，费用先维持原样",
    "终结当前购买流程，不需要安排新的送达时段",
    "请停掉订单 V7C105 接下来的配送，退款另行商议",
    "后续交付不再进行，只办理撤单本身",
    "订单 V7C107 结束履约，既不改期也不退费",
    "停止继续准备这笔购买，款项问题之后再说",
)

_DISCOUNT_ENTITLEMENT_RESTORE = (
    "订单已经关闭，请把被占用的折扣资格重新放回账户",
    "撤单完成后抵扣权益没有复原，只处理这项权益",
    "交易早已取消，但优惠资格仍不可使用，请恢复它",
    "不用返款，把关闭交易时核销的折扣权益退回即可",
    "订单已是取消状态，请重新激活原来的抵扣资格",
    "这次不撤单也不退款，只修复未返还的优惠权益",
    "已终止的购买仍占着折扣名额，请释放该资格",
    "把取消交易消耗的抵扣权益恢复成可用状态",
)

_AMOUNT_STRING_CONTRACT: tuple[tuple[Intent, str], ...] = (
    (Intent.DUPLICATE_CHARGE, "账单重复收取同一笔费用，请退款41元"),
    (Intent.DUPLICATE_CHARGE, "一回消费产生两条扣款，请退我27元重复款"),
    (Intent.MISSING_OR_WRONG_ITEM, "少收到一件已付款商品，按漏送退款14元"),
    (Intent.MISSING_OR_WRONG_ITEM, "送错规格，针对错货部分退款22元"),
    (Intent.PARTIAL_REFUND, "保留订单其余内容，仅办理部分退款9元"),
    (Intent.PARTIAL_REFUND, "无需整单返还，直接申请局部退款17元"),
    (Intent.FULL_REFUND, "整单内容都无法使用，请退款完整58元"),
    (Intent.FULL_REFUND, "所有商品全部退款，本单金额58元原路返还"),
)


def build_classifier_v7_remediation() -> tuple[SFTTrainingRecord, ...]:
    examples = [
        *(('lifecycle_stop', Intent.CANCEL_ORDER, text) for text in _LIFECYCLE_STOP),
        *(("discount_entitlement_restore", Intent.COUPON_ISSUE, text) for text in _DISCOUNT_ENTITLEMENT_RESTORE),
        *(("amount_string_contract", intent, text) for intent, text in _AMOUNT_STRING_CONTRACT),
    ]
    counters: dict[str, int] = {}
    records = []
    for category, intent, text in examples:
        counters[category] = counters.get(category, 0) + 1
        index = counters[category]
        prompt = build_intent_prompt(text)
        completion = json.dumps(
            classifier_target_for_text(intent, text).model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(
            f"v7:{category}:{index}\n{prompt}\n{completion}".encode()
        ).hexdigest()
        records.append(
            SFTTrainingRecord(
                schema_version="servicepilot-classifier-sft-v7-remediation",
                record_id=f"classifier-v7-{digest[:20]}",
                source_record_id=f"v7-train-{category}-{index:02d}",
                split=DataSplit.TRAIN,
                messages=(
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": completion},
                ),
            )
        )
    return tuple(records)


def build_classifier_v7_sft() -> tuple[SFTTrainingRecord, ...]:
    """Append bounded remediation to v5; v6 is intentionally not inherited."""

    return build_classifier_v5_sft() + build_classifier_v7_remediation()
