"""Milestone 22: IP Nirmaan over MCP, and organizational events on the M18 bus.

* A separate tool table: plan a project, then ask why a task is blocked, over
  the stdio transport, in-process.
* Task actions go through the engine (state machine, authority, constitution,
  audit); a refusal saves nothing, and the MCP caller can never act as a human.
* Task completion, gate approval, and escalation are published to the M18 bus,
  derived from the audit trail, and a VeriTriage automation rule reacts.
* VeriTriage learns one generic EventKind and nothing about Nirmaan.
* Crown jewel: a new MCP tool needs only registration.
"""

from __future__ import annotations

import io
import json

import pytest

from nirmaan.events import TOPICS, org_events
from nirmaan.integrations.veritriage import AutomationBridge
from nirmaan.mcp import McpContext, NirmaanMcpServer, list_tools, register_tool
from nirmaan.models import EscalationKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.registry import Registries
from nirmaan.work import ProjectStore

from nirmaan_helpers import drive, human, tid


@pytest.fixture()
def bridge(tmp_path):
    from veritriage.workspace import WorkspaceServices

    return AutomationBridge(WorkspaceServices(session_root=tmp_path / "sessions"))


@pytest.fixture()
def server(nirmaan_org, tmp_path, bridge):
    ctx = McpContext(nirmaan_org, ProjectStore(tmp_path / "nirmaan"), bridge.publish, bridge.recent)
    return NirmaanMcpServer(ctx)


def _call(server, name, **arguments):
    """One tools/call over the wire; returns (payload, is_error)."""
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}})
    result = server.handle_line(line)["result"]
    text = result["content"][0]["text"]
    return (text if result["isError"] else json.loads(text)), result["isError"]


def _ok(server, name, **arguments):
    payload, is_error = _call(server, name, **arguments)
    assert not is_error, payload
    return payload


def _plan(server, requirement="Create a 4-port AXI-to-NoC bridge.", **extra):
    return _ok(server, "plan_project", requirement=requirement, **extra)


def _task(plan, stage):
    return next(t for t in plan["tasks"] if t["id"] == f"{plan['project']}:{stage}")


# --- The tool table and the transport --------------------------------------------------------


def test_plan_then_ask_why_over_stdio(server):
    """The roadmap's done-when: plan a project and ask why a task is blocked, over MCP."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "plan_project", "arguments": {"requirement": "Create a 4-port AXI-to-NoC bridge."}}},
    ]
    out = io.StringIO()
    NirmaanMcpServer(server._ctx, io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n"), out).serve_forever()
    responses = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r["id"] for r in responses] == [1, 2, 3]  # the notification got no response
    assert responses[0]["result"]["serverInfo"]["name"] == "ip-nirmaan"
    names = {t["name"] for t in responses[1]["result"]["tools"]}
    assert {"plan_project", "project_status", "why_blocked", "start_task", "approve_task"} <= names
    plan = json.loads(responses[2]["result"]["content"][0]["text"])
    assert "GATE Gate: Architecture approval" in "\n".join(plan["plan"])

    why = _ok(server, "why_blocked", project=plan["project"], task="microarchitecture")
    assert why["blocked"] and "IP architecture" in "\n".join(why["explanation"])
    assert why["chain"]["upstream"]
    status = _ok(server, "project_status", project=plan["project"])
    assert status["project"] == plan["project"] and status["gates"]
    assert _ok(server, "list_projects")[0]["project"] == plan["project"]
    assert _ok(server, "audit_trail", project=plan["project"])["chain_problems"] == []


def test_unknown_tools_and_projects_are_tool_errors(server):
    message, is_error = _call(server, "no_such_tool")
    assert is_error and "Unknown tool" in message
    message, is_error = _call(server, "project_status", project="prj-nope")
    assert is_error and "Unknown project" in message
    assert server.handle_line("not json")["error"]["code"] == -32700
    assert server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 9, "method": "nope"}))["error"]["code"] == -32601


def test_the_two_tool_tables_are_separate():
    """VeriTriage's M8 table learns nothing about Nirmaan, and the reverse."""
    from veritriage.mcp import list_tools as veritriage_tools

    ours = {t.name for t in list_tools()}
    theirs = {t.name for t in veritriage_tools()}
    assert ours and theirs and not ours & theirs


# --- Actions go through the engine ------------------------------------------------------------


def test_actions_move_work_through_the_engine(server):
    plan = _plan(server)
    req = _task(plan, "requirements")
    project = plan["project"]
    assert _ok(server, "start_task", project=project, task="requirements", role=req["owner"])["result"] == "in_progress"
    submitted = _ok(server, "submit_task", project=project, task="requirements", role=req["owner"],
                    artifacts=[{"kind": "requirements_spec", "title": "Bridge requirements"}])
    assert submitted["result"] == "in_review" and submitted["audit_entries_added"] >= 1
    assert _ok(server, "review_task", project=project, task="requirements", role=req["reviewer"],
               verdict="approve", comments="complete")["result"] == "passed"
    approved = _ok(server, "approve_task", project=project, task="requirements", role=req["approver"])
    assert approved["task"]["status"] == "completed"
    audit = _ok(server, "audit_trail", project=project, tail=50)
    assert audit["chain_problems"] == []
    actors = {e["actor"] for e in audit["tail"] if e["action"] in ("task.start", "task.review", "task.approve")}
    assert all("mcp" in a for a in actors), actors


def test_refused_actions_change_nothing(server, tmp_path):
    plan = _plan(server)
    project = plan["project"]
    before = _ok(server, "audit_trail", project=project)["entries"]
    message, is_error = _call(server, "start_task", project=project, task="requirements",
                              role="product.management.roadmap.junior")
    assert is_error and "only the owner" in message
    message, is_error = _call(server, "start_task", project=project, task="microarchitecture",
                              role=_task(plan, "microarchitecture")["owner"])
    assert is_error and "not ready" in message
    assert _ok(server, "audit_trail", project=project)["entries"] == before


def test_mcp_cannot_act_as_a_human(server, nirmaan_org, fixed_clock):
    """A human-required gate is refused over MCP by the constitution, not by this layer."""
    store = server._ctx.store
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-port AXI-to-NoC bridge.")
    gate = tid(engine, "microarchitecture.gate")
    drive(engine, until=gate)
    store.save(engine.state)
    owner = engine.task(gate).owner
    message, is_error = _call(server, "approve_task", project=engine.state.project.id, task=gate, role=owner)
    assert is_error and "requires a human approver" in message
    assert store.load(engine.state.project.id).tasks[gate].status is TaskStatus.READY
    arguments = {name for t in list_tools() for name in t.input_schema.get("properties", {})}
    assert not arguments & {"agent", "actor_kind", "kind_of_actor", "as_human", "human"}


# --- Organizational events --------------------------------------------------------------------


def test_events_are_derived_from_the_audit_trail(nirmaan_org, fixed_clock, bridge):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-port AXI-to-NoC bridge.")
    before = len(engine.state.audit)
    drive(engine, until=tid(engine, "interface-spec.axi"))
    engine.escalate(tid(engine, "interface-spec.axi"), human(engine.task(tid(engine, "interface-spec.axi")).owner),
                    EscalationKind.TECHNICAL, "spec ambiguity")
    events = org_events(engine.state, since=before)
    topics = [e.topic for e in events]
    assert {"task.completed", "gate.approved", "escalation.raised"} <= set(topics)
    by_seq = {e.sequence: e for e in engine.state.audit}
    for event in events:  # every event is substantiated by the audit entry that caused it
        assert by_seq[event.audit_sequence].hash == event.audit_hash
        assert TOPICS[by_seq[event.audit_sequence].action] == event.topic
    assert org_events(engine.state, since=len(engine.state.audit)) == []

    reactions = bridge.publish(events)
    assert [r["topic"] for r in reactions] == topics
    recorded = bridge.recent()
    assert len(recorded) == len(events)
    assert all(e["kind"] == "external" and e["source"] == "nirmaan" for e in recorded)


def test_task_completion_and_gate_approval_over_mcp_publish_events(server):
    plan = _plan(server)
    project, req = plan["project"], _task(plan, "requirements")
    _ok(server, "start_task", project=project, task="requirements", role=req["owner"])
    _ok(server, "submit_task", project=project, task="requirements", role=req["owner"],
        artifacts=[{"kind": "requirements_spec", "title": "Bridge requirements"}])
    _ok(server, "review_task", project=project, task="requirements", role=req["reviewer"], verdict="approve")
    approved = _ok(server, "approve_task", project=project, task="requirements", role=req["approver"])
    assert [e["topic"] for e in approved["events"]] == ["task.completed"]
    assert approved["events"][0]["subject"] == f"{project}:requirements"

    gate = _task(plan, "requirements.gate")
    assert _ok(server, "show_plan", project=project)["plan"]
    passed = _ok(server, "approve_task", project=project, task="requirements.gate", role=gate["owner"])
    assert passed["task"]["status"] == "completed"
    assert [e["topic"] for e in passed["events"]] == ["gate.approved"]
    recent = _ok(server, "organization_events")
    assert [e["payload"]["topic"] for e in recent] == ["task.completed", "gate.approved"]


def test_escalation_over_mcp_reaches_the_bus_and_the_shipped_rule_reacts(server):
    plan = _plan(server)
    project, req = plan["project"], _task(plan, "requirements")
    raised = _ok(server, "escalate_task", project=project, task="requirements", role=req["owner"],
                 reason="the NoC flit width is unspecified", question="Which flit width?")
    esc = raised["result"]["escalation"]
    assert raised["task"]["status"] == "escalated"
    [event] = raised["events"]
    assert event["topic"] == "escalation.raised" and event["rules_fired"] == ["nirmaan-escalation-raised"]
    assert event["actions"][0]["action"] == "notify" and event["actions"][0]["executed"]
    why = _ok(server, "why_blocked", project=project, task="requirements")
    assert esc in "\n".join(why["explanation"])
    resolved = _ok(server, "resolve_escalation", project=project, role=raised["result"]["routed_to"],
                   escalation=esc, resolution="128-bit flits")
    assert resolved["result"] == "resolved" and resolved["events"] == []


def test_a_veritriage_rule_reacts_to_an_organizational_event(server):
    """A rule registered on VeriTriage's own registry, as plain data, fires on a Nirmaan event."""
    from veritriage.automation import register_rule, unregister_rule
    from veritriage.models import ActionKind, AutomationRule

    register_rule(AutomationRule(rule_id="test-summarize-on-completion", description="test",
                                 when="nirmaan.task_completed", then=(ActionKind.SUMMARIZE_CHANGES,)))
    try:
        plan = _plan(server)
        project, req = plan["project"], _task(plan, "requirements")
        _ok(server, "start_task", project=project, task="requirements", role=req["owner"])
        _ok(server, "submit_task", project=project, task="requirements", role=req["owner"],
            artifacts=[{"kind": "requirements_spec", "title": "Bridge requirements"}])
        _ok(server, "review_task", project=project, task="requirements", role=req["reviewer"], verdict="approve")
        [event] = _ok(server, "approve_task", project=project, task="requirements", role=req["approver"])["events"]
        assert event["rules_fired"] == ["test-summarize-on-completion"]
        [action] = event["actions"]
        # Decide, never execute beyond the closed vocabulary: the workspace declines honestly.
        assert action["action"] == "summarize_changes" and not action["executed"] and action["skipped_reason"]
    finally:
        unregister_rule("test-summarize-on-completion")


def test_external_events_do_not_fire_verification_rules(bridge):
    """EXTERNAL is inert for VeriTriage's own triggers: only registered topic triggers match."""
    from veritriage.automation import RuleEngine, available_triggers
    from veritriage.models import EventKind

    event = bridge.services.events.publish(EventKind.EXTERNAL, {"topic": "task.completed"}, source="ci")
    fired = [o.rule_id for o in RuleEngine().evaluate(event) if o.matched]
    assert fired == []  # wrong source: even Nirmaan's triggers decline
    builtin = [t for t_id, t in available_triggers().items() if not t_id.startswith("nirmaan.")]
    assert all(t.kind is not EventKind.EXTERNAL for t in builtin)


# --- Crown jewel ------------------------------------------------------------------------------


def test_a_new_mcp_tool_needs_only_registration(server):
    """A new question over MCP is one registration: no transport, context, or engine change.

    Registered in a scope (M49), so it is gone when the scope ends, with no unregister.
    """

    with Registries.scoped():

        @register_tool("open_escalation_count", "How many escalations are open in a project.",
                       {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]})
        def _count(ctx, arguments):
            state = ctx.store.load(arguments["project"])
            return {"open": sum(1 for e in state.escalations.values() if e.state.value == "open")}

        plan = _plan(server)
        req = _task(plan, "requirements")
        _ok(server, "escalate_task", project=plan["project"], task="requirements", role=req["owner"], reason="why")
        listed = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
        assert "open_escalation_count" in {t["name"] for t in listed["result"]["tools"]}
        assert _ok(server, "open_escalation_count", project=plan["project"]) == {"open": 1}
        with pytest.raises(ValueError):
            register_tool("open_escalation_count", "dup", {})(lambda c, a: None)
    assert "open_escalation_count" not in {t.name for t in list_tools()}


def test_the_cli_exposes_the_server():
    from typer.testing import CliRunner

    from nirmaan.cli import app

    result = CliRunner().invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0 and "MCP" in result.output
