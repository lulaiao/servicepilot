# Architecture

Phase 0 establishes module boundaries only. The deterministic core will own
domain transitions and policy assertions; all later agent writes must pass
through typed MCP services. Routing, memory, retrieval, monitoring, tracing,
evaluation, and training remain separate consumers of the same authoritative
business state.

