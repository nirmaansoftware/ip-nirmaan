"""Milestone 29: the RTL gates on the remaining RTL stages, and automatic antecedent covers.

The four stages M27 deferred (``parameter-change`` ``rtl-change``, the
``rtl-fix`` stages of ``regression-investigation`` and ``timing-closure``, and
``new-ip`` ``cdc-design``) now carry ``RTL_GATES``, as data. And the cover run
behind ``NOT_VACUOUS`` derives a cover for every assertion's antecedent, so a
proof whose assertions are guarded by conditions that never hold is refused.
Real-tool tests skip when an executable is absent, or fail when CI names it in
NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nirmaan_helpers import GATE_TOOLS, drive, human, tid
from test_nirmaan_design_agents import RTL, answer, counter_files, needs, token, upstream, with_workspace
from test_nirmaan_formal_gate import COUNTER, COUNTER_SBY, FORMAL, runs_of, sby_file
from test_nirmaan_gates_everywhere import (  # noqa: F401 (broker_owner is a fixture)
    ALL_CHECKS,
    COVERED,
    FORMAL_TOOLS,
    NOT_VACUOUS,
    SYNTH,
    broker_owner,
    with_formal,
)

from nirmaan.integrations.eda_antecedents import derive
from nirmaan.integrations.eda_parsers import parse_sby_cover
from nirmaan.models import Assurance, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolBroker, review_task, run_task
from nirmaan.work.policy import unsatisfied_requirements

#: Each request, the workflow it plans, its RTL task, the stage whose approved output the RTL cites,
#: and the decisions on the way.
FLOWS = {
    "Change the data width of the timer from 32 to 64 bits.":
        ("parameter-change", "rtl-change.datapath", "microarchitecture", {}),
    "The timer regression is failing since the last merge.":
        ("regression-investigation", "rtl-fix", "root-cause", {"root-cause": "rtl_bug"}),
    "Close timing on the timer: negative slack on the count path.":
        ("timing-closure", "rtl-fix", "classify", {"classify": "rtl_path"}),
    "Create a 4-port AXI-to-NoC bridge with two clock domains.":
        ("new-ip", "cdc-design", "microarchitecture", {}),
}
#: The workflow and stage of each newly gated stage.
STAGES = {(wf, stage.split(".")[0]) for wf, stage, _, _ in FLOWS.values()}

#: A guard that never holds once reset has been seen: the count never passes LIMIT. The assertion
#: under it is never checked, so it "holds", and so does the whole proof.
NEVER_CHECKED = "    always @(posedge clk)\n        if (seen_reset && count > LIMIT)\n            assert (!wrap);\n"


def _latch(rtl: str) -> str:
    out = rtl.replace(
        "    assign wrap = en && (count == LIMIT);\n",
        "    reg wrap_l;\n    /* verilator lint_off LATCH */\n    always @(*)\n        if (en)\n"
        "            wrap_l = (count == LIMIT);\n    /* verilator lint_on LATCH */\n"
        "    assign wrap = en && wrap_l;\n")
    assert out != rtl
    return out


@pytest.fixture(params=list(FLOWS), ids=[FLOWS[r][0] for r in FLOWS])
def gated(request, nirmaan_org, fixed_clock, tmp_path):
    """Each newly gated stage at its seat, upstream approved, with a workspace and a citation."""
    workflow, stage, source, outcomes = FLOWS[request.param]
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request.param)
    assert engine.state.project.workflows == (workflow,)
    rtl = tid(engine, stage)
    drive(engine, until=rtl, outcomes=outcomes, workspace=tmp_path / "drive")
    assert engine.task(rtl).status is TaskStatus.READY
    with_workspace(engine, rtl, tmp_path / "work")
    return engine, rtl, token(upstream(engine, source))


# --- The stages, as data ---------------------------------------------------------------------------


def test_the_remaining_rtl_stages_carry_the_rtl_gates():
    from nirmaan.company.workflows import RTL_GATES, WORKFLOWS

    flows = {wf.id: wf for wf in WORKFLOWS}
    for workflow, stage in STAGES:
        st = flows[workflow].stage(stage)
        assert st.evidence[1:] == RTL_GATES, (workflow, stage)
        assert set(st.outputs) == {"rtl_source", "testbench"}, (workflow, stage)


def test_every_stage_that_produces_rtl_is_gated():
    """No stage writes RTL without the gates: the four M27 stages, block-design, and these four."""
    from nirmaan.company.workflows import RTL_GATES, WORKFLOWS

    ungated = [(wf.id, st.id) for wf in WORKFLOWS for st in wf.stages
               if "rtl_source" in st.outputs and st.evidence[1:] != RTL_GATES]
    assert ungated == []


def test_the_cdc_seat_builds_on_approved_inputs_and_may_run_the_checks(nirmaan_org):
    assert nirmaan_org.capabilities["rtl.cdc_design"].approved_inputs
    tools = set(nirmaan_org.skills["cdc_design"].tools)
    assert {"lint.run", "simulator.run", "synth.run", "formal.run", "formal.cover"} <= tools


def test_the_planned_tasks_are_gated(gated, nirmaan_org):
    engine, rtl, cite = gated
    task = engine.task(rtl)
    assert nirmaan_org.capabilities[task.capability].approved_inputs
    assert {t for r in task.evidence_requirements if r.before_review for t in r.tools} == ALL_CHECKS
    unmet = unsatisfied_requirements(engine.state, task)
    assert SYNTH in unmet and FORMAL not in unmet and NOT_VACUOUS not in unmet


# --- The gates keep bad RTL from review, on every newly gated stage ----------------------------------


@needs(*GATE_TOOLS)
def test_a_latch_blocks_review(gated):
    engine, rtl, cite = gated
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite, _latch(COUNTER)))])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail and SYNTH in report.detail
    runs = runs_of(engine, report)
    assert runs["lint.run"].succeeded and runs["simulator.run"].succeeded
    assert not runs["synth.run"].succeeded and "latches 1 exceeds max_latches 0" in runs["synth.run"].summary
    assert engine.task(rtl).status is TaskStatus.IN_PROGRESS and engine.task(rtl).artifacts == ()


@needs(*GATE_TOOLS)
def test_a_failing_simulation_blocks_review(gated):
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
    assert "every assertion antecedent reached (1 of 1)" in runs["formal.cover"].summary
    task = engine.task(rtl)
    assert unsatisfied_requirements(engine.state, task) == ["Independent review recorded"]
    review_task(engine, rtl, ModelRuntime(MockLLM()))
    engine.approve(rtl, human(task.approver), "gated, proven, every antecedent reached")
    assert engine.task(rtl).status is TaskStatus.COMPLETED
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)


@needs(*FORMAL_TOOLS)
def test_an_assertion_that_is_never_checked_is_refused(gated):
    """The proof passes and the seat's own cover is reached, yet one assertion never fires."""
    engine, rtl, cite = gated
    rtl_text = with_formal(COUNTER, NEVER_CHECKED)
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(cite, rtl_text), sby_file(cite))])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail and NOT_VACUOUS in report.detail
    runs = runs_of(engine, report)
    assert runs["formal.run"].succeeded  # the proof alone passes: that is the hole M29 closes
    cover = runs["formal.cover"]
    line = rtl_text.splitlines().index("            assert (!wrap);") + 1
    assert not cover.succeeded and f"the assertion at counter.v:{line} is never checked" in cover.summary
    result = json.loads(Path(cover.references[1]).read_text())["result"]
    assert result["metrics"]["covers_reached"] == 1 and result["metrics"]["covers_unreached"] == 0
    assert result["metrics"]["antecedents_reached"] == 1 and result["metrics"]["antecedents_unreached"] == 1
    (diag,) = [d for d in result["diagnostics"] if d["code"] == "ANTECEDENT"]
    assert diag["file"] == "counter.v" and diag["line"] == line and "assert (!wrap);" in diag["message"]
    ev = next(engine.state.evidence[e] for e in report.evidence if engine.state.evidence[e].tool_run == cover.id)
    assert not ev.substantiated
    assert engine.task(rtl).status is TaskStatus.IN_PROGRESS and engine.task(rtl).artifacts == ()


# --- Antecedent covers on the fixtures ------------------------------------------------------------------


#: Assertions per fixture file, each in procedural code under at least one guard.
ASSERTIONS = {"counter.v": 1, "axi4_lite_regs.v": 14, "sync_fifo.v": 18, "rr_arbiter.v": 9, "apb_regs.v": 8}


@pytest.mark.parametrize("name", list(ASSERTIONS))
def test_a_cover_is_derived_for_every_fixture_assertion_without_moving_a_line(name):
    source = next(RTL.rglob(name)).read_text()
    d = derive(source, name)
    assert [s.kind for s in d.sites] == ["guarded"] * ASSERTIONS[name]
    assert d.text.count("\n") == source.count("\n")  # every cover keeps its assertion's line
    copy = d.text.splitlines()
    for s in d.sites:
        assert copy[s.line - 1][s.column - 1:].startswith("cover (1'b1); assert")
    stripped = d.text.replace("begin cover (1'b1); ", "")
    assert re.sub(r"(assert \(.*?\);) end", r"\1", stripped) == source  # nothing else changed


@needs("sby", "yosys", "yices-smt2")
@pytest.mark.parametrize("sby,source,covers", COVERED, ids=[c[0] for c in COVERED])
def test_every_fixture_antecedent_is_reached(broker_owner, tmp_path, sby, source, covers):
    engine, owner = broker_owner
    params = {"sby": str(RTL / sby), "sources": str(RTL / source), "workdir": str(tmp_path)}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert run.succeeded, run.summary
    metrics = json.loads(Path(run.references[1]).read_text())["result"]["metrics"]
    assert metrics["covers_reached"] == covers and metrics["covers_unreached"] == 0  # the seat's, as in M27
    # Loops, generate blocks, and task calls elaborate one cover per instance: at least one per assertion.
    assert metrics["antecedents_reached"] >= ASSERTIONS[Path(source).name]
    assert metrics["antecedents_unreached"] == 0 and metrics["antecedents_unelaborated"] == 0
    manifest = json.loads((tmp_path / "antecedents.json").read_text())["sites"]
    assert len(manifest) == ASSERTIONS[Path(source).name]
    assert {s["source"] for s in manifest} == {str((RTL / source).resolve())}


@needs("sby", "yosys", "yices-smt2")
def test_an_unreachable_antecedent_fails_the_cover_run_as_a_recorded_run(broker_owner, tmp_path):
    engine, owner = broker_owner
    (tmp_path / "counter.v").write_text(with_formal(COUNTER, NEVER_CHECKED))
    (tmp_path / "counter.sby").write_text(COUNTER_SBY)
    params = {"sby": str(tmp_path / "counter.sby"), "sources": str(tmp_path / "counter.v"),
              "workdir": str(tmp_path / "run")}
    proof, _ = ToolBroker(engine).invoke(owner, "formal.run", {**params, "workdir": str(tmp_path / "proof")})
    assert proof.succeeded, proof.summary
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert run.id in engine.state.tool_runs and not run.succeeded
    assert "vacuous: 1 of 2 assertion antecedents never reached" in run.summary


@needs("sby", "yosys")
def test_an_assertion_whose_antecedent_cannot_be_derived_is_refused(broker_owner, tmp_path):
    """Never silently skipped: an assertion the deriver cannot handle fails the run, with its line."""
    engine, owner = broker_owner
    rtl = with_formal(COUNTER, "    always @(posedge clk)\n        assert (count <= LIMIT) else $error(\"over\");\n")
    (tmp_path / "counter.v").write_text(rtl)
    (tmp_path / "counter.sby").write_text(COUNTER_SBY)
    params = {"sby": str(tmp_path / "counter.sby"), "sources": str(tmp_path / "counter.v"),
              "workdir": str(tmp_path / "run")}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    line = rtl.splitlines().index("        assert (count <= LIMIT) else $error(\"over\");") + 1
    assert not run.succeeded and "cannot derive the antecedent of 1 assertion" in run.summary
    assert f"counter.v:{line} (an assertion with an action block is not supported)" in run.summary


# --- The deriver, on text (no tools needed) -----------------------------------------------------------


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(s.kind, s.reason) for s in derive(text, "x.v").sites]


def test_a_module_scope_implication_gains_a_cover_of_its_antecedent():
    text = "module m(input clk, a, b);\n    assert property (@(posedge clk) disable iff (b) a && b |-> ##0 a);\nendmodule\n"
    assert _kinds(text) == [("underived", "the sequence operator '##' is not supported")]
    text = "module m(input clk, a, b);\n    assert property (@(posedge clk) disable iff (!b) a && b |=> b);\nendmodule\n"
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["implication"]
    assert d.text.splitlines()[1].endswith(" cover property (@(posedge clk) disable iff (!b) a && b);")
    (site,) = d.sites
    assert d.text.splitlines()[1][site.column - 1:].startswith("cover property")


def test_a_procedural_implication_is_covered_on_its_own_path():
    text = "module m(input clk, a, b, c);\n    always @(posedge clk)\n        if (c) assert property (a |-> b);\nendmodule\n"
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["implication"]
    assert "if (c) begin cover property (a); assert property (a |-> b); end" in d.text


def test_an_else_branch_and_a_case_arm_keep_their_structure():
    text = ("module m(input clk, a, input [1:0] s);\n    always @* begin\n"
            "        if (a) assert (s != 0); else assert (s == 0);\n"
            "        case (s) IDLE: assert (!a); default: ; endcase\n    end\nendmodule\n")
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["guarded"] * 3
    assert ("if (a) begin cover (1'b1); assert (s != 0); end else begin cover (1'b1); assert (s == 0); end"
            in d.text)
    assert "IDLE: begin cover (1'b1); assert (!a); end" in d.text


def test_unguarded_and_unsupported_assertions_are_listed():
    text = ("`define CHECK(x) assert (x)\n"
            "module m(input clk, a, b);\n"
            "    property p; a; endproperty\n"
            "    assert property (a || b);\n"
            "    assert property (p);\n"
            "    assert property ((a |-> b));\n"
            "    always @(posedge clk) assert #0 (a);\n"
            "    always @(posedge clk) assert (a) $display(\"ok\"); else $error(\"no\");\n"
            "endmodule\n")
    assert _kinds(text) == [
        ("underived", "the macro CHECK asserts, and a macro body is not expanded"),
        ("unguarded", ""),
        ("underived", "the named property p is not expanded"),
        ("underived", "an implication inside parentheses is not supported"),
        ("underived", "a deferred assertion is not supported"),
        ("underived", "an assertion with an action block is not supported"),
    ]


def test_assumptions_covers_and_comments_are_left_alone():
    text = ("module m(input clk, a);\n    // assert (a); in a comment\n    /* assert (a); */\n"
            "    always @* begin assume (a); cover (a); end\nendmodule\n")
    d = derive(text, "x.v")
    assert d.sites == () and d.text == text


def test_the_parser_counts_antecedents_apart_from_the_seats_covers():
    log = (FIXTURES / "eda" / "sby_cover_pass.log").read_text()
    where = re.search(r"at \w+: (\S+):(\d+)\.(\d+)", log)
    site = {"file": where[1], "line": int(where[2]), "column": int(where[3]), "assertion": "assert (x);"}
    as_antecedent = parse_sby_cover(log, 0, [site])
    assert not as_antecedent.passed and "no cover statement" in as_antecedent.summary  # the seat must still cover
    assert as_antecedent.metrics["antecedents_reached"] == 1 and as_antecedent.metrics["covers_reached"] == 0
    elsewhere = parse_sby_cover(log, 0, [{**site, "line": 999}])
    assert elsewhere.passed and elsewhere.metrics["antecedents_unelaborated"] == 1
    (warn,) = [d for d in elsewhere.diagnostics if d.code == "ANTECEDENT"]
    assert warn.severity == "warning" and warn.line == 999


FIXTURES = Path(__file__).parent / "fixtures"


# --- Crown jewel: a new workflow gains antecedent covers by data alone ---------------------------------


@needs(*FORMAL_TOOLS)
def test_a_new_workflow_with_the_gates_refuses_a_never_checked_assertion_with_no_core_changes(
        fixed_clock, tmp_path):
    """An extension's workflow carries RTL_GATES; the antecedent check comes with them, unnamed by any core."""
    from nirmaan.company import builder
    from nirmaan.company.workflows import REVIEWED, RTL_GATES, rv, st
    from nirmaan.models import IntentRule, WorkflowTemplate
    from nirmaan.org import register_extension, unregister_extension

    flow = WorkflowTemplate(
        id="test-guarded-fix", name="Guarded fix", description="An RTL fix, gated.", intents=("guarded_fix",),
        stages=(st("impact", "Impact", "RTL", "rtl.impact", review=rv("rtl.review"), outputs=("impact_analysis",),
                   evidence=(REVIEWED,)),
                st("fix", "Fix", "RTL", "rtl.implement", depends_on=("impact",), review=rv("rtl.review"),
                   outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES))))

    @register_extension("test-guarded-fix")
    def guarded(b):
        b.add(IntentRule(intent="guarded_fix", patterns=(r"\bguarded fix\b",), priority=1), flow)

    try:
        engine = Orchestrator(builder().build(), clock=fixed_clock).plan("Make a guarded fix to the timer.")
        assert engine.state.project.workflows == ("test-guarded-fix",)
        fix = tid(engine, "fix")
        drive(engine, until=fix)
        with_workspace(engine, fix, tmp_path)
        cite = token(upstream(engine, "impact"))
        bad = answer(*counter_files(cite, with_formal(COUNTER, NEVER_CHECKED)), sby_file(cite))
        report = run_task(engine, fix, ModelRuntime(MockLLM(script=[bad])))
        assert report.status is ResultStatus.REFUSED and NOT_VACUOUS in report.detail
        report = run_task(engine, fix, ModelRuntime(MockLLM(script=[answer(*counter_files(cite), sby_file(cite))])))
        assert report.status is ResultStatus.SUBMITTED, report.detail
    finally:
        unregister_extension("test-guarded-fix")


# --- Laws ------------------------------------------------------------------------------------------------


def test_the_core_never_names_antecedents_and_the_deriver_imports_nothing_of_nirmaan():
    src = Path(__file__).parents[1] / "src" / "nirmaan"
    for part in ("runtime", "work", "orchestrator", "models"):
        for py in (src / part).rglob("*.py"):
            assert "antecedent" not in py.read_text(encoding="utf-8"), py
    deriver = (src / "integrations" / "eda_antecedents.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+(nirmaan|veritriage)", deriver, re.MULTILINE)


def test_ci_runs_the_formal_tests_with_the_tools_required():
    ci = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required = next(line for line in ci.splitlines() if line.strip().startswith("NIRMAAN_REQUIRE_EDA:"))
    assert {"sby", "yices-smt2", *GATE_TOOLS} <= set(required.split(":", 1)[1].split())
    assert re.search(r"python -m pytest\b(?![^\n]*(--ignore|-k|--deselect)[^\n]*gates_rest)", ci)


@needs(*GATE_TOOLS)
def test_the_drive_helper_works_a_newly_gated_stage_in_the_gated_order(nirmaan_org, fixed_clock, tmp_path):
    """drive takes timing-closure past its RTL fix: real runs, then submission."""
    request = "Close timing on the timer: negative slack on the count path."
    _, stage, _, outcomes = FLOWS[request]
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request)
    fix = tid(engine, stage)
    drive(engine, until=tid(engine, "reanalysis"), outcomes=outcomes, workspace=tmp_path)
    assert engine.task(fix).status is TaskStatus.COMPLETED
    order = [a.action for a in engine.state.audit if a.subject == fix and a.action in ("tool.run", "task.submit")]
    assert order == ["tool.run"] * 3 + ["task.submit"]
