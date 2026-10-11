"""Milestone 27: the design gates on every RTL workflow, and proofs that are not vacuous.

The RTL stages of ``new-ip``, ``feature-addition``, and ``rtl-change`` now
carry the same before-review checks as ``block-design``: approved inputs only,
real lint and simulation, synthesis with no latches, and, when the seat writes
a ``.sby``, a proof that passes and a cover run that reaches every cover under
the same assumptions. All of it is data on the stages. Real-tool tests skip
when an executable is absent, or fail when CI names it in NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import GATE_TOOLS, agent, drive, human, tid
from test_nirmaan_design_agents import (
    AXI,
    RTL,
    answer,
    counter_files,
    token,
    upstream,
    with_workspace,
)
from test_nirmaan_formal_gate import COUNTER, COUNTER_SBY, FORMAL, runs_of, sby_file
from laws import needs

from nirmaan.integrations.eda_parsers import parse_sby_cover
from nirmaan.models import Assurance, DecisionKind, EscalationKind, EvidenceKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import (
    MockLLM,
    ModelRuntime,
    ResultStatus,
    ToolBroker,
    assemble,
    render_work_prompt,
    review_task,
    run_task,
)
from nirmaan.work import PolicyViolationError
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
NEW_IP = "Create a 4-port AXI-to-NoC bridge."
FEATURE = "Add QoS arbitration to an existing NoC router."
CHANGE = "Fix the RTL bug in the timer."
#: Each request, the workflow it plans, its RTL task, and the stage whose approved output the RTL cites.
FLOWS = {
    NEW_IP: ("new-ip", "rtl-implementation.axi", "microarchitecture"),
    FEATURE: ("feature-addition", "rtl-change.arbitration", "microarchitecture"),
    CHANGE: ("rtl-change", "change", "impact"),
}
SYNTH = "Synthesizes with Yosys, with no latches"
NOT_VACUOUS = "The proof is not vacuous: every cover is reached"
ALL_CHECKS = {"lint.run", "simulator.run", "synth.run", "formal.run", "formal.cover"}
FORMAL_TOOLS = ("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")


def with_formal(rtl: str, text: str) -> str:
    """The RTL with ``text`` added to its formal section."""
    at = rtl.rindex("`endif\nendmodule")
    return rtl[:at] + text + rtl[at:]


def without_covers(rtl: str) -> str:
    start = rtl.index("    // Cover (M27)")
    return rtl[:start].rstrip() + "\n" + rtl[rtl.rindex("`endif\nendmodule"):]


@pytest.fixture(params=list(FLOWS), ids=[FLOWS[r][0] for r in FLOWS])
def gated(request, nirmaan_org, fixed_clock, tmp_path):
    """Each workflow at its RTL seat, upstream approved, with a workspace and a citation."""
    workflow, stage, source = FLOWS[request.param]
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request.param)
    assert engine.state.project.workflows == (workflow,)
    rtl = tid(engine, stage)
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "work")
    return engine, rtl, token(upstream(engine, source))


# --- The stages, as data ---------------------------------------------------------------------


def test_every_rtl_workflow_carries_the_block_design_gates():
    from nirmaan.company.workflows import BLOCK_DESIGN, RTL_GATES, WORKFLOWS

    block = BLOCK_DESIGN.stage("rtl-implementation")
    # One set of checks, the same everywhere; block-design adds the register map's when one is approved (M41).
    assert block.evidence[1:-1] == RTL_GATES and block.evidence[-1].tools == ("regmap.verify",)
    flows = {wf.id: wf for wf in WORKFLOWS}
    for workflow, stage, _ in FLOWS.values():
        rtl = flows[workflow].stage(stage.split(".")[0])
        assert rtl.capability == "rtl.implement"
        assert rtl.evidence[1:] == RTL_GATES, workflow
        assert set(rtl.outputs) == {"rtl_source", "testbench"}
    cover = next(r for r in RTL_GATES if r.description == NOT_VACUOUS)
    assert cover.before_review and cover.tools == ("formal.cover",) and cover.when_produced == ("formal_spec",)
    assert [(b.param, b.kinds) for b in cover.files] == [("sby", ("formal_spec",)), ("sources", ("rtl_source",))]


def test_the_planned_rtl_tasks_are_gated_and_build_only_on_approved_inputs(gated, nirmaan_org):
    engine, rtl, cite = gated
    task = engine.task(rtl)
    assert nirmaan_org.capabilities[task.capability].approved_inputs
    assert {t for r in task.evidence_requirements if r.before_review for t in r.tools} == ALL_CHECKS
    unmet = unsatisfied_requirements(engine.state, task)
    assert SYNTH in unmet and FORMAL not in unmet and NOT_VACUOUS not in unmet  # formal only with a .sby
    text = render_work_prompt(assemble(engine, rtl)).render()
    assert NOT_VACUOUS in text and "applies only if you produce a formal_spec file" in text
    assert cite in text  # the approved upstream reaches the seat, even from behind a gate


def test_approved_inputs_are_checked_through_a_gate(nirmaan_org, fixed_clock):
    """new-ip's RTL waits on the architecture gate: the microarchitecture behind it must be approved."""
    from nirmaan.work.policy import PolicyContext, PolicyEngine, upstream_artifacts

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(NEW_IP)
    workflow, stage, source = FLOWS[NEW_IP]
    rtl = tid(engine, stage)
    drive(engine, until=rtl)
    task = engine.task(rtl)
    assert all(engine.task(d).kind.value == "gate" for d in task.depends_on)
    behind = upstream(engine, source)
    assert [a.id for a in upstream_artifacts(engine.state, task)] == [behind]

    state = engine.state.model_copy(deep=True)
    state.artifacts[behind] = state.artifacts[behind].model_copy(update={"assurance": Assurance.EXECUTED})
    ctx = PolicyContext(nirmaan_org, state, "task.start", agent(task.owner), task)
    problems = [v.message for v in PolicyEngine(nirmaan_org).evaluate(ctx) if v.check == "approved-inputs"]
    assert problems and "executed, not approved" in problems[0]


def test_an_unapproved_impact_analysis_cannot_start_an_rtl_change(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(CHANGE)
    impact, change = tid(engine, "impact"), tid(engine, "change")
    drive(engine, until=impact)
    owner = agent(engine.task(impact).owner)
    engine.start(impact, owner)
    engine.submit(impact, owner, [{"kind": "impact_analysis", "title": "Draft impact"}])
    engine.escalate(impact, owner, EscalationKind.TECHNICAL, reason="withdrawn before review")
    task = engine.task(impact)
    authority = AuthorityService(engine.org)
    manager = next(r for r in task.escalation_path
                   if authority.check(r, DecisionKind.CANCEL_TASK, task.criticality, task.unit).allowed)
    engine.cancel(impact, human(manager), "withdrawn")
    assert engine.task(change).status is TaskStatus.READY

    llm = MockLLM()
    with pytest.raises(PolicyViolationError, match=r"P8.*executed, not approved"):
        run_task(engine, change, ModelRuntime(llm))
    assert llm.calls == [] and engine.state.tool_runs == {}


# --- The gates keep bad RTL from review, on every workflow ----------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_a_latch_in_an_rtl_answer_blocks_review(gated):
    engine, rtl, cite = gated
    latch = COUNTER.replace(
        "    assign wrap = en && (count == LIMIT);\n",
        "    reg wrap_l;\n    /* verilator lint_off LATCH */\n    always @(*)\n        if (en)\n"
        "            wrap_l = (count == LIMIT);\n    /* verilator lint_on LATCH */\n"
        "    assign wrap = en && wrap_l;\n")
    assert latch != COUNTER
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite, latch))])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail and SYNTH in report.detail
    runs = runs_of(engine, report)
    assert runs["lint.run"].succeeded and runs["simulator.run"].succeeded
    assert not runs["synth.run"].succeeded and "latches 1 exceeds max_latches 0" in runs["synth.run"].summary
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()


@needs("verilator", "iverilog", "vvp", "yosys")
def test_a_failing_self_check_blocks_review(gated):
    engine, rtl, cite = gated
    src, tb = counter_files(cite)
    failing = {**tb, "content": (RTL / "counter_tb_fail.v").read_text()}
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(src, failing)])))

    assert report.status is ResultStatus.REFUSED and "Self-checking simulation passes" in report.detail
    assert not runs_of(engine, report)["simulator.run"].succeeded
    assert engine.task(rtl).artifacts == ()


@needs(*FORMAL_TOOLS)
def test_clean_rtl_with_a_proof_reaches_review_and_approval(gated):
    engine, rtl, cite = gated
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite), sby_file(cite))])))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    runs = runs_of(engine, report)
    assert set(runs) == ALL_CHECKS and all(r.succeeded for r in runs.values())
    task = engine.task(rtl)
    arts = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in task.artifacts}
    assert runs["formal.cover"].params["sby"] == arts["formal_spec"].location
    assert runs["formal.cover"].params["sources"] == (arts["rtl_source"].location,)
    assert unsatisfied_requirements(engine.state, task) == ["Independent review recorded"]
    review_task(engine, rtl, ModelRuntime(MockLLM()))
    engine.approve(rtl, human(task.approver), "gated, proven, not vacuous")
    assert engine.task(rtl).status is TaskStatus.COMPLETED
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)


# --- Vacuous proofs are refused --------------------------------------------------------------------


VACUOUS = {
    # An input that is never raised: the counter never counts, so nothing is ever checked.
    "over-constrained": "    always @(*)\n        assume (!en);\n",
    # Contradictory on the path to the interesting state: the proof never gets there.
    "contradictory": "    always @(*)\n        if (en && count == 4'd5)\n            assume (1'b0);\n",
}


@needs(*FORMAL_TOOLS)
@pytest.mark.parametrize("assumption", list(VACUOUS), ids=list(VACUOUS))
def test_a_vacuous_proof_is_refused_as_a_recorded_failed_run(counter_like_rtl, assumption):
    engine, rtl, cite = counter_like_rtl
    vacuous = with_formal(COUNTER, VACUOUS[assumption])
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(cite, vacuous), sby_file(cite))])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail and NOT_VACUOUS in report.detail
    runs = runs_of(engine, report)
    assert runs["formal.run"].succeeded  # the proof alone passes: that is the hole
    cover = runs["formal.cover"]
    assert not cover.succeeded and "vacuous: 1 of 1 cover never reached" in cover.summary
    metrics = json.loads(Path(cover.references[1]).read_text())["result"]["metrics"]
    assert metrics["covers_reached"] == 0 and metrics["covers_unreached"] == 1
    ev = next(engine.state.evidence[e] for e in report.evidence if engine.state.evidence[e].tool_run == cover.id)
    assert not ev.substantiated  # on the record, and it counts for nothing
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()


@needs(*FORMAL_TOOLS)
def test_assume_false_fails_the_proof_and_the_cover_run(counter_like_rtl):
    """Assumptions unsatisfiable from the first step: smtbmc already errors, and no cover is reached."""
    engine, rtl, cite = counter_like_rtl
    vacuous = with_formal(COUNTER, "    always @(*)\n        assume (1'b0);\n")
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(cite, vacuous), sby_file(cite))])))

    assert report.status is ResultStatus.REFUSED and FORMAL in report.detail and NOT_VACUOUS in report.detail
    runs = runs_of(engine, report)
    assert not runs["formal.run"].succeeded
    assert not runs["formal.cover"].succeeded and "never reached" in runs["formal.cover"].summary


@needs(*FORMAL_TOOLS)
def test_a_proof_with_no_covers_is_refused(counter_like_rtl):
    engine, rtl, cite = counter_like_rtl
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(cite, without_covers(COUNTER)), sby_file(cite))])))

    assert report.status is ResultStatus.REFUSED and NOT_VACUOUS in report.detail
    runs = runs_of(engine, report)
    assert runs["formal.run"].succeeded
    assert not runs["formal.cover"].succeeded and "no cover statement" in runs["formal.cover"].summary


@pytest.fixture()
def counter_like_rtl(nirmaan_org, fixed_clock, tmp_path):
    """The new-ip RTL seat, where the vacuity cases are submitted."""
    workflow, stage, source = FLOWS[NEW_IP]
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(NEW_IP)
    rtl = tid(engine, stage)
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "work")
    return engine, rtl, token(upstream(engine, source))


# --- Covers are reached on every fixture block -----------------------------------------------------


COVERED = [
    ("counter.sby", "counter.v", 1),
    ("axi4_lite/axi4_lite_regs.sby", "axi4_lite/axi4_lite_regs.v", 8),
    ("sync_fifo/sync_fifo.sby", "sync_fifo/sync_fifo.v", 6),
    ("sync_fifo/sync_fifo_depth5.sby", "sync_fifo/sync_fifo.v", 6),
    ("rr_arbiter/rr_arbiter.sby", "rr_arbiter/rr_arbiter.v", 8),
    ("rr_arbiter/rr_arbiter_n5.sby", "rr_arbiter/rr_arbiter.v", 10),
    ("apb_regs/apb_regs.sby", "apb_regs/apb_regs.v", 4),
]


@pytest.fixture()
def broker_owner(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(NEW_IP)
    rtl = tid(engine, FLOWS[NEW_IP][1])
    return engine, agent(engine.task(rtl).owner)


@needs("sby", "yosys", "yices-smt2")
@pytest.mark.parametrize("sby,source,covers", COVERED, ids=[c[0] for c in COVERED])
def test_every_fixture_proof_reaches_all_its_covers(broker_owner, tmp_path, sby, source, covers):
    engine, owner = broker_owner
    params = {"sby": str(RTL / sby), "sources": str(RTL / source), "workdir": str(tmp_path)}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert run.succeeded, run.summary
    metrics = json.loads(Path(run.references[1]).read_text())["result"]["metrics"]
    assert metrics["covers_reached"] == covers and metrics["covers_unreached"] == 0


@needs("sby", "yosys", "yices-smt2")
def test_the_cover_run_uses_the_seats_own_setup_and_writes_nothing_beside_it(broker_owner, tmp_path):
    engine, owner = broker_owner
    submitted = tmp_path / "attempt"
    submitted.mkdir()
    for name in ("counter.v", "counter.sby"):
        shutil.copy(RTL / name, submitted / name)
    before = sorted(p.name for p in submitted.iterdir())
    params = {"sby": str(submitted / "counter.sby"), "sources": str(submitted / "counter.v"),
              "workdir": str(tmp_path / "run")}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert run.succeeded, run.summary
    assert sorted(p.name for p in submitted.iterdir()) == before
    derived = (tmp_path / "run" / "counter_cover.sby").read_text()
    assert "mode cover" in derived and "mode prove" not in derived
    assert "depth 12" in derived and "read -formal counter.v" in derived  # the same bound and script
    # M29: the run reads a copy of the submitted RTL, made in its own directory, that differs only by
    # the cover derived for the assertion's antecedent, on the assertion's own line.
    copy = (tmp_path / "run" / "antecedents" / "counter.v").resolve()
    assert str(copy) in derived.splitlines()  # the [files] entry names the copy
    original, instrumented = (submitted / "counter.v").read_text().splitlines(), copy.read_text().splitlines()
    assert len(original) == len(instrumented)
    assert [(a, b) for a, b in zip(original, instrumented) if a != b] == [
        ("            assert (count <= LIMIT);", "            begin cover (1'b1); assert (count <= LIMIT); end")]


@needs("sby", "yosys")
def test_a_multi_task_setup_is_a_recorded_failure(broker_owner, tmp_path):
    engine, owner = broker_owner
    shutil.copy(RTL / "counter.v", tmp_path / "counter.v")
    (tmp_path / "counter.sby").write_text("[tasks]\nprf\n\n" + COUNTER_SBY.replace("mode prove", "prf: mode prove"))
    params = {"sby": str(tmp_path / "counter.sby"), "sources": str(tmp_path / "counter.v"),
              "workdir": str(tmp_path / "run")}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert not run.succeeded and "[tasks]" in run.summary


@needs("sby", "yosys")
def test_a_cover_run_over_a_setup_that_does_not_read_the_rtl_fails(broker_owner, tmp_path):
    engine, owner = broker_owner
    params = {"sby": str(RTL / "counter.sby"), "sources": str(AXI / "axi4_lite_regs.v"),
              "workdir": str(tmp_path)}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert not run.succeeded and "does not read axi4_lite_regs.v" in run.summary


# --- The parser, on captured output (no tools needed) -----------------------------------------------


def _log(name: str) -> str:
    return (FIXTURES / "eda" / name).read_text()


def test_the_cover_parser_passes_only_when_every_cover_is_reached():
    ok = parse_sby_cover(_log("sby_cover_pass.log"), 0)
    assert ok.passed and ok.metrics["covers_reached"] == 1 and ok.metrics["covers_unreached"] == 0

    missed = parse_sby_cover(_log("sby_cover_unreached.log"), 2)
    assert not missed.passed and missed.summary.startswith("vacuous: 1 of 1 cover never reached")
    (diag,) = [d for d in missed.diagnostics if d.code == "COVER"]
    assert diag.file == "cond.v" and diag.line == 37

    none = parse_sby_cover(_log("sby_cover_none.log"), 0)
    assert "DONE (PASS" in _log("sby_cover_none.log")  # SymbiYosys itself calls this a pass
    assert not none.passed and "no cover statement" in none.summary

    assert not parse_sby_cover(_log("sby_cover_pass.log"), 1).passed  # a nonzero exit never passes


# --- Crown jewel: another workflow gains the gates by data alone -------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_a_fourth_workflow_is_gated_with_no_core_changes(fixed_clock, tmp_path):
    """The parameter-change RTL stage, gated by an extension: data only, no core code."""
    from nirmaan.company import builder
    from nirmaan.company.workflows import PARAMETER_CHANGE, REVIEWED, RTL_GATES
    from nirmaan.models import IntentRule
    from nirmaan.org import register_extension, unregister_extension

    kept = ("impact", "interface-update", "microarchitecture", "rtl-change")
    stages = tuple(s.model_copy(update={"evidence": (REVIEWED, *RTL_GATES), "outputs": ("rtl_source", "testbench"),
                                        "variants": s.variants[:1]})
                   if s.id == "rtl-change" else s for s in PARAMETER_CHANGE.stages if s.id in kept)
    flow = PARAMETER_CHANGE.model_copy(update={"id": "gated-parameter-change",
                                               "intents": ("gated_parameter_change",), "stages": stages})

    @register_extension("test-gated-parameter-change")
    def gated_flow(b):
        b.add(IntentRule(intent="gated_parameter_change", patterns=(r"\bgated width\b",), priority=1), flow)

    try:
        engine = Orchestrator(builder().build(), clock=fixed_clock).plan("Make a gated width change to the timer.")
        assert engine.state.project.workflows == ("gated-parameter-change",)
        rtl = next(t.id for t in engine.state.tasks.values() if t.stage == "rtl-change")
        drive(engine, until=rtl)
        with_workspace(engine, rtl, tmp_path)
        cite = token(upstream(engine, "microarchitecture"))
        latch = COUNTER.replace("    assign wrap = en && (count == LIMIT);\n",
                                "    reg wrap_l;\n    /* verilator lint_off LATCH */\n    always @(*)\n"
                                "        if (en)\n            wrap_l = (count == LIMIT);\n"
                                "    /* verilator lint_on LATCH */\n    assign wrap = en && wrap_l;\n")
        report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite, latch))])))
        assert report.status is ResultStatus.REFUSED and SYNTH in report.detail
        report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite))])))
        assert report.status is ResultStatus.SUBMITTED, report.detail
    finally:
        unregister_extension("test-gated-parameter-change")


# --- drive follows the gated order ---------------------------------------------------------------------


@needs(*GATE_TOOLS)
def test_drive_runs_the_checks_before_it_submits(nirmaan_org, fixed_clock, tmp_path):
    """The migrated helper: real files, real runs, then submission, never the other way round."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(FEATURE)
    rtl = tid(engine, FLOWS[FEATURE][1])
    drive(engine, until=tid(engine, "rtl-lint"), workspace=tmp_path)
    task = engine.task(rtl)
    assert task.status is TaskStatus.COMPLETED
    runs = [engine.state.tool_runs[engine.state.evidence[e].tool_run] for e in task.evidence
            if engine.state.evidence[e].kind is EvidenceKind.TOOL_RUN]
    assert {r.tool for r in runs} == {"lint.run", "simulator.run", "synth.run"} and all(r.succeeded for r in runs)
    order = [a.action for a in engine.state.audit if a.subject == rtl and a.action in ("tool.run", "task.submit")]
    assert order == ["tool.run"] * 3 + ["task.submit"]  # every check ran, then the work was submitted
    locations = {engine.state.artifacts[a].location for a in task.artifacts}
    assert set(runs[0].values("sources")) <= locations


# --- Laws ----------------------------------------------------------------------------------------------


def test_the_core_never_names_the_cover_check():
    """Non-vacuity is data on the stages and one backend: the runtime, policy, and planner never name it."""
    src = Path(__file__).parents[1] / "src" / "nirmaan"
    for part in ("runtime", "work", "orchestrator", "models"):
        for py in (src / part).rglob("*.py"):
            assert "formal.cover" not in py.read_text(encoding="utf-8"), py
    eda = (src / "integrations" / "eda.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+\S*veritriage", eda, re.MULTILINE)  # only the adapter imports it


def test_ci_requires_the_formal_tools_so_formal_tests_never_skip_there():
    ci = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required = next(line for line in ci.splitlines() if line.strip().startswith("NIRMAAN_REQUIRE_EDA:"))
    assert {"sby", "yices-smt2", *GATE_TOOLS} <= set(required.split(":", 1)[1].split())
