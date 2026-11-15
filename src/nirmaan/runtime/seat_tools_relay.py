"""The stdio relay Claude Code starts as the brokered server (M75, tools in the loop). Holds no tool.

    /usr/bin/env -i <python> -I seat_tools_relay.py <socket>

Claude Code speaks MCP to it on stdin and stdout, one JSON-RPC message per
line. It answers the handshake itself and hands every ``tools/list`` and
``tools/call`` to the eval process over the private socket, with the token
from the file beside the socket, and passes the reply back. Every tool runs
in the eval process, through the broker (``seat_tools.SeatTools``), which
refuses, caps and records; nothing here can run or read anything.

It imports only the standard library and is started with an empty
environment in isolated mode, so no credential, path or package of the eval
process reaches it.
"""

import json
import socket
import sys
from pathlib import Path

PROTOCOL = "2025-06-18"


def ask(path, token, method, params):
    """The eval process's reply to one request, or an error when it cannot be reached."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3600)
            conn.connect(path)
            conn.sendall(json.dumps({"token": token, "method": method, "params": params}).encode("utf-8") + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode("utf-8"))
    except (OSError, ValueError) as exc:
        return {"error": f"the broker is not reachable ({type(exc).__name__})"}


def respond(message, path, token):
    """The JSON-RPC response to one message, or None for a notification."""
    if "id" not in message:
        return None
    method, mid = message.get("method"), message["id"]
    if method == "initialize":
        asked = (message.get("params") or {}).get("protocolVersion")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": asked if isinstance(asked, str) else PROTOCOL, "capabilities": {"tools": {}},
            "serverInfo": {"name": "nirmaan-broker", "version": "1"}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method in ("tools/list", "tools/call"):
        reply = ask(path, token, method, message.get("params") or {})
        if "result" in reply:
            return {"jsonrpc": "2.0", "id": mid, "result": reply["result"]}
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(reply.get("error"))}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method!r}"}}


def main(argv):
    path = argv[1]
    token = (Path(path).parent / "token").read_text(encoding="utf-8").strip()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if not isinstance(message, dict):
            continue
        out = respond(message, path, token)
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
