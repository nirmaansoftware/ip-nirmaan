"""IP Nirmaan over MCP (M22): plan, status, why, and task actions for AI hosts.

A separate tool table from VeriTriage's (``veritriage.mcp``); serve it with
``nirmaan mcp`` or ``python -m nirmaan.mcp``. See docs/NIRMAAN_MCP.md.
"""

from nirmaan.mcp.server import NirmaanMcpServer
from nirmaan.mcp.tools import McpContext, McpIdentityError, ToolSpec, call_tool, list_tools, register_tool, unregister_tool

__all__ = ["McpContext", "McpIdentityError", "NirmaanMcpServer", "ToolSpec", "call_tool", "list_tools", "register_tool",
           "unregister_tool"]


def serve(root: str = ".nirmaan", role: str | None = None) -> None:
    """Serve the tool table on stdin/stdout until EOF, as one agent in ``role`` if given (M50)."""
    from pathlib import Path

    NirmaanMcpServer(McpContext.default(Path(root), role)).serve_forever()
