"""The random-stimulus and equivalence eval cases (wave 2, W2-E3).

Two cases judge verification seats of M68's block-verification workflow, each
on an approved block of its own:

* ``dv/random-crc`` (``tests/fixtures/dv/crc8/``) judges the testbench seat on
  ``directed_testing`` and ``constrained_random`` (the ``random_stimulus``
  refinement adds the second): the seat's testbench must pass the approved CRC
  engine and fail each of five RTL mutants, on a failed check.
* ``dv/equiv-gray`` (``tests/fixtures/dv/gray_counter/``) judges the
  ``equivalence`` seat (M69) on ``equivalence_checking``: the seat's eqy setup
  must prove the approved Gray-code counter and its approved refactor
  equivalent, and fail each of three refactors that are not.

Each request plans block-verification and its seat's packet, for the owner and
the reviewer, carries every skill the case judges. Real-tool tests need the
simulators (CRC) or the formal tools with eqy (Gray) (``laws.needs``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS
from test_nirmaan_gates_everywhere import FORMAL_TOOLS

from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.models import ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
CRC = "tests/fixtures/dv/crc8"
GRAY = "tests/fixtures/dv/gray_counter"

#: Each case: its fixture folder, seat, the seat task's skills, owner and reviewer (docs/BLOCK_VERIFICATION.md).
CASES = {
    "dv/random-crc": (CRC, "testbench", ("directed_testing", "constrained_random"),
                      "verification.dynamic.testbench.testing.senior", "verification.dynamic.testbench.tech_lead"),
    "dv/equiv-gray": (GRAY, "equivalence", ("equivalence_checking",),
                      "verification.formal.equivalence.engineer", "verification.formal.proof.model_checking.senior"),
}

#: Each mutant of a case's control, with the judge that catches it.
CRC_MUTANTS = {
    "crc8_block_poly_tap.v": "the polynomial lacks its x^2 tap (0x03)",
    "crc8_block_reflected_input.v": "each byte is taken bit 0 first",
    "crc8_block_no_final_xor.v": "the check value is not inverted",
    "crc8_block_init_loses.v": "a byte offered with init wins over the reload",
    "crc8_block_hold_ignored.v": "valid is ignored: a byte is taken at every edge",
}
GRAY_MUTANTS = {
    "gray_counter_refactor_flip_wrong_bit.v": "the wrong bit flips after an odd code ending in 1",
    "gray_counter_refactor_wrap_off_by_one.v": "wrap is high at count 14, not 15",
    "gray_counter_refactor_reset_to_one.v": "reset loads 0001, not 0000",
}
MUTANTS = {"dv/random-crc": CRC_MUTANTS, "dv/equiv-gray": GRAY_MUTANTS}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _control(case):
    [control] = [c for c in case.held_out if c.scorer == "must-fail"]
    return control


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def _trial(nirmaan_org, fixed_clock, tmp_path, case_id):
    case = _case(case_id)
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert len(score.failed_runs) == len(MUTANTS[case_id])
    return {j.run: j for j in trial.judge_runs}, score


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                 fixed_clock):
    case = _case(case_id)
    _, seat, skills, owner, reviewer = CASES[case_id]
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == seat and set(case.skills) == set(skills)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "block_verification"
    [task] = [t for t in engine.state.tasks.values() if t.stage == seat]
    assert task.workflow == "block-verification"
    assert (task.skills, task.owner, task.reviewer) == (skills, owner, reviewer)
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, (case_id, role)
        assert packet.domain.declines is None
    # The case fixes the seat's upstream stages from its own files (the equivalence stage reads only the RTL).
    assert set(case.upstream) <= {t.stage for t in engine.state.tasks.values()}
    assert "design-under-test" in {engine.task(d).stage for d in task.depends_on}


def test_the_refinement_words_are_what_plan_the_seats_skills_and_stage(nirmaan_org, fixed_clock):
    """"constrained-random" adds constrained_random to the testbench; "equivalence" plans the equivalence stage."""
    crc = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case("dv/random-crc").request)
    assert "random_stimulus" in crc.state.project.analysis.features
    assert "equivalence" not in {t.stage for t in crc.state.tasks.values()}
    gray = Orchestrator(nirmaan_org, clock=fixed_clock).plan(_case("dv/equiv-gray").request)
    assert "equivalence" in gray.state.project.analysis.features


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_mutant_in_the_folder_is_listed_by_its_case(case_id):
    folder, *_ = CASES[case_id]
    [(replaced, listed)] = _control(_case(case_id)).mutants.items()
    assert [Path(m).name for m in listed] == list(MUTANTS[case_id])
    assert Path(replaced).name == ("crc8_block.v" if case_id == "dv/random-crc" else "gray_counter_refactor.v")
    assert {f.name for f in (REPO / folder / "mutants").iterdir()} == set(MUTANTS[case_id])


# --- The random CRC case ----------------------------------------------------------------------------


@needs(*GATE_TOOLS)
def test_the_reference_testbench_passes_and_fails_every_crc_mutant_on_a_check(nirmaan_org, fixed_clock, tmp_path):
    """Each mutant fails a check of the testbench (a "checks failed" verdict), never a build."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/random-crc")
    for run in score.failed_runs:
        assert runs[run].tool == "simulator.run" and "checks failed" in runs[run].summary, runs[run].summary


def _weak_run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM(list(files))
    return case, run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                          sandbox=tmp_path / "sandbox", clock=fixed_clock)


#: A testbench that passes its own gate: one fixed message with valid held high, and one check value.
WEAK_TB = """\
`timescale 1ns / 1ps
module weak_crc_tb;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic init = 1'b0;
    logic valid = 1'b0;
    logic [7:0] data = 8'd0;
    wire  [7:0] crc;
    int errors = 0;
    logic [8*64-1:0] nonce;
    always #5 clk = ~clk;
    crc8_block dut (.clk(clk), .rst_n(rst_n), .init(init), .valid(valid), .data(data), .crc(crc));
    initial begin
        repeat (2) @(posedge clk);
        #1 rst_n = 1'b1;
        valid = 1'b1;
        foreach_byte();
        @(posedge clk);
        #1 valid = 1'b0;
        if (crc !== 8'hXX) errors++;
        if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, 1 - errors, errors);
        $finish;
    end
endmodule
"""


def _reference_crc(message: bytes) -> int:
    state = 0xFF
    for byte in message:
        state ^= byte
        for _ in range(8):
            state = ((state << 1) ^ 0x07) & 0xFF if state & 0x80 else (state << 1) & 0xFF
    return state ^ 0xFF


def _directed_tb() -> str:
    """The weak testbench: the bytes of one message in a row (valid held high), then one comparison."""
    message = b"123456789"
    drive = "".join(f"        data = 8'h{b:02X}; @(posedge clk); #1;\n" for b in message)
    expected = f"8'h{_reference_crc(message):02X}"
    return (WEAK_TB.replace("        foreach_byte();\n        @(posedge clk);\n", drive)
            .replace("8'hXX", expected))


@needs(*GATE_TOOLS)
def test_a_fixed_message_testbench_passes_its_gate_and_lets_the_valid_and_reload_mutants_survive(
        nirmaan_org, fixed_clock, tmp_path):
    """Valid is never low and init never meets a byte, so the first two checks of the specification are all it has."""
    files = [("weak_crc_tb.sv", "testbench", _directed_tb(), "weak_crc_tb")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/random-crc", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    first_survivor = _control(case).mutants[f"{CRC}/crc8_block.v"][3]  # init_loses: the first two catch only 3
    assert score.summary.startswith(f"mutant {first_survivor} survived: simulator.run"), score.summary
    assert len(score.failed_runs) == 3  # the polynomial, the byte order and the final inversion; it stops at the first survivor


def _constrained_tb(edit) -> str:
    text = _text(f"{CRC}/crc8_block_tb.sv")
    edited = edit(text)
    assert edited != text
    return edited


@needs(*GATE_TOOLS)
def test_a_random_testbench_whose_constraints_never_meet_init_with_valid_lets_the_reload_mutant_survive(
        nirmaan_org, fixed_clock, tmp_path):
    """Random is not enough: the constraint "init only with valid low" keeps the corner out of reach."""
    def edit(text):
        text = text.replace("            if (i && v) both_cycles++;\n", "            if (i) v = 1'b0;\n")
        return text.replace("both_cycles < 20 || ", "")
    files = [("crc8_block_tb.sv", "testbench", _constrained_tb(edit), "crc8_block_tb")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/random-crc", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith(f"mutant {CRC}/mutants/crc8_block_init_loses.v survived: simulator.run"), \
        score.summary
    assert len(score.failed_runs) == 3  # the scorer stops at the first survivor


@needs(*GATE_TOOLS)
def test_a_random_testbench_that_is_too_short_lets_the_mutants_it_never_reaches_survive(nirmaan_org, fixed_clock,
                                                                                       tmp_path):
    """The same checks over 12 random cycles (its own thinness check removed) pass the gate and miss the corners."""
    def edit(text):
        text = text.replace("repeat (6000)", "repeat (12)")
        start = text.index("        if (checks < 6000")
        end = text.index("        if (errors == 0)")
        return text[:start] + text[end:]
    files = [("crc8_block_tb.sv", "testbench", _constrained_tb(edit), "crc8_block_tb")]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/random-crc", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert "survived: simulator.run" in score.summary, score.summary


def test_the_reference_testbench_fails_itself_when_its_random_run_is_too_thin():
    """The reference carries its own guard: it counts the corners it reached and fails below a floor."""
    text = _text(f"{CRC}/crc8_block_tb.sv")
    assert "random run too thin" in text and "both_cycles < 20" in text


# --- The equivalence case ---------------------------------------------------------------------------


@needs(*FORMAL_TOOLS, "eqy", "make")
def test_the_reference_setup_passes_the_refactor_and_fails_every_mutant_on_a_partition(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    """Each mutant is run by eqy and fails to prove a partition; none is a refusal or a build error."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/equiv-gray")
    for run in score.failed_runs:
        summary = runs[run].summary
        assert runs[run].tool == "equivalence.run" and summary.startswith("eqy: "), summary
        assert "partitions not equivalent" in summary or "not equivalent" in summary, summary
