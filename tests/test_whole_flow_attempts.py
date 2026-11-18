"""Attempts in a whole flow (G3 third addendum, 2026-11-19; gates WF21 and WF22).

Fake and replay models only; no model is called. WF21 (c): a whole-flow stage's first-attempt prompt is the same
whether the run allows one attempt or three. WF22: on the default harness's three attempts, a stage whose
second model call returns no answer ends, the later stages do not run, the trial fails, and the live run's stop
rule fires on it; the answer is never asked for again within the stage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import load_cases, load_record, record_run
from nirmaan.evals.flow import FlowReplayLLM, run_flow
from nirmaan.evals.records import RunStopped, flow_stopped
from nirmaan.models import ScoreStatus
from nirmaan.runtime import Completion, ModelRuntime, harness, register_runtime, unregister_runtime

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make")
TIMER = "flow/axil-timer"
SECOND = "interface_spec"  # the output kind of the timer flow's second stage


@pytest.fixture(scope="module")
def timer():
    return next(c for c in load_cases(EVALS, flow="whole") if c.id == TIMER)


# --- WF21 (c): the first attempt of a stage is the same prompt on one attempt and on three -----------------------


@TOOLS
def test_a_stages_first_attempt_prompt_is_the_same_on_one_attempt_and_on_three(nirmaan_org, timer, tmp_path,
                                                                               fixed_clock):
    """Every stage of the replayed flow passes on its first attempt, so each recorded call is a first attempt."""
    seen = {}
    for attempts in (1, 3):
        llm = FlowReplayLLM(timer, ROOT)
        run = run_flow(nirmaan_org, timer, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=ROOT,
                       attempts=attempts, sandbox=tmp_path / f"a{attempts}", clock=fixed_clock)
        assert [s.attempts for s in run.stages] == [1] * len(timer.exercised)
        assert len(llm.calls) == len(timer.exercised)  # one call per seated stage: all first attempts
        seen[attempts] = llm.calls
    for one, three in zip(seen[1], seen[3]):
        assert one == three and one.render() == three.render() and one.system == three.system
    # What does differ is the fingerprint: the run's attempts are part of it, and only they separate the two.
    assert harness.harness_sha256(attempts=1, flow="whole") != harness.harness_sha256(flow="whole")


# --- WF22: a stage's second call returns no answer, on three attempts --------------------------------------------


class _SecondCallEmpty(FlowReplayLLM):
    """At the second stage: the first call is a refused answer (no uncertainty), the second returns no answer, and a
    third call, if the stage ever made one, would be the good reference answer."""

    def __init__(self, case, repo) -> None:
        super().__init__(case, repo)
        self.stage_calls = 0

    def complete(self, prompt, tools=None):
        if SECOND not in prompt.outputs:
            return super().complete(prompt, tools)
        self.stage_calls += 1
        self.calls.append(prompt)
        if self.stage_calls == 1:
            good = super().complete(prompt, tools)
            self.calls.pop()
            head, rest = good.text.split("\n", 1)
            data = json.loads(head)
            del data["uncertainty"]
            return Completion(json.dumps(data) + "\n" + rest, self.name)
        if self.stage_calls == 2:
            return Completion("", self.name, error="no model answer")
        return super().complete(prompt, tools)


@TOOLS
def test_a_stages_second_call_with_no_answer_ends_the_stage_the_trial_fails_and_the_stop_rule_fires(
        nirmaan_org, timer, tmp_path, fixed_clock):
    assert harness.run_attempts(None, "default") == 3  # the default harness's own attempts
    llm = _SecondCallEmpty(timer, ROOT)
    register_runtime("wf22-fake")(lambda: ModelRuntime(llm, runtime_id="wf22-fake"))
    try:
        with pytest.raises(RunStopped) as stop:
            record_run(nirmaan_org, [timer], "wf22-fake", trials=3, repo=ROOT, out=tmp_path / "results",
                       clock=fixed_clock, stop_on_no_answer=True)
    finally:
        unregister_runtime("wf22-fake")
    record = load_record(stop.value.path)
    [trial] = record.trials  # the run stopped on this trial: trials 2 and 3 never started
    assert record.manifest.trials == 3 and not trial.result.replay
    assert llm.stage_calls == 2  # the stage was not asked a third time, though its attempts allowed it
    second = trial.stages[1]
    assert second.model_calls == 2 and second.status == "in_progress" and second.attempts == 2
    assert trial.stages[0].status == "completed"
    assert [s.status for s in trial.stages[2:]] == ["not run"] * (len(trial.stages) - 2)
    assert not trial.result.submitted and not trial.result.passed and trial.result.seat_status == "not run"
    assert all(s.status is ScoreStatus.NOT_RUN for s in trial.result.scores)
    assert f"stage {second.stage} did not complete" in trial.result.detail
    assert [bool(a.error) for a in trial.answers] == [False, False, True]  # stage 1, the refused call, the empty one
    assert not trial.answers[-1].text and trial.answers[-1].error and flow_stopped(trial)
    assert len(trial.stages) == len(timer.exercised)
