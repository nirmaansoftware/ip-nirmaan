"""WF23 question 1 on the timer path: a seat ``.sby`` at the flow's RTL stage (plan 2026-11-22, section 14).

Security asked (``evals/plans/2026-11-22-g3-whole-flow.md``, section 14, question 1): can a timer seat that declares
a ``formal_spec`` make ``formal.run`` and ``formal.cover`` run SBY, Yosys and a solver over its setup, which section
12 says does not happen? Settled by a test of the flow's RTL stage with a seat ``.sby``. This is that test.

Replay only; no model is called. The flow is ``flow/axil-timer`` as the planned workflow seats it (``run_flow``, the
default harness, three attempts per stage). Each stage replays the case's reference answer; at the RTL stage the
answer also declares one more file, of kind ``formal_spec``: the committed setup
``tests/fixtures/rtl/axil_timer/axil_timer.sby``, which reads only the seat's own ``axil_timer.v``.

What the tests pin, as the code does it today: the RTL stage's prompt names ``formal.run`` and ``formal.cover`` and
the ``formal_spec`` that starts them; nothing refuses the extra kind; both gates run SymbiYosys over the seat's own
setup before review, with the run's sources and setup the seat's files; and when one fails, a retry gives the seat
that run's summary and log excerpt, as for any other gate. So the formal gates do run on the timer path. These runs
are not ``vvp``, so in the ``live-eval`` job they stay with the runner account (``docs/LIVE_EVAL_EVIDENCE.md``,
section 6), screened before they run by the SBY checks of ``docs/GATE_INPUTS.md``, section 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import load_cases
from nirmaan.evals.flow import FlowReplayLLM, run_flow
from nirmaan.runtime import Completion, ModelRuntime

ROOT = Path(__file__).resolve().parents[1]
TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make", "sby", "yices-smt2")
TIMER = "flow/axil-timer"
SBY = ROOT / "tests" / "fixtures" / "rtl" / "axil_timer" / "axil_timer.sby"
RTL = "rtl-implementation"
FORMAL = ("formal.run", "formal.cover")
#: A setup the formal gates refuse on their bounds: a bounded check of four steps proves nothing, and four steps
#: leave covers unreached. Used once, on the first attempt, to make a formal run fail.
BOUNDED = SBY.read_text(encoding="utf-8").replace("mode prove", "mode bmc").replace("depth 10", "depth 4")


class _SeatSby(FlowReplayLLM):
    """The reference flow, whose RTL stage answer also declares a ``formal_spec``: ``setups[n]`` on the stage's
    n-th call (the last one on any later call)."""

    def __init__(self, case, repo, *setups: str) -> None:
        super().__init__(case, repo)
        self.setups = setups
        self.rtl_calls = 0

    def complete(self, prompt, tools=None):
        answer = super().complete(prompt, tools)
        if "rtl_source" not in prompt.outputs or answer.error:
            return answer
        setup = self.setups[min(self.rtl_calls, len(self.setups) - 1)]
        self.rtl_calls += 1
        head, rest = answer.text.split("\n", 1)
        data = json.loads(head)
        cites = data["files"][0]["summary"].split(", from ", 1)[1]  # the same citations as the replayed RTL
        data["files"].append({"path": SBY.name, "kind": "formal_spec", "title": SBY.name,
                              "summary": f"{SBY.name}, from {cites}"})
        return Completion(f"{json.dumps(data)}\n{rest}=== FILE: {SBY.name} ===\n{setup}=== END FILE ===\n", self.name)


@pytest.fixture(scope="module")
def timer():
    return next(c for c in load_cases(ROOT / "evals", flow="whole") if c.id == TIMER)


def _rtl(run):
    return next(s for s in run.stages if s.stage == RTL)


@TOOLS
def test_a_timer_seat_that_writes_a_sby_makes_the_rtl_stage_run_formal_and_cover(nirmaan_org, timer, tmp_path,
                                                                                 fixed_clock):
    llm = _SeatSby(timer, ROOT, SBY.read_text(encoding="utf-8"))
    run = run_flow(nirmaan_org, timer, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=ROOT,
                   sandbox=tmp_path, clock=fixed_clock)
    [prompt] = [p for p in llm.calls if "rtl_source" in p.outputs]
    # The stage's outputs do not include a formal_spec, but its prompt names the gates and the kind that starts them.
    assert "formal_spec" not in prompt.outputs
    text = prompt.render()
    assert "applies only if you produce a formal_spec file" in text
    assert all(f"Input contract of {tool}" in text for tool in FORMAL)
    # Nothing refuses the extra kind: the stage reaches review on its first attempt, with the seat's .sby recorded.
    rtl = _rtl(run)
    assert rtl.status == "in_review" and rtl.attempts == 1
    task = run.engine.task(rtl.task)
    kinds = {run.engine.state.artifacts[a].kind: run.engine.state.artifacts[a] for a in task.artifacts}
    assert set(kinds) == {"rtl_source", "testbench", "formal_spec"}
    # Both formal gates ran SymbiYosys before review, over the seat's own setup and the seat's own RTL.
    runs = {g.tool: run.engine.state.tool_runs[g.run] for g in rtl.gate_runs}
    assert [g.tool for g in rtl.gate_runs] == ["lint.run", "simulator.run", "synth.run", *FORMAL]
    for tool in FORMAL:
        ran = runs[tool]
        assert ran.succeeded and ran.task == rtl.task, (tool, ran.summary)
        assert ran.params["sby"] == kinds["formal_spec"].location
        assert Path(ran.params["sby"]).read_text(encoding="utf-8") == SBY.read_text(encoding="utf-8")
        assert list(ran.params["sources"]) == [kinds["rtl_source"].location]
        log = Path(ran.references[0]).read_text(encoding="utf-8", errors="replace")
        assert "SBY" in log and "DONE (PASS" in log  # SymbiYosys itself ran, with Yosys and the solver under it
    assert runs["formal.run"].summary == "symbiyosys: formal passed: every property proven"
    assert runs["formal.cover"].summary.startswith("symbiyosys-cover: not vacuous: every cover reached")
    assert run.result.passed and run.result.submitted


@TOOLS
def test_a_failed_formal_run_returns_its_log_excerpt_to_the_timer_seat_on_a_retry(nirmaan_org, timer, tmp_path,
                                                                                  fixed_clock):
    llm = _SeatSby(timer, ROOT, BOUNDED, SBY.read_text(encoding="utf-8"))
    run = run_flow(nirmaan_org, timer, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=ROOT,
                   sandbox=tmp_path, clock=fixed_clock)
    rtl = _rtl(run)
    assert rtl.status == "in_review" and rtl.attempts == 2
    first = [g for g in rtl.gate_runs if g.tool in FORMAL][:2]
    assert [(g.tool, g.succeeded) for g in first] == [("formal.run", False), ("formal.cover", False)]
    assert first[0].summary.startswith("limit not met: proven 0 is below min_proven 1")
    retry = [p for p in llm.calls if "rtl_source" in p.outputs][1].render()
    for g in first:  # each failed formal run comes back as its summary and an excerpt of the SBY log
        assert f"- Failed run [run:{g.run}] {g.tool}" in retry
        excerpt = retry.split(f"- Log excerpt of [run:{g.run}]", 1)[1].split("\n- ", 1)[0]
        lines = [line for line in excerpt.splitlines()[1:] if line.startswith("| ")]
        assert any(line.startswith("| SBY ") for line in lines), lines  # lines SymbiYosys itself wrote
