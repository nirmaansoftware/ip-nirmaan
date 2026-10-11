"""Milestone 26: synthesis and formal as before-review checks.

The ``block-design`` RTL stage goes to review only after real Yosys synthesis
(with no latches) over the produced RTL, and, when the seat writes a ``.sby``
(kind ``formal_spec``), after a real SymbiYosys proof over that RTL. Both are
data on the stage. Failing runs are recorded; a run that could not happen is
refused and never counted. Real-tool tests skip when an executable is absent,
or fail when CI names it in NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import drive, human, tid
from test_nirmaan_design_agents import (
    AXI,
    AXI_BLOCK,
    COUNTER_BLOCK,
    RTL,
    answer,
    counter_files,
    file,
    token,
    upstream,
    with_workspace,
)
from laws import needs

from nirmaan.integrations.eda import Backend, EdaResult, register_backend, unregister_backend
from nirmaan.models import Assurance, EvidenceKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
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
from nirmaan.work.policy import satisfies, unsatisfied_requirements

COUNTER = (RTL / "counter.v").read_text()
COUNTER_SBY = (RTL / "counter.sby").read_text()
SYNTH = "Synthesizes with Yosys, with no latches"
FORMAL = "Formal properties are proven"


def sby_file(cite: str, content: str = COUNTER_SBY, path: str = "counter.sby") -> dict:
    return file(path, "formal_spec", content, cite)


def runs_of(engine, report) -> dict:
    return {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in report.tool_runs}


def requirement(engine, task_id: str, description: str):
    return next(r for r in engine.task(task_id).evidence_requirements if r.description == description)


@pytest.fixture()
def counter_rtl(nirmaan_org, fixed_clock, tmp_path):
    """The counter block at its RTL seat, upstream approved, with a workspace."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "work")
    return engine, rtl, token(upstream(engine, "microarchitecture"))


@pytest.fixture()
def axi_rtl(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "work")
    return engine, rtl, token(upstream(engine, "microarchitecture"))


def axi_files(cite: str, rtl: str | None = None) -> list[dict]:
    return [file("axi4_lite_regs.v", "rtl_source", rtl or (AXI / "axi4_lite_regs.v").read_text(), cite,
                 entry="axi4_lite_regs"),
            file("axi4_lite_regs_tb.v", "testbench", (AXI / "axi4_lite_regs_tb.v").read_text(), cite,
                 entry="axi4_lite_regs_tb"),
            sby_file(cite, (AXI / "axi4_lite_regs.sby").read_text(), "axi4_lite_regs.sby")]


# --- The stage, as data ------------------------------------------------------------------


def test_the_rtl_stage_checks_synthesis_always_and_formal_when_a_setup_is_produced(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    synth, formal = requirement(engine, rtl, SYNTH), requirement(engine, rtl, FORMAL)
    assert synth.before_review and synth.tools == ("synth.run",) and synth.when_produced == ()
    assert dict(synth.params) == {"max_latches": "0"}
    assert [(b.param, b.kinds, b.entry) for b in synth.files] == [("sources", ("rtl_source",), False),
                                                                  ("top", ("rtl_source",), True)]
    assert formal.before_review and formal.tools == ("formal.run",) and formal.when_produced == ("formal_spec",)
    assert [(b.param, b.kinds) for b in formal.files] == [("sby", ("formal_spec",)), ("sources", ("rtl_source",))]
    # Before anything is produced, the conditional requirement is not among the unmet ones.
    assert FORMAL not in unsatisfied_requirements(engine.state, engine.task(rtl))
    assert SYNTH in unsatisfied_requirements(engine.state, engine.task(rtl))
    drive(engine, until=rtl)
    text = render_work_prompt(assemble(engine, rtl)).render()  # the seat is told formal is its choice
    assert "applies only if you produce a formal_spec file" in text


# --- Synthesis keeps bad RTL from review ---------------------------------------------------


@needs("verilator", "yosys")
def test_a_latch_hidden_from_lint_cannot_reach_review(counter_rtl):
    """A lint waiver silences Verilator; synthesis still finds the latch."""
    engine, rtl, cite = counter_rtl
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
    synth = runs["synth.run"]
    assert not synth.succeeded and "latches 1 exceeds max_latches 0" in synth.summary
    assert synth.params["max_latches"] == 0.0  # typed by the contract (M39)
    ev = next(engine.state.evidence[e] for e in report.evidence if engine.state.evidence[e].tool_run == synth.id)
    assert not ev.substantiated  # the failure is on the record
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()


@needs("verilator", "yosys")
def test_rtl_that_fails_synthesis_cannot_reach_review(counter_rtl):
    """The RTL names a top module it does not define: Yosys fails, and the failure is recorded."""
    engine, rtl, cite = counter_rtl
    src, tb = counter_files(cite)
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer({**src, "entry": "counter_top"}, tb)])))

    assert report.status is ResultStatus.REFUSED and SYNTH in report.detail
    synth = runs_of(engine, report)["synth.run"]
    assert not synth.succeeded and "synthesis failed" in synth.summary
    assert "counter_top" in Path(synth.references[0]).read_text()
    assert engine.task(rtl).status is TaskStatus.IN_PROGRESS


# --- Formal keeps bad RTL from review --------------------------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
def test_a_formal_counterexample_keeps_rtl_from_review(axi_rtl):
    """A read channel that takes a second read while one is pending: the testbench never tries it."""
    engine, rtl, cite = axi_rtl
    source = (AXI / "axi4_lite_regs.v").read_text()
    mutant = source.replace("assign s_axil_arready = !s_axil_rvalid;", "assign s_axil_arready = 1'b1;")
    assert mutant != source
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*axi_files(cite, mutant))])))

    assert report.status is ResultStatus.REFUSED and FORMAL in report.detail
    runs = runs_of(engine, report)
    assert all(runs[t].succeeded for t in ("lint.run", "simulator.run", "synth.run"))
    formal = runs["formal.run"]
    assert not formal.succeeded and "formal fail" in formal.summary
    result = json.loads(Path(formal.references[1]).read_text())["result"]
    assert result["metrics"]["status"] == "FAIL" and result["metrics"]["traces"]
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()


@needs("verilator", "yosys", "sby")
def test_a_setup_that_does_not_read_the_submitted_rtl_fails(counter_rtl):
    """The .sby proves its own embedded copy of the module, not the file submitted."""
    engine, rtl, cite = counter_rtl
    embedded = COUNTER_SBY.replace("[files]\ncounter.v\n", "[file counter.v]\n" + COUNTER)
    assert embedded != COUNTER_SBY
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(cite), sby_file(cite, embedded))])))

    assert report.status is ResultStatus.REFUSED
    formal = runs_of(engine, report)["formal.run"]
    assert not formal.succeeded and "does not read" in formal.summary and "counter.v" in formal.summary


# --- Passing checks allow review ---------------------------------------------------------


@needs("verilator", "yosys", "sby", "yices-smt2")
def test_passing_synthesis_and_formal_allow_review(counter_rtl):
    engine, rtl, cite = counter_rtl
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite), sby_file(cite))])))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    task = engine.task(rtl)
    arts = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in task.artifacts}
    assert set(arts) == {"rtl_source", "testbench", "formal_spec"}
    runs = runs_of(engine, report)
    assert set(runs) == {"lint.run", "simulator.run", "synth.run", "formal.run", "formal.cover"}
    assert all(r.succeeded for r in runs.values())
    assert runs["synth.run"].params["sources"] == (arts["rtl_source"].location,)
    assert runs["synth.run"].params["top"] == "counter"
    assert runs["formal.run"].params["sby"] == arts["formal_spec"].location
    assert runs["formal.run"].params["sources"] == (arts["rtl_source"].location,)
    assert runs["formal.cover"].params["sby"] == arts["formal_spec"].location  # M27: and it is not vacuous
    assert unsatisfied_requirements(engine.state, task) == ["Independent review recorded"]

    llm = MockLLM()
    review_task(engine, rtl, ModelRuntime(llm))
    assert "[options]" in llm.calls[0].render()  # the reviewer reads the proof setup too
    engine.approve(rtl, human(task.approver), "lint-clean, simulated, synthesized, proven")
    assert engine.task(rtl).status is TaskStatus.COMPLETED
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)


@needs("verilator", "yosys")
def test_without_a_setup_formal_is_neither_run_nor_required(counter_rtl):
    engine, rtl, cite = counter_rtl
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite))])))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    assert set(runs_of(engine, report)) == {"lint.run", "simulator.run", "synth.run"}
    assert "formal.run" not in report.detail
    assert unsatisfied_requirements(engine.state, engine.task(rtl)) == ["Independent review recorded"]


# --- A formal run that did not happen is never counted ------------------------------------------


@needs("verilator", "yosys")
def test_without_sby_a_produced_setup_blocks_the_task(counter_rtl, monkeypatch):
    engine, rtl, cite = counter_rtl
    real = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None if name == "sby" else real(name, *a, **k))
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite), sby_file(cite))])))

    assert report.status is ResultStatus.BLOCKED
    task = engine.task(rtl)
    assert task.status is TaskStatus.BLOCKED and "sby" in task.blocked_reason
    assert "formal.run" not in {r.tool for r in engine.state.tool_runs.values()}
    assert task.artifacts == ()


def test_a_claimed_formal_pass_without_a_run_is_refused(counter_rtl, monkeypatch, tmp_path):
    engine, rtl, cite = counter_rtl
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    lie = answer(*counter_files(cite), sby_file(cite), tool_runs=["run-0077"],
                 claims=["formal proof passed: every property proven"])
    with pytest.raises(PolicyViolationError, match="P5"):
        run_task(engine, rtl, ModelRuntime(MockLLM(script=[lie])))
    assert "run-0077" not in engine.state.tool_runs
    assert not any(r.tool == "formal.run" for r in engine.state.tool_runs.values())
    assert engine.task(rtl).artifacts == ()


@needs("yosys")
def test_a_synthesis_run_without_the_fixed_parameters_does_not_count(counter_rtl, tmp_path):
    """A person synthesizes by hand without the latch limit: a real run, but not this requirement's."""
    engine, rtl, _ = counter_rtl
    owner = human(engine.task(rtl).owner)
    engine.start(rtl, owner)
    req = requirement(engine, rtl, SYNTH)
    base = {"sources": str(RTL / "counter.v"), "top": "counter"}
    verdicts = []
    for extra in ({}, {"max_latches": "0"}):
        run, _ = ToolBroker(engine).invoke(owner, "synth.run", {**base, **extra, "workdir": str(tmp_path / str(extra))},
                                           rtl)
        assert run.succeeded, run.summary
        ev = engine.record_evidence(rtl, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
        verdicts.append(satisfies(engine.state, ev, req))
    assert verdicts == [False, True]


# --- Limits on any EDA metric ------------------------------------------------------------


@needs("true")
def test_a_limit_on_a_metric_the_backend_does_not_report_fails(counter_rtl, tmp_path):
    engine, rtl, _ = counter_rtl
    owner = human(engine.task(rtl).owner)
    register_backend(Backend("metricless", "synth.run", ("true",), lambda job: [["true"]],
                             lambda run: EdaResult(True, "done", (), {"cells": 3}), ("sources",)))
    try:
        params = {"sources": str(RTL / "counter.v"), "backend": "metricless", "workdir": str(tmp_path)}
        run, _ = ToolBroker(engine).invoke(owner, "synth.run", {**params, "max_cells": "3"}, rtl)
        assert run.succeeded, run.summary
        run, _ = ToolBroker(engine).invoke(owner, "synth.run", {**params, "max_cells": "2"}, rtl)
        assert not run.succeeded and "cells 3 exceeds max_cells 2" in run.summary
        run, _ = ToolBroker(engine).invoke(owner, "synth.run", {**params, "max_widgets": "0"}, rtl)
        assert not run.succeeded and "widgets was not reported" in run.summary
    finally:
        unregister_backend("synth.run", "metricless")


# --- Crown jewel: a new before-review check needs no core changes ---------------------------------


def test_a_new_before_review_check_needs_no_core_changes(fixed_clock, tmp_path):
    """A header check with a fixed parameter, and a waiver check that applies only to waivers.

    Only data and a tool binding are added: nothing in the runtime, prompt
    renderer, engine, policy, or broker changes.
    """
    from nirmaan.company import builder
    from nirmaan.company.workflows import BLOCK_DESIGN
    from nirmaan.models import EvidenceRequirement, FileInput, IntentRule, ToolRisk, ToolSpec, ToolStatus
    from nirmaan.org import register_extension, unregister_extension
    from nirmaan.runtime import ToolOutcome, register_binding, unregister_binding

    @register_binding("header.check")
    def header(params, engine):
        missing = [s for s in params["sources"].split(",") if params["marker"] not in Path(s).read_text()]
        return ToolOutcome(not missing, f"no {params['marker']} in {', '.join(missing)}" if missing else "headers ok")

    @register_binding("waiver.check")
    def waiver(params, engine):
        unsigned = [w for w in params["waivers"].split(",") if "approved-by:" not in Path(w).read_text()]
        return ToolOutcome(not unsigned, "unsigned waiver" if unsigned else "waivers signed")

    def gate(description, tool, *files, **kw):
        return EvidenceRequirement(description=description, accepts=(EvidenceKind.TOOL_RUN,), tools=(tool,),
                                   files=files, before_review=True, **kw)

    rtl_stage = next(s for s in BLOCK_DESIGN.stages if s.id == "rtl-implementation")
    stage = rtl_stage.model_copy(update={"evidence": (
        rtl_stage.evidence[0],  # the independent review, and none of the EDA checks: no tools needed
        gate("Every RTL file carries the licence header", "header.check",
             FileInput(param="sources", kinds=("rtl_source",)), params=(("marker", "SPDX-License-Identifier"),)),
        gate("Every lint waiver is signed", "waiver.check",
             FileInput(param="waivers", kinds=("lint_waiver",)), when_produced=("lint_waiver",)))})
    flow = BLOCK_DESIGN.model_copy(update={
        "id": "headered-block", "intents": ("headered_block",),
        "stages": tuple(stage if s.id == stage.id else s for s in BLOCK_DESIGN.stages
                        if s.id in ("requirements", "interface-spec", "register-map", "microarchitecture", stage.id))})

    @register_extension("test-header-check")
    def headers(b):
        b.add(ToolSpec(id="header.check", name="Header check", category="eda", risk=ToolRisk.EXECUTE,
                       status=ToolStatus.AVAILABLE),
              ToolSpec(id="waiver.check", name="Waiver check", category="eda", risk=ToolRisk.EXECUTE,
                       status=ToolStatus.AVAILABLE),
              IntentRule(intent="headered_block", patterns=(r"\bheadered\b",), priority=1),
              flow)
        b.definition.skills = [s.model_copy(update={"tools": (*s.tools, "header.check", "waiver.check")})
                               if s.id == "rtl_design" else s for s in b.definition.skills]

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Create a headered 4-bit counter.")
        rtl = tid(engine, "rtl-implementation")
        assert engine.state.project.workflows == ("headered-block",)
        drive(engine, until=rtl)
        with_workspace(engine, rtl, tmp_path)
        cite = token(upstream(engine, "microarchitecture"))
        src, tb = counter_files(cite)

        report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(src, tb)])))
        assert report.status is ResultStatus.REFUSED and "licence header" in report.detail
        assert "waiver.check" not in {r.tool for r in engine.state.tool_runs.values()}  # no waiver, no run

        headed = {**src, "content": "// SPDX-License-Identifier: Apache-2.0\n" + src["content"]}
        unsigned = file("lint.waiver", "lint_waiver", "WIDTH on line 3: intended.\n", cite)
        report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(headed, tb, unsigned)])))
        assert report.status is ResultStatus.REFUSED and "waiver is signed" in report.detail

        signed = {**unsigned, "content": unsigned["content"] + "approved-by: lead\n"}
        report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(headed, tb, signed)])))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        header_run = runs_of(engine, report)["header.check"]
        assert header_run.params["marker"] == "SPDX-License-Identifier"
    finally:
        unregister_extension("test-header-check")
        unregister_binding("header.check")
        unregister_binding("waiver.check")


# --- With the repair loop: a counterexample is repairable, and never counts ---------------------


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
def test_a_counterexample_repaired_on_the_next_attempt_reaches_review(axi_rtl):
    engine, rtl, cite = axi_rtl
    source = (AXI / "axi4_lite_regs.v").read_text()
    mutant = source.replace("assign s_axil_arready = !s_axil_rvalid;", "assign s_axil_arready = 1'b1;")
    llm = MockLLM(script=[answer(*axi_files(cite, mutant)), answer(*axi_files(cite))])
    report = run_task(engine, rtl, ModelRuntime(llm), attempts=2)

    assert report.status is ResultStatus.SUBMITTED, report.detail
    assert [a["status"] for a in report.attempts] == ["refused", "submitted"]
    (first,) = [a for a in engine.state.attempts.values() if a.task == rtl]
    assert FORMAL in first.refusal and "formal_spec" in {a.kind for a in first.artifacts}
    assert all(a.id not in engine.state.artifacts for a in first.artifacts)  # the refused files never count
    failed = {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in first.tool_runs}["formal.run"]
    assert not failed.succeeded
    passing = {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in report.attempts[1]["tool_runs"]}
    submitted = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in engine.task(rtl).artifacts}
    assert passing["formal.run"].succeeded and passing["formal.run"].params["sby"] == submitted["formal_spec"].location
    assert failed.params["sby"] != submitted["formal_spec"].location
