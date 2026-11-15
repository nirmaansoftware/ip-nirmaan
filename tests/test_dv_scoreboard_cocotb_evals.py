"""The scoreboard and cocotb eval cases (wave 2, W2-E6).

Two cases judge the testbench seat of M68's block-verification workflow, each
asked for one of M83's refinements:

* ``dv/scoreboard-mac`` (``tests/fixtures/dv/mac8/``) judges ``directed_testing``
  and ``reference_modelling`` (the word "scoreboard" adds the second): the
  seat's SystemVerilog testbench must pass the approved saturating MAC block
  and fail each of five RTL mutants, on a failed check. Its gate is the HDL
  testbench gate.
* ``dv/cocotb-crc`` (``tests/fixtures/dv/crc8/``, the CRC engine of
  ``dv/random-crc``) judges ``directed_testing`` and ``python_verification``
  (the word "cocotb" adds the second): the seat's Python tests must pass the
  approved CRC engine under the cocotb gate and fail each of the same five RTL
  mutants, on a failed test, never a build.

Each request plans block-verification and the testbench seat's packet, for the
owner and the reviewer, carries every skill the case judges. Real-tool tests
need the simulators (and cocotb) (``laws.needs``); nothing here states a
measured figure, and the reference tests assert at run time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS

from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.models import FileInput, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
MAC = "tests/fixtures/dv/mac8"
CRC = "tests/fixtures/dv/crc8"
COCOTB = ("iverilog", "vvp")

OWNER = "verification.dynamic.testbench.testing.senior"
REVIEWER = "verification.dynamic.testbench.tech_lead"

#: Each case: its seat's skills, then the gate description its testbench task carries.
CASES = {
    "dv/scoreboard-mac": (("directed_testing", "reference_modelling"), "The seat's testbench passes on the approved RTL"),
    "dv/cocotb-crc": (("directed_testing", "python_verification"), "The seat's cocotb tests pass on the approved RTL"),
}

#: Each mutant of a case's control, with the change it makes.
MAC_MUTANTS = {
    "mac8_no_saturate.v": "the total wraps at 24 bits and the flag never rises",
    "mac8_clear_loses.v": "an accumulate offered with clr wins over the clear",
    "mac8_signed_operands.v": "the operands are read as signed numbers",
    "mac8_flag_not_sticky.v": "the flag follows the latest accumulate",
    "mac8_clear_keeps_flag.v": "a clear zeroes the total and leaves the flag",
}
CRC_MUTANTS = ["crc8_block_poly_tap.v", "crc8_block_reflected_input.v", "crc8_block_no_final_xor.v",
               "crc8_block_init_loses.v", "crc8_block_hold_ignored.v"]


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _control(case):
    [control] = [c for c in case.held_out if c.scorer == "must-fail"]
    return control


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def _trial(nirmaan_org, fixed_clock, tmp_path, case_id, count):
    case = _case(case_id)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert len(score.failed_runs) == count
    return {j.run: j for j in trial.judge_runs}, score


def _weak_run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM(list(files))
    return case, run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                          sandbox=tmp_path / "sandbox", clock=fixed_clock)


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                 fixed_clock):
    case = _case(case_id)
    skills, _ = CASES[case_id]
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == "testbench" and set(case.skills) == set(skills)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "block_verification"
    [task] = [t for t in engine.state.tasks.values() if t.stage == "testbench"]
    assert task.workflow == "block-verification"
    assert (task.skills, task.owner, task.reviewer) == (skills, OWNER, REVIEWER)
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, (case_id, role)
        assert packet.domain.declines is None
    assert set(case.upstream) <= {engine.task(d).stage for d in task.depends_on}


def test_the_refinement_words_are_what_add_the_skills_and_pick_the_gate(nirmaan_org, fixed_clock):
    """"scoreboard" keeps the HDL gate; "cocotb" swaps it for the cocotb backend's, whose files are the Python tests."""
    for case_id, (_, description) in CASES.items():
        engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case(case_id).request)
        [task] = [t for t in engine.state.tasks.values() if t.stage == "testbench"]
        gates = {r.description: r for r in task.evidence_requirements if r.before_review}
        assert set(gates) == {description}, case_id
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case("dv/cocotb-crc").request)
    [task] = [t for t in engine.state.tasks.values() if t.stage == "testbench"]
    [gate] = [r for r in task.evidence_requirements if r.before_review]
    assert gate.params == (("backend", "cocotb"),)
    assert FileInput(param="cocotb", kinds=("testbench",)) in gate.files
    features = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case("dv/scoreboard-mac").request).state.project.analysis.features
    assert "scoreboard" in features and "cocotb" not in features


def test_every_mutant_in_the_folders_is_listed_by_its_cases():
    [(replaced, listed)] = _control(_case("dv/scoreboard-mac")).mutants.items()
    assert [Path(m).name for m in listed] == list(MAC_MUTANTS) and Path(replaced).name == "mac8.v"
    assert {f.name for f in (REPO / MAC / "mutants").iterdir()} == set(MAC_MUTANTS)
    [(replaced, listed)] = _control(_case("dv/cocotb-crc")).mutants.items()
    assert [Path(m).name for m in listed] == CRC_MUTANTS and Path(replaced).name == "crc8_block.v"
    # The cocotb case judges the CRC engine's mutants of dv/random-crc: one folder, two seats.
    assert listed == _control(_case("dv/random-crc")).mutants[replaced]
    assert {f.name for f in (REPO / CRC / "mutants").iterdir()} == set(CRC_MUTANTS)


def test_the_cocotb_reference_is_python_the_cocotb_gate_can_name():
    case = _case("dv/cocotb-crc")
    [ref] = case.reference
    assert ref.path.endswith(".py") and ref.entry == "crc8_block"
    control = _control(case)
    assert control.params == {"backend": "cocotb"} and control.seat_files == {"cocotb": ("testbench",)}


# --- The scoreboard case ----------------------------------------------------------------------------


@needs(*GATE_TOOLS)
def test_the_reference_testbench_passes_and_fails_every_mac_mutant_on_a_check(nirmaan_org, fixed_clock, tmp_path):
    """Each mutant fails a check of the scoreboard (a "checks failed" verdict), never a build."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/scoreboard-mac", len(MAC_MUTANTS))
    for run in score.failed_runs:
        assert runs[run].tool == "simulator.run" and "checks failed" in runs[run].summary, runs[run].summary


def _scoreboard_tb(edit) -> str:
    text = _text(f"{MAC}/mac8_tb.sv")
    edited = edit(text)
    assert edited != text
    return edited


@needs(*GATE_TOOLS)
def test_a_scoreboard_that_never_saturates_lets_the_wrapping_mutant_survive(nirmaan_org, fixed_clock, tmp_path):
    """The model and the scoreboard are all there, but the largest operands are never offered in a row."""
    def edit(text):
        text = text.replace("8'hFF, 8'hFF", "8'h01, 8'h01")
        return text.replace("sat_edges < 40 || clr_sat < 1 || ", "")
    files = [("mac8_tb.sv", "testbench", _scoreboard_tb(edit), "mac8_tb")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/scoreboard-mac", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith(f"mutant {MAC}/mutants/mac8_no_saturate.v survived: simulator.run"), score.summary


@needs(*GATE_TOOLS)
def test_a_scoreboard_that_checks_only_the_total_lets_the_flag_mutants_survive(nirmaan_org, fixed_clock, tmp_path):
    """The scoreboard compares `acc` and never `sat`: wrapping is caught by the total, the flag mutants are not."""
    def edit(text):
        return text.replace("if (acc !== m_acc || sat !== m_sat) begin", "if (acc !== m_acc) begin")
    files = [("mac8_tb.sv", "testbench", _scoreboard_tb(edit), "mac8_tb")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/scoreboard-mac", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    survivor = _control(case).mutants[f"{MAC}/mac8.v"][3]  # flag_not_sticky: only the flag shows it
    assert score.summary.startswith(f"mutant {survivor} survived: simulator.run"), score.summary
    assert len(score.failed_runs) == 3  # the scorer stops at the first survivor


def test_the_reference_scoreboard_fails_itself_when_its_run_is_too_thin():
    text = _text(f"{MAC}/mac8_tb.sv")
    assert "run too thin" in text and "sat_edges < 40" in text and "clr_en < 20" in text


# --- The cocotb case --------------------------------------------------------------------------------


@needs(*COCOTB, modules=("cocotb",))
def test_the_reference_tests_pass_and_fail_every_crc_mutant_on_a_failed_test(nirmaan_org, fixed_clock, tmp_path):
    """Each mutant fails a Python test (cocotb's verdict), never a build."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/cocotb-crc", len(CRC_MUTANTS))
    for run in score.failed_runs:
        assert runs[run].tool == "simulator.run" and runs[run].summary.startswith("cocotb: "), runs[run].summary
        assert "failed" in runs[run].summary and "build" not in runs[run].summary.lower(), runs[run].summary


def _reference_crc(message: bytes) -> int:
    state = 0xFF
    for byte in message:
        state ^= byte
        for _ in range(8):
            state = ((state << 1) ^ 0x07) & 0xFF if state & 0x80 else (state << 1) & 0xFF
    return state ^ 0xFF


#: Python tests that pass the gate and the approved RTL: one fixed message with valid held high, one check value.
WEAK_TESTS = '''\
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge


@cocotb.test()
async def one_message(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.init.value = 0
    dut.valid.value = 0
    dut.data.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.valid.value = 1
    for byte in MESSAGE:
        dut.data.value = byte
        await RisingEdge(dut.clk)
    dut.valid.value = 0
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.crc.value) == EXPECTED, f"crc 0x{int(dut.crc.value):02x}"
'''


@needs(*COCOTB, modules=("cocotb",))
def test_fixed_message_tests_pass_their_gate_and_let_the_reload_mutant_survive(nirmaan_org, fixed_clock, tmp_path):
    """Valid is high for the whole message and init never meets a byte: the first three checks are all it has."""
    message = b"123456789"
    source = f"MESSAGE = {list(message)!r}\nEXPECTED = {_reference_crc(message)}\n\n" + WEAK_TESTS
    files = [("weak_crc_cocotb.py", "testbench", source, "crc8_block")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/cocotb-crc", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    survivor = _control(case).mutants[f"{CRC}/crc8_block.v"][3]  # init_loses: the first three catch only 3
    assert score.summary.startswith(f"mutant {survivor} survived: simulator.run"), score.summary
    assert len(score.failed_runs) == 3


@needs(*COCOTB, modules=("cocotb",))
def test_python_tests_that_assert_nothing_let_the_first_mutant_survive(nirmaan_org, fixed_clock, tmp_path):
    """cocotb passes a test that raises nothing, so the gate passes it and the control does not."""
    source = WEAK_TESTS.split("    assert int(dut.crc.value)")[0].replace("for byte in MESSAGE:", "for byte in (0x31,):")
    files = [("weak_crc_cocotb.py", "testbench", source, "crc8_block")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/cocotb-crc", files)
    assert result.submitted, result.detail
    [score] = result.scores
    first = _control(case).mutants[f"{CRC}/crc8_block.v"][0]
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith(f"mutant {first} survived: simulator.run"), score.summary
