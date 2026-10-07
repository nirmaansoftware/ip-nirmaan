"""Milestone 29: verification plans, loaded from a file and written by a seat.

A plan (requirements, and the verification items that prove them) is loaded
from a small versioned JSON file through the task engine, all or nothing, and
exported back in the same format. A verification-plan seat on ``block-design``
writes one from the approved interface spec; a real ``vplan.check`` run
validates it before review, and on approval the engine records it, so
``nirmaan gaps`` answers from the seat's plan. Nothing here ever makes a
requirement backed: only a passing, cited run does (M24).

Most tests use the fake lint and simulation executables of the M24 tests; the
AXI4-Lite demo runs the real tools. No test calls a model API.
"""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid
from test_nirmaan_engineering_graph import (  # noqa: F401  (fake_eda and axi are fixtures)
    AXI,
    art_of,
    axi,
    axi_files,
    fake_eda,
    needs,
    run_rtl_seat,
    token,
)

from nirmaan import engineering, vplan
from nirmaan.company.traceability import ItemKind
from nirmaan.models import Assurance, MemoryScope, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, review_task, run_task
from nirmaan.work import ProjectStore, TaskEngine
from nirmaan.work.engine import WorkError

SRC = Path(__file__).resolve().parents[1] / "src" / "nirmaan"
AXI_PLANNED = "Create an AXI4-Lite register block with a verification plan."
PLAN_FILE = AXI / "verification_plan.json"
SPEC_FILE = AXI / "interface_spec.md"


def fixture_plan() -> dict:
    return json.loads(PLAN_FILE.read_text())


def dump(plan: dict) -> str:
    return json.dumps(plan, indent=2) + "\n"


def seat_answer(path: str, kind: str, content: str, cite: str, entry: str | None = None) -> str:
    meta = {"path": path, "kind": kind, "title": path, "summary": f"{path}, from {cite}.",
            **({"entry": entry} if entry else {})}
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": [meta],
                       "escalation": None})
    return f"{head}\n=== FILE: {path} ===\n{content}=== END FILE ===\n"


def run_seat(engine, stage: str, cites: str, path: str, kind: str, content: str, tmp_path: Path,
             entry: str | None = None):
    seat = tid(engine, stage)
    engine.remember(MemoryScope.TASK, seat, "input.workspace", str(tmp_path / stage),
                    human(engine.task(seat).owner))
    cite = token(engine.task(tid(engine, cites)).artifacts[0])
    return run_task(engine, seat, ModelRuntime(MockLLM(script=[seat_answer(path, kind, content, cite, entry)])))


def review_and_approve(engine, stage: str) -> None:
    seat = tid(engine, stage)
    assert review_task(engine, seat, ModelRuntime(MockLLM())).status is ResultStatus.SUBMITTED
    engine.approve(seat, human(engine.task(seat).approver), "agreed")


@pytest.fixture()
def planned(nirmaan_org, fixed_clock, tmp_path):
    """The block with a plan stage, its interface spec written by the seat (the fixture) and approved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_PLANNED)
    drive(engine, until=tid(engine, "interface-spec"))
    report = run_seat(engine, "interface-spec", "requirements", "interface_spec.md", "interface_spec",
                      SPEC_FILE.read_text(), tmp_path)
    assert report.status is ResultStatus.SUBMITTED, report.detail
    review_and_approve(engine, "interface-spec")
    assert engine.task(tid(engine, "dv-plan")).status is TaskStatus.READY
    return engine


def write_plan(engine, tmp_path: Path, plan: dict | str):
    content = plan if isinstance(plan, str) else dump(plan)
    return run_seat(engine, "dv-plan", "interface-spec", "verification_plan.json", "verification_plan",
                    content, tmp_path)


def check_run(engine):
    return [r for r in engine.state.tool_runs.values() if r.tool == "vplan.check"][-1]


def manager_of(engine, *task_ids: str) -> str:
    """The nearest role that manages the owners of all these tasks."""
    chains = [[r.id for r in engine.org.line_chain(engine.task(t).owner)] for t in task_ids]
    return next(r for r in chains[0] if all(r in c for c in chains[1:]))


def spec_id(engine) -> str:
    return engine.task(tid(engine, "interface-spec")).artifacts[0]


# --- The format -------------------------------------------------------------------------------


def test_spec_requirements_are_read_from_their_tags():
    found = vplan.spec_requirements(SPEC_FILE.read_text())
    plan = {r["id"]: r for r in fixture_plan()["requirements"]}
    assert [r.id for r in found] == ["AXIL-ORDER", "AXIL-WSTRB", "AXIL-SLVERR", "AXIL-LATENCY", "AXIL-B2B",
                                     "AXIL-RESET", "AXIL-SYNTH", "AXIL-FORMAL"]
    for req in found:  # the fixture plan quotes the spec exactly, section and all
        assert (req.text, req.section) == (plan[req.id]["text"], plan[req.id]["section"])
    assert "[req:" not in "".join(r.text for r in found)


def test_the_fixture_plan_is_valid():
    plan = vplan.parse(PLAN_FILE.read_text())
    assert len(plan.requirements) == 8 and len(plan.items) == 6
    assert vplan.check_against_specs(plan, {"interface_spec.md": SPEC_FILE.read_text()}) == []


# --- Import: through the engine, all or nothing -----------------------------------------------


def import_doc(engine, rtl: str) -> dict:
    """A plan for the axi project: the spec is a driven (file-less) artifact, so it is named by ID."""
    plan = fixture_plan()
    for req in plan["requirements"]:
        req["source"] = spec_id(engine)
    return plan


def importer(engine, rtl: str):
    return human(manager_of(engine, tid(engine, "interface-spec"), rtl))


def test_an_import_round_trips(axi):
    engine, rtl = axi
    before = engine.state
    text = dump(import_doc(engine, rtl))
    report = vplan.import_plan(engine, importer(engine, rtl), text)
    assert (report.requirements, report.items) == (8, 6)
    exported = vplan.export_plan(engine.state)
    assert exported == text  # canonical in, canonical out

    again = TaskEngine(engine.org, before)
    vplan.import_plan(again, importer(engine, rtl), exported)
    assert again.state.spec_requirements == engine.state.spec_requirements
    assert again.state.verification_items == engine.state.verification_items
    tb = art_of(engine, rtl, "testbench")
    assert {i.artifact for i in engine.state.verification_items.values()} == {tb.id}  # bound now


def test_an_import_is_audited_and_authorized(axi):
    engine, rtl = axi
    actor = importer(engine, rtl)
    count = len(engine.state.audit)
    vplan.import_plan(engine, actor, dump(import_doc(engine, rtl)))
    added = engine.state.audit[count:]
    assert [e.action for e in added] == ["trace.requirement"] * 8 + ["trace.item"] * 6
    assert {e.actor for e in added} == {actor.label}
    assert all(r.recorded_by == actor.label for r in engine.state.spec_requirements.values())


def test_a_bad_file_is_refused_with_line_reasons_and_nothing_is_recorded(axi):
    engine, rtl = axi
    before = engine.state
    plan = import_doc(engine, rtl)
    plan["requirements"][1]["status"] = "passed"  # a plan declares; it never records a result
    plan["requirements"].append(dict(plan["requirements"][0]))  # a duplicate ID
    plan["items"][0]["kind"] = "waveform_eyeball"  # not a registered kind
    plan["items"][1]["proves"] = ["AXIL-NOPE"]
    text = dump(plan)
    lines = text.splitlines()

    def line_of(needle: str, nth: int = 0) -> int:
        return [i for i, l in enumerate(lines, 1) if needle in l][nth]

    with pytest.raises(vplan.PlanError) as refused:
        vplan.import_plan(engine, importer(engine, rtl), text)
    joined = "\n".join(refused.value.problems)
    status, duplicate = line_of('"status"'), line_of('"id": "AXIL-B2B"', 1)
    kind, nope = line_of("waveform_eyeball"), line_of("AXIL-NOPE") - 1  # the line of "proves": [
    assert f"line {status}: unknown field 'status'" in joined
    assert f"line {duplicate}: duplicate requirement ID 'AXIL-B2B'" in joined
    assert f"line {kind}: unknown verification-item kind 'waveform_eyeball'" in joined
    assert f"line {nope}: proves 'AXIL-NOPE'" in joined
    assert engine.state is before and engine.state.spec_requirements == {}

    with pytest.raises(vplan.PlanError) as broken:
        vplan.import_plan(engine, importer(engine, rtl), '{\n  "format": "nirmaan.vplan",\n  "version": 1,\n}\n')
    assert broken.value.problems[0].startswith("line 4:")
    assert engine.state is before


def test_unresolved_references_and_engine_refusals_refuse_the_whole_file(axi):
    engine, rtl = axi
    before = engine.state
    plan = import_doc(engine, rtl)
    plan["items"][2]["file"] = "nowhere.v"
    with pytest.raises(vplan.PlanError) as refused:
        vplan.import_plan(engine, importer(engine, rtl), dump(plan))
    assert any("nowhere.v" in p and p.startswith("line ") for p in refused.value.problems)
    assert engine.state is before

    # Every record is made through the engine: an actor it refuses refuses the file, with each line.
    stranger = next(r for r in engine.org.roles
                    if r not in {engine.task(rtl).owner, engine.task(rtl).reviewer}
                    and r not in {x.id for x in engine.org.line_chain(engine.task(rtl).owner)}
                    and r not in {x.id for x in engine.org.line_chain(engine.task(tid(engine, "interface-spec")).owner)})
    with pytest.raises(vplan.PlanError) as unauthorized:
        vplan.import_plan(engine, human(stranger), dump(import_doc(engine, rtl)))
    assert len(unauthorized.value.problems) >= 8 and all(p.startswith("line ") for p in unauthorized.value.problems)
    assert "may not record" in unauthorized.value.problems[0]
    assert engine.state is before and engine.state.audit == before.audit


def test_an_import_never_counts_as_passing(axi):
    engine, rtl = axi
    runs, evidence = dict(engine.state.tool_runs), dict(engine.state.evidence)
    assurance = {a.id: a.assurance for a in engine.state.artifacts.values()}
    last_run = list(runs)[-1]
    vplan.import_plan(engine, importer(engine, rtl), dump(import_doc(engine, rtl)))
    assert engine.state.tool_runs == runs and engine.state.evidence == evidence
    assert {a.id: a.assurance for a in engine.state.artifacts.values()} == assurance
    coverage = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    # Only the seat's simulation, recorded before the import, backs anything.
    for req in (r for r in coverage.values() if r.backed):
        assert all(i.run in runs and list(runs).index(i.run) <= list(runs).index(last_run) for i in req.items)
    assert not coverage["AXIL-B2B"].backed and not coverage["AXIL-SYNTH"].backed
    assert not coverage["AXIL-FORMAL"].backed

    # And a plan that tries to say a result is refused outright.
    plan = import_doc(engine, rtl)
    plan["items"][0]["passed"] = True
    with pytest.raises(vplan.PlanError, match="unknown field 'passed'"):
        vplan.import_plan(engine, importer(engine, rtl), dump(plan))


def test_the_cli_imports_and_exports(axi, tmp_path):
    from nirmaan.cli import app

    engine, rtl = axi
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id
    good = tmp_path / "plan.json"
    good.write_text(dump(import_doc(engine, rtl)))
    bad = tmp_path / "bad.json"
    bad.write_text(dump({**import_doc(engine, rtl), "version": 2}))

    role = importer(engine, rtl).role
    refused = CliRunner().invoke(app, ["vplan", "import", project, str(bad), "--as", role, "--root", str(root)])
    assert refused.exit_code == 1 and "line 3:" in refused.output and "version" in refused.output
    assert ProjectStore(root).load(project).spec_requirements == {}

    result = CliRunner().invoke(app, ["vplan", "import", project, str(good), "--as", role, "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "8 requirements" in result.output and "6 verification items" in result.output
    out = tmp_path / "exported.json"
    exported = CliRunner().invoke(app, ["vplan", "export", project, "--out", str(out), "--root", str(root)])
    assert exported.exit_code == 0, exported.output
    assert out.read_text() == good.read_text()
    printed = CliRunner().invoke(app, ["vplan", "export", project, "--root", str(root)])
    assert json.loads(printed.output) == json.loads(good.read_text())


# --- The verification-plan seat -------------------------------------------------------------


def test_the_plan_stage_is_data_and_planned_on_request(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_PLANNED)
    plan, rtl = engine.task(tid(engine, "dv-plan")), engine.task(tid(engine, "rtl-implementation"))
    assert plan.capability == "dv.plan" and plan.depends_on == (tid(engine, "interface-spec"),)
    assert plan.expected_outputs == ("verification_plan",)
    assert rtl.depends_on == (tid(engine, "microarchitecture"),)  # nothing waits on the plan
    check = next(r for r in plan.evidence_requirements if r.before_review)
    assert check.tools == ("vplan.check",)

    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    assert tid(plain, "dv-plan") not in plain.state.tasks
    assert plain.task(tid(plain, "rtl-implementation")).depends_on == (tid(plain, "microarchitecture"),)


def test_the_check_refuses_a_plan_that_misses_a_spec_requirement(planned, tmp_path):
    engine = planned
    seat = tid(engine, "dv-plan")
    plan = fixture_plan()
    plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "AXIL-FORMAL"]
    report = write_plan(engine, tmp_path, plan)
    assert report.status is ResultStatus.REFUSED, report.detail
    assert engine.task(seat).status is TaskStatus.IN_PROGRESS and not engine.task(seat).artifacts
    run = check_run(engine)
    assert not run.succeeded and "AXIL-FORMAL" in run.summary and "interface_spec.md" in run.summary
    assert Path(run.params["spec"]).read_bytes() == SPEC_FILE.read_bytes()  # the approved spec, as recorded


@pytest.mark.parametrize("change, reason", [
    (lambda p: p["requirements"][0].update(text="Back-to-back works."), "does not quote"),
    (lambda p: p["items"][0].update(kind="eyeball"), "unknown verification-item kind 'eyeball'"),
    (lambda p: p["requirements"].append({"id": "AXIL-EXTRA", "text": "x", "source": "interface_spec.md"}),
     "AXIL-EXTRA is not a requirement"),
    (lambda p: p["items"][0].update(file="sim/axi4_lite_regs_tb.v"), "plain file name"),
    (lambda p: p["requirements"][0].update(source="other_spec.md"), "other_spec.md"),
])
def test_the_check_refuses_a_plan_that_does_not_match_the_spec(planned, tmp_path, change, reason):
    plan = fixture_plan()
    change(plan)
    report = write_plan(planned, tmp_path, plan)
    assert report.status is ResultStatus.REFUSED
    assert reason in check_run(planned).summary


def test_approval_records_the_plan_and_items_bind_to_the_file_once_written(planned, fake_eda, tmp_path):
    engine = planned
    seat = tid(engine, "dv-plan")
    report = write_plan(engine, tmp_path, fixture_plan())
    assert report.status is ResultStatus.SUBMITTED, report.detail
    run = check_run(engine)
    assert run.succeeded and "8 of 8" in run.summary and "AXIL-SYNTH" in run.summary  # the itemless ones named
    assert engine.state.spec_requirements == {}  # nothing before approval
    review_and_approve(engine, "dv-plan")

    plan_art = engine.state.artifacts[engine.task(seat).artifacts[0]]
    assert plan_art.assurance is Assurance.APPROVED
    reqs, items = engine.state.spec_requirements, engine.state.verification_items
    assert sorted(reqs) == sorted(r["id"] for r in fixture_plan()["requirements"])
    assert {r.source for r in reqs.values()} == {spec_id(engine)}
    assert reqs["AXIL-SLVERR"].section == "5"
    assert {(i.file, i.plan, i.artifact) for i in items.values()} == {("axi4_lite_regs_tb.v", plan_art.id, "")}
    assert items["tb-top"].proves == ("AXIL-ORDER", "AXIL-RESET")
    recorded = [e for e in engine.state.audit if e.action.startswith("trace.")]
    assert len(recorded) == 14 and all(e.details["plan"] == plan_art.id for e in recorded)
    assert {e.actor for e in recorded} == {engine.system.label}  # a consequence of the approval

    # No testbench yet: every item is unverifiable, and says why.
    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert not any(s.backed for s in status.values())
    assert "no recorded artifact holds axi4_lite_regs_tb.v yet" in status["AXIL-SLVERR"].items[0].reason

    # The RTL seat works from the approved plan, and writes the testbench the items name.
    rtl = run_rtl_seat(engine, tmp_path, axi_files())
    tb = art_of(engine, rtl, "testbench")
    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert {r for r, s in status.items() if s.backed} == {"AXIL-RESET", "AXIL-WSTRB", "AXIL-ORDER",
                                                          "AXIL-SLVERR", "AXIL-LATENCY"}
    assert status["AXIL-SLVERR"].items[0].artifact == tb.id
    graph = engineering.engineering_graph(engine.state)
    edges = {(e["from"], e["relation"], e["to"]) for e in graph["edges"]}
    assert ("tb-slverr", "held_in", tb.id) in edges and ("tb-slverr", "planned_in", plan_art.id) in edges
    assert vplan.export_plan(engine.state) == PLAN_FILE.read_text()  # the seat's plan, round-tripped


def test_a_plan_changed_after_review_is_not_approved(planned, tmp_path):
    engine = planned
    seat = tid(engine, "dv-plan")
    assert write_plan(engine, tmp_path, fixture_plan()).status is ResultStatus.SUBMITTED
    assert review_task(engine, seat, ModelRuntime(MockLLM())).status is ResultStatus.SUBMITTED
    plan_art = engine.state.artifacts[engine.task(seat).artifacts[0]]
    Path(plan_art.location).write_text(PLAN_FILE.read_text().replace("MAX_LATENCY", "MIN_LATENCY"))
    before = engine.state
    with pytest.raises(WorkError, match="does not match its recorded digest"):
        engine.approve(seat, human(engine.task(seat).approver))
    assert engine.state is before and engine.task(seat).status is TaskStatus.IN_REVIEW


# --- The AXI4-Lite demo, with the real tools --------------------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_the_axi4_lite_demo_is_driven_by_the_seats_plan(nirmaan_org, fixed_clock, tmp_path):
    from nirmaan.cli import app

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_PLANNED)
    drive(engine, until=tid(engine, "interface-spec"))
    stages = (("interface-spec", "requirements", "interface_spec.md", "interface_spec", None),
              ("dv-plan", "interface-spec", "verification_plan.json", "verification_plan", None),
              ("microarchitecture", "interface-spec", "microarchitecture.md", "microarchitecture_spec", None))
    for stage, cites, path, kind, entry in stages:
        report = run_seat(engine, stage, cites, path, kind, (AXI / path).read_text(), tmp_path, entry)
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_and_approve(engine, stage)
    assert len(engine.state.verification_items) == 6  # recorded from the approved plan, before any RTL

    rtl = tid(engine, "rtl-implementation")
    seat = engine.task(rtl)
    engine.remember(MemoryScope.TASK, rtl, "input.workspace", str(tmp_path / "rtl"), human(seat.owner))
    micro = token(engine.task(tid(engine, "microarchitecture")).artifacts[0])
    files = [{"path": p, "kind": k, "title": p, "summary": f"{p}, from {micro}.", "entry": e}
             for p, k, e in (("axi4_lite_regs.v", "rtl_source", "axi4_lite_regs"),
                             ("axi4_lite_regs_tb.v", "testbench", "axi4_lite_regs_tb"))]
    text = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": files,
                       "escalation": None}) + "\n" + "".join(
        f"=== FILE: {f['path']} ===\n{(AXI / f['path']).read_text()}=== END FILE ===\n" for f in files)
    assert run_task(engine, rtl, ModelRuntime(MockLLM(script=[text]))).status is ResultStatus.SUBMITTED
    review_and_approve(engine, "rtl-implementation")

    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    proven = {"AXIL-RESET", "AXIL-WSTRB", "AXIL-ORDER", "AXIL-SLVERR", "AXIL-LATENCY"}
    assert {r for r, s in status.items() if s.backed} == proven  # as in the M24 demo
    tb = art_of(engine, rtl, "testbench")
    for rid in proven:  # each by the real simulation, cited and substantiated
        run = engine.state.tool_runs[status[rid].items[0].run]
        assert run.tool == "simulator.run" and run.succeeded and tb.location in run.params["sources"]
    gaps = {r.requirement: r for r in engineering.unbacked_requirements(engine.state)}
    assert set(gaps) == {"AXIL-B2B", "AXIL-SYNTH", "AXIL-FORMAL"}
    assert "coverage.read" in next(i.reason for i in gaps["AXIL-B2B"].items if i.item == "cov-b2b")
    assert all("no verification item" in gaps[r].reasons[0] for r in ("AXIL-SYNTH", "AXIL-FORMAL"))

    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    result = CliRunner().invoke(app, ["gaps", engine.state.project.id, "--root", str(root)])
    assert result.exit_code == 1 and "5 of 8 recorded requirements are backed" in result.output
    data = json.loads(CliRunner().invoke(app, ["gaps", engine.state.project.id, "--root", str(root),
                                               "--json"]).output)
    assert sorted(r["requirement"] for r in data if not r["backed"]) == ["AXIL-B2B", "AXIL-FORMAL", "AXIL-SYNTH"]
    assert vplan.export_plan(engine.state) == PLAN_FILE.read_text()


# --- Crown jewel ------------------------------------------------------------------------------


def test_a_plan_seat_against_a_new_spec_kind_with_a_new_item_kind_needs_no_core_changes(fixed_clock, tmp_path):
    """A workflow added by extension plans against a software spec, with a newly registered item kind.

    Nothing in the engine, runtime, policy, broker, vplan reader, or check changes.
    """
    from nirmaan.company import builder
    from nirmaan.models import (
        Criticality,
        EvidenceKind,
        EvidenceRequirement,
        FileInput,
        IntentRule,
        ReviewRequirement,
        StageTemplate,
        WorkflowTemplate,
    )
    from nirmaan.org import register_extension, unregister_extension

    reviewed = EvidenceRequirement(description="Independent review recorded", accepts=(EvidenceKind.REVIEW_RECORD,))

    @register_extension("test-planned-software")
    def planned_software(b):
        b.add(
            IntentRule(intent="planned_software", patterns=(r"\bsoftware spec with a test list\b",), priority=5),
            WorkflowTemplate(
                id="planned-software", name="Planned software spec", description="A spec, then its plan.",
                intents=("planned_software",),
                stages=(
                    StageTemplate(id="requirements", title="Requirements", phase="Requirements",
                                  capability="req.analyze", criticality=Criticality.MEDIUM,
                                  review=ReviewRequirement(capability="req.review"),
                                  outputs=("requirements_spec",), evidence=(reviewed,)),
                    StageTemplate(id="software-spec", title="Software spec", phase="Architecture",
                                  capability="arch.software", depends_on=("requirements",),
                                  criticality=Criticality.MEDIUM, review=ReviewRequirement(capability="arch.review"),
                                  outputs=("software_architecture",), evidence=(reviewed,)),
                    StageTemplate(id="test-list", title="Test list", phase="Verification", capability="dv.plan",
                                  depends_on=("software-spec",), criticality=Criticality.MEDIUM,
                                  review=ReviewRequirement(capability="dv.review"), outputs=("verification_plan",),
                                  evidence=(reviewed, EvidenceRequirement(
                                      description="The plan covers the approved software spec",
                                      accepts=(EvidenceKind.TOOL_RUN,), tools=("vplan.check",),
                                      files=(FileInput(param="plan", kinds=("verification_plan",)),
                                             FileInput(param="spec", kinds=("software_architecture",),
                                                       upstream=True)),
                                      before_review=True))),
                ),
            ),
        )

    spec = ("# Timer driver\n\n## 1. API\n\n* `timer_load` writes the reload value. [req:TMR-LOAD]\n"
            "* The driver builds with no warnings. [req:TMR-CLEAN]\n")
    plan = {"format": "nirmaan.vplan", "version": 1,
            "requirements": [
                {"id": "TMR-CLEAN", "text": "The driver builds with no warnings.", "source": "sw_spec.md",
                 "section": "1"},
                {"id": "TMR-LOAD", "text": "`timer_load` writes the reload value.", "source": "sw_spec.md",
                 "section": "1"}],
            "items": [
                {"id": "build-clean", "kind": "warning-free", "file": "timer.c", "name": "timer_load",
                 "proves": ["TMR-CLEAN"], "rationale": "a strict build"},
                {"id": "load-test", "kind": "test", "file": "timer_test.c", "name": "load_test",
                 "proves": ["TMR-LOAD"], "rationale": ""}]}
    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a timer software spec with a test list.")
        drive(engine, until=tid(engine, "software-spec"))
        report = run_seat(engine, "software-spec", "requirements", "sw_spec.md", "software_architecture", spec,
                          tmp_path)
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_and_approve(engine, "software-spec")

        refused = run_seat(engine, "test-list", "software-spec", "plan.json", "verification_plan", dump(plan),
                           tmp_path)
        assert refused.status is ResultStatus.REFUSED  # "warning-free" is not a kind yet
        assert "unknown verification-item kind 'warning-free'" in check_run(engine).summary

        engineering.register_item_kind(ItemKind("warning-free", ("fw.build",), "a strict, warning-free build"))
        report = run_seat(engine, "test-list", "software-spec", "plan.json", "verification_plan", dump(plan),
                          tmp_path)
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_and_approve(engine, "test-list")
        spec_art = engine.task(tid(engine, "software-spec")).artifacts[0]
        assert {r.source for r in engine.state.spec_requirements.values()} == {spec_art}
        assert engine.state.verification_items["build-clean"].kind == "warning-free"
        assert [r.requirement for r in engineering.unbacked_requirements(engine.state)] == ["TMR-CLEAN", "TMR-LOAD"]
    finally:
        unregister_extension("test-planned-software")
        engineering.unregister_item_kind("warning-free")


# --- Laws ---------------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_import_laws_hold():
    for path in (SRC / "vplan.py", SRC / "integrations" / "vplan.py"):
        assert not any(m == "veritriage" or m.startswith("veritriage.") for m in _imports(path)), path
    # The runtime, the engine, and the policy name no plan kind, capability, stage, or tool.
    names = ("verification_plan", "vplan", "dv.plan", "dv-plan", "interface_spec")
    for path in [*sorted((SRC / "runtime").glob("*.py")), SRC / "work" / "engine.py", SRC / "work" / "policy.py",
                 *sorted((SRC / "orchestrator").glob("*.py"))]:
        text = path.read_text()
        assert not any(n in text for n in names), path


def test_no_model_api_is_called(axi, monkeypatch):
    engine, rtl = axi

    def refuse(*a, **k):
        raise AssertionError("a model was called")

    trap = types.ModuleType("anthropic")
    trap.__getattr__ = refuse
    monkeypatch.setitem(sys.modules, "anthropic", trap)
    import nirmaan.integrations.veritriage as bridge

    monkeypatch.setattr(bridge, "generate", refuse)
    monkeypatch.setattr(bridge, "ground", refuse)
    vplan.import_plan(engine, importer(engine, rtl), dump(import_doc(engine, rtl)))
    vplan.export_plan(engine.state)
    vplan.check_against_specs(vplan.parse(PLAN_FILE.read_text()), {"interface_spec.md": SPEC_FILE.read_text()})
