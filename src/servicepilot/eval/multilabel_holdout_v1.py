"""Independently authored sealed cases for the three-label composition head."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class MultiLabelHoldoutCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "servicepilot-multilabel-holdout-v1"
    case_id: str
    split: str = "sealed_test"
    category: str
    text: str
    labels: tuple[Intent, ...]
    semantic_signature_sha256: str


D = Intent.DELIVERY_DELAY
C = Intent.COMPLAINT_ESCALATION
R = Intent.PARTIAL_REFUND

_CASES: tuple[tuple[str, str, tuple[Intent, ...]], ...] = (
    ("explicit_pair", "比平台写的时间晚了四十分钟还没到，我要求客服主管介入处理", (D, C)),
    ("explicit_pair", "午饭至今没有送来，请替我提交一张正式服务投诉单", (D, C)),
    ("explicit_pair", "地图上的骑手半小时没移动，把这件事转给人工坐席解决", (D, C)),
    ("explicit_pair", "承诺十二点前送达，现在已经一点了，我要向配送团队投诉", (D, C)),
    ("explicit_pair", "包裹仍停在上一站，请升级此问题并由专员答复", (D, C)),
    ("explicit_pair", "外卖一直显示取餐中，麻烦建立人工升级工单", (D, C)),
    ("explicit_pair", "预计到达时间反复后延，我需要真人客服接管", (D, C)),
    ("explicit_pair", "货物过了约定日期仍在途中，请记录投诉并给我人工回电", (D, C)),
    ("explicit_pair", "配送页两小时没有新进展，这个服务问题请交主管跟进", (D, C)),
    ("explicit_pair", "今天未能如期收货，请把异常上报给客服专员", (D, C)),
    ("three_intent", "晚餐迟迟没送到，给我退其中九元并请人工客服追查", (D, C, R)),
    ("three_intent", "快件超过承诺日期，我只退运费部分，同时登记一次投诉", (D, C, R)),
    ("three_intent", "骑手停留太久，退还五元餐费，并让客服主管处理", (D, C, R)),
    ("three_intent", "货还在运输中没有按期到，请部分退款十二元并升级工单", (D, C, R)),
    ("three_intent", "送达晚了一个小时，少收我八元，再安排专员回访", (D, C, R)),
    ("three_intent", "物流三天未更新，我申请退回部分货款并提交服务投诉", (D, C, R)),
    ("three_intent", "订单错过到达窗口，请退配送费且转人工团队调查", (D, C, R)),
    ("three_intent", "包裹仍未抵达，先返还十元，然后请真人坐席跟进", (D, C, R)),
    ("three_intent", "配送严重超时，给个部分退款，也请把问题上报主管", (D, C, R)),
    ("three_intent", "预定时段内没收到商品，退一部分费用并创建投诉记录", (D, C, R)),
    ("delivery_only", "现在比预计时间晚了很久，我只想查询配送异常", (D,)),
    ("delivery_only", "快件应当昨天到，目前仍显示运输中", (D,)),
    ("delivery_only", "餐已经超过送达窗口，不需要做其他操作", (D,)),
    ("delivery_only", "骑手的位置一直不变，帮我看看为什么这么慢", (D,)),
    ("delivery_only", "包裹没赶上约定日期，这次先登记延误", (D,)),
    ("delivery_only", "系统连续推迟到达时间，我想了解当前进度", (D,)),
    ("delivery_only", "商品本该上午送到，下午仍没有收到", (D,)),
    ("delivery_only", "订单在配送站滞留了一整天", (D,)),
    ("delivery_only", "物流进度从昨晚开始就没有变化", (D,)),
    ("delivery_only", "配送用时远超页面最初给出的范围", (D,)),
    ("negated_escalation", "餐送晚了，但不用找人工，也不要创建投诉", (D,)),
    ("negated_escalation", "包裹还没到，请别把问题升级给主管", (D,)),
    ("negated_escalation", "骑手进度太慢，这次不要转客服专员", (D,)),
    ("negated_escalation", "物流已经逾期，我明确拒绝提交服务投诉", (D,)),
    ("negated_escalation", "预计时间早就过了，不必安排真人回访", (D,)),
    ("negated_escalation", "配送停住了，先查进度，禁止建立升级工单", (D,)),
    ("negated_escalation", "货物没有按期抵达，但请勿让人工团队介入", (D,)),
    ("negated_escalation", "外卖超时，仅记录延误，不投诉任何人", (D,)),
    ("negated_escalation", "快件还在上一站，暂时不需要客服主管处理", (D,)),
    ("negated_escalation", "订单晚到，别替我上报，也别联系专员", (D,)),
    ("conditional_or_historical", "如果明早还没收到，我到时再要求人工处理", (D,)),
    ("conditional_or_historical", "配送仍很慢，若今晚没到再提交投诉", (D,)),
    ("conditional_or_historical", "包裹晚点了，后续继续停滞才升级主管", (D,)),
    ("conditional_or_historical", "骑手还没来，先等等，超过两小时再找专员", (D,)),
    ("conditional_or_historical", "上周的迟到已由人工解决，这单只查配送", (D,)),
    ("conditional_or_historical", "此前已经投诉过，本次超时不要重复建单", (D,)),
    ("conditional_or_historical", "昨天客服主管回访过，现在仅记录未送达", (D,)),
    ("conditional_or_historical", "旧订单转过专员，这个包裹晚到无需再转", (D,)),
    ("conditional_or_historical", "货物若明天仍在途中，我会考虑正式投诉", (D,)),
    ("conditional_or_historical", "先处理当前延误，暂不执行我之前说的升级", (D,)),
    ("complaint_only", "配送本身已经恢复，我仍要求客服主管调查服务态度", (C,)),
    ("complaint_only", "商品按时到了，但我要就沟通过程提交正式投诉", (C,)),
    ("complaint_only", "请创建人工工单处理商家拒绝答复的问题", (C,)),
    ("complaint_only", "我需要真人客服接手，不涉及配送或退款", (C,)),
    ("complaint_only", "请安排专员回电说明为何无人处理我的反馈", (C,)),
    ("complaint_only", "把客服态度问题升级给值班主管", (C,)),
    ("complaint_only", "我要登记服务投诉，订单已经正常完成", (C,)),
    ("complaint_only", "请让人工团队复核商户处理流程", (C,)),
    ("complaint_only", "这次只建立投诉记录，不查询物流", (C,)),
    ("complaint_only", "请上报专员调查错误的客服答复", (C,)),
    ("refund_only", "商品有一件破损，只退这一件对应的金额", (R,)),
    ("refund_only", "我只申请返还包装费三元", (R,)),
    ("refund_only", "少了一份配菜，请部分退款", (R,)),
    ("refund_only", "订单已准时送达，但其中两件需要退钱", (R,)),
    ("refund_only", "请退回差价七元，不做整单退款", (R,)),
    ("refund_only", "饮料漏了，返还饮料这一项的费用即可", (R,)),
    ("refund_only", "优惠没有生效，我要求退部分价款", (R,)),
    ("refund_only", "餐品数量不足，只退缺失部分", (R,)),
    ("refund_only", "收货正常，我仅申请十元补偿退款", (R,)),
    ("refund_only", "把运费退给我，其他商品不用退", (R,)),
    ("delivery_refund", "订单晚了一个小时，只需退配送费，不要转人工", (D, R)),
    ("delivery_refund", "包裹逾期未到，我申请部分退款，但不提交投诉", (D, R)),
    ("delivery_refund", "送达进度停滞，请返还五元，客服无需介入", (D, R)),
    ("delivery_refund", "货物错过约定日期，退运费即可，别建立工单", (D, R)),
    ("delivery_refund", "骑手严重迟到，给我部分退款，不用主管处理", (D, R)),
    ("delivery_refund", "外卖到达时间一再延后，只退八元且不要投诉", (D, R)),
    ("delivery_refund", "物流两天没更新，请退一部分货款，暂不找专员", (D, R)),
    ("delivery_refund", "商品未按时交付，返还差价，不安排人工回访", (D, R)),
    ("delivery_refund", "配送超出承诺窗口，退包装费但不要上报", (D, R)),
    ("delivery_refund", "包裹仍在途中，申请十元退款，仅此两项诉求", (D, R)),
)


def build_multilabel_holdout_v1() -> tuple[MultiLabelHoldoutCase, ...]:
    cases = []
    for index, (category, text, labels) in enumerate(_CASES, start=1):
        signature = hashlib.sha256(
            json.dumps(
                {"category": category, "labels": [label.value for label in labels], "index": index},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cases.append(
            MultiLabelHoldoutCase(
                case_id=f"multilabel-holdout-v1-{index:03d}",
                category=category,
                text=text,
                labels=labels,
                semantic_signature_sha256=signature,
            )
        )
    return tuple(cases)
