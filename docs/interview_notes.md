# Interview notes

Answers in this document must reflect implemented behavior and measured
evidence. Topics are filled as their owning phase completes.

## Phase 0 decisions

### Why an explicit state machine first?

The project is evaluated by transactional outcomes, recovery paths, and routing
changes after tool observations. An explicit typed state machine makes those
transitions inspectable and testable. A graph framework remains an option if
later requirements demonstrate a need for persisted interruption/resumption.

### Why can transaction state not live only in a conversation summary?

Summaries are lossy model-generated text and may be stale. Refund amount, order
version, payment records, and write results require authoritative typed storage,
source timestamps, and concurrency controls. Conversation memory may reference
those facts but cannot replace them.

### How is real completion distinguished from a claim?

The planned judge checks the authoritative final repository state, matching
idempotent audit events, and executable policy assertions. Agent text is an
observation, not proof of completion.

### Why were these technologies selected instead of popular alternatives?

The project does not treat popularity as evidence. Phase 0 accepts only choices
needed to keep the deterministic core testable: Python 3.11, an explicit typed
state machine, repository interfaces, and JSONL traces. FastAPI, PostgreSQL, the
MCP SDK, retrieval libraries, inference servers, and local models are currently
provisional or deferred. Each is promoted only after an equal-budget comparison
against the simplest baseline and credible alternatives, with license,
compatibility, correctness, reliability, latency, memory, and operational cost
recorded. The decision and its reversal condition live in an ADR.

### Why is Qwen not automatically the chosen model?

It is a candidate suggested by the original brief, not experimental evidence.
The actual choice depends on the role: structured extraction, planning/tool use,
embedding, reranking, monitoring, and training have different objectives. After
GPU repair and official model-card/license verification, candidates will be
tested on frozen ServicePilot scenarios against deterministic and smaller-model
baselines. The smallest model that meets quality and safety gates is preferred;
larger size must justify its measured latency, memory, and disk cost.

## Phase 1 decisions

### How does the system avoid duplicate refunds after a lost response?

The write service stores an action-scoped idempotency key together with a hash
of the normalized request and the authoritative result inside the same
repository transaction as the refund. An identical retry returns that result
before checking the now-stale order version. Reusing the key with different
parameters raises an idempotency conflict. A concurrent test submits 32
identical calls and verifies that exactly one refund exists.

### Why use immutable records and optimistic versions?

Immutable dataclasses make state changes explicit and prevent hidden in-place
mutation. Each accepted mutation returns a new aggregate with an incremented
version. Callers must provide the version observed during preview; a mismatch
rejects stale decisions before a write. The in-memory lock makes Phase 1 atomic,
while the same contract can map to a PostgreSQL transaction later.

### Why keep policy in both text and executable code?

Natural-language sections are retrievable evidence for later Policy Agents.
Executable assertions are deterministic truth for write authorization and
evaluation. Stable evidence IDs and policy versions connect the two, so an
Agent cannot approve an operation merely by generating persuasive text.

## Phase 2 decisions

### Why MCP SDK v2 rather than the already installed v1?

At implementation time, official v2.0.0 was the stable line and supported the
2026-07-28 protocol plus earlier revisions. The existing v1.28.1 environment did
not expose the v2 `MCPServer` and `Client` API and was already on the maintenance
line. Starting new code on v1 would create immediate migration debt. We pinned
v2 and proved actual tool discovery and structured in-memory calls rather than
relying only on documentation.

### Why is an internal Gateway still needed if MCP already wraps tools?

MCP standardizes discovery, schemas, calls and transports. It does not define
ServicePilot's retry budget, transaction confirmation, idempotency fingerprint,
optimistic version recovery, fault curriculum, trace summary or error policy.
Those remain application concerns in `ReliableToolGateway` and the domain
service. This separation also permits the deterministic baseline to run without
starting a network server.

### What happens when a refund commits but the response is lost?

The fault hook raises only after `create_refund_request` commits. Gateway marks
the failure retryable and sends the identical request again. The domain service
finds the action-scoped idempotency record and returns the original refund
before rejecting the now-stale version or consumed token. The contract test
asserts one refund and two attempts.

### Why are version conflicts not automatically retried?

A version conflict means the user's confirmation was based on stale business
state. Blind retry could execute an action the user did not approve under the
new conditions. Recovery must re-read, re-evaluate policy, generate a new
preview and obtain confirmation.

## Phase 3 decisions

### Why start with a rule Agent instead of a local LLM?

The rule baseline isolates system correctness from model variance. If
confirmation, idempotency, state transitions, fault recovery or the Judge are
wrong, an LLM would make the failure harder to localize. The baseline also
provides a lower-bound cost/quality point that every local model must beat under
the same tool and turn budget.

### How do we know the Agent really completed the task?

The final message is not an evaluation input. The Judge reads the order,
refunds, coupon, delivery issues, handoff tickets and schedule from the
Repository, then checks required/forbidden actions and policy evidence. A unit
test deliberately gives the Judge an impossible expected state while retaining
an Agent success claim; it is labeled `FALSE_SUCCESS`.

### Why is a 100% Phase 3 score not a model-quality claim?

The 36 cases are a deterministic development catalog deliberately aligned with
the explicit rule baseline. The score proves that the executable loop and
assertions agree on these fixed cases. It does not measure paraphrase
generalization, unseen policy reasoning or learned tool use. Phase 4 must use a
sealed scenario split and equal-budget comparisons before making those claims.

### How does the user simulator avoid leaking hidden state?

The user simulator owns the scenario and releases order ID, refund details or
new schedule only through explicit response methods after the Agent asks. It can
reject an unexplained or undesired write. The Agent does not read the Judge's
expected final state.

## Phase 4 model decision

### Why did the project keep rules after the 7B model had better Macro-F1?

Component accuracy was not the deployment objective. Qwen2.5-7B-Instruct
improved development Macro-F1 from 0.8333 to 0.8909, but when substituted into
the same routed Agent it reduced executable success from 36/36 to 32/36,
introduced 0.0556 false-success and 0.1111 high-risk control error, added about
2.09 seconds per scenario, and required 14.3 GiB peak VRAM. The deterministic
Judge exposed errors that an intent leaderboard would hide, so the rule
classifier remained the smallest candidate satisfying the MVP safety and task
requirements.

### Is the 7B comparison a full LLM Agent comparison?

No. It is intentionally a learned-extractor comparison. Both variants share
the deterministic action policy, Router, Gateway, confirmation protocol and
Judge; only intent/slot extraction changes. Claiming autonomous 7B planning or
tool use from this experiment would overstate the implementation.
