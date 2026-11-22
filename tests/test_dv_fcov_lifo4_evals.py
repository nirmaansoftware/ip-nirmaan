"""The functional coverage eval case (RX-E4, wave 2 close).

``dv/fcov-lifo4`` judges the coverage-closure seat of the signoff-preparation workflow, the stage that plans
``functional_coverage`` for its seat (and requires a ``coverage.read`` run as its evidence). The seat writes a
functional coverage model of one approved block, ``lifo4`` (a four-entry stack), from the approved requirement
matrix, and delivers it as the coverage report. A testbench the seat never sees drives the block and reads what
the model reports: the model must report no hole when the stimulus drives every scenario the matrix names, and
a hole for each of six stimuli that skip one scenario.

``coverage.read`` measures code coverage only; this case does not judge a percentage. The judge runs the tool
because the stage's evidence names it, and it passes or fails on the simulation verdict, as the knowledge
document says a functional claim must be checked (a self-checking test that tallies each scenario).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from laws import needs

from nirmaan.evals import load_cases, validate_case
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.evals.scorers import ScoreContext, scorer_spec
from nirmaan.models import Actor, ActorKind, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, ToolBroker, ToolHandle, assemble

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
LIFO = "tests/fixtures/dv/lifo4"
FIXTURE = REPO / LIFO
CASE = "dv/fcov-lifo4"
SEAT = "coverage-closure"
COVERAGE_TOOLS = ("verilator", "verilator_coverage")

#: The stimulus mutants of the control, in the order it runs them, each with the scenario it takes out.
MUTANTS = {
    "lifo4_fcov_tb_no_underflow.sv": "scn_underflow",
    "lifo4_fcov_tb_no_both_empty.sv": "scn_both_empty",
    "lifo4_fcov_tb_no_overflow.sv": "scn_overflow",
    "lifo4_fcov_tb_no_both_full.sv": "scn_both_full",
    "lifo4_fcov_tb_no_both_mid.sv": "scn_both_mid",
    "lifo4_fcov_tb_no_reset_busy.sv": "scn_reset_busy",
}
#: A bin of the reference model that a model can make true by construction, and the mutant that bin alone sees.
BINS = {
    "x[3]": "lifo4_fcov_tb_no_underflow.sv",
    "x[6]": "lifo4_fcov_tb_no_both_empty.sv",
    "x[2]": "lifo4_fcov_tb_no_overflow.sv",
    "x[8]": "lifo4_fcov_tb_no_both_full.sv",
    "x[7]": "lifo4_fcov_tb_no_both_mid.sv",
    "rst_busy": "lifo4_fcov_tb_no_reset_busy.sv",
}
MODEL = FIXTURE / "fcov" / "lifo4_fcov_model.sv"


def _case():
    return next(c for c in load_cases(EVALS) if c.id == CASE)


def _control():
    [control] = _case().held_out
    return control


# --- Planning, packets and the files -------------------------------------------------------------------


def test_the_case_plans_signoff_preparation_and_its_seat_carries_the_judged_skill(nirmaan_org, fixed_clock):
    case = _case()
    assert validate_case(nirmaan_org, case, REPO) == []
    assert case.seat == SEAT and case.skills == ("functional_coverage",)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    assert engine.state.project.analysis.intent == "signoff_preparation"
    [task] = [t for t in engine.state.tasks.values() if t.stage == SEAT]
    assert task.workflow == "signoff-preparation" and task.skills == ("functional_coverage",)
    assert task.expected_outputs == ("coverage_report",)
    # The stage's own evidence names a coverage.read run: the control's tool is the one the stage asks for.
    assert any("coverage.read" in r.tools for r in task.evidence_requirements)
    assert _control().tool == "coverage.read"
    for role in (task.owner, task.reviewer):
        packet = assemble(engine, task.id, role=role)
        assert "functional_coverage" in {s.id for s in packet.domain.skills}, role
        assert packet.domain.declines is None
    assert {engine.task(d).stage for d in task.depends_on} == set(case.upstream) == {"plan-audit"}


def test_the_mutants_in_the_folder_are_the_ones_listed_and_each_takes_one_scenario_out():
    control = _control()
    [(original, mutants)] = control.mutants.items()
    assert [Path(m).name for m in mutants] == list(MUTANTS)
    assert {f.name for f in (FIXTURE / "mutants").iterdir()} == set(MUTANTS)
    clean = (REPO / original).read_text(encoding="utf-8")
    for name, scenario in MUTANTS.items():
        text = (FIXTURE / "mutants" / name).read_text(encoding="utf-8")
        body = text.split("\n", 2)[2]  # the two comment lines the mutant starts with
        assert body == clean.replace(f"        {scenario};\n", ""), name
        assert clean.count(f"        {scenario};\n") == 1


def test_the_matrix_and_the_model_agree_on_the_ports_and_the_fifteen_bins():
    matrix = (FIXTURE / "traceability_matrix.md").read_text(encoding="utf-8")
    model = MODEL.read_text(encoding="utf-8")
    ports = matrix.split("```\n")[1]
    assert ports.startswith("module lifo4_fcov (")
    for name in ("clk", "rst_n", "push", "pop", "din", "dout", "count", "empty", "full", "err", "planned", "holes"):
        assert name in ports and name in model
    assert "Fifteen scenarios in all" in matrix and "assign planned = 15;" in model
    spec = (FIXTURE / "interface_spec.md").read_text(encoding="utf-8")
    import re

    tagged = re.findall(r"\[req:([A-Z0-9-]+)\]", spec)
    assert len(tagged) == len(set(tagged)) == 7
    assert all(f"| {r} |" in matrix for r in tagged)


def test_the_case_gives_the_seat_the_matrix_only_and_the_reference_is_one_coverage_report():
    case = _case()
    assert [f.path for f in case.upstream["plan-audit"]] == [f"{LIFO}/traceability_matrix.md"]
    assert [(f.path, f.kind) for f in case.reference] == [(f"{LIFO}/fcov/lifo4_fcov_model.sv", "coverage_report")]
    # The stimulus and the block are held out: no document the seat is given names them or their files.
    text = (FIXTURE / "traceability_matrix.md").read_text(encoding="utf-8")
    assert "scn_" not in text and "lifo4_fcov_tb" not in text and "lifo4.v" not in text


# --- The control, for real -----------------------------------------------------------------------------


@needs(*COVERAGE_TOOLS)
def test_the_reference_model_passes_the_clean_stimulus_and_fails_every_mutant(nirmaan_org, fixed_clock, tmp_path):
    case = _case()
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert trial.result.passed, trial.result.detail
    [score] = trial.result.scores
    assert "6 of 6 mutants failed it" in score.summary, score.summary
    runs = {j.run: j for j in trial.judge_runs}
    assert [runs[r].tool for r in score.runs] == ["coverage.read"]
    assert runs[score.runs[0]].succeeded and "coverage read over" in runs[score.runs[0]].summary
    assert len(score.failed_runs) == len(MUTANTS)
    for run in score.failed_runs:  # a mutant fails on a hole the model reports, so its coverage is never read
        assert "coverage not read: simulation failed" in runs[run].summary, runs[run].summary


def _judge(nirmaan_org, fixed_clock, tmp_path, model_text: str):
    """The case's check, run by the scorer on a model that never went through a seat."""
    case = _case()
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    [seat] = [t for t in engine.state.tasks.values() if t.stage == SEAT]
    tools = ToolHandle(ToolBroker(engine), Actor(role=str(seat.owner), kind=ActorKind.SYSTEM, name="scorer"), seat.id)
    model = tmp_path / "lifo4_fcov.sv"
    model.write_text(model_text, encoding="utf-8")
    state = SimpleNamespace(artifacts={"a": SimpleNamespace(kind="coverage_report", location=str(model))},
                            tool_runs={})
    ctx = ScoreContext(SimpleNamespace(state=state), SimpleNamespace(id=seat.id, artifacts=["a"]), _control(), REPO,
                       tools, tmp_path / "check-1")
    return scorer_spec("must-fail").fn(ctx)


@needs(*COVERAGE_TOOLS)
def test_the_reference_model_text_passes_the_scorer(nirmaan_org, fixed_clock, tmp_path):
    score = _judge(nirmaan_org, fixed_clock, tmp_path, MODEL.read_text(encoding="utf-8"))
    assert score.status is ScoreStatus.PASSED, score.summary
    assert "6 of 6 mutants failed it" in score.summary


@needs(*COVERAGE_TOOLS)
def test_a_model_that_never_reports_a_hole_survives_the_first_mutant(nirmaan_org, fixed_clock, tmp_path):
    text = MODEL.read_text(encoding="utf-8")
    line = "    assign holes = 15 - ones({rst_busy, lv, x});\n"
    assert text.count(line) == 1
    score = _judge(nirmaan_org, fixed_clock, tmp_path, text.replace(line, "    assign holes = 0;\n"))
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith(f"mutant {LIFO}/mutants/lifo4_fcov_tb_no_underflow.sv survived: coverage.read"), \
        score.summary
    assert len(score.runs) == 1 and score.failed_runs == ()


@needs(*COVERAGE_TOOLS)
@pytest.mark.parametrize("bin_name", sorted(BINS))
def test_a_model_with_one_bin_true_by_construction_survives_exactly_the_mutant_that_bin_alone_sees(
        nirmaan_org, fixed_clock, tmp_path, bin_name):
    """The bin is counted hit from the start: the clean stimulus passes, and the stimulus without its scenario too."""
    text = MODEL.read_text(encoding="utf-8")
    if bin_name == "rst_busy":
        old, new = "logic       rst_busy = 1'b0;", "logic       rst_busy = 1'b1;"
    else:
        index = int(bin_name[2:-1])
        old, new = "logic [8:0] x = 9'd0;", f"logic [8:0] x = 9'd{1 << index};"
    assert text.count(old) == 1
    score = _judge(nirmaan_org, fixed_clock, tmp_path, text.replace(old, new))
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith(f"mutant {LIFO}/mutants/{BINS[bin_name]} survived: coverage.read"), score.summary
    assert len(score.failed_runs) == list(MUTANTS).index(BINS[bin_name])  # every earlier mutant was still caught


@needs(*COVERAGE_TOOLS)
@pytest.mark.parametrize("planned, why", [(16, "a bin no stimulus can hit"), (14, "fewer bins than the matrix names")])
def test_a_model_that_plans_the_wrong_number_of_bins_fails_the_clean_run(nirmaan_org, fixed_clock, tmp_path, planned,
                                                                         why):
    text = MODEL.read_text(encoding="utf-8")
    if planned == 16:
        text = text.replace("assign planned = 15;", "assign planned = 16;").replace("15 - ones(", "16 - ones(")
    else:
        text = text.replace("assign planned = 15;", "assign planned = 14;")
    score = _judge(nirmaan_org, fixed_clock, tmp_path, text)
    assert score.status is ScoreStatus.FAILED, why
    assert score.summary.startswith("the clean inputs do not pass: coverage.read run-"), score.summary
    assert "coverage not read: simulation failed" in score.summary, score.summary
    assert len(score.runs) == 1 and score.failed_runs == ()
