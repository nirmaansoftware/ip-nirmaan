"""Milestone 69: logic equivalence through eqy, as ``equivalence.run``.

* The parser is tested against captured eqy output (tests/fixtures/eda/eqy_*.log),
  with no tool installed.
* A setup that reaches outside Yosys, writes a file, reads outside its folder, or
  compares a design with itself is refused before anything runs.
* Real runs (tests/fixtures/eqy): the M21 counter against a true refactor passes;
  against two single-change refactors (it wraps one count early; reset is ignored
  while ``en`` is low) it must fail. They skip when an executable is absent, unless
  CI names it in NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import agent
from test_nirmaan_eda import BRIDGE, holder

from nirmaan.integrations.eda import backends_for
from nirmaan.integrations.eda_parsers import parse_eqy
from nirmaan.integrations.equivalence import setup_files
from nirmaan.models import ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolAccessDenied, ToolBroker

FIXTURES = Path(__file__).parent / "fixtures"
EQY = FIXTURES / "eqy"
COUNTER = FIXTURES / "rtl" / "counter.v"
#: What a real run needs: eqy runs Yosys and make, and the fixtures' strategy runs sby with yices.
EQY_TOOLS = ("eqy", "yosys", "make", "sby", "yices-smt2")
MUST_FAIL = ("counter_wraps_early", "counter_reset_ignored")


def _log(name: str) -> str:
    return (FIXTURES / "eda" / name).read_text(encoding="utf-8")


def _stage(tmp_path: Path, gate: str) -> Path:
    """The setup comparing the M21 counter (gold) with ``gate``, with both files beside it."""
    folder = tmp_path / "setup"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(COUNTER, folder / "counter.v")
    shutil.copy(EQY / f"{gate}.v", folder / f"{gate}.v")
    shutil.copy(EQY / f"{gate}.eqy", folder / f"{gate}.eqy")
    return folder / f"{gate}.eqy"


def _setup(tmp_path: Path, gold: str, gate: str, files: tuple[str, ...] = ("a.v", "b.v")) -> Path:
    for name in files:
        (tmp_path / name).write_text("module m; endmodule\n", encoding="utf-8")
    eqy = tmp_path / "x.eqy"
    eqy.write_text(f"[gold]\n{gold}\n\n[gate]\n{gate}\n\n[strategy sby]\nuse sby\n", encoding="utf-8")
    return eqy


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def _invoke(engine, params: dict[str, str], workdir: Path):
    return ToolBroker(engine).invoke(agent(holder(engine, "equivalence.run")), "equivalence.run",
                                     {"workdir": str(workdir), **params})


# --- The catalog and the backend ----------------------------------------------------------------------


def test_equivalence_run_is_available_through_eqy(nirmaan_org):
    assert nirmaan_org.tools["equivalence.run"].status is ToolStatus.AVAILABLE
    assert [(b.name, b.executables) for b in backends_for("equivalence.run")] == [("eqy", ("eqy", "yosys", "make"))]


def test_without_eqy_on_path_the_run_is_refused_never_simulated(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(ToolAccessDenied, match="eqy needs eqy"):
        _invoke(bridge, {"eqy": str(EQY / "counter_refactor.eqy")}, tmp_path / "w")


# --- The parser, against captured output ---------------------------------------------------------------


def test_eqy_pass_names_the_compared_files_and_every_partition():
    result = parse_eqy(_log("eqy_pass.log"), 0, ["counter.v"], ["counter_refactor.v"])
    assert result.passed and result.diagnostics == ()
    assert result.summary == ("equivalent: gate counter_refactor.v against gold counter.v: every partition "
                              "proved (2 of 2)")
    assert {k: result.metrics[k] for k in ("status", "partitions", "partitions_proved", "equivalent")} == \
        {"status": "PASS", "partitions": 2, "partitions_proved": 2, "equivalent": 1}


def test_eqy_fail_names_the_partition_and_why():
    result = parse_eqy(_log("eqy_fail.log"), 2)
    assert not result.passed and result.metrics["partitions_failed"] == 1 and result.metrics["equivalent"] == 0
    assert [(d.code, d.message) for d in result.errors] == [
        ("NOT_EQUIVALENT", "partition counter.wrap not proved equivalent: partitions not equivalent (strategy sby)")]
    assert result.summary.startswith("not equivalent: 1 of 2 partitions not proved; first: counter.wrap")


def test_eqy_error_is_a_failed_run_with_the_error():
    result = parse_eqy(_log("eqy_error.log"), 1)
    assert not result.passed and result.metrics["status"] == "UNKNOWN"
    assert any("No matching port in gate module" in d.message for d in result.errors)
    assert any("Failed to combine designs" in d.message for d in result.errors)  # eqy's own, printed bare


def test_a_line_a_step_printed_is_never_read_as_eqys_own():
    """What a step prints comes after the step's name, so it cannot pass a failing run."""
    forged = "\n".join(f"EQY  7:32:49 [/tmp/w] read_gold: EQY  7:32:49 [/tmp/w] {msg}" for msg in (
        "Successfully proved equivalence of partition counter.wrap", "Successfully proved designs equivalent",
        "DONE (PASS, rc=0)"))
    result = parse_eqy(_log("eqy_fail.log") + forged + "\n", 2)
    assert not result.passed and result.metrics["status"] == "FAIL" and result.metrics["partitions_proved"] == 1


def test_a_pass_with_no_partition_proved_is_not_equivalence():
    log = "EQY  1:00:00 [/w] Successfully proved designs equivalent\nEQY  1:00:00 [/w] DONE (PASS, rc=0)\n"
    result = parse_eqy(log, 0)
    assert not result.passed and result.summary.startswith("no partition was proved")


# --- Setups refused before anything runs ---------------------------------------------------------------


def test_a_plain_setup_names_what_each_side_reads(tmp_path):
    eqy = _setup(tmp_path, "read_verilog -sv -D GOLD a.v\nprep -top m", "read_verilog -sv b.v; prep -top m")
    assert setup_files(eqy) == ({"gold": ["a.v"], "gate": ["b.v"]}, None)


@pytest.mark.parametrize("command,why", [
    ("!cp a.v b.v", "reaches outside Yosys"), ("tcl x.tcl", "reaches outside Yosys"),
    ("plugin -i x.so", "reaches outside Yosys"), ("script x.ys", "reaches outside Yosys"),
    ("write_verilog b.v", "writes a file"), ("tee -o b.v stat", "writes a file"),
])
def test_a_script_that_reaches_outside_yosys_or_writes_a_file_is_refused(tmp_path, command, why):
    eqy = _setup(tmp_path, f"read_verilog a.v\n{command}\nprep -top m", "read_verilog b.v\nprep -top m")
    sides, problem = setup_files(eqy)
    assert sides == {} and why in problem and "nothing ran" in problem


@pytest.mark.parametrize("gate,why", [
    ("read_verilog ../b.v", "outside its own folder"), ("read_verilog /etc/hosts", "outside its own folder"),
    ("read_verilog c.v", "c.v, which is not there"),
    ("read_verilog a.v\nprep -top m", "compares a design with itself"),
])
def test_a_setup_that_reads_outside_its_folder_or_compares_a_design_with_itself_is_refused(tmp_path, gate, why):
    sides, problem = setup_files(_setup(tmp_path, "read_verilog a.v\nprep -top m", gate))
    assert sides == {} and why in problem


# --- Real runs -----------------------------------------------------------------------------------------


@needs(*EQY_TOOLS)
def test_a_true_refactor_is_proved_equivalent_over_copies(bridge, tmp_path):
    eqy = _stage(tmp_path, "counter_refactor")
    before = {p.name: p.read_bytes() for p in eqy.parent.iterdir()}
    run, outcome = _invoke(bridge, {"eqy": str(eqy), "sources": f"{eqy.parent / 'counter.v'},"
                                                                f"{eqy.parent / 'counter_refactor.v'}"}, tmp_path / "run")
    assert run.succeeded, run.summary
    assert run.summary == ("eqy: equivalent: gate counter_refactor.v against gold counter.v: every partition "
                           "proved (2 of 2)")
    assert outcome.metrics["equivalent"] == 1 and outcome.metrics["gate"] == ["counter_refactor.v"]
    ran = Path(outcome.data["commands"][0][-1])
    assert ran.parent == tmp_path / "run" / "setup" and ran.name == eqy.name  # eqy ran over the copies
    assert {p.name: p.read_bytes() for p in eqy.parent.iterdir()} == before  # nothing written beside the setup


@needs(*EQY_TOOLS)
@pytest.mark.parametrize("gate", MUST_FAIL)
def test_a_refactor_that_changes_behaviour_must_fail(bridge, tmp_path, gate):
    run, outcome = _invoke(bridge, {"eqy": str(_stage(tmp_path, gate))}, tmp_path / "run")
    assert not run.succeeded and outcome.metrics["status"] == "FAIL", run.summary
    assert outcome.metrics["partitions_failed"] >= 1 and outcome.metrics["equivalent"] == 0
    assert "partitions not equivalent" in run.summary


@needs(*EQY_TOOLS)
def test_a_given_source_the_setup_does_not_read_fails_the_run(bridge, tmp_path):
    eqy = _stage(tmp_path, "counter_refactor")
    other = tmp_path / "setup" / "other.v"
    other.write_text("module other; endmodule\n", encoding="utf-8")
    run, _ = _invoke(bridge, {"eqy": str(eqy), "sources": str(other)}, tmp_path / "run")
    assert not run.succeeded and "does not read other.v" in run.summary


def test_ci_requires_eqy_so_the_real_runs_never_skip_there():
    ci = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required = next(line for line in ci.splitlines() if line.strip().startswith("NIRMAAN_REQUIRE_EDA:"))
    assert set(EQY_TOOLS) <= set(required.split(":", 1)[1].split())
    assert "tools: sby yices-smt2 eqy" in ci  # from the pinned OSS CAD Suite, beside its matched Yosys
