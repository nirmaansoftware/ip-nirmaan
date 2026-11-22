"""The second root-cause case and the second triage case (RX-E3).

Same seats and gates as ``tests/test_debug_evals.py`` (``docs/REPRO_GATES.md``), each on RTL under investigation of
its own:

* ``debug/root-cause-debounce`` (``tests/fixtures/dv/debounce/``) judges the root-cause seat on ``root_cause_analysis``:
  the failing log's first ERROR is a symptom, and a line that looks right (a high bounce filtered) is evidence
  against a counter that is broken in general. Two controls, on two implementations. The seat's task carries only
  ``root_cause_analysis`` (the workflow gives the root-cause stage no ``log_analysis``), so the case names that
  skill alone.
* ``debug/triage-pwm-gen`` (``tests/fixtures/dv/pwm_gen/``) judges the triage seat on ``failure_triage``: a
  pulse-width modulator with three independent defects, one repro per bucket, judged by ``must-fail-each``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS

from nirmaan.evals import ReplayLLM, evaluate, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.integrations.eda import NONCE_ARG
from nirmaan.models import ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
DEB = "tests/fixtures/dv/debounce"
PWM = "tests/fixtures/dv/pwm_gen"
ROOT, TRIAGE = "debug/root-cause-debounce", "debug/triage-pwm-gen"

CASES = {
    ROOT: ("root-cause", {"root_cause_analysis"}, "verification.debug.analysis.root_cause.senior",
           "verification.debug.analysis.tech_lead"),
    TRIAGE: ("triage", {"failure_triage"}, "verification.debug.triage.engineer", None),
}
SEEDED = {
    ROOT: {"debounce_rise_only_restart.v", "debounce_alt_clear_on_low.v"},
    TRIAGE: {"pwm_gen_wide_pulse.v", "pwm_gen_short_period.v", "pwm_gen_live_duty.v"},
}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_request_plans_a_reproduction_and_its_seat_carries_the_judged_skill(case_id, nirmaan_org, fixed_clock):
    seat, skills, owner, reviewer = CASES[case_id]
    case = _case(case_id)
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == seat and set(case.skills) == skills
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    [task] = [t for t in engine.state.tasks.values() if t.stage == case.seat]
    assert (task.owner, task.reviewer) == (owner, reviewer)
    for role in (r for r in (task.owner, task.reviewer) if r):
        packet = assemble(engine, task.id, role=role)
        assert skills <= {s.id for s in packet.domain.skills}, (case_id, role)
    assert set(case.upstream) <= {t.stage for t in engine.state.tasks.values()}


def test_the_root_cause_case_names_log_analysis_and_a_decision():
    case = _case(ROOT)
    assert case.outcome == "rtl_bug" and case.skills == ("root_cause_analysis",)
    assert case.inputs == {"triage": {"paths": (f"{DEB}/logs/regression_fail.log",)}}
    assert [list(c.case_files["sources"]) for c in case.held_out] == [[f"{DEB}/debounce.v"], [f"{DEB}/alt/debounce.v"]]
    assert all(c.scorer == "must-fail" for c in case.held_out)
    triage = _case(TRIAGE)
    assert triage.outcome is None and triage.held_out[0].scorer == "must-fail-each"
    assert triage.inputs == {"triage": {"paths": tuple(f"{PWM}/logs/{n}_fail.log"
                                                       for n in ("pulse_width", "period", "duty_update"))}}


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_seeded_file_in_the_folder_is_listed_by_its_case(case_id):
    listed = [Path(m).name for check in _case(case_id).held_out for muts in check.mutants.values() for m in muts]
    assert set(listed) == SEEDED[case_id]
    folder = DEB if case_id == ROOT else PWM
    assert {f.name for f in (REPO / folder / "mutants").iterdir()} == SEEDED[case_id]


def test_the_debounce_log_has_a_symptom_first_and_a_correct_line_that_rules_out_a_general_fault():
    log = _text(f"{DEB}/logs/regression_fail.log")
    lines = log.splitlines()
    first_error = next(i for i, line in enumerate(lines) if line.startswith("ERROR:"))
    high_bounce = next(i for i, line in enumerate(lines) if "high bounce of 3 cycles done, clean=0" in line)
    assert high_bounce < first_error  # the filtered high pulse is logged before the first ERROR
    assert log.count("ERROR:") == 3 and "differed for only 2 cycles" in lines[first_error]


def test_each_pwm_log_names_one_failure():
    for name, text in (("pulse_width", "pulse of 4 clocks, expected 3"), ("period", "7 clocks apart, expected 8"),
                       ("duty_update", "pwm high for 2 clocks before the next period")):
        log = _text(f"{PWM}/logs/{name}_fail.log")
        assert text in log and log.count("ERROR:") == 1, name


def _simulate(tmp_path, sources, *args):
    """Run the sources (paths from the repository root) from their folder, so a log names a file by its bare name."""
    folder = (REPO / sources[-1]).parent
    out = tmp_path / "sim.vvp"
    names = [str((REPO / s).relative_to(folder)) for s in sources]
    subprocess.run(["iverilog", "-g2012", "-o", str(out), *names], check=True, capture_output=True, cwd=folder)
    return subprocess.run(["vvp", str(out), *args], check=True, capture_output=True, text=True, cwd=folder).stdout


@needs(*GATE_TOOLS)
def test_each_failing_log_is_what_the_regression_test_prints_on_the_buggy_rtl(tmp_path):
    assert _simulate(tmp_path, [f"{DEB}/mutants/debounce_rise_only_restart.v", f"{DEB}/debounce_regress_tb.v"]) \
        == _text(f"{DEB}/logs/regression_fail.log")
    for name in ("pulse_width", "period", "duty_update"):
        out = _simulate(tmp_path, [f"{PWM}/pwm_gen_buggy.v", f"{PWM}/pwm_gen_regress_tb.v"], f"+test={name}")
        assert out == _text(f"{PWM}/logs/{name}_fail.log"), name


@needs(*GATE_TOOLS)
def test_the_pwm_regression_tests_each_fail_one_seeded_defect_only(tmp_path):
    """The buggy RTL is the three seeded defects together; each regression test fails on its own defect alone."""
    own = {"pulse_width": "wide_pulse", "period": "short_period", "duty_update": "live_duty"}
    for test, mutant in own.items():
        for other in own.values():
            out = _simulate(tmp_path, [f"{PWM}/mutants/pwm_gen_{other}.v", f"{PWM}/pwm_gen_regress_tb.v"],
                            f"+test={test}")
            assert ("ERROR:" in out) is (other == mutant), (test, other)
        assert "ERROR:" not in _simulate(tmp_path, [f"{PWM}/pwm_gen.v", f"{PWM}/pwm_gen_regress_tb.v"], f"+test={test}")


@needs(*GATE_TOOLS)
def test_the_triage_repro_given_to_the_root_cause_seat_is_tied_to_one_implementation(tmp_path):
    """It probes the count register: it reproduces on the RTL under investigation and passes the fixed one, and it
    does not build on the second implementation, so handing it over does not hand over the held-out answer."""
    repro = f"{DEB}/debounce_triage_repro.v"
    assert "1 failed" in _simulate(tmp_path, [f"{DEB}/mutants/debounce_rise_only_restart.v", repro])
    assert "0 failed" in _simulate(tmp_path, [f"{DEB}/debounce.v", repro])
    with pytest.raises(subprocess.CalledProcessError):
        _simulate(tmp_path, [f"{DEB}/alt/debounce.v", repro])


def _trial(nirmaan_org, fixed_clock, tmp_path, case_id):
    case = _case(case_id)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    return trial


@needs(*GATE_TOOLS)
def test_the_reference_repro_reproduces_and_fails_both_defective_debounce_implementations(nirmaan_org, fixed_clock,
                                                                                         tmp_path):
    trial = _trial(nirmaan_org, fixed_clock, tmp_path, ROOT)
    [gate] = [g for g in trial.result.gate_runs if g.tool == "simulator.run"]
    assert gate.succeeded and "failure reproduced" in gate.summary, gate.summary
    assert [s.status for s in trial.result.scores] == [ScoreStatus.PASSED] * 2
    assert all(len(s.failed_runs) == 2 for s in trial.result.scores)


@needs(*GATE_TOOLS)
def test_the_reference_pwm_repros_each_reproduce_and_each_seeded_defect_fails_one_of_its_own(nirmaan_org, fixed_clock,
                                                                                            tmp_path):
    trial = _trial(nirmaan_org, fixed_clock, tmp_path, TRIAGE)
    repro = [g for g in trial.result.gate_runs if "failure reproduced" in g.summary]
    assert len(repro) == 3 and all(g.succeeded for g in repro), repro
    [score] = trial.result.scores
    assert score.status is ScoreStatus.PASSED and "each of 3 mutants fails a file of its own" in score.summary


@needs(*GATE_TOOLS)
@pytest.mark.parametrize("case_id", sorted(CASES))
@pytest.mark.parametrize("knowledge", (True, False), ids=("documents-on", "documents-off"))
def test_each_seat_is_told_the_plusarg_and_the_verdict_line_its_repro_gate_reads(case_id, knowledge, nirmaan_org,
                                                                                 fixed_clock, tmp_path):
    """The triage card names the contract (the failure_triage card, ip#438). The root-cause card does not yet, so for
    that seat only the case's own constraint carries it; the reference answer follows it and reproduces."""
    case = _case(case_id)
    llm = replay_llm(case, REPO)
    result, _ = evaluate(nirmaan_org, case, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=REPO,
                         sandbox=tmp_path / "sandbox", clock=fixed_clock, knowledge=knowledge)
    prompt = llm.calls[0].render()
    if case_id == TRIAGE:
        assert f'$value$plusargs("{NONCE_ARG.lstrip("+")}%s"' in prompt
        assert '$display("NIRMAAN-SIM %0s %0d passed, %0d failed"' in prompt
    assert result.passed, result.detail


def _reference(case_id, *, drop=(), replace=None):
    out = []
    for f in _case(case_id).reference:
        name = Path(f.path).name
        if name in drop:
            continue
        out.append((name, f.kind, replace[name] if replace and name in replace else _text(f.path), f.entry))
    return out


def _run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM(files, outcome=case.outcome)
    return run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                    sandbox=tmp_path / "sandbox", clock=fixed_clock)


@needs(*GATE_TOOLS)
def test_a_debounce_repro_with_only_a_high_pulse_passes_the_rtl_and_never_reaches_review(nirmaan_org, fixed_clock,
                                                                                       tmp_path):
    """The defect shows only on a low pulse while clean is high; a high bounce is filtered by the RTL under
    investigation too (the log's correct line)."""
    repro = _text(f"{DEB}/debounce_repro.v")
    weak = repro.replace('step(1\'b0, 1\'b1, "first cycle of a low pulse");\n        step(1\'b0, 1\'b1, "second cycle of a low pulse");',
                         'step(1\'b1, 1\'b1, "first cycle of a low pulse");\n        step(1\'b1, 1\'b1, "second cycle of a low pulse");')
    weak = weak.replace('step(1\'b0, (k >= STABLE) ? 1\'b0 : 1\'b1, "settled release")',
                        'step(1\'b1, 1\'b1, "settled release")')
    assert weak != repro
    files = _reference(ROOT, replace={"debounce_repro.v": weak})
    result = _run(nirmaan_org, fixed_clock, tmp_path, ROOT, files)
    assert not result.submitted, result
    assert "failure not reproduced" in result.detail, result.detail


@needs(*GATE_TOOLS)
def test_a_debounce_repro_that_expects_the_wrong_value_fails_the_clean_run_of_the_control(nirmaan_org, fixed_clock,
                                                                                         tmp_path):
    """It fails the RTL under investigation (the gate passes it) but also the fixed RTL, by expecting clean to move
    during the low pulse."""
    repro = _text(f"{DEB}/debounce_repro.v")
    weak = repro.replace('step(1\'b0, 1\'b1, "second cycle of a low pulse");', 'step(1\'b0, 1\'b0, "second cycle of a low pulse");')
    assert weak != repro
    files = _reference(ROOT, replace={"debounce_repro.v": weak})
    result = _run(nirmaan_org, fixed_clock, tmp_path, ROOT, files)
    assert result.submitted, result.detail
    assert result.scores[0].status is ScoreStatus.FAILED and not result.passed
    assert "the clean inputs do not pass" in result.scores[0].summary, result.scores[0].summary


@needs(*GATE_TOOLS)
def test_a_triage_with_a_repro_for_two_of_three_bugs_fails_the_third(nirmaan_org, fixed_clock, tmp_path):
    files = _reference(TRIAGE, drop=("pwm_gen_repro_duty_update.v",))
    result = _run(nirmaan_org, fixed_clock, tmp_path, TRIAGE, files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and "only 2 of 3 mutants have a file of their own" in score.summary


@needs(*GATE_TOOLS)
def test_one_pwm_repro_that_checks_all_three_things_cannot_stand_for_three_buckets(nirmaan_org, fixed_clock, tmp_path):
    """A single repro that measures the pulse, the period and the mid-period change fails all three seeded bugs, so
    only one mutant has a file of its own."""
    drop = ("pwm_gen_repro_period.v", "pwm_gen_repro_duty_update.v")
    pulse = _text(f"{PWM}/pwm_gen_repro_pulse_width.v")
    whole = pulse.replace(
        '        @(posedge pwm);\n        width = 0;\n        while (pwm) begin\n            width = width + 1;\n            @(posedge clk); #1;\n        end\n        verdict_check(width === 3, "the second pulse is not 3 clocks");',
        '        @(posedge pwm);\n        t0 = cycle;\n        @(negedge pwm);\n        @(posedge pwm);\n        verdict_check(cycle - t0 === PERIOD, "rising edges of pwm are not PERIOD clocks apart");\n'
        '        repeat (4) @(posedge clk);\n        #1 duty = 4\'d6;\n        repeat (2) begin\n            @(posedge clk); #1;\n'
        '            verdict_check(pwm === 1\'b0, "pwm rose after duty changed in the middle of a period");\n        end')
    assert whole != pulse
    files = _reference(TRIAGE, drop=drop, replace={"pwm_gen_repro_pulse_width.v": whole})
    result = _run(nirmaan_org, fixed_clock, tmp_path, TRIAGE, files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED, score
    assert "only 1 of 3 mutants have a file of their own" in score.summary, score.summary
