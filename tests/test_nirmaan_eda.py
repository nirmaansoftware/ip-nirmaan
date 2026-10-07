"""Milestone 21: real design tools through open-source EDA.

* Parsers are tested against captured tool output (tests/fixtures/eda), with
  no tool installed.
* Real-tool tests run Verilator, Icarus, Yosys, and SymbiYosys over the fixture
  RTL in tests/fixtures/rtl, and skip when an executable is absent.
* A missing executable is a refusal with a reason, never a simulated run.
* A real lint run substantiates the RTL lint requirement with no human
  attestation.
* Crown jewel: a new backend needs zero core changes.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import GATE_TOOLS, agent, drive, tid

from nirmaan.integrations.eda import (
    Backend,
    EdaResult,
    register_backend,
    triage_simulation,
    unregister_backend,
)
from nirmaan.integrations.eda_parsers import parse_sby, parse_simulation, parse_verilator_lint, parse_yosys
from nirmaan.models import Assurance, EvidenceKind, TaskStatus, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import ToolAccessDenied, ToolBroker
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
EDA = FIXTURES / "eda"
RTL = FIXTURES / "rtl"
COUNTER = RTL / "counter.v"
BRIDGE = "Create a 4-port AXI-to-NoC bridge."


def _text(name: str) -> str:
    return (EDA / name).read_text(encoding="utf-8")


def needs(*executables: str):
    """Skip without the executables, except those CI names in NIRMAAN_REQUIRE_EDA (then it fails)."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def holder(engine, tool: str) -> str:
    """A role that may use ``tool``: the organization decides who, not the test."""
    authority = AuthorityService(engine.org)
    for role in engine.org.roles:
        if authority.may_use_tool(role, tool)[0]:
            return role
    raise AssertionError(f"no role may use {tool}")


def invoke(engine, tool: str, params: dict[str, str], tmp_path: Path, task: str | None = None):
    return ToolBroker(engine).invoke(agent(holder(engine, tool)), tool, {"workdir": str(tmp_path), **params}, task)


# --- The catalog -------------------------------------------------------------------------


def test_the_open_source_tools_are_available_and_the_rest_stay_contracts(nirmaan_org):
    for tool in ("lint.run", "simulator.run", "test.run", "synth.run", "formal.run"):
        assert nirmaan_org.tools[tool].status is ToolStatus.AVAILABLE, tool
    for tool in ("equivalence.run", "cdc.run"):  # sta.run and pnr.run: M25, tests/test_nirmaan_physical.py
        assert nirmaan_org.tools[tool].status is ToolStatus.CONTRACT_ONLY, tool


# --- Parsers, against captured output (no tool needed) ------------------------------------


def test_verilator_lint_clean():
    result = parse_verilator_lint(_text("verilator_lint_clean.log"), 0)
    assert result.passed and result.diagnostics == () and result.summary.startswith("lint clean")


def test_verilator_lint_warnings_fail_lint():
    result = parse_verilator_lint(_text("verilator_lint_warnings.log"), 1)
    assert not result.passed and not result.errors
    assert [w.code for w in result.warnings] == ["WIDTHTRUNC", "UNUSEDSIGNAL"]
    first = result.warnings[0]
    assert (first.file, first.line, first.column) == ("bad.v", 7, 29)
    assert "2 warnings" in result.summary and "WIDTHTRUNC" in result.summary


def test_verilator_lint_syntax_error():
    result = parse_verilator_lint(_text("verilator_lint_error.log"), 1)
    assert not result.passed and len(result.errors) == 1  # "Cannot continue" is noise
    assert (result.errors[0].file, result.errors[0].line) == ("bad2.v", 3)
    assert "syntax error" in result.errors[0].message


def test_icarus_passing_simulation():
    result = parse_simulation(_text("icarus_sim_pass.log"), (0, 0))
    assert result.passed and result.metrics["finished"] and result.metrics["end_time"] == "130000"


def test_icarus_failing_simulation_exits_zero_but_fails():
    result = parse_simulation(_text("icarus_sim_fail.log"), (0, 0))
    assert not result.passed and len(result.errors) == 4
    assert (result.errors[0].file, result.errors[0].line) == ("counter_tb_fail.v", 23)
    assert "4 errors" in result.summary


def test_icarus_compile_error():
    result = parse_simulation(_text("icarus_compile_error.log"), (2,))
    assert not result.passed and result.errors[0].file == "bad2.v"
    assert "$finish never reached" in result.summary


def test_verilator_simulation():
    passed = parse_simulation(_text("verilator_sim_pass.log"), (0, 0))
    assert passed.passed and passed.metrics["end_time"] == "130ns"
    failed = parse_simulation(_text("verilator_sim_fail.log"), (0, 1))
    assert not failed.passed and failed.errors[0].line == 23 and "Assertion failed" in failed.errors[0].message


def test_yosys_synthesis_statistics():
    result = parse_yosys(_text("yosys_synth.log"), 0, _text("yosys_stat.json"))
    assert result.passed and not result.errors
    assert result.metrics["cells"] == 15 and result.metrics["flip_flops"] == 4 and result.metrics["latches"] == 0
    assert result.summary.startswith("synthesis passed: 15 cells")


def test_yosys_error():
    result = parse_yosys(_text("yosys_error.log"), 1)
    assert not result.passed and "not found" in result.errors[0].message


def test_symbiyosys_proof_and_counterexample():
    proof = parse_sby(_text("sby_pass.log"), 0)
    assert proof.passed and proof.metrics["status"] == "PASS"
    cex = parse_sby(_text("sby_fail.log"), 2)
    assert not cex.passed and cex.metrics["status"] == "FAIL"
    assert len(cex.errors) == 1 and (cex.errors[0].file, cex.errors[0].line) == ("counter.v", 30)
    assert "step 11" in cex.errors[0].message and len(cex.metrics["traces"]) == 2
    crashed = parse_sby("Traceback (most recent call last):\nFileNotFoundError: counter.v\n", 1)
    assert not crashed.passed and "did not finish (exit status 1): FileNotFoundError" in crashed.summary


# --- Refusal: a missing executable is never simulated -------------------------------------


def test_a_missing_executable_is_a_refusal_with_a_reason(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing on PATH
    for tool in ("lint.run", "simulator.run", "synth.run", "formal.run"):
        with pytest.raises(ToolAccessDenied, match="not found"):
            # Each tool gets only parameters its contract declares (M28): formal takes no top.
            invoke(bridge, tool, {"sources": str(COUNTER), **({} if tool == "formal.run" else {"top": "counter"})},
                   tmp_path)
    with pytest.raises(ToolAccessDenied, match="verilator"):
        invoke(bridge, "lint.run", {"sources": str(COUNTER)}, tmp_path)
    assert bridge.state.tool_runs == {}  # nothing ran, so nothing was recorded


def test_an_unknown_backend_is_refused(bridge, tmp_path):
    with pytest.raises(ToolAccessDenied, match="no backend named"):
        invoke(bridge, "lint.run", {"sources": str(COUNTER), "backend": "nosuch"}, tmp_path)


# --- Real tools --------------------------------------------------------------------------


@needs("verilator")
def test_real_lint_of_the_fixture_is_clean(bridge, tmp_path):
    run, outcome = invoke(bridge, "lint.run", {"sources": str(COUNTER), "top": "counter"}, tmp_path)
    assert run.succeeded and "lint clean" in run.summary
    log, result = (Path(r) for r in run.references)
    assert log.is_file() and result.is_file() and "verilator --lint-only" in log.read_text()
    assert outcome.data["executables"]["verilator"] == shutil.which("verilator")


@needs("verilator")
def test_real_lint_failure_is_a_recorded_failed_run(bridge, tmp_path):
    bad = tmp_path / "bad.v"
    bad.write_text("module bad(input wire [7:0] a, output wire [3:0] q);\n  assign q = a;\nendmodule\n")
    run, outcome = invoke(bridge, "lint.run", {"sources": str(bad)}, tmp_path)
    assert not run.succeeded and run.id in bridge.state.tool_runs
    assert any(d["code"] == "WIDTHTRUNC" for d in outcome.data["result"]["diagnostics"])


@needs("verilator")
def test_missing_sources_are_a_recorded_failed_run(bridge, tmp_path):
    run, _ = invoke(bridge, "lint.run", {"sources": str(tmp_path / "nope.v")}, tmp_path)
    assert not run.succeeded and "not found" in run.summary


@needs("sleep")
def test_a_timeout_is_a_recorded_failed_run(bridge, tmp_path):
    register_backend(Backend("sleeper", "lint.run", ("sleep",), lambda job: [["sleep", "30"]],
                             lambda run: EdaResult(run.returncode == 0, "slept")))
    try:
        params = {"sources": str(COUNTER), "backend": "sleeper", "timeout": "1"}
        run, _ = invoke(bridge, "lint.run", params, tmp_path)
        assert not run.succeeded and run.summary == "sleeper: timed out after 1s in sleep"
    finally:
        unregister_backend("lint.run", "sleeper")


@needs("yosys")
def test_real_synthesis_of_the_fixture(bridge, tmp_path):
    run, outcome = invoke(bridge, "synth.run", {"sources": str(COUNTER), "top": "counter"}, tmp_path)
    assert run.succeeded, run.summary
    metrics = outcome.data["result"]["metrics"]
    assert metrics["cells"] > 0 and metrics["flip_flops"] == 4 and metrics["latches"] == 0


@needs("iverilog", "vvp")
def test_real_icarus_simulation_passes(bridge, tmp_path):
    params = {"sources": f"{COUNTER},{RTL / 'counter_tb.v'}", "top": "counter_tb", "backend": "icarus"}
    run, _ = invoke(bridge, "test.run", params, tmp_path)
    assert run.succeeded and "simulation passed" in run.summary, run.summary


@needs("verilator")
def test_real_verilator_simulation_passes(bridge, tmp_path):
    params = {"sources": f"{COUNTER},{RTL / 'counter_tb.v'}", "top": "counter_tb", "backend": "verilator-sim"}
    run, _ = invoke(bridge, "simulator.run", params, tmp_path)
    assert run.succeeded and "simulation passed" in run.summary, run.summary


@needs("iverilog", "vvp")
def test_a_failing_simulation_log_feeds_veritriage(bridge, tmp_path):
    params = {"sources": f"{COUNTER},{RTL / 'counter_tb_fail.v'}", "top": "counter_tb_fail", "backend": "icarus"}
    run, _ = invoke(bridge, "simulator.run", params, tmp_path / "sim")
    assert not run.succeeded and "4 errors" in run.summary
    triage, outcome = triage_simulation(ToolBroker(bridge), agent(holder(bridge, "veritriage.investigate")), run,
                                        workspace=str(tmp_path / "vt"))
    assert triage.tool == "veritriage.investigate" and triage.succeeded
    assert triage.params["paths"] == run.references[0] and triage.references[0].startswith("ses-")
    assert set(bridge.state.tool_runs) == {run.id, triage.id}  # two real runs, both on the record


@needs("sby", "yosys", "yices-smt2")  # yices is smtbmc's default solver
def test_real_formal_proof_and_counterexample(bridge, tmp_path):
    run, _ = invoke(bridge, "formal.run", {"sby": str(RTL / "counter.sby")}, tmp_path / "pass")
    assert run.succeeded and "formal passed" in run.summary, run.summary
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "counter.v").write_text(COUNTER.read_text().replace("count <= LIMIT);", "count < LIMIT);"))
    shutil.copy(RTL / "counter.sby", broken / "counter.sby")
    run, outcome = invoke(bridge, "formal.run", {"sby": str(broken / "counter.sby")}, tmp_path / "fail")
    assert not run.succeeded and outcome.data["result"]["metrics"]["status"] == "FAIL"


# --- Evidence: a real lint run meets the RTL lint requirement ------------------------------


@needs("verilator", *GATE_TOOLS)  # M27: the RTL stage before it is gated
def test_real_lint_substantiates_the_rtl_lint_requirement(bridge, tmp_path):
    lint = tid(bridge, "rtl-lint")
    drive(bridge, until=lint)
    owner = agent(bridge.task(lint).owner)  # an AI agent: it cannot attest to anything
    bridge.start(lint, owner)
    bridge.submit(lint, owner, [{"kind": "lint_report", "title": "Lint of counter"}])
    run, _ = ToolBroker(bridge).invoke(owner, "lint.run", {"sources": str(COUNTER), "workdir": str(tmp_path)}, lint)
    ev = bridge.record_evidence(lint, owner, EvidenceKind.TOOL_RUN, run.summary,
                                reference=run.references[0], tool_run=run.id)
    task = bridge.task(lint)
    assert ev.substantiated and unsatisfied_requirements(bridge.state, task) == []
    assert task.status is TaskStatus.COMPLETED
    assert all(bridge.state.evidence[e].kind is not EvidenceKind.HUMAN_ATTESTATION for e in task.evidence)
    assert bridge.state.artifacts[task.artifacts[0]].assurance is Assurance.VERIFIED


# --- Crown jewel: a new backend needs zero core changes -----------------------------------


def test_a_new_backend_needs_no_core_changes(bridge, tmp_path, monkeypatch):
    """A lint backend the core has never heard of: an executable, its steps, its parser."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "fakelint"
    tool.write_text('#!/bin/sh\nfor f in "$@"; do echo "checked $f"; done\necho "fakelint: 0 issues"\n')
    tool.chmod(0o755)

    def parse(run) -> EdaResult:
        clean = run.returncode == 0 and "fakelint: 0 issues" in run.log
        return EdaResult(clean, "0 issues" if clean else "issues found")

    register_backend(Backend("fakelint", "lint.run", ("fakelint",),
                             lambda job: [["fakelint", *job.sources]], parse))
    try:
        params = {"sources": str(COUNTER), "backend": "fakelint"}
        with pytest.raises(ToolAccessDenied, match="fakelint needs fakelint"):
            invoke(bridge, "lint.run", params, tmp_path / "w1")  # not on PATH yet: refused
        monkeypatch.setenv("PATH", f"{bin_dir}:{Path(shutil.which('sh')).parent}")
        lint = tid(bridge, "rtl-lint")
        run, _ = invoke(bridge, "lint.run", params, tmp_path / "w2", lint)
        assert run.succeeded and run.summary == "fakelint: 0 issues"
        assert f"checked {COUNTER}" in Path(run.references[0]).read_text()  # it really ran
        owner = agent(bridge.task(lint).owner)
        ev = bridge.record_evidence(lint, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
        assert ev.substantiated and unsatisfied_requirements(bridge.state, bridge.task(lint)) == []
    finally:
        unregister_backend("lint.run", "fakelint")
