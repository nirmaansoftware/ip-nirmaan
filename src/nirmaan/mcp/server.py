"""Minimal MCP stdio transport for the IP Nirmaan tool table.

The same protocol subset as VeriTriage's M8 server (``initialize``, the
``notifications/initialized`` notification, ``ping``, ``tools/list``,
``tools/call``) over newline-delimited JSON-RPC 2.0, but over Nirmaan's own
table. It is a separate copy on purpose: VeriTriage's transport is bound to its
table and services, and the import laws keep the two apart (docs/NIRMAAN_MCP.md).
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

import nirmaan
from nirmaan.mcp.tools import McpContext, call_tool, list_tools

#: The MCP protocol revision this transport implements the subset of.
PROTOCOL_VERSION = "2024-11-05"

_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_PARSE_ERROR = -32700


class NirmaanMcpServer:
    """Serves the IP Nirmaan tool table over newline-delimited JSON-RPC."""

    def __init__(self, ctx: McpContext, in_stream: TextIO | None = None, out_stream: TextIO | None = None) -> None:
        self._ctx = ctx
        self._in = in_stream if in_stream is not None else sys.stdin
        self._out = out_stream if out_stream is not None else sys.stdout

    def serve_forever(self) -> None:
        """Read requests until EOF; one JSON-RPC message per line."""
        for line in self._in:
            line = line.strip()
            if not line:
                continue
            response = self.handle_line(line)
            if response is not None:
                self._out.write(json.dumps(response) + "\n")
                self._out.flush()

    def handle_line(self, line: str) -> dict[str, Any] | None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, _PARSE_ERROR, f"parse error: {exc}")
        if not isinstance(message, dict):
            return _error(None, _PARSE_ERROR, "expected a JSON-RPC object")
        return self.handle_message(message)

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        if msg_id is None:
            return None  # a notification (including notifications/initialized): no response
        if method == "initialize":
            return _result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ip-nirmaan", "version": nirmaan.__version__},
            })
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            return _result(msg_id, {"tools": [
                {"name": s.name, "description": s.description, "inputSchema": s.input_schema} for s in list_tools()
            ]})
        if method == "tools/call":
            return self._handle_tool_call(msg_id, params)
        return _error(msg_id, _METHOD_NOT_FOUND, f"method not found: {method}")

    def _handle_tool_call(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            return _error(msg_id, _INVALID_PARAMS, "tools/call requires a tool 'name'")
        try:
            result = call_tool(self._ctx, name, params.get("arguments") or {})
        except KeyError as exc:
            return _result(msg_id, _tool_error(str(exc.args[0]) if exc.args else str(exc)))
        except Exception as exc:  # noqa: BLE001 - refusals are shown to the model, never crash the loop
            return _result(msg_id, _tool_error(f"{type(exc).__name__}: {exc}"))
        text = json.dumps(result, indent=2, default=str)
        return _result(msg_id, {"content": [{"type": "text", "text": text}], "isError": False})


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}
