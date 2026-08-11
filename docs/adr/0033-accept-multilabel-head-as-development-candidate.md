# ADR 0033: Accept the multi-label head as a development candidate only

- Status: Accepted
- Date: 2026-08-11

## Context

The frozen supervised-head protocol trained a three-label linear head over frozen Qwen2.5-7B v5
representations. Four predeclared seeds used the same family-split 192-record train set, 48-record dev
set, fixed 0.5 threshold, optimizer, epoch count, model revision, and Adapter checkpoint. No sealed
records were present or accessed.

A separate shortcut audit found 0.8333 exact-set accuracy for character n-gram centroids. Its complaint
escalation F1 was 1.0, showing that this synthetic label has strong lexical cues even though nearest
cross-split character similarity remained moderate (mean 0.2484, maximum 0.6552).

## Result

All four seeds passed every development gate. Macro-F1 and exact-set accuracy were 1.0 with population
standard deviation 0.0; complaint-escalation false-positive rate was 0.0 and all three label F1 values
were 1.0. Peak allocated VRAM was 14655.55 MiB in every run.

The head-training wall time is not a clean seed comparison because three runs overlapped on shared
compute. It is retained as raw resource evidence, not interpreted as model variance.

## Decision

Accept this head as a **synthetic development candidate only**. Do not connect it to the executable
Agent, replace the v5 generative output, or claim production/generalization quality yet.

The next mandatory gate is a newly and independently authored multi-label holdout. It must be frozen
before inference, contain no template-family reuse, keep the protocol and threshold unchanged, and
measure per-label quality, exact-set accuracy, escalation false positives, and semantic-boundary
failures. The previously consumed composition holdout cannot be reused for selection.

## Rationale

- Four seeds establish optimization stability on the current split.
- Family-level partitioning and fixed thresholds reduce direct leakage and selection flexibility.
- Perfect synthetic dev scores plus a lexically easy complaint label do not establish external
  validity.
- Deferring Agent integration preserves a clean falsification gate and prevents a development win from
  silently becoming a resume claim.

## Consequences

- The formal manifest is the traceable source for hashes, seed results, variance, and resource cost.
- Any resume statement must say “four-seed synthetic development screen” until the independent holdout
  and executable Agent gates pass.
- Failure on the new holdout rejects or narrows this candidate; it does not trigger threshold tuning on
  the sealed data.
