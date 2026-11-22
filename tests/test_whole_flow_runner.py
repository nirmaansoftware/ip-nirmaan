"""The whole-flow runner, part 4b (G3, council record 2026-11-17, decision 3; gates WF4, WF6, WF8).

Every stage is seated through run_task with one seat runtime, in dependency order; review and approval are a
pass-through under the harness's own actor with a true note; a stage that does not reach review stops the flow;
only the final block is judged, on the files of every stage. Replays, no model call: the reference flow passes
every check for both cases and re-judges clean; a flow with a planted upstream fault fails; a flow on the
conforming RTL passes; a flow whose second stage never reaches review is a failed trial with the later stages and
every check not run. The label comes from the case; the requirements seat reads the fixed document as text; the
whole-flow stop rule reads the last answer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import load_cases, load_record, record_run, rejudge
from nirmaan.evals.flow import NOTE_UNCHECKED, PASSTHROUGH, FlowReplayLLM, run_flow
from nirmaan.evals.records import flow_stopped, no_model_answer
from nirmaan.evals.runner import FIXTURE
from nirmaan.models import CaseFile, EvalResult, EvalTrial, RecordedAnswer, ScoreStatus
from nirmaan.runtime import Completion, ModelRuntime, harness

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make")
A = "tests/fixtures/rtl/axi4_lite"
T = "tests/fixtures/rtl/axil_timer"
F = "tests/fixtures/fw/axi4_lite"


@pytest.fixture(scope="module")
def flows():
    return {c.id: c for c in load_cases(EVALS, flow="whole")}


def _swap(case, **files):
    """The case with some reference files put in another's place (the planted fault, the conforming RTL); each
    stand-in is answered under the name of the file it replaces."""
    ref = [CaseFile(path=files.get(Path(f.path).name, f.path), kind=f.kind, entry=f.entry) for f in case.reference]
    names = {files[Path(f.path).name]: Path(f.path).name for f in case.reference if Path(f.path).name in files}
    return case.model_copy(update={"reference": tuple(ref)}), names


def _replay(case, names=None):
    llm = FlowReplayLLM(case, ROOT)
    renamed = {Path(p).name: n for p, n in (names or {}).items()}
    llm._files = [(renamed.get(name, name), kind, text, entry) for name, kind, text, entry in llm._files]
    return llm


def _flow(nirmaan_org, case, tmp_path, fixed_clock, llm=None):
    if isinstance(case, tuple):
        case, names = case
        llm = llm or _replay(case, names)
    llm = llm or FlowReplayLLM(case, ROOT)
    return run_flow(nirmaan_org, case, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=ROOT,
                    sandbox=tmp_path / "flow", clock=fixed_clock), llm


# --- The reference flow, through every seated stage (WF4) ---------------------------------------------------------


@TOOLS
@pytest.mark.parametrize("case_id", ["flow/axil-timer", "flow/axi4-lite-regs-driver"])
def test_the_reference_flow_passes_every_check_and_re_judges_clean(nirmaan_org, flows, tmp_path, case_id):
    case = flows[case_id]
    path = record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path / "results")
    record = load_record(path)
    [trial] = record.trials
    assert path.name.endswith("-whole-flow") and record.manifest.flow == "whole" and trial.flow == "whole"
    assert trial.result.passed, [(s.name, s.status.value, s.summary) for s in trial.result.scores]
    assert all(s.status is ScoreStatus.PASSED for s in trial.result.scores) and len(trial.result.scores) == len(
        case.held_out)
    assert [s.stage for s in trial.stages] == list(case.exercised)
    assert [s.status for s in trial.stages[:-1]] == ["completed"] * (len(trial.stages) - 1)
    assert trial.stages[-1].status == "in_review"  # the final block is judged, not approved
    assert trial.flow_digest and trial.flow_digest.startswith("sha256:") and trial.skills == {}
    assert trial.result.attempts == max(s.attempts for s in trial.stages) == 1
    for stage in trial.stages:
        assert stage.skills and set(stage.skills) == set(case.exercised[stage.stage])
        assert "reviewed in the repository" not in stage.note and stage.note.startswith("Whole-flow evaluation: "
                                                                                       "not reviewed.")
        assert FIXTURE not in (stage.reviewed_by or "") + (stage.approved_by or "")
    for stage in trial.stages[:-1]:  # every stage before the last: the harness's pass-through, never the fixture
        assert stage.reviewed_by.endswith(f"({PASSTHROUGH})") and stage.approved_by.endswith(f"({PASSTHROUGH})")
    assert trial.stages[-1].reviewed_by is None
    # The specification stages have no before-review check: "submitted, not checked".
    assert next(s for s in trial.stages if s.stage == "interface-spec").note == NOTE_UNCHECKED
    rtl = next(s for s in trial.stages if s.stage == "rtl-implementation")
    assert "Before-review checks passed: " in rtl.note and rtl.gate_runs
    outcomes = rejudge(nirmaan_org, record, {case.id: case}, repo=ROOT, sandbox=tmp_path / "rejudge")
    assert [o.same for o in outcomes] == [True], [o.differences for o in outcomes]
    # The harness is the whole flow's: its own fingerprint, on the result and every answer.
    assert trial.result.harness == harness.harness_sha256(flow="whole", cli=None)
    assert all(a.harness == trial.result.harness for a in trial.answers)


@TOOLS
def test_the_requirements_seat_reads_the_fixed_document_as_text(nirmaan_org, flows, tmp_path, fixed_clock):
    case = flows["flow/axil-timer"]
    _, llm = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    first = llm.calls[0]
    assert "requirements_spec" in first.outputs
    text = first.render()
    assert (EVALS / "flow" / "axil_timer" / "requirements.md").read_text(encoding="utf-8") in text
    assert all("[req:TMR-MODULE]" not in call.render() or call is first or "requirements_spec" not in call.outputs
               for call in llm.calls)


# --- Planted faults and the conforming RTL ------------------------------------------------------------------------


@TOOLS
def test_a_flow_ending_in_a_mutant_rtl_fails(nirmaan_org, flows, tmp_path, fixed_clock):
    case = _swap(flows["flow/axil-timer"], **{"axil_timer.v": f"{T}/mutants/axil_timer_reload_off_by_one.v",
                                              "axil_timer_tb.v": f"{T}/axil_timer_tb_trivial.v"})
    case = (case[0].model_copy(update={"reference": tuple(
        f.model_copy(update={"entry": "axil_timer_tb_trivial"}) if f.kind == "testbench" else f
        for f in case[0].reference)}), case[1])
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    assert run.result.submitted and not run.result.passed
    assert [s.status for s in run.result.scores] == [ScoreStatus.FAILED, ScoreStatus.FAILED]


@TOOLS
def test_a_flow_with_the_wrong_map_fails_on_both_rtls(nirmaan_org, flows, tmp_path, fixed_clock):
    case = _swap(flows["flow/axi4-lite-regs-driver"], **{"axi4_lite_regs_map.h": f"{F}/axi4_lite_regs_map_wrong.h",
                                                         "axi4_lite_regs_test.c": f"{F}/axi4_lite_regs_test_lenient.c"})
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    verdicts = {s.name.split(".")[0]: s.status for s in run.result.scores}
    assert run.result.submitted and not run.result.passed
    assert verdicts["5"] is ScoreStatus.FAILED and verdicts["6"] is ScoreStatus.FAILED


@TOOLS
def test_a_flow_on_the_conforming_rtl_passes_and_check_5_takes_the_rtl_stages_top(nirmaan_org, flows, tmp_path,
                                                                                   fixed_clock):
    case = _swap(flows["flow/axi4-lite-regs-driver"], **{"axi4_lite_regs.v": f"{A}/variants/axi4_lite_regs_lat2.v"})
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    assert run.result.passed, [(s.name, s.status.value, s.summary) for s in run.result.scores]
    [check5] = [s for s in run.result.scores if s.name.startswith("5.")]
    params = run.engine.state.tool_runs[check5.runs[0]].params
    assert params["top"] == "axi4_lite_regs" and any("lat2" in str(p) or "axi4_lite_regs.v" in str(p)
                                                     for p in params["rtl"])


@TOOLS
def test_a_flow_test_stricter_than_the_contract_is_named_as_an_inference(nirmaan_org, flows, tmp_path, fixed_clock):
    """The conforming RTL with a testbench written to its one choice (exactly 2 cycles): the flow's block passes
    the reference testbench, and its own testbench fails on the reference RTL; the cause is stated as an inference."""
    case = _swap(flows["flow/axi4-lite-regs-driver"],
                 **{"axi4_lite_regs.v": f"{A}/variants/axi4_lite_regs_lat2.v",
                    "axi4_lite_regs_tb.v": f"{A}/variants/axi4_lite_regs_tb_strict2.v"})
    case = (case[0].model_copy(update={"reference": tuple(
        f.model_copy(update={"entry": "axi4_lite_regs_tb_strict2"}) if f.kind == "testbench" else f
        for f in case[0].reference)}), case[1])
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    verdicts = {s.name.split(".")[0]: s.status for s in run.result.scores}
    assert verdicts["1"] is ScoreStatus.PASSED and verdicts["3"] is ScoreStatus.FAILED and not run.result.passed
    assert "an inference, not a fact" in run.result.detail and "stricter than the contract" in run.result.detail


@TOOLS
def test_a_plain_fault_is_not_called_a_stricter_test(nirmaan_org, flows, tmp_path, fixed_clock):
    case = _swap(flows["flow/axil-timer"], **{"axil_timer.v": f"{T}/mutants/axil_timer_reload_off_by_one.v",
                                              "axil_timer_tb.v": f"{T}/axil_timer_tb_trivial.v"})
    case = (case[0].model_copy(update={"reference": tuple(
        f.model_copy(update={"entry": "axil_timer_tb_trivial"}) if f.kind == "testbench" else f
        for f in case[0].reference)}), case[1])
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock)
    assert not run.result.passed and "stricter than the contract" not in run.result.detail


# --- A stage that never reaches review ----------------------------------------------------------------------------


class _Silent(FlowReplayLLM):
    """No answer at the interface-spec stage, as on a usage limit; every other stage answers."""

    def complete(self, prompt, tools=None):
        if "interface_spec" in prompt.outputs:
            self.calls.append(prompt)
            return Completion("", error="no model answer")
        return super().complete(prompt, tools)


def test_a_flow_whose_second_stage_never_reaches_review_is_a_failed_trial(nirmaan_org, flows, tmp_path, fixed_clock):
    case = flows["flow/axil-timer"]
    run, _ = _flow(nirmaan_org, case, tmp_path, fixed_clock, _Silent(case, ROOT))
    assert not run.result.submitted and not run.result.passed and run.result.seat_status == "not run"
    statuses = [s.status for s in run.stages]
    assert statuses[0] == "completed" and statuses[1] != "completed" and statuses[2:] == ["not run", "not run"]
    assert all(s.status is ScoreStatus.NOT_RUN for s in run.result.scores)
    assert "stage interface-spec did not complete" in run.result.detail


# --- The stop rule (WF8) --------------------------------------------------------------------------------------------


def _trial(*answers) -> EvalTrial:
    from datetime import datetime, timezone

    at = datetime(2026, 11, 18, tzinfo=timezone.utc)
    result = EvalResult(case="c", case_digest="d", runtime="claude-code", replay=False, version="t", started_at=at,
                        duration_s=1, seat="s", seat_status="x", submitted=False, attempts=1, passed=False,
                        audit_ok=True, sandbox="s")
    return EvalTrial(record="r", trial=1, stage="s", result=result, flow="whole",
                     answers=tuple(RecordedAnswer(mode="work", prompt_sha256="p", packet_sha256="k", text=t, error=e)
                                   for t, e in answers))


def test_the_whole_flow_stop_rule_reads_the_last_answer():
    limit = _trial(("a", None), ("b", None), ("", "hit your limit"))
    assert flow_stopped(limit) and no_model_answer(limit)  # the single-seat rule reads the last answer too
    assert not flow_stopped(_trial(("a", None), ("b", None), ("c", None)))
    assert not flow_stopped(_trial(("a", None), ("", None)))  # no text but no error: an answer, however empty
    assert not flow_stopped(_trial())


# --- The fingerprint carries the flow module ---------------------------------------------------------------------


def test_the_whole_flow_fingerprint_digests_this_module():
    [rel] = harness.FLOW_CODE
    expected = "sha256:" + hashlib.sha256((harness.SOURCE_ROOT / rel).read_bytes()).hexdigest()
    assert harness.fingerprint(flow="whole")["flow"]["code"] == {rel: expected}
