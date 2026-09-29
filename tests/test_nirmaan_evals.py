"""Milestone 27: seat evaluation. Does a seat's work actually work?

An evaluation case (``evals/``) is data: a request, the seat under evaluation,
reference documents that fix its approved upstream, a reference answer for
replay, and held-out checks the seat never sees. ``run_case`` plans the request
in a sandbox, puts a runtime in the seat through the unchanged ``run_task``,
then runs the held-out checks through the broker. A case passes only when the
work reached review and every held-out check passed, each backed by a recorded
tool run. No test calls a model API.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from test_nirmaan_design_agents import needs

import nirmaan
from nirmaan.cli import app
from nirmaan.demos import demo
from nirmaan.evals import (
    EvalError,
    ReplayLLM,
    load_case,
    load_cases,
    register_scorer,
    run_case,
    unregister_scorer,
    validate_case,
    write_result,
)
from nirmaan.models import EvalCase, Score, ScoreStatus
from nirmaan.runtime import MockLLM, ModelRuntime

REPO = Path(__file__).parents[1]
EVALS = REPO / "evals"
AXI = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
SHIPPED = ["rtl/apb-regs", "rtl/axi4-lite-regs", "rtl/rr-arbiter", "rtl/sync-fifo"]

#: A testbench that exercises nothing: it resets the block, prints PASS, and stops.
WEAK_TB = """\
`timescale 1ns / 1ps
module weak_tb;
    reg aclk = 1'b0;
    reg aresetn = 1'b0;
    wire awready, wready, bvalid, arready, rvalid;
    wire [1:0] bresp, rresp;
    wire [31:0] rdata;
    always #5 aclk = ~aclk;
    axi4_lite_regs dut (
        .aclk(aclk), .aresetn(aresetn),
        .s_axil_awaddr(4'd0), .s_axil_awvalid(1'b0), .s_axil_awready(awready),
        .s_axil_wdata(32'd0), .s_axil_wstrb(4'd0), .s_axil_wvalid(1'b0), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(1'b0),
        .s_axil_araddr(4'd0), .s_axil_arvalid(1'b0), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(1'b0)
    );
    initial begin
        #20 aresetn = 1'b1;
        #50 $display("weak_tb: PASS");
        $finish;
    end
endmodule
"""


def _spec_case(tmp_path: Path, held_out: list[dict], case_id: str = "tmp/interface-spec") -> Path:
    """A fast case with no EDA gates: the AXI4-Lite interface-spec seat, replaying the fixture spec."""
    path = tmp_path / "cases" / "spec.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "id": case_id,
        "request": "Create an AXI4-Lite register block.",
        "seat": "interface-spec",
        "expected_behavior": "An interface specification for the block.",
        "reference": [{"path": str(AXI / "interface_spec.md"), "kind": "interface_spec"}],
        "held_out": held_out,
    }), encoding="utf-8")
    return path


# --- Cases are data -----------------------------------------------------------------------


def test_every_shipped_case_is_valid(nirmaan_org):
    cases = load_cases(EVALS)
    assert [c.id for c in cases] == SHIPPED
    for case in cases:
        assert isinstance(case, EvalCase)
        assert validate_case(nirmaan_org, case, REPO) == [], case.id
        assert case.expected_behavior and case.known_failure_modes and case.held_out


def test_an_invalid_case_is_reported_not_run(nirmaan_org, tmp_path):
    case = load_case(_spec_case(tmp_path, [{"name": "x", "scorer": "no-such-scorer",
                                             "case_files": {"sources": ["missing.v"]}}]))
    problems = validate_case(nirmaan_org, case, REPO)
    assert any("no-such-scorer" in p for p in problems)
    assert any("missing.v" in p for p in problems)
    bad_seat = case.model_copy(update={"seat": "no-such-stage"})
    assert any("no-such-stage" in p for p in validate_case(nirmaan_org, bad_seat, REPO))


# --- The judge is a real tool run ---------------------------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
@pytest.mark.parametrize("case_id", SHIPPED)
def test_replaying_the_reference_scores_every_check(nirmaan_org, fixed_clock, tmp_path, case_id):
    case = next(c for c in load_cases(EVALS) if c.id == case_id)
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    assert result.replay and result.runtime == "replay"
    assert result.submitted, result.detail
    assert result.passed, result.detail
    assert result.audit_ok
    assert {g.tool for g in result.gate_runs if g.succeeded} >= {"lint.run", "simulator.run", "synth.run"}
    assert result.scores and all(s.status is ScoreStatus.PASSED and s.runs for s in result.scores)


@needs("verilator", "iverilog", "vvp", "yosys")
def test_what_the_gates_miss_the_held_out_testbench_catches(nirmaan_org, fixed_clock, tmp_path):
    """RTL with a wrong reset value and a testbench that checks nothing reaches review; the judge fails it."""
    case = load_case(EVALS / "rtl" / "axi4_lite_regs.json")
    original = (AXI / "axi4_lite_regs.v").read_text()
    buggy = original.replace("reg3 <= {DATA_WIDTH{1'b0}};", "reg3 <= {DATA_WIDTH{1'b1}};")
    assert buggy != original
    llm = ReplayLLM([("axi4_lite_regs.v", "rtl_source", buggy, "axi4_lite_regs"),
                     ("weak_tb.v", "testbench", WEAK_TB, "weak_tb")])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="weak-seat"), repo=REPO,
                      sandbox=tmp_path, clock=fixed_clock)
    assert result.runtime == "weak-seat" and not result.replay
    assert result.submitted, result.detail  # its own lint, simulation, and synthesis all passed
    assert {g.tool for g in result.gate_runs if g.succeeded} >= {"lint.run", "simulator.run", "synth.run"}
    [held] = result.scores
    assert held.status is ScoreStatus.FAILED and held.runs
    assert not result.passed


def test_an_unusable_answer_fails_the_case_honestly(nirmaan_org, fixed_clock, tmp_path):
    case = load_case(EVALS / "rtl" / "axi4_lite_regs.json")
    runtime = ModelRuntime(MockLLM(script=["I would write the RTL like this, roughly."]), runtime_id="rambler")
    result = run_case(nirmaan_org, case, runtime, repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    assert not result.submitted and not result.passed
    assert "not a JSON object" in result.detail
    assert result.scores and all(s.status is ScoreStatus.NOT_RUN and not s.runs for s in result.scores)


def test_a_held_out_check_that_cannot_run_is_not_run(nirmaan_org, fixed_clock, tmp_path):
    """The broker refuses (the spec seat's owner is not granted the simulator): not run, never passed."""
    case = load_case(_spec_case(tmp_path, [{
        "name": "simulate the reference", "scorer": "held-out-run", "tool": "simulator.run",
        "case_files": {"sources": [str(AXI / "axi4_lite_regs.v"), str(AXI / "axi4_lite_regs_tb.v")]},
        "params": {"top": "axi4_lite_regs_tb"},
    }]))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result.detail
    [score] = result.scores
    assert score.status is ScoreStatus.NOT_RUN and not score.runs
    assert score.summary.startswith("simulator.run not run:"), score.summary
    assert not result.passed


def test_a_pass_needs_a_recorded_run(nirmaan_org, fixed_clock, tmp_path):
    """A scorer that says 'passed' without a passing run the broker recorded is recorded as failed."""

    @register_scorer("says-so")
    def _says_so(ctx) -> Score:
        return Score(scorer="says-so", name=ctx.check.name, status=ScoreStatus.PASSED, summary="trust me")

    try:
        case = load_case(_spec_case(tmp_path, [{"name": "vibes", "scorer": "says-so"}]))
        result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    finally:
        unregister_scorer("says-so")
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED
    assert "no passing run" in score.summary
    assert not result.passed


def test_a_gate_before_the_seat_stops_the_run(nirmaan_org, fixed_clock, tmp_path):
    """The harness fixes work stages only; it never passes a gate on anyone's behalf."""
    case = load_case(_spec_case(tmp_path, []))
    case = case.model_copy(update={"request": demo("1").requirement})
    with pytest.raises(EvalError, match="gate"):
        run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)


def test_the_sandbox_is_separate_and_the_result_says_what_ran(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    case = load_case(_spec_case(tmp_path, []))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not (tmp_path / ".nirmaan").exists()
    assert result.submitted and result.passed  # no held-out checks: reaching review is the whole case
    assert result.sandbox.startswith(str(tmp_path / "sandbox"))
    assert result.version == nirmaan.__version__
    path = write_result(result, tmp_path / "out")
    data = json.loads(path.read_text())
    assert data["case"] == "tmp/interface-spec" and data["runtime"] == "replay" and data["replay"] is True
    assert data["case_digest"].startswith("sha256:")
    other = load_case(_spec_case(tmp_path / "b", [], case_id="tmp/interface-spec"))
    assert run_case(nirmaan_org, other, repo=REPO, sandbox=tmp_path / "s2",
                    clock=fixed_clock).case_digest == result.case_digest  # same inputs, same digest


def test_the_runner_names_no_stage_tool_kind_or_role(nirmaan_org):
    """Stages, tools, artifact kinds, and roles come from case data, never from the evaluation code."""
    org = nirmaan_org
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles) | set(org.tools)
                  | {s.id for w in org.workflows.values() for s in w.stages}
                  | {k for w in org.workflows.values() for s in w.stages for k in s.outputs})
    package = Path(nirmaan.__file__).parent / "evals"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in vocabulary, f"{path.name} hard-codes {node.value!r}"


# --- Crown jewel and CLI ------------------------------------------------------------------


def test_a_new_case_or_scorer_needs_zero_core_changes(fixed_clock, tmp_path):
    """A scorer registered here and a case written here run through ``nirmaan eval run``."""

    @register_scorer("reads-back")
    def _reads_back(ctx) -> Score:
        runs = [ctx.tools.invoke("artifact.read", artifact=a)[0] for a in ctx.task.artifacts]
        return Score(scorer="reads-back", name=ctx.check.name, status=ScoreStatus.PASSED,
                     summary=f"read back {len(runs)} artifacts", runs=tuple(runs))

    try:
        _spec_case(tmp_path, [{"name": "every artifact reads back", "scorer": "reads-back"}], "tmp/reads-back")
        out = tmp_path / "out"
        listed = CliRunner().invoke(app, ["eval", "list", "--cases", str(tmp_path / "cases")])
        assert listed.exit_code == 0 and "tmp/reads-back" in listed.output
        ran = CliRunner().invoke(app, ["eval", "run", "--replay", "--cases", str(tmp_path / "cases"),
                                       "--repo", str(REPO), "--out", str(out)])
    finally:
        unregister_scorer("reads-back")
    assert ran.exit_code == 0, ran.output
    assert "PASS tmp/reads-back" in ran.output
    [written] = list(out.rglob("*.json"))
    assert json.loads(written.read_text())["scores"][0]["status"] == "passed"


def test_the_cli_refuses_an_unclear_request_and_fails_a_failing_case(tmp_path):
    cases = tmp_path / "cases"
    neither = CliRunner().invoke(app, ["eval", "run", "--cases", str(EVALS)])
    assert neither.exit_code != 0 and "--runtime" in neither.output
    unknown = CliRunner().invoke(app, ["eval", "run", "rtl/nope", "--replay", "--cases", str(EVALS)])
    assert unknown.exit_code != 0 and "rtl/nope" in unknown.output
    _spec_case(tmp_path, [{"name": "simulate", "scorer": "held-out-run", "tool": "simulator.run",
                           "case_files": {"sources": [str(AXI / "axi4_lite_regs.v")]}}])
    failed = CliRunner().invoke(app, ["eval", "run", "--replay", "--cases", str(cases), "--repo", str(REPO),
                                      "--out", str(tmp_path / "out"), "--json"])
    assert failed.exit_code == 1
    [row] = json.loads(failed.output)
    assert row["passed"] is False and row["scores"][0]["status"] == "not_run"
