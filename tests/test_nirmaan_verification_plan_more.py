"""Milestone 38: checked plans on ``new-ip`` and ``feature-addition``, and amending a recorded plan.

The ``dv-plan`` stage of both workflows now writes a ``nirmaan.vplan`` file
that a real ``vplan.check`` holds to the approved requirements spec before
review, and approval records it, so ``nirmaan gaps`` answers from it. A later
plan version (from a seat, or ``nirmaan vplan import --amend``) adds,
modifies, and retires requirements and items through the same check and the
same approval; the versions it supersedes stay on the audit trail. An import
may plan items whose files are not recorded yet, as the seat does.

Nothing here makes a requirement backed: only a passing, cited run does (M24).
No test calls a model API.
"""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import FIXTURES, drive, human, tid, work
from test_nirmaan_engineering_graph import (  # noqa: F401  (fake_eda and axi are fixtures)
    AXI,
    AXI_BLOCK,
    answer,
    art_of,
    axi,
    axi_files,
    fake_eda,
    needs,
    run_rtl_seat,
    token,
)
from test_nirmaan_verification_plan import (
    check_run,
    dump,
    fixture_plan,
    import_doc,
    importer,
    review_and_approve,
    run_seat,
    spec_id,
)

from nirmaan import engineering, vplan
from nirmaan.company.traceability import ItemKind
from nirmaan.models import MemoryScope, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, run_task
from nirmaan.work import ProjectStore, TaskEngine
from nirmaan.work.audit import verify_chain
from nirmaan.work.engine import WorkError

SRC = Path(__file__).resolve().parents[1] / "src" / "nirmaan"
NEW_IP = "Create a 4-port AXI-to-NoC bridge."
FEATURE = "Add QoS arbitration to an existing NoC router."
VPLAN = FIXTURES / "vplan"
COUNTER_PLAN = VPLAN / "verification_plan.json"
PROSE = "# Verification plan\n\nAXI and NoC ports, one test per channel.\n"
RTL = FIXTURES / "rtl"


def counter_plan() -> dict:
    return json.loads(COUNTER_PLAN.read_text())


def at_plan_seat(org, clock, request: str):
    engine = Orchestrator(org, clock=clock).plan(request)
    drive(engine, until=tid(engine, "dv-plan"))
    assert engine.task(tid(engine, "dv-plan")).status is TaskStatus.READY
    return engine


def cites(engine) -> str:
    """The stage whose approved requirements spec the plan seat cites."""
    return "requirements" if tid(engine, "requirements") in engine.state.tasks else "requirements-delta"


# --- 1. The plan seat on new-ip and feature-addition -----------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_a_new_ip_plan_is_checked_recorded_and_feeds_gaps(nirmaan_org, fixed_clock, tmp_path):
    from nirmaan.cli import app

    engine = at_plan_seat(nirmaan_org, fixed_clock, NEW_IP)
    seat = tid(engine, "dv-plan")
    spec = engine.state.artifacts[engine.task(tid(engine, "requirements")).artifacts[0]]
    report = run_seat(engine, "dv-plan", "requirements", "verification_plan.json", "verification_plan",
                      COUNTER_PLAN.read_text(), tmp_path)
    assert report.status is ResultStatus.SUBMITTED, report.detail
    run = check_run(engine)
    assert run.succeeded and "3 of 3" in run.summary and "CNT-SYNTH" in run.summary
    assert Path(run.params["spec"]).read_bytes() == (VPLAN / "requirements_spec.md").read_bytes()
    assert engine.state.spec_requirements == {}  # nothing before approval
    review_and_approve(engine, "dv-plan")
    plan_art = engine.task(seat).artifacts[0]
    assert sorted(engine.state.spec_requirements) == ["CNT-COUNT", "CNT-RESET", "CNT-SYNTH"]
    assert {r.source for r in engine.state.spec_requirements.values()} == {spec.id}
    item = engine.state.verification_items["tb-count"]
    assert (item.file, item.plan, item.artifact) == ("counter_tb.v", plan_art, "")

    # The RTL seat writes the testbench the plan names; the real simulation backs what it proves.
    rtl = tid(engine, "rtl-implementation.axi")
    engine.remember(MemoryScope.TASK, rtl, "input.workspace", str(tmp_path / "rtl"), human(engine.task(rtl).owner))
    micro = engine.task(tid(engine, "microarchitecture")).artifacts[0]
    files = [("counter.v", "rtl_source", "counter", (RTL / "counter.v").read_text()),
             ("counter_tb.v", "testbench", "counter_tb", (RTL / "counter_tb.v").read_text())]
    assert run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(files, token(micro))]))).status \
        is ResultStatus.SUBMITTED
    review_and_approve(engine, "rtl-implementation.axi")
    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert {r for r, s in status.items() if s.backed} == {"CNT-COUNT", "CNT-RESET"}
    sim = engine.state.tool_runs[status["CNT-COUNT"].items[0].run]
    assert sim.tool == "simulator.run" and sim.succeeded
    assert status["CNT-SYNTH"].reasons == ("no verification item is recorded as proving it",)

    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    result = CliRunner().invoke(app, ["gaps", engine.state.project.id, "--root", str(root)])
    assert result.exit_code == 1 and "2 of 3 recorded requirements are backed" in result.output
    assert "CNT-SYNTH" in result.output


@pytest.mark.parametrize("request_text", [NEW_IP, FEATURE], ids=["new-ip", "feature-addition"])
def test_old_flows_are_migrated_without_weakening_them(nirmaan_org, fixed_clock, tmp_path, request_text):
    # The stage is checked on every request, not only one that asks for a plan.
    engine = at_plan_seat(nirmaan_org, fixed_clock, request_text)
    seat = engine.task(tid(engine, "dv-plan"))
    check = next(r for r in seat.evidence_requirements if r.before_review)
    assert check.tools == ("vplan.check",)
    assert {(b.param, b.kinds, b.upstream) for b in check.files} == {
        ("plan", ("verification_plan",), False), ("spec", ("requirements_spec",), True)}
    assert tid(engine, cites(engine)) in seat.depends_on or any(
        engine.task(d).kind.value == "gate" and tid(engine, cites(engine)) in engine.task(d).depends_on
        for d in seat.depends_on)
    assert any(seat.id in t.depends_on for t in engine.state.tasks.values())  # work still waits on the plan

    # A prose plan, as these stages wrote before M38, no longer reaches review.
    report = run_seat(engine, "dv-plan", cites(engine), "verification_plan.md", "verification_plan", PROSE,
                      tmp_path)
    assert report.status is ResultStatus.REFUSED
    assert not check_run(engine).succeeded and engine.task(seat.id).status is TaskStatus.IN_PROGRESS
    assert engine.state.spec_requirements == {}

    # The migrated drive writes a tagged requirements spec and a plan file, and passes the real check.
    fresh = at_plan_seat(nirmaan_org, fixed_clock, request_text)
    work(fresh, tid(fresh, "dv-plan"), workspace=tmp_path / "drive")
    assert fresh.task(tid(fresh, "dv-plan")).status is TaskStatus.COMPLETED
    assert check_run(fresh).succeeded
    assert sorted(fresh.state.spec_requirements) == ["CNT-COUNT", "CNT-RESET", "CNT-SYNTH"]


# --- 2. Amending a recorded plan --------------------------------------------------------------


def amended(engine, rtl: str) -> dict:
    """Version 2 of the axi plan: modify, retire (a backed requirement), and add."""
    plan = import_doc(engine, rtl)
    latency = next(r for r in plan["requirements"] if r["id"] == "AXIL-LATENCY")
    latency["text"] = "The bound is at most 2 cycles for writes and reads, from reset."
    plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "AXIL-SLVERR"]
    plan["requirements"].append({"id": "AXIL-IRQ", "text": "An interrupt is raised on a write to REG3.",
                                 "source": spec_id(engine), "section": "9"})
    plan["items"] = [i for i in plan["items"] if i["id"] != "tb-slverr"]
    next(i for i in plan["items"] if i["id"] == "cov-b2b")["rationale"] = "Needs a coverage measurement."
    plan["items"].append({"id": "tb-irq", "kind": "test", "file": "axi4_lite_regs_tb.v", "name": "irq fires",
                          "proves": ["AXIL-IRQ"], "rationale": ""})
    plan["retired"] = [{"requirement": "AXIL-SLVERR", "reason": "Unmapped accesses move to the bus fabric."},
                       {"item": "tb-slverr", "reason": "Its requirement is retired."}]
    return plan


def test_an_amendment_adds_modifies_and_retires_with_history_kept(axi):
    engine, rtl = axi
    actor = importer(engine, rtl)
    vplan.import_plan(engine, actor, dump(import_doc(engine, rtl)))
    v1 = engine.state
    backed = {r.requirement for r in engineering.requirement_coverage(v1) if r.backed}
    assert "AXIL-SLVERR" in backed  # retiring backed work is allowed, and recorded with its reason

    report = vplan.amend_plan(engine, actor, dump(amended(engine, rtl)))
    assert (report.added, report.modified, report.retired) == (
        ("AXIL-IRQ", "tb-irq"), ("AXIL-LATENCY", "cov-b2b"), ("AXIL-SLVERR", "tb-slverr"))
    reqs, items = engine.state.spec_requirements, engine.state.verification_items
    assert reqs["AXIL-SLVERR"].retired == "Unmapped accesses move to the bus fabric."  # kept, marked
    assert reqs["AXIL-SLVERR"].revision == 2 and items["tb-slverr"].retired
    assert reqs["AXIL-LATENCY"].revision == 2 and reqs["AXIL-ORDER"].revision == 1

    # History: nothing deleted; every superseded version is on the audit trail, whole.
    assert engine.state.audit[:len(v1.audit)] == v1.audit and verify_chain(engine.state.audit) == []
    versions = vplan.history(engine.state, "AXIL-LATENCY")
    assert [v.revision for v in versions] == [1, 2]
    assert versions[0] == v1.spec_requirements["AXIL-LATENCY"] and versions[1] == reqs["AXIL-LATENCY"]
    retire = next(e for e in engine.state.audit if e.action == "trace.requirement.retire")
    assert retire.subject == "AXIL-SLVERR" and retire.reason == reqs["AXIL-SLVERR"].retired
    assert retire.details["backed_by"]  # the passing run it had, named
    assert vplan.history(engine.state, "tb-slverr", "item")[0] == v1.verification_items["tb-slverr"]

    # gaps reads the current version: the retired requirement is neither counted nor a gap.
    coverage = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert "AXIL-SLVERR" not in coverage and "AXIL-IRQ" in coverage and len(coverage) == 8
    assert not coverage["AXIL-IRQ"].backed and "does not occur" in coverage["AXIL-IRQ"].reasons[0]
    graph = engineering.engineering_graph(engine.state)
    assert "tb-slverr" not in {n["id"] for n in graph["nodes"]}
    exported = json.loads(vplan.export_plan(engine.state))
    assert "AXIL-SLVERR" not in {r["id"] for r in exported["requirements"]} and "retired" not in exported

    # The same version again changes nothing; a retired ID is never reused.
    count = len(engine.state.audit)
    again = amended(engine, rtl)
    again["retired"] = []
    assert vplan.amend_plan(engine, actor, dump(again)).added == ()
    assert len(engine.state.audit) == count
    reuse = amended(engine, rtl)
    reuse["retired"] = []
    reuse["requirements"].append({"id": "AXIL-SLVERR", "text": "x", "source": spec_id(engine)})
    with pytest.raises(vplan.PlanError, match="never reused"):
        vplan.amend_plan(engine, actor, dump(reuse))


def test_an_amendment_must_account_for_every_record(axi):
    engine, rtl = axi
    actor = importer(engine, rtl)
    vplan.import_plan(engine, actor, dump(import_doc(engine, rtl)))
    before = engine.state
    dropped = import_doc(engine, rtl)
    dropped["items"] = [i for i in dropped["items"] if i["id"] != "tb-wstrb"]  # silently dropped
    with pytest.raises(vplan.PlanError, match="tb-wstrb is recorded and not in this plan"):
        vplan.amend_plan(engine, actor, dump(dropped))
    assert engine.state is before
    # A plain import still only adds, and refuses a retirement.
    with pytest.raises(vplan.PlanError, match="--amend"):
        vplan.import_plan(engine, actor, dump(amended(engine, rtl)))
    assert engine.state is before


def test_retiring_needs_a_reason(axi):
    engine, rtl = axi
    actor = importer(engine, rtl)
    vplan.import_plan(engine, actor, dump(import_doc(engine, rtl)))
    before = engine.state
    plan = amended(engine, rtl)
    plan["retired"][0]["reason"] = "  "
    text = dump(plan)
    line = next(n for n, l in enumerate(text.splitlines(), 1) if '"reason": "  "' in l)
    with pytest.raises(vplan.PlanError) as refused:
        vplan.amend_plan(engine, actor, text)
    assert f"line {line}: reason must be a non-empty string" in refused.value.problems
    del plan["retired"][1]["reason"]
    with pytest.raises(vplan.PlanError, match="has no 'reason'"):
        vplan.amend_plan(engine, actor, dump(plan))
    assert engine.state is before
    with pytest.raises(WorkError, match="reason"):  # the engine refuses it too
        engine.retire_spec_requirement(actor, "AXIL-SYNTH", " ")
    with pytest.raises(WorkError, match="tb-top"):  # and keeps no active item proving a retired requirement
        engine.retire_spec_requirement(actor, "AXIL-RESET", "dropped")
    assert engine.state is before


def test_an_amendment_that_misses_a_spec_requirement_is_refused(nirmaan_org, fixed_clock, fake_eda, tmp_path):
    """On import: the spec is a recorded, tagged file, so the seat's check applies to the amendment too."""
    engine = located_spec(nirmaan_org, fixed_clock, tmp_path)
    actor = human(engine.task(tid(engine, "interface-spec")).owner)
    vplan.import_plan(engine, actor, dump(fixture_plan()))
    before = engine.state
    plan = fixture_plan()
    plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "AXIL-FORMAL"]
    plan["retired"] = [{"requirement": "AXIL-FORMAL", "reason": "No formal tool on this project."}]
    with pytest.raises(vplan.PlanError) as refused:
        vplan.amend_plan(engine, actor, dump(plan))
    assert any("AXIL-FORMAL is not in the plan" in p for p in refused.value.problems)
    assert engine.state is before


# --- 3. Planned items in an import ------------------------------------------------------------


def located_spec(org, clock, tmp_path):
    """The AXI4-Lite block (no plan stage) with its interface spec written by the seat and approved."""
    engine = Orchestrator(org, clock=clock).plan(AXI_BLOCK)
    drive(engine, until=tid(engine, "interface-spec"))
    report = run_seat(engine, "interface-spec", "requirements", "interface_spec.md", "interface_spec",
                      (AXI / "interface_spec.md").read_text(), tmp_path)
    assert report.status is ResultStatus.SUBMITTED, report.detail
    review_and_approve(engine, "interface-spec")
    return engine


def test_an_import_plans_items_whose_files_are_not_recorded_yet(nirmaan_org, fixed_clock, fake_eda, tmp_path):
    engine = located_spec(nirmaan_org, fixed_clock, tmp_path)
    spec = engine.task(tid(engine, "interface-spec")).artifacts[0]
    actor = human(engine.task(tid(engine, "interface-spec")).owner)
    report = vplan.import_plan(engine, actor, dump(fixture_plan()))
    assert (report.requirements, report.items) == (8, 6)
    items = engine.state.verification_items
    assert {(i.file, i.plan, i.artifact) for i in items.values()} == {("axi4_lite_regs_tb.v", spec, "")}
    assert {e.actor for e in engine.state.audit if e.action == "trace.item"} == {actor.label}
    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert "no recorded artifact holds axi4_lite_regs_tb.v yet" in status["AXIL-SLVERR"].items[0].reason

    rtl = run_rtl_seat(engine, tmp_path, axi_files())  # the file arrives; the items bind to it
    tb = art_of(engine, rtl, "testbench")
    status = {r.requirement: r for r in engineering.requirement_coverage(engine.state)}
    assert status["AXIL-SLVERR"].backed and status["AXIL-SLVERR"].items[0].artifact == tb.id


def test_an_unplannable_item_is_refused_with_its_line(axi):
    engine, rtl = axi  # the spec here is a driven artifact with no file: nothing to attribute a plan to
    before = engine.state
    plan = import_doc(engine, rtl)
    plan["items"][2]["file"] = "nowhere.v"
    plan["items"][3]["file"] = "sim/elsewhere_tb.v"
    with pytest.raises(vplan.PlanError) as refused:
        vplan.import_plan(engine, importer(engine, rtl), dump(plan))
    joined = "\n".join(refused.value.problems)
    assert "nowhere.v" in joined and "no recorded file" in joined and "sim/elsewhere_tb.v" in joined
    assert all(p.startswith("line ") for p in refused.value.problems)
    assert engine.state is before


# --- 4. The CLI ----------------------------------------------------------------------------------


def test_the_cli_amends_and_gaps_reads_the_current_version(axi, tmp_path):
    from nirmaan.cli import app

    engine, rtl = axi
    root = tmp_path / "store"
    vplan.import_plan(engine, importer(engine, rtl), dump(import_doc(engine, rtl)))
    ProjectStore(root).save(engine.state)
    project, role = engine.state.project.id, importer(engine, rtl).role
    v2 = tmp_path / "v2.json"
    v2.write_text(dump(amended(engine, rtl)))
    plain = CliRunner().invoke(app, ["vplan", "import", project, str(v2), "--as", role, "--root", str(root)])
    assert plain.exit_code == 1 and "--amend" in plain.output
    result = CliRunner().invoke(app, ["vplan", "import", project, str(v2), "--as", role, "--amend",
                                      "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "added 2" in result.output and "modified 2" in result.output and "retired 2" in result.output
    gaps = CliRunner().invoke(app, ["gaps", project, "--root", str(root)])
    assert "4 of 8 recorded requirements are backed" in gaps.output and "AXIL-SLVERR" not in gaps.output


# --- 5. Crown jewel ---------------------------------------------------------------------------------


def test_a_replan_stage_amending_the_plan_needs_no_core_changes(fixed_clock, tmp_path):
    """A workflow added by extension plans against a spec, revises the spec, and re-plans.

    The re-plan retires, modifies, and adds through the same check and approval, with a newly
    registered item kind. Nothing in the engine, runtime, policy, broker, or vplan changes.
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

    M = Criticality.MEDIUM
    reviewed = EvidenceRequirement(description="Independent review recorded", accepts=(EvidenceKind.REVIEW_RECORD,))

    def plan_check() -> EvidenceRequirement:
        return EvidenceRequirement(description="The plan covers the approved software spec",
                                   accepts=(EvidenceKind.TOOL_RUN,), tools=("vplan.check",),
                                   files=(FileInput(param="plan", kinds=("verification_plan",)),
                                          FileInput(param="spec", kinds=("software_architecture",), upstream=True)),
                                   before_review=True)

    def stage(id: str, capability: str, after: tuple[str, ...], output: str, review: str, *evidence):
        return StageTemplate(id=id, title=id, phase="Verification", capability=capability, depends_on=after,
                             criticality=M, review=ReviewRequirement(capability=review), outputs=(output,),
                             evidence=(reviewed, *evidence))

    @register_extension("test-replanned-software")
    def replanned(b):
        b.add(
            IntentRule(intent="replanned_software", patterns=(r"\bre-planned test list\b",), priority=5),
            WorkflowTemplate(
                id="replanned-software", name="Re-planned software spec", description="A spec, a plan, again.",
                intents=("replanned_software",),
                stages=(
                    stage("requirements", "req.analyze", (), "requirements_spec", "req.review"),
                    stage("software-spec", "arch.software", ("requirements",), "software_architecture",
                          "arch.review"),
                    stage("test-list", "dv.plan", ("software-spec",), "verification_plan", "dv.review",
                          plan_check()),
                    stage("spec-update", "arch.software", ("test-list",), "software_architecture", "arch.review"),
                    stage("test-list-update", "dv.plan", ("spec-update",), "verification_plan", "dv.review",
                          plan_check()),
                ),
            ),
        )

    spec1 = ("# Timer driver\n\n## 1. API\n\n* `timer_load` writes the reload value. [req:TMR-LOAD]\n"
             "* The driver builds with no warnings. [req:TMR-CLEAN]\n")
    spec2 = ("# Timer driver\n\n## 1. API\n\n* `timer_load` writes the reload value. [req:TMR-LOAD]\n"
             "* The timer raises `irq` when it reaches zero. [req:TMR-IRQ]\n")
    plan1 = {"format": "nirmaan.vplan", "version": 1,
             "requirements": [
                 {"id": "TMR-CLEAN", "text": "The driver builds with no warnings.", "source": "sw_spec.md",
                  "section": "1"},
                 {"id": "TMR-LOAD", "text": "`timer_load` writes the reload value.", "source": "sw_spec.md",
                  "section": "1"}],
             "items": [
                 {"id": "build-clean", "kind": "test", "file": "timer.c", "name": "timer_load",
                  "proves": ["TMR-CLEAN"], "rationale": ""},
                 {"id": "load-test", "kind": "test", "file": "timer_test.c", "name": "load_test",
                  "proves": ["TMR-LOAD"], "rationale": ""}]}
    plan2 = {"format": "nirmaan.vplan", "version": 1,
             "requirements": [
                 {"id": "TMR-IRQ", "text": "The timer raises `irq` when it reaches zero.", "source": "sw_spec.md",
                  "section": "1"},
                 plan1["requirements"][1]],
             "items": [
                 {"id": "irq-fires", "kind": "irq-check", "file": "timer_test.c", "name": "irq_test",
                  "proves": ["TMR-IRQ"], "rationale": "the interrupt line, observed"},
                 {**plan1["items"][1], "rationale": "load, then read back"}]}
    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a timer software spec with a re-planned test list.")
        drive(engine, until=tid(engine, "software-spec"))
        for stage_id, cited, path, kind, content in (
                ("software-spec", "requirements", "sw_spec.md", "software_architecture", spec1),
                ("test-list", "software-spec", "plan.json", "verification_plan", dump(plan1)),
                ("spec-update", "test-list", "sw_spec.md", "software_architecture", spec2)):
            report = run_seat(engine, stage_id, cited, path, kind, content, tmp_path)
            assert report.status is ResultStatus.SUBMITTED, report.detail
            review_and_approve(engine, stage_id)
        v1 = engine.state
        assert sorted(v1.spec_requirements) == ["TMR-CLEAN", "TMR-LOAD"]

        # A version that drops recorded work without retiring it is refused before review.
        engineering.register_item_kind(ItemKind("irq-check", ("fw.soc_test",), "an interrupt observed on a core"))
        refused = run_seat(engine, "test-list-update", "spec-update", "plan.json", "verification_plan",
                           dump(plan2), tmp_path)
        assert refused.status is ResultStatus.REFUSED
        assert "TMR-CLEAN is recorded and not in this plan" in check_run(engine).summary

        plan2["retired"] = [{"requirement": "TMR-CLEAN", "reason": "The spec no longer requires it."},
                            {"item": "build-clean", "reason": "Its requirement is retired."}]
        report = run_seat(engine, "test-list-update", "spec-update", "plan.json", "verification_plan",
                          dump(plan2), tmp_path)
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_and_approve(engine, "test-list-update")

        reqs, items = engine.state.spec_requirements, engine.state.verification_items
        new_spec = engine.task(tid(engine, "spec-update")).artifacts[0]
        new_plan = engine.task(tid(engine, "test-list-update")).artifacts[0]
        assert reqs["TMR-CLEAN"].retired == "The spec no longer requires it." and items["build-clean"].retired
        assert reqs["TMR-LOAD"].source == new_spec and reqs["TMR-LOAD"].revision == 2
        assert items["irq-fires"].kind == "irq-check" and items["irq-fires"].plan == new_plan
        assert items["load-test"].rationale == "load, then read back"
        assert [v.source for v in vplan.history(engine.state, "TMR-LOAD")] == [
            v1.spec_requirements["TMR-LOAD"].source, new_spec]
        amends = [e for e in engine.state.audit[len(v1.audit):] if e.action.startswith("trace.")]
        assert {e.actor for e in amends} == {engine.system.label} and all(e.details["plan"] == new_plan
                                                                          for e in amends)
        assert [r.requirement for r in engineering.unbacked_requirements(engine.state)] == ["TMR-IRQ", "TMR-LOAD"]
    finally:
        unregister_extension("test-replanned-software")
        engineering.unregister_item_kind("irq-check")


# --- 6. Laws ----------------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_import_laws_hold():
    for path in (SRC / "vplan.py", SRC / "integrations" / "vplan.py", SRC / "engineering.py"):
        assert not any(m == "veritriage" or m.startswith("veritriage.") for m in _imports(path)), path
    names = ("verification_plan", "vplan", "dv.plan", "dv-plan", "requirements_spec", "interface_spec")
    for path in [*sorted((SRC / "runtime").glob("*.py")), SRC / "work" / "engine.py", SRC / "work" / "policy.py",
                 *sorted((SRC / "orchestrator").glob("*.py"))]:
        text = path.read_text()
        assert not any(n in text for n in names), path


def test_the_contract_scan_holds(nirmaan_org):
    from nirmaan.models import ToolStatus
    from nirmaan.runtime import available_bindings

    spec = nirmaan_org.tools["vplan.check"]
    assert spec.status is ToolStatus.AVAILABLE and "vplan.check" in available_bindings()
    assert {p.name for p in spec.params} == {"plan", "spec"}
    read = set(__import__("re").findall(r"""params\.get\(['"]([a-z_]+)['"]""",
                                        (SRC / "integrations" / "vplan.py").read_text()))
    assert read == {"plan", "spec"}
    # Every check the two workflows now carry names a tool that really runs here.
    for wf in ("new-ip", "feature-addition"):
        stage = nirmaan_org.workflows[wf].stage("dv-plan")
        for req in (r for r in stage.evidence if r.before_review):
            assert all(nirmaan_org.tools[t].status is ToolStatus.AVAILABLE for t in req.tools)


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
    actor = importer(engine, rtl)
    vplan.import_plan(engine, actor, dump(import_doc(engine, rtl)))
    vplan.amend_plan(engine, actor, dump(amended(engine, rtl)))
    vplan.history(engine.state, "AXIL-LATENCY")
    TaskEngine(engine.org, engine.state)
