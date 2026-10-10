"""Milestone 29: interrupts, a second core, a code-size gate, and APB in the RISC-V firmware loop.

* The design's ``irq`` output reaches the core's interrupt input; the timer's
  tests prove the interrupt fires, is handled, is acknowledged by a register
  write, and stays silent when masked, and fail on a design whose IRQ is broken.
* The same SoC, driver, and tests run on PicoRV32 and on SERV, chosen by the
  ``core`` parameter; a third core is one ``register_core`` call.
* ``max_text_bytes`` limits the image's code size, as data in the gate.
* An APB design sits behind an APB bridge, chosen from the design's ports.
Real-tool tests skip when an executable is absent, or fail when CI names it in
NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shutil
from pathlib import Path

import pytest

from test_nirmaan_firmware import DRIVER, FIXTURES, RTL, TESTS, invoke, joined
from test_nirmaan_riscv_firmware import CROSS, EXPECTED_CHECKS, ON_RISCV, SOC_TOOLS, needs

from nirmaan.integrations.firmware_riscv import (
    BUSES,
    CORES,
    SERV_FILES,
    SOC,
    Core,
    bus_of,
    design_ports,
    parse_cross_build,
    register_core,
    unregister_core,
)
from nirmaan.orchestrator import Orchestrator

TIMER_RTL = FIXTURES / "rtl" / "axil_timer" / "axil_timer.v"
TIMER_FW = FIXTURES / "fw" / "axil_timer"
TIMER = tuple(TIMER_FW / n for n in ("axil_timer_map.h", "axil_timer_drv.h", "axil_timer_drv.c",
                                     "axil_timer_test.c"))
TIMER_CHECKS = {"registers_reset_and_read_back", "interrupt_fires_and_is_handled",
                "interrupt_is_acknowledged_by_a_register_write", "masked_interrupt_does_not_fire",
                "unmasking_a_pending_interrupt_fires_it"}
APB_RTL = FIXTURES / "rtl" / "apb_regs" / "apb_regs.v"
APB_FW = FIXTURES / "fw" / "apb_regs"
APB = tuple(APB_FW / n for n in ("apb_regs_map.h", "apb_regs_drv.h", "apb_regs_drv.c", "apb_regs_test.c"))

BOTH = pytest.mark.parametrize("core", ["picorv32", "serv"])

#: SERV 1.4.0 (olofk/serv, tag 1.4.0, commit 7d9cde4), byte for byte.
SERV_SHA256 = {
    "serv_aligner.v": "adeff8f442db6c93f48e551721146b40c398ab14dcb5b22339746329e7a24f3b",
    "serv_alu.v": "2e0c31b5b992618e514083aacf10cb38c2229b68b3b1e93d6663104f32143332",
    "serv_bufreg.v": "76404174ec92c6cf68e0042798dede84d77c5e454c7f428afc7b9f612a3c52d4",
    "serv_bufreg2.v": "6586c95a64a064ff6f4d001996d33f15e0f6d452e01ebb4da6120db06ddd0a51",
    "serv_compdec.v": "a7d22f519786fa9f92b3df5813ed7eeda6612ab38f554c3f396e8d415f089a30",
    "serv_csr.v": "2dd7167ed44817d921318a5d463281b43820c25e476039a604e95948be567e62",
    "serv_ctrl.v": "eb198ba7594f918da2784f9b6f8c82de1b95e3ffdd3383f2f533872999e9dab5",
    "serv_debug.v": "815a6b0da1a49d41faa72edd8f397f89ec79334b292b94991f60002b0776082f",
    "serv_decode.v": "7300a04280b14ec4a39fe63bee474bf76c08abd75b608ab667f6a943d016c662",
    "serv_immdec.v": "80ec5a265194eb40f3413742fc9da0a23ed78f8bdf5add3e58b45fa1850b2bd5",
    "serv_mem_if.v": "a4fbd74579447710ed43e81dd80b4ea9415da0a3425a447f29446f9bd7a9aa6f",
    "serv_rf_if.v": "63fd0d2ec2f89201b20690c467ebbcae964a85b4570254a95154f832cf0dcb2e",
    "serv_rf_ram.v": "779ad3243dfa648f276240d260ff4ac1a1e83cc1364afb93d40c586905ce4338",
    "serv_rf_ram_if.v": "abb39b6bdf4d335bd2f90f75ddb1a410500a1a51a3e9f170453cb491d98d8697",
    "serv_rf_top.v": "89faedf7530c34305bfbffd261732d95016bf5627f10b7bbafaa8e1fd6cd49c9",
    "serv_state.v": "20d53b8da058f9a2815c84489f32a7f3622e2a0b393d2867b630a07ae44ac8dd",
    "serv_top.v": "c35b88bed5732309069203b2d04421622eaae108d5bf5daef3de273daf43388e",
    "LICENSE": "d9a1bd691f04280a8369a4aa69b6be20c0e2ee6d164a17ad8a8ef49da8ea0ea9",
}


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(ON_RISCV)


def soc_run(block, sources, rtl, workdir: Path, **params):
    return invoke(block, "fw.soc_test", {"sources": joined(*sources), "rtl": str(rtl), **params}, workdir)


def checks_of(outcome) -> dict[str, bool]:
    return {c["name"]: c["passed"] for c in outcome.data["result"]["metrics"]["checks"]}


def broken_timer(tmp_path: Path, irq: str) -> Path:
    """The timer with its interrupt line replaced, under the same module name."""
    text = TIMER_RTL.read_text()
    broken = text.replace("    assign irq = expired && ie;\n", f"    assign irq = {irq};\n")
    assert broken != text
    path = tmp_path / "broken" / "axil_timer.v"
    path.parent.mkdir(parents=True)
    path.write_text(broken)
    return path


# --- The gate, the parser, and the registries, as data -----------------------------------------


def test_the_cross_build_requirement_limits_the_code_size(block):
    firmware = block.task(next(t for t in block.state.tasks if block.state.tasks[t].stage == "firmware"))
    cross = next(r for r in firmware.evidence_requirements if r.tools == ("fw.cross_build",))
    assert dict(cross.params) == {"max_text_bytes": "16384"}
    soc = next(r for r in firmware.evidence_requirements if r.tools == ("fw.soc_test",))
    assert dict(soc.params) == {"require_irq": "auto"}  # the default core, as in M27; M35 adds require_irq


def test_the_size_parser_reports_text_bytes():
    result = parse_cross_build(CROSS, (0, 0, 0, 0))
    assert result.metrics["text_bytes"] == result.metrics["text"] == 9332


def test_cores_and_buses_are_data():
    assert set(CORES) == {"picorv32", "serv"}
    assert CORES["picorv32"].verilog[1] == SOC / "picorv32.v"
    assert [p.name for p in CORES["serv"].verilog[1:]] == list(SERV_FILES)
    assert {b.name for b in BUSES.values()} == {"axi4-lite", "apb"}
    assert bus_of(design_ports([str(RTL)], "axi4_lite_regs")).name == "axi4-lite"
    assert bus_of(design_ports([str(APB_RTL)], "apb_regs")).name == "apb"
    assert "irq" in design_ports([str(TIMER_RTL)], "axil_timer")
    assert "irq" not in design_ports([str(RTL)], "axi4_lite_regs")


def test_the_soc_names_no_design_no_core_and_no_bus():
    """The SoC instantiates `NIRMAAN_CORE and its bridge `NIRMAAN_BRIDGE; each bridge, `NIRMAAN_DUT."""
    def code(name: str) -> str:  # the Verilog without its comments, which do say what the macros may be
        return re.sub(r"//[^\n]*|/\*.*?\*/", "", (SOC / name).read_text(), flags=re.DOTALL)

    soc = code("nirmaan_soc.v")
    assert "`NIRMAAN_CORE" in soc and "`NIRMAAN_BRIDGE" in soc
    assert not re.search(r"picorv32|serv|axi|apb|axi4_lite_regs|axil_timer", soc)
    for bridge in ("bridge_axil.v", "bridge_apb.v"):
        text = code(bridge)
        assert "`NIRMAAN_DUT" in text and not re.search(r"axi4_lite_regs|apb_regs|axil_timer|picorv32|serv", text)
    runtime = (SOC / "soc_runtime.c").read_text()
    assert not re.search(r"picorv32|serv|maskirq|mstatus", runtime)  # the core's part is in irq_<core>.S


# --- Refusals and recorded failures ---------------------------------------------------------


@needs(*SOC_TOOLS, riscv=True)
def test_an_unknown_core_and_an_unknown_bus_are_recorded_failed_runs(block, tmp_path):
    run, _ = soc_run(block, (*DRIVER, TESTS), RTL, tmp_path / "core", core="vexriscv")
    assert not run.succeeded and run.id in block.state.tool_runs
    assert "unknown core 'vexriscv'" in run.summary and "picorv32, serv" in run.summary
    lone = tmp_path / "lone.v"
    lone.write_text("module lone(input wire clk, input wire [3:0] addr, output wire [31:0] data);\n"
                    "  assign data = {28'b0, addr};\nendmodule\n")
    run, _ = soc_run(block, (*DRIVER, TESTS), lone, tmp_path / "bus")
    assert not run.succeeded and "no bus the SoC knows" in run.summary
    assert "s_axil_awaddr" in run.summary and "psel" in run.summary


@needs(riscv=True)
def test_an_oversized_image_is_refused_as_a_recorded_failed_run(block, tmp_path):
    params = {"sources": joined(*DRIVER, TESTS), "max_text_bytes": "4096"}
    run, outcome = invoke(block, "fw.cross_build", params, tmp_path)
    assert not run.succeeded and run.id in block.state.tool_runs
    measured = outcome.data["result"]["metrics"]["text_bytes"]
    assert measured > 4096 and f"text_bytes {measured} exceeds max_text_bytes 4096" in run.summary
    fits, _ = invoke(block, "fw.cross_build", {**params, "max_text_bytes": "16384"}, tmp_path / "fits")
    assert fits.succeeded, fits.summary


# --- Real runs, on both cores ----------------------------------------------------------------


@needs(*SOC_TOOLS, riscv=True)
@BOTH
def test_the_register_driver_passes_on_each_core(block, tmp_path, core):
    run, outcome = soc_run(block, (*DRIVER, TESTS), RTL, tmp_path, core=core)
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(EXPECTED_CHECKS, True)
    log = Path(run.references[0]).read_text()
    assert "FWTEST BUS read 0x5 -> 0x00000000 SLVERR" in log  # the RTL's own decode
    assert f"+define+NIRMAAN_CORE=nirmaan_core_{core}" in log
    assert "+define+NIRMAAN_BRIDGE=nirmaan_bridge_axil" in log and "NIRMAAN_DUT_IRQ" not in log
    for name in (p.name for p in CORES[core].verilog):
        assert name in log


@needs(*SOC_TOOLS, riscv=True)
@BOTH
def test_the_interrupt_fires_is_acknowledged_and_masked_on_each_core(block, tmp_path, core):
    run, outcome = soc_run(block, TIMER, TIMER_RTL, tmp_path, core=core)
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(TIMER_CHECKS, True)
    log = Path(run.references[0]).read_text()
    assert "+define+NIRMAAN_DUT_IRQ" in log
    # The acknowledgement is a register write: the W1C to STATUS, on the RTL.
    assert "FWTEST BUS write 0xc = 0x00000001 strobe 0xf -> OKAY" in log
    assert "FWTEST BUS write 0x8 = 0x00000005 strobe 0xf -> SLVERR" in log  # COUNT is read only


@needs(*SOC_TOOLS, riscv=True)
@BOTH
@pytest.mark.parametrize("irq, failing", [
    ("1'b0", {"interrupt_fires_and_is_handled", "interrupt_is_acknowledged_by_a_register_write",
              "unmasking_a_pending_interrupt_fires_it"}),
    ("expired", {"masked_interrupt_does_not_fire", "unmasking_a_pending_interrupt_fires_it"}),
])
def test_a_broken_irq_is_caught_on_each_core(block, tmp_path, core, irq, failing):
    run, outcome = soc_run(block, TIMER, broken_timer(tmp_path, irq), tmp_path / "run", core=core)
    assert not run.succeeded and run.id in block.state.tool_runs
    checks = checks_of(outcome)
    assert {name for name, ok in checks.items() if not ok} == failing
    assert set(checks) == TIMER_CHECKS  # every check ran and reported
    assert sorted(failing)[0] in run.summary or any(name in run.summary for name in failing)


@needs(*SOC_TOOLS, riscv=True)
@BOTH
def test_the_apb_driver_passes_against_the_apb_rtl_on_each_core(block, tmp_path, core):
    run, outcome = soc_run(block, APB, APB_RTL, tmp_path, core=core)
    assert run.succeeded, run.summary
    assert checks_of(outcome) == dict.fromkeys(EXPECTED_CHECKS, True)
    log = Path(run.references[0]).read_text()
    assert "+define+NIRMAAN_BRIDGE=nirmaan_bridge_apb" in log and "bridge_apb.v" in log
    # PSLVERR from the RTL's own decode reaches the driver as SLVERR.
    assert "FWTEST BUS read 0x5 -> 0x00000000 SLVERR" in log
    assert "FWTEST BUS write 0x10 = 0xdeadbeef strobe 0xf -> SLVERR" in log


@needs(*SOC_TOOLS, riscv=True)
def test_the_apb_driver_fails_against_the_wrong_map(block, tmp_path):
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    for path in APB:
        shutil.copy(path, wrong / path.name)
    header = wrong / "apb_regs_map.h"
    header.write_text(header.read_text().replace("APB_REGS_REG2_OFFSET 0x8u", "APB_REGS_REG2_OFFSET 0x4u"))
    run, outcome = soc_run(block, tuple(wrong / p.name for p in APB), APB_RTL, tmp_path / "run")
    assert not run.succeeded and "write_then_read_every_register" in run.summary
    assert [n for n, ok in checks_of(outcome).items() if not ok] == ["write_then_read_every_register"]


# --- Crown jewel: a third core needs zero core changes ----------------------------------------


WRAPPER = """\
// A third core for the crown-jewel test: PicoRV32 built another way, behind the SoC's interface.
module nirmaan_core_picorv32_barrel (
    input wire clk, input wire resetn, output wire trap,
    output wire mem_valid, input wire mem_ready, output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata, output wire [3:0] mem_wstrb, input wire [31:0] mem_rdata,
    input wire irq
);
    /* verilator lint_off PINCONNECTEMPTY */
    picorv32 #(.ENABLE_COUNTERS(0), .BARREL_SHIFTER(1), .TWO_CYCLE_ALU(1), .ENABLE_IRQ(1),
               .ENABLE_IRQ_QREGS(1), .ENABLE_IRQ_TIMER(0), .PROGADDR_IRQ(32'h10),
               .LATCHED_IRQ(32'hffff_fff7)) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
        .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(), .mem_la_wstrb(),
        .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(),
        .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
        .irq({28'b0, irq, 3'b0}), .eoi(), .trace_valid(), .trace_data()
    );
    /* verilator lint_on PINCONNECTEMPTY */
endmodule
"""


@needs(*SOC_TOOLS, riscv=True)
def test_a_new_core_needs_no_core_changes(block, tmp_path):
    """A core the SoC has never seen: its wrapper and its runtime file, registered as data."""
    wrapper = tmp_path / "third" / "core_picorv32_barrel.v"
    wrapper.parent.mkdir()
    wrapper.write_text(WRAPPER)
    register_core(Core("picorv32-barrel", "nirmaan_core_picorv32_barrel", (wrapper, SOC / "picorv32.v"),
                       CORES["picorv32"].runtime, CORES["picorv32"].march))
    try:
        run, outcome = soc_run(block, TIMER, TIMER_RTL, tmp_path / "run", core="picorv32-barrel")
        assert run.succeeded, run.summary
        assert checks_of(outcome) == dict.fromkeys(TIMER_CHECKS, True)
        log = Path(run.references[0]).read_text()
        assert "+define+NIRMAAN_CORE=nirmaan_core_picorv32_barrel" in log and "core_picorv32_barrel.v" in log
    finally:
        unregister_core("picorv32-barrel")
    assert "picorv32-barrel" not in CORES


# --- The vendored core, and the laws ---------------------------------------------------------


def test_serv_is_unmodified_and_licensed():
    folder = SOC / "serv"
    assert {p.name for p in folder.iterdir()} == set(SERV_SHA256)
    for name, digest in SERV_SHA256.items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, name
    assert "ISC License" in (folder / "LICENSE").read_text()
    licenses = {n: re.search(r"SPDX-License-Identifier: (\S+)", (folder / n).read_text())[1] for n in SERV_FILES}
    # SERV is ISC; its compressed decoder is adapted from lowRISC's Ibex and keeps Ibex's Apache-2.0 header.
    assert licenses == {**dict.fromkeys(SERV_FILES, "ISC"), "serv_compdec.v": "Apache-2.0"}


def test_the_new_modules_keep_the_import_laws():
    src = Path(__file__).parent.parent / "src"
    tree = ast.parse((src / "nirmaan" / "integrations" / "firmware_riscv.py").read_text())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.split(".")[0] == "veritriage" for m in imported)
    assert "nirmaan.integrations.veritriage" not in imported
    runtime = "".join(p.read_text() for p in (src / "nirmaan" / "runtime").glob("*.py"))
    assert not re.search(r"\b(?:serv|picorv32|max_text_bytes|apb)\b", runtime)  # the runtime names no core or bus
