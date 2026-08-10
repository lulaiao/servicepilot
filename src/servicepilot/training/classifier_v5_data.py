"""Train-only hard negatives for v4 development failure categories."""

import hashlib
import json

from servicepilot.eval.models import Intent
from servicepilot.routing.structured_output import build_intent_prompt
from servicepilot.training.classifier_data import classifier_target_for_text
from servicepilot.training.classifier_v4_catalog import build_classifier_v4_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord

_CANCEL_NOT_RESCHEDULE = (
    "停止订单 V5C001，配送时间不用调整",
    "这次购买不再继续，请撤销而不是改约",
    "订单 V5C003 直接取消，不需要选择新时段",
    "我改变了购买决定，请终止交易但别改配送时间",
    "请关闭订单 V5C005，原预约安排无需变更",
    "不是换时间，我要取消整个订单",
    "订单 V5C007 不再需要，请先预览取消影响",
    "请结束本次履约，不要把它推迟到其他日期",
    "撤销订单 V5C009，但不要发起改期操作",
    "我决定放弃这笔交易，不是调整送达计划",
    "按确认流程取消订单 V5C011，新时间不用填写",
    "这单不要继续配送，请作废而非重新预约",
)

_RESCHEDULE_NOT_CANCEL = (
    "保留订单 V5R001，只把送达调整到明日下午三点",
    "我仍然需要商品，请改约而不是取消",
    "订单 V5R003 换到明日15点，不要终止交易",
    "购买决定不变，只修改预约配送时段",
    "请预览订单 V5R005 的时间调整，不办理撤销",
    "不是放弃订单，我只想换一个送达日期",
    "订单 V5R007 保持有效，将履约改到明天下午",
    "不要取消这笔交易，请重新安排配送时间",
    "把订单 V5R009 延后到15点，其他内容不变",
    "我会继续购买，但当前预约时间需要修改",
    "按确认流程为订单 V5R011 改期，不做退款取消",
    "这单继续履约，只把送达计划换到明日",
)

_DELAY_AND_ESCALATION = (
    "订单 V5M001 已经迟到，同时请建立人工投诉",
    "配送长时间未完成，而且我要客服专员介入",
    "先登记订单 V5M003 的运输超时，再创建投诉工单",
    "送达超过承诺时间，并且自动客服没有解决问题",
    "订单 V5M005 发生履约延误，还需要转交人工团队",
    "请同时上报配送迟滞与正式投诉",
    "订单 V5M007 一直没有送到，随后让专员接手",
    "记录本次超时，并为服务问题建立人工工单",
    "订单 V5M009 运输进度停滞，而且我要升级客服",
    "配送异常和投诉升级两个诉求都要完成",
    "订单 V5M011 超过预计时间，请同步转人工处理",
    "上报迟到情况，然后登记一条客服投诉",
    "订单 V5M013 仍在途中，同时安排人工跟进",
    "送达延误尚未解决，我还要创建升级工单",
    "订单 V5M015 配送逾期，并请客服人员介入",
    "既要记录运输超时，也要提交正式投诉",
    "订单 V5M017 迟迟未完成履约，请一并转交专员",
    "先处理送达异常，再让人工团队继续跟进",
    "订单 V5M019 已晚于承诺节点，同时建立投诉记录",
    "配送进度卡住了，而且我要求人工客服处理",
    "订单 V5M021 出现延误，请上报并升级工单",
    "登记运输迟到，同时把问题交给客服专员",
    "订单 V5M023 没有按时送达，还需要投诉商家服务",
    "延迟报告与人工投诉都不能遗漏",
)


def build_classifier_v5_hard_negatives() -> tuple[SFTTrainingRecord, ...]:
    groups = (
        ("cancel_not_reschedule", Intent.CANCEL_ORDER, _CANCEL_NOT_RESCHEDULE),
        ("reschedule_not_cancel", Intent.RESCHEDULE, _RESCHEDULE_NOT_CANCEL),
        ("delay_and_escalation", Intent.MULTI_INTENT, _DELAY_AND_ESCALATION),
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
                f"v5:{category}:{index}\n{prompt}\n{completion}".encode()
            ).hexdigest()
            records.append(
                SFTTrainingRecord(
                    schema_version="servicepilot-classifier-sft-v5-hard-negative",
                    record_id=f"classifier-v5-{digest[:20]}",
                    source_record_id=f"v5-train-{category}-{index:02d}",
                    split=DataSplit.TRAIN,
                    messages=(
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": completion},
                    ),
                )
            )
    return tuple(records)


def build_classifier_v5_sft() -> tuple[SFTTrainingRecord, ...]:
    """Keep v4 dev immutable and append only newly authored train records."""

    return build_classifier_v4_sft() + build_classifier_v5_hard_negatives()
