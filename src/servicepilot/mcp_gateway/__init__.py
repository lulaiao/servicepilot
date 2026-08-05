"""Reliable MCP client gateway."""

from servicepilot.mcp_gateway.errors import ToolErrorCode

__all__ = [
    "ReliableToolGateway",
    "ToolErrorCode",
    "ToolFailure",
    "ToolResult",
]


def __getattr__(name: str) -> object:
    if name in {"ReliableToolGateway", "ToolFailure", "ToolResult"}:
        from servicepilot.mcp_gateway.gateway import (
            ReliableToolGateway,
            ToolFailure,
            ToolResult,
        )

        return {
            "ReliableToolGateway": ReliableToolGateway,
            "ToolFailure": ToolFailure,
            "ToolResult": ToolResult,
        }[name]
    raise AttributeError(name)
