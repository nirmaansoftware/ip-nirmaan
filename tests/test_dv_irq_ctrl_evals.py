"""The interrupt controller verification eval cases (wave 2, W2-E1).

Two cases judge verification seats of M68's block-verification workflow on one
approved block, the interrupt controller in ``tests/fixtures/dv/irq_ctrl/``:

* ``dv/directed-irq-ctrl`` judges the testbench seat (``directed_testing``,
  ``systemverilog``): the seat's testbench must pass the approved RTL and fail
  each of five RTL mutants.
* ``dv/plan-irq-ctrl`` judges the dv-plan seat (``verification_planning``): the
  seat's plan must pass ``vplan.check`` against the approved specification and
  fail against two specification mutants (a requirement added, one changed).

Each request plans block-verification and its seat's packet, for the owner and
the reviewer, carries every skill the case judges. Real-tool tests need the
simulators (``laws.needs``).
"""

from __future__ import annotations

import json
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
IRQ = "tests/fixtures/dv/irq_ctrl"
RTL = f"{IRQ}/irq_ctrl.v"
SPEC = f"{IRQ}/interface_spec.md"

#: Each case: its seat, the seat task's skills, owner and reviewer (docs/BLOCK_VERIFICATION.md).
CASES = {
    "dv/directed-irq-ctrl": ("testbench", ("directed_testing", "systemverilog"),
                             "verification.simulation.systemverilog.senior", "verification.simulation.tech_lead"),
    "dv/plan-irq-ctrl": ("dv-plan", ("verification_planning",),
                         "verification.planning.engineer", "verification.planning.senior"),
}

#: The RTL mutants the directed case's control lists, each with a check of the reference testbench it fails.
RTL_MUTANTS = {
    "irq_ctrl_priority_inverted.v": "source 0 first: irq_id",
    "irq_ctrl_ack_ignored.v": "level cleared once low",
    "irq_ctrl_level_mask_ignored.v": "level source disabled: irq",
    "irq_ctrl_clear_beats_set.v": "level held through its clear",
    "irq_ctrl_w1c_clears_all.v": "one bit cleared",
}

#: The specification mutants the plan case's control lists, each with the problem vplan.check reports.
SPEC_MUTANTS = {
    "interface_spec_added_req.md": "requirement IRQ-RECLAIM is not in the plan",
    "interface_spec_priority_changed.md": "IRQ-PRIORITY does not quote interface_spec.md",
}


def _case(case_id):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _control(case):
    [control] = [c for c in case.held_out if c.scorer == "must-fail"]
    return control


# --- Planning and packets ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_case_plans_block_verification_and_its_seat_carries_the_judged_skills(case_id, nirmaan_org,
                                                                                 fixed_clock):
    case = _case(case_id)
    seat, skills, owner, reviewer = CASES[case_id]
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
    # The case fixes the seat's upstream stages from its own files.
    assert set(case.upstream) <= {engine.task(d).stage for d in task.depends_on}


def test_every_mutant_in_the_folder_is_listed_by_its_case():
    folder = REPO / IRQ / "mutants"
    rtl = {Path(m).name for m in _control(_case("dv/directed-irq-ctrl")).mutants[RTL]}
    spec = {Path(m).name for m in _control(_case("dv/plan-irq-ctrl")).mutants[SPEC]}
    assert rtl == set(RTL_MUTANTS) and spec == set(SPEC_MUTANTS)
    assert {f.name for f in folder.iterdir()} == rtl | spec


# --- The directed testbench case --------------------------------------------------------------------


@needs(*GATE_TOOLS)
def test_the_reference_testbench_passes_and_fails_every_rtl_mutant_on_a_check(nirmaan_org, fixed_clock, tmp_path):
    """Each mutant fails a check of the testbench (a "checks failed" verdict), never a build."""
    case = _case("dv/directed-irq-ctrl")
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert len(score.failed_runs) == len(RTL_MUTANTS)
    runs = {j.run: j for j in trial.judge_runs}
    for run in score.failed_runs:
        assert runs[run].tool == "simulator.run" and "checks failed" in runs[run].summary, runs[run].summary


#: A testbench that passes its own gate and checks reset values and one register, and nothing else.
WEAK_TB = """\
`timescale 1ns / 1ps
module weak_irq_tb;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic we = 1'b0;
    logic [1:0] addr = 2'd0;
    logic [31:0] wdata = 32'd0;
    logic [31:0] rdata;
    logic irq;
    logic [4:0] irq_id;
    int errors = 0;
    logic [8*64-1:0] nonce;
    always #5 clk = ~clk;
    irq_ctrl dut (.clk(clk), .rst_n(rst_n), .src(8'd0), .we(we), .addr(addr), .wdata(wdata),
                  .rdata(rdata), .irq(irq), .irq_id(irq_id));
    initial begin
        repeat (2) @(posedge clk);
        #1 rst_n = 1'b1;
        we = 1'b1; wdata = 32'h0000_00FF;
        @(posedge clk);
        #1 we = 1'b0;
        if (rdata !== 32'h0000_00FF) errors++;
        if (irq !== 1'b0) errors++;
        if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, 2 - errors, errors);
        $finish;
    end
endmodule
"""


@needs(*GATE_TOOLS)
def test_a_testbench_that_never_raises_a_source_fails_the_control(nirmaan_org, fixed_clock, tmp_path):
    """The weak testbench passes the gate and the approved RTL; the first mutant it cannot see survives."""
    case = _case("dv/directed-irq-ctrl")
    llm = ReplayLLM([("weak_irq_tb.sv", "testbench", WEAK_TB, "weak_irq_tb")])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    first = _control(case).mutants[RTL][0]
    assert score.summary.startswith(f"mutant {first} survived: simulator.run"), score.summary


# --- The verification plan case ---------------------------------------------------------------------


def test_the_reference_plan_passes_and_fails_every_specification_mutant(nirmaan_org, fixed_clock, tmp_path):
    case = _case("dv/plan-irq-ctrl")
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    runs = {j.run: j for j in trial.judge_runs}
    summaries = [runs[r].summary for r in score.failed_runs]
    assert len(summaries) == len(SPEC_MUTANTS)
    for summary, problem in zip(summaries, SPEC_MUTANTS.values()):
        assert problem in summary, summary


def test_a_plan_missing_a_requirement_is_refused_before_review(nirmaan_org, fixed_clock, tmp_path):
    """The dv-plan gate: a plan that drops the same-edge race never reaches review, so it is never judged."""
    case = _case("dv/plan-irq-ctrl")
    plan = json.loads((REPO / IRQ / "irq_ctrl_vplan.json").read_text(encoding="utf-8"))
    plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "IRQ-SET-WINS"]
    for item in plan["items"]:
        item["proves"] = [p for p in item["proves"] if p != "IRQ-SET-WINS"]
    plan["items"] = [i for i in plan["items"] if i["proves"]]
    llm = ReplayLLM([("irq_ctrl_vplan.json", "verification_plan", json.dumps(plan, indent=2) + "\n", None)])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted and not result.passed
    assert "IRQ-SET-WINS is not in the plan" in result.detail, result.detail
