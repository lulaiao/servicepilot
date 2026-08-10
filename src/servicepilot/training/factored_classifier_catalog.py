"""Independent train/dev catalog for the factored issue/action classifier."""

import hashlib
import json
import re
from dataclasses import dataclass

from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    FactoredSlots,
    IssueType,
    RequestedAction,
)
from servicepilot.routing.models import RiskLevel
from servicepilot.routing.structured_output import build_factored_intent_prompt
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


@dataclass(frozen=True)
class FactoredFamily:
    family_id: str
    issue_type: IssueType
    requested_actions: tuple[RequestedAction, ...]
    train_texts: tuple[str, ...]
    dev_texts: tuple[str, ...]


def _family(
    family_id: str,
    issue: IssueType,
    actions: tuple[RequestedAction, ...],
    train: tuple[str, str, str, str],
    dev: tuple[str, str],
) -> FactoredFamily:
    return FactoredFamily(family_id, issue, actions, train, dev)


FACTORED_FAMILIES = (
    _family("query", IssueType.NONE, (RequestedAction.ORDER_QUERY,),
        ("查询订单 FQ1001 的处理进度", "我只想看看这笔购买到哪一步", "读取订单 FQ1003 的当前状态", "请告知最新履约节点，不要修改订单"),
        ("帮我核实订单 FDQ901 现在处于什么环节", "仅了解购买进展，不执行售后操作")),
    _family("cancel", IssueType.NONE, (RequestedAction.CANCEL_ORDER,),
        ("取消订单 FC2001，暂时不退款", "这笔购买不再继续，请关闭订单", "终止订单 FC2003，但不要改配送时间", "我决定撤销交易，只办理取消"),
        ("让订单 FDC921 停止后续履约，款项先不处理", "不再保留这次购买，请按流程作废")),
    _family("full_refund", IssueType.NONE, (RequestedAction.FULL_REFUND,),
        ("订单 FF3001 直接申请全额退款58元", "退回本次支付的全部金额42元", "我要整单退款31元，没有其他问题", "订单 FF3004 的所有费用都返还20元"),
        ("请把订单 FDF931 的完整支付额退款64元", "本次只要求全款退回27元")),
    _family("partial_refund", IssueType.NONE, (RequestedAction.PARTIAL_REFUND,),
        ("订单 FP4001 只申请部分退款12元", "保留其余收费，退我8元", "创建一笔局部退款15元", "订单 FP4004 不是全额退，只退款6元"),
        ("从订单 FDP941 中退回部分金额19元", "其余款项不变，我只要退款11元")),
    _family("reschedule", IssueType.NONE, (RequestedAction.RESCHEDULE,),
        ("订单 FR5001 保持有效，改到明天下午", "我还需要商品，只调整配送日期", "把订单 FR5003 的时段换到十五点", "不要取消交易，请重新预约送达时间"),
        ("继续履约订单 FDR951，但将安排改到周五", "购买不变，只换一个配送时段")),
    _family("complaint", IssueType.NONE, (RequestedAction.COMPLAINT_ESCALATION,),
        ("我要就服务态度建立人工投诉", "请把这次体验升级给客服主管", "创建投诉工单并转交专员", "我要求人工团队介入处理投诉"),
        ("请登记正式投诉，让人工客服跟进", "把服务问题升级到专员处理")),
    _family("delay", IssueType.DELIVERY_DELAY, (),
        ("订单 FL6001 超过承诺时间仍未送达", "配送进度长时间没有变化", "订单 FL6003 的履约已经逾期", "预定送达节点过去了，商品还在途中"),
        ("订单 FDL961 晚于预计时间且尚未完成", "物流状态停滞，送达发生延误")),
    _family("delay_complaint", IssueType.DELIVERY_DELAY, (RequestedAction.COMPLAINT_ESCALATION,),
        ("订单 FMC7001 配送逾期，同时建立人工投诉", "送达超时了，还要客服专员介入", "记录运输延误并创建投诉工单", "订单 FMC7004 一直没到，请升级人工处理"),
        ("订单 FDMC971 超过承诺节点，并要求正式投诉", "物流迟滞尚未解决，同时转交客服主管")),
    _family("missing", IssueType.MISSING_OR_WRONG_ITEM, (),
        ("订单 FM8001 少送了一件商品", "包裹内容与清单不符", "订单 FM8003 收到了错误型号", "已付款的餐品有一份没有送来"),
        ("订单 FDM981 出现漏发，但我还没决定怎么处理", "收到的货品不是下单的那一款")),
    _family("missing_refund", IssueType.MISSING_OR_WRONG_ITEM, (RequestedAction.PARTIAL_REFUND,),
        ("订单 FMR8101 少送一项，请退款12元", "收到错货，针对该商品退我8元", "订单 FMR8103 漏发配件，需要部分退款15元", "包裹装错内容，请退款6元处理"),
        ("订单 FDMR991 缺少一件已付款商品，请退回19元", "实际货品错误，我要求对应部分退款11元")),
    _family("duplicate", IssueType.DUPLICATE_CHARGE, (),
        ("订单 FD8201 对同一支付扣了两次", "账单出现两笔相同收费", "订单 FD8203 被重复记账", "同一笔购买产生了额外扣款"),
        ("订单 FDD992 存在重复收费，但暂不退款", "银行卡为同一交易扣款两遍")),
    _family("duplicate_refund", IssueType.DUPLICATE_CHARGE, (RequestedAction.PARTIAL_REFUND,),
        ("订单 FDR8301 重复扣费，请退款58元", "同一交易收了两次，退我23元", "订单 FDR8303 多记一笔，请退款31元", "核实重复收费并退回19元"),
        ("订单 FDDR993 被再次扣款，请返还多收的42元", "账单重复入账，我要求退款17元")),
    _family("coupon", IssueType.COUPON_ISSUE, (),
        ("订单 FK9001 取消后优惠券没有恢复", "抵扣券显示不可用", "订单 FK9003 的优惠券仍被标记已核销", "结算时优惠码无法生效"),
        ("订单 FDK994 完成售后后券状态仍不正确", "我的折扣券无法在当前购买中使用")),
    _family("out_of_scope", IssueType.OUT_OF_SCOPE, (),
        ("帮我写一首关于夏天的诗", "查询明天的股票涨幅", "如何配置家庭路由器", "推荐一部科幻电影"),
        ("解释一下量子纠缠", "给我制定一份健身计划")),
)

_ORDER_ID = re.compile(r"订单\s*([A-Z0-9]{6,})")
_AMOUNT = re.compile(r"(?:退款|退我|退回|返还)[^0-9]{0,12}(\d+(?:\.\d{1,2})?)\s*元")
_HIGH_ACTIONS = frozenset({RequestedAction.CANCEL_ORDER, RequestedAction.FULL_REFUND, RequestedAction.PARTIAL_REFUND, RequestedAction.RESCHEDULE})
_HIGH_ISSUES = frozenset({IssueType.MISSING_OR_WRONG_ITEM, IssueType.DUPLICATE_CHARGE})


def _target(family: FactoredFamily, text: str) -> FactoredIntentResult:
    order = _ORDER_ID.search(text)
    amount = _AMOUNT.search(text)
    high = family.issue_type in _HIGH_ISSUES or bool(_HIGH_ACTIONS & set(family.requested_actions))
    medium = family.issue_type in {IssueType.DELIVERY_DELAY, IssueType.COUPON_ISSUE} or RequestedAction.COMPLAINT_ESCALATION in family.requested_actions
    return FactoredIntentResult(
        issue_type=family.issue_type,
        requested_actions=family.requested_actions,
        slots=FactoredSlots(order_id=order.group(1) if order else None, requested_amount=amount.group(1) if amount else None),
        risk_level=RiskLevel.HIGH if high else RiskLevel.MEDIUM if medium else RiskLevel.LOW,
        confidence=1.0,
        needs_clarification=family.issue_type is not IssueType.OUT_OF_SCOPE and order is None,
    )


def build_factored_classifier_sft() -> tuple[SFTTrainingRecord, ...]:
    records = []
    for family in FACTORED_FAMILIES:
        for split, texts in ((DataSplit.TRAIN, family.train_texts), (DataSplit.DEV, family.dev_texts)):
            for index, text in enumerate(texts, start=1):
                completion = json.dumps(_target(family, text).model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256(f"factored-v1:{family.family_id}:{split.value}:{index}\n{text}\n{completion}".encode()).hexdigest()
                records.append(SFTTrainingRecord(
                    schema_version="servicepilot-factored-classifier-v1",
                    record_id=f"factored-{digest[:20]}",
                    source_record_id=f"factored-{split.value}-{family.family_id}-{index:02d}",
                    split=split,
                    messages=({"role": "user", "content": build_factored_intent_prompt(text)}, {"role": "assistant", "content": completion}),
                ))
    return tuple(records)
