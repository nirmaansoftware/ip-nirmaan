"""Repro gates on regression investigation: triage and root cause show the failure reproduces (M71).

A regression investigation asked to reproduce its failure hands over the RTL under
investigation, and triage and root cause each write repro testbenches that
``simulator.run`` runs with ``expect=fail`` on that approved RTL, one file at a
time, before the work goes on: such a run passes only when the testbench's own
verdict reports a failed check, and only a requirement that fixes ``expect=fail``
reads it. Through the eval harness, the must-fail scorer then judges a root-cause
seat's repro against the fixed RTL, and ``must-fail-each`` a triage seat's repros,
one per seeded bug. Every request that does not ask for a reproduction plans
exactly as before. Real-tool tests skip when an executable is absent (or fail
when CI names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import pytest

from laws import needs
from test_nirmaan_applicability_golden import REQUESTS

from nirmaan.company import builder
from nirmaan.evals import load_case, run_case, validate_case
from nirmaan.integrations.eda_parsers import parse_reproduction
from nirmaan.models import FileInput, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import assemble

REPO = Path(__file__).resolve().parents[1]
COUNTER = "tests/fixtures/rtl/counter.v"
FAILING_LOG = "tests/fixtures/eda/icarus_sim_fail.log"
SIM_TOOLS = ("iverilog", "vvp")

ROOT_CAUSE = "Investigate the failing counter test in regression and reproduce the failure."
TRIAGE = "Triage the failing tests in the nightly regression and write a repro for each failure."
#: Regression investigations that ask for no reproduction, and requests elsewhere that say "reproduce": as before.
NOT_REPRODUCTION = (
    "Investigate the failing uart_tx test in regression.",
    "Triage the failing tests in the nightly regression.",
    "The regression started failing after the latest commit; investigate the failure.",
    "Create a FIFO whose overflow behaviour reproduces the old design's.",
)


def _task(engine, stage):
    tasks = [t for t in engine.state.tasks.values() if t.stage == stage]
    assert len(tasks) == 1, [t.id for t in tasks]
    return tasks[0]


def _gates(task):
    return [r for r in task.evidence_requirements if r.before_review]


# --- Planning --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("request_text", [ROOT_CAUSE, TRIAGE])
def test_a_reproduction_hands_over_the_rtl_and_gates_triage_and_root_cause(request_text, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert engine.state.project.workflows == ("regression-investigation",)
    assert "reproduction" in engine.state.project.analysis.features
    handed = _task(engine, "design-under-investigation")
    assert handed.expected_outputs == ("rtl_source",) and not _gates(handed) and handed.reviewer
    for stage in ("triage", "root-cause"):
        task = _task(engine, stage)
        assert handed.id in task.depends_on and "testbench" in task.expected_outputs
        [gate] = _gates(task)
        assert gate.tools == ("simulator.run",) and gate.params == (("expect", "fail"),)
        assert gate.files == (FileInput(param="sources", kinds=("rtl_source",), upstream=True),
                              FileInput(param="sources", kinds=("testbench",), each=True),
                              FileInput(param="top", kinds=("testbench",), entry=True))
    assert _task(engine, "triage").skills == ("failure_triage",)
    assert _task(engine, "root-cause").skills == ("root_cause_analysis",)


@pytest.mark.parametrize("request_text", [ROOT_CAUSE, TRIAGE])
def test_each_debug_seat_carries_its_skill_and_may_run_the_reproduction(request_text, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    for stage, skill, owner in (("triage", "failure_triage", "verification.debug.triage.engineer"),
                                ("root-cause", "root_cause_analysis", "verification.debug.root_cause.senior")):
        task = _task(engine, stage)
        assert task.owner == owner
        assert "simulator.run" in nirmaan_org.tools_of(owner)
        for seat in (None, task.owner, task.reviewer):
            if seat is None and task.reviewer is None:
                continue
            packet = assemble(engine, task.id) if seat is None else assemble(engine, task.id, role=seat)
            assert skill in {s.id for s in packet.domain.skills}, seat
            assert packet.domain.declines is None


def test_one_at_a_time_is_for_the_tasks_own_files_only():
    with pytest.raises(ValueError, match="one at a time"):
        FileInput(param="sources", kinds=("rtl_source",), upstream=True, each=True)
    with pytest.raises(ValueError, match="one at a time"):
        FileInput(param="top", kinds=("testbench",), entry=True, each=True)


def test_a_refinement_may_depend_only_on_an_earlier_stage():
    from nirmaan.company.workflows import REGRESSION_INVESTIGATION
    from nirmaan.models import Condition, Refinement

    b = builder()
    late = Refinement(when=Condition(any_of=("reproduction",)), depends_on=("verify-fix",))
    stages = tuple(s.model_copy(update={"refinements": (late,)}) if s.id == "triage" else s
                   for s in REGRESSION_INVESTIGATION.stages)
    b.definition.workflows = [wf.model_copy(update={"stages": stages}) if wf.id == "regression-investigation"
                              else wf for wf in b.definition.workflows]
    with pytest.raises(ValueError, match="a refinement depends on verify-fix, which is not an earlier stage"):
        b.build()


# --- The verdict ---------------------------------------------------------------------------------------------

NONCE = "0123456789abcdef"


def _log(*lines: str) -> str:
    return "\n".join(["$ iverilog -g2012 -o sim.vvp -s tb tb.v counter.v", f"$ vvp -n sim.vvp +nirmaan_nonce={NONCE}",
                      *lines, "tb.v:40: $finish called at 120 (1ps)", ""])


@pytest.mark.parametrize("log,codes,reproduced,said", [
    (_log(f"NIRMAAN-SIM {NONCE} 1 passed, 1 failed"), (0, 0), True, "reports 1 of 2 checks failed"),
    (_log(f"NIRMAAN-SIM {NONCE} 2 passed, 0 failed"), (0, 0), False, "all 2 checks passed"),
    (_log("no verdict here"), (0, 0), False, "no single verdict"),
    (_log(f"NIRMAAN-SIM {NONCE} 0 passed, 1 failed", f"NIRMAAN-SIM {NONCE} 0 passed, 1 failed"), (0, 0), False,
     "no single verdict"),
    (_log(f"NIRMAAN-SIM {NONCE} 0 passed, 1 failed", "NIRMAAN-SIM feedface 0 passed, 1 failed"), (0, 0), False,
     "not printed by this run's testbench"),
    ("$ iverilog -g2012 -o sim.vvp -s tb tb.v counter.v\ntb.v:3: syntax error\n", (1,), False,
     "the build did not succeed"),
    (f"$ vvp -n sim.vvp +nirmaan_nonce={NONCE}\nNIRMAAN-SIM {NONCE} 0 passed, 1 failed\n", (0, 0), False,
     "$finish never reached"),
])
def test_only_the_testbenchs_own_failed_check_is_a_reproduction(log, codes, reproduced, said):
    result = parse_reproduction(log, codes, NONCE)
    assert result.passed is reproduced and result.metrics["reproduced"] is reproduced
    assert said in result.summary, result.summary


def test_a_reproduction_is_read_only_where_a_requirement_fixes_it():
    """A passing ``expect=fail`` run never meets a requirement for a passing simulation, and vice versa."""
    from types import SimpleNamespace

    from nirmaan.company.workflows import REPRODUCES, RTL_GATES
    from nirmaan.models import EvidenceKind, ToolRun
    from nirmaan.work.policy import satisfies

    def met(run: ToolRun, req) -> bool:
        state = SimpleNamespace(tool_runs={run.id: run})
        return satisfies(state, SimpleNamespace(substantiated=True, kind=EvidenceKind.TOOL_RUN, tool_run=run.id), req)

    passing = next(r for r in RTL_GATES if r.tools == ("simulator.run",))
    repro = ToolRun(id="run-0001", tool="simulator.run", actor="a", task="t", succeeded=True, summary="reproduced",
                    params={"sources": ("counter.v", "tb.v"), "top": "tb", "expect": "fail"})
    plain = repro.model_copy(update={"params": {"sources": ("counter.v", "tb.v"), "top": "tb"}})
    assert met(repro, REPRODUCES) and not met(repro, passing)
    assert met(plain, passing) and not met(plain, REPRODUCES)
    assert not repro.answers(()) and plain.answers(())
    explicit = plain.model_copy(update={"params": {**plain.params, "expect": "pass"}})
    assert met(explicit, passing) and explicit.answers(())  # pass, said or not, is a plain pass


@needs(*SIM_TOOLS)
def test_an_expect_other_than_pass_or_fail_is_refused(nirmaan_org, tmp_path):
    from nirmaan.runtime import ToolBroker
    from nirmaan.models import Actor, ActorKind

    engine = Orchestrator(nirmaan_org).plan(ROOT_CAUSE)
    tb = _write(tmp_path, "wrap_repro.v", _tb("wrap_repro", WRAP))
    owner = _task(engine, "root-cause").owner
    _, outcome = ToolBroker(engine).invoke(Actor(role=owner, kind=ActorKind.AI_AGENT, name="t"), "simulator.run",
                                           {"sources": [str(REPO / COUNTER), tb], "top": "wrap_repro",
                                            "expect": "maybe", "workdir": str(tmp_path / "run")})
    assert not outcome.succeeded and "expect must be pass or fail" in outcome.summary


# --- Nothing else moves ----------------------------------------------------------------------------------


@cache
def _pre_m71_org():
    """The organization with M71's planning data taken out: no reproduction feature, no handed-over RTL stage,
    no refinements or repro gates on triage and root cause. The new tool and the two cards' grant of it stay:
    they route nothing."""
    from nirmaan.company.workflows import REPRODUCES

    b = builder()
    d = b.definition
    d.features = [f for f in d.features if f.feature != "reproduction"]

    def before(stage):
        return stage.model_copy(update={"refinements": (),
                                        "evidence": tuple(r for r in stage.evidence if r != REPRODUCES)})

    d.workflows = [wf.model_copy(update={"stages": tuple(before(s) for s in wf.stages
                                                         if s.id != "design-under-investigation")})
                   if wf.id == "regression-investigation" else wf for wf in d.workflows]
    return b.build()


def _plan(org, text, clock):
    """Every task, keyed by its ID within the project (the project ID follows the organization's fingerprint)."""
    state = Orchestrator(org, clock=clock).plan(text).state
    pid = state.project.id
    return {t.id.removeprefix(pid + ":"): json.loads(t.model_dump_json().replace(pid, "<project>"))
            for t in state.tasks.values()}


@pytest.mark.parametrize("request_text", [*REQUESTS, *NOT_REPRODUCTION])
def test_every_other_request_plans_exactly_as_before(request_text, nirmaan_org, fixed_clock):
    project = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text).state.project
    # The feature may be read elsewhere ("reproduces" in a FIFO request); only regression investigation uses it.
    assert "reproduction" not in project.analysis.features or "regression-investigation" not in project.workflows
    assert _plan(_pre_m71_org(), request_text, fixed_clock) == _plan(nirmaan_org, request_text, fixed_clock)


def test_a_reproduction_changes_only_the_handed_over_rtl_triage_and_root_cause(nirmaan_org, fixed_clock):
    before, after = _plan(_pre_m71_org(), ROOT_CAUSE, fixed_clock), _plan(nirmaan_org, ROOT_CAUSE, fixed_clock)
    assert set(after) - set(before) == {"design-under-investigation", "ws.rtl"}
    changed = {tid for tid in before if before[tid] != after[tid]}
    assert {"triage", "root-cause"} <= changed
    # The path through the handed-over RTL is one stage longer, so later tasks' priorities move with it, and
    # the debug workstream waits on that stage.
    for tid in changed - {"triage", "root-cause"}:
        assert {k for k in after[tid] if after[tid][k] != before[tid][k]} <= {"priority", "status"}, tid


# --- The gates, for real, through the eval harness ---------------------------------------------------------

#: Two bugs in the counter, each one change: after a wrap the count restarts at 1; it counts with ``en`` low.
WRAP_BUG = ("        else if (wrap)\n            count <= 4'd0;", "        else if (wrap)\n            count <= 4'd1;")
HOLD_BUG = ("        else if (en)\n            count <= count + 4'd1;", "        else\n            count <= count + 4'd1;")

WRAP = """\
        en = 1'b1;
        for (i = 1; i <= 10; i = i + 1) begin
            @(negedge clk);
            if (i >= 9)
                check(i % 10);
        end
"""
HOLD = """\
        en = 1'b1;
        for (i = 1; i <= 3; i = i + 1)
            @(negedge clk);
        check(4'd3);
        en = 1'b0;
        for (i = 1; i <= 3; i = i + 1)
            @(negedge clk);
        check(4'd3);
"""
#: Checks only before the wrap: it passes on the wrap bug, so it reproduces nothing.
WEAK = """\
        en = 1'b1;
        for (i = 1; i <= 5; i = i + 1)
            @(negedge clk);
        check(4'd5);
"""
#: Both checks in one testbench: it fails on either bug, so it cannot stand for one bucket.
BOTH = HOLD + """\
        en = 1'b1;
        for (i = 1; i <= 7; i = i + 1)
            @(negedge clk);
        check(4'd0);
"""


def _tb(module: str, body: str) -> str:
    return f"""\
`timescale 1ns / 1ps
module {module};
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer errors = 0;
    integer checks = 0;
    integer i;
    reg [8*64-1:0] nonce;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    task check(input [3:0] want);
        begin
            checks = checks + 1;
            if (count !== want) begin
                $display("ERROR: count is %0d, expected %0d", count, want);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        @(negedge clk);
        rst = 1'b0;
{body}        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
"""


def _write(folder: Path, name: str, text: str) -> str:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _rtl(folder: Path, *bugs: tuple[str, str]) -> str:
    text = (REPO / COUNTER).read_text(encoding="utf-8")
    for old, new in bugs:
        assert old in text
        text = text.replace(old, new)
    return _write(folder, "counter.v", text)


def _repro(folder: Path, module: str, body: str) -> dict:
    return {"path": _write(folder, f"{module}.v", _tb(module, body)), "kind": "testbench", "entry": module}


def _case(tmp_path: Path, request: str, seat: str, upstream: dict, reference: list[dict], held_out: list[dict],
          **extra) -> Path:
    data = {"id": f"tmp/repro-{seat}", "request": request, "seat": seat,
            "expected_behavior": "Repro testbenches that fail on the RTL under investigation and pass on the fix.",
            "upstream": upstream, "reference": reference, "held_out": held_out, **extra}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _root_cause_case(tmp_path: Path, seat_body: str) -> Path:
    buggy = _rtl(tmp_path / "under-investigation", WRAP_BUG)
    report = _write(tmp_path / "triage", "triage_report.md", "One bucket: the count after a wrap is 1, not 0.\n")
    return _case(
        tmp_path, ROOT_CAUSE, "root-cause",
        {"design-under-investigation": [{"path": buggy, "kind": "rtl_source", "entry": "counter"}],
         "triage": [{"path": report, "kind": "triage_report"}, _repro(tmp_path / "triage", "wrap_repro", WRAP)]},
        [{"path": _write(tmp_path / "seat", "root_cause.md", "RTL bug: the wrap branch loads 1, not 0.\n"),
          "kind": "root_cause_analysis"}, _repro(tmp_path / "seat", "root_cause_repro", seat_body)],
        [{"name": "The seat's repro passes on the fixed RTL and fails on the RTL under investigation",
          "scorer": "must-fail", "tool": "simulator.run", "seat_files": {"sources": ["testbench"]},
          "seat_entries": {"top": ["testbench"]}, "case_files": {"sources": [COUNTER]},
          "mutants": {COUNTER: [buggy]}}],
        outcome="rtl_bug", inputs={"triage": {"paths": [FAILING_LOG]}})


@needs(*SIM_TOOLS)
def test_a_root_cause_seat_reproduces_the_failure_and_its_repro_is_judged_against_the_fix(nirmaan_org,
                                                                                         fixed_clock, tmp_path):
    case = load_case(_root_cause_case(tmp_path, WRAP))
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [g.tool for g in result.gate_runs] == ["simulator.run"] and result.gate_runs[0].succeeded
    assert "failure reproduced" in result.gate_runs[0].summary
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores


@needs(*SIM_TOOLS)
def test_a_root_cause_whose_repro_passes_on_the_rtl_does_not_reach_review(nirmaan_org, fixed_clock, tmp_path):
    case = load_case(_root_cause_case(tmp_path, WEAK))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted, result
    assert "failure not reproduced" in result.detail and "all 1 check passed" in result.detail, result.detail


def test_a_decision_seat_names_its_outcome(nirmaan_org, tmp_path):
    case = load_case(_root_cause_case(tmp_path, WRAP))
    assert validate_case(nirmaan_org, case.model_copy(update={"outcome": None}), REPO) == [
        "seat 'root-cause' is a decision: the case's outcome must be one of "
        "['rtl_bug', 'testbench_bug', 'infrastructure', 'spec_ambiguity'], not None"]
    assert "inputs for stage 'change-correlation', which is not in the planned workflow" in validate_case(
        nirmaan_org, case.model_copy(update={"inputs": {"change-correlation": {"paths": (FAILING_LOG,)}}}), REPO)


def _triage_case(tmp_path: Path, *repros: tuple[str, str]) -> Path:
    clean = str(REPO / COUNTER)
    return _case(
        tmp_path, TRIAGE, "triage",
        {"design-under-investigation": [{"path": _rtl(tmp_path / "under-investigation", WRAP_BUG, HOLD_BUG),
                                         "kind": "rtl_source", "entry": "counter"}]},
        [{"path": _write(tmp_path / "seat", "triage_report.md", "Two buckets: the wrap, and counting while idle.\n"),
          "kind": "triage_report"}, *(_repro(tmp_path / "seat", m, b) for m, b in repros)],
        [{"name": "Each bucket's repro passes on the fixed RTL, and each seeded bug fails a repro of its own",
          "scorer": "must-fail-each", "tool": "simulator.run", "seat_files": {"sources": ["testbench"]},
          "seat_entries": {"top": ["testbench"]}, "case_files": {"sources": [clean]},
          "mutants": {clean: [_rtl(tmp_path / "bug-wrap", WRAP_BUG), _rtl(tmp_path / "bug-hold", HOLD_BUG)]}}],
        inputs={"triage": {"paths": [FAILING_LOG]}})


@needs(*SIM_TOOLS)
def test_a_triage_seat_reproduces_each_bucket_on_its_own_and_each_bug_fails_a_repro_of_its_own(nirmaan_org,
                                                                                              fixed_clock, tmp_path):
    case = load_case(_triage_case(tmp_path, ("wrap_repro", WRAP), ("hold_repro", HOLD)))
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    repro = [g for g in result.gate_runs if "failure reproduced" in g.summary]
    assert len(repro) == 2 and all(g.succeeded for g in repro), repro  # one run per repro, each on its own
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores
    assert "each of 2 mutants fails a file of its own" in result.scores[0].summary


@needs(*SIM_TOOLS)
def test_one_repro_that_fails_every_bug_cannot_stand_for_two_buckets(nirmaan_org, fixed_clock, tmp_path):
    case = load_case(_triage_case(tmp_path, ("both_repro", BOTH)))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [s.status for s in result.scores] == [ScoreStatus.FAILED], result.scores
    assert "only 1 of 2 mutants have a file of their own" in result.scores[0].summary


@needs(*SIM_TOOLS)
def test_a_triage_repro_that_does_not_reproduce_stops_the_work_even_beside_one_that_does(nirmaan_org,
                                                                                       fixed_clock, tmp_path):
    case = load_case(_triage_case(tmp_path, ("wrap_repro", WRAP), ("weak_repro", WEAK)))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted, result
    assert "weak_repro.v on its own" in result.detail, result.detail
