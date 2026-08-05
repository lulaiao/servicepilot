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
