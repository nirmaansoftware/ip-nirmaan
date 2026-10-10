"""Milestone 35: interrupts in host co-simulation, and precise bus-error traps.

* ``fw.test`` implements ``nirmaan_irq.h`` from the design's own ``irq``
  output, so the M29 timer tests run in host co-simulation as on both cores,
  and fail on the same broken IRQs.
* A bus-fault handler (``nirmaan_bus_fault_attach``) is called precisely: in
  host co-simulation before the failing access returns, and on PicoRV32 at
  the instruction boundary right after the faulting load or store, with its
  address checked against the run's own image. SERV says it cannot.
* ``require_irq`` and ``require_bus_error_trap`` make the interrupt and the
  trap gate data.
Real-tool tests skip when an executable is absent, or fail when CI names it in
NIRMAAN_REQUIRE_EDA. See docs/FIRMWARE_IRQ_TRAPS.md.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_nirmaan_firmware import COSIM, DRIVER, RTL, TESTS, WITH_DRIVER, invoke, joined, needs
from test_nirmaan_riscv_firmware import ON_RISCV, SOC_TOOLS
from test_nirmaan_riscv_firmware import needs as needs_riscv
from test_nirmaan_riscv_next import TIMER, TIMER_CHECKS, TIMER_FW, TIMER_RTL, WRAPPER, broken_timer, checks_of

from nirmaan.integrations.firmware import parse_fw_test
from nirmaan.integrations.firmware_riscv import CORES, SOC, Core, register_core, toolchain, unregister_core
from nirmaan.orchestrator import Orchestrator

FAULT = (*TIMER[:3], TIMER_FW / "axil_timer_fault_test.c")
FAULT_CHECKS = {"bus_errors_are_reported_per_access", "unmapped_read_traps_precisely", "failed_writes_trap_precisely",
                "okay_accesses_do_not_trap", "a_detached_handler_gets_no_traps"}
TRAP_CHECKS = {"unmapped_read_traps_precisely", "failed_writes_trap_precisely", "okay_accesses_do_not_trap"}
#: The traps the fault tests cause, in order: (direction, offset).
TRAPS = [("read", 0x5), ("write", 0x8), ("write", 0xE)]


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(WITH_DRIVER)


@pytest.fixture()
def riscv(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(ON_RISCV)


def cosim(block, sources, rtl, workdir: Path, **params):
    return invoke(block, "fw.test", {"sources": joined(*sources), "rtl": str(rtl), **params}, workdir)


def soc(block, sources, rtl, workdir: Path, **params):
    return invoke(block, "fw.soc_test", {"sources": joined(*sources), "rtl": str(rtl), **params}, workdir)


def log_of(run) -> str:
    return Path(run.references[0]).read_text()


def traps_of(outcome) -> list[tuple[str, int]]:
    return [(t["access"], t["offset"]) for t in outcome.data["result"]["metrics"]["traps"]]


def firmware_requirements(engine):
    task = engine.task(next(t for t in engine.state.tasks if engine.state.tasks[t].stage == "firmware"))
    return {(r.tools[0], tuple(sorted(dict(r.params)))): r for r in task.evidence_requirements if r.tools}


# --- The parser (no tool needed) --------------------------------------------------------------

HOST_LOG = """\
FWTEST BUS write 0x0 = 0x00000003 strobe 0xf -> OKAY
FWTEST IRQ taken
FWTEST BUS read 0x5 -> 0x00000000 SLVERR
FWTEST TRAP bus-error read 0x5 SLVERR
FWTEST TRAP bus-error write 0xe SLVERR at pc 0x000004c4
FWTEST PASS interrupt_fires_and_is_handled
FWTEST SUMMARY 1 passed, 0 failed, 40 cycles
"""


def test_the_parser_counts_interrupts_taken_and_traps_delivered():
    result = parse_fw_test(HOST_LOG, (0,))
    assert result.passed, result.summary
    assert result.metrics["irq_taken"] == 1 and result.metrics["bus_error_traps"] == 2
    assert result.metrics["traps"] == [
        {"access": "read", "offset": 0x5, "response": "SLVERR", "pc": None},
        {"access": "write", "offset": 0xE, "response": "SLVERR", "pc": 0x4C4},
    ]


def test_a_required_interrupt_or_trap_that_never_happened_fails_the_run(tmp_path):
    quiet = "FWTEST PASS reset_values\nFWTEST SUMMARY 1 passed, 0 failed, 10 cycles\n"
    assert parse_fw_test(quiet, (0,), require={"irq": False, "bus_error_trap": False}).passed
    result = parse_fw_test(quiet, (0,), require={"irq": True, "bus_error_trap": False})
    assert not result.passed and "require_irq" in result.summary and "no interrupt was taken" in result.summary
    result = parse_fw_test(quiet, (0,), require={"irq": False, "bus_error_trap": True})
    assert not result.passed and "require_bus_error_trap" in result.summary
    assert parse_fw_test(HOST_LOG, (0,), require={"irq": True, "bus_error_trap": True}).passed


# --- Contracts and the gate, as data ----------------------------------------------------------


def test_the_new_parameters_are_declared(nirmaan_org):
    for tool in ("fw.test", "fw.soc_test"):
        spec = nirmaan_org.tools[tool]
        assert spec.param("require_irq") and spec.param("require_bus_error_trap"), tool


def test_the_gate_requires_the_interrupt_when_the_design_has_one(block, riscv):
    assert dict(firmware_requirements(block)[("fw.test", ("require_irq",))].params) == {"require_irq": "auto"}
    reqs = firmware_requirements(riscv)
    assert dict(reqs[("fw.soc_test", ("require_irq",))].params) == {"require_irq": "auto"}
    assert not any(t == "fw.soc_test" and "require_bus_error_trap" in p for t, p in reqs)


def test_the_gate_requires_interrupts_and_traps_when_the_request_asks(nirmaan_org, fixed_clock):
    asked = Orchestrator(nirmaan_org, clock=fixed_clock).plan(
        "Create an AXI4-Lite register block with an interrupt and its driver for a RISC-V core, "
        "with precise bus error traps.")
    reqs = firmware_requirements(asked)
    assert dict(reqs[("fw.test", ("require_irq",))].params) == {"require_irq": "yes"}
    assert dict(reqs[("fw.soc_test", ("require_irq",))].params) == {"require_irq": "yes"}
    trap = reqs[("fw.soc_test", ("require_bus_error_trap",))]
    assert dict(trap.params) == {"require_bus_error_trap": "yes"} and trap.before_review


# --- Interrupts in host co-simulation ---------------------------------------------------------


@needs(*COSIM)
def test_the_timer_interrupt_fires_is_acknowledged_and_masked_in_host_cosim(block, tmp_path):
    run, outcome = cosim(block, TIMER, TIMER_RTL, tmp_path, require_irq="auto")
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(TIMER_CHECKS, True)
    log = log_of(run)
    assert "-DNIRMAAN_DUT_IRQ" in log
    # Taken twice: once on expiry, once on unmasking the pending expiry; never while masked.
    assert outcome.data["result"]["metrics"]["irq_taken"] == 2
    assert "FWTEST BUS write 0xc = 0x00000001 strobe 0xf -> OKAY" in log  # the W1C acknowledgement, on the RTL
    assert "FWTEST BUS write 0x8 = 0x00000005 strobe 0xf -> SLVERR" in log


@needs(*COSIM)
@pytest.mark.parametrize("irq, failing", [
    ("1'b0", {"interrupt_fires_and_is_handled", "interrupt_is_acknowledged_by_a_register_write",
              "unmasking_a_pending_interrupt_fires_it"}),
    ("expired", {"masked_interrupt_does_not_fire", "unmasking_a_pending_interrupt_fires_it"}),
])
def test_a_broken_irq_is_caught_in_host_cosim(block, tmp_path, irq, failing):
    run, outcome = cosim(block, TIMER, broken_timer(tmp_path, irq), tmp_path / "run")
    assert not run.succeeded and run.id in block.state.tool_runs
    checks = checks_of(outcome)
    assert {name for name, ok in checks.items() if not ok} == failing
    assert set(checks) == TIMER_CHECKS


@needs(*COSIM)
def test_the_wrong_timer_driver_fails_in_host_cosim(block, tmp_path):
    """IE at bit 2 instead of bit 1: it compiles, and only the RTL shows the interrupt is never enabled."""
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    for path in TIMER:
        shutil.copy(path, wrong / path.name)
    header = wrong / "axil_timer_map.h"
    header.write_text(header.read_text().replace("AXIL_TIMER_CTRL_IE 0x2u", "AXIL_TIMER_CTRL_IE 0x4u"))
    run, outcome = cosim(block, tuple(wrong / p.name for p in TIMER), TIMER_RTL, tmp_path / "run")
    assert not run.succeeded and "interrupt_fires_and_is_handled" in run.summary
    assert {n for n, ok in checks_of(outcome).items() if not ok} == {
        "interrupt_fires_and_is_handled", "interrupt_is_acknowledged_by_a_register_write",
        "unmasking_a_pending_interrupt_fires_it"}
    assert "FWTEST BUS write 0x0 = 0x00000005 strobe 0xf -> OKAY" in log_of(run)  # EN and the wrong IE bit


@needs(*COSIM)
def test_require_irq_is_checked_against_the_design_and_the_run(block, tmp_path):
    # A design with no irq: "auto" asks nothing of it; "yes" is a recorded failed run before anything runs.
    run, _ = cosim(block, (*DRIVER, TESTS), RTL, tmp_path / "auto", require_irq="auto")
    assert run.succeeded, run.summary
    run, _ = cosim(block, (*DRIVER, TESTS), RTL, tmp_path / "yes", require_irq="yes")
    assert not run.succeeded and run.id in block.state.tool_runs
    assert "require_irq=yes" in run.summary and "no irq output" in run.summary
    # A design with an irq whose tests never take it: every check passes, and the gate still fails it.
    run, outcome = cosim(block, FAULT, TIMER_RTL, tmp_path / "never", require_irq="auto")
    assert outcome.data["result"]["metrics"]["passed"] == len(FAULT_CHECKS)
    assert not run.succeeded and "no interrupt was taken" in run.summary
    run, _ = cosim(block, TIMER, TIMER_RTL, tmp_path / "bad", require_irq="sometimes")
    assert not run.succeeded and "require_irq must be auto, yes, or no" in run.summary


# --- Precise bus errors -----------------------------------------------------------------------


@needs(*COSIM)
def test_bus_errors_are_reported_per_access_and_trap_precisely_in_host_cosim(block, tmp_path):
    run, outcome = cosim(block, FAULT, TIMER_RTL, tmp_path, require_bus_error_trap="yes")
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(FAULT_CHECKS, True)
    assert traps_of(outcome) == TRAPS
    assert all(t["pc"] is None for t in outcome.data["result"]["metrics"]["traps"])
    # Each trap line follows the transfer that caused it, before any other transfer.
    lines = [line for line in log_of(run).splitlines() if line.startswith(("FWTEST BUS", "FWTEST TRAP"))]
    for i, line in enumerate(lines):
        if line.startswith("FWTEST TRAP"):
            assert lines[i - 1].endswith("SLVERR"), lines[i - 1]


def _instruction_at(elf: Path, pc: int) -> tuple[str, str]:
    """The function and mnemonic at ``pc`` in ``elf``, by the toolchain's own disassembler."""
    text = subprocess.run([toolchain() + "objdump", "-d", str(elf)], capture_output=True, text=True,
                          check=True).stdout
    function = ""
    for line in text.splitlines():
        if m := re.match(r"^[0-9a-f]+ <([^>]+)>:$", line):
            function = m[1]
        elif (m := re.match(r"^\s*([0-9a-f]+):\s+[0-9a-f]+\s+(\S+)", line)) and int(m[1], 16) == pc:
            return function, m[2]
    raise AssertionError(f"no instruction at 0x{pc:x}")


def assert_precise(run, outcome, workdir: Path):
    traps = outcome.data["result"]["metrics"]["traps"]
    assert [(t["access"], t["offset"]) for t in traps] == TRAPS
    elf = workdir / "rv32" / "firmware.elf"
    for trap in traps:
        function, mnemonic = _instruction_at(elf, trap["pc"])
        if trap["access"] == "read":
            assert (function, mnemonic) == ("soc_read32", "lw"), trap
        else:
            assert function in ("store", "soc_write32") and mnemonic in ("sw", "sh", "sb"), trap


@needs_riscv(*SOC_TOOLS, riscv=True)
def test_a_bus_error_traps_precisely_on_picorv32(riscv, tmp_path):
    run, outcome = soc(riscv, FAULT, TIMER_RTL, tmp_path, require_bus_error_trap="yes")
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(FAULT_CHECKS, True)
    assert "+define+NIRMAAN_CORE_BUS_ERR" in log_of(run)
    assert_precise(run, outcome, tmp_path)


@needs_riscv(*SOC_TOOLS, riscv=True)
def test_serv_says_it_has_no_precise_trap(riscv, tmp_path):
    run, outcome = soc(riscv, FAULT, TIMER_RTL, tmp_path, core="serv", require_bus_error_trap="yes")
    assert not run.succeeded
    checks = checks_of(outcome)
    assert {n for n, ok in checks.items() if not ok} == TRAP_CHECKS
    assert checks["bus_errors_are_reported_per_access"]  # the response codes still arrive per access
    assert "this platform has no precise bus-error trap" in log_of(run)
    assert "NIRMAAN_CORE_BUS_ERR" not in log_of(run)


@needs_riscv(*SOC_TOOLS, riscv=True)
def test_interrupts_still_work_with_the_bus_error_line_on_picorv32(riscv, tmp_path):
    run, outcome = soc(riscv, TIMER, TIMER_RTL, tmp_path, require_irq="yes")
    assert run.succeeded, run.summary
    assert outcome.data["result"]["metrics"]["irq_taken"] == 2


@needs(*COSIM)
def test_a_design_that_hides_its_errors_fails_the_trap_checks(block, tmp_path):
    """Unmapped reads answered OKAY: the per-access check and the read trap both catch it."""
    text = TIMER_RTL.read_text()
    hidden = text.replace("s_axil_rresp <= RESP_SLVERR;", "s_axil_rresp <= RESP_OKAY;")
    assert hidden != text
    path = tmp_path / "hidden" / "axil_timer.v"
    path.parent.mkdir()
    path.write_text(hidden)
    run, outcome = cosim(block, FAULT, path, tmp_path / "run")
    assert not run.succeeded
    failed = {n for n, ok in checks_of(outcome).items() if not ok}
    assert {"bus_errors_are_reported_per_access", "unmapped_read_traps_precisely"} <= failed


# --- Crown jewel: a core with a bus-error line is data ----------------------------------------


@needs_riscv(*SOC_TOOLS, riscv=True)
def test_a_new_bus_error_core_needs_no_core_changes(riscv, tmp_path):
    """M29's third core, given a bus-error input, registered with bus_error=True: precise traps on it."""
    wrapper = tmp_path / "third" / "core_picorv32_barrel.v"
    wrapper.parent.mkdir()
    text = WRAPPER.replace("    input wire irq\n", "    input wire irq, input wire bus_err\n")
    text = text.replace(".irq({28'b0, irq, 3'b0})", ".irq({27'b0, bus_err, irq, 3'b0})")
    text = text.replace(".LATCHED_IRQ(32'hffff_fff7)", ".LATCHED_IRQ(32'hffff_ffe7)")
    assert text.count("bus_err") == 2 and "ffe7" in text
    wrapper.write_text(text)
    register_core(Core("picorv32-barrel", "nirmaan_core_picorv32_barrel", (wrapper, SOC / "picorv32.v"),
                       CORES["picorv32"].runtime, CORES["picorv32"].march, bus_error=True))
    try:
        run, outcome = soc(riscv, FAULT, TIMER_RTL, tmp_path / "run", core="picorv32-barrel",
                           require_bus_error_trap="yes")
        assert run.succeeded, run.summary
        assert checks_of(outcome) == dict.fromkeys(FAULT_CHECKS, True)
        assert_precise(run, outcome, tmp_path / "run")
    finally:
        unregister_core("picorv32-barrel")
    assert "picorv32-barrel" not in CORES


# --- The laws ---------------------------------------------------------------------------------


def test_the_import_laws_and_the_runtime_still_hold():
    src = Path(__file__).parent.parent / "src"
    for name in ("firmware.py", "firmware_riscv.py"):
        tree = ast.parse((src / "nirmaan" / "integrations" / name).read_text())
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(m.split(".")[0] == "veritriage" for m in imported), name
        assert "nirmaan.integrations.veritriage" not in imported, name
    runtime = "".join(p.read_text() for p in (src / "nirmaan" / "runtime").glob("*.py"))
    assert not re.search(r"\b(?:require_irq|require_bus_error_trap|irq)\b", runtime)
    # The SoC runtime names no core: the core's part, bus errors included, is in irq_<core>.S.
    assert not re.search(r"picorv32|serv|maskirq|getq|mstatus", (SOC / "soc_runtime.c").read_text())
