"""Milestone 37: a real ``sta.run`` on ``timing-closure`` ``reanalysis``, and antecedents of named properties
and macros.

On the RTL branch, ``reanalysis`` needs a real STA run over the approved fixed RTL (synthesized to the PDK's
Liberty, then timed under the task's SDC), before review, as data. Without a timer the task is BLOCKED, never
faked. The cover run behind ``NOT_VACUOUS`` now inlines named properties and expands macros that assert, and
derives a cover for each, as for any written assertion. See docs/STA_AND_ANTECEDENTS.md.

Real-tool tests skip when an executable is absent, or fail when CI names it in NIRMAAN_REQUIRE_EDA; the real
timing-closure project runs in CI's physical-design job.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from nirmaan_helpers import GATE_TOOLS, agent, drive, human, tid
from test_nirmaan_design_agents import answer, counter_files, file, needs, token, upstream, with_workspace
from test_nirmaan_formal_gate import runs_of
from test_nirmaan_gates_everywhere import broker_owner  # noqa: F401 (a fixture)
from test_nirmaan_physical import PD, TINY_LIB, fake_tool, invoke, nangate45, only_on_path

from nirmaan.integrations.eda_antecedents import definitions, derive
from nirmaan.models import Assurance, EvidenceKind, MemoryScope, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolAccessDenied, ToolBroker, review_task, run_task
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
PROPS = RTL / "props"
PROD3 = RTL / "prod3"
PROD3_SDC = PD / "prod3.sdc"
TIMING = "Close timing on the timer: negative slack on the count path."
RETIMED = "Timing met on the fixed RTL: synthesized to the target library, then timed under the task's SDC"
CLEAN = "Clean timing report"


def _inputs(engine, task_id: str, **values: str) -> None:
    owner = human(engine.task(task_id).owner)
    for key, value in values.items():
        engine.remember(MemoryScope.TASK, task_id, f"input.{key}", value, owner)


def _report(cite: str) -> str:
    note = file("timing.md", "timing_report", "# Timing re-analysis\n\nSee the sta.run record.\n", cite)
    return answer(note)


# --- The requirement, as data -------------------------------------------------------------------------------


def test_reanalysis_needs_a_real_sta_run_over_the_fixed_rtl_on_the_rtl_branch():
    from nirmaan.company.workflows import WORKFLOWS
    from nirmaan.models import EvidenceKind as K

    stage = next(wf for wf in WORKFLOWS if wf.id == "timing-closure").stage("reanalysis")
    by = {r.description: r for r in stage.evidence}
    retimed = by[RETIMED]
    assert retimed.accepts == (K.TOOL_RUN,) and retimed.tools == ("sta.run",) and retimed.before_review
    (binding,) = retimed.files
    assert binding.param == "sources" and binding.kinds == ("rtl_source",) and binding.upstream
    assert retimed.when_upstream == ("rtl_source",)
    clean = by[CLEAN]  # the attestation stays only where no RTL was fixed
    assert K.HUMAN_ATTESTATION in clean.accepts and set(clean.when_upstream) == {"constraints", "layout"}
    assert not clean.applies((), ("rtl_source",)) and retimed.applies((), ("rtl_source",))
    assert clean.applies((), ("constraints",)) and not retimed.applies((), ("constraints",))
    assert not retimed.applies(())  # a requirement scoped to upstream kinds never applies blind


@needs(*GATE_TOOLS)
def test_on_the_rtl_branch_only_the_real_run_is_asked_for(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(TIMING)
    reanalysis = tid(engine, "reanalysis")
    drive(engine, until=reanalysis, outcomes={"classify": "rtl_path"}, workspace=tmp_path)
    unmet = unsatisfied_requirements(engine.state, engine.task(reanalysis))
    assert RETIMED in unmet and CLEAN not in unmet


def test_on_the_constraint_branch_the_old_requirement_stands(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(TIMING)
    reanalysis = tid(engine, "reanalysis")
    drive(engine, until=reanalysis, outcomes={"classify": "constraint_issue"})
    unmet = unsatisfied_requirements(engine.state, engine.task(reanalysis))
    assert CLEAN in unmet and RETIMED not in unmet
    drive(engine, until=None)  # attested, reviewed, approved, as before M37
    assert engine.task(reanalysis).status is TaskStatus.COMPLETED


@needs(*GATE_TOOLS)
def test_without_a_timer_reanalysis_is_blocked_never_faked(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(TIMING)
    fix, reanalysis = tid(engine, "rtl-fix"), tid(engine, "reanalysis")
    drive(engine, until=fix, outcomes={"classify": "rtl_path"}, workspace=tmp_path / "drive")
    with_workspace(engine, fix, tmp_path / "fix")
    report = run_task(engine, fix, ModelRuntime(MockLLM(script=[answer(*counter_files(token(upstream(engine,
                                                                                               "classify"))))])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    review_task(engine, fix, ModelRuntime(MockLLM()))
    engine.approve(fix, human(engine.task(fix).approver), "gated")
    with_workspace(engine, reanalysis, tmp_path / "work")
    _inputs(engine, reanalysis, sdc=str(PROD3_SDC), top="counter", liberty=str(TINY_LIB))
    only_on_path(monkeypatch, tmp_path / "empty")  # no sta, no openroad, no yosys
    cite = token(upstream(engine, "rtl-fix"))
    report = run_task(engine, reanalysis, ModelRuntime(MockLLM(script=[_report(cite)])))

    assert report.status is ResultStatus.BLOCKED, report.detail
    assert "opensta needs sta on PATH, not found" in report.detail
    assert "openroad-sta needs openroad on PATH, not found" in report.detail
    task = engine.task(reanalysis)
    assert task.status is TaskStatus.BLOCKED and task.artifacts == ()
    assert [r for r in engine.state.tool_runs.values() if r.task == reanalysis] == []  # refused, never run


# --- sta.run synthesizes the RTL it is given ---------------------------------------------------------------


def _yosys_stand_in(bin_dir: Path, ok: bool = True) -> None:
    body = ("echo \"yosys: $*\"; printf 'module prod3(clk);\\n  input clk;\\nendmodule\\n' > netlist.v"
            if ok else "echo 'ERROR: syntax error'; exit 1")
    fake_tool(bin_dir, "yosys", body)


def test_sta_with_sources_synthesizes_then_times_in_one_run(broker_owner, tmp_path, monkeypatch):
    engine, _ = broker_owner
    bin_dir = tmp_path / "bin"
    _yosys_stand_in(bin_dir)
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)
    params = {"sources": str(PROD3 / "prod3.v"), "sdc": str(PROD3_SDC), "top": "prod3", "liberty": str(TINY_LIB)}
    run, outcome = invoke(engine, "sta.run", params, tmp_path / "w")
    assert run.succeeded and run.summary.startswith("opensta: timing met"), run.summary
    assert [c[0] for c in outcome.data["commands"]] == ["yosys", "sta"]
    netlist = tmp_path / "w" / "netlist.v"
    assert outcome.data["result"]["metrics"]["netlist"] == str(netlist)
    script = (tmp_path / "w" / "sta.tcl").read_text()
    assert f'read_verilog "{netlist}"' in script and "link_design prod3" in script
    synth = (tmp_path / "w" / "synth_liberty.ys").read_text()
    assert f'read_verilog -sv "{PROD3 / "prod3.v"}"' in synth and "write_verilog" in synth


def test_sta_input_problems_are_recorded_failed_runs_or_refusals(broker_owner, tmp_path, monkeypatch):
    engine, _ = broker_owner
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)
    shell_path = os.environ["PATH"]
    monkeypatch.setenv("PATH", str(bin_dir))  # the stand-in timer only: no Yosys, wherever the shell lives
    base = {"sdc": str(PROD3_SDC), "top": "prod3", "liberty": str(TINY_LIB)}
    with pytest.raises(ToolAccessDenied, match="needs yosys on PATH to synthesize sources"):
        invoke(engine, "sta.run", {**base, "sources": str(PROD3 / "prod3.v")}, tmp_path / "a")
    assert engine.state.tool_runs == {}
    monkeypatch.setenv("PATH", shell_path)

    _yosys_stand_in(bin_dir)
    both, _ = invoke(engine, "sta.run", {**base, "sources": str(PROD3 / "prod3.v"),
                                         "netlist": str(PROD3 / "prod3.v")}, tmp_path / "b")
    assert not both.succeeded and "a netlist or sources, not both" in both.summary
    neither, _ = invoke(engine, "sta.run", base, tmp_path / "c")
    assert not neither.succeeded and "missing parameter netlist" in neither.summary

    _yosys_stand_in(bin_dir, ok=False)
    bad, outcome = invoke(engine, "sta.run", {**base, "sources": str(PROD3 / "prod3.v")}, tmp_path / "d")
    assert not bad.succeeded and "synthesis failed" in bad.summary and "syntax error" in bad.summary
    assert [c[0] for c in outcome.data["commands"]] == ["yosys"]  # the timer never ran
    assert len(engine.state.tool_runs) == 3


@needs("yosys")
def test_real_synthesis_feeds_the_timer_the_netlist_it_wrote(broker_owner, tmp_path, monkeypatch):
    engine, _ = broker_owner
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    import shutil
    fake_tool(bin_dir, "yosys", f"exec '{shutil.which('yosys')}' \"$@\"")
    only_on_path(monkeypatch, bin_dir)
    params = {"sources": str(PROD3 / "prod3.v"), "sdc": str(PROD3_SDC), "top": "prod3", "liberty": str(TINY_LIB)}
    run, outcome = invoke(engine, "sta.run", params, tmp_path / "w")
    assert run.succeeded, run.summary
    netlist = Path(outcome.data["result"]["metrics"]["netlist"]).read_text()
    assert "module prod3(" in netlist and "DFF" in netlist


# --- Real, in CI's physical-design job: a timing-closure project whose fix closes timing ---------------------


@needs("openroad", "yosys", *GATE_TOOLS)
def test_a_real_timing_closure_project_shows_the_violation_and_the_fix(nirmaan_org, fixed_clock, tmp_path):
    pdk = nangate45()
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(TIMING)
    analysis, fix, reanalysis = (tid(engine, s) for s in ("sta-analysis", "rtl-fix", "reanalysis"))
    design = {"sdc": str(PROD3_SDC), "top": "prod3", **pdk}

    # Before: the RTL as it stands, under the project's SDC, on the analysis task.
    before, outcome = ToolBroker(engine).invoke(
        agent(engine.task(analysis).owner), "sta.run",
        {**design, "sources": str(PROD3 / "before" / "prod3.v"), "workdir": str(tmp_path / "before")}, analysis)
    before_metrics = outcome.data["result"]["metrics"]
    assert not before.succeeded and before.id in engine.state.tool_runs, before.summary
    assert before_metrics["worst_slack"] < 0 and before_metrics["tns"] < 0, before.summary

    # The fix: pipelined RTL through its RTL gates, reviewed and approved.
    drive(engine, until=fix, outcomes={"classify": "rtl_path"}, workspace=tmp_path / "drive")
    with_workspace(engine, fix, tmp_path / "fix")
    cite = token(upstream(engine, "classify"))
    rtl = file("prod3.v", "rtl_source", (PROD3 / "prod3.v").read_text(), cite, entry="prod3")
    tb = file("prod3_tb.v", "testbench", (PROD3 / "prod3_tb.v").read_text(), cite, entry="prod3_tb")
    report = run_task(engine, fix, ModelRuntime(MockLLM(script=[answer(rtl, tb)])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    review_task(engine, fix, ModelRuntime(MockLLM()))
    engine.approve(fix, human(engine.task(fix).approver), "pipelined, gated")
    fixed = next(engine.state.artifacts[a] for a in engine.task(fix).artifacts
                 if engine.state.artifacts[a].kind == "rtl_source")
    assert fixed.assurance is Assurance.APPROVED

    # After: reanalysis times the approved fix for real, and goes to review.
    assert engine.task(reanalysis).status is TaskStatus.READY
    with_workspace(engine, reanalysis, tmp_path / "re")
    _inputs(engine, reanalysis, **design)
    report = run_task(engine, reanalysis, ModelRuntime(MockLLM(script=[_report(token(fixed.id))])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    after = runs_of(engine, report)["sta.run"]
    assert after.succeeded and fixed.location in after.params["sources"], after.summary
    after_metrics = json.loads(Path(after.references[1]).read_text())["result"]["metrics"]
    assert after_metrics["worst_slack"] >= 0 and after_metrics["tns"] == 0
    ev = next(engine.state.evidence[e] for e in report.evidence if engine.state.evidence[e].tool_run == after.id)
    assert ev.substantiated and ev.kind is EvidenceKind.TOOL_RUN
    assert unsatisfied_requirements(engine.state, engine.task(reanalysis)) == ["Independent review recorded"]
    (tmp_path / "slack.json").write_text(json.dumps({
        "before": {k: before_metrics[k] for k in ("worst_slack", "worst_hold_slack", "tns")},
        "after": {k: after_metrics[k] for k in ("worst_slack", "worst_hold_slack", "tns")},
        "before_summary": before.summary, "after_summary": after.summary}, indent=2))


# --- Named properties and macros, on text --------------------------------------------------------------------


def _sites(text: str, defs=None) -> list[tuple[str, str]]:
    return [(s.kind, s.reason) for s in derive(text, "x.v", defs).sites]


def test_a_named_property_with_arguments_is_inlined_and_covered_on_its_path():
    text = ("module m(input clk, a, input [3:0] c);\n"
            "    property within(x, l = 4'd9);\n        x <= l;\n    endproperty\n"
            "    always @(posedge clk)\n        if (a)\n            assert property (within(c));\n"
            "endmodule\n")
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["guarded"]
    lines = d.text.splitlines()
    assert d.text.count("\n") == text.count("\n")
    assert lines[6] == "            begin cover property (1'b1); assert property ((c) <= (4'd9)); end"
    assert not "".join(lines[1:4]).strip()  # the declaration is blanked, its newlines kept
    (site,) = d.sites
    assert site.line == 7 and lines[6][site.column - 1:].startswith("cover property")


def test_a_named_implication_gets_a_cover_of_its_antecedent_with_the_arguments():
    text = ("module m(input clk, a, b);\n"
            "    property p_impl(logic x, logic y);\n        @(posedge clk) disable iff (!b) x |=> y;\n    endproperty\n"
            "    assert property (p_impl(a && b, a));\n"
            "    always @(posedge clk) assert property (@(posedge clk) q(a));\n"
            "    property q(z); z; endproperty\n"
            "endmodule\n")
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["implication", "guarded"]
    line = d.text.splitlines()[4]
    assert line.startswith("    assert property (@(posedge clk) disable iff (!b) (a && b) |=> (a));")
    assert line.endswith(" cover property (@(posedge clk) disable iff (!b) (a && b));")


def test_nested_named_properties_and_assumptions_are_inlined_too():
    text = ("module m(input clk, a, b);\n"
            "    property inner(x); x || b; endproperty\n"
            "    property outer(y); inner(y); endproperty\n"
            "    always @(posedge clk) begin assume property (inner(a)); if (b) assert property (outer(a)); end\n"
            "endmodule\n")
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["guarded"]
    assert "assume property ((a) || b);" in d.text
    assert "begin cover property (1'b1); assert property (((a)) || b); end" in d.text


def test_a_macro_that_asserts_is_expanded_and_covered_without_moving_a_line():
    text = ("`define ASSERT_IMPL(a, b) if (a) assert (b)\n"
            "`define CHK(x) \\\n    assert (x)\n"
            "module m(input clk, a, b);\n"
            "    always @(posedge clk) `ASSERT_IMPL(a && b,\n                                       a);\n"
            "    always @(posedge clk) if (b) `CHK(a);\n"
            "    localparam W = `WIDTH;\n"
            "endmodule\n")
    d = derive(text, "x.v")
    assert [s.kind for s in d.sites] == ["guarded", "guarded"]
    assert d.text.count("\n") == text.count("\n")
    lines = d.text.splitlines()
    assert lines[4] == "    always @(posedge clk) if (a && b) begin cover (1'b1); assert (a); end"
    assert lines[5] == ""  # the use's second line: its newline follows the expansion
    assert lines[6] == "    always @(posedge clk) if (b) begin cover (1'b1); assert (a); end"
    assert "`WIDTH" in lines[7]  # a macro that does not assert is left to the frontend
    assert [s.line for s in d.sites] == [5, 7]


def test_a_macro_defined_in_another_file_of_the_setup_is_expanded():
    header = "`define ASSERT_IMPL(a, b) if (a) assert (b)\n"
    body = "module m(input clk, a, b);\n    always @(posedge clk) `ASSERT_IMPL(a, b);\nendmodule\n"
    defs = definitions([header, body])
    assert derive(header, "h.vh", defs).sites == ()  # defining a macro asserts nothing
    d = derive(body, "m.v", defs)
    assert [s.kind for s in d.sites] == ["guarded"]
    assert "if (a) begin cover (1'b1); assert (b); end" in d.text


REFUSED = [
    ("module m(input a, b);\n    property p; a; endproperty\n    property q; b; endproperty\n"
     "    assert property (p and q);\nendmodule\n",
     "the named property p is used inside an expression; only a whole property body is inlined"),
    ("module m(input a);\n    property p(x); x; endproperty\n    assert property (p(.x(a)));\nendmodule\n",
     "named arguments to a property are not supported"),
    ("module m(input a, b);\n    property p(x, y); x || y; endproperty\n    assert property (p(a));\nendmodule\n",
     "property p takes 2 arguments, 1 given"),
    ("module m(input clk, a);\n    property p; @(posedge clk) a; endproperty\n"
     "    assert property (@(posedge clk) p);\nendmodule\n",
     "both the assertion and property p name a clock"),
    ("module m(input clk, a);\n    sequence s; a ##1 a; endsequence\n    assert property (s);\nendmodule\n",
     "the named sequence s is not expanded"),
    ("`define CHK(x) assert (x)\n`define CHK(x) assert (!(x))\nmodule m(input clk, a);\n"
     "    always @(posedge clk) `CHK(a);\nendmodule\n",
     "the macro CHK is defined more than once"),
    ("`define CHK(x) assert (x``_ok)\nmodule m(input clk, a);\n    always @(posedge clk) `CHK(a);\nendmodule\n",
     "the macro CHK pastes or stringifies tokens"),
    ("`define CHK(x, y) assert (x || y)\nmodule m(input clk, a);\n    always @(posedge clk) `CHK(a);\nendmodule\n",
     "the macro CHK takes 2 arguments, 1 given"),
]


@pytest.mark.parametrize("text,reason", REFUSED, ids=[r for _, r in REFUSED])
def test_what_cannot_be_derived_is_refused_with_its_line_and_reason(text, reason):
    sites = derive(text, "x.v").sites
    assert [(s.kind, s.reason) for s in sites] == [("underived", reason)]
    line = next(i for i, ln in enumerate(text.splitlines(), 1) if re.search(r"assert|`CHK\(a", ln)
                and "define" not in ln and "property p" not in ln[:16])
    assert sites[0].line == line


def test_nesting_too_deep_is_refused():
    props = "".join(f"    property p{i}; p{i + 1}; endproperty\n" for i in range(10))
    text = f"module m(input a);\n{props}    property p10; a; endproperty\n    assert property (p0);\nendmodule\n"
    assert _sites(text) == [("underived", "property p0 is nested too deeply")]


# --- Named properties and macros, in real cover runs ----------------------------------------------------------


PROP_SETUPS = [("props/counter_props.sby", "props/counter_props.v", 2),
               ("props/counter_macros.sby", "props/counter_macros.v", 1)]


@needs("sby", "yosys", "yices-smt2")
@pytest.mark.parametrize("sby,source,assertions", PROP_SETUPS, ids=["named-properties", "macros"])
def test_every_named_property_and_macro_antecedent_is_reached(broker_owner, tmp_path, sby, source, assertions):
    engine, owner = broker_owner
    params = {"sby": str(RTL / sby), "sources": str(RTL / source), "workdir": str(tmp_path)}
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", params)
    assert run.succeeded, run.summary
    metrics = json.loads(Path(run.references[1]).read_text())["result"]["metrics"]
    assert metrics["covers_reached"] == 1 and metrics["covers_unreached"] == 0
    assert metrics["antecedents_reached"] == assertions and metrics["antecedents_unreached"] == 0
    assert metrics["antecedents_unelaborated"] == 0


def _setup(tmp_path: Path, name: str, rtl: str, *extra: str) -> dict[str, str]:
    (tmp_path / f"{name}.v").write_text(rtl)
    for other in extra:
        (tmp_path / other).write_text((PROPS / other).read_text())
    (tmp_path / f"{name}.sby").write_text((PROPS / f"{name}.sby").read_text())
    return {"sby": str(tmp_path / f"{name}.sby"), "sources": str(tmp_path / f"{name}.v"),
            "workdir": str(tmp_path / "run")}


@needs("sby", "yosys", "yices-smt2")
def test_an_unreachable_antecedent_through_a_named_property_fails(broker_owner, tmp_path):
    engine, owner = broker_owner
    source = (PROPS / "counter_props.v").read_text()
    never = "        if (seen_reset && count > LIMIT)\n            assert property (within_limit(count, LIMIT));\n"
    rtl = source.replace("        if (seen_reset && !rst)\n            assert property", never +
                         "        if (seen_reset && !rst)\n            assert property", 1)
    assert rtl != source
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", _setup(tmp_path, "counter_props", rtl))
    line = rtl.splitlines().index("        if (seen_reset && count > LIMIT)") + 2
    assert run.id in engine.state.tool_runs and not run.succeeded
    assert "vacuous: 1 of 3 assertion antecedents never reached" in run.summary, run.summary
    assert f"counter_props.v:{line} is never checked" in run.summary


@needs("sby", "yosys", "yices-smt2")
def test_an_unreachable_antecedent_through_a_macro_fails(broker_owner, tmp_path):
    engine, owner = broker_owner
    source = (PROPS / "counter_macros.v").read_text()
    use = "        `ASSERT_IMPL(seen_reset, count <= LIMIT);\n"
    rtl = source.replace(use, use + "        `ASSERT_IMPL(seen_reset && count > LIMIT, !wrap);\n")
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover",
                                       _setup(tmp_path, "counter_macros", rtl, "assert_macros.vh"))
    line = rtl.splitlines().index("        `ASSERT_IMPL(seen_reset && count > LIMIT, !wrap);") + 1
    assert not run.succeeded and "vacuous: 1 of 2 assertion antecedents never reached" in run.summary, run.summary
    assert f"counter_macros.v:{line} is never checked" in run.summary


@needs("sby", "yosys")
def test_an_unsupported_named_property_is_refused_by_the_cover_run(broker_owner, tmp_path):
    engine, owner = broker_owner
    rtl = (PROPS / "counter_props.v").read_text().replace(
        "assert property (wraps_when_enabled);", "assert property (wraps_when_enabled and wraps_when_enabled);")
    run, _ = ToolBroker(engine).invoke(owner, "formal.cover", _setup(tmp_path, "counter_props", rtl))
    assert not run.succeeded and "cannot derive the antecedent of 1 assertion" in run.summary
    assert "the named property wraps_when_enabled is used inside an expression" in run.summary


# --- Crown jewel: a branch-scoped requirement is data alone ----------------------------------------------------


def test_a_new_workflow_scopes_a_requirement_to_one_branch_with_no_core_changes(fixed_clock):
    from nirmaan.company import builder
    from nirmaan.company.workflows import REVIEWED, rv, st
    from nirmaan.models import EvidenceKind as K
    from nirmaan.models import EvidenceRequirement, IntentRule, WorkflowTemplate
    from nirmaan.org import register_extension, unregister_extension

    signed = EvidenceRequirement(description="Impact signed off by a person", accepts=(K.HUMAN_ATTESTATION,),
                                 when_upstream=("impact_analysis",))
    flow = WorkflowTemplate(
        id="test-branch-scoped", name="Branch scoped", description="One check, on one branch only.",
        intents=("branch_scoped",),
        stages=(st("triage", "Triage", "RTL", "rtl.impact", review=rv("rtl.review"), outcomes=("deep", "shallow"),
                   outputs=("root_cause_analysis",), evidence=(REVIEWED,)),
                st("deep", "Deep", "RTL", "rtl.impact", depends_on=("triage",), branch=("triage", "deep"),
                   review=rv("rtl.review"), outputs=("impact_analysis",), evidence=(REVIEWED,)),
                st("shallow", "Shallow", "RTL", "req.analyze", depends_on=("triage",), branch=("triage", "shallow"),
                   review=rv("req.review"), outputs=("requirements_spec",), evidence=(REVIEWED,)),
                st("close", "Close", "RTL", "rtl.impact", depends_on=("deep", "shallow"), review=rv("rtl.review"),
                   outputs=("impact_analysis",), evidence=(REVIEWED, signed))))

    @register_extension("test-branch-scoped")
    def scoped(b):
        b.add(IntentRule(intent="branch_scoped", patterns=(r"\bbranch scoped\b",), priority=1), flow)

    try:
        for outcome, applies in (("deep", True), ("shallow", False)):
            engine = Orchestrator(builder().build(), clock=fixed_clock).plan("A branch scoped change.")
            close = tid(engine, "close")
            drive(engine, until=close, outcomes={"triage": outcome})
            assert (signed.description in unsatisfied_requirements(engine.state, engine.task(close))) is applies
    finally:
        unregister_extension("test-branch-scoped")


# --- Laws ----------------------------------------------------------------------------------------------------


def test_the_core_names_no_stage_tool_or_style_of_this_milestone():
    src = Path(__file__).parents[1] / "src" / "nirmaan"
    for part in ("runtime", "work", "orchestrator", "models"):
        for py in (src / part).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for word in ("antecedent", "endproperty", "`define", "sta.run", "synth.run", "rtl_source", "reanalysis"):
                assert word not in text, (py, word)
    deriver = (src / "integrations" / "eda_antecedents.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+(nirmaan|veritriage)", deriver, re.MULTILINE)


def test_ci_runs_the_real_timing_closure_project_in_the_physical_design_job():
    ci = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = ci[ci.index("  physical-design:"):ci.index("  dashes:")]
    required = next(ln for ln in job.splitlines() if ln.strip().startswith("NIRMAAN_REQUIRE_EDA:"))
    assert {"yosys", "openroad", "sta", *GATE_TOOLS} <= set(required.split(":", 1)[1].split())
    assert "tests/test_nirmaan_sta_antecedents.py" in job
