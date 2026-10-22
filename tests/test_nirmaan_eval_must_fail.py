"""Milestone 58: eval cases name the skills they judge; a must-fail scorer; evidence records.

A case lists the skills it judges (``EvalCase.skills``), checked against the
skill catalog, and a run record keeps each one's digest (card plus knowledge
document) and the head SHA. The ``must-fail`` scorer is a negative control: the
seat's testbench or the case's assertions pass the clean RTL, reach every
cover, and fail on each mutant. ``load_evidence`` refuses a replay and a trial
with a human attestation. No test calls a model.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from laws import needs
from test_nirmaan_evals import _spec_case
from test_nirmaan_live_eval import spec_claude  # noqa: F401 (a fixture)

from nirmaan.cli import app
from nirmaan.evals import (
    EvalError,
    ReplayLLM,
    load_case,
    load_cases,
    load_evidence,
    load_record,
    record_run,
    register_scorer,
    run_case,
    skill_digest,
    unregister_scorer,
    validate_case,
)
from nirmaan.evals.cases import case_digest
from nirmaan.evals import runner
from nirmaan.evals.records import record_trial
from nirmaan.evals.runner import replay_llm
from nirmaan.evals.scorers import ScoreContext, scorer_spec
from nirmaan.models import Actor, ActorKind, EvidenceKind, HeldOutCheck, Score, ScoreStatus
from nirmaan.runtime import ModelRuntime

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
FIFO = "tests/fixtures/rtl/sync_fifo"
CLEAN = f"{FIFO}/sync_fifo.v"
OVERFLOW = f"{FIFO}/mutants/sync_fifo_overflow.v"
POW2 = f"{FIFO}/mutants/sync_fifo_pow2_wrap.v"
SPEC_CASE = "spec/axi4-lite-interface"

#: A FIFO testbench that checks one thing after reset and never fills the FIFO.
WEAK_FIFO_TB = """\
`timescale 1ns / 1ps
module weak_fifo_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    wire full, empty;
    wire [7:0] rd_data;
    wire [3:0] count;
    always #5 clk = ~clk;
    sync_fifo dut (
        .clk(clk), .rst_n(rst_n), .wr_en(1'b0), .wr_data(8'd0), .full(full),
        .rd_en(1'b0), .rd_data(rd_data), .empty(empty), .count(count)
    );
    reg [8*64-1:0] nonce;
    initial begin
        #20 rst_n = 1'b1;
        #20 if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, empty === 1'b1, empty !== 1'b1);
        $finish;
    end
endmodule
"""


def _testbench_check(name: str = "The seat's testbench fails each mutant", clean: str = CLEAN) -> dict:
    """The seat's own testbench, run on the clean RTL and on each mutant standing in for it."""
    return {"name": name, "scorer": "must-fail", "tool": "simulator.run",
            "seat_files": {"sources": ["testbench"]}, "seat_entries": {"top": ["testbench"]},
            "case_files": {"sources": [clean]}, "mutants": {clean: [OVERFLOW, POW2]}}


def _proof_check(sby: str) -> dict:
    """The fixture's assertions, proven on the clean RTL with every cover reached, and on each mutant."""
    return {"name": f"{sby} fails each mutant", "scorer": "must-fail", "tool": "formal.run",
            "cover_tool": "formal.cover", "case_files": {"sby": [f"{FIFO}/{sby}"], "sources": [CLEAN]},
            "mutants": {CLEAN: [OVERFLOW, POW2]}}


def _fifo_case(tmp_path: Path, held_out: list[dict], case_id: str = "tmp/sync-fifo-must-fail") -> Path:
    """The shipped sync FIFO case with other held-out checks."""
    data = json.loads((EVALS / "rtl" / "sync_fifo.json").read_text(encoding="utf-8"))
    data.update(id=case_id, held_out=held_out)
    path = tmp_path / "cases" / "fifo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- Cases name skills ---------------------------------------------------------------------


def test_a_case_names_skills_from_the_catalog(nirmaan_org, tmp_path):
    case = load_case(_spec_case(tmp_path, []))
    assert case.skills == ()
    named = case.model_copy(update={"skills": ("interface_specification",)})
    assert validate_case(nirmaan_org, named, REPO) == []
    unknown = case.model_copy(update={"skills": ("interface_specification", "no_such_skill")})
    assert validate_case(nirmaan_org, unknown, REPO) == ["unknown skill 'no_such_skill': not in the skill catalog"]
    twice = case.model_copy(update={"skills": ("interface_specification", "interface_specification")})
    assert validate_case(nirmaan_org, twice, REPO) == ["a skill is named twice"]


def test_a_skill_digest_is_its_card_and_its_knowledge_document(nirmaan_org, tmp_path):
    before = skill_digest(nirmaan_org, "rtl_design", tmp_path)
    assert before.startswith("sha256:") and before == skill_digest(nirmaan_org, "rtl_design", tmp_path)
    assert before != skill_digest(nirmaan_org, "interface_specification", tmp_path)
    other = tmp_path / "knowledge" / "design" / "rtl_microarchitecture.md"
    other.parent.mkdir(parents=True)
    other.write_text("Knowledge only: no tool run backs this.\n", encoding="utf-8")
    assert skill_digest(nirmaan_org, "rtl_design", tmp_path) == before  # another skill's document
    document = other.parent / "rtl_design.md"
    document.write_text("Knowledge only: no tool run backs this.\n", encoding="utf-8")
    with_document = skill_digest(nirmaan_org, "rtl_design", tmp_path)
    assert with_document != before
    document.write_text("Knowledge only: no tool run backs this. Edited.\n", encoding="utf-8")
    assert skill_digest(nirmaan_org, "rtl_design", tmp_path) != with_document


# --- Negative controls are checked before they run ----------------------------------------


def test_a_mutant_must_stand_in_for_a_case_file(nirmaan_org, tmp_path):
    check = {**_testbench_check(), "mutants": {"tests/fixtures/rtl/sync_fifo/not_given.v": [OVERFLOW]},
             "cover_tool": "no.such.tool"}
    case = load_case(_fifo_case(tmp_path, [check]))
    problems = validate_case(nirmaan_org, case, REPO)
    assert any("not_given.v, which is not one of its case files" in p for p in problems), problems
    assert any("unknown cover tool 'no.such.tool'" in p for p in problems), problems
    missing = load_case(_fifo_case(tmp_path / "b", [{**_testbench_check(), "mutants": {CLEAN: ["gone.v"]}}]))
    assert validate_case(nirmaan_org, missing, REPO) == ["file not found: gone.v"]


def test_a_mutant_is_part_of_the_case_digest(tmp_path):
    a = load_case(_fifo_case(tmp_path / "a", [_testbench_check()]))
    b = load_case(_fifo_case(tmp_path / "b", [{**_testbench_check(), "mutants": {CLEAN: [OVERFLOW]}}]))
    assert case_digest(a, REPO) != case_digest(b, REPO)


# --- The must-fail scorer, on real tools ---------------------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
def test_the_reference_testbench_and_proofs_catch_the_mutants(nirmaan_org, fixed_clock, tmp_path):
    """Clean RTL passes, covers are reached, and each mutant fails; a proof at one parameter point misses one."""
    case = load_case(_fifo_case(tmp_path, [_testbench_check(), _proof_check("sync_fifo_depth5.sby"),
                                           _proof_check("sync_fifo.sby")]))
    assert validate_case(nirmaan_org, case, REPO) == []
    trial = record_trial(nirmaan_org, case, ModelRuntime(replay_llm(case, REPO), runtime_id="replay"), replay=True,
                         record="tmp", trial=1, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    result = trial.result
    assert result.submitted, result.detail
    testbench, depth5, depth8 = result.scores

    assert testbench.status is ScoreStatus.PASSED, testbench.summary
    assert len(testbench.runs) == 1 and len(testbench.failed_runs) == 2
    assert "2 of 2 mutants failed it" in testbench.summary
    assert depth5.status is ScoreStatus.PASSED, depth5.summary
    assert len(depth5.runs) == 2 and len(depth5.failed_runs) == 2 and "every cover reached" in depth5.summary
    # The DEPTH 8 proof cannot see a pointer that wraps only at a power of two: formal at each parameter point.
    assert depth8.status is ScoreStatus.FAILED
    assert depth8.summary.startswith(f"mutant {POW2} survived: formal.run")
    assert not result.passed

    runs = {j.run: j for j in trial.judge_runs}
    for run in testbench.failed_runs:
        assert runs[run].tool == "simulator.run" and not runs[run].succeeded
        assert "simulation failed" in runs[run].summary and "checks failed" in runs[run].summary, runs[run].summary
    assert runs[testbench.runs[0]].succeeded and runs[testbench.runs[0]].params["top"] == "sync_fifo_tb"
    # Every run's inputs are staged inside the sandbox and stay there with its record.
    stage = tmp_path / "sandbox" / "judge" / "check-1"
    for run in (*testbench.runs, *testbench.failed_runs):
        for source in runs[run].params["sources"]:
            assert Path(source).is_relative_to(stage) and Path(source).is_file(), source
    assert [runs[r].tool for r in depth5.runs] == ["formal.run", "formal.cover"]
    assert all(runs[r].succeeded for r in depth5.runs)
    assert all(not runs[r].succeeded and "formal fail" in runs[r].summary and "[ASSERT]" in runs[r].summary
               for r in depth5.failed_runs)


@needs("verilator", "iverilog", "vvp", "yosys")
def test_a_testbench_that_misses_the_mutants_fails(nirmaan_org, fixed_clock, tmp_path):
    """The seat's testbench passes its own gates and the clean RTL, but cannot tell a mutant from it."""
    case = load_case(_fifo_case(tmp_path, [_testbench_check()]))
    rtl = (REPO / CLEAN).read_text(encoding="utf-8")
    llm = ReplayLLM([("sync_fifo.v", "rtl_source", rtl, "sync_fifo"),
                     ("weak_fifo_tb.v", "testbench", WEAK_FIFO_TB, "weak_fifo_tb")])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith(f"mutant {OVERFLOW} survived: simulator.run run-"), score.summary
    assert score.summary.endswith(" passed") and len(score.runs) == 1 and score.failed_runs == ()


@needs("verilator", "iverilog", "vvp", "yosys")
def test_clean_inputs_that_fail_are_a_failed_control(nirmaan_org, fixed_clock, tmp_path):
    """If the clean side does not pass, no mutant is run: the control proves nothing."""
    case = load_case(_fifo_case(tmp_path, [_testbench_check(clean=OVERFLOW) | {"mutants": {OVERFLOW: [POW2]}}]))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith("the clean inputs do not pass: simulator.run")
    assert len(score.runs) == 1 and score.failed_runs == ()


class _FakeTools:
    """A tool handle whose simulator fails on a mutant: it records what each run was given, and checks it exists."""

    def __init__(self):
        self.calls: list[dict] = []

    def invoke(self, tool, **params):
        sources = [Path(p) for p in params["sources"]]
        assert all(p.is_file() for p in sources)
        self.calls.append(params)
        mutant = "mutant" in sources[0].parent.name
        outcome = SimpleNamespace(succeeded=not mutant, references=("log",), summary="ran")
        return f"run-{len(self.calls):04d}", outcome


def test_with_no_sandbox_folder_the_staged_inputs_are_removed():
    check = HeldOutCheck(name="mutants fail", scorer="must-fail", tool="simulator.run",
                         case_files={"sources": (CLEAN,)}, mutants={CLEAN: (OVERFLOW, POW2)})
    tools = _FakeTools()
    score = scorer_spec("must-fail").fn(ScoreContext(None, None, check, REPO, tools))
    assert score.status is ScoreStatus.PASSED and score.summary.endswith("2 of 2 mutants failed it")
    staged = [Path(p) for call in tools.calls for p in call["sources"]]
    assert len(staged) == 3 and not any(p.exists() or p.parent.exists() for p in staged)


def test_a_second_run_into_the_same_sandbox_folder_stages_afresh(tmp_path):
    check = HeldOutCheck(name="mutants fail", scorer="must-fail", tool="simulator.run",
                         case_files={"sources": (CLEAN,)}, mutants={CLEAN: (OVERFLOW,)})
    tools = _FakeTools()
    for _ in range(2):
        score = scorer_spec("must-fail").fn(ScoreContext(None, None, check, REPO, tools, tmp_path / "check-1"))
        assert score.status is ScoreStatus.PASSED, score.summary
    stages = {Path(call["sources"][0]).parent.parent for call in tools.calls}
    assert len(stages) == 2 and all(s.parent == tmp_path / "check-1" and s.is_dir() for s in stages)


def test_a_must_fail_check_with_no_mutant_is_not_run(nirmaan_org, fixed_clock, tmp_path):
    check = {"name": "nothing to fail", "scorer": "must-fail", "tool": "spec.check",
             "seat_files": {"spec": ["interface_spec"]}}
    result = run_case(nirmaan_org, load_case(_spec_case(tmp_path, [check])), repo=REPO, sandbox=tmp_path / "s",
                      clock=fixed_clock)
    [score] = result.scores
    assert score.status is ScoreStatus.NOT_RUN and "names no mutant" in score.summary and not result.passed


@pytest.mark.parametrize("cite", ["passing", "absent"])
def test_a_claimed_failed_run_must_be_a_recorded_failed_run(nirmaan_org, fixed_clock, tmp_path, cite):
    """The runner overturns a pass whose negative control cites a run that passed, or no run at all."""

    @register_scorer("claims-a-mutant-failed")
    def _claims(ctx) -> Score:
        run, _ = ctx.tools.invoke("artifact.read", artifact=ctx.task.artifacts[0])
        return Score(scorer="claims-a-mutant-failed", name=ctx.check.name, status=ScoreStatus.PASSED,
                     summary="every mutant failed", runs=(run,),
                     failed_runs=(run if cite == "passing" else "run-9999",))

    try:
        case = load_case(_spec_case(tmp_path, [{"name": "claims", "scorer": "claims-a-mutant-failed"}]))
        result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "s", clock=fixed_clock)
    finally:
        unregister_scorer("claims-a-mutant-failed")
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and not result.passed
    assert score.summary.startswith("claimed a run failed with no failed run recorded in the sandbox")


# --- Run records: skill digests, head SHA, and what counts as evidence ---------------------


def _spec_with_skills():
    case = next(c for c in load_cases(EVALS) if c.id == SPEC_CASE)
    return case.model_copy(update={"skills": ("interface_specification",)})


def test_a_record_names_the_head_sha_and_each_skill_digest(nirmaan_org, fixed_clock, tmp_path):
    path = record_run(nirmaan_org, [_spec_with_skills()], None, trials=1, repo=REPO, out=tmp_path,
                      head_sha="0123456789abcdef0123456789abcdef01234567", clock=fixed_clock)
    record = load_record(path)
    assert record.manifest.head_sha == "0123456789abcdef0123456789abcdef01234567"
    [trial] = record.trials
    assert trial.skills == {"interface_specification": skill_digest(nirmaan_org, "interface_specification", REPO)}
    assert trial.result.attestations == ()


def test_the_cli_records_the_head_sha(fixed_clock, tmp_path):
    _spec_case(tmp_path, [], "tmp/head-sha")
    ran = CliRunner().invoke(app, ["eval", "run", "--replay", "--cases", str(tmp_path / "cases"),
                                   "--repo", str(REPO), "--out", str(tmp_path / "out")])
    assert ran.exit_code == 0, ran.output
    [manifest] = (tmp_path / "out").rglob("manifest.json")
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    expected = head.stdout.strip() if head.returncode == 0 else None
    assert json.loads(manifest.read_text())["head_sha"] == expected


def test_the_evidence_loader_refuses_a_replay(nirmaan_org, fixed_clock, tmp_path):
    path = record_run(nirmaan_org, [_spec_with_skills()], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock)
    assert load_record(path).manifest.replay  # readable as a record, never as evidence
    with pytest.raises(EvalError, match="is a replay: it proves the cases, not a model"):
        load_evidence(path)
    # A replayed trial inside a record that says it is live is refused too.
    manifest = json.loads((path / "manifest.json").read_text())
    (path / "manifest.json").write_text(json.dumps({**manifest, "replay": False, "runtime": "claude-code"}))
    with pytest.raises(EvalError, match="trial 1 is a replay"):
        load_evidence(path)


def test_the_evidence_loader_refuses_an_attestation(nirmaan_org, fixed_clock, tmp_path, spec_claude):  # noqa: F811
    path = record_run(nirmaan_org, [_spec_with_skills()], "claude-code", trials=1, repo=REPO, out=tmp_path,
                      head_sha="0" * 40, clock=fixed_clock)
    record = load_evidence(path)  # a live, tool-judged record is evidence
    assert not record.manifest.replay and record.trials[0].result.passed
    [trial_file] = path.rglob("trial-01.json")
    data = json.loads(trial_file.read_text())
    data["result"]["attestations"] = ["ev-0007"]  # a dv_ran requirement met by a person's word
    trial_file.write_text(json.dumps(data))
    with pytest.raises(EvalError, match=r"carries a human attestation \(ev-0007\)"):
        load_evidence(path)


def test_the_runner_records_a_human_attestation_on_the_seat(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    """The producer side: an attestation recorded on the seat's task is listed on the result."""
    real = runner.run_task
    recorded = []

    def attest_then_run(engine, task_id, runtime, **kw):
        ev = engine.record_evidence(task_id, Actor(role=str(engine.task(task_id).owner), kind=ActorKind.HUMAN,
                                                   name="test"), EvidenceKind.HUMAN_ATTESTATION, "ran it elsewhere")
        recorded.append(ev.id)
        return real(engine, task_id, runtime, **kw)

    monkeypatch.setattr(runner, "run_task", attest_then_run)
    result = run_case(nirmaan_org, _spec_with_skills(), repo=REPO, sandbox=tmp_path / "s", clock=fixed_clock)
    assert len(recorded) == 1 and result.attestations == tuple(recorded)


# --- The six shipped cases name their skills -----------------------------------------------


def test_the_shipped_cases_name_the_skills_they_judge(nirmaan_org):
    named = {c.id: c.skills for c in load_cases(EVALS)}
    assert named == {
        "firmware/axi4-lite-driver": ("device_drivers",),
        "rtl/apb-regs": ("rtl_design", "apb"),
        "rtl/axi4-lite-regs": ("rtl_design", "axi"),
        "rtl/rr-arbiter": ("rtl_design",),
        "rtl/sync-fifo": ("rtl_design",),
        "spec/axi4-lite-interface": ("interface_specification",),
    }
    for case in load_cases(EVALS):
        assert validate_case(nirmaan_org, case, REPO) == [], case.id
