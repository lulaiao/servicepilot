# ADR 0040: Compare generative JSON and cross-encoder multi-label structures

- Status: Accepted as a development-only protocol
- Date: 2026-08-13

## Context

Two independently frozen holdouts rejected mean-pooled single-linear heads. V1 under-predicted minority
labels; balanced v2 over-predicted labels under natural wording. Further linear-head data iteration
would risk adapting the experiment process to consumed holdout evidence rather than addressing the
representation mismatch.

## Decision

Stop the linear-head line and compare two structurally different, already available local candidates on
the balanced v2 development split only:

1. Qwen2.5-7B with the selected v5 Adapter emits an exact three-boolean JSON object using greedy
   decoding. Negated, historical, conditional, and policy-only mentions are explicitly defined as
   false. Invalid schemas become all-false predictions and count against both schema and task metrics.
2. BGE reranker v2-m3 acts as a cross encoder over each request and each of three fixed label
   definitions. Its relevance logit uses a predeclared zero threshold; no dev threshold fitting is
   allowed.

Both models already have pinned revisions and Apache-2.0-compatible local artifacts. The comparison
reports schema validity, per-label precision/recall/F1, macro-F1, exact-set accuracy, complaint false
positives, latency, RAM, and peak VRAM. Selection uses the same safety and quality gates as prior
screens, with schema validity at least 0.99 added for generation.

## Rationale

- Generative decoding can represent joint label scope and negation rather than projecting a pooled
  vector through independent hyperplanes.
- A cross encoder jointly attends to the request and a semantic label definition, providing a smaller
  discriminative alternative without downloading another model.
- A fixed zero logit avoids creating another hidden degree of freedom through dev threshold tuning.
- Reusing cached candidates controls cost and makes the technology choice explainable by same-data
  evidence rather than popularity.

## Consequences

This is a synthetic development comparison and accesses no sealed records. A passing winner still
requires a newly authored sealed v3 before Agent integration. If neither candidate passes, the project
retains the current generative Agent baseline and stops this secondary-intent enhancement rather than
weakening gates.
