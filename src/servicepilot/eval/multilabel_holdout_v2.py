"""Independently authored sealed v2 cases for the three-label composition head."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent


class MultiLabelHoldoutV2Case(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "servicepilot-multilabel-holdout-v2"
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
    ("label_set_000", "我想了解普通订单通常由谁负责派送", ()),
    ("label_set_000", "能否说明申请售后需要准备哪些材料", ()),
    ("label_set_000", "这笔订单已经全部处理好，不需要采取任何动作", ()),
    ("label_set_000", "请告诉我会员积分的有效期限", ()),
    ("label_set_000", "我只是查看商家的营业时间，没有售后诉求", ()),
    ("label_set_000", "怎样修改账户里保存的联系电话", ()),
    ("label_set_000", "想咨询发票抬头可以填写哪些内容", ()),
    ("label_set_000", "订单顺利完成了，我来问一下评价入口在哪里", ()),
    ("label_set_001", "面包压坏了一角，按受损比例退一点钱就可以", (R,)),
    ("label_set_001", "套餐里少了主食，请把主食那部分金额原路返还", (R,)),
    ("label_set_001", "实际称重比结算数量少，只需要补退差额", (R,)),
    ("label_set_001", "不用取消整个订单，把重复收取的服务费退掉", (R,)),
    ("label_set_001", "其中一盒已经变质，请单独返还这一盒的钱", (R,)),
    ("label_set_001", "优惠券抵扣少算了四块，我要拿回这部分差价", (R,)),
    ("label_set_001", "其余商品都保留，仅对缺少的配件做金额补退", (R,)),
    ("label_set_001", "这单无需人工调查，请直接退回多收的包装费用", (R,)),
    ("label_set_010", "我不是来查物流的，请找负责售后的真人与我沟通", (C,)),
    ("label_set_010", "订单早已结束，但商家的处理态度需要正式反馈", (C,)),
    ("label_set_010", "请把客服反复答非所问的情况提交给管理人员", (C,)),
    ("label_set_010", "我需要一个人工受理编号来追踪这次服务争议", (C,)),
    ("label_set_010", "没有退款要求，请安排能处理纠纷的工作人员联系我", (C,)),
    ("label_set_010", "请对坐席擅自结束会话一事发起内部核查", (C,)),
    ("label_set_010", "我要将错误承诺的问题正式反映到客服管理层", (C,)),
    ("label_set_010", "麻烦指派一位真人负责跟进商户拒绝沟通的问题", (C,)),
    ("label_set_011", "餐品不新鲜，退掉这道菜的钱，并请真人处理卫生反馈", (C, R)),
    ("label_set_011", "多收了附加费，请返还差额，同时让管理人员核查收费", (C, R)),
    ("label_set_011", "配件缺失要补退对应金额，商家拒绝回应也请人工跟进", (C, R)),
    ("label_set_011", "商品已经收到，只退破损部分，并正式反馈包装问题", (C, R)),
    ("label_set_011", "请退回未提供服务的费用，再由工作人员调查虚假描述", (C, R)),
    ("label_set_011", "重量不足需要退差价，也请记录商户多次少称的问题", (C, R)),
    ("label_set_011", "把漏送饮品的钱返还，另外请真人受理我的服务申诉", (C, R)),
    ("label_set_011", "订单没有晚到；我要补退优惠差额，并请管理层答复", (C, R)),
    ("label_set_100", "约定的安装人员到现在都没有出现", (D,)),
    ("label_set_100", "生鲜车次已越过预约时间，页面仍显示等待装车", (D,)),
    ("label_set_100", "同城文件原本半小时前应签收，目前还在路上", (D,)),
    ("label_set_100", "药品配送窗口已经结束，收件人仍未拿到", (D,)),
    ("label_set_100", "运输轨迹整晚停在分拨中心没有变化", (D,)),
    ("label_set_100", "商家说已出库，但承诺的送达日期已经过去", (D,)),
    ("label_set_100", "预约时段只剩最后几分钟，配送员还未出发", (D,)),
    ("label_set_100", "这件急件错过了计划航班，预计会晚一天抵达", (D,)),
    ("label_set_101", "冷链商品没有按预约时间来，请退掉冷链附加费", (D, R)),
    ("label_set_101", "文件迟迟未签收，把加急服务的差价退给我", (D, R)),
    ("label_set_101", "安装配送爽约了，只需返还本次上门费用", (D, R)),
    ("label_set_101", "药品超过送达窗口，申请退回运送费，不需要人工介入", (D, R)),
    ("label_set_101", "生鲜还在仓库，按延误时长给我补退部分金额", (D, R)),
    ("label_set_101", "快递比承诺日期晚了，退掉我购买的时效服务费", (D, R)),
    ("label_set_101", "外送超过九十分钟，少收取一部分餐费即可", (D, R)),
    ("label_set_101", "货物卡在中转站，请返还加价配送的那部分钱", (D, R)),
    ("label_set_110", "预约送货无人上门，请让工作人员查明是谁漏派", (D, C)),
    ("label_set_110", "急件错过交付节点，我要向负责时效的团队正式反馈", (D, C)),
    ("label_set_110", "骑手尚未取货，请安排真人核查调度记录", (D, C)),
    ("label_set_110", "货车长时间停在途中，麻烦由管理人员接手查询", (D, C)),
    ("label_set_110", "预计抵达日期又被改晚，请人工受理这次履约争议", (D, C)),
    ("label_set_110", "餐食到店后一直没人配送，我要正式反映调度问题", (D, C)),
    ("label_set_110", "重要药品没有在窗口内送来，请真人负责持续追踪", (D, C)),
    ("label_set_110", "签收时间已经逾期，请将异常提交给配送管理人员", (D, C)),
    ("label_set_111", "家电没有按约送装，退部分上门费并让负责人调查", (D, C, R)),
    ("label_set_111", "加急文件晚了一天，返还加急差价并由真人跟进", (D, C, R)),
    ("label_set_111", "生鲜配送超出保鲜时限，退一部分货款并正式受理反馈", (D, C, R)),
    ("label_set_111", "药品迟到且保温袋破损，请补退费用并安排人工核查", (D, C, R)),
    ("label_set_111", "外卖过了饭点才出发，退部分餐费并提交调度申诉", (D, C, R)),
    ("label_set_111", "货物滞留导致活动无法使用，请退服务费并由管理层答复", (D, C, R)),
    ("label_set_111", "预约配送连续爽约，返还一部分钱并指派真人处理", (D, C, R)),
    ("label_set_111", "包裹延误且时效费未兑现，请退差额并正式追查原因", (D, C, R)),
)


def build_multilabel_holdout_v2() -> tuple[MultiLabelHoldoutV2Case, ...]:
    cases = []
    for index, (category, text, labels) in enumerate(_CASES, start=1):
        signature = hashlib.sha256(
            json.dumps(
                {"category": category, "labels": [label.value for label in labels], "index": index},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cases.append(
            MultiLabelHoldoutV2Case(
                case_id=f"multilabel-holdout-v2-{index:03d}",
                category=category,
                text=text,
                labels=labels,
                semantic_signature_sha256=signature,
            )
        )
    return tuple(cases)
