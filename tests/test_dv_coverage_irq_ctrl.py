"""The coverage verification eval case, and cover bounds on the must-fail scorer (wave 2, W2-E5).

``dv/coverage-irq-ctrl`` judges the coverage seat of M68's block-verification workflow (``code_coverage``) on
the interrupt controller of ``dv/directed-irq-ctrl``. The seat is handed an approved testbench that only resets
the block; its own must reach the M70 bounds (``COVERAGE_TARGETS``) on the approved RTL and still fail RTL
mutants. The scorer's ``cover_bounds`` apply those bounds to the ``cover_tool`` run, so a coverage case is judged
on line and toggle coverage the way the seat's own gate is. Real-tool tests need Verilator and its coverage tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS

from nirmaan.company.workflows import COVERAGE_TARGETS
from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.models import HeldOutCheck, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
IRQ = REPO / "tests" / "fixtures" / "dv" / "irq_ctrl"
CASE = "dv/coverage-irq-ctrl"
COVERAGE_TOOLS = ("verilator", "verilator_coverage")
#: The weak testbenches: each passes its own checks on the approved RTL and misses the bounds, and why.
WEAK = {
    "irq_ctrl_idle_tb.sv": "never raises a source",
    "irq_ctrl_no_ack_tb.sv": "never acknowledges or clears",
    "irq_ctrl_no_mask_tb.sv": "never masks, never writes MODE",
}
MUTANTS = ("irq_ctrl_priority_inverted.v", "irq_ctrl_ack_ignored.v", "irq_ctrl_level_mask_ignored.v")


def _case():
    return next(c for c in load_cases(EVALS) if c.id == CASE)


def _check():
    [check] = _case().held_out
    return check


# --- The scorer's cover bounds (no tool needed) ----------------------------------------------------------


def test_a_check_without_cover_bounds_dumps_as_it_always_did():
    """No case digest changes: the new field is left out of a dump while it is empty."""
    plain = HeldOutCheck(name="n", scorer="must-fail", tool="simulator.run", cover_tool="formal.cover")
    assert "cover_bounds" not in plain.model_dump() and "cover_bounds" not in plain.model_dump(mode="json")
    bounded = HeldOutCheck(name="n", scorer="must-fail", cover_bounds=("line>=90",))
    assert bounded.model_dump(mode="json")["cover_bounds"] == ["line>=90"]
    assert HeldOutCheck.model_validate(bounded.model_dump(mode="json")) == bounded


def test_a_cover_bound_must_read_as_a_bound():
    with pytest.raises(ValueError, match="needs a number|reads metric"):
        HeldOutCheck(name="n", cover_bounds=("line>=lots",))
    with pytest.raises(ValueError, match="reads metric"):
        HeldOutCheck(name="n", cover_bounds=("line",))


def test_the_case_bounds_are_the_coverage_gates_bounds():
    from nirmaan.models.workflow import Bound

    assert tuple(Bound.parse(t) for t in _check().cover_bounds) == COVERAGE_TARGETS


def test_no_other_shipped_case_has_cover_bounds():
    assert [c.id for c in load_cases(EVALS) if any(h.cover_bounds for h in c.held_out)] == [CASE]


# --- Planning, packets and the files ------------------------------------------------------------------------


def test_the_case_plans_block_verification_and_its_seat_carries_the_judged_skills(nirmaan_org, fixed_clock):
    case = _case()
    assert validate_case(nirmaan_org, case, REPO) == []
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "block_verification"
    [task] = [t for t in engine.state.tasks.values() if t.stage == "coverage"]
    assert task.workflow == "block-verification" and "code_coverage" in task.skills
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, role
    assert {engine.task(d).stage for d in task.depends_on} == {"design-under-test", "testbench"}
    # Its gate carries the same bounds the scorer applies.
    (gate,) = [r for r in task.evidence_requirements if r.before_review]
    assert gate.tools == ("coverage.read",) and gate.bounds == COVERAGE_TARGETS


def test_the_mutants_and_weak_testbenches_are_the_ones_listed():
    check = _check()
    assert {Path(m).name for ms in check.mutants.values() for m in ms} == set(MUTANTS)
    assert {f.name for f in (IRQ / "coverage").glob("*.sv")} == set(WEAK)
    assert {f.name for f in (IRQ / "mutants").iterdir()}.issuperset(MUTANTS)
    # The testbench the seat is handed is the idle one: it is the weakest, and the seat extends it.
    assert [f.path for f in _case().upstream["testbench"]] == ["tests/fixtures/dv/irq_ctrl/coverage/irq_ctrl_idle_tb.sv"]


# --- The reference answer, for real -------------------------------------------------------------------------


@needs(*GATE_TOOLS, *COVERAGE_TOOLS)
def test_the_reference_meets_the_bounds_passes_the_rtl_and_fails_every_mutant(nirmaan_org, fixed_clock, tmp_path):
    case = _case()
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert "3 of 3 mutants failed it" in score.summary and "every cover reached" in score.summary, score.summary
    runs = {j.run: j for j in trial.judge_runs}
    clean, cover = score.runs
    assert runs[clean].tool == runs[cover].tool == "coverage.read"
    assert runs[cover].succeeded and "line 100.00%" in runs[cover].summary, runs[cover].summary
    assert len(score.failed_runs) == len(MUTANTS)
    for run in score.failed_runs:  # a mutant fails a check of the testbench, so its coverage is never read
        assert "coverage not read: simulation failed" in runs[run].summary, runs[run].summary


# --- A weak testbench passes its own checks and fails the bounds ----------------------------------------------


def _judge(nirmaan_org, fixed_clock, tmp_path, tb: Path, bounds: bool = True):
    """The case's check, run by the scorer on a testbench that never went through the coverage gate.

    The gate refuses a testbench that misses the bounds before review, so a weak one never reaches the scorer in a
    full run; here the scorer gets a stand-in for the seat's task, with the coverage seat's own tool authority.
    """
    from types import SimpleNamespace

    from nirmaan.evals.scorers import ScoreContext, scorer_spec
    from nirmaan.models import Actor, ActorKind
    from nirmaan.runtime import ToolBroker, ToolHandle

    case = _case()
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    [seat] = [t for t in engine.state.tasks.values() if t.stage == "coverage"]
    tools = ToolHandle(ToolBroker(engine), Actor(role=str(seat.owner), kind=ActorKind.SYSTEM, name="scorer"), seat.id)
    state = SimpleNamespace(artifacts={"a": SimpleNamespace(kind="testbench", location=str(tb))}, tool_runs={})
    check = _check().model_copy(update={"seat_entries": {}, "params": {"top": tb.stem},
                                        **({} if bounds else {"cover_bounds": ()})})
    ctx = ScoreContext(SimpleNamespace(state=state), SimpleNamespace(id=seat.id, artifacts=["a"]), check, REPO, tools,
                       tmp_path / "check-1")
    return scorer_spec("must-fail").fn(ctx)


@needs(*COVERAGE_TOOLS)
@pytest.mark.parametrize("name", sorted(WEAK))
def test_a_weak_testbench_passes_its_checks_and_the_rtl_but_fails_the_bounds(nirmaan_org, fixed_clock, tmp_path,
                                                                             name):
    score = _judge(nirmaan_org, fixed_clock, tmp_path, IRQ / "coverage" / name)
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith("covers not reached on the clean inputs: coverage.read run-"), score.summary
    assert "limit not met" in score.summary and "is below min_" in score.summary, score.summary
    assert len(score.runs) == 2 and score.failed_runs == ()  # the clean run passed its own checks; no mutant ran


@needs(*COVERAGE_TOOLS)
def test_without_cover_bounds_the_same_testbench_meets_the_cover_run_and_fails_on_a_mutant(nirmaan_org, fixed_clock,
                                                                                         tmp_path):
    """The scorer as it was: a cover tool with no bounds only has to run and pass."""
    score = _judge(nirmaan_org, fixed_clock, tmp_path, IRQ / "coverage" / "irq_ctrl_idle_tb.sv", bounds=False)
    assert score.status is ScoreStatus.FAILED and "survived: coverage.read" in score.summary, score.summary


@needs(*COVERAGE_TOOLS)
def test_the_full_testbench_meets_the_bounds_and_fails_each_mutant(nirmaan_org, fixed_clock, tmp_path):
    score = _judge(nirmaan_org, fixed_clock, tmp_path, IRQ / "irq_ctrl_tb.sv")
    assert score.status is ScoreStatus.PASSED, score.summary
    assert "every cover reached" in score.summary and "3 of 3 mutants failed it" in score.summary


@needs(*GATE_TOOLS, *COVERAGE_TOOLS)
def test_the_coverage_gate_refuses_the_idle_testbench_before_review(nirmaan_org, fixed_clock, tmp_path):
    case = _case()
    idle = IRQ / "coverage" / "irq_ctrl_idle_tb.sv"
    llm = ReplayLLM([(idle.name, "testbench", idle.read_text(encoding="utf-8"), idle.stem),
                     ("irq_ctrl_coverage_report.md", "coverage_report", "# Coverage report\n", None)])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted and "limit not met" in result.detail, result.detail
