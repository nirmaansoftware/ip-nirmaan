"""IP Nirmaan over MCP (M22): plan, status, why, and task actions for AI hosts.

A separate tool table from VeriTriage's (``veritriage.mcp``); serve it with
``nirmaan mcp`` or ``python -m nirmaan.mcp``. See docs/NIRMAAN_MCP.md.
"""

from nirmaan.mcp.server import NirmaanMcpServer
from nirmaan.mcp.tools import McpContext, ToolSpec, call_tool, list_tools, register_tool, unregister_tool

__all__ = ["McpContext", "NirmaanMcpServer", "ToolSpec", "call_tool", "list_tools", "register_tool",
           "unregister_tool"]


def serve(root: str = ".nirmaan") -> None:
    """Serve the tool table on stdin/stdout until EOF."""
    from pathlib import Path

    NirmaanMcpServer(McpContext.default(Path(root))).serve_forever()
