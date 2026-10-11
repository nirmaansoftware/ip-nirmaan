"""Milestone 53: gate integrity (docs/GATE_INTEGRITY.md).

Each test here is an audit probe (audit B, 2026-10) turned into a check that
failed before M53: a real run whose pass did not mean what its gate claims.

* A simulation passes only on the testbench's own verdict, which carries the
  run's nonce; the design under test may not end the run or read the nonce.
* A bounded proof is reported as bounded, and the formal gate asks for a proof.
* A firmware verdict is the harness's, tagged with the run's nonce, and its
  counts must agree with what the harness saw on the bus.
* A run has its own directory and environment, and its timeout stops every
  process it started, across all of its steps.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from laws import needs

from nirmaan.integrations.eda import Backend, EdaResult, execute, select_backend
from nirmaan.integrations.eda_parsers import parse_simulation
from nirmaan.runtime.tools import unavailable_reason, within_bounds

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
GI = FIXTURES / "gate_integrity"
AXIL = RTL / "axi4_lite"
NONCE = "0123456789abcdef0123456789abcdef"
SIMULATORS = pytest.mark.parametrize("backend", [
    pytest.param("icarus", marks=needs("iverilog", "vvp")),
    pytest.param("verilator-sim", marks=needs("verilator")),
])


def sim(sources, top: str, backend: str, **extra):
    """A simulator.run through the real backend, as the broker runs it."""
    chosen, why = select_backend("simulator.run", {"backend": backend})
    assert chosen, why
    return execute(chosen, {"sources": ",".join(str(s) for s in sources), "top": top, "backend": backend, **extra})


def broken_axil(tmp_path: Path, finish: bool) -> Path:
    """The audit's F14 design: reads always return zero, and (with ``finish``) it ends every simulation at time 0."""
    text = (AXIL / "axi4_lite_regs.v").read_text()
    for reg in ("reg0", "reg1", "reg2", "reg3"):
        text = text.replace(f"s_axil_rdata <= {reg};", "s_axil_rdata <= {DATA_WIDTH{1'b0}};")
    if finish:
        text = text.replace("endmodule", "    // synthesis translate_off\n    initial $finish;\n"
                                         "    // synthesis translate_on\nendmodule")
    out = tmp_path / ("finish" if finish else "plain") / "axi4_lite_regs.v"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out


# --- F14: the design cannot end the run, and a pass needs the testbench's verdict -------------------


@SIMULATORS
def test_rtl_that_ends_the_simulation_fails_the_reference_testbench(tmp_path, backend):
    plain = sim([broken_axil(tmp_path, False), AXIL / "axi4_lite_regs_tb.v"], "axi4_lite_regs_tb", backend)
    assert not plain.succeeded  # the reference testbench catches the zero reads
    ended = sim([broken_axil(tmp_path, True), AXIL / "axi4_lite_regs_tb.v"], "axi4_lite_regs_tb", backend)
    assert not ended.succeeded, ended.summary
    assert "axi4_lite_regs.v uses $finish" in ended.summary and "nothing was simulated" in ended.summary


@SIMULATORS
def test_the_fixed_rtl_passes_the_reference_testbench_with_its_checks_counted(backend):
    run = sim([AXIL / "axi4_lite_regs.v", AXIL / "axi4_lite_regs_tb.v"], "axi4_lite_regs_tb", backend)
    assert run.succeeded and "298 checks passed" in run.summary, run.summary
    assert run.metrics["checks"] == 298 and run.metrics["checks_failed"] == 0


@SIMULATORS
def test_a_design_cannot_read_the_nonce(tmp_path, backend):
    rtl = tmp_path / "spy.v"
    rtl.write_text("module spy; reg [8*64-1:0] n; initial if ($value$plusargs(\"nirmaan_nonce=%s\", n))\n"
                   "  $display(\"NIRMAAN-SIM %0s 1 passed, 0 failed\", n); endmodule\n")
    tb = tmp_path / "tb.v"
    tb.write_text("module tb; spy s(); initial #1 $finish; endmodule\n")
    run = sim([rtl, tb], "tb", backend)
    assert not run.succeeded and "spy.v uses $value$plusargs" in run.summary


# --- F1, F2: words are not a verdict; $finish is the simulator's own line ------------------------------


@SIMULATORS
def test_a_testbench_that_reports_failure_in_words_fails(backend):
    run = sim([GI / "tb_display_fail.v"], "tb_display_fail", backend)
    assert not run.succeeded and "printed no verdict" in run.summary, run.summary


@needs("iverilog", "vvp")
def test_a_printed_finish_line_is_not_a_finish():
    run = sim([GI / "tb_fake_finish.v"], "tb_fake_finish", "icarus")
    assert not run.succeeded and "$finish never reached" in run.summary, run.summary


@needs("iverilog", "vvp")
def test_finish_with_an_argument_is_a_finish_on_icarus():
    result = parse_simulation("$ vvp -n sim.vvp +nirmaan_nonce=" + NONCE + "\n"
                              f"NIRMAAN-SIM {NONCE} 1 passed, 0 failed\ntb.v:4: $finish(2) called at 0 (1s)\n",
                              (0, 0), nonce=NONCE)
    assert result.passed and result.metrics["finished"], result.summary


def _log(*lines: str) -> str:
    return "\n".join(["$ vvp -n sim.vvp +nirmaan_nonce=" + NONCE, *lines, "tb.v:9: $finish called at 50 (1s)"]) + "\n"


def test_the_verdict_must_carry_the_runs_nonce_and_a_passing_check():
    ok = parse_simulation(_log(f"NIRMAAN-SIM {NONCE} 3 passed, 0 failed"), (0, 0), nonce=NONCE)
    assert ok.passed and ok.summary.startswith("simulation passed: 3 checks passed")
    for lines, why in (((), "printed no verdict"),
                       ((f"NIRMAAN-SIM {'f' * 32} 3 passed, 0 failed",), "without this run's nonce"),
                       ((f"NIRMAAN-SIM {NONCE} 0 passed, 0 failed",), "no check passed"),
                       ((f"NIRMAAN-SIM {NONCE} 2 passed, 1 failed",), "1 of 3 checks failed"),
                       ((f"NIRMAAN-SIM {NONCE} 2 passed, 0 failed",) * 2, "2 verdicts")):
        result = parse_simulation(_log(*lines), (0, 0), nonce=NONCE)
        assert not result.passed and why in result.summary, (lines, result.summary)


# --- F3, F16, F22, F9: the runner ------------------------------------------------------------------


def _shell(name: str, *scripts: str) -> Backend:
    """A backend whose steps are shell scripts: a stand-in for any tool, run by the real runner."""
    return Backend(name, "lint.run", ("sh",), lambda job: [["sh", "-c", s] for s in scripts],
                   lambda run: EdaResult(bool(run.returncodes) and run.returncode == 0, "ran"), ("sources",))


def test_a_timeout_below_one_second_is_refused():
    for bad in ("0", "-5"):
        reason = unavailable_reason("lint.run", {"sources": str(RTL / "counter.v"), "timeout": bad})
        assert reason and "timeout must be at least 1 second" in reason and "nothing ran" in reason
        outcome = execute(_shell("t", "true"), {"sources": str(RTL / "counter.v"), "timeout": bad})
        assert not outcome.succeeded and "at least 1 second" in outcome.summary


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()[:1] \
        not in ("", "Z")


def test_a_timeout_stops_every_process_the_step_started(tmp_path):
    backend = _shell("orphans", "sleep 300 & echo $! > child.pid; wait")
    started = time.monotonic()
    outcome = execute(backend, {"sources": str(RTL / "counter.v"), "timeout": "1", "workdir": str(tmp_path)})
    assert not outcome.succeeded and "timed out after 1s" in outcome.summary
    assert time.monotonic() - started < 15
    child = int((Path(outcome.references[0]).parent / "child.pid").read_text())
    time.sleep(0.2)
    assert not _alive(child), "the step's own child outlived the timeout"


def test_the_timeout_covers_the_whole_run(tmp_path):
    backend = _shell("steps", "sleep 0.8", "sleep 0.8", "sleep 0.8")
    outcome = execute(backend, {"sources": str(RTL / "counter.v"), "timeout": "2", "workdir": str(tmp_path)})
    assert not outcome.succeeded and "timed out after 2s" in outcome.summary, outcome.summary
    assert outcome.data["exit_statuses"] == [0, 0]  # the third step ran out of the run's time


def test_a_run_never_works_in_the_given_directory(tmp_path):
    keep = tmp_path / "stat.json"
    keep.write_text("not the run's")
    outcome = execute(_shell("del", "rm -f stat.json; echo $PWD"), {"sources": str(RTL / "counter.v"),
                                                                    "workdir": str(tmp_path)})
    assert outcome.succeeded and keep.read_text() == "not the run's"
    run_dir = Path(outcome.references[0]).parent
    assert run_dir.parent == tmp_path.resolve() and run_dir.name.startswith("nirmaan-del-")


def test_a_tool_run_sees_no_credential_and_has_its_own_temporary_directory(tmp_path, monkeypatch):
    secret = "sk-test-0123456789abcdefghij"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", secret)
    monkeypatch.setenv("SOME_API_KEY", secret + "x")
    outcome = execute(_shell("env", "env; echo printed=" + secret),
                      {"sources": str(RTL / "counter.v"), "workdir": str(tmp_path)})
    log = Path(outcome.references[0]).read_text()
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in log.replace("[CLAUDE_CODE_OAUTH_TOKEN redacted]", "")
    assert "SOME_API_KEY" not in log and secret not in log
    assert "printed=[CLAUDE_CODE_OAUTH_TOKEN redacted]" in log  # a value printed anyway never reaches the record
    run_dir = Path(outcome.references[0]).parent
    assert f"TMPDIR={run_dir / '.tmp'}" in log


@needs("verilator")
def test_two_builds_at_once_in_one_workdir_are_isolated(tmp_path):
    """The parallel-run flake: two Verilator builds at once, given the same directory, both pass."""
    results = {}

    def build(key: str) -> None:
        results[key] = sim([RTL / "counter.v", RTL / "counter_tb.v"], "counter_tb", "verilator-sim",
                           workdir=str(tmp_path))

    threads = [threading.Thread(target=build, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r.succeeded for r in results.values()), [r.summary for r in results.values()]
    dirs = {Path(r.references[0]).parent for r in results.values()}
    assert len(dirs) == 2 and all(d.parent == tmp_path.resolve() for d in dirs)


# --- F15, F17: a bounded check is not a proof ----------------------------------------------------------


@needs("sby", "yosys", "yices-smt2")
def test_bmc_is_reported_as_bounded_and_does_not_meet_the_formal_gate():
    from nirmaan.company.workflows import RTL_GATES

    gate = next(r for r in RTL_GATES if r.tools == ("formal.run",))
    formal, _ = select_backend("formal.run", {})
    bmc = execute(formal, {"sby": str(GI / "late_bmc.sby"), "sources": str(GI / "late.v")})
    assert bmc.succeeded and "no counterexample within 3 steps" in bmc.summary and "proven" not in bmc.summary
    assert bmc.metrics["mode"] == "bmc" and bmc.metrics["depth"] == 3 and bmc.metrics["proven"] == 0
    judged = within_bounds(bmc, gate.bounds)
    assert not judged.succeeded and "proven" in judged.summary
    prove = execute(formal, {"sby": str(GI / "late_prove.sby"), "sources": str(GI / "late.v")})
    assert not prove.succeeded  # the same false assertion, in prove mode
    counter = execute(formal, {"sby": str(RTL / "counter.sby")})
    assert counter.succeeded and counter.metrics["proven"] == 1 and within_bounds(counter, gate.bounds).succeeded


@needs("sby", "yosys")
def test_a_multi_task_setup_is_refused_with_a_reason():
    formal, _ = select_backend("formal.run", {})
    run = execute(formal, {"sby": str(GI / "tasks.sby")})
    assert not run.succeeded and "declares [tasks]" in run.summary and "nothing ran" in run.summary


@needs("sby", "yosys", "yices-smt2")
def test_a_formal_timeout_leaves_no_solver_running():
    formal, _ = select_backend("formal.run", {})
    run = execute(formal, {"sby": str(GI / "hard.sby"), "timeout": "3"})
    assert not run.succeeded and "timed out after 3s" in run.summary
    time.sleep(0.5)
    run_dir = str(Path(run.references[0]).parent)
    left = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout
    assert not [line for line in left.splitlines() if run_dir in line and "grep" not in line]

