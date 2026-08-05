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
