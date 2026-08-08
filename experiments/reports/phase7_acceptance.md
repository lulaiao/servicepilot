# Phase 7 acceptance: bounded Monitor and executable fault workload

Date: 2026-08-08  
Status: Accepted

## Accepted boundary

The Monitor reads only redacted trace summaries, deterministic Judge results,
and Harness budgets. It has no Repository, Dispatcher, raw-argument, credential,
or business-write access. Findings remain advisory recommendations; existing
Harness and Guardrail components own enforcement.

Synchronous and bounded asynchronous paths share one thirteen-rule engine. The
asynchronous queue applies backpressure instead of silently dropping safety
observations.

## Executable workload

Revision `2f1314a` executed 1,008 real Harness runs over the frozen 36-scenario
catalog. A fixed seed assigns 28 redacted-boundary profiles: four clean,
thirteen single-fault, and eleven two-fault profiles. The profiles cover all
thirteen declared Monitor fault classes.

| Metric | Result |
| --- | ---: |
| Executable trajectories | 1,008 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| Sync/async parity | 1.0000 |
| Monitor-caused state mutations | 0 |
| Authoritative task success | 1.0000 |
| Natural retry trajectories | 308 |
| Successful natural recoveries | 308 |
| Mean synchronous Monitor latency | 0.0145 ms |
| P95 synchronous Monitor latency | 0.0251 ms |
| Mean async round-trip latency | 0.0172 ms |

The no-Monitor/non-interference assertion fingerprints authoritative order,
refund, and audit state before and after both Monitor paths. No fingerprint
changed. Naturally injected transient Gateway failures are counted from
Harness retry telemetry rather than being relabeled as terminal tool failures.

## Reproducibility

- Seed: `20260808`
- Schedule SHA-256:
  `bd37f5705b1842006a9ab9fdf66e16068591fe88b504ab84647f3dae512df2c7`
- Raw report SHA-256:
  `b5511faa171a97ba4b3b70320177be2c1b5fcf088d73300832a16c96d9155bcd`
- Manifest: `experiments/manifests/phase7_executable_monitor.json`

## Limitations

- All trajectories use the deterministic internal scenario catalog rather than
  production traffic.
- Transient retry recovery is exercised inside the real Gateway/Harness path;
  the other Monitor classes are injected at the typed redacted boundary. This
  evaluates detection wiring, not their natural incidence distribution.
- The latency result is for deterministic CPU rules and an in-process queue;
  it is not a distributed Monitor service benchmark.

