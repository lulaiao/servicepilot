# Architecture

The Phase 1 deterministic core now owns immutable domain records, explicit order
transitions, versioned policy assertions, repository contracts, and
preview-confirm-execute transaction services.

The in-memory repository uses a process-local re-entrant transaction lock. It is
the accepted unit-test adapter, not the production concurrency claim. A later
PostgreSQL adapter must preserve the same repository and service invariants.

All later MCP tools call `TransactionService`; they may not write repository
state directly. Routing, memory, retrieval, monitoring, tracing, evaluation,
and training remain separate consumers of the same authoritative business
state.

For high-risk writes:

1. preview evaluates current policy and creates a payload-bound token;
2. execute validates token, idempotency fingerprint, and aggregate version;
3. the mutation and idempotency record are stored atomically;
4. the confirmation is consumed and an audit event is appended;
5. an identical retry returns the stored result before stale-version checks.

## MCP boundary

Five official MCP SDK v2 servers expose 22 tools: Order, Payment/Refund, Coupon,
Policy, and Merchant/Delivery. Native async MCP functions avoid worker-thread
coupling and delegate to a transport-independent `ServiceRegistry`.

The call path is:

```text
Agent -> ReliableToolGateway -> MCP/Registry -> TransactionService
      -> PolicyEngine + DomainRepository
```

The Gateway owns trace IDs, duration, result summary, call/retry budgets,
exponential backoff, error classification and fault injection. MCP owns protocol
discovery, schemas, structured output and transport compatibility. The domain
service remains the only high-risk write authority.

## Phase 3 executable loop

```text
ScenarioSpec -> FSMUserSimulator <-> RuleBasedSingleAgent
                                  -> ReliableToolGateway
                                  -> authoritative Repository
Trajectory + final Repository ----> DeterministicJudge -> EvalReport
```

The Agent receives information through simulated user messages. It asks for
order ID and transactional slots, previews high-risk writes, explains the
preview, waits for confirmation, and only then executes. The Judge is outside
the Agent and has read-only access to the final authoritative state.

## Agent Harness boundary

Runtime assembly is behind a typed `AgentRuntimeHarness` and trial assembly is
behind an `EvaluationHarness`. The Runtime Harness owns sessions,
budgets, guardrail ordering, dependency injection, trace/checkpoint recording
and termination. The Evaluation Harness owns isolated environment setup, user
simulation, authoritative grading and aggregation.

The Harness is not a new business authority. Writes still flow exclusively
through `ReliableToolGateway` to `TransactionService`; replay and evaluation
paths are forbidden from issuing writes. Detailed contracts and acceptance
criteria are in `docs/harness_design.md`.

## Evidence and delivery boundary

Evaluation artifacts are produced from fixed scenario catalogs and deterministic
Judges. Reports never become claims by themselves: tracked Manifests bind data,
protocol, revision, seed and raw-result hashes, while ADRs record whether a gate
accepted or rejected a candidate.

The Phase 10 demo runs four CPU-only executable cases and renders their escaped
JSONL events into a dependency-free HTML viewer. The viewer is presentation
only: it cannot execute tools or mutate business state.
