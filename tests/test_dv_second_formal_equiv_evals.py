"""The second formal case and the second equivalence case (RX-E1).

Two cases add independent evidence on skills that rested on one case each, each
on an approved block of its own (neither block is held out by another case):

* ``dv/formal-rr-arbiter`` (``tests/fixtures/dv/rr_arbiter/``) judges
  ``formal_verification``, ``sva`` and ``assertion_coverage`` a second time, on
  a round-robin arbiter whose state is a pointer: the seat's proof must pass the
  approved RTL with every cover reached and fail each of four RTL mutants on an
  assertion. Properties of one cycle (one hot, only requesters, a grant when
  someone asks) let the fixed-priority mutant survive.
* ``dv/equiv-updown`` (``tests/fixtures/dv/updown_counter/``) judges
  ``equivalence_checking`` a second time, on an up/down counter with a load and
  its adder-free refactor: the seat's eqy setup must prove the approved pair
  equivalent and fail each of three refactors that are not.

Each request plans block-verification and its seat's packet, for the owner and
the reviewer, carries every skill the case judges. Real-tool tests need the
formal tools (``laws.needs``).
"""

from __future__ import annotations

import re
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
ARB = "tests/fixtures/dv/rr_arbiter"
UPDOWN = "tests/fixtures/dv/updown_counter"

#: Each case: its fixture folder, seat, the seat task's skills, owner and reviewer (docs/BLOCK_VERIFICATION.md),
#: the file the control replaces and the other case on the same skills.
CASES = {
    "dv/formal-rr-arbiter": (ARB, "assertions-formal", ("formal_verification", "sva", "assertion_coverage"),
                             "verification.formal.proof.property.senior",
                             "verification.formal.proof.model_checking.senior", "rr_arbiter.v",
                             "dv/formal-credit-counter"),
    "dv/equiv-updown": (UPDOWN, "equivalence", ("equivalence_checking",),
                        "verification.formal.equivalence.engineer",
                        "verification.formal.proof.model_checking.senior", "updown_counter_refactor.v",
                        "dv/equiv-gray"),
}

ARB_MUTANTS = {
    "rr_arbiter_fixed_priority.v": "the pointer is never updated, so requester 0 always wins",
    "rr_arbiter_skip_rotation.v": "the pointer takes the index after the granted requester",
    "rr_arbiter_idle_resets_pointer.v": "an idle edge loads the reset pointer",
    "rr_arbiter_reset_pointer.v": "reset loads 0, not 2",
}
UPDOWN_MUTANTS = {
    "updown_counter_refactor_down_chain.v": "counting down toggles along the up chain",
    "updown_counter_refactor_load_after_count.v": "an enabled count wins over a load",
    "updown_counter_refactor_borrow_at_one.v": "borrow is high at count 1, not 0",
}
MUTANTS = {"dv/formal-rr-arbiter": ARB_MUTANTS, "dv/equiv-updown": UPDOWN_MUTANTS}


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


def _weak_run(nirmaan_org, fixed_clock, tmp_path, case_id, files):
    case = _case(case_id)
    llm = ReplayLLM([(name, kind, text, None) for name, kind, text in files])
    return case, run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                          sandbox=tmp_path / "sandbox", clock=fixed_clock)


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                 fixed_clock):
    case = _case(case_id)
    _, seat, skills, owner, reviewer, *_ = CASES[case_id]
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
    assert set(case.upstream) <= {t.stage for t in engine.state.tasks.values()}
    assert "design-under-test" in {engine.task(d).stage for d in task.depends_on}


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_is_a_second_case_on_a_block_no_other_case_uses(case_id):
    """Independent evidence: same skills as the first case, a different block, and no shared reference RTL."""
    folder, *_, other = CASES[case_id]
    case, first = _case(case_id), _case(other)
    assert case.skills == first.skills and case.seat == first.seat
    assert not any(p.startswith(folder) for p in json_paths(first))
    used = json_paths(case)
    for other_case in load_cases(EVALS):
        if other_case.id != case_id:
            assert not any(p.startswith(folder) for p in json_paths(other_case)), other_case.id
    assert used and all(p.startswith(folder) for p in used)


def json_paths(case) -> set[str]:
    """Every fixture path the case names: upstream files, reference, case files and the control's mutants."""
    paths = {i.path for items in case.upstream.values() for i in items} | {r.path for r in case.reference}
    for control in case.held_out:
        for group in (control.case_files or {}).values():
            paths.update(group)
        for replaced, listed in (control.mutants or {}).items():
            paths.add(replaced)
            paths.update(listed)
    return paths


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_mutant_in_the_folder_is_listed_by_its_case(case_id):
    folder, *_, replaced, _ = CASES[case_id]
    [(path, listed)] = _control(_case(case_id)).mutants.items()
    assert [Path(m).name for m in listed] == list(MUTANTS[case_id])
    assert Path(path).name == replaced
    assert {f.name for f in (REPO / folder / "mutants").iterdir()} == set(MUTANTS[case_id])


def test_the_specifications_tag_every_requirement_the_reference_properties_cite():
    spec = _text(f"{ARB}/interface_spec.md")
    props = _text(f"{ARB}/rr_arbiter_check.sv")
    tags = set(re.findall(r"\[req:(RR-[A-Z-]+)\]", spec))
    cited = set(re.findall(r"RR-[A-Z]+(?:-[A-Z]+)*", props))
    assert cited and cited <= tags, cited - tags
    assert {"RR-RESET", "RR-PICK", "RR-ROTATE", "RR-YIELD", "RR-BOUND"} <= cited


# --- The formal case --------------------------------------------------------------------------------


@needs(*FORMAL_TOOLS)
def test_the_reference_proof_passes_and_fails_every_arbiter_mutant_on_an_assertion(nirmaan_org, fixed_clock,
                                                                                  tmp_path):
    """Each mutant fails an assertion of the proof, never a build or a refusal."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/formal-rr-arbiter")
    assert "with every cover reached" in score.summary, score.summary
    for run in score.failed_runs:
        summary = runs[run].summary
        assert runs[run].tool == "formal.run" and summary.startswith("symbiyosys: formal fail: "), summary
        assert re.search(r": \[ASSERT\] assertion \S+ failed", summary), summary


#: One cycle only: one hot, only requesters, a grant when someone asks. True and inductive, but no rotation.
WEAK_ARB = """\
`timescale 1ns / 1ps
module rr_arbiter_check (input wire clk, input wire rst_n, input wire [2:0] req);
    wire [2:0] grant;
    wire [1:0] last;
    rr_arbiter dut (.clk(clk), .rst_n(rst_n), .req(req), .grant(grant), .last(last));
    reg past_valid = 1'b0;
    always @(posedge clk)
        past_valid <= 1'b1;
    always @(*)
        if (!past_valid)
            assume (!rst_n);
    always @(*)
        if (past_valid) begin
            assert ((grant & ~req) == 3'b000);
            assert ((grant & (grant - 3'b001)) == 3'b000);
            assert ((req != 3'b000) == (grant != 3'b000));
        end
    always @(posedge clk)
        if (past_valid && rst_n) begin
            cover (req == 3'b111 && grant == 3'b001);
            cover (req == 3'b111 && grant == 3'b010);
            cover (req == 3'b111 && grant == 3'b100);
            cover (req == 3'b000);
        end
endmodule
"""


@needs(*FORMAL_TOOLS)
def test_one_cycle_safety_passes_its_gates_and_lets_the_fixed_priority_mutant_survive(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    files = [("rr_arbiter_check.sv", "assertions", WEAK_ARB),
             ("rr_arbiter_check.sby", "formal_spec", _text(f"{ARB}/rr_arbiter_check.sby"))]
    case, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/formal-rr-arbiter", files)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    first = _control(case).mutants[f"{ARB}/rr_arbiter.v"][0]
    assert score.summary.startswith(f"mutant {first} survived: formal.run"), score.summary


@needs(*FORMAL_TOOLS)
def test_a_proof_that_never_ties_the_pointer_to_its_model_is_not_inductive_and_is_refused(nirmaan_org, fixed_clock,
                                                                                        tmp_path):
    """The reference properties without the pointer check: induction starts from a pointer the model never reaches."""
    reference = _text(f"{ARB}/rr_arbiter_check.sv")
    line = "            assert (last == m_last);                                // RR-RESET, RR-ROTATE, RR-HOLD\n"
    assert line in reference
    files = [("rr_arbiter_check.sv", "assertions", reference.replace(line, "")),
             ("rr_arbiter_check.sby", "formal_spec", _text(f"{ARB}/rr_arbiter_check.sby"))]
    _, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/formal-rr-arbiter", files)
    assert not result.submitted and not result.passed
    assert "formal unknown" in result.detail, result.detail


@needs(*FORMAL_TOOLS)
def test_a_proof_whose_assumption_blocks_the_requests_is_refused_for_its_covers(nirmaan_org, fixed_clock,
                                                                                tmp_path):
    """A vacuous proof: with no requester ever asking, every property holds and no cover is reached."""
    reference = _text(f"{ARB}/rr_arbiter_check.sv")
    marker = "    // The first edge is a reset"
    assert marker in reference
    blocked = reference.replace(marker, "    always @(*)\n        assume (req == 3'b000);\n\n" + marker)
    files = [("rr_arbiter_check.sv", "assertions", blocked),
             ("rr_arbiter_check.sby", "formal_spec", _text(f"{ARB}/rr_arbiter_check.sby"))]
    _, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/formal-rr-arbiter", files)
    assert not result.submitted and not result.passed
    assert "cover" in result.detail.lower(), result.detail


# --- The equivalence case ---------------------------------------------------------------------------


@needs(*FORMAL_TOOLS, "eqy", "make")
def test_the_reference_setup_passes_the_refactor_and_fails_every_mutant_on_a_partition(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    """Each mutant is run by eqy and fails to prove a partition; none is a refusal or a build error."""
    runs, score = _trial(nirmaan_org, fixed_clock, tmp_path, "dv/equiv-updown")
    for run in score.failed_runs:
        summary = runs[run].summary
        assert runs[run].tool == "equivalence.run" and summary.startswith("eqy: "), summary
        assert "not equivalent" in summary, summary


@needs(*FORMAL_TOOLS, "eqy", "make")
def test_a_setup_that_reads_the_original_on_both_sides_is_refused_before_review(nirmaan_org, fixed_clock, tmp_path):
    """Comparing a design with itself proves nothing: the equivalence gate refuses it."""
    eqy = _text(f"{UPDOWN}/updown_counter.eqy").replace("updown_counter_refactor.v", "updown_counter.v")
    assert "updown_counter_refactor" not in eqy
    _, result = _weak_run(nirmaan_org, fixed_clock, tmp_path, "dv/equiv-updown",
                          [("updown_counter.eqy", "equivalence_setup", eqy)])
    assert not result.submitted and not result.passed
    assert result.detail, "the refusal names its reason"


def _eqy_on_updown(tmp_path, gate_file, strategy):
    """Run eqy directly: the approved up/down counter against one refactor file, with this strategy block."""
    import shutil
    import subprocess

    folder = tmp_path / "run"
    folder.mkdir(parents=True)
    shutil.copy(REPO / UPDOWN / "updown_counter.v", folder / "updown_counter.v")
    shutil.copy(gate_file, folder / "gate.v")
    (folder / "s.eqy").write_text(
        "[gold]\nread_verilog -sv updown_counter.v\nprep -top updown_counter\n\n"
        "[gate]\nread_verilog -sv gate.v\nprep -top updown_counter\n\n" + strategy, encoding="utf-8")
    done = subprocess.run(["eqy", "-f", "-d", "out", "s.eqy"], cwd=folder, capture_output=True, text=True,
                          timeout=300, stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout + done.stderr


#: Strategy blocks a seat would plausibly write: the reference setup's depth and shallower ones. Depth is not
#: what separates the two strategies on this block, so the test pins a short and the reference depth for each.
SAT = "[strategy simple]\nuse sat\ndepth {depth}\n"
SBY = "[strategy sby]\nuse sby\nengine smtbmc\ndepth {depth}\n"
DEPTHS = (5, 10)


@needs(*FORMAL_TOOLS, "eqy", "make")
@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("mutant", sorted(UPDOWN_MUTANTS))
def test_a_sat_setup_fails_each_updown_mutant_as_the_sby_setup_does(tmp_path, mutant, depth):
    """What a ``use sat`` setup does to the mutants of ``dv/equiv-updown`` (W2-C meeting 1, decision 3, item 4).

    Unlike ``dv/equiv-gray`` (``tests/test_dv_crc_gray_evals.py``), where ``use sat`` lets the wrong-flip-bit
    mutant survive, here ``use sat`` at depth 5 and at depth 10 reports each of the three mutants not equivalent,
    exactly as ``use sby`` with smtbmc does. So on this case a seat that writes ``use sat`` is still judged on its
    setup by the case's must-fail control and no mutant survives it. If an eqy or Yosys release changes this, the
    test fails and the case's reading is to be revisited."""
    gate = REPO / UPDOWN / "mutants" / mutant
    sat_code, sat_out = _eqy_on_updown(tmp_path / "sat", gate, SAT.format(depth=depth))
    sby_code, sby_out = _eqy_on_updown(tmp_path / "sby", gate, SBY.format(depth=depth))
    assert sby_code != 0 and "DONE (FAIL" in sby_out, sby_out[-800:]
    assert sat_code != 0 and "DONE (FAIL" in sat_out, sat_out[-800:]


@needs(*FORMAL_TOOLS, "eqy", "make")
@pytest.mark.parametrize("depth", DEPTHS)
def test_a_sat_setup_proves_the_approved_refactor_equivalent(tmp_path, depth):
    """The approved pair passes under ``use sat`` too, so the fail above is the mutants' and not the strategy's."""
    code, out = _eqy_on_updown(tmp_path, REPO / UPDOWN / "updown_counter_refactor.v", SAT.format(depth=depth))
    assert code == 0 and "DONE (PASS" in out, out[-800:]
