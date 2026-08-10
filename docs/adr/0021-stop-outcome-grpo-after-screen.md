# ADR 0021: Stop outcome GRPO after bounded screen

- Status: Accepted
- Date: 2026-08-10

## Evidence

The frozen 10-step screen completed on GPU 0 without a safety termination. It
ran 40 executable rewards, loaded zero sealed records, reached overall training
Schema validity 0.95, runtime-error rate 0.025, maximum KL 0.0001992, and four
steps with non-zero reward variance. LoRA parameter delta L2 was 0.002973. All
training-mechanics gates passed.

The resulting adapter then ran the unchanged 36-scenario development Harness.
Task success and final-state accuracy remained 0.9444; policy violation,
False-success, unsafe high-risk error, and runtime errors remained zero. The
same two scenarios failed, so training produced no executable utility gain.

Schema validity regressed from 1.0 to 0.9722. For the input `整单退款，原因是质量问题`,
the model emitted unsupported secondary intent `quality_problem`. Mean scenario
latency increased from 1.8650 to 1.9722 seconds and P95 from 2.1752 to 2.3398
seconds, though latency was not the decisive gate.

## Decision

Reject the GRPO candidate. Do not run repeated seeds and do not inspect sealed
test performance. Training completion is not equivalent to Agent improvement.

Future RL work requires a larger and more difficult on-policy prompt pool plus
a reward term that preserves exact Schema vocabulary without reducing the hard
safety constraints. Such work is a new protocol, not a continuation or tuning
of this screen. The selected four-seed SFT v3 adapters remain the reportable
learned baseline.
