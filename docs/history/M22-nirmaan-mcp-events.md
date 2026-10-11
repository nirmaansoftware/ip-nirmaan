# Milestone 22 - IP Nirmaan over MCP, and organizational events (roadmap Stage 3)

Claude Code or Cursor can now plan a project, ask "why is this blocked?", and
move tasks through their lifecycle over MCP, and organizational moments reach
the M18 bus so VeriTriage automation rules can react. Version bump is left to
the coordinator at merge.

**A second tool table, not an extension of the first.** `src/nirmaan/mcp/`
(`tools.py` table with `@register_tool`, `server.py` stdio transport,
`__main__.py`) mirrors M8's shape. VeriTriage's table cannot hold Nirmaan tools
(it would have to import Nirmaan), and its `McpStdioServer` is bound to its
table and `WorkspaceServices`, so Nirmaan carries its own ~80-line JSON-RPC
subset rather than generalizing VeriTriage for Nirmaan's sake. Serve with
`nirmaan mcp --root .nirmaan` or `python -m nirmaan.mcp`. 16 tools: plan,
list, show, status, why, audit, organization events, and nine task actions.
No tool name collides with VeriTriage's (`recent_events` was renamed
`organization_events` when a test caught the overlap).

**Actions go through the engine.** Each action tool is load, one `TaskEngine`
call, save: state machine, authority, constitution, one audit entry. Refusals
come back as MCP tool errors and save nothing. **The MCP caller is always
`ActorKind.AI_AGENT`**; there is no flag to act as a human, so human-required
gates are refused by P12 and attestations over MCP are unsubstantiated. People
use the CLI for those.

**The event-bus coupling question, resolved.** `EventKind` stays a closed
verification vocabulary plus ONE generic member, `EventKind.EXTERNAL`: events
published by a system beside VeriTriage, with `Event.source` naming the
publisher and `payload["topic"]` naming what happened. VeriTriage names no
Nirmaan concept; no built-in trigger applies to EXTERNAL, so it is inert until
someone registers a trigger. That one enum member is the only change inside
`src/veritriage/`. Rejected: Nirmaan members in `EventKind` (couples the
engine), a Nirmaan-only bus (rules could not react), wrapping `EventBus`
(`Event.kind` is typed).

**Events are projections of the audit trail**, not engine hooks.
`nirmaan/events.py` maps `task.complete`, `gate.approve`, `escalation.raise`
audit entries to `task.completed`, `gate.approved`, `escalation.raised`
`OrgEvent`s carrying the entry's sequence and hash. The engine is untouched,
indirect completions (approval implies completion) are caught for free, and an
event cannot exist for a change the engine did not commit. The bridge registers
three triggers (`nirmaan.task_completed`, `nirmaan.gate_approved`,
`nirmaan.escalation_raised`), ships one rule (`nirmaan-escalation-raised` ->
NOTIFY), and adds `AutomationBridge`, which publishes onto a
`WorkspaceServices` bus with `source="nirmaan"`, evaluates rules, and dispatches
through `dispatch_actions`. Each MCP action returns the events it caused and
what automation decided.

13 new tests in `tests/test_nirmaan_mcp.py` (892 total). Crown jewel
`test_a_new_mcp_tool_needs_only_registration`. The existing M19 import-law and
no-dash tests cover the new modules and `docs/NIRMAAN_MCP.md` automatically.
Design doc: `docs/NIRMAAN_MCP.md`.

Deferred: a durable event log (the audit trail is the durable record), more
topics (one row in `TOPICS` plus a trigger), and tool-run evidence over MCP
(after Stage 2's real bindings).
