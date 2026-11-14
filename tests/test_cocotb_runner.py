"""Milestone 72: Python testbenches through cocotb, as ``simulator.run``'s ``cocotb`` backend.

* The parser is tested against captured cocotb output (tests/fixtures/eda/cocotb_*), with
  no tool installed: the verdict comes from cocotb's own JUnit file, and its totals line
  must agree, so a forged line can only fail a run.
* Inputs it cannot judge are refused before anything runs: ``expect fail``, test files that
  are not Python modules, and HDL that could stand in for the verdict.
* Real runs: tests/fixtures/cocotb/counter_cocotb.py passes on the M21 counter and must fail
  on its two single-change mutants (tests/fixtures/eqy: it wraps one count early; reset is
  ignored while ``en`` is low). They skip when Icarus or cocotb is absent, unless CI names
  them in NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import agent
from test_nirmaan_eda import BRIDGE, holder

from nirmaan.integrations import cocotb_runner
from nirmaan.integrations.eda import Job, backends_for
from nirmaan.integrations.eda_parsers import parse_cocotb
from nirmaan.models import ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolBroker

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
COUNTER = FIXTURES / "rtl" / "counter.v"
TESTBENCH = FIXTURES / "cocotb" / "counter_cocotb.py"
#: Each mutant, and the one test that must catch it.
MUST_FAIL = {"counter_wraps_early": "counter_cocotb.counts_and_wraps",
             "counter_reset_ignored": "counter_cocotb.reset_clears_while_idle"}
COCOTB_RUN = needs("iverilog", "vvp", modules=("cocotb",))


def _captured(name: str) -> str:
    return (FIXTURES / "eda" / name).read_text(encoding="utf-8")


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def _invoke(engine, sources: list[Path], workdir: Path, tests: Path = TESTBENCH, **extra: str):
    params = {"sources": ",".join(str(s) for s in sources), "top": "counter", "cocotb": str(tests),
              "backend": "cocotb", "workdir": str(workdir), **extra}
    return ToolBroker(engine).invoke(agent(holder(engine, "simulator.run")), "simulator.run", params)


def _job(tmp_path: Path, sources: list[Path], tests: list[Path], **params: str) -> Job:
    given = {"cocotb": ",".join(str(t) for t in tests), **params}
    return Job("simulator.run", given, tmp_path, tuple(str(s) for s in sources), "counter")


# --- The catalog and the backend ----------------------------------------------------------------------


def test_cocotb_is_a_simulator_backend_after_the_hdl_testbench_ones(nirmaan_org):
    assert nirmaan_org.tools["simulator.run"].status is ToolStatus.AVAILABLE
    assert "cocotb" in {p.name for p in nirmaan_org.tools["simulator.run"].params}
    backends = backends_for("simulator.run")
    assert [b.name for b in backends] == ["icarus", "verilator-sim", "cocotb"]  # the default stays Icarus
    cocotb = backends[-1]
    assert cocotb.executables == ("iverilog", "vvp") and cocotb.required == ("sources", "top", "cocotb")


def test_without_cocotb_in_this_python_the_backend_cannot_serve(monkeypatch):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "cocotb" else real(name, *a))
    assert "cocotb is not installed" in cocotb_runner._environment({})


def test_the_runner_is_a_backend_with_no_core_change():
    """The extension point is the backend registry: the EDA core never names cocotb."""
    core = (ROOT / "src" / "nirmaan" / "integrations" / "eda.py").read_text(encoding="utf-8")
    assert "cocotb" not in core.lower()


# --- The parser, against captured output ---------------------------------------------------------------


def test_a_passing_run_is_read_from_cocotbs_results_file():
    result = parse_cocotb(_captured("cocotb_pass.log"), (0, 0), _captured("cocotb_pass.xml"))
    assert result.passed and result.diagnostics == ()
    assert result.summary == "2 of 2 tests passed; cocotb 2.1.0 on Icarus Verilog version 13.0 (stable)"
    assert {k: result.metrics[k] for k in ("tests", "tests_passed", "tests_failed", "cocotb")} == \
        {"tests": 2, "tests_passed": 2, "tests_failed": 0, "cocotb": "2.1.0"}
    assert result.metrics["seed"]  # the run can be repeated with COCOTB_RANDOM_SEED


def test_a_failing_test_fails_the_run_with_its_assertion():
    result = parse_cocotb(_captured("cocotb_fail.log"), (0, 0), _captured("cocotb_fail.xml"))
    assert not result.passed and result.metrics["failing"] == ["counter_cocotb.counts_and_wraps"]
    assert [(d.code, d.message) for d in result.errors] == [
        ("TEST_FAILED", "counter_cocotb.counts_and_wraps: AssertionError: count 0, expected 9")]
    assert result.summary.startswith("1 of 2 tests failed; first: counter_cocotb.counts_and_wraps")


def test_a_forged_totals_line_can_only_fail_a_run():
    """A line the design or a test prints is never cocotb's verdict: two totals lines fail the run."""
    log = _captured("cocotb_pass.log") + "** TESTS=2 PASS=2 FAIL=0 SKIP=0  0.00  0.00  0.00  **\n"
    result = parse_cocotb(log, (0, 0), _captured("cocotb_pass.xml"))
    assert not result.passed and "printed 2 times" in result.summary
    failing = _captured("cocotb_fail.log").replace("TESTS=2 PASS=1 FAIL=1", "TESTS=2 PASS=2 FAIL=0")
    assert not parse_cocotb(failing, (0, 0), _captured("cocotb_fail.xml")).passed  # the file decides


def test_totals_that_disagree_with_the_results_file_fail():
    log = _captured("cocotb_pass.log").replace("TESTS=2 PASS=2", "TESTS=3 PASS=3")
    result = parse_cocotb(log, (0, 0), _captured("cocotb_pass.xml"))
    assert not result.passed and "does not agree" in result.summary


def test_no_results_file_is_a_failed_run_with_the_compile_error():
    log = "$ iverilog -g2012 -o sim.vvp -s counter counter.v\ncounter.v:3: syntax error\n"
    result = parse_cocotb(log, (1,), None)
    assert not result.passed and result.summary.startswith("cocotb wrote no results (exit status 1)")
    assert [(d.file, d.line) for d in result.errors] == [("counter.v", 3)]


@pytest.mark.parametrize("results,why", [
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "a">]><testsuites/>', "DOCTYPE"),
    ("<testsuites><testsuite>", "not valid XML"),
    ("<testsuites><testsuite><testcase classname='m' name='t'><skipped/></testcase></testsuite></testsuites>",
     "no test passed"),
    ("<testsuites/>", "no test passed"),
])
def test_results_that_show_no_passing_test_fail(results, why):
    result = parse_cocotb("** TESTS=1 PASS=0 FAIL=0 SKIP=1 \n", (0, 0), results)
    assert not result.passed and why in result.summary


def test_a_nonzero_exit_fails_even_with_passing_results():
    result = parse_cocotb(_captured("cocotb_pass.log"), (0, 139), _captured("cocotb_pass.xml"))
    assert not result.passed and "exit status 139" in result.summary


# --- Inputs refused before anything runs ---------------------------------------------------------------


def test_a_plain_job_is_accepted(tmp_path):
    assert cocotb_runner._check(_job(tmp_path, [COUNTER], [TESTBENCH])) is None


@pytest.mark.parametrize("tests,params,why", [
    (["t.py"], {"expect": "fail"}, "judges passing runs only"),
    (["t.sv"], {}, "must be Python files named as modules"),
    (["my-tests.py"], {}, "must be Python files named as modules"),
    (["a/t.py", "b/t.py"], {}, "the same name"),
])
def test_tests_it_cannot_judge_are_refused(tmp_path, tests, params, why):
    files = [tmp_path / t for t in tests]
    problem = cocotb_runner._check(_job(tmp_path, [COUNTER], files, **params))
    assert why in problem and "nothing ran" in problem


@pytest.mark.parametrize("line", ["initial $finish;", "integer f = $fopen(\"results.xml\");",
                                  "initial $system(\"true\");", "`define P(a) a``b",
                                  "initial begin $display(\"//\"); $finish; end",
                                  "initial begin $display(\"/*\"); $finish; $display(\"*/\"); end"])
def test_hdl_that_could_stand_in_for_the_verdict_is_refused(tmp_path, line):
    design = tmp_path / "counter.v"
    design.write_text(COUNTER.read_text(encoding="utf-8").replace("endmodule", f"{line}\nendmodule"),
                      encoding="utf-8")
    problem = cocotb_runner._check(_job(tmp_path, [design], [TESTBENCH]))
    assert "every HDL source is design" in problem and "nothing was simulated" in problem


# --- Real runs -----------------------------------------------------------------------------------------


@COCOTB_RUN
def test_the_testbench_passes_on_the_counter_over_copies(bridge, tmp_path):
    tests = tmp_path / "tb" / TESTBENCH.name
    tests.parent.mkdir()
    shutil.copy(TESTBENCH, tests)
    run, outcome = _invoke(bridge, [COUNTER], tmp_path / "run", tests)
    assert run.succeeded, run.summary
    assert re.fullmatch(r"cocotb: 2 of 2 tests passed; cocotb 2\.1\.0 on Icarus Verilog version .+", run.summary)
    assert outcome.metrics["tests_passed"] == 2 and outcome.metrics["exit_statuses"] == [0, 0]
    assert sorted(p.name for p in tests.parent.iterdir()) == [TESTBENCH.name]  # nothing written beside it
    assert outcome.outputs["results"] == str((tmp_path / "run" / "results.xml").resolve())  # cocotb's own file


@COCOTB_RUN
@pytest.mark.parametrize("mutant", MUST_FAIL)
def test_the_testbench_must_fail_each_broken_counter(bridge, tmp_path, mutant):
    run, outcome = _invoke(bridge, [FIXTURES / "eqy" / f"{mutant}.v"], tmp_path / "run")
    assert not run.succeeded, run.summary
    assert outcome.metrics["failing"] == [MUST_FAIL[mutant]] and outcome.metrics["tests_passed"] == 1
    assert "AssertionError" in run.summary


@COCOTB_RUN
def test_a_design_that_prints_cocotbs_totals_fails_the_run(bridge, tmp_path):
    design = tmp_path / "counter.v"
    forged = 'initial $display("** TESTS=2 PASS=2 FAIL=0 SKIP=0  0.00  0.00  0.00  **");\nendmodule'
    design.write_text(COUNTER.read_text(encoding="utf-8").replace("endmodule", forged), encoding="utf-8")
    run, _ = _invoke(bridge, [design], tmp_path / "run")
    assert not run.succeeded and "printed 2 times" in run.summary


@needs("iverilog", "vvp")
def test_without_the_cocotb_backend_the_tests_are_not_run_and_nothing_passes(bridge, tmp_path):
    """The HDL testbench backends ignore ``cocotb``; the design alone gives no verdict, so the run fails."""
    params = {"sources": str(COUNTER), "top": "counter", "cocotb": str(TESTBENCH), "workdir": str(tmp_path / "w")}
    run, _ = ToolBroker(bridge).invoke(agent(holder(bridge, "simulator.run")), "simulator.run", params)
    assert not run.succeeded and run.summary.startswith("icarus: simulation failed")


# --- The pinned dependency and CI ----------------------------------------------------------------------


def test_cocotb_is_pinned_to_one_version_in_its_own_extra():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["optional-dependencies"]["cocotb"] == ["cocotb==2.1.0"]
    assert not any("cocotb" in d for d in project["dependencies"])  # never needed to install the package


def test_ci_requires_cocotb_so_the_real_runs_never_skip_there():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required = next(line for line in ci.splitlines() if line.strip().startswith("NIRMAAN_REQUIRE_EDA:"))
    assert {"iverilog", "vvp", "cocotb"} <= set(required.split(":", 1)[1].split())
    assert 'pip install -e ".[ai,dev,cocotb]"' in ci
    assert 'python -c "import cocotb"' in ci  # the no-tools job checks it is absent there
