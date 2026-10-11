"""Milestone 44: one end-to-end factory project, from a request to a signed-off layout and its export.

* A request that asks for a layout plans ``block-design`` with six layout stages after the RTL, as data,
  whose checks run over the approved upstream artifacts only (the workflow connection).
* A tool's output becomes a stage's artifact (``yields``): a run records what it wrote, the runtime records
  those files as the task's artifacts, and the engine refuses one that is not the very file a passing run over
  the approved inputs wrote. The DFT stage now inserts scan into the approved RTL this way.
* A deliverable folder can list a tool's recorded runs, so ``06_formal`` and ``07_lint`` hold the runs that
  gated the RTL.
* The whole project, end to end, in CI's ``physical-design`` job: MockLLM seats answer with the AXI4-Lite
  fixtures, every check is a real tool run, people approve, and ``nirmaan export`` fills all ten folders.
  Locally it runs up to the layout and skips there; CI requires the tools.
* Crown jewel: a new tool output that becomes an artifact, and a folder that lists a new tool's runs, need
  zero core changes.

See docs/FACTORY_E2E.md.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import human, needs, tid
from test_nirmaan_design_agents import answer, file, token
from test_nirmaan_physical import (
    SKY130HD,
    SKY130HD_CORNERS,
    SKY130HD_PNR,
    SKY130HD_PV,
    only_on_path,
    sky130hd,
)

from nirmaan.models import (
    Assurance,
    EvidenceKind,
    MemoryScope,
    ReviewState,
    TaskKind,
    TaskStatus,
    Verdict,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolBroker, review_task, run_task
from nirmaan.work import PolicyViolationError

FIXTURES = Path(__file__).parent / "fixtures"
AXI = FIXTURES / "rtl" / "axi4_lite"
FW = FIXTURES / "fw" / "axi4_lite"
SDC = FIXTURES / "pd" / "axi4_lite_regs.sdc"
TOP = "axi4_lite_regs"
REQUEST = "Create an AXI4-Lite register block with a register map, a driver, scan chains, and a layout on sky130hd."
LAYOUT_STAGES = ("timing-constraints", "synthesis", "floorplan", "place-route", "physical-verification",
                 "sta-signoff")
#: What the line needs before the layout: the RTL gates, the register map's co-simulation, scan, and the driver.
FRONT_TOOLS = ("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2", "cc", "make")
#: The design inputs of the layout tools: in this project they must be approved artifacts, never typed paths.
DESIGN_PARAMS = ("sources", "netlist", "sdc", "spef", "def")
#: The PDK and the top module, as the person running the line sets them on each layout task (PDK paths are
#: relative to NIRMAAN_PDK_ROOT, as CI's physical-design job sets it).
LAYOUT_INPUTS = {
    **SKY130HD, **SKY130HD_PNR, **SKY130HD_CORNERS, **SKY130HD_PV, "top": TOP, "utilization": "30",
    "timeout": "900", "tie_high": "sky130_fd_sc_hd__conb_1/HI", "tie_low": "sky130_fd_sc_hd__conb_1/LO",
    "buffer_cell": "sky130_fd_sc_hd__buf_4/A/X",
}
#: Scan as the DFT lead sets it: eight balanced chains (one 206-flop chain takes ATPG over ten minutes).
SCAN = {"chains": "8"}
#: For the tests of the hand-off alone: ATPG graded on a sample of the faults, recorded as such in the run.
QUICK_SCAN = {**SCAN, "fault_sample": "64"}
QUICK = {"dft.atpg": {"min_test_coverage": "90", "fault_sample": "64"}}


@pytest.fixture()
def line(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REQUEST)


def _inputs(engine, task_id: str, **values: str) -> None:
    owner = human(engine.task(task_id).owner)
    for key, value in values.items():
        engine.remember(MemoryScope.TASK, task_id, f"input.{key}", value, owner)


def _approved(engine, stage: str, kind: str):
    task = engine.task(tid(engine, stage))
    return next(engine.state.artifacts[a] for a in task.artifacts if engine.state.artifacts[a].kind == kind)


# --- The workflow connection, as data ---------------------------------------------------------------------


def test_a_layout_request_plans_the_layout_stages_on_approved_inputs(line, nirmaan_org, fixed_clock):
    assert line.state.project.analysis.intent == "block_design"
    assert line.state.project.workflows == ("block-design",)
    assert {"layout", "dft", "firmware", "register_map"} <= set(line.state.project.analysis.features)
    tasks = {t.stage: t for t in line.state.tasks.values() if t.stage and t.kind is TaskKind.WORK}
    assert set(LAYOUT_STAGES) <= set(tasks)

    def deps(stage: str) -> set[str]:
        return {line.task(d).stage for d in tasks[stage].depends_on}

    assert deps("timing-constraints") == {"rtl-implementation"}
    assert deps("synthesis") == {"rtl-implementation"}
    assert deps("floorplan") == {"synthesis", "timing-constraints"}
    assert deps("place-route") == {"synthesis", "timing-constraints", "floorplan"}
    assert deps("physical-verification") == {"place-route"}
    assert deps("sta-signoff") == {"place-route", "physical-verification", "timing-constraints"}

    # Every layout check runs before review, and every design input is an approved upstream artifact.
    bound = {}
    for stage in LAYOUT_STAGES:
        (check,) = [r for r in tasks[stage].evidence_requirements if r.accepts == (EvidenceKind.TOOL_RUN,)]
        assert check.before_review and check.files, stage
        bound[stage] = {b.param: (b.kinds, b.upstream) for b in check.files}
    assert bound["timing-constraints"] == {"sdc": (("constraints",), False), "sources": (("rtl_source",), True)}
    assert bound["synthesis"] == {"sources": (("rtl_source",), True)}
    assert bound["floorplan"] == bound["place-route"] == {"netlist": (("netlist",), True),
                                                          "sdc": (("constraints",), True)}
    assert bound["physical-verification"] == {"def": (("layout",), True), "netlist": (("power_netlist",), True)}
    assert bound["sta-signoff"] == {"netlist": (("routed_netlist",), True), "spef": (("parasitics",), True),
                                    "sdc": (("constraints",), True)}

    # What each stage yields is what the next one binds; the reports travel too.
    yields = {s: dict(r.yields) for s in LAYOUT_STAGES for r in tasks[s].evidence_requirements if r.yields}
    assert yields == {
        "synthesis": {"netlist": "netlist", "synthesis_report": "log"},
        "floorplan": {"floorplan": "def"},
        "place-route": {"layout": "def", "routed_netlist": "netlist", "power_netlist": "pg_netlist",
                        "parasitics": "spef"},
        "physical-verification": {"gds": "gds", "physical_verification_report": "log"},
        "sta-signoff": {"timing_report": "log"},
    }
    for stage in LAYOUT_STAGES:
        produced = {k for r in tasks[stage].evidence_requirements for k, _ in r.yields}
        assert produced <= set(tasks[stage].expected_outputs), stage
    gates = [t for t in line.state.tasks.values() if t.kind is TaskKind.GATE]
    assert [g.gate for g in gates] == ["gate.implementation"] and tasks["sta-signoff"].id in gates[0].depends_on

    # A block that asks for no layout plans none of it.
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan(
        "Create an AXI4-Lite register block with a register map and a driver.")
    assert "layout" not in plain.state.project.analysis.features
    assert not set(LAYOUT_STAGES) & {t.stage for t in plain.state.tasks.values()}


def test_the_layout_stages_hold_the_same_limits_as_physical_implementation():
    from nirmaan.company.workflows import WORKFLOWS

    flows = {wf.id: wf for wf in WORKFLOWS}
    block, pd = flows["block-design"], flows["physical-implementation"]
    for stage in ("place-route", "physical-verification", "sta-signoff"):
        limits = {k: v for r in pd.stage(stage).evidence for k, v in r.params}
        ours = {k: v for r in block.stage(stage).evidence for k, v in r.params}
        assert limits.items() <= ours.items(), stage
    assert dict(block.stage("synthesis").evidence[-1].params) == {"backend": "yosys-liberty"}
    assert dict(block.stage("floorplan").evidence[-1].params)["stop_after"] == "floorplan"
    assert dict(block.stage("place-route").evidence[-1].params)["stop_after"] == "extract"


def test_the_dft_stage_inserts_scan_into_the_approved_rtl():
    from nirmaan.company.workflows import WORKFLOWS

    dft = next(wf for wf in WORKFLOWS if wf.id == "block-design").stage("dft")
    first = dft.evidence[1]
    assert first.tools == ("dft.scan_insert",) and first.before_review
    assert [(b.param, b.kinds, b.upstream) for b in first.files] == [("sources", ("rtl_source",), True)]
    assert first.yields == (("dft_netlist", "scan_netlist"),)


# --- Tool outputs as artifacts ----------------------------------------------------------------------------


def _drive_to(engine, stage: str, tmp_path: Path, rtl: Path = AXI / "axi4_lite_regs.v") -> None:
    """Take the line's front end to ``stage`` READY, with seats answering from the AXI4-Lite fixtures."""
    _front_end(engine, tmp_path, rtl, until=stage)


def _scan_by_hand(engine, tmp_path: Path, source: str):
    """The DFT owner runs scan insertion and its checks through the broker, as the M25 DFT test does."""
    seat = tid(engine, "dft")
    owner = human(engine.task(seat).owner)
    engine.start(seat, owner)
    broker = ToolBroker(engine)

    def run(tool: str, sources: str, name: str, **extra: str):
        done, outcome = broker.invoke(owner, tool, {"sources": sources, "top": TOP,
                                                    "workdir": str(tmp_path / name), **extra}, seat)
        engine.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, done.summary,
                               reference=done.references[0], tool_run=done.id)
        return done, outcome

    insert, outcome = run("dft.scan_insert", source, "insert", chains="8")
    assert insert.succeeded, insert.summary
    netlist = outcome.data["result"]["metrics"]["scan_netlist"]
    assert insert.outputs["scan_netlist"] == netlist  # the run records what it wrote
    return seat, owner, run, netlist


@needs(*FRONT_TOOLS)
def test_a_yielded_artifact_must_be_the_file_the_passing_run_wrote(line, tmp_path):
    _drive_to(line, "dft", tmp_path)
    rtl = _approved(line, "rtl-implementation", "rtl_source")
    seat, owner, run, netlist = _scan_by_hand(line, tmp_path, rtl.location)
    copy = tmp_path / "elsewhere" / "scan.v"
    copy.parent.mkdir()
    shutil.copy(netlist, copy)
    for tool in ("dft.check", "dft.scan_sim", "dft.atpg"):
        checked, _ = run(tool, str(copy), f"copy-{tool}", **QUICK.get(tool, {}))
        assert checked.succeeded, checked.summary
    draft = {"kind": "dft_netlist", "title": "scan.v", "summary": "Scan netlist."}
    # Checked, but not the file a scan insertion over the approved RTL wrote: it does not open review.
    with pytest.raises(PolicyViolationError, match="no passing run .* wrote"):
        line.submit(seat, owner, [{**draft, "location": str(copy)}])
    for tool in ("dft.check", "dft.scan_sim", "dft.atpg"):
        checked, _ = run(tool, netlist, tool, **QUICK.get(tool, {}))
        assert checked.succeeded, checked.summary
    line.submit(seat, owner, [{**draft, "location": netlist}])
    assert line.task(seat).status is TaskStatus.IN_REVIEW


@needs(*FRONT_TOOLS)
def test_a_yielded_artifact_must_come_from_the_approved_upstream(line, tmp_path):
    _drive_to(line, "dft", tmp_path)
    unapproved = tmp_path / "other" / "axi4_lite_regs.v"
    unapproved.parent.mkdir()
    shutil.copy(AXI / "axi4_lite_regs.v", unapproved)  # the same bytes, but not the approved artifact
    seat, owner, run, netlist = _scan_by_hand(line, tmp_path, str(unapproved))
    for tool in ("dft.check", "dft.scan_sim", "dft.atpg"):
        run(tool, netlist, tool, **QUICK.get(tool, {}))
    with pytest.raises(PolicyViolationError, match="approved upstream rtl_source"):
        line.submit(seat, owner, [{"kind": "dft_netlist", "title": "scan.v", "location": netlist}])


@needs(*FRONT_TOOLS)
def test_the_runtime_records_what_a_passing_run_wrote_as_the_tasks_artifacts(line, tmp_path):
    _drive_to(line, "dft", tmp_path)
    seat = tid(line, "dft")
    _inputs(line, seat, top=TOP, **QUICK_SCAN)
    report = run_task(line, seat, ModelRuntime(MockLLM(script=[answer()])))  # the seat writes nothing
    assert report.status is ResultStatus.SUBMITTED, report.detail
    runs = {line.state.tool_runs[r].tool: line.state.tool_runs[r] for r in report.tool_runs}
    assert {"dft.scan_insert", "dft.check", "dft.scan_sim", "dft.atpg"} <= set(runs)
    assert all(r.succeeded for r in runs.values()), {t: r.summary for t, r in runs.items()}
    (art,) = [line.state.artifacts[a] for a in line.task(seat).artifacts]
    rtl = _approved(line, "rtl-implementation", "rtl_source")
    assert art.kind == "dft_netlist" and art.location == runs["dft.scan_insert"].outputs["scan_netlist"]
    assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
    assert art.derived_from == (rtl.id,) and runs["dft.scan_insert"].id in art.summary
    assert runs["dft.scan_insert"].values("sources") == [rtl.location]
    assert runs["dft.check"].values("sources") == [art.location]  # the later checks ran on the yielded file
    assert runs["dft.check"].params["top"] == TOP


@needs(*FRONT_TOOLS)
def test_without_the_pd_tools_the_layout_stages_block(line, tmp_path, monkeypatch):
    """No timer here: the constraints seat is BLOCKED, and nothing is recorded as run."""
    _drive_to(line, "dft", tmp_path)  # the RTL is approved: the layout's first stage is READY
    seat = tid(line, "timing-constraints")
    assert line.task(seat).status is TaskStatus.READY
    _inputs(line, seat, **LAYOUT_INPUTS)
    rtl = _approved(line, "rtl-implementation", "rtl_source")
    only_on_path(monkeypatch, tmp_path / "empty")  # no sta, no openroad, no yosys
    sdc = file("axi4_lite_regs.sdc", "constraints", SDC.read_text(), token(rtl.id))
    report = run_task(line, seat, ModelRuntime(MockLLM(script=[answer(sdc)])))
    assert report.status is ResultStatus.BLOCKED, report.detail
    assert "sta" in report.detail and "not found" in report.detail
    assert line.task(seat).status is TaskStatus.BLOCKED
    assert [r for r in line.state.tool_runs.values() if r.task == seat] == []


# --- The line, end to end ---------------------------------------------------------------------------------


def _seat(engine, stage: str, files: list[tuple[str, str, Path, str | None]], tmp_path: Path, **inputs: str):
    """One seat answers with these fixture files ((name, kind, path, entry)), citing an approved input."""
    seat = tid(engine, stage)
    assert engine.task(seat).status is TaskStatus.READY, (seat, engine.task(seat).status)
    _inputs(engine, seat, workspace=str(tmp_path / stage), **inputs)
    upstream = [a for d in engine.task(seat).depends_on for a in engine.task(d).artifacts]
    cite = token(upstream[0]) if upstream else ""
    llm = MockLLM(script=[answer(*(file(name, kind, path.read_text(), cite, entry)
                                   for name, kind, path, entry in files))])
    report = run_task(engine, seat, ModelRuntime(llm))
    assert report.status is ResultStatus.SUBMITTED, (stage, report.detail)
    review = review_task(engine, seat, ModelRuntime(MockLLM()))
    assert review.status is ResultStatus.SUBMITTED, (stage, review.detail)
    task = engine.task(seat)
    assert task.review_state is ReviewState.PASSED, stage
    engine.approve(seat, human(task.approver), "checked and agreed")
    assert engine.task(seat).status is TaskStatus.COMPLETED, stage
    return report


def _requirements(engine, tmp_path: Path) -> None:
    """The requirements owner (a person: nothing upstream to cite) submits the spec; a person reviews it."""
    seat = tid(engine, "requirements")
    task = engine.task(seat)
    owner = human(task.owner)
    engine.start(seat, owner)
    path = tmp_path / "requirements" / "requirements_spec.md"
    path.parent.mkdir(parents=True)
    shutil.copy(AXI / "requirements_spec.md", path)
    engine.submit(seat, owner, [{"kind": "requirements_spec", "title": path.name, "location": str(path),
                                 "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}])
    engine.review(seat, human(engine.task(seat).reviewer), Verdict.APPROVE, "the request, baselined")
    engine.approve(seat, human(engine.task(seat).approver), "agreed")
    assert engine.task(seat).status is TaskStatus.COMPLETED


def _front_end(engine, tmp_path: Path, rtl: Path, until: str | None = None, scan: dict | None = None) -> None:
    """Requirements to the driver (and scan), each stage by its seat, reviewed, and approved by a person."""
    scan = SCAN if scan is None else scan
    stages = [
        ("interface-spec", [("interface_spec.md", "interface_spec", AXI / "interface_spec.md", None)], {}),
        ("register-map", [("register_map.json", "register_map", AXI / "register_map.json", None)], {}),
        ("microarchitecture", [("microarchitecture.md", "microarchitecture_spec", AXI / "microarchitecture.md",
                                None)], {}),
        ("rtl-implementation", [("axi4_lite_regs.v", "rtl_source", rtl, TOP),
                                ("axi4_lite_regs_tb.v", "testbench", AXI / "axi4_lite_regs_tb.v",
                                 "axi4_lite_regs_tb"),
                                ("axi4_lite_regs.sby", "formal_spec", AXI / "axi4_lite_regs.sby", None)], {}),
        ("dft", [], {"top": TOP, **scan}),
        ("firmware", [(p.name, "driver", p, None) for p in (FW / "axi4_lite_regs_map.h",
                                                             FW / "axi4_lite_regs_drv.h", FW / "axi4_lite_regs_drv.c")]
         + [("axi4_lite_regs_test.c", "driver_test", FW / "axi4_lite_regs_test.c", None)], {}),
    ]
    _requirements(engine, tmp_path)
    for stage, files, inputs in stages:
        if stage == until:
            return
        _seat(engine, stage, files, tmp_path, **inputs)
    assert until is None or engine.task(tid(engine, until)).status is TaskStatus.READY


def _layout(engine, tmp_path: Path) -> None:
    for stage in LAYOUT_STAGES:
        files = [("axi4_lite_regs.sdc", "constraints", SDC, None)] if stage == "timing-constraints" else []
        _seat(engine, stage, files, tmp_path, **LAYOUT_INPUTS)
    (gate,) = [t for t in engine.state.tasks.values() if t.kind is TaskKind.GATE]
    assert gate.status is TaskStatus.READY and gate.human_required
    engine.approve_gate(gate.id, human(gate.owner), "signed off: timing, DRC, and LVS clean")


@needs(*FRONT_TOOLS, "openroad", "sta", "klayout")
def test_one_request_runs_from_requirements_to_a_signed_off_layout(line, tmp_path):
    sky130hd(SKY130HD_CORNERS, SKY130HD_PV)
    _front_end(line, tmp_path, AXI / "axi4_lite_regs.v")
    _layout(line, tmp_path)
    state = line.state
    work = [t for t in state.tasks.values() if t.kind is TaskKind.WORK]
    assert all(t.status is TaskStatus.COMPLETED for t in work), [(t.id, t.status) for t in work]
    assert all(a.assurance is Assurance.APPROVED for a in state.artifacts.values())

    # Each layout stage ran on what the stage before it approved, never on a typed path or a fixture.
    approved = {a.location for a in state.artifacts.values()}
    layout_runs = [r for r in state.tool_runs.values()
                   if r.task in {tid(line, s) for s in LAYOUT_STAGES}]
    assert {r.tool for r in layout_runs} == {"sta.run", "synth.run", "pnr.run", "pv.run"}
    for run in layout_runs:
        for param in DESIGN_PARAMS:
            for value in run.values(param):
                assert value in approved and str(FIXTURES) not in value, (run.id, param, value)
    netlist = _approved(line, "synthesis", "netlist")
    rtl = _approved(line, "rtl-implementation", "rtl_source")
    assert netlist.derived_from == (rtl.id,)
    assert _approved(line, "place-route", "layout").derived_from[0] == netlist.id
    signoff = next(r for r in layout_runs if r.task == tid(line, "sta-signoff"))
    assert signoff.values("spef") == [_approved(line, "place-route", "parasitics").location]

    # The real numbers, as the runs reported them.
    def metrics(run):
        return json.loads(Path(run.references[1]).read_text())["result"]["metrics"]

    pnr = metrics(next(r for r in layout_runs if r.task == tid(line, "place-route")))
    assert pnr["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"]
    assert pnr["drc_violations"] == 0 and pnr["unconnected_supply_pins"] == 0 and pnr["fill_shapes"] > 0
    pv = metrics(next(r for r in layout_runs if r.task == tid(line, "physical-verification")))
    assert pv["drc_violations"] == 0 and pv["lvs_mismatches"] == 0
    sta = metrics(signoff)
    assert sta["timing_corners"] == 3 and sta["worst_slack"] > 0 and sta["unannotated_nets"] == 0
    summary = {"tool_runs": len(state.tool_runs), "artifacts": len(state.artifacts), "audit": len(state.audit),
               "synth": metrics(next(r for r in layout_runs if r.task == tid(line, "synthesis"))),
               "pnr": pnr, "pv": pv, "sta": sta}
    (tmp_path / "m44_summary.json").write_text(json.dumps(summary, indent=2, default=str))  # kept by CI

    # nirmaan export: all ten folders, from this project's own records.
    from nirmaan.cli import app
    from nirmaan.work.store import ProjectStore

    root, out = tmp_path / ".nirmaan", tmp_path / "export"
    ProjectStore(root).save(state)
    result = CliRunner().invoke(app, ["export", state.project.id, "--out", str(out), "--root", str(root)],
                                env={"COLUMNS": "400"})
    assert result.exit_code == 0, result.output
    folders = sorted(p.name for p in out.iterdir() if p.is_dir())
    assert folders == ["01_requirement", "02_architecture", "03_microarchitecture", "04_rtl", "05_verification",
                       "06_formal", "07_lint", "08_documentation", "09_evidence", "10_signoff"]

    def copies(folder: str) -> dict[str, bytes]:
        """Each artifact's copied file in the folder, by the name after its assurance label."""
        found = {}
        for path in (out / folder).iterdir():
            rest = path.name.partition(".APPROVED.")[2]
            if rest and rest not in ("md", "provenance.json"):
                found[rest] = path.read_bytes()
        return found

    assert (AXI / "requirements_spec.md").read_bytes() in copies("01_requirement").values()
    assert {(AXI / "interface_spec.md").read_bytes(), (AXI / "register_map.json").read_bytes()} <= \
        set(copies("02_architecture").values())
    assert (AXI / "microarchitecture.md").read_bytes() in copies("03_microarchitecture").values()
    rtl_files = copies("04_rtl")
    assert (AXI / "axi4_lite_regs.v").read_bytes() in rtl_files.values() and SDC.read_bytes() in rtl_files.values()
    for name in ("scan.v", "netlist.v", "route.def", "final.v", "final_pg.v", "route.spef", "layout.gds",
                 "floorplan.def"):
        assert name in rtl_files, (name, sorted(rtl_files))
    assert (AXI / "axi4_lite_regs_tb.v").read_bytes() in copies("05_verification").values()
    assert (FW / "axi4_lite_regs_drv.c").read_bytes() in copies("08_documentation").values()
    for folder, tools in (("06_formal", {"formal.run", "formal.cover"}), ("07_lint", {"lint.run"})):
        listed = [json.loads(p.read_text()) for p in (out / folder).glob("tool_runs/*/run.json")]
        assert {r["tool"] for r in listed} == tools and all(r["succeeded"] for r in listed), folder
        assert all(r["task"] == tid(line, "rtl-implementation") for r in listed)

    # The evidence lists only recorded, passing runs, and every claim of a run cites one.
    listed = [json.loads(p.read_text()) for p in (out / "09_evidence").glob("tool_runs/*/run.json")]
    assert {r["id"] for r in listed} == set(state.tool_runs)
    assert all(r["succeeded"] and state.tool_runs[r["id"]].succeeded for r in listed)
    for ev in state.evidence.values():
        assert ev.kind is not EvidenceKind.CLAIM
        if ev.kind is EvidenceKind.TOOL_RUN:
            assert ev.substantiated and state.tool_runs[ev.tool_run].succeeded
    chain = json.loads((out / "09_evidence" / "audit_chain.json").read_text())
    assert chain["verify_chain"]["intact"]
    trace = json.loads((out / "09_evidence" / "requirement_trace.json").read_text())
    assert trace["untraced"] == []
    signoff_json = json.loads((out / "10_signoff" / "signoff.json").read_text())
    (gate,) = signoff_json["gates"]
    assert gate["gate"] == "gate.implementation" and gate["signed_off"] and gate["audit"]["human"]
    index = (out / "INDEX.md").read_text()
    assert "Missing deliverables: 0" in index and "Unfiled artifacts: 0" in index


# --- Crown jewel: a new yielded output, and a folder of a new tool's runs, need zero core changes -----------


def test_a_new_tool_output_and_a_folder_of_its_runs_need_no_core_changes(fixed_clock, tmp_path):
    """A new tool whose output a stage yields, and a folder listing its runs: no runtime, engine, policy,
    broker, or export change."""
    from nirmaan.company import builder
    from nirmaan.export import export_project, register_folder, unregister_folder
    from nirmaan.models import (
        Capability,
        CapabilityKind,
        Criticality,
        DeliverableFolder,
        EvidenceRequirement,
        FileInput,
        Function,
        IntentRule,
        OrgUnit,
        ReviewRequirement,
        Skill,
        StageTemplate,
        ToolRisk,
        ToolSpec,
        ToolStatus,
        UnitKind,
        WorkflowTemplate,
    )
    from nirmaan.org import register_extension, unregister_extension
    from nirmaan.runtime import ToolOutcome, register_binding, unregister_binding

    @register_binding("bundle.pack")
    def pack(params, engine):
        out = Path(str(params["workdir"])) / "bundle.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        sources = [Path(s) for s in str(params["sources"]).split(",")]
        out.write_text("".join(s.read_text() for s in sources))
        return ToolOutcome(True, f"packed {len(sources)} file(s)", outputs={"bundle": str(out)})

    @register_extension("test-bundles")
    def bundles(b):
        b.add(
            ToolSpec(id="bundle.pack", name="Bundler", category="eda", risk=ToolRisk.EXECUTE,
                     status=ToolStatus.AVAILABLE),
            Capability(id="doc.bundle", name="Bundling", kind=CapabilityKind.EXECUTION,
                       description="Pack approved documents into one bundle.", produces=("bundle",),
                       approved_inputs=True),
            Skill(id="bundling", name="Bundling", domain="documentation", provides=("doc.bundle",),
                  tools=("bundle.pack",), validation_criteria=("The bundle holds the approved brief.",)),
            OrgUnit(id="architecture.bundles", name="Bundles", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                    parent="architecture", noun="Bundler", skills=("bundling",)),
            IntentRule(intent="bundle", patterns=(r"\bbundle\b",), priority=5),
            WorkflowTemplate(
                id="bundle", name="Bundle", description="Bundle a brief.", intents=("bundle",),
                stages=(
                    StageTemplate(id="brief", title="Brief", phase="Requirements", capability="req.analyze",
                                  criticality=Criticality.MEDIUM, outputs=("requirements_spec",),
                                  review=ReviewRequirement(capability="req.review")),
                    StageTemplate(
                        id="pack", title="Pack", phase="Requirements", capability="doc.bundle",
                        depends_on=("brief",), criticality=Criticality.MEDIUM, outputs=("bundle",),
                        review=ReviewRequirement(capability="arch.review"),
                        evidence=(EvidenceRequirement(
                            description="Packed from the approved brief", accepts=(EvidenceKind.TOOL_RUN,),
                            tools=("bundle.pack",), before_review=True, yields=(("bundle", "bundle"),),
                            files=(FileInput(param="sources", kinds=("requirements_spec",), upstream=True),)),)),
                ),
            ),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a bundle for the timer.")
        brief, seat = tid(engine, "brief"), tid(engine, "pack")
        owner = human(engine.task(brief).owner)
        engine.start(brief, owner)
        spec = tmp_path / "brief.md"
        spec.write_text("# Brief\n")
        engine.submit(brief, owner, [{"kind": "requirements_spec", "title": "brief.md", "location": str(spec),
                                      "digest": "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()}])
        engine.review(brief, human(engine.task(brief).reviewer), Verdict.APPROVE, "a brief")
        engine.approve(brief, human(engine.task(brief).approver))
        assert engine.task(brief).status is TaskStatus.COMPLETED
        _inputs(engine, seat, workdir=str(tmp_path / "pack"))
        report = run_task(engine, seat, ModelRuntime(MockLLM(script=[answer()])))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        (art,) = [engine.state.artifacts[a] for a in engine.task(seat).artifacts]
        assert art.kind == "bundle" and Path(art.location).read_text() == "# Brief\n"
        assert art.derived_from == tuple(engine.task(brief).artifacts)

        register_folder(DeliverableFolder(id="11_bundles", title="Bundles", artifact_kinds=("bundle",),
                                          tool_runs=("bundle.pack",)))
        export_project(org, engine.state, tmp_path / "out")
        folder = tmp_path / "out" / "11_bundles"
        runs = [json.loads(p.read_text()) for p in folder.glob("tool_runs/*/run.json")]
        assert [r["tool"] for r in runs] == ["bundle.pack"] and runs[0]["outputs"] == {"bundle": art.location}
        assert any(p.name.endswith(".bundle.txt") for p in folder.iterdir())
        assert "bundle.pack" in (folder / "README.md").read_text()
    finally:
        unregister_folder("11_bundles")
        unregister_extension("test-bundles")
        unregister_binding("bundle.pack")


# --- Import laws ------------------------------------------------------------------------------------------


def test_the_changed_modules_keep_the_import_laws_and_name_nothing():
    src = Path(__file__).parents[1] / "src" / "nirmaan"
    for path in (src / "runtime" / "model.py", src / "runtime" / "tools.py", src / "work" / "policy.py",
                 src / "export.py", src / "models" / "workflow.py", src / "models" / "deliverable.py"):
        tree = ast.parse(path.read_text())
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(n.startswith("veritriage") for n in names), path
        constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for word in ("netlist", "scan_netlist", "layout", "06_formal", "07_lint", "lint.run", "pnr.run"):
            assert word not in constants, (path, word)
