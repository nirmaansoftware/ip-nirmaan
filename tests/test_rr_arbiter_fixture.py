"""Milestone 26: the round-robin arbiter fixture set, proven by real tools.

``tests/fixtures/rtl/rr_arbiter/`` holds what the design seats are expected to
produce for a round-robin arbiter over N requesters: an interface spec, a
microarchitecture plan, the RTL, a self-checking testbench, a deliberately
wrong testbench, and two SymbiYosys proofs (the default N 4, and N 5, where
the pointer wraps before a power of two). These tests run the files
through the M21 bindings, via the broker, so every claim that the fixture
works is a recorded real run. Each test skips when its executable is absent,
except those CI names in ``NIRMAAN_REQUIRE_EDA``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test_nirmaan_eda import BRIDGE, invoke
from laws import needs

from nirmaan.orchestrator import Orchestrator

ARB = Path(__file__).parent / "fixtures" / "rtl" / "rr_arbiter"
RTL = ARB / "rr_arbiter.v"
TOP = "rr_arbiter"


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def test_the_fixture_set_is_complete():
    names = {p.name for p in ARB.iterdir()}
    assert {"interface_spec.md", "microarchitecture.md", "rr_arbiter.v", "rr_arbiter_tb.v",
            "rr_arbiter_tb_fail.v", "rr_arbiter.sby", "rr_arbiter_n5.sby"} <= names
    rtl = RTL.read_text(encoding="utf-8")
    assert "parameter N = 4" in rtl
    for port in ("clk", "rst_n", "req", "grant"):
        assert port in rtl, port


@needs("verilator")
def test_real_lint_is_clean(bridge, tmp_path):
    run, _ = invoke(bridge, "lint.run", {"sources": str(RTL), "top": TOP}, tmp_path)
    assert run.succeeded and "lint clean" in run.summary, run.summary


@pytest.mark.parametrize("backend", [
    pytest.param("icarus", marks=needs("iverilog", "vvp")),
    pytest.param("verilator-sim", marks=needs("verilator")),
])
def test_real_simulation_passes(bridge, tmp_path, backend):
    params = {"sources": f"{RTL},{ARB / 'rr_arbiter_tb.v'}", "top": "rr_arbiter_tb", "backend": backend}
    run, _ = invoke(bridge, "simulator.run", params, tmp_path)
    assert run.succeeded and "simulation passed" in run.summary, run.summary
    assert "rr_arbiter_tb: PASS" in Path(run.references[0]).read_text()


@pytest.mark.parametrize("backend", [
    pytest.param("icarus", marks=needs("iverilog", "vvp")),
    pytest.param("verilator-sim", marks=needs("verilator")),
])
def test_the_wrong_testbench_is_a_recorded_failed_run(bridge, tmp_path, backend):
    params = {"sources": f"{RTL},{ARB / 'rr_arbiter_tb_fail.v'}", "top": "rr_arbiter_tb_fail",
              "backend": backend}
    run, outcome = invoke(bridge, "test.run", params, tmp_path)
    assert not run.succeeded and run.id in bridge.state.tool_runs
    assert "simulation failed" in run.summary and "rotation with everyone requesting" in run.summary, run.summary
    assert outcome.data["result"]["metrics"]["errors"] >= 1


@needs("yosys")
def test_real_synthesis(bridge, tmp_path):
    run, outcome = invoke(bridge, "synth.run", {"sources": str(RTL), "top": TOP}, tmp_path)
    assert run.succeeded, run.summary
    metrics = outcome.data["result"]["metrics"]
    assert metrics["cells"] > 0 and metrics["flip_flops"] > 0 and metrics["latches"] == 0


@needs("sby", "yosys", "yices-smt2")  # yices is smtbmc's default solver
@pytest.mark.parametrize("sby", ["rr_arbiter.sby", "rr_arbiter_n5.sby"])
def test_real_formal_proof_of_the_arbitration_rules(bridge, tmp_path, sby):
    run, _ = invoke(bridge, "formal.run", {"sby": str(ARB / sby)}, tmp_path)
    assert run.succeeded and "formal passed" in run.summary, run.summary
