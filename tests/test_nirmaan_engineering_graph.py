"""Milestone 24: the cross-domain engineering graph (roadmap Stage 5).

Artifacts are linked to VeriTriage Design Graph nodes by parsing their real,
digest-checked bytes through the bridge; requirements are linked to the
verification items recorded as proving them; and one call answers "which
requirements are not yet backed by passing verification evidence?".

Most tests drive the AXI4-Lite RTL seat with fake lint and simulation
executables that the test writes (real brokered runs of real processes, just
not Verilator or Icarus), so they need no EDA tools. The Stage 5 demo runs the
real tools and skips without them (or fails when CI names them in
NIRMAAN_REQUIRE_EDA). No test calls a model API.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid
from laws import needs

from nirmaan import engineering
from nirmaan.company.traceability import ItemKind, LinkKind
from nirmaan.export import export_project, folders
from nirmaan.integrations.eda import Backend, register_backend, unregister_backend
from nirmaan.integrations.eda_parsers import EdaResult
from nirmaan.models import EvidenceKind, ExportSection, MemoryScope, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolBroker, review_task, run_task
from nirmaan.work import ProjectStore
from nirmaan.work.engine import AuthorityError, WorkError

AXI = Path(__file__).parent / "fixtures" / "rtl" / "axi4_lite"
AXI_BLOCK = "Create an AXI4-Lite register block."
RTL_FILE = "axi4_lite_regs.v"
TB_FILE = "axi4_lite_regs_tb.v"


def token(art_id: str) -> str:
    return "[artifact:" + "".join(c if c.isalnum() or c in "._-" else "." for c in art_id) + "]"


def answer(files: list[tuple[str, str, str, str]], cite: str) -> str:
    """A scripted RTL-seat answer: (path, kind, entry, content) per file."""
    meta = [{"path": p, "kind": k, "title": p, "summary": f"{p}, from {cite}.", "entry": e}
            for p, k, e, _ in files]
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                       "escalation": None}, indent=1)
    return head + "\n" + "".join(f"=== FILE: {p} ===\n{c}=== END FILE ===\n" for p, _, _, c in files)


def axi_files(rtl: str | None = None, tb: str | None = None) -> list[tuple[str, str, str, str]]:
    return [(RTL_FILE, "rtl_source", "axi4_lite_regs", rtl or (AXI / RTL_FILE).read_text()),
            (TB_FILE, "testbench", "axi4_lite_regs_tb", tb or (AXI / TB_FILE).read_text())]


@pytest.fixture()
def fake_eda(tmp_path, monkeypatch):
    """Lint and simulation backends whose executables this test writes; the real ones are off PATH.

    ``fakesim`` passes unless FAKESIM=fail is set when it runs: a real process, a real exit code.
    """
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    scripts = {
        "fakelint": '#!/bin/sh\necho "fakelint $*"\necho "fakelint: clean"\n',
        "fakesim": ('#!/bin/sh\necho "fakesim $*"\n'
                    'if [ "$FAKESIM" = fail ]; then echo "fakesim: FAIL"; exit 1; fi\necho "fakesim: PASS"\n'),
        "fakesynth": '#!/bin/sh\necho "fakesynth $*"\n',
    }
    for name, body in scripts.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)

    def parse(marker: str):
        def _parse(run) -> EdaResult:
            ok = run.returncode == 0 and marker in run.log
            return EdaResult(ok, marker if ok else run.log.strip().splitlines()[-1])
        return _parse

    register_backend(Backend("fakelint", "lint.run", ("fakelint",), lambda j: [["fakelint", *j.sources]],
                             parse("fakelint: clean")))
    register_backend(Backend("fakesim", "simulator.run", ("fakesim",), lambda j: [["fakesim", *j.sources]],
                             parse("fakesim: PASS"), ("sources", "top")))
    # M26: the RTL stage also synthesizes before review, with a latch count to check.
    register_backend(Backend("fakesynth", "synth.run", ("fakesynth",), lambda j: [["fakesynth", *j.sources]],
                             lambda run: EdaResult(run.returncode == 0, "fakesynth: done", (), {"latches": 0}),
                             ("sources", "top")))
    # Only the fakes: on CI the real tools share /usr/bin with sh, and the scripts need no PATH (#!/bin/sh).
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("FAKESIM", raising=False)
    yield bin_dir
    unregister_backend("lint.run", "fakelint")
    unregister_backend("simulator.run", "fakesim")
    unregister_backend("synth.run", "fakesynth")


def run_rtl_seat(engine, tmp_path: Path, files) -> str:
    """Drive to the RTL seat, answer with ``files``, pass the before-review gate, and review it."""
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    assert engine.task(rtl).status is TaskStatus.READY
    engine.remember(MemoryScope.TASK, rtl, "input.workspace", str(tmp_path / "work"), human(engine.task(rtl).owner))
    micro = engine.task(tid(engine, "microarchitecture")).artifacts[0]
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(files, token(micro))])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    return rtl


@pytest.fixture()
def axi(nirmaan_org, fixed_clock, fake_eda, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = run_rtl_seat(engine, tmp_path, axi_files())
    return engine, rtl


def art_of(engine, task_id: str, kind: str):
    return next(engine.state.artifacts[a] for a in engine.task(task_id).artifacts
                if engine.state.artifacts[a].kind == kind)


def spec_id(engine) -> str:
    return engine.task(tid(engine, "interface-spec")).artifacts[0]


def spec_author(engine):
    return human(engine.task(tid(engine, "interface-spec")).owner)


def rtl_owner(engine, rtl: str):
    return human(engine.task(rtl).owner)


def holder(engine, tool: str) -> str:
    authority = AuthorityService(engine.org)
    return next(r for r in engine.org.roles if authority.may_use_tool(r, tool)[0])


def simulate(engine, rtl: str, tmp_path: Path, name: str):
    tb, src = art_of(engine, rtl, "testbench"), art_of(engine, rtl, "rtl_source")
    run, _ = ToolBroker(engine).invoke(agent(holder(engine, "simulator.run")), "simulator.run",
                                       {"sources": f"{src.location},{tb.location}", "top": "axi4_lite_regs_tb",
                                        "workdir": str(tmp_path / name)}, rtl)
    return run


# --- VeriTriage: the RTL provider is the parser ---------------------------------------------


def test_the_rtl_provider_reads_modules_port_groups_and_instances():
    from veritriage.design import DesignRelation, NodeKind, build_design_graph, make_node_id
    from veritriage.project import build_project_model

    model = build_project_model(AXI / RTL_FILE)
    assert [m.name for m in model.dut.modules] == ["axi4_lite_regs"]
    (bus,) = model.dut.interfaces
    assert bus.name == "axi4_lite_regs.s_axil" and bus.module == "axi4_lite_regs"
    assert len(bus.signals) == 17 and "s_axil_wstrb" in bus.signals and "aclk" not in bus.signals

    tb = build_project_model(AXI / TB_FILE)
    modules = {m.name: m for m in tb.dut.modules}
    assert modules["axi4_lite_regs"].parent == "axi4_lite_regs_tb"
    assert modules["axi4_lite_regs"].source_file is None  # instantiated here, defined elsewhere
    assert [i.name for i in tb.dut.interfaces] == ["axi4_lite_regs.s_axil"]  # from the named connections
    graph = build_design_graph(tb)
    dut, iface = make_node_id(NodeKind.MODULE, "axi4_lite_regs"), make_node_id(NodeKind.INTERFACE, bus.name)
    assert graph.targets(make_node_id(NodeKind.MODULE, "axi4_lite_regs_tb"), DesignRelation.INSTANTIATES)[0].id == dut
    assert [n.id for n in graph.sources(dut, DesignRelation.CONNECTS)] == [iface]


def test_task_calls_keywords_and_strings_are_not_instances(tmp_path):
    from veritriage.project import build_project_model

    source = tmp_path / "noise.v"
    source.write_text('module top;\n  // child fake (x);\n  wire w;\n  initial begin\n'
                      '    check("child c (", 1);\n    if (w) $display("x");\n  end\n'
                      '  child #(.W(2)) u_child (.a_x(w), .a_y(w), .a_z(w));\nendmodule\n')
    model = build_project_model(source)
    assert {m.name: m.parent for m in model.dut.modules} == {"top": None, "child": "top"}
    assert [i.name for i in model.dut.interfaces] == ["child.a"]


# --- Links: parsed from the real bytes, never asserted -----------------------------------


def test_links_come_from_the_real_parse(axi):
    engine, rtl = axi
    links = engineering.artifact_links(engine.state)
    assert links.refused == []
    src, tb = art_of(engine, rtl, "rtl_source"), art_of(engine, rtl, "testbench")
    got = {(l.artifact, l.kind, l.node_kind, l.node_name) for l in links.links}
    assert got == {
        (src.id, "defines", "module", "axi4_lite_regs"),
        (tb.id, "exercises", "module", "axi4_lite_regs"),
        (tb.id, "exercises", "interface", "axi4_lite_regs.s_axil"),
    }
    by = {(l.artifact, l.node_name): l for l in links.links}
    assert by[src.id, "axi4_lite_regs"].node == by[tb.id, "axi4_lite_regs"].node  # one Design Graph node
    assert by[src.id, "axi4_lite_regs"].digest == src.digest
    assert "instantiates" in by[tb.id, "axi4_lite_regs"].rationale


def test_a_link_follows_the_file_not_the_title(nirmaan_org, fixed_clock, fake_eda, tmp_path):
    """The seat calls its files axi4_lite_regs.*, but the bytes define reg_bank: the link says reg_bank."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    renamed = [(p, k, e, c.replace("axi4_lite_regs", "reg_bank").replace("reg_bank_tb", "axi4_lite_regs_tb"))
               for p, k, e, c in axi_files()]
    rtl = run_rtl_seat(engine, tmp_path, renamed)
    names = {(l.kind, l.node_name) for l in engineering.artifact_links(engine.state).links}
    assert names == {("defines", "reg_bank"), ("exercises", "reg_bank"), ("exercises", "reg_bank.s_axil")}
    assert art_of(engine, rtl, "rtl_source").title == RTL_FILE


def test_a_tampered_file_is_refused(axi):
    engine, rtl = axi
    tb = art_of(engine, rtl, "testbench")
    Path(tb.location).write_text(Path(tb.location).read_text() + "// edited after it was recorded\n")
    links = engineering.artifact_links(engine.state)
    (refused,) = links.refused
    assert refused.artifact == tb.id and "does not match its recorded digest" in refused.reason
    assert tb.digest in refused.reason
    assert {l.artifact for l in links.links} == {art_of(engine, rtl, "rtl_source").id}

    engine.record_spec_requirement(spec_author(engine), "AXIL-RESET", "Every register resets to zero.", spec_id(engine))
    engine.record_verification_item(rtl_owner(engine, rtl), "tb-reset", "test", "axi4_lite_regs_tb", tb.id,
                                    ("AXIL-RESET",))
    (gap,) = engineering.unbacked_requirements(engine.state)
    assert "does not match its recorded digest" in gap.items[0].reason


def test_a_file_that_is_gone_or_has_no_digest_is_refused(axi):
    engine, rtl = axi
    Path(art_of(engine, rtl, "rtl_source").location).unlink()
    (refused,) = engineering.artifact_links(engine.state).refused
    assert "no longer exists" in refused.reason


# --- Requirement-to-item traceability, recorded through the engine -------------------------


def test_traceability_is_recorded_with_provenance_and_audited(axi):
    engine, rtl = axi
    tb = art_of(engine, rtl, "testbench")
    req = engine.record_spec_requirement(spec_author(engine), "AXIL-SLVERR", "Unmapped addresses get SLVERR.",
                                         spec_id(engine), section="5")
    item = engine.record_verification_item(rtl_owner(engine, rtl), "tb-slverr", "test", "unmapped write SLVERR",
                                           tb.id, ("AXIL-SLVERR",), rationale="the check names it")
    assert req.recorded_by == spec_author(engine).label and req.source == spec_id(engine)
    assert item.recorded_by == rtl_owner(engine, rtl).label and item.proves == ("AXIL-SLVERR",)
    assert [e.action for e in engine.state.audit[-2:]] == ["trace.requirement", "trace.item"]
    assert engine.state.spec_requirements["AXIL-SLVERR"] == req
    assert engine.state.verification_items["tb-slverr"] == item


def test_traceability_refuses_what_it_cannot_stand_behind(axi):
    engine, rtl = axi
    tb = art_of(engine, rtl, "testbench")
    author = spec_author(engine)
    with pytest.raises(WorkError, match="unknown artifact"):
        engine.record_spec_requirement(author, "R1", "text", "nope#a1")
    engine.record_spec_requirement(author, "R1", "text", spec_id(engine))
    with pytest.raises(WorkError, match="already recorded"):
        engine.record_spec_requirement(author, "R1", "again", spec_id(engine))
    with pytest.raises(WorkError, match="unknown requirement"):
        engine.record_verification_item(rtl_owner(engine, rtl), "i1", "test", "x", tb.id, ("R9",))
    with pytest.raises(WorkError, match="no recorded file"):  # the spec, as driven here, is not a file
        engine.record_verification_item(author, "i1", "test", "x", spec_id(engine), ("R1",))
    stranger = next(r for r in engine.org.roles
                    if r not in (engine.task(rtl).owner, engine.task(rtl).reviewer)
                    and r not in {x.id for x in engine.org.line_chain(engine.task(rtl).owner)})
    with pytest.raises(AuthorityError):
        engine.record_verification_item(human(stranger), "i1", "test", "x", tb.id, ("R1",))


# --- The gap query ------------------------------------------------------------------------


def record_plan(engine, rtl: str) -> None:
    tb, src = art_of(engine, rtl, "testbench"), art_of(engine, rtl, "rtl_source")
    author, owner = spec_author(engine), rtl_owner(engine, rtl)
    for rid, text in (("AXIL-SLVERR", "Unmapped addresses get SLVERR."),
                      ("AXIL-SYNTH", "Synthesizes with Yosys, with no latches."),
                      ("AXIL-B2B", "Back-to-back transactions with no idle cycle.")):
        engine.record_spec_requirement(author, rid, text, spec_id(engine))
    engine.record_verification_item(owner, "tb-slverr", "test", "unmapped write SLVERR", tb.id, ("AXIL-SLVERR",))
    engine.record_verification_item(owner, "tb-b2b", "test", "back-to-back read", tb.id, ("AXIL-B2B",))
    engine.record_verification_item(owner, "cov-b2b", "coverage_point", "back-to-back", tb.id, ("AXIL-B2B",))
    del src


def test_the_gap_query_counts_only_passing_substantiated_runs(axi, tmp_path):
    engine, rtl = axi
    record_plan(engine, rtl)
    coverage = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert coverage["AXIL-SLVERR"].backed  # the seat's own passing, cited simulation of this very file
    assert coverage["AXIL-SLVERR"].items[0].status == "passed"
    assert [r.requirement for r in engineering.unbacked_requirements(engine.state)] == ["AXIL-B2B", "AXIL-SYNTH"]
    assert "no verification item" in coverage["AXIL-SYNTH"].reasons[0]
    cov = next(i for i in coverage["AXIL-B2B"].items if i.item == "cov-b2b")
    assert cov.status == "not_run" and "coverage.read" in cov.reason

    # A passing run that no substantiated evidence cites does not count, even as the latest run.
    run = simulate(engine, rtl, tmp_path, "uncited")
    assert run.succeeded
    slverr = engineering.requirement_coverage(engine.state)[1]
    assert slverr.requirement == "AXIL-SLVERR" and not slverr.backed
    assert "not cited by substantiated tool-run evidence" in slverr.items[0].reason

    # Claims and attestations never stand in for the run.
    owner = agent(engine.task(rtl).owner)
    engine.record_evidence(rtl, owner, EvidenceKind.CLAIM, "I am sure SLVERR works")
    engine.record_evidence(rtl, human(engine.task(rtl).owner), EvidenceKind.HUMAN_ATTESTATION, "attested SLVERR")
    slverr = next(r for r in engineering.unbacked_requirements(engine.state) if r.requirement == "AXIL-SLVERR")
    assert "claim" in slverr.items[0].reason and "attestation" in slverr.items[0].reason

    engine.record_evidence(rtl, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
    assert "AXIL-SLVERR" not in {r.requirement for r in engineering.unbacked_requirements(engine.state)}


def test_a_failed_run_leaves_a_gap(axi, tmp_path, monkeypatch):
    engine, rtl = axi
    record_plan(engine, rtl)
    monkeypatch.setenv("FAKESIM", "fail")
    run = simulate(engine, rtl, tmp_path, "failing")
    assert not run.succeeded
    ev = engine.record_evidence(rtl, agent(engine.task(rtl).owner), EvidenceKind.TOOL_RUN, run.summary,
                                tool_run=run.id)
    assert not ev.substantiated
    slverr = next(r for r in engineering.unbacked_requirements(engine.state) if r.requirement == "AXIL-SLVERR")
    assert slverr.items[0].status == "failed" and "fakesim: FAIL" in slverr.items[0].reason
    assert slverr.items[0].run == run.id


def test_an_item_its_file_does_not_mention_is_a_gap(axi):
    engine, rtl = axi
    engine.record_spec_requirement(spec_author(engine), "R1", "text", spec_id(engine))
    engine.record_verification_item(rtl_owner(engine, rtl), "ghost", "test", "a check nobody wrote",
                                    art_of(engine, rtl, "testbench").id, ("R1",))
    (gap,) = engineering.unbacked_requirements(engine.state)
    assert "does not occur in" in gap.items[0].reason


def test_no_model_api_is_called(axi, tmp_path, monkeypatch):
    engine, rtl = axi
    record_plan(engine, rtl)

    def refuse(*a, **k):
        raise AssertionError("a model was called")

    trap = types.ModuleType("anthropic")
    trap.__getattr__ = refuse  # any use of the SDK fails the test
    monkeypatch.setitem(sys.modules, "anthropic", trap)
    import nirmaan.integrations.veritriage as bridge

    monkeypatch.setattr(bridge, "generate", refuse)
    monkeypatch.setattr(bridge, "ground", refuse)
    engineering.artifact_links(engine.state)
    engineering.unbacked_requirements(engine.state)
    engineering.engineering_graph(engine.state)
    export_project(engine.org, engine.state, tmp_path / "out")


# --- Surfaces: graph, export, CLI -----------------------------------------------------------


def test_the_engineering_graph_joins_trace_and_design(axi):
    engine, rtl = axi
    record_plan(engine, rtl)
    graph = engineering.engineering_graph(engine.state)
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {(e["from"], e["relation"], e["to"]) for e in graph["edges"]}
    tb = art_of(engine, rtl, "testbench")
    iface = next(l.node for l in engineering.artifact_links(engine.state).links if l.node_kind == "interface")
    assert nodes[iface]["kind"] == "design:interface"
    assert (tb.id, "exercises", iface) in edges
    assert ("tb-slverr", "proves", "req:AXIL-SLVERR") in edges and ("tb-slverr", "held_in", tb.id) in edges
    assert nodes["req:AXIL-SYNTH"]["backed"] is False


def test_the_export_writes_the_gaps_into_evidence(axi, tmp_path):
    engine, rtl = axi
    record_plan(engine, rtl)
    before = list(engine.state.audit)
    export_project(engine.org, engine.state, tmp_path / "out")
    folder = next(f.id for f in folders() if ExportSection.ENGINEERING_GRAPH in f.sections)
    assert folder == "09_evidence"
    data = json.loads((tmp_path / "out" / folder / "engineering_graph.json").read_text())
    assert [r["requirement"] for r in data["unbacked"]] == ["AXIL-B2B", "AXIL-SYNTH"]
    assert len(data["links"]) == 3 and data["refused"] == []
    gaps = (tmp_path / "out" / folder / "requirement_gaps.md").read_text()
    assert "AXIL-SYNTH" in gaps and "no verification item" in gaps
    assert "engineering_graph.json" in (tmp_path / "out" / "INDEX.md").read_text()
    assert engine.state.audit == before
    export_project(engine.org, engine.state, tmp_path / "again")  # deterministic
    assert (tmp_path / "again" / folder / "engineering_graph.json").read_bytes() == \
        (tmp_path / "out" / folder / "engineering_graph.json").read_bytes()


def test_the_cli_answers_the_question(axi, tmp_path):
    from nirmaan.cli import app

    engine, rtl = axi
    record_plan(engine, rtl)
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id
    result = CliRunner().invoke(app, ["gaps", project, "--root", str(root)])
    assert result.exit_code == 1, result.output
    assert "AXIL-SYNTH" in result.output and "AXIL-SLVERR" not in result.output
    data = json.loads(CliRunner().invoke(app, ["gaps", project, "--root", str(root), "--json"]).output)
    assert [r["requirement"] for r in data if not r["backed"]] == ["AXIL-B2B", "AXIL-SYNTH"]
    links = CliRunner().invoke(app, ["links", project, "--root", str(root)])
    assert links.exit_code == 0 and "axi4_lite_regs.s_axil" in links.output


# --- Crown jewel: new kinds need zero core changes --------------------------------------------


def test_a_new_link_kind_or_item_kind_needs_zero_core_changes(axi, tmp_path):
    engine, rtl = axi
    src = art_of(engine, rtl, "rtl_source")
    engineering.register_link_kind(LinkKind(
        id="declares-port-bundle", artifact_kinds=("rtl_source",), node_kinds=("interface",),
        walk=("<connects",), description="an RTL file declares the port bundles of the modules it defines"))
    engineering.register_item_kind(ItemKind(
        id="lint-clean", tools=("lint.run",), description="a file proven clean by a lint run"))
    try:
        links = engineering.artifact_links(engine.state).links
        assert (src.id, "declares-port-bundle", "axi4_lite_regs.s_axil") in {
            (l.artifact, l.kind, l.node_name) for l in links}
        engine.record_spec_requirement(spec_author(engine), "AXIL-LINT", "Lint clean.", spec_id(engine))
        engine.record_verification_item(rtl_owner(engine, rtl), "lint-rtl", "lint-clean", "axi4_lite_regs",
                                        src.id, ("AXIL-LINT",))
        (status,) = engineering.requirement_coverage(engine.state)
        assert status.backed and engine.state.tool_runs[status.items[0].run].tool == "lint.run"
    finally:
        engineering.unregister_link_kind("declares-port-bundle")
        engineering.unregister_item_kind("lint-clean")
    (status,) = engineering.requirement_coverage(engine.state)
    assert not status.backed and "unknown verification-item kind" in status.items[0].reason


# --- The Stage 5 demo: the AXI4-Lite flow, with real tools ------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_stage5_demo_on_the_axi4_lite_flow(nirmaan_org, fixed_clock, tmp_path):
    """The Stage 4 flow for real, then: what does passing simulation prove, and what is still open?"""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    stages = (("interface-spec", "requirements", [("interface_spec.md", "interface_spec", None)]),
              ("microarchitecture", "interface-spec", [("microarchitecture.md", "microarchitecture_spec", None)]),
              ("rtl-implementation", "microarchitecture", [(RTL_FILE, "rtl_source", "axi4_lite_regs"),
                                                           (TB_FILE, "testbench", "axi4_lite_regs_tb")]))
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, outputs in stages:
        seat = tid(engine, stage)
        engine.remember(MemoryScope.TASK, seat, "input.workspace", str(tmp_path / stage),
                        human(engine.task(seat).owner))
        cite = token(engine.task(tid(engine, source)).artifacts[0])
        files = [(p, k, e, (AXI / p).read_text()) for p, k, e in outputs]
        meta = [{k: v for k, v in f.items() if v is not None}
                for f in ({"path": p, "kind": k, "title": p, "summary": f"{p}, from {cite}.", "entry": e}
                          for p, k, e, _ in files)]
        text = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                           "escalation": None}) + "\n" + "".join(
            f"=== FILE: {p} ===\n{c}=== END FILE ===\n" for p, _, _, c in files)
        assert run_task(engine, seat, ModelRuntime(MockLLM(script=[text]))).status is ResultStatus.SUBMITTED
        assert review_task(engine, seat, ModelRuntime(MockLLM())).status is ResultStatus.SUBMITTED
        engine.approve(seat, human(engine.task(seat).approver), "agreed")

    rtl = tid(engine, "rtl-implementation")
    spec = engine.state.artifacts[spec_id(engine)]
    assert spec.location and Path(spec.location).read_bytes() == (AXI / "interface_spec.md").read_bytes()
    src, tb = art_of(engine, rtl, "rtl_source"), art_of(engine, rtl, "testbench")

    # The RTL and testbench link to axi4_lite_regs, parsed from the approved files.
    links = {(l.artifact, l.kind, l.node_name) for l in engineering.artifact_links(engine.state).links}
    assert {(src.id, "defines", "axi4_lite_regs"), (tb.id, "exercises", "axi4_lite_regs"),
            (tb.id, "exercises", "axi4_lite_regs.s_axil")} <= links

    # Interface-spec requirements (section 8 and the policies it tests), quoted by the spec's author.
    author, dv = spec_author(engine), rtl_owner(engine, rtl)
    requirements = {
        "AXIL-RESET": ("7", "During and after reset every register holds its reset value (zero)."),
        "AXIL-WSTRB": ("4", "Only the bytes whose wstrb bit is set are written."),
        "AXIL-ORDER": ("4", "AW and W may arrive in either order or together."),
        "AXIL-SLVERR": ("5", "An unmapped access is answered with SLVERR."),
        "AXIL-LATENCY": ("6", "B and R are valid at most 2 cycles after the request completes."),
        "AXIL-B2B": ("8", "Back-to-back transactions with no idle cycle."),
        "AXIL-SYNTH": ("8", "Synthesizes with Yosys, with no latches."),
        "AXIL-FORMAL": ("8", "A formal proof of the handshake rules."),
    }
    for rid, (section, text) in requirements.items():
        engine.record_spec_requirement(author, rid, text, spec.id, section=section)
    for item, kind, name, proves in (
        ("tb-top", "test", "axi4_lite_regs_tb", ("AXIL-RESET", "AXIL-ORDER")),
        ("tb-wstrb", "test", "wstrb 0101", ("AXIL-WSTRB",)),
        ("tb-slverr", "test", "unmapped write SLVERR", ("AXIL-SLVERR",)),
        ("tb-latency", "test", "MAX_LATENCY", ("AXIL-LATENCY",)),
        ("tb-b2b", "test", "back-to-back read", ("AXIL-B2B",)),
        ("cov-b2b", "coverage_point", "back-to-back", ("AXIL-B2B",)),
    ):
        engine.record_verification_item(dv, item, kind, name, tb.id, proves)

    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    proven = {"AXIL-RESET", "AXIL-WSTRB", "AXIL-ORDER", "AXIL-SLVERR", "AXIL-LATENCY"}
    assert {r for r, s in status.items() if s.backed} == proven
    for rid in proven:  # each backed by the real Icarus/Verilator simulation, cited and substantiated
        run = engine.state.tool_runs[status[rid].items[0].run]
        assert run.tool == "simulator.run" and run.succeeded and tb.location in run.params["sources"]
    gaps = {r.requirement: r for r in engineering.unbacked_requirements(engine.state)}
    assert set(gaps) == {"AXIL-B2B", "AXIL-SYNTH", "AXIL-FORMAL"}
    assert "coverage.read" in next(i.reason for i in gaps["AXIL-B2B"].items if i.item == "cov-b2b")
    assert all("no verification item" in gaps[r].reasons[0] for r in ("AXIL-SYNTH", "AXIL-FORMAL"))
    # The digests still match: the links and the evidence are about the approved bytes.
    for art in (src, tb):
        assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
