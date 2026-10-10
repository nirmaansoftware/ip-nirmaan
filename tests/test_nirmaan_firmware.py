"""Milestone 25, firmware: a C driver built strictly and tested against the real RTL.

* Parsers are pure functions of captured text, tested with no tool installed.
* ``fw.build`` compiles the driver under -std=c11 -Wall -Wextra -Werror -pedantic.
* ``fw.test`` builds a Verilator model of the approved RTL with an AXI4-Lite
  manager harness, links the driver and its tests, and runs them: every
  register access is a real bus transaction on the model.
* A wrong driver is a recorded failed run; a missing tool is a refusal.
* The firmware seat works from the approved RTL and interface spec only, and
  reaches review only after the build and the co-simulation passed.
Real-tool tests skip when an executable is absent, or fail when CI names it
in NIRMAAN_REQUIRE_EDA.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import agent, drive, human, tid

from nirmaan.integrations.eda import Backend, register_backend, select_backend, unregister_backend
from nirmaan.integrations.firmware import HARNESS, STRICT_FLAGS, parse_c_build, parse_fw_test
from nirmaan.models import Assurance, EvidenceKind, MemoryScope, ReviewState, TaskStatus, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolAccessDenied, ToolBroker, review_task, run_task
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
AXI = FIXTURES / "rtl" / "axi4_lite"
FW = FIXTURES / "fw" / "axi4_lite"
RTL = AXI / "axi4_lite_regs.v"
DRIVER = (FW / "axi4_lite_regs_map.h", FW / "axi4_lite_regs_drv.h", FW / "axi4_lite_regs_drv.c")
TESTS = FW / "axi4_lite_regs_test.c"
WITH_DRIVER = "Create an AXI4-Lite register block and its driver."


def needs(*executables: str):
    """Skip without the executables, except those CI names in NIRMAAN_REQUIRE_EDA (then it fails)."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


COSIM = ("cc", "verilator", "make")


def joined(*paths: Path) -> str:
    return ",".join(str(p) for p in paths)


def wrong_driver(tmp_path: Path) -> tuple[Path, ...]:
    """The fixture driver with the deliberately wrong register map, under the right file name."""
    folder = tmp_path / "wrong"
    folder.mkdir()
    shutil.copy(FW / "axi4_lite_regs_map_wrong.h", folder / "axi4_lite_regs_map.h")
    for name in ("axi4_lite_regs_drv.h", "axi4_lite_regs_drv.c", "axi4_lite_regs_test.c"):
        shutil.copy(FW / name, folder / name)
    return tuple(folder / n for n in ("axi4_lite_regs_map.h", "axi4_lite_regs_drv.h", "axi4_lite_regs_drv.c",
                                      "axi4_lite_regs_test.c"))


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(WITH_DRIVER)


def holder(engine, tool: str) -> str:
    authority = AuthorityService(engine.org)
    for role in engine.org.roles:
        if authority.may_use_tool(role, tool)[0]:
            return role
    raise AssertionError(f"no role may use {tool}")


def invoke(engine, tool: str, params: dict[str, str], workdir: Path, task: str | None = None):
    return ToolBroker(engine).invoke(agent(holder(engine, tool)), tool, {"workdir": str(workdir), **params}, task)


# --- The catalog and the seat, as data -----------------------------------------------------


def test_the_firmware_tools_are_available_and_the_general_compiler_stays_a_contract(nirmaan_org):
    assert nirmaan_org.tools["fw.build"].status is ToolStatus.AVAILABLE
    assert nirmaan_org.tools["fw.test"].status is ToolStatus.AVAILABLE
    assert nirmaan_org.tools["compiler.run"].status is ToolStatus.CONTRACT_ONLY


def test_a_driver_request_plans_a_firmware_stage_on_approved_inputs(block, nirmaan_org, fixed_clock):
    assert block.state.project.analysis.intent == "block_design"
    firmware = block.task(tid(block, "firmware"))
    assert set(firmware.depends_on) == {tid(block, "interface-spec"), tid(block, "rtl-implementation")}
    assert set(firmware.expected_outputs) == {"driver", "driver_test"}
    assert nirmaan_org.capabilities[firmware.capability].approved_inputs
    gated = {t: r for r in firmware.evidence_requirements if r.before_review for t in r.tools}
    assert set(gated) == {"fw.build", "fw.test"}
    rtl = next(b for b in gated["fw.test"].files if b.upstream)
    assert (rtl.param, rtl.kinds) == ("rtl", ("rtl_source",))
    assert firmware.owner.startswith("software.firmware.drivers.")
    assert firmware.reviewer and not firmware.reviewer.startswith("software.firmware.drivers.")
    # A register block with no driver asked for plans no firmware stage (M23 is unchanged).
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    assert "firmware" not in {t.stage for t in plain.state.tasks.values()}


# --- Parsers, against captured output (no tool needed) --------------------------------------

CLANG = """\
$ cc -std=c11 -Wall -Wextra -Werror -pedantic -c bad.c -o obj/0_bad.o
bad.c:3:9: error: unused variable 'unused' [-Werror,-Wunused-variable]
    3 |     int unused = 3;
      |         ^~~~~~
bad.c:6:22: error: call to undeclared function 'h'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
    6 | int g(void) { return h(); }
      |                      ^
2 errors generated.
"""

GCC = """\
$ cc -std=c11 -Wall -Wextra -Werror -pedantic -c /work/IP Nirmaan/drv.c -o obj/0_drv.o
/work/IP Nirmaan/drv.c: In function 'axil_regs_read':
/work/IP Nirmaan/drv.c:12:14: error: comparison of integer expressions of different signedness: 'int' and 'unsigned int' [-Werror=sign-compare]
   12 |     if (index >= AXIL_REGS_COUNT) {
      |              ^~
/work/IP Nirmaan/drv.c:3:10: note: in expansion of macro 'AXIL_REGS_COUNT'
cc1: all warnings being treated as errors
"""

GCC_FATAL = """\
$ cc -std=c11 -c inc.c -o obj/0_inc.o
inc.c:1:10: fatal error: nothere.h: No such file or directory
    1 | #include "nothere.h"
      |          ^~~~~~~~~~~
compilation terminated.
"""

LINK = """\
$ cc drv.o -o drv
/usr/bin/ld: drv.o: in function `g':
drv.c:(.text+0x1c): undefined reference to `h'
collect2: error: ld returned 1 exit status
"""


def test_the_c_build_parser_reads_clang_and_gcc():
    clang = parse_c_build(CLANG, (1,))
    assert not clang.passed and len(clang.errors) == 2 and clang.warnings == []
    first = clang.errors[0]
    assert (first.file, first.line, first.column, first.code) == ("bad.c", 3, 9, "-Wunused-variable")
    assert first.message == "unused variable 'unused'"
    assert clang.errors[1].code == "-Wimplicit-function-declaration"
    assert "2 errors" in clang.summary and "-Wunused-variable" in clang.summary

    gcc = parse_c_build(GCC, (1,))
    assert len(gcc.diagnostics) == 1  # the note and the "In function" line are context, not diagnostics
    d = gcc.diagnostics[0]
    assert (d.file, d.line, d.code, d.severity) == ("/work/IP Nirmaan/drv.c", 12, "-Wsign-compare", "error")

    fatal = parse_c_build(GCC_FATAL, (1,))
    assert [(e.file, e.message) for e in fatal.errors] == [("inc.c", "nothere.h: No such file or directory")]

    link = parse_c_build(LINK, (1,))
    assert not link.passed and any("undefined reference" in e.message for e in link.errors)


def test_the_c_build_parser_passes_only_a_clean_build():
    clean = "$ cc -std=c11 -c a.c -o obj/0_a.o\n$ cc -std=c11 -c b.c -o obj/1_b.o\n"
    result = parse_c_build(clean, (0, 0))
    assert result.passed and result.metrics["compiled"] == 2
    assert result.summary == "built clean: 2 compiler runs, 0 errors, 0 warnings"
    warned = parse_c_build("$ cc -c a.c\na.c:1:1: warning: something odd [-Wpedantic]\n", (0,))
    assert not warned.passed and warned.warnings[0].code == "-Wpedantic"  # a warning is never clean
    assert not parse_c_build("$ cc -c a.c\n", (1,)).passed  # a failing exit status alone fails


PASSING = """\
$ Vdut
FWTEST BUS read 0x0 -> 0x00000000 OKAY
FWTEST PASS reset_values
FWTEST BUS read 0x5 -> 0x00000000 SLVERR
FWTEST PASS unmapped_read_reports_slverr
FWTEST SUMMARY 2 passed, 0 failed, 12 cycles
"""


def test_the_fw_test_parser_reads_checks():
    result = parse_fw_test(PASSING, (0, 0, 0))
    assert result.passed and result.summary == "co-simulation passed: 2 checks, 0 failed (12 cycles, 2 bus transfers)"
    assert result.metrics["checks"] == [{"name": "reset_values", "passed": True, "detail": ""},
                                        {"name": "unmapped_read_reports_slverr", "passed": True, "detail": ""}]

    failing = PASSING.replace("FWTEST PASS reset_values", "FWTEST FAIL reset_values: REG0 read 0x1")
    failing = failing.replace("2 passed, 0 failed", "1 passed, 1 failed")
    result = parse_fw_test(failing, (0, 0, 1))
    assert not result.passed and result.errors[0].code == "reset_values"
    assert result.summary == "co-simulation failed: 1 of 2 checks failed; first: reset_values: REG0 read 0x1"


def test_the_fw_test_parser_fails_what_did_not_really_pass():
    silent = "$ Vdut\nFWTEST ERROR the tests reported no checks\nFWTEST SUMMARY 0 passed, 0 failed, 5 cycles\n"
    assert not parse_fw_test(silent, (0, 0, 1)).passed
    hang = ("$ Vdut\nFWTEST ERROR bus timeout: no write response handshake for offset 0x0 within 1000 cycles\n"
            "FWTEST SUMMARY 0 passed, 1 failed, 1004 cycles\n")
    result = parse_fw_test(hang, (0, 0, 3))
    assert not result.passed and "bus timeout" in result.summary
    # An exit status of 0 without a summary is not a pass: the harness never finished.
    assert not parse_fw_test("$ Vdut\nFWTEST PASS reset_values\n", (0, 0, 0)).passed
    build = "$ verilator --cc x.v\n%Error: x.v:3:1: syntax error, unexpected endmodule\n"
    result = parse_fw_test(build, (0, 1))
    assert not result.passed and result.summary.startswith("build failed before co-simulation")
    assert result.errors[0].file == "x.v"


# --- Refusals: a missing tool is never a simulated run ---------------------------------------


def test_missing_tools_are_refused_with_a_reason(block, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing on PATH
    with pytest.raises(ToolAccessDenied, match=r"host-cc needs cc.*riscv-gcc needs riscv64-unknown-elf-gcc"):
        invoke(block, "fw.build", {"sources": joined(*DRIVER)}, tmp_path)
    with pytest.raises(ToolAccessDenied, match=r"verilator-cosim needs cc, verilator, make.*never simulated"):
        invoke(block, "fw.test", {"sources": joined(*DRIVER, TESTS), "rtl": str(RTL)}, tmp_path)
    assert block.state.tool_runs == {}


def test_the_cross_compiler_backend_is_refused_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    backend, why = select_backend("fw.build", {"backend": "riscv-gcc"})
    assert backend is None and "riscv-gcc needs riscv64-unknown-elf-gcc" in why


# --- Real tools ----------------------------------------------------------------------------


@needs("cc")
def test_the_fixture_driver_builds_clean_under_strict_flags(block, tmp_path):
    run, outcome = invoke(block, "fw.build", {"sources": joined(*DRIVER)}, tmp_path)
    assert run.succeeded, run.summary
    log = Path(run.references[0]).read_text()
    for flag in STRICT_FLAGS:
        assert flag in log
    assert "-fsyntax-only" in log and f"-I{HARNESS}" in log  # headers compile on their own too
    assert outcome.data["result"]["metrics"]["compiled"] == 3


@needs("cc")
def test_a_strict_warning_fails_the_build_as_a_recorded_run(block, tmp_path):
    lax = tmp_path / "lax.c"
    lax.write_text("int twice(int a) {\n    int unused = 3;\n    return 2 * a;\n}\n")
    run, outcome = invoke(block, "fw.build", {"sources": str(lax)}, tmp_path / "w")
    assert not run.succeeded and run.id in block.state.tool_runs
    diags = outcome.data["result"]["diagnostics"]
    assert [(d["line"], d["code"]) for d in diags] == [(2, "-Wunused-variable")]


@needs(*COSIM)
def test_the_driver_passes_against_the_real_rtl(block, tmp_path):
    run, outcome = invoke(block, "fw.test", {"sources": joined(*DRIVER, TESTS), "rtl": str(RTL)}, tmp_path)
    assert run.succeeded, run.summary
    checks = {c["name"]: c["passed"] for c in outcome.data["result"]["metrics"]["checks"]}
    assert checks == {"reset_values": True, "write_then_read_every_register": True, "byte_lane_writes": True,
                      "unmapped_read_reports_slverr": True,
                      "unmapped_write_reports_slverr_and_changes_nothing": True,
                      "bad_index_is_refused_by_the_driver": True}
    log = Path(run.references[0]).read_text()
    # Real transactions on the model: the SLVERR came from the RTL's own decode.
    assert "FWTEST BUS read 0x5 -> 0x00000000 SLVERR" in log
    assert "FWTEST BUS write 0xe = 0xdeadbeef strobe 0xf -> SLVERR" in log
    assert "FWTEST BUS write 0x4 = 0x00ab0000 strobe 0x4 -> OKAY" in log
    assert "verilator --cc --exe --build" in log and run.params["rtl"] == str(RTL)


@needs(*COSIM)
def test_a_wrong_driver_is_a_recorded_failed_run(block, tmp_path):
    run, outcome = invoke(block, "fw.test", {"sources": joined(*wrong_driver(tmp_path)), "rtl": str(RTL)},
                          tmp_path / "w")
    assert not run.succeeded and run.id in block.state.tool_runs
    assert "write_then_read_every_register" in run.summary and "REG1 read 0x0123abcd" in run.summary
    failed = [c["name"] for c in outcome.data["result"]["metrics"]["checks"] if not c["passed"]]
    assert failed == ["write_then_read_every_register"]


# --- The seat: approved RTL in, real build and co-simulation, review, approval ---------------


def token(art_id: str) -> str:
    return "[artifact:" + re.sub(r"[^A-Za-z0-9._\-]", ".", art_id) + "]"


def file(path: str, kind: str, content: str, cite: str, entry: str | None = None) -> dict:
    return {"path": path, "kind": kind, "title": path, "summary": f"{path}, from {cite}.",
            "content": content, **({"entry": entry} if entry else {})}


def answer(*files: dict) -> str:
    meta = [{k: v for k, v in f.items() if k != "content"} for f in files]
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                       "escalation": None}, indent=1)
    return f"{head}\n" + "".join(f"=== FILE: {f['path']} ===\n{f['content']}=== END FILE ===\n" for f in files)


def workspace(engine, task_id: str, path: Path) -> None:
    engine.remember(MemoryScope.TASK, task_id, "input.workspace", str(path), human(engine.task(task_id).owner))


def firmware_answer(cite: str, map_header: Path = FW / "axi4_lite_regs_map.h") -> str:
    files = [file("axi4_lite_regs_map.h", "driver", map_header.read_text(), cite)]
    files += [file(p.name, "driver", p.read_text(), cite) for p in DRIVER[1:]]
    files.append(file(TESTS.name, "driver_test", TESTS.read_text(), cite))
    return answer(*files)


def design_the_block(engine, tmp_path: Path) -> None:
    """The M23 flow: interface spec, microarchitecture, RTL, each by a seat, reviewed and approved."""
    stages = (("interface-spec", "requirements", [("interface_spec.md", "interface_spec", None)]),
              ("microarchitecture", "interface-spec", [("microarchitecture.md", "microarchitecture_spec", None)]),
              ("rtl-implementation", "microarchitecture", [("axi4_lite_regs.v", "rtl_source", "axi4_lite_regs"),
                                                           ("axi4_lite_regs_tb.v", "testbench", "axi4_lite_regs_tb")]))
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, outputs in stages:
        seat = tid(engine, stage)
        workspace(engine, seat, tmp_path / stage)
        cite = token(engine.task(tid(engine, source)).artifacts[0])
        llm = MockLLM(script=[answer(*(file(name, kind, (AXI / name).read_text(), cite, entry)
                                       for name, kind, entry in outputs))])
        report = run_task(engine, seat, ModelRuntime(llm))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_task(engine, seat, ModelRuntime(MockLLM()))
        engine.approve(seat, human(engine.task(seat).approver), "agreed")


def approved_rtl(engine):
    rtl = engine.task(tid(engine, "rtl-implementation"))
    return next(engine.state.artifacts[a] for a in rtl.artifacts if engine.state.artifacts[a].kind == "rtl_source")


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_the_firmware_seat_runs_its_driver_on_the_approved_rtl(block, tmp_path):
    """Approved RTL, then the firmware seat, real build and co-simulation, review, approval."""
    design_the_block(block, tmp_path)
    seat = tid(block, "firmware")
    assert block.task(seat).status is TaskStatus.READY
    workspace(block, seat, tmp_path / "firmware")
    spec = block.task(tid(block, "interface-spec")).artifacts[0]
    rtl = approved_rtl(block)
    llm = MockLLM(script=[firmware_answer(token(spec))])
    report = run_task(block, seat, ModelRuntime(llm))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    prompt = llm.calls[0].render()
    assert "module axi4_lite_regs" in prompt and "Register map" in prompt  # approved upstream, verbatim
    assert "with the approved rtl_source" in prompt
    task = block.task(seat)
    assert task.status is TaskStatus.IN_REVIEW
    arts = [block.state.artifacts[a] for a in task.artifacts]
    assert sorted(a.kind for a in arts) == ["driver", "driver", "driver", "driver_test"]
    for art in arts:
        assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
        assert art.derived_from == (spec,)
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    assert set(runs) == {"fw.build", "fw.test"} and all(r.succeeded for r in runs.values())
    assert runs["fw.test"].params["rtl"] == rtl.location  # the approved file, not a copy of the fixture
    assert set(runs["fw.test"].params["sources"].split(",")) == {a.location for a in arts}
    assert unsatisfied_requirements(block.state, task) == ["Independent review recorded"]

    reviewer = MockLLM()
    review = review_task(block, seat, ModelRuntime(reviewer))
    assert review.status is ResultStatus.SUBMITTED and block.task(seat).review_state is ReviewState.PASSED
    assert "nirmaan_fw_test" in reviewer.calls[0].render()  # the reviewer reads the driver tests
    block.approve(seat, human(task.approver), "driver runs on the approved RTL")
    assert block.task(seat).status is TaskStatus.COMPLETED
    assert all(block.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)
    for ev in (block.state.evidence[e] for e in block.task(seat).evidence):
        assert ev.kind is not EvidenceKind.CLAIM
        if ev.kind is EvidenceKind.TOOL_RUN:
            assert ev.substantiated and block.state.tool_runs[ev.tool_run].succeeded


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_the_wrong_driver_cannot_reach_review(block, tmp_path):
    design_the_block(block, tmp_path)
    seat = tid(block, "firmware")
    workspace(block, seat, tmp_path / "firmware")
    cite = token(block.task(tid(block, "interface-spec")).artifacts[0])
    report = run_task(block, seat, ModelRuntime(MockLLM(script=[
        firmware_answer(cite, FW / "axi4_lite_regs_map_wrong.h")])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail
    task = block.task(seat)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    assert runs["fw.build"].succeeded  # it compiles cleanly: only the RTL shows the bug
    assert not runs["fw.test"].succeeded and "write_then_read_every_register" in runs["fw.test"].summary
    ev = next(block.state.evidence[e] for e in report.evidence
              if block.state.evidence[e].tool_run == runs["fw.test"].id)
    assert not ev.substantiated  # the failure is on the record


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_a_co_simulation_against_other_rtl_does_not_open_review(block, tmp_path):
    """The policy, not only the runtime: the passing run must name the approved RTL."""
    design_the_block(block, tmp_path)
    seat = tid(block, "firmware")
    owner = agent(block.task(seat).owner)
    block.start(seat, owner)
    folder = tmp_path / "manual"
    folder.mkdir()
    copies = [Path(shutil.copy(p, folder / p.name)) for p in (*DRIVER, TESTS)]
    elsewhere = Path(shutil.copy(RTL, tmp_path / "other_copy.v"))
    broker = ToolBroker(block)
    build, _ = broker.invoke(owner, "fw.build", {"sources": joined(*copies[:3]), "workdir": str(tmp_path / "b")},
                             seat)
    test, _ = broker.invoke(owner, "fw.test", {"sources": joined(*copies), "rtl": str(elsewhere),
                                               "require_irq": "auto",  # as the gate asks (M35)
                                               "workdir": str(tmp_path / "t")}, seat)
    assert build.succeeded and test.succeeded
    for run in (build, test):
        block.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
    drafts = [{"kind": "driver", "title": p.name, "location": str(p)} for p in copies[:3]]
    drafts.append({"kind": "driver_test", "title": copies[3].name, "location": str(copies[3])})
    from nirmaan.work import PolicyViolationError

    with pytest.raises(PolicyViolationError, match="approved upstream rtl_source"):
        block.submit(seat, owner, drafts)


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_rtl_changed_after_approval_is_not_co_simulated(block, tmp_path):
    design_the_block(block, tmp_path)
    rtl = approved_rtl(block)
    Path(rtl.location).write_text(Path(rtl.location).read_text() + "// edited after approval\n")
    seat = tid(block, "firmware")
    workspace(block, seat, tmp_path / "firmware")
    cite = token(block.task(tid(block, "interface-spec")).artifacts[0])
    report = run_task(block, seat, ModelRuntime(MockLLM(script=[firmware_answer(cite)])))
    assert report.status is ResultStatus.REFUSED  # as for a missing file in M23: the check is unmet
    assert "fw.test not run: no approved upstream rtl_source file" in report.detail
    assert all(block.state.tool_runs[r].tool != "fw.test" for r in block.state.tool_runs)
    assert block.task(seat).status is TaskStatus.IN_PROGRESS and block.task(seat).artifacts == ()


# --- Crown jewel: a new firmware backend needs zero core changes -----------------------------


def test_a_new_firmware_backend_needs_no_core_changes(block, tmp_path, monkeypatch):
    """An ARM cross compiler the core has never heard of: an executable, its steps, the shared parser."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    compiler = bin_dir / "arm-none-eabi-gcc"
    compiler.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in *.c) echo "compiled $a";; esac; done\n')
    compiler.chmod(0o755)

    def steps(job):
        return [["arm-none-eabi-gcc", *STRICT_FLAGS, "-mcpu=cortex-m0", "-c", s]
                for s in job.sources if s.endswith(".c")]

    register_backend(Backend("arm-cc", "fw.build", ("arm-none-eabi-gcc",), steps,
                             lambda run: parse_c_build(run.log, run.returncodes)))
    try:
        params = {"sources": joined(*DRIVER), "backend": "arm-cc"}
        with pytest.raises(ToolAccessDenied, match="arm-cc needs arm-none-eabi-gcc"):
            invoke(block, "fw.build", params, tmp_path / "w1")  # not on PATH yet: refused
        monkeypatch.setenv("PATH", f"{bin_dir}:{Path(shutil.which('sh')).parent}")
        seat = tid(block, "firmware")
        run, _ = invoke(block, "fw.build", params, tmp_path / "w2", seat)
        assert run.succeeded and run.summary == "arm-cc: built clean: 1 compiler run, 0 errors, 0 warnings"
        assert f"compiled {DRIVER[2]}" in Path(run.references[0]).read_text()  # it really ran
    finally:
        unregister_backend("fw.build", "arm-cc")


# --- The import laws ----------------------------------------------------------------------


def test_the_firmware_module_keeps_the_import_laws():
    src = Path(__file__).parent.parent / "src"
    tree = ast.parse((src / "nirmaan" / "integrations" / "firmware.py").read_text())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(m.split(".")[0] == "veritriage" for m in imported)
    assert "nirmaan.integrations.veritriage" not in imported
    runtime = "".join(p.read_text() for p in (src / "nirmaan" / "runtime").glob("*.py"))
    assert not re.search(r"firmware|fw\.|driver", runtime)  # the runtime names no seat
