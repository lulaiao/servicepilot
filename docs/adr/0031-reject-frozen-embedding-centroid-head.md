# ADR 0031: Reject frozen embedding centroid head

- Status: Accepted
- Date: 2026-08-11

## Context

After the character n-gram head failed its false-positive gate, ServicePilot tested whether semantic
representations from the already deployed Qwen2.5-7B plus selected v5 Adapter could support the same
fixed binary head. Model parameters were frozen, no additional model was downloaded, and the decision
threshold remained a fixed zero cosine margin.

Representations used attention-masked mean pooling over the last hidden layer. The base view contained
36 delivery-primary examples; the augmented view contained 148 examples after adding the adversarial
train/dev contract. Evaluation used the same six relevant v4 dev cases.

## Result

Both frozen-embedding heads achieved 50% accuracy, precision 0.5, recall 0.6667, and F1 0.5714. Each
produced two false positives and one false negative. The existing generative secondary output achieved
83.33% accuracy and F1 0.80 with no false positives.

Representation extraction took 4.7982 seconds and 14617.73 MiB peak allocated VRAM, excluding model
load. Thus the candidate was both worse in quality and materially more expensive than the lexical
screen.

## Decision

Reject mean-pooled frozen-Qwen centroid heads. Do not tune pooling, margins, or a supervised linear
head against the six-case dev slice. The sample is too small for a credible learned-head selection.

Before revisiting a BCE/multi-label classification head, create a substantially larger independently
partitioned multi-label dataset with enough positive, negative, negated, conditional, historical, and
three-intent cases. The generative v5 output remains the development baseline.
