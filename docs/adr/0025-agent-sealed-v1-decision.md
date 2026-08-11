# ADR 0025: Agent sealed v1 one-shot decision

- Status: Accepted
- Date: 2026-08-11

## Context

After selecting v5 checkpoint-10 only as a development candidate, ServicePilot froze a new 24-case
end-to-end Agent suite. It was authored after model selection, contains two cases for every intent,
and covers confirmation refusal, prompt injection, transient retry, and lost-response recovery. Its
catalog hash is `23238445db69cf8567ad375d88d992f6bbbbaefefe2ef31d4be0671f5cdd3b34`.

The candidate was evaluated exactly once with the same Qwen2.5-7B revision, BF16 dtype, adapter,
Harness, budgets, and deterministic Judge used for executable dev evaluation. No result-driven
change or rerun is permitted on this catalog.

## Result

- executable task success: 21/24 (87.5%);
- final-state accuracy: 87.5%;
- schema-valid rate: 95.83%;
- high-risk task failure: 2/12 (16.67%);
- committed unsafe write: 0;
- false success: 0;
- mean/P95 scenario latency: 2.4566/2.6698 seconds;
- peak allocated VRAM: 14627.2 MiB.

The three task failures are distinct:

1. cancellation without refund was classified as rescheduling and safely stopped with zero tools;
2. duplicate-charge output serialized `requested_amount` as a JSON number, failed Schema parsing,
   and safely fell back with zero tools;
3. coupon restoration was classified as cancellation and attempted `preview_cancel`; domain policy
   rejected the preview, so no write committed and no success was claimed.

Static Trace audit identified the third call as an unexpected tool attempt (1/24, 4.17%). The legacy
Judge checked only explicitly forbidden tools, not every business-action call outside
`allowed_actions`. The Judge is therefore strengthened for future suites with `UNEXPECTED_ACTION`
(Harness support tools such as policy search remain permitted); the consumed sealed report remains
immutable and is not rerun.

## Decision

Reject v5 checkpoint-10 as a final/production candidate. Retain it as the strongest development
baseline because it materially exceeds the rule Agent on the same sealed suite (87.5% versus 29.17%)
and produced no committed unsafe write or false-success claim.

Future work must use train/dev-only data for the three observed failure classes and must be evaluated
on a newly versioned holdout. Agent sealed v1 is exhausted and cannot be used for model selection,
threshold changes, Prompt changes, or regression reruns.
