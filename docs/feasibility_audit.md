# Phase 0 feasibility audit

Audit date: 2026-08-05 (Asia/Shanghai)  
Workspace: `/data/ssd1/lla/servicepilot`

## Executive result

The host has ample CPU, RAM, and disk capacity for the deterministic simulator,
scenario runner, retrieval corpus, and local experiment artifacts. Phase 1 can
proceed without Docker or a GPU by using an in-process repository and synthetic
data. Python 3.11 is not in the default `PATH`, but an existing compatible
environment was discovered and used for Phase 1:
`/data/ssd1/lla/conda_envs/mcp-sql-reflex-rl/bin/python` (Python 3.11.15).
Docker daemon access and the NVIDIA runtime are currently blocked and must be
resolved before container integration or model experiments.

## Observed environment

| Item | Observed value | Assessment |
| --- | --- | --- |
| OS | Ubuntu 22.04 LTS, kernel `5.15.0-70-generic` | Supported; kernel string carries an older Ubuntu build tag but userland reports Jammy |
| CPU | 2 × Intel Xeon Gold 6530, 64 cores / 128 threads, 4 NUMA nodes | More than sufficient for deterministic tests and data generation |
| Memory | 503 GiB total, 401 GiB available | Sufficient; all 7.6 GiB swap was in use during audit and should be monitored |
| Workspace disk | 15 TiB total, 3.4 TiB available, 76% used | Sufficient for MVP; set artifact quotas before model/training work |
| Inodes | 466M total, 5% used | No inode pressure |
| Python | System CPython 3.8.10; existing project environment CPython 3.11.15 | Target runtime available through an explicit interpreter path |
| Git | 2.25.1 | Adequate |
| Docker | CLI 23.0.4, Compose 2.17.2 | Installed, but daemon socket access is denied |
| CUDA toolkit | `nvcc` 12.1 (V12.1.66) | Toolkit exists; not proof that runtime is usable |
| NVIDIA runtime | Kernel modules loaded; `nvidia-smi` cannot communicate with driver | Blocker for GPU inference/training |
| Directory access | `/data/ssd1/lla` writable by `lula:lula` | Project creation is feasible |
| Open-file limit | 1,048,576 | Suitable for local service tests |

The parent workspace is not a Git repository. A new, independent Git repository
was initialized at `/data/ssd1/lla/servicepilot`. No project directory existed
before creation. No applicable parent `AGENTS.md` was found within the searched
workspace depth.

## Capacity estimate and guardrails

These are planning bounds, not measured experiment results:

- Source, tests, policies, and 1,000 compressed JSONL trajectories: normally
  below 10 GiB; reserve 50 GiB for reports and trace variants.
- PostgreSQL and indexes for synthetic MVP data: reserve 20 GiB initially.
- Model weights, optimizer state, and checkpoints may consume hundreds of GiB.
  Before Phase 9, require an explicit per-run disk budget and retain only
  manifest-addressed checkpoints.
- Four A6000-class GPUs would be adequate for the proposed small-model LoRA and
  bounded GRPO experiments, but the actual GPU inventory is **unknown** because
  `nvidia-smi` failed. No throughput or VRAM claim is made.

## Risks and mitigations

1. **Python environment isolation — low.** Python 3.8 remains the system
   default, so commands must explicitly use the discovered Python 3.11
   environment. Do not mutate the system Python or assume shell activation.
2. **GPU driver/runtime — high for model phases, none for Phase 1.** Ask the
   server administrator to validate driver/library compatibility and device
   visibility. Re-run `nvidia-smi` before selecting vLLM, SGLang, PyTorch, or
   model wheels.
3. **Docker permissions — medium.** The active user cannot connect to
   `/var/run/docker.sock`. Phase 1 will use an in-memory implementation; later
   persistence tests can use a user-managed PostgreSQL instance or approved
   Docker access.
4. **Disk growth — medium.** The volume is already 76% used. Use manifests,
   quotas, checksums, and cleanup policies; never commit weights, volumes, or
   bulk traces.
5. **Dependency/API drift — medium.** Pin tested dependency ranges and lock
   exact versions after Python 3.11 is available. Verify the official MCP SDK
   interface immediately before Phase 2 rather than guessing an API today.
6. **Training throughput — unknown.** GPU quantity, VRAM, utilization, and
   driver status were not measurable. Benchmark a small single-GPU workload
   before scheduling multi-GPU experiments.
7. **Data leakage — medium.** Generate all business records and keep scenario
   splits manifest-addressed. Hash normalized scenario families before split to
   prevent paraphrase leakage.

## Phase 0 acceptance evidence

- Repository skeleton and project metadata exist.
- The health smoke test has no third-party dependencies.
- Model downloads, paid APIs, system package installs, and Docker services were
  not invoked.
- Test result is recorded in `CHANGELOG.md` after execution.
