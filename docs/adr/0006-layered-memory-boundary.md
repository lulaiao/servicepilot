# ADR 0006: Deterministic typed memory before learned memory

- Status: Accepted
- Date: 2026-08-08

## Context

ServicePilot needs cross-turn references and consented preferences without
allowing stale conversation text to become transactional truth. A generic
vector memory or LLM-generated summary would add retrieval and generation
variance before the precedence, expiry, consent and deletion semantics were
proven.

## Decision

Implement four explicit layers behind a lightweight internal boundary:

1. a bounded ordered recent-message window;
2. strongly typed working facts with source, observation time, validity and
   entity version;
3. deterministic factual summaries derived only from valid non-sensitive
   working facts;
4. purpose-bound, expiring long-term items requiring explicit user consent.

Authoritative tool facts outrank user, long-term and summary facts. Conflicting
values retain both fact IDs and a selection reason. Expired transaction facts
are removed rather than guessed. Long-term storage rejects sensitive keys and
obvious phone, card and email patterns even when consent exists.

Use an in-process thread-safe adapter for Phase 5 because the selection target
is semantic correctness, not multi-process durability. Storage remains behind
a boundary so a database adapter can be compared later.

## Alternatives

### Store the full transcript only

Simple, but loses important facts outside the context window and does not
provide source authority, expiry or user deletion semantics.

### Use an LLM summary immediately

Deferred because a generated statement can merge speculation with fact. A
learned summarizer must later beat the deterministic factual baseline on fact
precision, conflict safety, privacy and latency.

### Use a vector database as long-term memory

Deferred until Phase 6 retrieval requirements exist. Vector similarity does
not itself implement consent, source authority, expiry or transactional
freshness.

## Evidence and reversal conditions

Phase 5 tests cover 20-turn retention, reference resolution, stale expiry,
summary conflict, injected false memory, sensitive-data rejection, consent,
revocation and deletion. The frozen five-case ablation improves Memory
capability success from 0.4 to 1.0 without regressing three safety cases.

Replace the in-memory adapter only when durability or multi-process access is a
measured requirement. Add a learned summarizer only if it improves coverage
while retaining deterministic fact precision and privacy gates.
