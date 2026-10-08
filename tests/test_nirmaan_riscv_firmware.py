"""Milestone 27: the driver cross-compiled for RV32I and run on a RISC-V core against the real RTL.

* ``fw.cross_build`` compiles the driver and its tests under the strict flags
  for bare-metal RV32I, links them with the SoC runtime (crt0, linker script,
  HAL, a small libc), and reports the ELF's code size.
* ``fw.soc_test`` runs that image on PicoRV32 in a Verilator model of a small
  SoC whose device window is the approved RTL: every register access is a CPU
  load or store that becomes a real AXI4-Lite transfer on the design.
* A wrong driver is a recorded failed run; a missing toolchain is a refusal.
* A request that names RISC-V adds both checks to the firmware seat's gate,
  as data; other requests are unchanged.
Real-tool tests skip when an executable is absent, or fail when CI names it in
NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import human, tid
from test_nirmaan_firmware import (
    DRIVER,
    RTL,
    TESTS,
    approved_rtl,
    design_the_block,
    firmware_answer,
    invoke,
    joined,
    token,
    workspace,
    wrong_driver,
)

from nirmaan.integrations.eda import Backend, register_backend, select_backend, unregister_backend
from nirmaan.integrations.firmware import STRICT_FLAGS
from nirmaan.integrations.firmware_riscv import (
    RISCV_GCC,
    SOC,
    TARGET_FLAGS,
    parse_cross_build,
    parse_soc_test,
    top_module,
)
from nirmaan.models import Assurance, EvidenceKind, ReviewState, TaskStatus, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolAccessDenied, review_task, run_task
from nirmaan.work.policy import unsatisfied_requirements

ON_RISCV = "Create an AXI4-Lite register block and its driver for a RISC-V core."
EXPECTED_CHECKS = {"reset_values", "write_then_read_every_register", "byte_lane_writes",
                   "unmapped_read_reports_slverr", "unmapped_write_reports_slverr_and_changes_nothing",
                   "bad_index_is_refused_by_the_driver"}

#: The vendored core, byte for byte as released upstream (YosysHQ/picorv32 at ef203c2).
PICORV32_SHA256 = "0836050971b3c6cdd28ac3b1e5719a67fb645161912bef1e472e63995ceb0622"


def needs(*executables: str, riscv: bool = False):
    """Skip without the executables (and, with ``riscv``, any RISC-V GCC), unless CI requires them."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    if riscv and not any(shutil.which(g) for g in RISCV_GCC):
        missing.append(RISCV_GCC[0])
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


SOC_TOOLS = ("verilator", "make")


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(ON_RISCV)


# --- The catalog and the gate, as data -------------------------------------------------------


def test_the_riscv_tools_are_available(nirmaan_org):
    assert nirmaan_org.tools["fw.cross_build"].status is ToolStatus.AVAILABLE
    assert nirmaan_org.tools["fw.soc_test"].status is ToolStatus.AVAILABLE
    assert {"fw.cross_build", "fw.soc_test"} <= set(nirmaan_org.skills["device_drivers"].tools)


def test_a_riscv_request_adds_the_soc_checks_and_others_do_not(block, nirmaan_org, fixed_clock):
    assert "riscv" in block.state.project.analysis.features
    firmware = block.task(tid(block, "firmware"))
    gated = {t: r for r in firmware.evidence_requirements if r.before_review for t in r.tools}
    assert set(gated) == {"fw.build", "fw.test", "fw.cross_build", "fw.soc_test"}
    rtl = next(b for b in gated["fw.soc_test"].files if b.upstream)
    assert (rtl.param, rtl.kinds) == ("rtl", ("rtl_source",))
    assert {b.kinds for b in gated["fw.cross_build"].files} == {("driver", "driver_test")}
    # Without RISC-V in the request the seat's gate is exactly M25's.
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block and its driver.")
    task = plain.task(tid(plain, "firmware"))
    assert {t for r in task.evidence_requirements if r.before_review for t in r.tools} == {"fw.build", "fw.test"}


# --- Parsers, against captured output (no tool needed) --------------------------------------

CROSS = """\
$ riscv64-unknown-elf-gcc -std=c11 -Wall -Wextra -Werror -pedantic -march=rv32i -c drv.c -o rv32/0_drv.o
$ riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -c crt0.S -o rv32/crt0.o
$ riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -nostdlib -T link.ld -o rv32/firmware.elf rv32/crt0.o rv32/0_drv.o -lgcc
$ riscv64-unknown-elf-size rv32/firmware.elf
   text\t   data\t    bss\t    dec\t    hex\tfilename
   9332\t      4\t    168\t   9504\t   2520\trv32/firmware.elf
"""


def test_the_cross_build_parser_reports_code_size():
    result = parse_cross_build(CROSS, (0, 0, 0, 0))
    assert result.passed
    assert (result.metrics["text"], result.metrics["data"], result.metrics["bss"]) == (9332, 4, 168)
    assert result.metrics["image_bytes"] == 9336 and result.metrics["compiled"] == 2
    assert result.summary == ("cross-built clean for RV32I: 2 compiler runs, 0 errors, 0 warnings; "
                              "firmware.elf text 9332, data 4, bss 168 bytes")
    link = CROSS.split("$ riscv64-unknown-elf-size")[0] + (
        "/usr/bin/riscv64-unknown-elf-ld: rv32/0_drv.o: in function `f':\n"
        "drv.c:(.text+0x8): undefined reference to `printf'\ncollect2: error: ld returned 1 exit status\n")
    failed = parse_cross_build(link, (0, 0, 1))
    assert not failed.passed and "undefined reference to `printf'" in failed.summary
    warned = CROSS.replace("   text", "drv.c:3:9: error: unused variable 'x' [-Werror=unused-variable]\n   text")
    assert not parse_cross_build(warned, (0, 0, 0, 0)).passed
    assert not parse_cross_build(CROSS.split("   text")[0], (0, 0, 0, 0)).passed  # no size: no image


def test_the_soc_parser_reads_checks_and_names_the_soc():
    log = CROSS + ("$ soc/Vsoc +firmware=rv32/firmware.hex\nFWTEST BUS read 0x5 -> 0x00000000 SLVERR\n"
                   "FWTEST PASS unmapped_read_reports_slverr\nFWTEST SUMMARY 1 passed, 0 failed, 900 cycles\n")
    result = parse_soc_test(log, (0, 0, 0, 0, 0, 0, 0))
    assert result.passed and result.metrics["text"] == 9332
    assert result.summary.startswith("SoC run passed: 1 check, 0 failed (900 cycles, 1 bus transfer)")
    trapped = log.replace("FWTEST SUMMARY 1 passed, 0 failed, 900 cycles",
                          "FWTEST ERROR the CPU trapped after 77 cycles")
    assert not parse_soc_test(trapped, (0, 0, 0, 0, 0, 0, 2)).passed


def test_the_soc_top_is_the_one_module_nothing_instantiates(tmp_path):
    one = tmp_path / "one.v"
    one.write_text("module leaf(input a); endmodule\nmodule top #(parameter W = 1) (input a);\n"
                   "  leaf u_leaf (.a(a));\nendmodule\n")
    assert top_module([str(one)]) == "top"
    assert top_module([str(RTL)]) == "axi4_lite_regs"
    two = tmp_path / "two.v"
    two.write_text("module a; endmodule\nmodule b; endmodule\n")
    assert top_module([str(two)]) is None  # ambiguous: the run asks for top=


# --- Refusals: a missing toolchain is never a simulated run -----------------------------------


def test_a_missing_toolchain_is_refused_with_a_reason(block, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing on PATH
    with pytest.raises(ToolAccessDenied, match=r"no RISC-V GCC on PATH.*never simulated"):
        invoke(block, "fw.cross_build", {"sources": joined(*DRIVER, TESTS)}, tmp_path)
    with pytest.raises(ToolAccessDenied, match=r"picorv32-verilator needs verilator, make.*no RISC-V GCC"):
        invoke(block, "fw.soc_test", {"sources": joined(*DRIVER, TESTS), "rtl": str(RTL)}, tmp_path)
    assert block.state.tool_runs == {}
    backend, why = select_backend("fw.soc_test", {})
    assert backend is None and "riscv64-unknown-elf-gcc or riscv64-elf-gcc" in why


# --- Real tools ----------------------------------------------------------------------------


@needs(riscv=True)
def test_the_driver_and_its_tests_cross_build_for_rv32i(block, tmp_path):
    run, outcome = invoke(block, "fw.cross_build", {"sources": joined(*DRIVER, TESTS)}, tmp_path)
    assert run.succeeded, run.summary
    log = Path(run.references[0]).read_text()
    for flag in (*STRICT_FLAGS, *TARGET_FLAGS):
        assert flag in log
    link = next(c for c in outcome.data["commands"] if "-T" in c)
    assert link[link.index("-T") + 1] == str(SOC / "link.ld") and "crt0.S" in log
    elf = tmp_path / "rv32" / "firmware.elf"
    assert elf.read_bytes()[:4] == b"\x7fELF" and elf.read_bytes()[4] == 1  # a 32-bit ELF
    assert elf.read_bytes()[18] == 243  # e_machine EM_RISCV
    metrics = outcome.data["result"]["metrics"]
    assert metrics["text"] > 0 and metrics["image_bytes"] == metrics["text"] + metrics["data"]
    # the driver, its tests, the SoC runtime, the libc, crt0, and (M29) the core's interrupt runtime
    assert metrics["compiled"] == 6


@needs(riscv=True)
def test_a_strict_warning_fails_the_cross_build_as_a_recorded_run(block, tmp_path):
    lax = tmp_path / "lax.c"
    lax.write_text("int twice(int a) {\n    int unused = 3;\n    return 2 * a;\n}\n")
    run, outcome = invoke(block, "fw.cross_build", {"sources": str(lax)}, tmp_path / "w")
    assert not run.succeeded and run.id in block.state.tool_runs
    assert [d["code"] for d in outcome.data["result"]["diagnostics"]] == ["-Wunused-variable"]


@needs(*SOC_TOOLS, riscv=True)
def test_the_driver_passes_on_a_riscv_core_against_the_real_rtl(block, tmp_path):
    run, outcome = invoke(block, "fw.soc_test", {"sources": joined(*DRIVER, TESTS), "rtl": str(RTL)}, tmp_path)
    assert run.succeeded, run.summary
    checks = {c["name"]: c["passed"] for c in outcome.data["result"]["metrics"]["checks"]}
    assert checks == dict.fromkeys(EXPECTED_CHECKS, True)
    log = Path(run.references[0]).read_text()
    # The CPU's own loads and stores, on the RTL: SLVERR from its decode, byte lanes from byte stores.
    assert "FWTEST BUS read 0x5 -> 0x00000000 SLVERR" in log
    assert "FWTEST BUS write 0xe = 0xdeadbeef strobe 0xf -> SLVERR" in log
    assert "FWTEST BUS write 0x4 = 0xabababab strobe 0x4 -> OKAY" in log  # sb replicates the byte
    assert "picorv32.v" in log and "+define+NIRMAAN_DUT=axi4_lite_regs" in log
    assert run.params["rtl"] == str(RTL) and outcome.data["result"]["metrics"]["text"] > 0


@needs(*SOC_TOOLS, riscv=True)
def test_a_wrong_driver_fails_on_the_core_as_a_recorded_run(block, tmp_path):
    run, outcome = invoke(block, "fw.soc_test", {"sources": joined(*wrong_driver(tmp_path)), "rtl": str(RTL)},
                          tmp_path / "w")
    assert not run.succeeded and run.id in block.state.tool_runs
    assert "write_then_read_every_register" in run.summary and "REG1 read 0x0123abcd" in run.summary
    failed = [c["name"] for c in outcome.data["result"]["metrics"]["checks"] if not c["passed"]]
    assert failed == ["write_then_read_every_register"]


# --- The seat: the M25 flow, plus the cross build and the run on the core --------------------


@needs(*SOC_TOOLS, "cc", "iverilog", "vvp", "yosys", riscv=True)
def test_the_firmware_seat_runs_its_driver_on_a_riscv_core(block, tmp_path):
    design_the_block(block, tmp_path)
    seat = tid(block, "firmware")
    workspace(block, seat, tmp_path / "firmware")
    spec = block.task(tid(block, "interface-spec")).artifacts[0]
    rtl = approved_rtl(block)
    report = run_task(block, seat, ModelRuntime(MockLLM(script=[firmware_answer(token(spec))])))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    task = block.task(seat)
    assert task.status is TaskStatus.IN_REVIEW
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    assert set(runs) == {"fw.build", "fw.test", "fw.cross_build", "fw.soc_test"}
    assert all(r.succeeded for r in runs.values())
    assert runs["fw.soc_test"].params["rtl"] == rtl.location  # the approved file
    arts = {block.state.artifacts[a].location for a in task.artifacts}
    assert set(runs["fw.soc_test"].params["sources"].split(",")) == arts
    assert unsatisfied_requirements(block.state, task) == ["Independent review recorded"]

    review = review_task(block, seat, ModelRuntime(MockLLM()))
    assert review.status is ResultStatus.SUBMITTED and block.task(seat).review_state is ReviewState.PASSED
    block.approve(seat, human(task.approver), "driver runs on the core against the approved RTL")
    assert block.task(seat).status is TaskStatus.COMPLETED
    assert all(block.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)
    for ev in (block.state.evidence[e] for e in block.task(seat).evidence):
        assert ev.kind is not EvidenceKind.CLAIM
        if ev.kind is EvidenceKind.TOOL_RUN:
            assert ev.substantiated and block.state.tool_runs[ev.tool_run].succeeded


# --- Crown jewel: another core or simulator needs zero core changes -------------------------


def test_a_new_soc_backend_needs_no_core_changes(block, tmp_path, monkeypatch):
    """A simulator the core has never heard of: an executable, its steps, the shared parser."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sim = bin_dir / "other-rv-sim"
    sim.write_text('#!/bin/sh\necho "FWTEST BUS read 0x0 -> 0x00000000 OKAY"\necho "FWTEST PASS ran_with_$1"\n'
                   'echo "FWTEST SUMMARY 1 passed, 0 failed, 10 cycles"\n')
    sim.chmod(0o755)

    def steps(job):
        return [["other-rv-sim", Path(job.sources[0]).name]]

    register_backend(Backend("other-core", "fw.soc_test", ("other-rv-sim",), steps,
                             lambda run: parse_soc_test(run.log, run.returncodes), ("sources", "rtl")))
    try:
        params = {"sources": joined(*DRIVER, TESTS), "rtl": str(RTL), "backend": "other-core"}
        with pytest.raises(ToolAccessDenied, match="other-core needs other-rv-sim"):
            invoke(block, "fw.soc_test", params, tmp_path / "w1")  # not on PATH yet: refused
        monkeypatch.setenv("PATH", f"{bin_dir}:{Path(shutil.which('sh')).parent}")
        run, _ = invoke(block, "fw.soc_test", params, tmp_path / "w2", tid(block, "firmware"))
        assert run.succeeded and run.summary.startswith("other-core: SoC run passed: 1 check")
        assert "FWTEST PASS ran_with_axi4_lite_regs_map.h" in Path(run.references[0]).read_text()  # it really ran
    finally:
        unregister_backend("fw.soc_test", "other-core")


# --- The vendored core, and the import laws -----------------------------------------------


def test_the_vendored_core_is_unmodified_and_licensed():
    core = (SOC / "picorv32.v").read_bytes()
    assert hashlib.sha256(core).hexdigest() == PICORV32_SHA256
    assert b"Permission to use, copy, modify, and/or distribute this software" in core  # ISC


def test_the_soc_names_no_design_and_the_module_keeps_the_import_laws():
    for name in ("nirmaan_soc.v", "soc_main.cpp", "soc_runtime.c", "nirmaan_soc.h"):
        assert not re.search(r"axi4_lite_regs|axil_regs", (SOC / name).read_text())
    src = Path(__file__).parent.parent / "src"
    tree = ast.parse((src / "nirmaan" / "integrations" / "firmware_riscv.py").read_text())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.split(".")[0] == "veritriage" for m in imported)
    assert "nirmaan.integrations.veritriage" not in imported
    runtime = "".join(p.read_text() for p in (src / "nirmaan" / "runtime").glob("*.py"))
    assert not re.search(r"riscv|soc_test|cross_build", runtime)  # the runtime names no target
    planner = (src / "nirmaan" / "orchestrator" / "planner.py").read_text()
    assert "riscv" not in planner  # the gate is data
