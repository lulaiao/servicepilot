# ServicePilot 售后政策 2026.1

生效时间：2026-01-01T00:00:00Z  
适用范围：程序生成的 ServicePilot 合成订单。

## policy_cancel_2026_1_section_2

处于 `CREATED`、`PAID` 或 `ACCEPTED` 状态的订单可以取消。进入制作、
配送或完成状态后，自动取消不再适用，应使用售后或人工升级流程。

## policy_partial_refund_2026_1_section_3

已完成订单因少件、错件、质量问题或重复扣款申请退款时，申请金额必须
大于零，且累计申请金额不得超过订单实付金额。

## policy_coupon_restore_2026_1_section_5

使用优惠券的订单成功取消后，可以将仍有效的合成优惠券恢复为可用状态。
恢复操作必须是幂等的。

## policy_reschedule_2026_1_section_6

处于 `PAID`、`ACCEPTED` 或 `PREPARING` 状态的订单可以申请修改预约或配送
时间。骑手取货、订单完成或订单取消后不得自动改期。

## policy_refund_exception_2026_1_section_8

标记为不可退款的本地服务预约，不接受仅因改变主意提出的退款；商品或服务
未按约提供等其他原因需要依据对应政策另行判断。
