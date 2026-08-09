# ADR 0015: Add a narrow deterministic multi-intent completion guard

- Status: Accepted
- Date: 2026-08-09

## Decision

Keep learned routing for ordinary single-intent requests, but invoke the
deterministic classifier as a guardrail for explicit conjunctions and Prompt
Injection. When the guard detects multiple intents, its typed primary and
secondary intent set becomes the completion contract; every intent must finish
before the Agent may claim success.

This follows the same minimal-runtime principles used by mature open-source
Agent systems: guardrails around unsafe boundaries, typed handoff metadata, and
durable state rather than unconstrained model autonomy. We retain the existing
ServicePilot Harness instead of adding a new framework because checkpointing,
tool guardrails, and resumability already exist locally.

## Evidence

On the unchanged 36-scenario dev Harness and the same SFT v2 checkpoint,
multi-intent success improved from 0/3 to 3/3, total task success from 0.8056 to
0.8889, and False-success from 0.1667 to 0.0833. The guard overrode four of 36
classifications. High-risk error remained 0.0556, so the zero-risk gate still
blocks formal training and sealed evaluation.

## Consequences

The next control is an output completion verifier that cross-checks claimed
success against required intent/tool completion. It must be tested separately;
the deterministic guard must not expand into a hidden replacement for the
learned classifier.
