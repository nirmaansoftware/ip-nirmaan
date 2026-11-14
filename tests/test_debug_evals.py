"""The two debug eval cases (wave 2, W2-E4).

Two cases judge the seats of the regression investigation that asks for a
reproduction (M71, ``docs/REPRO_GATES.md``), each on RTL under investigation
of its own:

* ``debug/root-cause-uart-tx`` (``tests/fixtures/dv/uart_tx/``) judges the
  root-cause seat on ``root_cause_analysis``: a UART transmitter that latches
  ``data`` on every start pulse, even while a frame is in flight. The seat's
  repro must fail the RTL under investigation under ``simulator.run`` with
  ``expect=fail`` (its gate before review), pass the fixed RTL, and fail a
  second implementation with the same defect, and pass that implementation
  fixed.
* ``debug/triage-three-bugs`` (``tests/fixtures/dv/uart_frame_tx/``) judges the
  triage seat on ``failure_triage``: a UART transmitter with parity and three
  independent defects, one repro testbench per bucket, judged by
  ``must-fail-each``.

Each request plans a regression investigation with the reproduction feature,
and each seat's packet carries the skill the case judges. Real-tool tests need
the simulators (``laws.needs``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS

from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.models import ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
UART = "tests/fixtures/dv/uart_tx"
FRAME = "tests/fixtures/dv/uart_frame_tx"

#: Each case: seat, the seat task's skills, owner and reviewer (docs/REPRO_GATES.md, "Who gets each task").
CASES = {
    "debug/root-cause-uart-tx": ("root-cause", ("root_cause_analysis",),
                                 "verification.debug.analysis.root_cause.senior",
                                 "verification.debug.analysis.tech_lead"),
    "debug/triage-three-bugs": ("triage", ("failure_triage",), "verification.debug.triage.engineer", None),
}
RTL_SEEDED = {
    "debug/root-cause-uart-tx": {"uart_tx_reload_while_busy.v": "data is latched on a start pulse while busy",
                                 "uart_tx_alt_reload.v": "the same defect in a shift-register implementation"},
    "debug/triage-three-bugs": {"uart_frame_tx_msb_first.v": "data bits go out most significant bit first",
                                "uart_frame_tx_odd_parity.v": "the parity bit has odd polarity",
                                "uart_frame_tx_short_stop.v": "the stop bit lasts half a bit period"},
}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def _plan(nirmaan_org, fixed_clock, case_id):
    case = _case(case_id)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    [task] = [t for t in engine.state.tasks.values() if t.stage == case.seat]
    return case, engine, task


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_request_plans_a_reproduction_and_its_seat_carries_the_judged_skill(case_id, nirmaan_org, fixed_clock):
    seat, skills, owner, reviewer = CASES[case_id]
    case, engine, task = _plan(nirmaan_org, fixed_clock, case_id)
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == seat and set(case.skills) == set(skills)
    assert engine.state.project.workflows == ("regression-investigation",)
    assert "reproduction" in engine.state.project.analysis.features
    assert (task.skills, task.owner, task.reviewer) == (skills, owner, reviewer)
    assert "simulator.run" in nirmaan_org.tools_of(owner)
    [gate] = [r for r in task.evidence_requirements if r.before_review]
    assert gate.tools == ("simulator.run",) and gate.params == (("expect", "fail"),)
    for role in (r for r in (task.owner, task.reviewer) if r):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, (case_id, role)
        assert packet.domain.declines is None
    # The RTL under investigation is a planned stage the case fixes from its own file, and the seat builds on it.
    assert set(case.upstream) <= {t.stage for t in engine.state.tasks.values()}
    assert "design-under-investigation" in {engine.task(d).stage for d in task.depends_on}


def test_the_root_cause_seat_is_a_decision_and_the_triage_seat_gets_every_log(nirmaan_org):
    root, triage = _case("debug/root-cause-uart-tx"), _case("debug/triage-three-bugs")
    assert root.outcome == "rtl_bug" and triage.outcome is None
    assert root.inputs == {"triage": {"paths": (f"{UART}/logs/regression_fail.log",)}}
    assert triage.inputs == {"triage": {"paths": (f"{FRAME}/logs/data_byte_fail.log",
                                                  f"{FRAME}/logs/parity_bit_fail.log",
                                                  f"{FRAME}/logs/frame_period_fail.log")}}


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_seeded_file_in_the_folder_is_listed_by_its_case(case_id):
    seeded = list(RTL_SEEDED[case_id])
    listed = [Path(m).name for check in _case(case_id).held_out for muts in check.mutants.values() for m in muts]
    assert set(listed) == set(seeded)
    folder = UART if case_id == "debug/root-cause-uart-tx" else FRAME
    assert {f.name for f in (REPO / folder / "mutants").iterdir()} == set(seeded)


def test_the_root_cause_case_has_two_controls_on_two_implementations():
    case = _case("debug/root-cause-uart-tx")
    assert [list(c.case_files["sources"]) for c in case.held_out] == [[f"{UART}/uart_tx.v"],
                                                                      [f"{UART}/alt/uart_tx.v"]]
    assert all(c.scorer == "must-fail" for c in case.held_out)
    assert _case("debug/triage-three-bugs").held_out[0].scorer == "must-fail-each"


def test_the_failing_logs_are_what_the_buggy_rtl_printed():
    """Each log is a real run: one ERROR line naming the failure, and the finish."""
    assert "received 0xb2, expected 0x3c" in _text(f"{UART}/logs/regression_fail.log")
    for name, text in (("data_byte", "received 0xd2, expected 0x4b"), ("parity_bit", "parity bit are odd"),
                       ("frame_period", "busy for 42 clocks, expected 44")):
        log = _text(f"{FRAME}/logs/{name}_fail.log")
        assert text in log and log.count("ERROR:") == 1, name


# --- The reference answers, run for real ------------------------------------------------------------


def _trial(nirmaan_org, fixed_clock, tmp_path, case_id):
    case = _case(case_id)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    return trial


@needs(*GATE_TOOLS)
def test_the_reference_repro_reproduces_on_the_rtl_and_fails_both_defective_implementations(nirmaan_org, fixed_clock,
                                                                                         tmp_path):
    trial = _trial(nirmaan_org, fixed_clock, tmp_path, "debug/root-cause-uart-tx")
    [gate] = [g for g in trial.result.gate_runs if g.tool == "simulator.run"]
    assert gate.succeeded and "failure reproduced" in gate.summary, gate.summary
    assert [s.status for s in trial.result.scores] == [ScoreStatus.PASSED] * 2
    for score in trial.result.scores:
        assert len(score.failed_runs) == 2  # both defective implementations, on a failed check
    for run in trial.judge_runs:
        if run.tool == "simulator.run" and "failed" in run.summary:
            assert "checks failed" in run.summary or "1 check failed" in run.summary, run.summary


@needs(*GATE_TOOLS)
def test_the_reference_triage_repros_each_reproduce_and_each_seeded_defect_fails_one_of_its_own(nirmaan_org,
                                                                                               fixed_clock,
                                                                                               tmp_path):
    trial = _trial(nirmaan_org, fixed_clock, tmp_path, "debug/triage-three-bugs")
    repro = [g for g in trial.result.gate_runs if "failure reproduced" in g.summary]
    assert len(repro) == 3 and all(g.succeeded for g in repro), repro
    [score] = trial.result.scores
    assert score.status is ScoreStatus.PASSED and "each of 3 mutants fails a file of its own" in score.summary


# --- Weak answers the controls fail -----------------------------------------------------------------




def _reference(case_id, *, drop=(), replace=None):
    """The case's reference answer as replay tuples, minus the files named by `drop`."""
    out = []
    for f in _case(case_id).reference:
        name = Path(f.path).name
        if name in drop:
            continue
        text = replace[name] if replace and name in replace else _text(f.path)
        out.append((name, f.kind, text, f.entry))
    return out


def _run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM(files, outcome=case.outcome)
    return run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                    sandbox=tmp_path / "sandbox", clock=fixed_clock)


@needs(*GATE_TOOLS)
def test_a_repro_whose_second_start_carries_the_same_byte_passes_the_rtl_and_never_reaches_review(
        nirmaan_org, fixed_clock, tmp_path):
    """The defect is visible only when the pulse while busy carries another byte."""
    repro = _text(f"{UART}/uart_tx_repro.v")
    weak = repro.replace("start = 1'b1; data = 8'hB2;", "start = 1'b1; data = 8'h3C;")
    assert weak != repro
    files = _reference("debug/root-cause-uart-tx", replace={"uart_tx_repro.v": weak})
    result = _run(nirmaan_org, fixed_clock, tmp_path, "debug/root-cause-uart-tx", files)
    assert not result.submitted, result
    assert "failure not reproduced" in result.detail, result.detail


@needs(*GATE_TOOLS)
def test_a_repro_that_fails_for_the_wrong_reason_fails_the_clean_run_of_the_control(nirmaan_org, fixed_clock,
                                                                                  tmp_path):
    """It fails the RTL under investigation (so the gate passes it), but it expects the wrong byte on every RTL."""
    repro = _text(f"{UART}/uart_tx_repro.v")
    weak = repro.replace("got !== 8'h3C", "got !== 8'h3D")
    assert weak != repro
    files = _reference("debug/root-cause-uart-tx", replace={"uart_tx_repro.v": weak})
    result = _run(nirmaan_org, fixed_clock, tmp_path, "debug/root-cause-uart-tx", files)
    assert result.submitted, result.detail
    assert [s.status for s in result.scores][0] is ScoreStatus.FAILED and not result.passed
    assert "the clean inputs do not pass" in result.scores[0].summary, result.scores[0].summary


@needs(*GATE_TOOLS)
def test_a_triage_with_a_repro_for_two_of_three_bugs_fails_the_third(nirmaan_org, fixed_clock, tmp_path):
    files = _reference("debug/triage-three-bugs", drop=("uart_frame_tx_repro_frame_period.v",))
    result = _run(nirmaan_org, fixed_clock, tmp_path, "debug/triage-three-bugs", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and "only 2 of 3 mutants have a file of their own" in score.summary


@needs(*GATE_TOOLS)
def test_one_repro_that_checks_the_whole_frame_cannot_stand_for_three_buckets(nirmaan_org, fixed_clock, tmp_path):
    """A single repro fails all three seeded bugs, so only one mutant has a file of its own."""
    drop = ("uart_frame_tx_repro_parity.v", "uart_frame_tx_repro_frame_period.v")
    data_order = _text(f"{FRAME}/uart_frame_tx_repro_data_order.v")
    whole = (data_order
             .replace("    integer    k;\n", "    integer    k;\n    integer    total = 0;\n"
                      "    always @(posedge clk) if (busy) total <= total + 1;\n")
             .replace("        repeat (6 * CLKS) @(posedge clk);",
                      "        repeat (CLKS) @(posedge clk);\n"
                      "        verdict_check(tx === 1'b1, \"parity bit of 0x4B is not 1\");\n"
                      "        repeat (6 * CLKS) @(posedge clk);\n"
                      "        verdict_check(total === 11 * CLKS, \"frame period is not 11 bit periods\");"))
    assert whole != data_order
    files = _reference("debug/triage-three-bugs", drop=drop, replace={"uart_frame_tx_repro_data_order.v": whole})
    result = _run(nirmaan_org, fixed_clock, tmp_path, "debug/triage-three-bugs", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED, score
