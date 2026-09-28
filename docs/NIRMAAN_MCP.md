# IP Nirmaan over MCP, and organizational events (M22)

Status: implemented on branch `m22/mcp-and-events`, awaiting owner review. This
is Stage 3 of `docs/ROADMAP.md`. Prose here is free of em and en dashes per the
standing style law.

---

## 1. Goal

Claude Code or Cursor can plan a project and ask "why is this blocked?" over
the Model Context Protocol, and can move tasks through their lifecycle, without
any of that bypassing the task engine. Organizational moments (a task completed,
a gate approved, an escalation raised) reach the M18 event bus, so VeriTriage
automation rules can react to them.

Two constraints shape everything below:

1. **VeriTriage never imports Nirmaan**, and inside Nirmaan only
   `integrations/veritriage.py` imports VeriTriage. A Nirmaan tool therefore
   cannot be added to VeriTriage's MCP tool table (M8), because that table would
   have to import Nirmaan to call it.
2. **`EventKind` is a closed verification vocabulary.** M19 deliberately did
   not reuse the M18 bus, because adding `task_completed` or `gate_approved` to
   `EventKind` would teach VeriTriage about the organization.

---

## 2. A separate tool table: `nirmaan.mcp`

```
src/nirmaan/mcp/
  __init__.py    public surface
  tools.py       the tool table: register_tool, list_tools, call_tool, McpContext
  server.py      NirmaanMcpServer: a newline-delimited JSON-RPC stdio loop
  __main__.py    python -m nirmaan.mcp --root .nirmaan
```

It mirrors the M8 shape exactly (transport-agnostic table, one thin stdio
transport, `register_tool` as the extension point), but it is a second table,
not an extension of the first. The two servers are started separately
(`veritriage mcp` and `nirmaan mcp`), and a host that wants both registers both.
No tool name appears in both tables (pinned by a test), so a host that loads
both servers never sees an ambiguous name.

**Why not reuse `veritriage.mcp.McpStdioServer`?** It is bound to VeriTriage's
table and to `WorkspaceServices` by design. Generalizing it would be a change to
VeriTriage made only for Nirmaan's benefit, and reaching it would route a pure
JSON transport through the bridge. The protocol subset is about 80 lines
(`initialize`, `ping`, `tools/list`, `tools/call`), dependency-free and fully
testable in-process, so Nirmaan carries its own. No MCP SDK dependency is added.

### 2.1 The tools

| Tool | Kind | What it does |
|---|---|---|
| `plan_project` | plan | Requirement in, organization-driven plan out; saved to the project store |
| `list_projects` | read | Saved projects with progress |
| `show_plan` | read | The plan tree with current statuses (`detail` for reviewers, evidence, routing) |
| `project_status` | read | The manager's status report: blockers, escalations, reviews, gates, risks |
| `why_blocked` | read | The dependency and evidence chain for one task, as lines and as a tree |
| `audit_trail` | read | The hash-chained audit trail, verified |
| `organization_events` | read | Organizational events on the bus, and what automation decided |
| `start_task` | action | `TaskEngine.start` |
| `submit_task` | action | `TaskEngine.submit` (artifacts become EXECUTED, never more) |
| `record_evidence` | action | `TaskEngine.record_evidence` (the engine decides whether it is substantiated) |
| `review_task` | action | `TaskEngine.review` |
| `approve_task` | action | `TaskEngine.approve` (gates route to `approve_gate`) |
| `complete_task` | action | `TaskEngine.complete` |
| `block_task` | action | `TaskEngine.block` |
| `escalate_task` | action | `TaskEngine.escalate` |
| `resolve_escalation` | action | `TaskEngine.resolve_escalation` |

Task IDs may be given short (`microarchitecture`) or qualified
(`<project>:microarchitecture`), as in the CLI.

### 2.2 Actions go through the engine, never around it

Every action tool does exactly what `nirmaan task ...` does: load the project
(the store verifies the audit chain), build a `TaskEngine`, call one engine
method, save. The state machine, the authority matrix, and the constitution all
run; one audit entry is appended per change. A refused action raises
`WorkError` or `PolicyViolationError`, the transport returns it as an MCP tool
error (`isError: true`) so the model sees why, and **nothing is saved**.

**The MCP caller is always an AI agent.** Every action is taken as
`Actor(role=<role>, kind=AI_AGENT, name="mcp")`. There is deliberately no flag
to act as a human: an MCP host is a model, and letting it claim to be a person
would be exactly the faked work the constitution forbids. The consequences are
the right ones and come from the engine, not from this layer: a gate that
requires a human (`P12`) is refused over MCP, and a human attestation recorded
over MCP is stored unsubstantiated. A person approves those with the CLI.

The table has no write path of its own. `test_the_engine_is_the_only_writer`
(M19) already forbids constructing a `ProjectState` or assigning `._state`
outside the engine, and it covers `nirmaan/mcp/` automatically.

### 2.3 Extension

Adding a tool is one `@register_tool(name, description, input_schema)` on a
function `(McpContext, arguments) -> data`. The crown jewel
`test_a_new_mcp_tool_needs_only_registration` adds a throwaway tool and calls it
over the stdio transport with zero core changes.

---

## 3. Organizational events on the M18 bus

### 3.1 The coupling question, and the answer

Options considered:

| Option | Verdict |
|---|---|
| Add `TASK_COMPLETED`, `GATE_APPROVED`, `ESCALATION_RAISED` to `EventKind` | Rejected. VeriTriage would name Nirmaan's concepts; every future organizational event would be a VeriTriage change. |
| A second bus inside Nirmaan | Rejected. VeriTriage rules could not react, which is the point of the stage. |
| Subclass or wrap `EventBus` in the bridge | Rejected. `Event.kind` is typed `EventKind`; any non-member breaks validation. |
| **One generic member, `EventKind.EXTERNAL`, whose payload names a topic** | **Adopted.** |

The one change inside `src/veritriage/`:

```python
#: Published by a system beside VeriTriage, through that system's own
#: integration. ``Event.source`` names the publisher and ``payload["topic"]``
#: names what happened in the publisher's vocabulary. VeriTriage never
#: interprets either: only triggers someone registers do.
EXTERNAL = "external"
```

Why this is the minimal, generic change:

* **It names no one.** Nothing in VeriTriage mentions Nirmaan, tasks, gates, or
  escalations. A CI adapter (the deferred M18.x item) could publish on the same
  member tomorrow with `source="ci"`.
* **It is inert by default.** Every built-in trigger declares a specific
  `EventKind`, so `Trigger.applies` is false for EXTERNAL events and no shipped
  VeriTriage rule fires on them (pinned by a test). The workspace's own
  `_automate` never publishes it.
* **The existing machinery is unchanged.** Ordering, replay, bounding, the
  content-derived `event_id`, and "decide, never execute" all hold as they are:
  an EXTERNAL event is just an event.
* **The action vocabulary stays closed.** A rule reacting to an organizational
  event can only request an `ActionKind` the workspace already has. No new
  execution path appears.

`Event.source` already existed (default `"workspace"`); the bridge publishes
with `source="nirmaan"`.

### 3.2 Events are derived from the audit trail

The engine is not given a hook or a listener. An organizational event is a
projection of an audit entry:

| Audit action | Topic |
|---|---|
| `task.complete` | `task.completed` |
| `gate.approve` | `gate.approved` |
| `escalation.raise` | `escalation.raised` |

`nirmaan/events.py` (pure, no VeriTriage import) turns audit entries at or after
a sequence into `OrgEvent` records. Every event carries the audit entry's
sequence and hash, so each one is substantiated by the hash-chained record of
the change that caused it. An event cannot be published for something the
engine did not commit, which is "never fake work" applied to events. It also
means `engine.py` and the planner are untouched: a completion caused
indirectly (approval leads to completion, an evidence record completes
submitted work) is published because its audit entry exists, with no code path
to forget.

### 3.3 Publishing through the bridge

`integrations/veritriage.py` gains:

* three triggers, registered on import like the tool bindings:
  `nirmaan.task_completed`, `nirmaan.gate_approved`, `nirmaan.escalation_raised`.
  Each applies to EXTERNAL events and matches on `source == "nirmaan"` and the
  topic. They are Nirmaan's vocabulary, so they live on Nirmaan's side.
* one shipped rule, `nirmaan-escalation-raised`, which requests `NOTIFY` when an
  escalation is raised (plain data, like the M18 built-ins). A NOTIFY is
  recorded for a client to deliver; nothing is called.
* `AutomationBridge`: holds a `WorkspaceServices` (and therefore its bus),
  publishes each `OrgEvent` as `EventKind.EXTERNAL`, evaluates the registered
  rules with `RuleEngine`, dispatches what they request through
  `WorkspaceServices.dispatch_actions`, and returns the reactions as plain
  data.

The MCP server owns one `AutomationBridge` for its lifetime. After every
mutating tool call it publishes the events derived from the audit entries that
call appended, and returns them (with the rules that fired and the action
results) in the tool result, so the host sees the reaction immediately.
`organization_events` reads the bus log.

The bus is in memory, as in M18: events published by one `nirmaan mcp` process
are visible to that process. The audit trail, not the bus, remains the durable
record, and because events are derived from it they can always be re-derived.

---

## 4. Laws, and the tests that hold them

| Law | Test |
|---|---|
| VeriTriage never imports Nirmaan; only the bridge imports VeriTriage | existing M19 AST tests, which now also cover `nirmaan/mcp/` and `nirmaan/events.py` |
| VeriTriage's MCP table learns nothing about Nirmaan | `test_the_two_tool_tables_are_separate` |
| MCP actions go through the engine; refusals change nothing | `test_actions_move_work_through_the_engine`, `test_refused_actions_change_nothing`, `test_mcp_cannot_act_as_a_human` |
| Plan, then ask why, over the wire | `test_plan_then_ask_why_over_stdio` |
| Events on completion, gate approval, escalation | `test_events_are_derived_from_the_audit_trail`, `test_task_completion_and_gate_approval_over_mcp_publish_events`, `test_escalation_over_mcp_reaches_the_bus_and_the_shipped_rule_reacts` |
| A VeriTriage rule reacts to a Nirmaan event | `test_a_veritriage_rule_reacts_to_an_organizational_event` |
| EXTERNAL is inert for VeriTriage's own rules | `test_external_events_do_not_fire_verification_rules` |
| Crown jewel: a new MCP tool needs only registration | `test_a_new_mcp_tool_needs_only_registration` |

---

## 5. Using it

```
nirmaan mcp --root .nirmaan          # or: python -m nirmaan.mcp --root .nirmaan
```

Claude Code (`.mcp.json`):

```json
{"mcpServers": {"ip-nirmaan": {"command": "nirmaan", "args": ["mcp", "--root", ".nirmaan"]}}}
```

Then: "plan a 4-port AXI-to-NoC bridge", followed by "why is the
microarchitecture task blocked?".

---

## 6. Deferred

* A durable event log (the bus is in memory by M18's design; the audit trail is
  the durable record).
* More topics (task started, review recorded, artifact verified). Adding one is
  one row in `TOPICS` in `nirmaan/events.py` plus a trigger in the bridge.
* Tools for tool-run evidence (`task tool` in the CLI). The broker path is
  unchanged and reachable from the CLI; exposing it over MCP should follow
  Stage 2's real bindings.
