# ADR 0003: MCP SDK v2 with an internal reliability gateway

- Status: Accepted
- Date: 2026-08-05

## Required capability

ServicePilot needs portable tool discovery/calls and exact structured schemas,
while retaining application-owned timeout, retry, budget, audit, confirmation,
idempotency, and fault semantics.

## Primary evidence

- The official repository identifies `mcp` v2 as the current stable line,
  supporting the 2026-07-28 specification and earlier revisions:
  https://github.com/modelcontextprotocol/python-sdk
- The signed v2.0.0 release was published on 2026-07-28:
  https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0
- The SDK is MIT licensed and requires Python 3.10+.
- Official v2 examples use `MCPServer`, typed tool signatures, structured output,
  `Client(server)` in-memory tests, stdio, and Streamable HTTP.

The local pre-existing Conda environment contained `mcp==1.28.1`. A clean
project `.venv` was therefore created with Python 3.11.15 and `mcp==2.0.0`.

## Alternatives

| Candidate | Correctness/capability | Reliability/observability | Complexity | Compatibility | Decision |
| --- | --- | --- | --- | --- | --- |
| Official SDK v2 + internal gateway | Actual v2 discovery and calls pass contract tests; supports current and earlier protocol revisions | Project controls retry, budgets, typed errors, idempotency and fault hooks | Moderate; protocol code is not reimplemented | Verified on project Python 3.11 | Accepted |
| Official SDK v1.28.1 | Installed locally but lacks the v2 `MCPServer`/`Client` surface and targets the maintenance line | Security fixes continue, but new project would begin on legacy API | Migration debt is immediate | Import spike confirmed incompatible API | Rejected |
| Fully custom MCP transport | Could match only the subset implemented | Maximum control, but protocol conformance and negotiation become project responsibility | Highest implementation and maintenance cost | No independent compatibility evidence | Rejected |
| SDK only, no internal gateway | Protocol calls work | Does not provide ServicePilot-specific budgets, error taxonomy, deterministic faults or recovery policy | Lowest initial code | Compatible | Rejected |

## Decision

- Pin `mcp==2.0.0`; upgrades require contract tests and an ADR amendment.
- Use five official `MCPServer` instances and native async tool functions.
- Keep Pydantic request models and `ServiceRegistry` as the transport-independent
  business boundary.
- Route Agent-side calls through `ReliableToolGateway`; it owns call budgets,
  bounded retry, exponential backoff, result summaries, trace IDs, durations,
  typed errors and deterministic fault injection.
- MCP tools may call `ServiceRegistry`, but neither layer may bypass
  `TransactionService` for high-risk business writes.
- Use in-memory `Client(server)` contract tests now. Prefer Streamable HTTP for a
  later deployment spike; no transport process is required for Phase 2.

## Consequences and reversal conditions

The project gains protocol conformance without outsourcing transaction safety to
the SDK. There are two validation layers—MCP signature validation and explicit
Pydantic domain-boundary validation—which is intentional defense in depth.

Revisit the pin when a v2 patch contains a relevant security/correctness fix.
Replace the internal gateway only if an SDK facility can provide the same typed
budget, retry, fault and trace contracts without coupling business state to the
transport.

