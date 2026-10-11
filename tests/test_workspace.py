"""Milestone 8: Verification Workspace & MCP Platform.

Covers the milestone's guarantees, not just its features: the CLI and MCP
consume the same service layer, Investigation Sessions are immutable and
deterministic, the public API never exposes raw parser objects, no MCP tool
bypasses the Verification Intelligence Core, no engine knows the workspace
exists, and adding a new endpoint requires only a tool (the crown-jewel
architecture test at the bottom of this file).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import pydantic

from laws import imports

import veritriage.workspace.services as services_module
from veritriage.graph.model import ArtifactType
from veritriage.mcp import McpStdioServer, call_tool, list_tools, register_tool, unregister_tool
from veritriage.workspace import (
    SessionStore,
    WorkspaceServices,
    navigation,
    search_knowledge,
    search_playbooks,
)

# .../src/veritriage/workspace/services.py -> parents[2] is the src/ root.
SRC = Path(services_module.__file__).parents[2]

#: Core packages that must never know the workspace or MCP exist.
_CORE_PACKAGES = (
    "graph",
    "parsers",
    "rules",
    "reasoning",
    "knowledge",
    "waveform",
    "engineering",
    "project",
    "history",
    "signatures",
    "similarity",
    "storage",
    "analytics",
    "feedback",
    "models",
    "reports",
    "dashboard",
)


@pytest.fixture()
def services(tmp_path):
    return WorkspaceServices(session_root=tmp_path / "sessions", db=tmp_path / "reg.db")


@pytest.fixture()
def session(services, fixture_log):
    return services.investigate(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )


# --- Sessions ---------------------------------------------------------------


def test_session_identity_is_deterministic(services, fixture_log, session):
    again = services.investigate(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    assert again.session_id == session.session_id
    assert session.session_id.startswith("ses-")


def test_sessions_are_immutable(session):
    with pytest.raises(pydantic.ValidationError):
        session.session_id = "ses-tampered"
    with pytest.raises(pydantic.ValidationError):
        session.report = session.report


def test_session_persistence_roundtrip(services, session):
    services.save(session)
    loaded = services.load(session.session_id)
    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.report.classification == session.report.classification
    assert set(loaded.graph.nodes) == set(session.graph.nodes)
    # Re-saving an unchanged session is byte-identical.
    store = SessionStore(services._store.root)
    first = store.path_for(session.session_id).read_bytes()
    services.save(loaded)
    assert store.path_for(session.session_id).read_bytes() == first


def test_list_sessions_summarizes(services, session):
    services.save(session)
    summaries = services.list_sessions()
    assert len(summaries) == 1
    assert summaries[0].session_id == session.session_id
    assert summaries[0].classification == "assertion_failure"


def test_load_unknown_session_returns_none(services):
    assert services.load("ses-000000000000") is None


def test_investigate_can_record_history(services, fixture_log):
    first = services.investigate(
        [fixture_log("uvm_assertion.log")], record_history=True
    )
    assert first.report.history is not None
    again = services.investigate(
        [fixture_log("uvm_assertion.log")], record_history=True
    )
    assert again.report.history.seen_before


# --- Services ---------------------------------------------------------------


def test_summary_is_bounded_and_complete(services, session):
    summary = services.summary(session)
    assert summary.classification == "assertion_failure"
    assert summary.top_hypothesis_id == "hyp-rtl_bug"
    assert summary.matched_patterns == ["axi.valid-drop-before-ready"]
    assert summary.engineering_commits == 2
    assert summary.evidence_nodes == len(session.graph.nodes)


def test_evidence_filters(services, session):
    failing = services.evidence(session, failing_only=True)
    assert failing and all(n.is_failing for n in failing)
    engineering = services.evidence(session, artifact_type="engineering_change")
    assert engineering and all(
        n.artifact_type == ArtifactType.ENGINEERING_CHANGE for n in engineering
    )


def test_evidence_graph_view_is_bounded(services, session):
    view = services.evidence_graph_view(session, max_nodes=2)
    assert len(view["nodes"]) <= 2
    included = {n["id"] for n in view["nodes"]}
    assert all(e["source"] in included and e["target"] in included for e in view["edges"])


def test_similar_regressions_probe_is_read_only(services, fixture_log):
    recorded = services.investigate(
        [fixture_log("uvm_assertion.log")], record_history=True
    )
    probe = services.investigate(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    matches = services.similar_regressions(probe)
    assert matches, "expected the recorded regression to match"
    # Probing never wrote to the database.
    from veritriage.storage import RegressionStore

    with RegressionStore(services._db) as store:
        assert store.count() == 1
    assert recorded.report.history is not None


def test_compare_same_and_different(services, fixture_log, session):
    same = services.investigate(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    other = services.investigate([fixture_log("uvm_timeout.log")])
    identical = services.compare(session, same)
    assert identical.same_signature and identical.shared_failing_descriptions
    different = services.compare(session, other)
    assert not different.same_signature
    assert different.classification_b == "timeout"


def test_timeline_without_engineering_context(services, fixture_log):
    bare = services.investigate([fixture_log("uvm_assertion.log")])
    events = services.timeline(bare)
    assert events and any(e.phase == "simulation" for e in events)


# --- Navigation -------------------------------------------------------------


def test_every_navigation_getter_hits_and_misses(session):
    assert navigation.hypothesis(session, "hyp-rtl_bug").id == "hyp-rtl_bug"
    assert navigation.hypothesis(session, "hyp-nope") is None
    assert navigation.recommendation(session, 0) is not None
    assert navigation.recommendation(session, 999) is None
    pattern = navigation.knowledge_pattern(session, "axi.valid-drop-before-ready")
    assert pattern is not None and pattern.playbook is not None
    assert navigation.knowledge_pattern(session, "axi.nope") is None
    commit = navigation.engineering_commit(session, "a1b2c3d")
    assert commit is not None and commit.correlated_failures
    assert navigation.engineering_commit(session, "ffffff") is None
    assert navigation.timeline_event(session, 0) is not None
    assert navigation.timeline_event(session, 999) is None
    node_id = session.report.reasoning.hypotheses[0].evidence_ids[0]
    detail = navigation.evidence_node(session, node_id)
    assert detail is not None and detail.node.id == node_id
    assert navigation.evidence_node(session, "ev-nope") is None


def test_waveform_observation_navigation(services, fixture_log):
    wave = services.investigate(
        [fixture_log("uvm_assertion.log"), fixture_log("axi_handshake_stall.wave.json")]
    )
    observation_id = wave.report.waveform.observations[0].observation_id
    hit = navigation.waveform_observation(wave, observation_id)
    assert hit is not None and hit.observation_id == observation_id
    assert navigation.waveform_observation(wave, "wobs-nope") is None


# --- Search -----------------------------------------------------------------


def test_search_evidence_is_deterministic_and_cited(services, session):
    first = services.search(session, "assertion")
    second = services.search(session, "assertion")
    assert first == second and first
    assert all(hit.node_id in session.graph.nodes for hit in first)


def test_search_knowledge_finds_all_kinds():
    hits = search_knowledge("handshake")
    kinds = {hit.kind for hit in hits}
    assert "pattern" in kinds
    assert hits == search_knowledge("handshake")  # deterministic
    playbooks = search_playbooks("reset")
    assert playbooks and all(hit.kind == "playbook" for hit in playbooks)


# --- MCP --------------------------------------------------------------------


def test_tool_table_lists_the_v1_set():
    names = {spec.name for spec in list_tools()}
    assert names >= {
        "analyze_regression",
        "get_investigation_summary",
        "get_evidence_graph",
        "get_hypothesis",
        "find_similar_regressions",
        "search_knowledge",
        "search_playbooks",
        "list_matched_patterns",
        "get_waveform_observations",
        "get_engineering_context",
        "get_timeline",
        "search_evidence",
    }
    for spec in list_tools():
        assert spec.description and spec.input_schema.get("type") == "object"


def test_mcp_stdio_full_conversation(services, fixture_log):
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "analyze_regression",
                "arguments": {"paths": [str(fixture_log("uvm_assertion.log"))]},
            },
        },
    ]
    out = io.StringIO()
    server = McpStdioServer(
        services,
        in_stream=io.StringIO("\n".join(json.dumps(m) for m in lines) + "\n"),
        out_stream=out,
    )
    server.serve_forever()
    responses = [json.loads(line) for line in out.getvalue().splitlines()]
    assert len(responses) == 3  # the notification gets no response
    assert responses[0]["result"]["serverInfo"]["name"] == "veritriage"
    assert responses[1]["result"]["tools"]
    summary = json.loads(responses[2]["result"]["content"][0]["text"])
    assert summary["classification"] == "assertion_failure"

    # The analyzed session persisted: a follow-up call finds it by ID alone.
    follow = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_hypothesis",
                "arguments": {
                    "session_id": summary["session_id"],
                    "hypothesis_id": summary["top_hypothesis_id"],
                },
            },
        }
    )
    hypothesis = json.loads(follow["result"]["content"][0]["text"])
    assert hypothesis["id"] == summary["top_hypothesis_id"]
    assert hypothesis["evidence_ids"]


def test_mcp_errors_are_contained(services):
    server = McpStdioServer(services, in_stream=io.StringIO(), out_stream=io.StringIO())
    parse = server.handle_line("this is not json")
    assert parse["error"]["code"] == -32700
    missing = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "no/such"})
    assert missing["error"]["code"] == -32601
    unknown_tool = server.handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nope"}}
    )
    assert unknown_tool["result"]["isError"]
    bad_session = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_investigation_summary",
                "arguments": {"session_id": "ses-000000000000"},
            },
        }
    )
    assert bad_session["result"]["isError"]


# --- Architecture guards ----------------------------------------------------


def test_cli_and_mcp_share_services():
    # Both clients import the workspace; neither imports the pipeline or any
    # parser/provider module directly.
    cli_imports = imports(SRC / "veritriage" / "cli" / "main.py")
    assert any(m.startswith("veritriage.workspace") for m in cli_imports)
    assert not any(m.startswith("veritriage.pipeline") for m in cli_imports)
    for path in (SRC / "veritriage" / "mcp").rglob("*.py"):
        imported = imports(path)
        assert not any(m.startswith("veritriage.pipeline") for m in imported), path.name
        assert not any(m.startswith("veritriage.parsers") for m in imported), path.name
        assert not any(
            m.startswith("veritriage.engineering") for m in imported
        ), path.name
        if path.name != "__init__.py":
            assert any(m.startswith("veritriage.workspace") for m in imported), path.name


def test_public_api_never_exposes_raw_parser_objects():
    # A raw parser/adapter/provider object can only cross the API if it is
    # imported; AST import analysis ignores prose that merely names them.
    banned = ("ParseResult", "Parser", "WaveformAdapter", "ContextProvider")
    for name in ("services.py", "navigation.py", "search.py", "session.py", "persistence.py"):
        for imported in imports(SRC / "veritriage" / "workspace" / name):
            leaf = imported.rsplit(".", maxsplit=1)[-1]
            assert leaf not in banned, f"workspace/{name} imports {imported}"


def test_no_engine_knows_workspace():
    for package in _CORE_PACKAGES:
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "veritriage.workspace" not in text, f"{path} imports the workspace"
            assert "veritriage.mcp" not in text, f"{path} imports the MCP layer"
    # The pipeline itself stays workspace-free too: dependencies point outward.
    pipeline = (SRC / "veritriage" / "pipeline.py").read_text(encoding="utf-8")
    assert "veritriage.workspace" not in pipeline and "veritriage.mcp" not in pipeline


def test_workspace_never_depends_on_ai():
    banned = ("anthropic", "reasoning.ai", "AIReasoner")
    for path in (SRC / "veritriage" / "workspace").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_mcp_tools_route_through_services():
    # Every registered tool handler lives in a module whose only platform
    # imports are the workspace: none can reach the pipeline or parsers.
    import veritriage.mcp.tools as tools_module

    for spec in list_tools():
        assert spec.handler.__module__ == tools_module.__name__, spec.name


# --- The crown jewel: a new endpoint is a new tool and nothing else ----------


def test_new_endpoint_needs_only_a_tool(services, session):
    # A throwaway tool defined entirely in this test: it answers a question no
    # built-in tool answers (count failing evidence), through the same
    # dispatcher and services, with zero changes to reasoning or any other
    # core module.
    @register_tool(
        "count_failing_evidence",
        "Count error/fatal evidence nodes in one session.",
        {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    )
    def _count(svc: WorkspaceServices, arguments: dict):
        loaded = svc.load(str(arguments["session_id"]))
        return {"failing": len(svc.evidence(loaded, failing_only=True))}

    try:
        services.save(session)
        # Served through the transport too, not just the dispatcher.
        server = McpStdioServer(services, in_stream=io.StringIO(), out_stream=io.StringIO())
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "count_failing_evidence",
                    "arguments": {"session_id": session.session_id},
                },
            }
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        assert payload["failing"] == len(services.evidence(session, failing_only=True))
        assert payload["failing"] > 0
        # And directly via the dispatcher.
        direct = call_tool(
            services, "count_failing_evidence", {"session_id": session.session_id}
        )
        assert direct == payload
    finally:
        unregister_tool("count_failing_evidence")
