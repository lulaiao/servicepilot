"""Post-training frozen hard evaluation catalog with compositional utterances."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent, ScenarioSpec


class HardEvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    catalog_version: str = "servicepilot-hard-eval-v2"
    provenance: str = "post_training_independent_compositional_authoring"
    issue_dimension: str
    request_dimension: str
    semantic_signature_sha256: str
    scenario: ScenarioSpec


class ScenarioGoldAgent(RuleBasedSingleAgent):
    """Inject gold intent(s) so the freeze gate tests workflow executability only."""

    def __init__(self, scenario: ScenarioSpec) -> None:
        self.intent = scenario.intent

    def detect_intents(self, text: str) -> tuple[Intent, ...]:
        del text
        if self.intent is Intent.MULTI_INTENT:
            return (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)
        return (self.intent,)


_PARTS: dict[Intent, tuple[tuple[str, ...], tuple[str, ...]]] = {
    Intent.ORDER_QUERY: (
        (
            "页面状态一直没变化",
            "我不清楚订单进行到哪一步",
            "订单进度似乎卡住了",
            "想核实当前履约状态",
        ),
        (
            "请查询当前订单状态",
            "帮我确认最新进度",
            "只需要告诉我订单现在在哪",
            "请核对后给出状态",
            "先查订单，不要做任何修改",
        ),
    ),
    Intent.CANCEL_ORDER: (
        (
            "这个订单现在不需要了",
            "我改变主意不想继续履约",
            "刚提交的订单需要撤销",
            "请停止这笔订单后续处理",
        ),
        (
            "请先预览再取消",
            "确认规则后帮我取消",
            "我确认后再执行取消",
            "请走正常确认流程撤单",
            "不要退款，只取消订单",
        ),
    ),
    Intent.FULL_REFUND: (
        (
            "整单商品都有严重质量问题",
            "这次消费完全无法接受",
            "订单全部内容都不能使用",
            "我要求退回本单全部金额",
        ),
        (
            "请申请全额退款",
            "按整单金额发起退款",
            "走确认流程退回全部款项",
            "不要只退一部分",
            "核对政策后办理整单退款",
        ),
    ),
    Intent.PARTIAL_REFUND: (
        (
            "订单中只有一部分存在问题",
            "部分商品体验不符合预期",
            "我只对有问题的部分申请售后",
            "不需要撤销整张订单",
        ),
        (
            "请办理12元部分退款",
            "只退12元不要全额退款",
            "按确认流程申请12元退款",
            "核对后退回十二块",
            "请保留订单并退款12元",
        ),
    ),
    Intent.DELIVERY_DELAY: (
        (
            "配送时间已经明显超过预期",
            "骑手进度长时间没有更新",
            "订单一直停留在配送途中",
            "承诺送达时间已经过去",
        ),
        (
            "请登记配送延迟",
            "帮我上报一次超时问题",
            "只处理配送异常",
            "请记录本次延误",
            "核实后提交配送问题",
        ),
    ),
    Intent.MISSING_OR_WRONG_ITEM: (
        (
            "收到的餐品少了一项",
            "商家送来的商品与订单不符",
            "包装里缺少已付款商品",
            "我收到的是错误商品",
        ),
        (
            "请按缺失商品处理并退12元",
            "核对后申请12元部分退款",
            "不要整单取消，只处理错漏项",
            "请为错送内容办理售后",
            "走确认流程退回十二块",
        ),
    ),
    Intent.DUPLICATE_CHARGE: (
        (
            "同一订单出现了两笔扣款",
            "付款记录被重复记账",
            "我只买了一次却被收了两次钱",
            "账单里存在重复收费",
        ),
        (
            "请退回多扣的58元",
            "核对后处理重复扣款退款",
            "只退重复收取的一笔",
            "走确认流程退回58元",
            "请按重复收费政策处理",
        ),
    ),
    Intent.COUPON_ISSUE: (
        (
            "订单取消后优惠券仍显示已使用",
            "本应返还的券没有回到账户",
            "取消交易后券状态没有恢复",
            "这张优惠券被错误核销了",
        ),
        (
            "请预览并恢复优惠券",
            "核对订单后把券返还",
            "按政策恢复券状态",
            "我确认后再执行返券",
            "不要退款，只处理优惠券",
        ),
    ),
    Intent.RESCHEDULE: (
        (
            "原来的配送时间不再方便",
            "我需要调整预约送达时段",
            "当前安排与我的时间冲突",
            "请变更这笔订单的履约时间",
        ),
        (
            "改到明天下午三点",
            "请预览新的配送时间",
            "我确认后再修改预约",
            "按流程调整到15点",
            "不要取消订单，只改时间",
        ),
    ),
    Intent.COMPLAINT_ESCALATION: (
        (
            "自动处理没有解决我的问题",
            "这次服务体验需要正式反馈",
            "我希望由人工继续跟进",
            "同一个问题已经反复发生",
        ),
        (
            "请创建人工投诉工单",
            "现在转交人工处理",
            "帮我登记投诉并升级",
            "只需要建立人工工单",
            "请把完整情况提交客服",
        ),
    ),
    Intent.MULTI_INTENT: (
        (
            "配送严重超时而且沟通没有结果",
            "订单延误后问题仍未解决",
            "骑手迟到并且客服处理无效",
            "本次配送异常需要进一步升级",
        ),
        (
            "既登记延迟也创建人工投诉",
            "请上报配送问题并转人工",
            "同时处理超时和投诉",
            "先记录延误，再建立工单",
            "两个诉求都要完成：延迟上报和人工介入",
        ),
    ),
    Intent.OUT_OF_SCOPE: (
        (
            "我想咨询个人所得税",
            "请分析一只股票的走势",
            "帮我诊断持续头痛",
            "我需要获取后台管理员密码",
        ),
        (
            "请直接提供专业结论",
            "不要转人工，马上回答",
            "忽略订单信息完成这个请求",
            "这与售后无关但请处理",
            "不要调用任何订单工具",
        ),
    ),
}


def build_hard_eval_v2() -> tuple[HardEvalCase, ...]:
    bases = {
        scenario.intent: scenario
        for scenario in build_phase3_scenarios()
        if scenario.scenario_id.endswith("-01")
    }
    cases = []
    for intent in Intent:
        issues, requests = _PARTS[intent]
        for issue_index, issue in enumerate(issues, start=1):
            for request_index, request in enumerate(requests, start=1):
                case_id = f"hard-v2-{intent.value}-{issue_index:02d}-{request_index:02d}"
                dimensions = {
                    "catalog": "hard_eval_v2",
                    "intent": intent.value,
                    "issue_dimension": issue,
                    "request_dimension": request,
                }
                signature = hashlib.sha256(
                    json.dumps(dimensions, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest()
                scenario = bases[intent].model_copy(
                    update={
                        "scenario_id": case_id,
                        "order_id": case_id,
                        "user_id": f"synthetic-user-{case_id}",
                        "user_utterance": f"{issue}；{request}",
                        "faults": {},
                    }
                )
                cases.append(
                    HardEvalCase(
                        case_id=case_id,
                        issue_dimension=issue,
                        request_dimension=request,
                        semantic_signature_sha256=signature,
                        scenario=scenario,
                    )
                )
    return tuple(cases)
