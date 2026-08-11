# ADR 0030: Reject lexical centroid secondary head

- Status: Accepted
- Date: 2026-08-11

## Context

After rejecting keyword composition binding, ServicePilot tested whether an independent multi-label
head could recover complaint escalation without relying on autoregressive `secondary_intents` tokens.
The cheapest falsifiable baseline was a dependency-free character 2-4 gram binary centroid head,
conditioned on the generative model already selecting `delivery_delay`.

The decision rule used a fixed zero cosine-similarity margin and no dev threshold tuning. The first
training view contained 30 delivery-plus-complaint positives and six delivery-only negatives from v5.
A second view added 112 applicable adversarial train/dev cases.

## Result

On six relevant v4 dev cases, the saved v7 generative output achieved F1 0.80 with zero false
positives and one false negative. The base lexical head improved recall to 1.0 and F1 to 0.8571 but
introduced one false positive. Adversarial augmentation introduced a second false positive and
reduced F1 to 0.75.

## Decision

Reject the lexical centroid head and do not tune its threshold. It does not meet the zero-unexpected-
secondary-action safety requirement. Retain the implementation and raw diagnostics as a cheap
baseline.

The next bounded candidate is a frozen semantic representation from the already shared Qwen model,
with the same independent head and fixed decision rule. This isolates representation quality without
adding a new deployed model or updating 7B parameters.
