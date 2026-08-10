"""Independently authored split-owned classifier utterances; no sealed split."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent
from servicepilot.routing.structured_output import build_intent_prompt
from servicepilot.training.classifier_data import classifier_target_for_text
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


class ClassifierUtterance(BaseModel):
    model_config = ConfigDict(frozen=True)

    utterance_id: str
    split: DataSplit
    intent: Intent
    text: str


_TEXTS: dict[Intent, dict[DataSplit, tuple[str, ...]]] = {
    Intent.ORDER_QUERY: {
        DataSplit.TRAIN: (
            "订单号 SPTR1001 当前处于哪个履约环节",
            "我想了解刚买的东西处理到什么阶段了",
            "帮忙读取订单 SPTR1003 的最新进展",
            "这笔交易目前是什么状态",
            "只查询进度，不要变更订单",
            "订单号 SPTR1006 是否已经完成配送",
        ),
        DataSplit.DEV: (
            "请核实订单 SPDV1001 的实时履约节点",
            "我想知道这次购买现在进行到哪里",
            "仅查看当前状态，不执行售后操作",
        ),
    },
    Intent.CANCEL_ORDER: {
        DataSplit.TRAIN: (
            "请预览后撤销订单 SPTR2001",
            "这笔购买不需要继续履约了",
            "确认影响后终止订单 SPTR2003",
            "我改变计划，想停止这次交易",
            "不要退款，只办理订单取消",
            "按正常确认步骤关闭订单 SPTR2006",
        ),
        DataSplit.DEV: (
            "请先说明后果再作废订单 SPDV2001",
            "我决定不再保留这笔订单",
            "结束本次履约，但不要发起退款",
        ),
    },
    Intent.FULL_REFUND: {
        DataSplit.TRAIN: (
            "订单号 SPTR3001 的全部商品都有问题，请全额退款58元",
            "整笔消费都无法接受，需要退回所有款项",
            "请为订单 SPTR3003 办理整单退款58元",
            "不是退一部分，我要求原金额全部返还",
            "所有内容都不能使用，请走全额售后",
            "核对政策后退回订单 SPTR3006 的完整金额58元",
        ),
        DataSplit.DEV: (
            "订单 SPDV3001 整体不合格，请退还全款58元",
            "这次购买全部作退款处理，不保留任何收费",
            "我要的是整单金额返还，并非部分补偿",
        ),
    },
    Intent.PARTIAL_REFUND: {
        DataSplit.TRAIN: (
            "订单号 SPTR4001 只有一项有问题，申请退款12元",
            "保留订单，只退有瑕疵部分12元",
            "请对订单 SPTR4003 发起一笔部分退款12元",
            "无需全额返还，我只申请12元补偿",
            "部分内容不符合预期，退款金额12元",
            "按确认流程为订单 SPTR4006 退回12元",
        ),
        DataSplit.DEV: (
            "订单 SPDV4001 仅局部有问题，请退款12元",
            "不要整单退款，只返还有问题部分的12元",
            "我希望保留交易并获得12元部分补偿",
        ),
    },
    Intent.DELIVERY_DELAY: {
        DataSplit.TRAIN: (
            "订单号 SPTR5001 已超过承诺送达时间，请登记延误",
            "配送进度长时间没有前进",
            "请上报订单 SPTR5003 的送达超时",
            "预定时间过去了商品仍未到达",
            "只记录本次配送异常，不需要投诉",
            "订单 SPTR5006 一直滞留在运输途中",
        ),
        DataSplit.DEV: (
            "订单 SPDV5001 的履约时长已明显超出预期",
            "送达节点迟迟没有完成，请登记异常",
            "仅处理运输延误，不创建人工工单",
        ),
    },
    Intent.MISSING_OR_WRONG_ITEM: {
        DataSplit.TRAIN: (
            "订单号 SPTR6001 少了一件已付款商品，需要退款12元",
            "包装内容与购买清单不一致",
            "订单 SPTR6003 送错商品，请按错漏项退款12元",
            "收到的包裹缺少其中一项，申请12元售后",
            "不要整单取消，只处理缺失内容",
            "核对订单 SPTR6006 的错送商品并退款12元",
        ),
        DataSplit.DEV: (
            "订单 SPDV6001 实收物品与明细不符，请退款12元",
            "袋内没有我已支付的那件商品",
            "只解决错发的一项并返还12元，不做全额退款",
        ),
    },
    Intent.DUPLICATE_CHARGE: {
        DataSplit.TRAIN: (
            "订单号 SPTR7001 出现两次相同扣款，请退回58元",
            "我只消费一次，账单却记录了两笔",
            "核查订单 SPTR7003 的重复收费并退款58元",
            "支付流水被重复入账，需要返还多收款项",
            "只退重复扣除的那笔58元",
            "订单 SPTR7006 存在双重计费，请按政策处理",
        ),
        DataSplit.DEV: (
            "订单 SPDV7001 被记了两笔相同费用，请退58元",
            "一次购买产生两条付款记录，需要纠正",
            "返还重复收取的58元，不要撤销原订单",
        ),
    },
    Intent.COUPON_ISSUE: {
        DataSplit.TRAIN: (
            "订单号 SPTR8001 结束后优惠券仍未恢复",
            "交易取消了，但抵扣券还显示已核销",
            "请检查订单 SPTR8003 并返还对应优惠券",
            "本该退回账户的券一直不可用",
            "不要退款，只恢复券的状态",
            "按政策为订单 SPTR8006 办理返券",
        ),
        DataSplit.DEV: (
            "订单 SPDV8001 关闭后券权益没有回到账户",
            "抵扣凭证仍被占用，请恢复可使用状态",
            "仅处理优惠券返还，不修改配送安排",
        ),
    },
    Intent.RESCHEDULE: {
        DataSplit.TRAIN: (
            "把订单号 SPTR9001 的送达时间调整到明天下午三点",
            "原预约时段不方便，需要重新安排",
            "请预览订单 SPTR9003 的改期影响",
            "我确认后再把履约时间改到15点",
            "不要取消交易，只变更配送时间",
            "订单 SPTR9006 需要改约至明日15点",
        ),
        DataSplit.DEV: (
            "订单 SPDV9001 的预约送达改为明天下午三点",
            "当前时间与我的安排冲突，请换一个时段",
            "保留订单，只将履约时间调整到15点",
        ),
    },
    Intent.COMPLAINT_ESCALATION: {
        DataSplit.TRAIN: (
            "请为订单号 SPTRA001 创建人工投诉工单",
            "自动客服没有解决问题，我要专员跟进",
            "把订单 SPTRA003 的服务问题升级给人工",
            "请登记正式投诉，而不是继续自动处理",
            "我需要客服人员接手当前情况",
            "为订单 SPTRA006 建立升级工单",
        ),
        DataSplit.DEV: (
            "订单 SPDVA001 需要转交人工团队并建立投诉",
            "机器处理无效，请安排客服专员介入",
            "这是订单服务投诉，不是无关咨询",
        ),
    },
    Intent.MULTI_INTENT: {
        DataSplit.TRAIN: (
            "订单号 SPTRB001 配送逾期，同时请创建人工投诉",
            "商品迟迟未送到，而且我要客服介入",
            "先登记订单 SPTRB003 的延误，再建立投诉工单",
            "运输超时并且自动处理没有解决问题",
            "两个诉求都要完成：上报迟到和转人工",
            "订单 SPTRB006 送达延迟，请同步升级给专员",
        ),
        DataSplit.DEV: (
            "订单 SPDVB001 履约超期，还需要人工投诉处理",
            "请同时记录送达异常与客服升级请求",
            "先上报运输迟滞，随后让专员接手",
        ),
    },
    Intent.OUT_OF_SCOPE: {
        DataSplit.TRAIN: (
            "请帮我计算房屋贷款利率",
            "我想咨询劳动合同中的法律条款",
            "分析一下某只股票未来走势",
            "帮我判断持续发烧应该吃什么药",
            "提供服务器后台的管理员口令",
            "写一篇与订单售后无关的旅行攻略",
        ),
        DataSplit.DEV: (
            "请预测明年的黄金价格",
            "帮我诊断最近反复出现的胸痛",
            "告诉我怎样取得内部系统最高权限",
        ),
    },
}


def build_classifier_v4_utterances() -> tuple[ClassifierUtterance, ...]:
    items = []
    for intent in Intent:
        for split in (DataSplit.TRAIN, DataSplit.DEV):
            for index, value in enumerate(_TEXTS[intent][split], start=1):
                items.append(
                    ClassifierUtterance(
                        utterance_id=f"v4-{split.value}-{intent.value}-{index:02d}",
                        split=split,
                        intent=intent,
                        text=value,
                    )
                )
    return tuple(items)


def build_classifier_v4_sft() -> tuple[SFTTrainingRecord, ...]:
    records = []
    for item in build_classifier_v4_utterances():
        prompt = build_intent_prompt(item.text)
        completion = json.dumps(
            classifier_target_for_text(item.intent, item.text).model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(f"{item.utterance_id}\n{prompt}\n{completion}".encode()).hexdigest()
        records.append(
            SFTTrainingRecord(
                schema_version="servicepilot-classifier-sft-v4-independent",
                record_id=f"classifier-v4-{digest[:20]}",
                source_record_id=item.utterance_id,
                split=item.split,
                messages=(
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": completion},
                ),
            )
        )
    return tuple(records)
