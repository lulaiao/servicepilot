#!/usr/bin/env python3
"""Build the frozen Phase 6E diagnostic query set from reviewed templates."""

import argparse
from pathlib import Path

from servicepilot.retrieval.models import RetrievalQuery

TEMPLATES: tuple[dict[str, object], ...] = (
    {
        "name": "cancel_preparing",
        "texts": (
            "制作中的外卖还能直接取消吗",
            "商家已经开始做了，取消规则是什么",
            "备餐阶段能不能自动撤单",
            "订单进入制作后如何取消",
            "正在出餐的订单可以马上取消吗",
            "已经制作了还能一键取消吗",
            "备餐中的单要走什么取消流程",
            "制作状态是否允许系统直接取消",
            "餐已经在做，我想取消怎么办",
            "2026政策对制作中取消怎么规定",
        ),
        "required": ("policy_cancel_2026_1_section_2",),
        "supporting": ("policy_manual_cancel_2026_1_section_13",),
        "contradictory": ("policy_cancel_2025_4_section_2",),
        "business_type": "food_delivery",
        "order_status": "preparing",
        "city": "Shanghai",
    },
    {
        "name": "manual_cancel",
        "texts": (
            "制作后不能自动取消时能转人工吗",
            "备餐订单怎样申请人工售后",
            "已经制作的订单谁来处理取消",
            "自动撤单失败后可以建人工工单吗",
            "制作中订单人工取消是否保证退款",
            "客服能受理正在制作的取消吗",
            "备餐阶段取消要升级人工吗",
            "无法直接取消时有什么售后流程",
            "制作订单提交人工是否一定退钱",
            "订单开始制作后的人工处理规则",
        ),
        "required": ("policy_manual_cancel_2026_1_section_13",),
        "supporting": ("policy_cancel_2026_1_section_2",),
        "contradictory": ("policy_cancel_2025_4_section_2",),
        "business_type": "food_delivery",
        "order_status": "preparing",
        "city": "Shanghai",
    },
    {
        "name": "refund_amount",
        "texts": (
            "少送商品可以退多少钱",
            "部分退款能超过订单实付吗",
            "错件申请退款的金额限制",
            "质量问题退款金额有什么要求",
            "重复扣款可以申请多少退款",
            "完成订单部分退款必须大于零吗",
            "少件退款上限是订单金额吗",
            "退款累计金额能否超过实付",
            "订单已完成，错件怎么计算退款",
            "部分退款金额规则是什么",
        ),
        "required": ("policy_partial_refund_2026_1_section_3",),
        "supporting": (),
        "contradictory": ("policy_refund_2025_4_section_3",),
        "business_type": "food_delivery",
        "order_status": "delivered",
        "city": "Shanghai",
    },
    {
        "name": "refund_timing",
        "texts": (
            "退款审核通过后多久能到账",
            "退款到账时间由谁决定",
            "退款成功为什么还没到银行卡",
            "支付渠道退款时效是什么",
            "已经同意退款，什么时候到账",
            "退款金额通过后多久到账",
            "审核完成后的退款去哪里查",
            "到账速度和退款资格是一回事吗",
            "退款申请批准后的到账规则",
            "渠道处理退款一般需要多久",
        ),
        "required": ("policy_refund_timing_2026_1_section_14",),
        "supporting": ("policy_partial_refund_2026_1_section_3",),
        "contradictory": (),
        "business_type": "food_delivery",
        "order_status": "delivered",
        "city": "Shanghai",
    },
    {
        "name": "coupon_restore",
        "texts": (
            "取消订单后用掉的优惠券能恢复吗",
            "退单以后红包券还能回来不",
            "订单取消了券怎么返还",
            "撤单后优惠券是否恢复可用",
            "取消成功后原优惠券还能用吗",
            "退单返券要满足什么条件",
            "订单撤销后券没有回来怎么办",
            "使用优惠券的订单取消后如何恢复",
            "取消订单会自动退回有效券吗",
            "退单后的优惠券恢复规则",
        ),
        "required": ("policy_coupon_restore_2026_1_section_5",),
        "supporting": ("policy_coupon_expiry_2026_1_section_15",),
        "contradictory": ("policy_coupon_issue_2026_1_section_10",),
        "business_type": "food_delivery",
        "order_status": "cancelled",
        "city": "Shanghai",
    },
    {
        "name": "coupon_expiry",
        "texts": (
            "取消订单时优惠券已经过期还能延期吗",
            "退单返券发现原券过期怎么办",
            "过期优惠券取消订单后会恢复吗",
            "撤单能延长优惠券有效期吗",
            "退回的券超过期限还能使用吗",
            "订单取消后的券可以续期吗",
            "原券失效后退单是否重新激活",
            "取消返券要检查有效期吗",
            "过期红包券会因为退单复活吗",
            "返券与有效期的判断规则",
        ),
        "required": ("policy_coupon_expiry_2026_1_section_15",),
        "supporting": ("policy_coupon_restore_2026_1_section_5",),
        "contradictory": ("policy_coupon_issue_2026_1_section_10",),
        "business_type": "food_delivery",
        "order_status": "cancelled",
        "city": "Shanghai",
    },
    {
        "name": "reschedule_eligibility",
        "texts": (
            "备餐中的订单还能修改配送时间吗",
            "哪些订单状态允许改期",
            "骑手取货后还能改送达时间吗",
            "已支付订单可以调整预约吗",
            "订单完成后能否重新安排时间",
            "正在准备的订单怎么改时间",
            "取消的订单还能修改预约吗",
            "配送时间修改受什么状态限制",
            "accepted状态允许重新预约吗",
            "订单改期的状态条件是什么",
        ),
        "required": ("policy_reschedule_2026_1_section_6",),
        "supporting": ("policy_reschedule_limit_2026_1_section_16",),
        "contradictory": (),
        "business_type": "food_delivery",
        "order_status": "preparing",
        "city": "Shanghai",
    },
    {
        "name": "reschedule_limit",
        "texts": (
            "一次改期可以提交几个时间",
            "频繁修改配送时间会怎样",
            "改期必须选择未来时间吗",
            "多次改预约是否要转人工",
            "一次能同时选两个新时间吗",
            "反复改期有什么限制",
            "预约改期次数太多怎么办",
            "提交配送改期的时间格式要求",
            "允许改期时每次能改几个时间",
            "频繁改时间是否改变状态条件",
        ),
        "required": ("policy_reschedule_limit_2026_1_section_16",),
        "supporting": ("policy_reschedule_2026_1_section_6",),
        "contradictory": (),
        "business_type": "food_delivery",
        "order_status": "preparing",
        "city": "Shanghai",
    },
    {
        "name": "refund_exception",
        "texts": (
            "不可退款预约因为改变主意能退款吗",
            "本地服务标记不退还能申请退款吗",
            "不可退款订单没按约服务怎么处理",
            "仅仅不想去了能退不可退款预约吗",
            "本地预约退款例外是什么",
            "不可退服务在什么原因下仍需判断",
            "改变主意是否属于不可退款例外",
            "明确不退款的预约可以随意退吗",
            "商家未履约时不可退款标签还有效吗",
            "本地服务退款限制规则",
        ),
        "required": ("policy_refund_exception_2026_1_section_8",),
        "supporting": ("policy_shanghai_local_cancel_2026_1_section_19",),
        "contradictory": ("policy_partial_refund_2026_1_section_3",),
        "business_type": "local_service",
        "order_status": "delivered",
        "city": "Shanghai",
    },
    {
        "name": "delivery_delay",
        "texts": (
            "骑手配送超时应该怎么记录",
            "外卖延迟是否要升级人工",
            "配送太慢能自动退款吗",
            "骑手迟到应该报什么异常",
            "订单配送延误怎样处理",
            "超时配送是否等于可以取消",
            "配送中的订单很慢怎么办",
            "延迟问题需要创建什么记录",
            "骑手超时能否直接退钱",
            "配送延迟的处理政策",
        ),
        "required": ("policy_delivery_delay_2026_1_section_11",),
        "supporting": ("policy_delivery_compensation_2026_1_section_18",),
        "contradictory": ("policy_cancel_2026_1_section_2",),
        "business_type": "food_delivery",
        "order_status": "picked_up",
        "city": "Shanghai",
    },
    {
        "name": "delivery_compensation",
        "texts": (
            "配送超时补偿需要先做什么",
            "骑手迟到一定自动退款吗",
            "延迟补偿资格由什么判断",
            "配送异常和退款是一回事吗",
            "申请超时补偿前要记录异常吗",
            "配送慢能直接获得退款吗",
            "超时活动补偿有哪些前置条件",
            "延误补偿由哪套规则决定",
            "记录配送异常后是否必然赔付",
            "配送超时的补偿政策",
        ),
        "required": ("policy_delivery_compensation_2026_1_section_18",),
        "supporting": ("policy_delivery_delay_2026_1_section_11",),
        "contradictory": ("policy_partial_refund_2026_1_section_3",),
        "business_type": "food_delivery",
        "order_status": "picked_up",
        "city": "Shanghai",
    },
    {
        "name": "coupon_issue",
        "texts": (
            "活动赠送的优惠券领取失败怎么办",
            "营销红包没有到账找谁处理",
            "活动券领取失败属于退单返券吗",
            "赠券失败要建什么工单",
            "营销活动优惠券没领到怎么处理",
            "领取活动券失败能走订单恢复吗",
            "系统赠送券失败应该联系哪个流程",
            "活动发券异常是否属于订单取消",
            "营销券领取问题怎么上报",
            "赠送优惠券失败的政策",
        ),
        "required": ("policy_coupon_issue_2026_1_section_10",),
        "supporting": (),
        "contradictory": ("policy_coupon_restore_2026_1_section_5",),
        "business_type": "food_delivery",
        "order_status": "cancelled",
        "city": "Shanghai",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("data/eval/phase6_reranker_diagnostic_queries.jsonl")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries: list[RetrievalQuery] = []
    for group_index, template in enumerate(TEMPLATES, start=1):
        required = tuple(template["required"])
        for variant, text in enumerate(template["texts"], start=1):
            queries.append(
                RetrievalQuery(
                    query_id=f"diag-{group_index:02d}-{variant:02d}",
                    text=str(text),
                    gold_evidence_ids=required,
                    required_evidence_ids=required,
                    supporting_evidence_ids=tuple(template["supporting"]),
                    contradictory_evidence_ids=tuple(template["contradictory"]),
                    policy_version="2026.1",
                    business_type=str(template["business_type"]),
                    order_status=str(template["order_status"]),
                    city=str(template["city"]),
                )
            )
    if len(queries) != 120 or len({item.text for item in queries}) != 120:
        raise SystemExit("diagnostic set must contain 120 unique queries")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(item.model_dump_json() for item in queries) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
