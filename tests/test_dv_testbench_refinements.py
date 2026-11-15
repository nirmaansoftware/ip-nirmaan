"""Block verification's testbench refinements for a scoreboard and for cocotb (M83, W2-R3).

Two more words refine ``block-verification``'s testbench task the way M68's
do: "scoreboard" or "reference model" adds ``reference_modelling``, and
"cocotb" or "Python tests" adds ``python_verification``, so the skills the
dv/scoreboard-mac and dv/cocotb-crc cases judge reach the testbench seat's
packet. Asked for cocotb, the testbench's before-review gate runs the seat's
Python tests through ``simulator.run``'s cocotb backend (M72) instead of the
HDL testbench gate. Every request without the two words plans as before and
renders the same prompts. Real-tool tests skip when Icarus or cocotb is absent
(or fail when CI names them in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import json
import re
import shutil
from functools import cache
from pathlib import Path

import pytest

from laws import needs
from test_block_verification import EVERYTHING, NOT_BLOCK_VERIFICATION, SEATS, SIM_LEAD, SPEC, TB_SENIOR
from test_nirmaan_applicability_golden import REQUESTS

from nirmaan.company import builder
from nirmaan.company.workflows import when
from nirmaan.evals import load_case, load_cases, run_case, validate_case
from nirmaan.models import FileInput, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import assemble, render_work_prompt

REPO = Path(__file__).resolve().parents[1]
COUNTER = "tests/fixtures/rtl/counter.v"
COUNTER_TB = "tests/fixtures/rtl/counter_tb.v"
COCOTB_TESTS = "tests/fixtures/cocotb/counter_cocotb.py"
WRAPS_EARLY = "tests/fixtures/eqy/counter_wraps_early.v"

NEW_FEATURES = ("scoreboard", "cocotb")

SCOREBOARD = "Verify the existing MAC block RTL with a scoreboard against a reference model."
COCOTB = "Verify the existing CRC block RTL with a cocotb testbench."
PYTHON = "Verify the existing CRC block RTL with Python tests."
ALL_TESTBENCH = ("Verify the existing CRC block RTL with constrained-random SystemVerilog stimulus, a scoreboard "
                 "and Python tests through cocotb.")

#: Each request's testbench seat: the task's skills, its owner and its reviewer.
TESTBENCH_SEATS = {
    SCOREBOARD: (("directed_testing", "reference_modelling"), TB_SENIOR, SIM_LEAD),
    COCOTB: (("directed_testing", "python_verification"), TB_SENIOR, SIM_LEAD),
    PYTHON: (("directed_testing", "python_verification"), TB_SENIOR, SIM_LEAD),
}

HDL_GATE = "The seat's testbench passes on the approved RTL"
COCOTB_GATE = "The seat's cocotb tests pass on the approved RTL"


def _testbench(engine):
    tasks = [t for t in engine.state.tasks.values() if t.stage == "testbench"]
    assert len(tasks) == 1, [t.id for t in tasks]
    return tasks[0]


def _gates(task):
    return {r.description: r for r in task.evidence_requirements if r.before_review}


# --- Planning and packets ------------------------------------------------------------------------------


@pytest.mark.parametrize("request_text", sorted(TESTBENCH_SEATS))
def test_each_refinement_reaches_the_testbench_seat(request_text, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert engine.state.project.workflows == ("block-verification",)
    task = _testbench(engine)
    skills, owner, reviewer = TESTBENCH_SEATS[request_text]
    assert (task.skills, task.owner, task.reviewer) == (skills, owner, reviewer)
    for seat in (None, owner, reviewer):
        packet = assemble(engine, task.id) if seat is None else assemble(engine, task.id, role=seat)
        assert set(skills) <= {s.id for s in packet.domain.skills}, seat
        assert packet.domain.declines is None


def test_a_scoreboard_keeps_the_hdl_testbench_gate(nirmaan_org, fixed_clock):
    task = _testbench(Orchestrator(nirmaan_org, clock=fixed_clock).plan(SCOREBOARD))
    assert set(_gates(task)) == {HDL_GATE}
    assert _gates(task)[HDL_GATE].params == ()


@pytest.mark.parametrize("request_text", [COCOTB, PYTHON])
def test_cocotb_gates_the_testbench_on_the_cocotb_backend_instead(request_text, nirmaan_org, fixed_clock):
    task = _testbench(Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text))
    gate, = _gates(task).values()
    assert gate.description == COCOTB_GATE
    assert gate.tools == ("simulator.run",) and gate.params == (("backend", "cocotb"),)
    assert gate.files == (FileInput(param="sources", kinds=("rtl_source",), upstream=True),
                          FileInput(param="cocotb", kinds=("testbench",)),
                          FileInput(param="top", kinds=("testbench",), entry=True))


def test_the_cocotb_seat_is_told_the_backend_and_the_test_modules(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COCOTB)
    prompt = render_work_prompt(assemble(engine, _testbench(engine).id), "work").render()
    assert "Set by the platform: backend=cocotb." in prompt
    assert "Parameter cocotb takes" in prompt and "The platform fills it from your testbench files" in prompt


def test_every_testbench_word_at_once_stays_within_the_domain_cap(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(ALL_TESTBENCH)
    task = _testbench(engine)
    assert task.skills == ("directed_testing", "systemverilog", "constrained_random", "reference_modelling",
                           "python_verification")
    assert set(_gates(task)) == {COCOTB_GATE}
    for seat in (task.owner, task.reviewer):
        assert assemble(engine, task.id, role=seat).domain.declines is None, seat


# --- Nothing else moves ----------------------------------------------------------------------------------

#: The HDL gate's plan-time clause: it holds for every request that does not ask for cocotb.
NOT_COCOTB = (when(none_of=("cocotb",)),)


@cache
def _pre_org():
    """The organization without this change: no new features, the testbench stage as M68 to M72 left it."""
    b = builder()
    d = b.definition
    d.features = [f for f in d.features if f.feature not in NEW_FEATURES]

    def stage(s):
        if s.id != "testbench":
            return s
        return s.model_copy(update={
            "refinements": tuple(r for r in s.refinements if not set(r.when.any_of) & set(NEW_FEATURES)),
            "evidence": tuple(r.model_copy(update={"when": ()}) if r.when == NOT_COCOTB else r
                              for r in s.evidence if dict(r.params).get("backend") != "cocotb")})

    d.workflows = [wf.model_copy(update={"stages": tuple(stage(s) for s in wf.stages)})
                   if wf.id == "block-verification" else wf for wf in d.workflows]
    return b.build()


def _plan(org, text, clock):
    """Every task, by its ID within the project, without the HDL gate's one new clause."""
    state = Orchestrator(org, clock=clock).plan(text).state
    pid = state.project.id
    tasks = {}
    for task in state.tasks.values():
        data = json.loads(task.model_dump_json().replace(pid, "<project>"))
        for req in data["evidence_requirements"]:
            if req["when"] == [{"on": "features", "all_of": [], "any_of": [], "none_of": ["cocotb"]}]:
                req["when"] = []
        tasks[task.id.removeprefix(pid + ":")] = data
    return tasks


def _prompts(org, text, clock):
    engine = Orchestrator(org, clock=clock).plan(text)
    return {(t.stage, mode): re.sub(r"prj-[0-9a-f]{10}", "prj-<id>",
                                    render_work_prompt(assemble(engine, t.id), mode).render())
            for t in engine.state.tasks.values() if t.stage for mode in ("work", "review")}


def _case_requests():
    """Every shipped case's request but the two that ask for the new words (the W2-E6 cases, written after them)."""
    return sorted({c.request for sub in ("dv", "rtl", "firmware", "spec") for c in load_cases(REPO / "evals" / sub)}
                  - {SCOREBOARD, COCOTB})


#: Every request written before this change: the golden suite's, M68's, and every eval case's.
EARLIER = sorted({*REQUESTS, *NOT_BLOCK_VERIFICATION, *(text for text, _ in SEATS), *_case_requests()})


def test_the_earlier_requests_name_neither_new_word(nirmaan_org, fixed_clock):
    for text in EARLIER:
        features = Orchestrator(nirmaan_org, clock=fixed_clock).plan(text).state.project.analysis.features
        assert not set(features) & set(NEW_FEATURES), text


@pytest.mark.parametrize("request_text", EARLIER)
def test_every_earlier_request_plans_and_prompts_as_before(request_text, nirmaan_org, fixed_clock):
    assert _plan(_pre_org(), request_text, fixed_clock) == _plan(nirmaan_org, request_text, fixed_clock)
    assert _prompts(_pre_org(), request_text, fixed_clock) == _prompts(nirmaan_org, request_text, fixed_clock)


def test_the_hdl_gate_changes_only_by_a_clause_that_holds_without_cocotb(nirmaan_org, fixed_clock):
    task = _testbench(Orchestrator(nirmaan_org, clock=fixed_clock).plan(EVERYTHING))
    gate, = _gates(task).values()
    assert gate.description == HDL_GATE and gate.when == NOT_COCOTB and gate.params == ()


# --- The cocotb gate, for real, through the eval harness ------------------------------------------------


def _case(tmp_path: Path, request: str, reference: list[dict], held_out: list[dict]) -> Path:
    data = {"id": "tmp/block-verification-cocotb", "request": request, "seat": "testbench",
            "expected_behavior": "The seat's tests pass on the approved RTL and fail the mutant.",
            "upstream": {"interface-spec": [{"path": SPEC, "kind": "interface_spec"}],
                         "design-under-test": [{"path": COUNTER, "kind": "rtl_source", "entry": "counter"}]},
            "reference": reference, "held_out": held_out}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


PYTHON_SEAT = [{"path": COCOTB_TESTS, "kind": "testbench", "entry": "counter"}]
COCOTB_REQUEST = "Verify the existing 4-bit wrapping counter RTL with cocotb tests."


@needs("iverilog", "vvp", modules=("cocotb",))
def test_a_cocotb_seat_passes_its_gate_on_the_approved_rtl_and_fails_the_mutant(nirmaan_org, fixed_clock,
                                                                                tmp_path):
    mutant = tmp_path / "mutants" / "counter.v"
    mutant.parent.mkdir(parents=True)
    shutil.copy(REPO / WRAPS_EARLY, mutant)
    case = load_case(_case(tmp_path, COCOTB_REQUEST, PYTHON_SEAT,
                           [{"name": "The seat's cocotb tests fail the mutant", "scorer": "must-fail",
                             "tool": "simulator.run", "params": {"backend": "cocotb"},
                             "seat_files": {"cocotb": ["testbench"]}, "seat_entries": {"top": ["testbench"]},
                             "case_files": {"sources": [COUNTER]}, "mutants": {COUNTER: [str(mutant)]}}]))
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores


@needs("iverilog", "vvp", modules=("cocotb",))
def test_python_tests_do_not_pass_the_hdl_gate(nirmaan_org, fixed_clock, tmp_path):
    """Without the word, the gate is the HDL testbench's: the Python tests are not run and the work is refused."""
    case = load_case(_case(tmp_path, "Verify the existing 4-bit wrapping counter RTL.", PYTHON_SEAT, []))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted, result


@needs("iverilog", "vvp", modules=("cocotb",))
def test_an_hdl_testbench_does_not_pass_the_cocotb_gate(nirmaan_org, fixed_clock, tmp_path):
    case = load_case(_case(tmp_path, COCOTB_REQUEST,
                           [{"path": COUNTER_TB, "kind": "testbench", "entry": "counter_tb"}], []))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted, result
