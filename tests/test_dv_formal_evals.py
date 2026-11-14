"""The formal verification eval cases (wave 2, W2-E2).

Two cases judge the proof seat (``assertions-formal``) of M68's
block-verification workflow, each on an approved block of its own:

* ``dv/formal-credit-counter`` (``tests/fixtures/dv/credit_counter/``) judges
  ``formal_verification``, ``sva`` and ``assertion_coverage``: the seat's proof
  must pass the approved RTL with every cover reached and fail each of four RTL
  mutants. One mutant is wrong only when ``MAX`` is not a power of two, so a
  proof at ``MAX`` 4 alone lets it survive.
* ``dv/prove-deep-counter`` (``tests/fixtures/dv/deep_counter/``) judges
  ``model_checking``: its request asks for an unbounded proof, and each of its
  four mutants goes wrong only 64 or more cycles after reset. A prove-mode
  (k-induction) proof with a 20-cycle unrolling fails each on its induction
  step; a bounded check of that depth passes them all, and the proof gate
  refuses it.

Each request plans block-verification, and the proof seat's packet, for the
owner and the reviewer, carries every skill the case judges. Real-tool tests
need the formal tools (``laws.needs``).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from laws import needs
from test_nirmaan_gates_everywhere import FORMAL_TOOLS

from nirmaan.evals import ReplayLLM, load_cases, run_case, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.models import ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
CREDIT = "tests/fixtures/dv/credit_counter"
DEEP = "tests/fixtures/dv/deep_counter"

FORMAL_SKILLS = ("formal_verification", "sva", "assertion_coverage")
PROPERTY = "verification.formal.proof.property.senior"
MODEL_CHECKING = "verification.formal.proof.model_checking.senior"

#: Each case: its fixture folder, approved RTL, the proof task's skills, owner and reviewer
#: (docs/BLOCK_VERIFICATION.md), and the status a mutant's failed run reports.
CASES = {
    "dv/formal-credit-counter": (CREDIT, f"{CREDIT}/credit_counter.v", FORMAL_SKILLS, PROPERTY, MODEL_CHECKING,
                                 "formal fail"),
    # Basecase passes and induction fails: sby reports UNKNOWN with the failed assertion.
    "dv/prove-deep-counter": (DEEP, f"{DEEP}/deep_counter.v", (*FORMAL_SKILLS, "model_checking"), MODEL_CHECKING,
                              PROPERTY, "formal unknown"),
}

#: The mutants each case's control lists.
MUTANTS = {
    "dv/formal-credit-counter": ["credit_counter_both_takes.v", "credit_counter_underflow_wraps.v",
                                 "credit_counter_err_not_sticky.v", "credit_counter_full_bit_test.v"],
    "dv/prove-deep-counter": ["deep_counter_carry_lost.v", "deep_counter_last_low_bits.v",
                              "deep_counter_wrap_to_one.v", "deep_counter_saturates.v"],
}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _control(case):
    [control] = [c for c in case.held_out if c.scorer == "must-fail"]
    return control


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_proof_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                       fixed_clock):
    case = _case(case_id)
    _, _, skills, owner, reviewer, _ = CASES[case_id]
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == "assertions-formal" and set(case.skills) <= set(skills)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "block_verification"
    [task] = [t for t in engine.state.tasks.values() if t.stage == case.seat]
    assert task.workflow == "block-verification"
    assert (task.skills, task.owner, task.reviewer) == (skills, owner, reviewer)
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert set(case.skills) <= {s.id for s in packet.domain.skills}, (case_id, role)
        assert packet.domain.declines is None
    # The case fixes the seat's upstream stages from its own files.
    assert set(case.upstream) <= {engine.task(d).stage for d in task.depends_on}


def test_only_the_deep_counter_asks_for_an_unbounded_proof():
    """The unbounded_proof feature is what puts model_checking on the proof task."""
    assert "unbounded proof" in _case("dv/prove-deep-counter").request
    assert "unbounded" not in _case("dv/formal-credit-counter").request


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_mutant_in_the_folder_is_listed_by_its_case(case_id):
    folder, rtl, *_ = CASES[case_id]
    listed = [Path(m).name for m in _control(_case(case_id)).mutants[rtl]]
    assert listed == MUTANTS[case_id]
    assert {f.name for f in (REPO / folder / "mutants").iterdir()} == set(listed)


# --- The reference proofs ---------------------------------------------------------------------------


@needs(*FORMAL_TOOLS)
@pytest.mark.parametrize("case_id", sorted(CASES))
def test_the_reference_proof_passes_and_fails_every_mutant_on_an_assertion(case_id, nirmaan_org, fixed_clock,
                                                                          tmp_path):
    """Each mutant fails an assertion of the proof, never a build or a refusal."""
    case = _case(case_id)
    *_, status = CASES[case_id]
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert "with every cover reached" in score.summary, score.summary
    assert len(score.failed_runs) == len(MUTANTS[case_id])
    runs = {j.run: j for j in trial.judge_runs}
    for run in score.failed_runs:
        summary = runs[run].summary
        assert runs[run].tool == "formal.run" and summary.startswith(f"symbiyosys: {status}: "), summary
        assert re.search(r": \[ASSERT\] assertion \S+ failed", summary), summary


# --- Weak property sets -----------------------------------------------------------------------------


def _weak_run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM([(name, kind, text, None) for name, kind, text in files])
    return case, run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                          sandbox=tmp_path / "sandbox", clock=fixed_clock)


@needs(*FORMAL_TOOLS)
def test_a_proof_at_max_4_only_passes_its_gates_and_lets_the_power_of_two_mutant_survive(nirmaan_org, fixed_clock,
                                                                                     tmp_path):
    """The council's rule: prove at each parameter point. MAX 4 is a power of two, so the bit test is right there."""
    reference = _text(f"{CREDIT}/credit_counter_check.sv")
    max5 = "    credit_counter_props #(.MAX(5)) max5 (.clk(clk), .rst_n(rst_n), .take(take), .give(give));\n"
    assert max5 in reference
    files = [("credit_counter_check.sv", "assertions", reference.replace(max5, "")),
             ("credit_counter_check.sby", "formal_spec", _text(f"{CREDIT}/credit_counter_check.sby"))]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/formal-credit-counter", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith(f"mutant {CREDIT}/mutants/credit_counter_full_bit_test.v survived: formal.run"), \
        score.summary
    assert len(score.failed_runs) == 3  # the other three fail at MAX 4 too


#: Properties that only bound the count and define the carry: true and inductive, but too weak.
WEAK_DEEP = """\
`timescale 1ns / 1ps
module deep_counter_check (input wire clk, input wire rst_n, input wire en, input wire clr);
    wire [6:0] count;
    wire carry;
    deep_counter #(.LIMIT(99)) dut (.clk(clk), .rst_n(rst_n), .en(en), .clr(clr), .count(count), .carry(carry));
    reg past_valid = 1'b0;
    always @(posedge clk)
        past_valid <= 1'b1;
    always @(*)
        if (!past_valid)
            assume (!rst_n);
    always @(*)
        if (past_valid) begin
            assert (count <= 7'd99);
            assert (carry == (en && !clr && count == 7'd99));
        end
    always @(posedge clk)
        if (past_valid && rst_n)
            cover (count == 7'd15);
endmodule
"""


@needs(*FORMAL_TOOLS)
def test_a_proof_that_only_bounds_the_count_lets_the_lost_carry_survive(nirmaan_org, fixed_clock, tmp_path):
    files = [("deep_counter_check.sv", "assertions", WEAK_DEEP),
             ("deep_counter_check.sby", "formal_spec", _text(f"{DEEP}/deep_counter_check.sby"))]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/prove-deep-counter", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    first = _control(case).mutants[f"{DEEP}/deep_counter.v"][0]
    assert score.summary.startswith(f"mutant {first} survived: formal.run"), score.summary


def _bmc(sby: str) -> str:
    assert "mode prove\n" in sby
    return sby.replace("mode prove\n", "mode bmc\n")


@needs(*FORMAL_TOOLS)
def test_a_bounded_check_of_the_same_depth_misses_every_deep_mutant(tmp_path):
    """Why the case needs an unbounded proof: the reference properties, checked 20 cycles deep, pass every mutant."""
    for name in MUTANTS["dv/prove-deep-counter"]:
        work = tmp_path / name
        work.mkdir()
        shutil.copy(REPO / DEEP / "mutants" / name, work / "deep_counter.v")
        shutil.copy(REPO / DEEP / "deep_counter_check.sv", work / "deep_counter_check.sv")
        (work / "bmc.sby").write_text(_bmc(_text(f"{DEEP}/deep_counter_check.sby")), encoding="utf-8")
        run = subprocess.run(["sby", "-f", "bmc.sby"], cwd=work, capture_output=True, text=True, timeout=300)
        assert run.returncode == 0 and "DONE (PASS" in run.stdout, (name, run.stdout[-2000:])


@needs(*FORMAL_TOOLS)
def test_a_bounded_check_is_refused_before_review(nirmaan_org, fixed_clock, tmp_path):
    """The proof gate asks for at least one property proven; a bmc run proves none, so it is never judged."""
    files = [("deep_counter_check.sv", "assertions", _text(f"{DEEP}/deep_counter_check.sv")),
             ("deep_counter_check.sby", "formal_spec", _bmc(_text(f"{DEEP}/deep_counter_check.sby")))]
    _, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/prove-deep-counter", files)
    assert not result.submitted and not result.passed
    assert "proven 0 is below min_proven 1" in result.detail, result.detail
