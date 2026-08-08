# Phase 6E evidence-label review

Date: 2026-08-08  
Scope: development diagnostics, not sealed evaluation

The 120-query diagnostic set contains twelve policy families with ten unique
paraphrases each. Every family was assigned three disjoint evidence roles:

- `required`: the authoritative section that must support the answer;
- `supporting`: relevant context that must not replace the primary section;
- `contradictory`: a related section that would support the wrong action or
  answer if treated as primary evidence.

| Family | Required | Supporting | Contradictory |
| --- | --- | --- | --- |
| preparing cancellation | cancel 2026.1 | manual cancellation | expired cancel 2025.4 |
| manual cancellation | manual cancellation | cancel 2026.1 | expired cancel 2025.4 |
| refund amount | partial-refund limits | none | expired refund 2025.4 |
| refund timing | refund timing | partial-refund limits | none |
| coupon restoration | coupon restoration | coupon expiry | marketing coupon issue |
| coupon expiry | coupon expiry | coupon restoration | marketing coupon issue |
| reschedule eligibility | reschedule states | reschedule limits | none |
| reschedule limits | reschedule limits | reschedule states | none |
| refund exception | non-refundable exception | Shanghai local cancellation | partial-refund limits |
| delivery delay | delivery-delay handling | delay compensation | cancellation |
| delay compensation | delay compensation | delivery-delay handling | partial refund |
| marketing coupon issue | marketing coupon issue | none | coupon restoration |

Schema validation enforces that required equals the legacy gold label and that
the three roles are disjoint. The generator also enforces exactly 120 unique
queries. This review improves label semantics but does not create 120
statistically independent observations: paraphrases within a family share the
same policy boundary. A separately authored sealed set remains required.
