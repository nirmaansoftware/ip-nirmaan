"""Milestone 40: recording explicit engineering decisions from the CLI and over MCP.

``nirmaan decide`` and the MCP tool ``record_decision`` are one engine call
each: the authority matrix sets the level a decision kind and criticality
need, P2 refuses a decision whose evidence is missing or (when important)
unsubstantiated, and P12's ``human-decisions`` check refuses an AI agent a
decision the matrix marks human-only. A new decision may supersede an earlier
one; the earlier one is kept and reads as superseded.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import drive, tid

import nirmaan
from nirmaan.cli import app
from nirmaan.company import nirmaan_definition
from nirmaan.export import export_project
from nirmaan.mcp import McpContext, NirmaanMcpServer
from nirmaan.models import Criticality, DecisionKind
from nirmaan.org.organization import OrganizationBuilder
from nirmaan.orchestrator import Orchestrator
from nirmaan.records import decision_records
from nirmaan.work import ProjectStore

BRIDGE = "Create a 4-port AXI-to-NoC bridge."
DIRECTOR = "architecture.micro.director"
JUNIOR = "design.rtl.design.fsm.junior"


@pytest.fixture()
def saved(nirmaan_org, fixed_clock, tmp_path):
    """A planned project driven to its requirements gate, so it holds substantiated evidence; saved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)
    drive(engine, until=tid(engine, "requirements.gate"))
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    evidence = [e for e in engine.task(tid(engine, "requirements")).evidence
                if engine.state.evidence[e].substantiated]
    assert evidence
    return root, engine.state.project.id, evidence


def _cli(*args):
    return CliRunner().invoke(app, [str(a) for a in args])


def _decide(root, project, statement, *extra):
    return _cli("decide", project, statement, "--root", root, *extra)


def _state(root, project):
    return ProjectStore(root).load(project)


def _server(org, root, tmp_path):
    from nirmaan.integrations.veritriage import AutomationBridge
    from veritriage.workspace import WorkspaceServices

    bridge = AutomationBridge(WorkspaceServices(session_root=tmp_path / "sessions"))
    return NirmaanMcpServer(McpContext(org, ProjectStore(root), bridge.publish, bridge.recent))


def _call(server, name, **arguments):
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}})
    result = server.handle_line(line)["result"]
    text = result["content"][0]["text"]
    return (text if result["isError"] else json.loads(text)), result["isError"]


# --- CLI: decide, list, supersede ------------------------------------------------------------


def test_cli_decides_lists_and_supersedes_keeping_history(saved):
    root, project, evidence = saved
    first = _decide(root, project, "Use round-robin arbitration", "--as", DIRECTOR,
                    "--kind", "architecture_decision", "--criticality", "high",
                    "--subject", "Which arbitration scheme?", "--option", "round-robin",
                    "--option", "fixed-priority", "--evidence", evidence[0],
                    "--rationale", "Bounded wait for every requester.")
    assert first.exit_code == 0, first.output
    assert "dec-001" in first.output
    second = _decide(root, project, "Use weighted round-robin", "--as", DIRECTOR,
                     "--kind", "architecture_decision", "--criticality", "high",
                     "--subject", "Which arbitration scheme?", "--option", "round-robin",
                     "--option", "weighted round-robin", "--evidence", evidence[0], "--supersedes", "dec-001")
    assert second.exit_code == 0, second.output

    state = _state(root, project)
    assert set(state.decisions) == {"dec-001", "dec-002"}  # history kept: the first is not edited or removed
    assert state.decisions["dec-001"].statement == "Use round-robin arbitration"
    assert state.decisions["dec-002"].supersedes == "dec-001"
    assert state.decisions["dec-001"].options == ("round-robin", "fixed-priority")

    listed = _cli("decisions", project, "--root", root, "--json")
    assert listed.exit_code == 0, listed.output
    rows = {r["id"]: r for r in json.loads(listed.output) if r["source"] == "decision_record"}
    assert rows["dec-001"]["status"] == "superseded" and rows["dec-001"]["superseded_by"] == "dec-002"
    assert rows["dec-002"]["status"] == "recorded" and rows["dec-002"]["supersedes"] == "dec-001"
    assert rows["dec-001"]["question"] == "Which arbitration scheme?"
    assert rows["dec-001"]["alternatives"] == ["round-robin", "fixed-priority"]
    assert rows["dec-001"]["kind"] == "architecture_decision" and rows["dec-001"]["criticality"] == "high"
    text = _cli("decisions", project, "--root", root)
    assert "superseded by dec-002" in text.output and "supersedes dec-001" in text.output


def test_a_decision_about_a_task_reads_the_task_as_its_question(saved):
    root, project, evidence = saved
    result = _decide(root, project, "Split the requirements into two documents", "--as", DIRECTOR,
                     "--kind", "modify_artifact", "--criticality", "low", "--task", "requirements")
    assert result.exit_code == 0, result.output
    state = _state(root, project)
    assert state.decisions["dec-001"].task == f"{project}:requirements"
    [row] = [r for r in decision_records(state) if r.source == "decision_record"]
    assert row.question == state.tasks[f"{project}:requirements"].title


def test_a_superseded_decision_cannot_be_superseded_again_or_by_another_kind(saved):
    root, project, evidence = saved
    base = ("--as", DIRECTOR, "--criticality", "medium")
    assert _decide(root, project, "A", "--kind", "architecture_decision", *base).exit_code == 0
    other_kind = _decide(root, project, "B", "--kind", "create_task", "--supersedes", "dec-001", *base)
    assert other_kind.exit_code == 1 and "kind" in other_kind.output
    lower = _decide(root, project, "B", "--kind", "architecture_decision", "--supersedes", "dec-001",
                    "--as", DIRECTOR, "--criticality", "low")
    assert lower.exit_code == 1 and "criticality" in lower.output
    unknown = _decide(root, project, "B", "--kind", "architecture_decision", "--supersedes", "dec-404", *base)
    assert unknown.exit_code == 1 and "dec-404" in unknown.output
    assert _decide(root, project, "B", "--kind", "architecture_decision", "--supersedes", "dec-001",
                   *base).exit_code == 0
    again = _decide(root, project, "C", "--kind", "architecture_decision", "--supersedes", "dec-001", *base)
    assert again.exit_code == 1 and "dec-002" in again.output
    assert set(_state(root, project).decisions) == {"dec-001", "dec-002"}


# --- Refusals --------------------------------------------------------------------------------


def test_a_decision_without_substantiated_evidence_is_refused(saved):
    root, project, _ = saved
    before = len(_state(root, project).audit)
    none = _decide(root, project, "Use a crossbar", "--as", DIRECTOR, "--kind", "architecture_decision",
                   "--criticality", "high")
    assert none.exit_code == 1 and "P2" in none.output
    invented = _decide(root, project, "Use a crossbar", "--as", DIRECTOR, "--kind", "architecture_decision",
                       "--criticality", "low", "--evidence", "ev-never-recorded")
    assert invented.exit_code == 1 and "P2" in invented.output and "ev-never-recorded" in invented.output
    state = _state(root, project)
    assert not state.decisions and len(state.audit) == before


def test_insufficient_authority_is_refused(saved):
    root, project, evidence = saved
    result = _decide(root, project, "Use a crossbar", "--as", JUNIOR, "--kind", "architecture_decision",
                     "--criticality", "high", "--evidence", evidence[0])
    assert result.exit_code == 1 and "needs" in result.output
    assert not _state(root, project).decisions


def test_human_only_decisions_are_refused_to_agents_on_the_cli_too(saved, nirmaan_org):
    root, project, evidence = saved
    vp = next(r.id for r in nirmaan_org.roles.values() if r.level.value == "vp")
    refused = _decide(root, project, "Ship it", "--as", vp, "--kind", "release", "--criticality", "low",
                      "--evidence", evidence[0], "--agent")
    assert refused.exit_code == 1 and "P12" in refused.output
    assert _decide(root, project, "Ship it", "--as", vp, "--kind", "release", "--criticality", "low",
                   "--evidence", evidence[0]).exit_code == 0


# --- MCP ---------------------------------------------------------------------------------------


def test_mcp_records_agent_kinds_and_refuses_human_only_ones(saved, nirmaan_org, tmp_path):
    root, project, evidence = saved
    server = _server(nirmaan_org, root, tmp_path)
    ok, is_error = _call(server, "record_decision", project=project, role=DIRECTOR,
                         kind="architecture_decision", criticality="high", statement="Use a crossbar",
                         subject="Which interconnect?", options=["crossbar", "ring"], evidence=evidence,
                         rationale="Fewer hops.")
    assert not is_error, ok
    assert ok["result"]["decision"] == "dec-001" and ok["audit_entries_added"] == 1
    assert _state(root, project).decisions["dec-001"].options == ("crossbar", "ring")

    vp = next(r.id for r in nirmaan_org.roles.values() if r.level.value == "vp")
    head = nirmaan_org.head_of(nirmaan_org.root.id).id
    before = len(_state(root, project).audit)
    for role, kind, crit in ((vp, "waive_requirement", "low"), (vp, "release", "medium"),
                             (vp, "approve_gate", "low"), (head, "architecture_decision", "critical")):
        reason, is_error = _call(server, "record_decision", project=project, role=role, kind=kind,
                                 criticality=crit, statement="x", evidence=evidence)
        assert is_error and "P12" in reason and "person" in reason, (kind, reason)
    state = _state(root, project)
    assert set(state.decisions) == {"dec-001"} and len(state.audit) == before


def test_mcp_supersedes_and_lists(saved, nirmaan_org, tmp_path):
    root, project, evidence = saved
    server = _server(nirmaan_org, root, tmp_path)
    for statement, extra in (("Use a crossbar", {}), ("Use a mesh", {"supersedes": "dec-001"})):
        _, is_error = _call(server, "record_decision", project=project, role=DIRECTOR,
                            kind="architecture_decision", criticality="medium", statement=statement, **extra)
        assert not is_error
    listed, _ = _call(server, "decisions", project=project)
    rows = {r["id"]: r for r in listed if r["source"] == "decision_record"}
    assert rows["dec-001"]["superseded_by"] == "dec-002" and rows["dec-002"]["supersedes"] == "dec-001"


# --- Audit, views, and export -----------------------------------------------------------------


def test_each_decision_is_one_audit_entry_with_its_details(saved):
    root, project, evidence = saved
    before = len(_state(root, project).audit)
    _decide(root, project, "A", "--as", DIRECTOR, "--kind", "architecture_decision", "--criticality", "medium",
            "--option", "A", "--option", "B")
    _decide(root, project, "B", "--as", DIRECTOR, "--kind", "architecture_decision", "--criticality", "medium",
            "--supersedes", "dec-001")
    state = _state(root, project)
    entries = state.audit[before:]
    assert [e.action for e in entries] == ["decision.record", "decision.record"]
    assert entries[0].details["options"] == ["A", "B"] and entries[0].details["criticality"] == "medium"
    assert entries[1].details["supersedes"] == "dec-001" and entries[1].actor.endswith(DIRECTOR)


def test_decisions_appear_in_the_export(saved, nirmaan_org, tmp_path):
    root, project, evidence = saved
    _decide(root, project, "Use a crossbar", "--as", DIRECTOR, "--kind", "architecture_decision",
            "--criticality", "medium", "--option", "crossbar", "--option", "ring")
    _decide(root, project, "Use a ring", "--as", DIRECTOR, "--kind", "architecture_decision",
            "--criticality", "medium", "--supersedes", "dec-001")
    out = tmp_path / "export"
    export_project(nirmaan_org, _state(root, project), out)
    data = json.loads((out / "10_signoff/decisions.json").read_text())
    rows = {d["id"]: d for d in data["decisions"]}
    assert rows["dec-001"]["superseded_by"] == "dec-002" and rows["dec-001"]["alternatives"] == ["crossbar", "ring"]
    text = (out / "10_signoff/decisions.md").read_text()
    assert "Superseded by: `dec-002`" in text and "Supersedes: `dec-001`" in text


# --- Crown jewel and laws ----------------------------------------------------------------------


def test_making_a_decision_human_only_is_one_row_of_data(saved, tmp_path):
    """No code names a human-only kind: flipping one authority row refuses agents, over the wire."""
    root, project, evidence = saved
    definition = nirmaan_definition()
    rules = [r.model_copy(update={"human_required": True})
             if (r.decision, r.criticality) == (DecisionKind.CREATE_TASK, Criticality.LOW) else r
             for r in definition.authority]
    org = OrganizationBuilder(definition.model_copy(update={"authority": rules})).build()
    server = _server(org, root, tmp_path)
    listed = server.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
    assert "record_decision" in {t["name"] for t in listed["result"]["tools"]}
    reason, is_error = _call(server, "record_decision", project=project, role=DIRECTOR, kind="create_task",
                             criticality="low", statement="Add a lint task")
    assert is_error and "P12" in reason
    _, is_error = _call(server, "record_decision", project=project, role=DIRECTOR, kind="create_task",
                        criticality="medium", statement="Add a lint task")
    assert not is_error


def test_no_decision_kind_is_named_outside_the_company_data():
    src = Path(nirmaan.__file__).parent
    kinds = {k.value for k in DecisionKind}
    for rel in ("work/policy.py", "mcp/tools.py", "records.py"):  # the engine names only its own actions
        for node in ast.walk(ast.parse((src / rel).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in kinds, (rel, node.value)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in (
                    "DecisionKind", "D"):
                pytest.fail(f"{rel} names DecisionKind.{node.attr}")


def test_the_import_laws_hold():
    src = Path(nirmaan.__file__).parent
    for rel in ("mcp/tools.py", "records.py", "work/policy.py", "work/engine.py", "cli.py"):
        tree = ast.parse((src / rel).read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(m.split(".")[0] == "veritriage" for m in imported), rel
    veritriage = Path(nirmaan.__file__).parent.parent / "veritriage"
    for path in veritriage.rglob("*.py"):
        assert not re.search(r"^\s*(from|import)\s+nirmaan\b", path.read_text(encoding="utf-8"), re.M), path
