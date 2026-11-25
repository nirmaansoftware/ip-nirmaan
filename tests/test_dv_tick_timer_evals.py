"""The tick timer verification eval cases (RX-E2, wave 2 close).

Two cases judge verification seats of M68's block-verification workflow on one approved block, the timer in
``tests/fixtures/dv/tick_timer/``, which has a one-shot and a periodic mode:

* ``dv/coverage-tick-timer`` judges the coverage seat (``code_coverage``): the seat's testbench must meet the
  coverage bounds on the approved RTL and fail each of four RTL mutants, one of them wrong in periodic mode only.
  That mutant is the second coverage case's answer to a surviving-mutant failure of ``dv/coverage-irq-ctrl``
  (coverage met, the masked path never checked): a testbench that checks the masked interrupt in one mode only
  meets the bounds and survives it, and a test here shows that.
* ``dv/plan-tick-timer`` judges the dv-plan seat (``verification_planning``): the seat's plan must pass
  ``vplan.check`` against the approved specification and fail against six specification mutants (a requirement
  added, removed, one number changed, one ID renamed, one ID tagged twice, one requirement changed in one mode).

``functional_coverage`` is not named: the coverage seat of block verification holds ``code_coverage`` only, and
the case judges line and toggle coverage, not a coverage model built from the plan.

No coverage percentage is stated in the repository for either case: the real-tool tests assert the bounds with
Verilator (``laws.needs`` skips them where it is absent), so each CI run is the record.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS

from nirmaan.company.workflows import COVERAGE_TARGETS
from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.evals.scorers import ScoreContext, scorer_spec
from nirmaan.models import Actor, ActorKind, ScoreStatus
from nirmaan.models.workflow import Bound
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, ToolBroker, ToolHandle, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
TT = "tests/fixtures/dv/tick_timer"
FIXTURE = REPO / TT
COV = "dv/coverage-tick-timer"
PLAN = "dv/plan-tick-timer"
COVERAGE_TOOLS = ("verilator", "verilator_coverage")

#: Each case: its seat, the seat task's skills, owner and reviewer (docs/BLOCK_VERIFICATION.md).
CASES = {
    COV: ("coverage", ("code_coverage",), None, None),
    PLAN: ("dv-plan", ("verification_planning",), "verification.methodology.planning.engineer",
           "verification.methodology.planning.senior"),
}

#: The RTL mutants of the coverage control, in the order it runs them; the last one is wrong in periodic mode only.
RTL_MUTANTS = ("tick_timer_oneshot_keeps_running.v", "tick_timer_load_late_applies.v",
               "tick_timer_clear_beats_set.v", "tick_timer_irq_ie_ignored_periodic.v")
#: The weak testbenches: each passes its own checks on the approved RTL and misses the bounds, and why.
WEAK = {
    "tick_timer_idle_tb.sv": "never starts the timer",
    "tick_timer_no_expiry_tb.sv": "never lets the count reach zero",
    "tick_timer_oneshot_only_tb.sv": "never runs periodic mode, the interrupt or the clear",
}
#: The specification mutants of the plan control, each with the problem vplan.check reports.
SPEC_MUTANTS = {
    "interface_spec_added_req.md": "requirement TMR-RESTART is not in the plan",
    "interface_spec_removed_req.md": "TMR-STOP",
    "interface_spec_range_changed.md": "TMR-PARAM does not quote interface_spec.md",
    "interface_spec_id_renamed.md": "TMR-EXPIRE-WINS",
    "interface_spec_id_duplicated.md": "TMR-EXPIRE is tagged more than once",
    "interface_spec_irq_mode_changed.md": "TMR-IRQ does not quote interface_spec.md",
}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _control(case):
    [control] = [c for c in case.held_out if c.scorer == "must-fail"]
    return control


# --- Planning, packets and the files -------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                 fixed_clock):
    case = _case(case_id)
    seat, skills, owner, reviewer = CASES[case_id]
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == seat and set(case.skills) == set(skills)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "block_verification"
    [task] = [t for t in engine.state.tasks.values() if t.stage == seat]
    assert task.workflow == "block-verification" and set(skills) <= set(task.skills)
    if owner:
        assert (task.owner, task.reviewer) == (owner, reviewer)
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, (case_id, role)
        assert packet.domain.declines is None
    stages = {engine.task(d).stage for d in task.depends_on}
    # The coverage seat is seated on the RTL and the testbench; the specification is handed to it as well.
    assert set(case.upstream) - {"interface-spec"} <= stages if case_id == COV else set(case.upstream) <= stages


def test_the_mutants_and_weak_testbenches_in_the_folders_are_the_ones_listed():
    cov, plan = _control(_case(COV)), _control(_case(PLAN))
    rtl = {Path(m).name for ms in cov.mutants.values() for m in ms}
    spec = {Path(m).name for ms in plan.mutants.values() for m in ms}
    assert rtl == set(RTL_MUTANTS) and spec == set(SPEC_MUTANTS)
    assert [Path(m).name for m in next(iter(cov.mutants.values()))] == list(RTL_MUTANTS)
    assert {f.name for f in (FIXTURE / "mutants").iterdir()} == rtl | spec
    assert {f.name for f in (FIXTURE / "coverage").glob("*.sv")} == set(WEAK)
    # The testbench the seat is handed is the idle one: it is the weakest, and the seat extends it.
    assert [f.path for f in _case(COV).upstream["testbench"]] == [f"{TT}/coverage/tick_timer_idle_tb.sv"]


def test_the_case_bounds_are_the_coverage_gates_bounds():
    assert tuple(Bound.parse(t) for t in _control(_case(COV)).cover_bounds) == COVERAGE_TARGETS


def test_the_coverage_gate_carries_the_bounds_the_scorer_applies(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case(COV).request)
    [task] = [t for t in engine.state.tasks.values() if t.stage == "coverage"]
    (gate,) = [r for r in task.evidence_requirements if r.before_review]
    assert gate.tools == ("coverage.read",) and gate.bounds == COVERAGE_TARGETS


def test_the_reference_plan_and_the_specification_agree_on_the_tagged_requirements():
    import re

    tagged = re.findall(r"\[req:([A-Z0-9-]+)\]", (FIXTURE / "interface_spec.md").read_text(encoding="utf-8"))
    plan = json.loads((FIXTURE / "tick_timer_vplan.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in plan["requirements"]] == tagged and len(tagged) == len(set(tagged)) == 15
    assert {p for i in plan["items"] for p in i["proves"]} == set(tagged)


# --- The coverage case: the reference, for real -----------------------------------------------------------


@needs(*GATE_TOOLS, *COVERAGE_TOOLS)
def test_the_reference_meets_the_bounds_passes_the_rtl_and_fails_every_mutant(nirmaan_org, fixed_clock, tmp_path):
    case = _case(COV)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert "4 of 4 mutants failed it" in score.summary and "every cover reached" in score.summary, score.summary
    runs = {j.run: j for j in trial.judge_runs}
    clean, cover = score.runs
    assert runs[clean].tool == runs[cover].tool == "coverage.read"
    assert runs[cover].succeeded and "limit not met" not in runs[cover].summary, runs[cover].summary
    assert len(score.failed_runs) == len(RTL_MUTANTS)
    for run in score.failed_runs:  # a mutant fails a check of the testbench, so its coverage is never read
        assert "coverage not read: simulation failed" in runs[run].summary, runs[run].summary


def _judge(nirmaan_org, fixed_clock, tmp_path, tb: Path):
    """The case's check, run by the scorer on a testbench that never went through the coverage gate.

    The gate refuses a testbench that misses the bounds before review, so a weak one never reaches the scorer in a
    full run; here the scorer gets a stand-in for the seat's task, with the coverage seat's own tool authority.
    """
    case = _case(COV)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    [seat] = [t for t in engine.state.tasks.values() if t.stage == "coverage"]
    tools = ToolHandle(ToolBroker(engine), Actor(role=str(seat.owner), kind=ActorKind.SYSTEM, name="scorer"), seat.id)
    state = SimpleNamespace(artifacts={"a": SimpleNamespace(kind="testbench", location=str(tb))}, tool_runs={})
    check = _control(case).model_copy(update={"seat_entries": {}, "params": {"top": tb.stem}})
    ctx = ScoreContext(SimpleNamespace(state=state), SimpleNamespace(id=seat.id, artifacts=["a"]), check, REPO, tools,
                       tmp_path / "check-1")
    return scorer_spec("must-fail").fn(ctx)


@needs(*COVERAGE_TOOLS)
@pytest.mark.parametrize("name", sorted(WEAK))
def test_a_weak_testbench_passes_its_checks_and_the_rtl_but_fails_the_bounds(nirmaan_org, fixed_clock, tmp_path,
                                                                             name):
    score = _judge(nirmaan_org, fixed_clock, tmp_path, FIXTURE / "coverage" / name)
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith("covers not reached on the clean inputs: coverage.read run-"), score.summary
    assert "limit not met" in score.summary and "is below min_" in score.summary, score.summary
    assert len(score.runs) == 2 and score.failed_runs == ()  # the clean run passed its own checks; no mutant ran


@needs(*COVERAGE_TOOLS)
def test_the_full_testbench_meets_the_bounds_and_fails_each_mutant(nirmaan_org, fixed_clock, tmp_path):
    score = _judge(nirmaan_org, fixed_clock, tmp_path, FIXTURE / "tick_timer_tb.sv")
    assert score.status is ScoreStatus.PASSED, score.summary
    assert "every cover reached" in score.summary and "4 of 4 mutants failed it" in score.summary


def _blind_to_the_periodic_mask(tmp_path: Path) -> Path:
    """The reference testbench with every check of the masked interrupt in periodic mode taken out.

    It keeps all the stimulus, so it runs every line the reference runs and meets the same bounds. It still checks
    the masked interrupt in one-shot mode, and everything else; only a block wrong in periodic mode, with the
    interrupt enable clear, is not seen.
    """
    text = (FIXTURE / "tick_timer_tb.sv").read_text(encoding="utf-8")
    marker = '        check("periodic, IE clear: irq masked", {31\'d0, irq}, 32\'d0);  // MASKED-PERIODIC-CHECK\n'
    state_check = '        check({what, ": irq"}, {31\'d0, irq}, {31\'d0, irq_v});\n'
    assert text.count(marker) == 1 and text.count(state_check) == 1
    # CTRL 3'b011 is periodic with IE clear: no state line of the testbench checks the interrupt there.
    text = text.replace(marker, "").replace(state_check, "        if (ctrl != 3'b011) check({what, \": irq\"}, {31'd0, irq}, {31'd0, irq_v});\n")
    text = text.replace("module tick_timer_tb;", "module tick_timer_blind_tb;").replace('"tick_timer_tb: PASS', '"tick_timer_blind_tb: PASS')
    tb = tmp_path / "tick_timer_blind_tb.sv"
    tb.write_text(text, encoding="utf-8")
    return tb


@needs(*COVERAGE_TOOLS)
def test_a_testbench_blind_to_the_periodic_mask_meets_the_bounds_and_survives_only_the_mode_qualified_mutant(
        nirmaan_org, fixed_clock, tmp_path):
    """The must-fail answer to the surviving mutant of dv/coverage-irq-ctrl: coverage reached, the mask unchecked."""
    score = _judge(nirmaan_org, fixed_clock, tmp_path, _blind_to_the_periodic_mask(tmp_path))
    assert score.status is ScoreStatus.FAILED
    survivor = f"{TT}/mutants/tick_timer_irq_ie_ignored_periodic.v"
    assert score.summary.startswith(f"mutant {survivor} survived: coverage.read"), score.summary
    # Every earlier mutant failed on a check, and the clean run and the cover run both passed the bounds; the
    # survivor's own run is listed after them (M6).
    assert len(score.runs) == 3 and len(score.failed_runs) == len(RTL_MUTANTS) - 1


@needs(*GATE_TOOLS, *COVERAGE_TOOLS)
def test_the_coverage_gate_refuses_the_idle_testbench_before_review(nirmaan_org, fixed_clock, tmp_path):
    case = _case(COV)
    idle = FIXTURE / "coverage" / "tick_timer_idle_tb.sv"
    llm = ReplayLLM([(idle.name, "testbench", idle.read_text(encoding="utf-8"), idle.stem),
                     ("tick_timer_coverage_report.md", "coverage_report", "# Coverage report\n", None)])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted and "limit not met" in result.detail, result.detail


# --- The verification plan case -------------------------------------------------------------------------------


def test_the_reference_plan_passes_and_fails_every_specification_mutant(nirmaan_org, fixed_clock, tmp_path):
    case = _case(PLAN)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, (trial.result.detail, [(j.run, j.summary) for j in trial.judge_runs],
                                 [x.summary for x in trial.result.scores])
    [score] = trial.result.scores
    runs = {j.run: j for j in trial.judge_runs}
    summaries = [runs[r].summary for r in score.failed_runs]
    assert len(summaries) == len(SPEC_MUTANTS)
    for summary, problem in zip(summaries, SPEC_MUTANTS.values()):
        assert problem in summary, summary


def test_a_plan_missing_a_requirement_is_refused_before_review(nirmaan_org, fixed_clock, tmp_path):
    """The dv-plan gate: a plan that drops the same-edge race never reaches review, so it is never judged."""
    case = _case(PLAN)
    plan = json.loads((FIXTURE / "tick_timer_vplan.json").read_text(encoding="utf-8"))
    plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "TMR-SET-WINS"]
    for item in plan["items"]:
        item["proves"] = [p for p in item["proves"] if p != "TMR-SET-WINS"]
    plan["items"] = [i for i in plan["items"] if i["proves"]]
    llm = ReplayLLM([("tick_timer_vplan.json", "verification_plan", json.dumps(plan, indent=2) + "\n", None)])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted and not result.passed
    assert "TMR-SET-WINS is not in the plan" in result.detail, result.detail
