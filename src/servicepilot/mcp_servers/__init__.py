"""ServicePilot MCP servers."""

__all__ = ["ServiceRegistry", "build_seeded_servers", "build_servers"]


def __getattr__(name: str) -> object:
    if name == "ServiceRegistry":
        from servicepilot.mcp_servers.registry import ServiceRegistry

        return ServiceRegistry
    if name in {"build_seeded_servers", "build_servers"}:
        from servicepilot.mcp_servers.factory import (
            build_seeded_servers,
            build_servers,
        )

        return {
            "build_seeded_servers": build_seeded_servers,
            "build_servers": build_servers,
        }[name]
    raise AttributeError(name)
