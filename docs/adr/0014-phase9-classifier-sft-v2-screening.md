# ADR 0014: Stop classifier SFT v2 after bounded screening

- Status: Accepted
- Date: 2026-08-08

## Context

SFT v2 corrected the objective/deployment mismatch and predeclared a 25-step,
single-seed screening gate before any repeated 7B training. The gate requires
task success not below the untrained 7B baseline and safety improvement over
SFT v1; sealed data remains unavailable during screening.

## Evidence

The screening run reached dev loss 0.09953 in 82.77 seconds with 16,426.9 MiB
peak training VRAM and zero sealed records loaded. On the same 36-scenario
executable dev Harness, Schema validity reached 1.0 and runtime errors fell to
zero. High-risk error fell to 0.0556 from the v1 candidate mean of 0.2111.

However, task success was only 0.8056, below the untrained 7B result of 0.8889,
and False-success rose to 0.1667. All three multi-intent scenarios failed. The
rule baseline remained 1.0 task success with zero high-risk errors.

## Decision

Stop SFT v2 at screening. Do not run four seeds and do not inspect sealed data.
The corrected classifier objective improves output validity and removes invalid
action crashes, but it does not yet improve end-to-end utility or honesty.

## Consequences

The next iteration should not simply train longer. It must first add a dedicated
multi-intent classifier/evaluation view and train explicit non-completion or
clarification behavior that prevents False-success. A CPU-only data and Judge
audit should verify these targets before another GPU screening. GRPO remains
blocked by the existing reward audits.
