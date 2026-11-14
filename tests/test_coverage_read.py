"""Code coverage through Verilator and verilator_coverage: ``coverage.read`` (M70).

``coverage.read`` builds a simulation with Verilator's line and toggle coverage,
runs the testbench as ``simulator.run`` runs it (its one verdict, with the run's
nonce), and has ``verilator_coverage`` read the data the run wrote. The parser
turns that data into line, toggle and branch percentages over the design files,
never the testbench; a requirement's bounds are the threshold. The must-fail
pair: on the same counter, a testbench that exercises it meets the bounds and
one that holds it in reset passes its own checks but fails them. Block
verification's coverage stage gates on it before review. Real-tool tests skip
when an executable is absent (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS, agent

from nirmaan.company.workflows import BLOCK_VERIFICATION, COVERAGE_TARGETS
from nirmaan.evals import load_case, run_case, validate_case
from nirmaan.integrations.eda import backends_for, execute
from nirmaan.integrations.eda_parsers import coverage_points, parse_coverage
from nirmaan.models import FileInput, ToolRisk, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import ToolBroker

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
COUNTER = FIXTURES / "rtl" / "counter.v"
FULL_TB = FIXTURES / "coverage" / "counter_full_tb.v"
IDLE_TB = FIXTURES / "coverage" / "counter_idle_tb.v"
#: Captured: counter_idle_tb.v run on counter.v, compiled by their file names (Verilator 5.052).
IDLE_DATA = (FIXTURES / "eda" / "verilator_coverage_idle.dat").read_text(encoding="utf-8")
NONCE = "0123456789abcdef0123456789abcdef"
COVERAGE_TOOLS = ("verilator", "verilator_coverage")


def _log(passed: int = 4, failed: int = 0) -> str:
    """A run's log as the backend writes it: its own echo of the step with the nonce, then the simulation."""
    return (f"$ obj/Vcounter_idle_tb +nirmaan_nonce={NONCE} +verilator+coverage+file+coverage_sim.dat\n"
            f"NIRMAAN-SIM {NONCE} {passed} passed, {failed} failed\n"
            "- counter_idle_tb.v:33: Verilog $finish\n"
            "- Verilator: $finish at 40ns; walltime 0.001 s; speed 54.348 us/s\n")


def _backend():
    return backends_for("coverage.read")[0]


def _holder(engine) -> str:
    authority = AuthorityService(engine.org)
    return next(r for r in engine.org.roles if authority.may_use_tool(r, "coverage.read")[0])


# --- The catalog -------------------------------------------------------------------------------------------


def test_coverage_read_is_available_runs_code_and_declares_what_it_reads(nirmaan_org):
    tool = nirmaan_org.tools["coverage.read"]
    assert tool.status is ToolStatus.AVAILABLE and tool.risk is ToolRisk.EXECUTE
    assert {p.name for p in tool.params} == {"sources", "top", "design", "backend", "workdir", "timeout"}
    assert [b.name for b in backends_for("coverage.read")] == ["verilator-coverage"]
    assert _backend().executables == COVERAGE_TOOLS


# --- The parser, on captured data (no tool needed) ----------------------------------------------------------


def test_the_captured_data_is_read_by_type_and_file():
    points = coverage_points(IDLE_DATA)
    assert {kind for _, kind, _ in points} == {"line", "toggle", "branch"}
    assert {source for source, _, _ in points} == {"counter.v", "counter_idle_tb.v"}


def test_only_the_design_files_count_and_percentages_round_down():
    result = parse_coverage(_log(), (0, 0, 0, 0), NONCE, IDLE_DATA, ["counter.v"])
    assert result.passed, result.summary
    m = result.metrics
    assert (m["line"], m["toggle"], m["branch"]) == (66.66, 18.75, 0.0)  # 2 of 3 lines: 66.66, never 66.67
    assert m["coverage"]["toggle"] == {"covered": 3, "points": 16}
    assert m["checks"] == 4
    assert "coverage read over counter.v: line 66.66% (2/3), toggle 18.75% (3/16), branch 0.00% (0/2)" \
        in result.summary


def test_a_type_is_read_from_the_page_when_a_point_has_no_type_key():
    data = "\n".join(line.replace("\x01t\x02toggle", "") for line in IDLE_DATA.splitlines())
    assert "\x01t\x02toggle" not in data
    result = parse_coverage(_log(), (0, 0, 0, 0), NONCE, data, ["counter.v"])
    assert result.metrics["toggle"] == 18.75


@pytest.mark.parametrize("log,codes,data,design,why", [
    (_log(failed=1), (0, 0, 0, 0), IDLE_DATA, ["counter.v"], "1 of 5 checks failed"),
    (_log(), (0, 1), IDLE_DATA, ["counter.v"], "exit status 1"),
    (_log().replace(f"NIRMAAN-SIM {NONCE}", f"NIRMAAN-SIM {'f' * 32}"), (0, 0, 0, 0), IDLE_DATA, ["counter.v"], "without this run's nonce"),
    (_log(), (0, 0, 0, 0), None, ["counter.v"], "wrote no coverage data"),
    (_log(), (0, 0, 0, 0), IDLE_DATA, ["counter.v", "other.v"], "no coverage point in other.v"),
], ids=["a-check-failed", "a-step-failed", "a-forged-verdict", "no-data", "a-design-file-not-built"])
def test_coverage_that_measured_nothing_or_a_testbench_that_failed_is_no_evidence(log, codes, data, design, why):
    result = parse_coverage(log, codes, NONCE, data, design)
    assert not result.passed and why in result.summary, result.summary
    assert "line" not in result.metrics


# --- What a run refuses before anything runs (no tool needed) ------------------------------------------------


def _refused(tmp_path: Path, tb_text: str | None = None, name: str = "counter_full_tb.v", **params) -> str:
    tb = tmp_path / name
    tb.write_text(FULL_TB.read_text(encoding="utf-8") if tb_text is None else tb_text, encoding="utf-8")
    outcome = execute(_backend(), {"sources": f"{COUNTER},{tb}", "top": "counter_full_tb",
                                   "workdir": str(tmp_path / "run"), **params})
    assert not outcome.succeeded and not outcome.references, outcome.summary
    return outcome.summary


FULL = FULL_TB.read_text(encoding="utf-8")


@pytest.mark.parametrize("text,why", [
    (FULL.replace("    integer i;", '    integer i;\n    initial $c("VerilatedCov::zero();");'), "uses $c"),
    (FULL.replace("    integer i;", '    integer i;\n    integer f;\n    initial f = $fopen("coverage_sim.dat");'),
     "uses $fopen"),
    (FULL.replace("    integer i;", '    integer i;\n    import "DPI-C" function void forge();'), "uses DPI"),
    (FULL.replace("    integer i;", "    integer i;\n    /* verilator coverage_off */"), "uses coverage_off"),
    (FULL.replace("`timescale 1ns / 1ps", '`timescale 1ns / 1ps\n`include "more.vh"'), "uses `include"),
    (FULL + '`verilator_config\ncoverage_off -file "*counter.v"\n', "uses `verilator_config"),
])
def test_a_testbench_that_could_forge_the_counts_is_refused(tmp_path, text, why):
    assert why in _refused(tmp_path, text)


def test_a_source_that_is_not_verilog_is_refused(tmp_path):
    assert "Verilog sources only" in _refused(tmp_path, name="counter_full_tb.vlt")


def test_the_testbench_is_never_measured_and_design_files_must_be_sources(tmp_path):
    tb = tmp_path / "counter_full_tb.v"
    assert "the testbench is never measured" in _refused(tmp_path, design=str(tb))
    assert "is not" in _refused(tmp_path, design=str(IDLE_TB))


# --- The must-fail pair, for real ----------------------------------------------------------------------------


def _run(engine, tb: Path, tmp_path: Path, bounds=COVERAGE_TARGETS):
    params = {"sources": f"{COUNTER},{tb}", "top": tb.stem, "workdir": str(tmp_path / tb.stem)}
    return ToolBroker(engine).invoke(agent(_holder(engine)), "coverage.read", params, bounds=bounds)


@needs(*COVERAGE_TOOLS)
def test_a_testbench_that_exercises_the_design_meets_the_bounds_and_an_idle_one_fails_them(nirmaan_org,
                                                                                            fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Verify the existing counter RTL with coverage.")
    full, outcome = _run(engine, FULL_TB, tmp_path)
    assert full.succeeded, full.summary
    assert (outcome.metrics["line"], outcome.metrics["toggle"], outcome.metrics["branch"]) == (100.0, 100.0, 100.0)
    assert full.bounds == COVERAGE_TARGETS
    assert {"log", "coverage", "info"} <= set(full.outputs)
    assert Path(full.outputs["info"]).read_text(encoding="utf-8").startswith("TN:")  # the lcov report
    idle, outcome = _run(engine, IDLE_TB, tmp_path)
    assert not idle.succeeded and "limit not met" in idle.summary, idle.summary
    assert "line 66.66 is below min_line 90" in idle.summary and "toggle 18.75 is below min_toggle 75" in idle.summary
    # Its own checks passed and the coverage was read: only the bounds failed it.
    assert outcome.metrics["checks"] == 4 and outcome.metrics["coverage"]["line"]["points"] == 3
    unbounded, _ = _run(engine, IDLE_TB, tmp_path / "unbounded", bounds=())
    assert unbounded.succeeded, unbounded.summary


@needs(*COVERAGE_TOOLS)
def test_a_testbench_whose_checks_fail_reads_no_coverage(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Verify the existing counter RTL with coverage.")
    wrong = tmp_path / "counter_full_tb.v"
    wrong.write_text(FULL.replace("check(4'd2);\n        @(negedge clk);", "check(4'd3);\n        @(negedge clk);", 1),
                     encoding="utf-8")
    run, _ = _run(engine, wrong, tmp_path)
    assert not run.succeeded and "coverage not read" in run.summary and "checks failed" in run.summary, run.summary


# --- Block verification's coverage gate ------------------------------------------------------------------------

REQUEST = "Verify the existing 4-bit wrapping counter RTL with coverage."


def test_the_coverage_stage_gates_on_coverage_read_over_the_approved_rtl(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REQUEST)
    task = next(t for t in engine.state.tasks.values() if t.stage == "coverage")
    (gate,) = [r for r in task.evidence_requirements if r.before_review]
    assert gate.tools == ("coverage.read",) and gate.bounds == COVERAGE_TARGETS
    assert [(b.metric, b.op, b.value) for b in gate.bounds] == [("line", "min", 90), ("toggle", "min", 75)]
    approved = FileInput(param="sources", kinds=("rtl_source",), upstream=True)
    assert approved in gate.files and FileInput(param="design", kinds=("rtl_source",), upstream=True) in gate.files
    assert not any("rtl_source" in b.kinds for b in gate.files if not b.upstream)
    stage = next(s for s in BLOCK_VERIFICATION.stages if s.id == "coverage")
    assert stage.outputs == ("testbench", "coverage_report") and "design-under-test" in stage.depends_on


def _case(tmp_path: Path, testbench: Path) -> Path:
    data = {"id": "tmp/block-verification-coverage", "request": REQUEST, "seat": "coverage",
            "expected_behavior": "The seat's testbench reaches the coverage targets on the approved RTL.",
            "upstream": {"interface-spec": [{"path": "tests/fixtures/vplan/requirements_spec.md",
                                             "kind": "interface_spec"}],
                         "design-under-test": [{"path": "tests/fixtures/rtl/counter.v", "kind": "rtl_source",
                                                "entry": "counter"}],
                         "testbench": [{"path": "tests/fixtures/rtl/counter_tb.v", "kind": "testbench",
                                        "entry": "counter_tb"}]},
            "reference": [{"path": str(testbench.relative_to(REPO)), "kind": "testbench", "entry": testbench.stem}],
            "held_out": []}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@needs(*GATE_TOOLS, *COVERAGE_TOOLS)
def test_a_coverage_seat_reaches_review_only_with_a_testbench_that_meets_the_targets(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    full = load_case(_case(tmp_path, FULL_TB))
    assert validate_case(nirmaan_org, full, REPO) == []
    result = run_case(nirmaan_org, full, repo=REPO, sandbox=tmp_path / "full", clock=fixed_clock)
    assert result.submitted, result
    idle = load_case(_case(tmp_path, IDLE_TB))
    result = run_case(nirmaan_org, idle, repo=REPO, sandbox=tmp_path / "idle", clock=fixed_clock)
    assert not result.submitted, result
    assert "limit not met" in result.detail, result.detail
