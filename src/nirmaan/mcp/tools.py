"""The IP Nirmaan MCP tool table (M22): plan, status, why, and task actions.

A second table beside VeriTriage's (M8), never an extension of it: VeriTriage
never imports Nirmaan, so its table cannot call these tools. The shape is the
same: a name, a description, a JSON-schema input contract, and a handler that
returns JSON-serializable data. ``server.py`` is one thin stdio transport.

Every action goes through the task engine, exactly as ``nirmaan task ...``
does: the state machine, the authority matrix, and the constitution run, one
audit entry records the change, and a refusal saves nothing. The caller is
always an AI agent; there is no way to act as a human over MCP. After each
action the organizational events it caused (derived from the audit entries it
appended) are published to the M18 bus through the bridge.

Adding a tool is one ``register_tool`` call (crown-jewel tested).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from nirmaan.company import build_organization
from nirmaan.events import org_events
from nirmaan.models import Actor, ActorKind, EscalationKind, EvidenceKind, Verdict
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import Organization
from nirmaan.views import plan_tree
from nirmaan.work import ProjectStore, TaskEngine, status_report, verify_chain, why_blocked

Publisher = Callable[[list], list]
Handler = Callable[["McpContext", dict[str, Any]], Any]


@dataclass
class McpContext:
    """What every tool needs: the organization, the project store, and the event publisher."""

    org: Organization
    store: ProjectStore
    publish: Publisher = field(default=lambda events: [])
    recent_events: Callable[[int], list] = field(default=lambda limit: [])

    @classmethod
    def default(cls, root: Path = Path(".nirmaan")) -> "McpContext":
        from nirmaan.integrations.veritriage import AutomationBridge

        bridge = AutomationBridge()
        return cls(build_organization(), ProjectStore(root), bridge.publish, bridge.recent)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler


_TOOLS: dict[str, ToolSpec] = {}


def register_tool(name: str, description: str, input_schema: dict[str, Any]) -> Callable[[Handler], Handler]:
    """Decorator adding a tool to the table.

    Raises:
        ValueError: If another tool already registered the same name.
    """

    def _register(handler: Handler) -> Handler:
        if name in _TOOLS and _TOOLS[name].handler is not handler:
            raise ValueError(f"MCP tool name {name!r} is already registered")
        _TOOLS[name] = ToolSpec(name, description, input_schema, handler)
        return handler

    return _register


def unregister_tool(name: str) -> None:
    """Remove a tool (used by tests to clean up throwaway tools)."""
    _TOOLS.pop(name, None)


def list_tools() -> list[ToolSpec]:
    """Every registered tool, in sorted-name order."""
    return [_TOOLS[name] for name in sorted(_TOOLS)]


def call_tool(ctx: McpContext, name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch one tool call.

    Raises:
        KeyError: If no tool with that name is registered.
    """
    spec = _TOOLS.get(name)
    if spec is None:
        raise KeyError(f"Unknown tool {name!r}. Registered tools: {', '.join(sorted(_TOOLS)) or '<none>'}")
    return spec.handler(ctx, arguments)


# --- Helpers ------------------------------------------------------------------------------


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


_PROJECT = {"project": {"type": "string", "description": "Project ID (a unique prefix is enough)."}}
_TASK = {"task": {"type": "string", "description": "Task ID, short ('microarchitecture') or '<project>:<stage>'."}}
_ROLE = {"role": {"type": "string", "description": "Role ID acting. The caller always acts as an AI agent."}}


def _load(ctx: McpContext, project: str) -> TaskEngine:
    return TaskEngine(ctx.org, ctx.store.load(project))


def _task_id(engine: TaskEngine, task: str) -> str:
    return task if ":" in task else f"{engine.state.project.id}:{task}"


def _actor(arguments: dict[str, Any]) -> Actor:
    return Actor(role=str(arguments["role"]), kind=ActorKind.AI_AGENT, name="mcp")


def _task_view(engine: TaskEngine, task_id: str) -> dict[str, Any]:
    t = engine.task(task_id)
    return {"id": t.id, "title": t.title, "kind": t.kind.value, "status": t.status.value,
            "owner": t.owner, "reviewer": t.reviewer, "approver": t.approver,
            "review_state": t.review_state.value}


def _act(ctx: McpContext, arguments: dict[str, Any], action: Callable[[TaskEngine, str, Actor], Any]) -> dict:
    """Load, run one engine operation, save, publish what the audit trail now records."""
    engine = _load(ctx, str(arguments["project"]))
    before = len(engine.state.audit)
    task_id = _task_id(engine, str(arguments["task"])) if "task" in arguments else None
    if task_id is not None:
        engine.task(task_id)  # unknown task: refused before anything runs
    result = action(engine, task_id, _actor(arguments))
    ctx.store.save(engine.state)
    events = org_events(engine.state, since=before)
    out: dict[str, Any] = {"result": result}
    if task_id is not None:
        out["task"] = _task_view(engine, task_id)
    out["audit_entries_added"] = len(engine.state.audit) - before
    out["events"] = ctx.publish(events) if events else []
    return out


# --- Planning and reading -----------------------------------------------------------------


@register_tool(
    "plan_project",
    "Turn a requirement into an organization-driven execution plan: owners, independent "
    "reviewers, approvers, gates, and evidence requirements. The plan is saved; every task "
    "starts PLANNED or READY (planning never claims anything was done).",
    _schema({
        "requirement": {"type": "string", "description": "e.g. 'Create a 4-port AXI-to-NoC bridge.'"},
        "human_gates": {"type": "array", "items": {"type": "string"}, "description": "Gate IDs to require a human at."},
        "auto_gates": {"type": "array", "items": {"type": "string"}, "description": "Gate IDs a non-human may approve."},
    }, ["requirement"]),
)
def _plan_project(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    overrides = {g: True for g in arguments.get("human_gates", [])} | {g: False for g in arguments.get("auto_gates", [])}
    engine = Orchestrator(ctx.org).plan(str(arguments["requirement"]), gate_overrides=overrides)
    ctx.store.save(engine.state)
    project = engine.state.project
    return {
        "project": project.id,
        "name": project.name,
        "intent": project.analysis.intent,
        "workflows": list(project.workflows),
        "tasks": [_task_view(engine, t) for t in engine.state.tasks],
        "plan": plan_tree(ctx.org, engine.state),
    }


@register_tool("list_projects", "Saved projects, with intent and progress.", _schema({}, []))
def _list_projects(ctx: McpContext, arguments: dict[str, Any]) -> list:
    out = []
    for state in ctx.store.list():
        report = status_report(ctx.org, state)
        out.append({"project": state.project.id, "name": state.project.name, "intent": report.intent,
                    "tasks": report.tasks, "progress": report.progress})
    return out


@register_tool(
    "show_plan",
    "A saved project's plan tree with current statuses.",
    _schema({**_PROJECT, "detail": {"type": "boolean", "description": "Reviewers, evidence, routing."}}, ["project"]),
)
def _show_plan(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    engine = _load(ctx, str(arguments["project"]))
    return {"project": engine.state.project.id,
            "plan": plan_tree(ctx.org, engine.state, bool(arguments.get("detail", False)))}


@register_tool(
    "project_status",
    "The manager's view of a project: progress, blockers, open escalations, pending reviews, "
    "gates, risks, and assumptions.",
    _schema(_PROJECT, ["project"]),
)
def _project_status(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return status_report(ctx.org, _load(ctx, str(arguments["project"])).state).to_dict()


@register_tool(
    "why_blocked",
    "Why is this task blocked? The dependency, review, escalation, and evidence chain, "
    "explained recursively down to whatever can move next.",
    _schema({**_PROJECT, **_TASK}, ["project", "task"]),
)
def _why_blocked(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    engine = _load(ctx, str(arguments["project"]))
    blocker = why_blocked(engine.state, _task_id(engine, str(arguments["task"])))
    return {"blocked": blocker.is_blocked, "explanation": blocker.lines(), "chain": blocker.to_dict()}


@register_tool(
    "audit_trail",
    "The project's hash-chained audit trail, verified: who did what, to what, and why.",
    _schema({**_PROJECT, "tail": {"type": "integer", "description": "Newest entries to return (default 20)."}},
            ["project"]),
)
def _audit_trail(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    state = _load(ctx, str(arguments["project"])).state
    tail = int(arguments.get("tail", 20))
    return {
        "entries": len(state.audit),
        "chain_problems": verify_chain(state.audit),
        "tail": [{"sequence": e.sequence, "actor": e.actor, "action": e.action, "subject": e.subject,
                  "reason": e.reason} for e in state.audit[-tail:]],
    }


@register_tool(
    "organization_events",
    "Organizational events (task completed, gate approved, escalation raised) published on "
    "the automation bus by this server.",
    _schema({"limit": {"type": "integer", "description": "Max events (default 50)."}}, []),
)
def _organization_events(ctx: McpContext, arguments: dict[str, Any]) -> list:
    return ctx.recent_events(int(arguments.get("limit", 50)))


# --- Task actions: every one is a TaskEngine call -------------------------------------------


@register_tool("start_task", "Start a READY task, as its owner.", _schema({**_PROJECT, **_TASK, **_ROLE},
                                                                           ["project", "task", "role"]))
def _start_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return _act(ctx, arguments, lambda e, t, a: e.start(t, a).status.value)


@register_tool(
    "submit_task",
    "Hand in work as the task's owner. Artifacts become EXECUTED, never more; verification "
    "and approval are separate, later steps.",
    _schema({
        **_PROJECT, **_TASK, **_ROLE,
        "artifacts": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string"}, "title": {"type": "string"}, "location": {"type": "string"}},
            "required": ["kind", "title"]}},
        "notes": {"type": "string"},
        "outcome": {"type": "string", "description": "Required for decision tasks."},
    }, ["project", "task", "role", "artifacts"]),
)
def _submit_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    drafts = [{"kind": a["kind"], "title": a["title"], "location": a.get("location")} for a in arguments["artifacts"]]
    return _act(ctx, arguments, lambda e, t, a: e.submit(
        t, a, drafts, str(arguments.get("notes", "")), arguments.get("outcome")).status.value)


@register_tool(
    "record_evidence",
    "Attach evidence to a task. The engine decides whether it is substantiated; only "
    "substantiated evidence satisfies a requirement, and a claim never does.",
    _schema({
        **_PROJECT, **_TASK, **_ROLE,
        "description": {"type": "string"},
        "kind": {"type": "string", "enum": [k.value for k in EvidenceKind]},
        "reference": {"type": "string", "description": "Artifact or review ID (short or qualified)."},
    }, ["project", "task", "role", "description", "kind"]),
)
def _record_evidence(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    def act(e: TaskEngine, t: str, a: Actor):
        ref = arguments.get("reference")
        if ref and ":" not in ref:
            ref = _task_id(e, ref)
        ev = e.record_evidence(t, a, EvidenceKind(arguments["kind"]), str(arguments["description"]), reference=ref)
        return {"evidence": ev.id, "substantiated": ev.substantiated}

    return _act(ctx, arguments, act)


@register_tool(
    "review_task",
    "Independently review submitted work, as its reviewer.",
    _schema({**_PROJECT, **_TASK, **_ROLE,
             "verdict": {"type": "string", "enum": [v.value for v in Verdict]},
             "comments": {"type": "string"}}, ["project", "task", "role", "verdict"]),
)
def _review_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    verdict = Verdict(arguments["verdict"])
    return _act(ctx, arguments, lambda e, t, a: e.review(
        t, a, verdict, str(arguments.get("comments", ""))).review_state.value)


@register_tool(
    "approve_task",
    "Approve reviewed work, or approve a gate. Gates that require a human cannot be approved "
    "over MCP; a person approves them with the CLI.",
    _schema({**_PROJECT, **_TASK, **_ROLE, "note": {"type": "string"}}, ["project", "task", "role"]),
)
def _approve_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return _act(ctx, arguments, lambda e, t, a: e.approve(t, a, str(arguments.get("note", ""))).status.value)


@register_tool("complete_task", "Complete a task whose work is approved or needs no review.",
               _schema({**_PROJECT, **_TASK, **_ROLE}, ["project", "task", "role"]))
def _complete_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return _act(ctx, arguments, lambda e, t, a: e.complete(t, a).status.value)


@register_tool("block_task", "Mark a task blocked, with the reason, as its owner or a manager.",
               _schema({**_PROJECT, **_TASK, **_ROLE, "reason": {"type": "string"}},
                       ["project", "task", "role", "reason"]))
def _block_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return _act(ctx, arguments, lambda e, t, a: e.block(t, a, str(arguments["reason"])).status.value)


@register_tool(
    "escalate_task",
    "Raise an escalation on a task. It is routed up the organization by kind.",
    _schema({
        **_PROJECT, **_TASK, **_ROLE,
        "reason": {"type": "string"},
        "kind": {"type": "string", "enum": [k.value for k in EscalationKind]},
        "question": {"type": "string", "description": "The blocking question."},
        "options": {"type": "array", "items": {"type": "string"}, "description": "Recommended options."},
    }, ["project", "task", "role", "reason"]),
)
def _escalate_task(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    kind = EscalationKind(arguments.get("kind", EscalationKind.TECHNICAL.value))

    def act(e: TaskEngine, t: str, a: Actor):
        esc = e.escalate(t, a, kind, str(arguments["reason"]), blocking_question=str(arguments.get("question", "")),
                         recommended_options=tuple(arguments.get("options", ())))
        return {"escalation": esc.id, "routed_to": esc.target_role}

    return _act(ctx, arguments, act)


@register_tool(
    "resolve_escalation",
    "Resolve an open escalation, as its target or someone above it.",
    _schema({**_PROJECT, **_ROLE, "escalation": {"type": "string"}, "resolution": {"type": "string"}},
            ["project", "role", "escalation", "resolution"]),
)
def _resolve_escalation(ctx: McpContext, arguments: dict[str, Any]) -> dict:
    return _act(ctx, arguments, lambda e, t, a: e.resolve_escalation(
        str(arguments["escalation"]), a, str(arguments["resolution"])).state.value)


__all__ = ["McpContext", "ToolSpec", "call_tool", "list_tools", "register_tool", "unregister_tool"]
