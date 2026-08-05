# Model selection protocol

Status: approved protocol; no local LLM has been selected.

## Roles are selected separately

A single model is not assumed to be optimal for every role. Candidates are
evaluated independently for:

- intent/slot structured extraction;
- coordinator/planner and tool use;
- summary generation;
- retrieval embedding;
- reranking;
- asynchronous quality monitoring;
- SFT/GRPO training base.

The first baseline for every role is deterministic rules, lexical retrieval, or
a MockModel where applicable. A learned model must demonstrate incremental value
over that baseline.

## Hard gates

A candidate is eliminated before benchmarking if any item is unresolved:

- official license does not permit the intended use or redistribution;
- exact model revision and model card are unavailable;
- required context cannot cover the measured trajectory distribution;
- tokenizer/chat template or structured-output path cannot be pinned;
- weights and runtime do not fit the measured GPU/CPU and disk budget;
- supported inference/training stack is incompatible with the audited driver,
  CUDA, Python, and PyTorch combination;
- offline execution is unavailable;
- output cannot be schema-validated before entering business logic.

## Evaluation matrix

Each surviving candidate receives 1–5 scores backed by raw artifacts.

| Criterion | Planner/tool model | Extractor | Embedding/reranker |
| --- | ---: | ---: | ---: |
| ServicePilot task quality | 35% | 45% | 50% |
| Structured-output validity | 20% | 25% | 5% |
| Fault recovery / robustness | 15% | 10% | 10% |
| Latency and throughput | 10% | 10% | 15% |
| Peak VRAM/RAM and disk | 10% | 5% | 10% |
| License and reproducibility | 10% | 5% | 10% |

Quality means ServicePilot metrics, not a generic leaderboard:

- planner: executable task success, policy violations, false success, invalid
  tool calls, recovery rate, turns and tool budget;
- extractor: intent Macro-F1, per-class recall, slot F1, schema-valid rate,
  calibration and high-risk routing errors;
- retrieval: Recall@K, MRR/nDCG, evidence citation accuracy, hard-negative error
  rate and downstream task failures;
- monitor: precision/recall on a human-reviewed calibration set and harmful
  intervention rate.

## Fair comparison rules

- Use the same frozen scenario split, prompts, tool schemas, context budget,
  decoding parameters, concurrency, retry policy, and hardware allocation.
- Record exact model/runtime revisions, quantization, seeds, warm-up, number of
  repetitions, peak memory, disk, latency percentiles, throughput, and failures.
- Report accuracy and cost together. A larger model wins only if its improvement
  justifies its measured resource and latency cost for the target role.
- Evaluate at least one smaller candidate and the deterministic baseline.
- Keep test scenarios sealed until the choice is frozen; tune only on train/dev.
- Store raw outputs and a SHA256-addressed manifest under `experiments/`.

## Candidate status

The original brief suggested Qwen2.5 model sizes. They remain **provisional
candidates**, not selected models. Before any download, compare at least:

1. the deterministic baseline;
2. one small local instruction model;
3. one medium local instruction model;

using the protocol above. Candidate names and revisions will be finalized only
after checking current official model cards, licenses, runtime support, and the
repaired GPU environment.

## Decision report template

Each model decision report must answer:

1. What exact role and failure mode required a model?
2. What baseline and alternatives were compared?
3. Which hard gates eliminated candidates?
4. On what fixed data, budget, and hardware were results measured?
5. What quality gain was obtained, and at what latency/VRAM/disk cost?
6. Which errors remain, and when should the selection be revisited?

