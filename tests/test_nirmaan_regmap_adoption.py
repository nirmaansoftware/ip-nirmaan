"""Milestone 41: the register map in ``block-design``, bit fields, and an APB host harness.

* A register map gains bit fields (rw, ro, wo, w1c), validated for overlaps
  and widths, lowered to field macros and accessors in the C header, and
  checked by the generated co-simulation test.
* The host co-simulation selects its bus manager as data (a registry); APB
  ships beside AXI4-Lite, so ``fw.test`` and ``regmap.verify`` run APB RTL.
* ``block-design`` plans a ``register-map`` stage when the request asks for
  one; the approved map judges the RTL (``regmap.verify``) and the driver
  (the generated header and an agreement unit) before review.
Real-tool tests skip when an executable is absent, or fail when CI names it
in NIRMAAN_REQUIRE_EDA (docs/REGISTER_MAP_ADOPTION.md).
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from nirmaan_helpers import agent, drive, human, tid
from test_nirmaan_design_agents import needs
from test_nirmaan_firmware import answer, file, holder, joined, token, workspace

from nirmaan.integrations.firmware import HARNESS, cosim_buses, register_cosim_bus, unregister_cosim_bus
from nirmaan.models import Access, Assurance, RegisterMap, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.regmap import c_test, load_map, lower, validate
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolBroker, review_task, run_task

FIXTURES = Path(__file__).parent / "fixtures"
APB = FIXTURES / "rtl" / "apb_regs"
APB_RTL = APB / "apb_regs.v"
APB_MAP = APB / "register_map.json"
APB_FW = FIXTURES / "fw" / "apb_regs"
APB_DRIVER = tuple(APB_FW / n for n in ("apb_regs_map.h", "apb_regs_drv.h", "apb_regs_drv.c"))
APB_TESTS = APB_FW / "apb_regs_test.c"
CSR = FIXTURES / "rtl" / "apb_csr"
CSR_RTL = CSR / "apb_csr.v"
CSR_MAP = CSR / "register_map.json"
CSR_FW = FIXTURES / "fw" / "apb_csr"
CSR_SOURCES = tuple(CSR_FW / n for n in ("apb_csr_drv.h", "apb_csr_drv.c", "apb_csr_test.c"))
COSIM = ("cc", "verilator", "make")
REQUEST = "Create an APB register block, with a register map, and its driver."


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REQUEST)


def invoke(engine, tool: str, params: dict, workdir: Path, task: str | None = None):
    return ToolBroker(engine).invoke(agent(holder(engine, tool)), tool, {"workdir": str(workdir), **params}, task)


def _csr(**changes) -> RegisterMap:
    return load_map(CSR_MAP).model_copy(update=changes)


def _with_field(reg: int, field: int, **changes) -> RegisterMap:
    base = load_map(CSR_MAP)
    regs = list(base.registers)
    fields = list(regs[reg].fields)
    fields[field] = fields[field].model_copy(update=changes)
    regs[reg] = regs[reg].model_copy(update={"fields": tuple(fields)})
    return base.model_copy(update={"registers": tuple(regs)})


def _with_register(reg: int, **changes) -> RegisterMap:
    base = load_map(CSR_MAP)
    regs = list(base.registers)
    regs[reg] = regs[reg].model_copy(update=changes)
    return base.model_copy(update={"registers": tuple(regs)})


# --- Fields: the format and its validation -------------------------------------------------


def test_the_fixture_maps_are_clean():
    assert validate(load_map(CSR_MAP)) == []
    assert validate(load_map(APB_MAP)) == []
    status = load_map(CSR_MAP).registers[2]
    assert [(f.name, f.lsb, f.high, f.access) for f in status.fields] == [
        ("RESET_DONE", 0, 0, Access.W1C), ("VERSION", 8, 15, Access.RO)]


@pytest.mark.parametrize("regmap,problem", [
    (_with_field(0, 1, lsb=0, msb=2), "overlap at bit 0"),
    (_with_field(0, 1, msb=0), "msb 0 is below lsb 1"),
    (_with_field(2, 1, msb=33), "beyond the 32-bit register"),
    (_with_field(0, 1, reset=8), "wider than its 3 bits"),
    (_with_field(0, 1, name="ENABLE"), "appears twice"),
    (_with_field(0, 1, name="mode 2"), "not a C identifier"),
    (_with_register(0, reset=0), "disagrees with its fields"),
    (_with_register(0, access=Access.RO), "access comes from its fields"),
])
def test_field_validation_names_each_problem(regmap, problem):
    problems = validate(regmap)
    assert any(problem in p for p in problems), problems


# --- The header --------------------------------------------------------------------------


def _defines(text: str) -> dict[str, int]:
    return {name: int(value.rstrip("uU"), 0) for name, value in
            re.findall(r"#define (\w+) (0x[0-9A-Fa-f]+u|\d+u)", text)}


def test_the_header_has_field_macros():
    header = lower(load_map(CSR_MAP), "c-header")
    defines = _defines(header)
    assert defines["APB_CSR_CTRL_MODE_SHIFT"] == 1 and defines["APB_CSR_CTRL_MODE_MASK"] == 0xE
    assert defines["APB_CSR_CTRL_MODE_RESET"] == 2 and defines["APB_CSR_CTRL_RESET"] == 4
    assert defines["APB_CSR_STATUS_VERSION_MASK"] == 0xFF00 and defines["APB_CSR_STATUS_VERSION_RESET"] == 0x12
    assert "#define APB_CSR_CTRL_MODE_GET(reg)" in header and "#define APB_CSR_CTRL_MODE_SET(reg, value)" in header
    assert "write-1-to-clear" in header
    table = lower(load_map(CSR_MAP), "markdown")
    assert "| `STATUS` | `RESET_DONE` | `[0]` | write-1-to-clear | `0x1` |" in table
    assert "| `CTRL` | `MODE` | `[3:1]` | read/write | `0x2` |" in table
    assert "Field" not in lower(load_map(APB_MAP), "markdown")  # a map with no fields lowers as in M30


@needs("cc")
def test_the_field_accessors_compile_strict_and_are_right(tmp_path):
    (tmp_path / "apb_csr_map.h").write_text(lower(load_map(CSR_MAP), "c-header"))
    (tmp_path / "use.c").write_text("""#include <stdint.h>
#include "apb_csr_map.h"
int main(void) {
    uint32_t ctrl = APB_CSR_CTRL_RESET;
    uint32_t status = APB_CSR_STATUS_RESET;
    int bad = 0;
    bad |= APB_CSR_CTRL_MODE_GET(ctrl) != 2u;
    ctrl = APB_CSR_CTRL_MODE_SET(ctrl, 7u);
    bad |= ctrl != 0xEu;
    ctrl = APB_CSR_CTRL_ENABLE_SET(ctrl, 1u);
    bad |= ctrl != 0xFu || APB_CSR_CTRL_MODE_GET(ctrl) != 7u;
    ctrl = APB_CSR_CTRL_MODE_SET(ctrl, 9u);  /* too wide: only the field's bits change */
    bad |= ctrl != 0x3u;
    bad |= APB_CSR_STATUS_VERSION_GET(status) != 0x12u || APB_CSR_STATUS_RESET_DONE_GET(status) != 1u;
    return bad;
}
""")
    built = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-o", str(tmp_path / "use"),
                            str(tmp_path / "use.c")], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    assert subprocess.run([str(tmp_path / "use")]).returncode == 0


@needs("cc")
def test_the_generated_test_compiles_strict(tmp_path):
    for regmap, name in ((load_map(CSR_MAP), "csr"), (load_map(APB_MAP), "regs")):
        (tmp_path / f"{name}.c").write_text(c_test(regmap))
        built = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", f"-I{HARNESS}",
                                "-fsyntax-only", str(tmp_path / f"{name}.c")], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr


@needs("verilator")
def test_the_field_fixture_is_lint_clean(block, tmp_path):
    run, _ = invoke(block, "lint.run", {"sources": str(CSR_RTL), "top": "apb_csr"}, tmp_path)
    assert run.succeeded, run.summary


# --- The APB host harness ----------------------------------------------------------------


def test_the_host_harness_drives_both_buses():
    buses = cosim_buses()
    assert buses["axi4-lite"].name == "axil_manager.cpp" and buses["apb"].name == "apb_manager.cpp"
    assert all(path.is_file() for path in buses.values())


@needs(*COSIM)
def test_the_apb_driver_passes_on_the_apb_rtl_in_the_host_harness(block, tmp_path):
    run, outcome = invoke(block, "fw.test", {"sources": joined(*APB_DRIVER, APB_TESTS), "rtl": str(APB_RTL),
                                             "bus": "apb"}, tmp_path)
    assert run.succeeded, run.summary
    checks = {c["name"]: c["passed"] for c in outcome.data["result"]["metrics"]["checks"]}
    assert len(checks) == 6 and all(checks.values())
    log = Path(run.references[0]).read_text()
    assert "apb_manager.cpp" in log
    assert "FWTEST BUS read 0x5 -> 0x00000000 SLVERR" in log  # the RTL's own PSLVERR
    assert "FWTEST BUS write 0x4 = 0x00ab0000 strobe 0x4 -> OKAY" in log


def _wrong_apb_driver(tmp_path: Path) -> tuple[Path, ...]:
    """The APB driver with REG2 placed on REG1's offset."""
    folder = tmp_path / "wrong"
    folder.mkdir()
    for path in (*APB_DRIVER, APB_TESTS):
        shutil.copy(path, folder / path.name)
    header = folder / "apb_regs_map.h"
    header.write_text(header.read_text().replace("APB_REGS_REG2_OFFSET 0x8u", "APB_REGS_REG2_OFFSET 0x4u"))
    return tuple(folder / p.name for p in (*APB_DRIVER, APB_TESTS))


@needs(*COSIM)
def test_a_wrong_apb_driver_fails_by_its_tests_and_against_the_map(block, tmp_path):
    wrong = _wrong_apb_driver(tmp_path)
    run, _ = invoke(block, "fw.test", {"sources": joined(*wrong), "rtl": str(APB_RTL), "bus": "apb"}, tmp_path / "a")
    assert not run.succeeded and "write_then_read_every_register" in run.summary, run.summary
    # With the approved map, the disagreement is caught at compile time, naming the macro.
    run, _ = invoke(block, "fw.test", {"sources": joined(*wrong), "rtl": str(APB_RTL), "map": str(APB_MAP)},
                    tmp_path / "b")
    assert not run.succeeded and "APB_REGS_REG2_OFFSET" in run.summary and "0x8u" in run.summary, run.summary
    run, _ = invoke(block, "fw.build", {"sources": joined(*wrong[:3]), "map": str(APB_MAP)}, tmp_path / "c")
    assert not run.succeeded and "APB_REGS_REG2_OFFSET" in run.summary, run.summary


@needs(*COSIM)
def test_the_bus_is_data_and_a_contradiction_is_a_recorded_failure(block, tmp_path):
    run, _ = invoke(block, "fw.test", {"sources": joined(*APB_DRIVER, APB_TESTS), "rtl": str(APB_RTL),
                                       "map": str(APB_MAP), "bus": "axi4-lite"}, tmp_path / "a")
    assert not run.succeeded and "contradicts" in run.summary and run.id in block.state.tool_runs
    run, _ = invoke(block, "fw.test", {"sources": joined(*APB_DRIVER, APB_TESTS), "rtl": str(APB_RTL),
                                       "bus": "ahb"}, tmp_path / "b")
    assert not run.succeeded and "no host co-simulation harness for a ahb bus" in run.summary


@needs(*COSIM)
def test_a_driver_that_writes_no_header_uses_the_generated_one(block, tmp_path):
    run, outcome = invoke(block, "fw.test", {"sources": joined(*CSR_SOURCES), "rtl": str(CSR_RTL),
                                             "map": str(CSR_MAP)}, tmp_path / "t")
    assert run.succeeded, run.summary
    checks = [c["name"] for c in outcome.data["result"]["metrics"]["checks"]]
    assert checks == ["version_and_id", "mode_keeps_enable", "bad_mode_is_refused", "reset_flag_is_acknowledged"]
    generated = tmp_path / "t" / "regmap" / "apb_csr_map.h"
    assert generated.read_text() == lower(load_map(CSR_MAP), "c-header")
    build, _ = invoke(block, "fw.build", {"sources": joined(*CSR_SOURCES), "map": str(CSR_MAP)}, tmp_path / "b")
    assert build.succeeded, build.summary
    without, _ = invoke(block, "fw.build", {"sources": joined(*CSR_SOURCES)}, tmp_path / "n")
    assert not without.succeeded and "apb_csr_map.h" in without.summary  # no map, no header


# --- The map judges APB RTL, fields included ------------------------------------------------


def _verify(engine, tmp_path, rtl: Path, regmap: RegisterMap | Path, top: str, rtl_text: str | None = None):
    if rtl_text is not None:
        rtl = tmp_path / rtl.name
        rtl.write_text(rtl_text)
    if isinstance(regmap, RegisterMap):
        path = tmp_path / "register_map.json"
        path.write_text(regmap.model_dump_json())
        regmap = path
    return invoke(engine, "regmap.verify", {"map": str(regmap), "rtl": str(rtl), "top": top}, tmp_path / "work")


@needs(*COSIM)
@pytest.mark.parametrize("rtl,regmap,top", [(APB_RTL, APB_MAP, "apb_regs"), (CSR_RTL, CSR_MAP, "apb_csr")])
def test_the_map_passes_on_the_apb_rtl_that_implements_it(block, tmp_path, rtl, regmap, top):
    run, outcome = _verify(block, tmp_path, rtl, regmap, top)
    assert run.succeeded, run.summary
    names = [c["name"] for c in outcome.data["result"]["metrics"]["checks"]]
    expected = ["reset_values", "write_then_read_every_register", "byte_strobes", "unmapped_response"]
    if top == "apb_csr":
        expected[2:2] = ["read_only_ignores_writes", "write_one_to_clear"]
    assert names == expected


@needs(*COSIM)
def test_a_map_that_disagrees_with_the_apb_rtl_fails_in_simulation(block, tmp_path):
    base = load_map(APB_MAP)
    regs = list(base.registers)
    regs[3] = regs[3].model_copy(update={"reset": 0xFFFFFFFF})
    run, _ = _verify(block, tmp_path, APB_RTL, base.model_copy(update={"registers": tuple(regs)}), "apb_regs")
    assert not run.succeeded and "reset_values" in run.summary and "REG3" in run.summary, run.summary


CSR_TEXT = CSR_RTL.read_text()


@needs(*COSIM)
@pytest.mark.parametrize("old,new,check,where", [
    ("mode <= 3'd2;", "mode <= 3'd3;", "reset_values", "CTRL.MODE"),
    ("2'd2: if (pstrb[0] && pwdata[0]) reset_done <= 1'b0;", "2'd2: if (pstrb[0]) reset_done <= pwdata[0];",
     "write_one_to_clear", "STATUS"),
    ("{16'd0, VERSION, 7'd0, reset_done}", "{16'd0, VERSION | scratch[7:0], 7'd0, reset_done}",
     "read_only_ignores_writes", "STATUS.VERSION"),
])
def test_field_mutants_fail_naming_the_check(block, tmp_path, old, new, check, where):
    assert old in CSR_TEXT
    run, _ = _verify(block, tmp_path, CSR_RTL, CSR_MAP, "apb_csr", CSR_TEXT.replace(old, new))
    assert not run.succeeded and check in run.summary and where in run.summary, run.summary


# --- block-design adopts the map -----------------------------------------------------------


def test_a_request_for_a_register_map_plans_the_stage(block, nirmaan_org, fixed_clock):
    assert "register_map" in block.state.project.analysis.features
    stage = block.task(tid(block, "register-map"))
    assert stage.capability == "arch.interface" and stage.expected_outputs == ("register_map",)
    assert stage.depends_on == (tid(block, "interface-spec"),)
    assert {t for r in stage.evidence_requirements if r.before_review for t in r.tools} == {"regmap.check"}
    rtl = block.task(tid(block, "rtl-implementation"))
    assert tid(block, "register-map") in rtl.depends_on
    verify = next(r for r in rtl.evidence_requirements if r.tools == ("regmap.verify",))
    assert verify.before_review and {(b.param, b.upstream) for b in verify.files} == {
        ("map", True), ("rtl", False), ("top", False)}
    firmware = block.task(tid(block, "firmware"))
    assert tid(block, "register-map") in firmware.depends_on
    for req in (r for r in firmware.evidence_requirements if r.before_review):
        assert any(b.param == "map" and b.upstream and b.optional for b in req.files), req.description
    # A register block whose request asks for no map plans none, and no regmap.verify.
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an APB register block and its driver.")
    assert "register-map" not in {t.stage for t in plain.state.tasks.values()}
    rtl = plain.task(tid(plain, "rtl-implementation"))
    assert all("regmap.verify" not in r.tools for r in rtl.evidence_requirements)


def _seat(engine, stage: str, source: str, files: list[tuple[str, str, str, str | None]], tmp_path: Path):
    """Run one seat with these files ((name, kind, content, entry)); return its report."""
    seat = tid(engine, stage)
    workspace(engine, seat, tmp_path / stage)
    cite = token(engine.task(tid(engine, source)).artifacts[0])
    llm = MockLLM(script=[answer(*(file(name, kind, content, cite, entry) for name, kind, content, entry in files))])
    return run_task(engine, seat, ModelRuntime(llm))


def _approve(engine, stage: str) -> None:
    seat = tid(engine, stage)
    review_task(engine, seat, ModelRuntime(MockLLM()))
    engine.approve(seat, human(engine.task(seat).approver), "agreed")
    assert engine.task(seat).status is TaskStatus.COMPLETED


def _up_to_rtl(engine, tmp_path: Path, map_text: str) -> None:
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, files in (
            ("interface-spec", "requirements",
             [("interface_spec.md", "interface_spec", (APB / "interface_spec.md").read_text(), None)]),
            ("register-map", "interface-spec", [("register_map.json", "register_map", map_text, None)]),
            ("microarchitecture", "interface-spec",
             [("microarchitecture.md", "microarchitecture_spec", (APB / "microarchitecture.md").read_text(), None)])):
        report = _seat(engine, stage, source, files, tmp_path)
        assert report.status is ResultStatus.SUBMITTED, report.detail
        _approve(engine, stage)


RTL_FILES = [("apb_regs.v", "rtl_source", APB_RTL.read_text(), "apb_regs"),
             ("apb_regs_tb.v", "testbench", (APB / "apb_regs_tb.v").read_text(), "apb_regs_tb")]


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_block_design_adopts_the_map_end_to_end(block, tmp_path):
    _up_to_rtl(block, tmp_path, APB_MAP.read_text())
    map_art = block.state.artifacts[block.task(tid(block, "register-map")).artifacts[0]]
    assert map_art.kind == "register_map" and map_art.assurance is Assurance.APPROVED

    report = _seat(block, "rtl-implementation", "microarchitecture", RTL_FILES, tmp_path)
    assert report.status is ResultStatus.SUBMITTED, report.detail
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    verify = runs["regmap.verify"]
    assert verify.succeeded and verify.params["map"] == map_art.location, verify.summary
    _approve(block, "rtl-implementation")

    files = [(p.name, "driver", p.read_text(), None) for p in APB_DRIVER]
    files.append((APB_TESTS.name, "driver_test", APB_TESTS.read_text(), None))
    report = _seat(block, "firmware", "interface-spec", files, tmp_path)
    assert report.status is ResultStatus.SUBMITTED, report.detail
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    assert {"fw.build", "fw.test"} <= set(runs) and all(r.succeeded for r in runs.values())
    assert runs["fw.test"].params["map"] == map_art.location  # the approved map chose the APB harness
    assert "apb_manager.cpp" in Path(runs["fw.test"].references[0]).read_text()
    _approve(block, "firmware")


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_rtl_that_disagrees_with_the_approved_map_cannot_reach_review(block, tmp_path):
    wrong = APB_MAP.read_text().replace('{"name": "REG3", "offset": 12, "access": "rw", "reset": 0}',
                                         '{"name": "REG3", "offset": 12, "access": "rw", "reset": 1}')
    assert wrong != APB_MAP.read_text()
    _up_to_rtl(block, tmp_path, wrong)
    report = _seat(block, "rtl-implementation", "microarchitecture", RTL_FILES, tmp_path)
    assert report.status is ResultStatus.REFUSED, report.detail
    runs = {block.state.tool_runs[r].tool: block.state.tool_runs[r] for r in report.tool_runs}
    assert runs["simulator.run"].succeeded  # the testbench passes: only the map catches it
    assert not runs["regmap.verify"].succeeded and "reset_values" in runs["regmap.verify"].summary
    assert block.task(tid(block, "rtl-implementation")).status is TaskStatus.IN_PROGRESS


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_a_driver_run_without_the_approved_map_does_not_open_review(block, tmp_path):
    from nirmaan.models import EvidenceKind
    from nirmaan.work import PolicyViolationError

    _up_to_rtl(block, tmp_path, APB_MAP.read_text())
    assert _seat(block, "rtl-implementation", "microarchitecture", RTL_FILES, tmp_path).status \
        is ResultStatus.SUBMITTED
    _approve(block, "rtl-implementation")
    seat = tid(block, "firmware")
    owner = agent(block.task(seat).owner)
    block.start(seat, owner)
    folder = tmp_path / "manual"
    folder.mkdir()
    copies = [Path(shutil.copy(p, folder / p.name)) for p in (*APB_DRIVER, APB_TESTS)]
    rtl = block.task(tid(block, "rtl-implementation"))
    approved = next(block.state.artifacts[a].location for a in rtl.artifacts
                    if block.state.artifacts[a].kind == "rtl_source")
    broker = ToolBroker(block)
    build, _ = broker.invoke(owner, "fw.build", {"sources": joined(*copies[:3]), "workdir": str(tmp_path / "b")},
                             seat)
    test, _ = broker.invoke(owner, "fw.test", {"sources": joined(*copies), "rtl": approved, "bus": "apb",
                                               "workdir": str(tmp_path / "t")}, seat)
    assert build.succeeded and test.succeeded
    for run in (build, test):
        block.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
    drafts = [{"kind": "driver", "title": p.name, "location": str(p)} for p in copies[:3]]
    drafts.append({"kind": "driver_test", "title": copies[3].name, "location": str(copies[3])})
    with pytest.raises(PolicyViolationError, match="approved upstream register_map"):
        block.submit(seat, owner, drafts)


# --- Crown jewel: a new co-simulation bus needs no core changes -----------------------------


@needs(*COSIM)
def test_a_new_cosimulation_bus_needs_no_core_changes(block, tmp_path):
    manager = tmp_path / "managers" / "apb4_manager.cpp"
    manager.parent.mkdir()
    shutil.copy(HARNESS / "apb_manager.cpp", manager)
    register_cosim_bus("apb4-test", manager)
    try:
        assert "apb4-test" in cosim_buses()
        run, _ = invoke(block, "fw.test", {"sources": joined(*APB_DRIVER, APB_TESTS), "rtl": str(APB_RTL),
                                           "bus": "apb4-test"}, tmp_path / "w")
        assert run.succeeded, run.summary
        assert "apb4_manager.cpp" in Path(run.references[0]).read_text()
    finally:
        unregister_cosim_bus("apb4-test")
    assert "apb4-test" not in cosim_buses()


def test_the_changed_modules_keep_the_import_laws():
    src = Path(__file__).parents[1] / "src" / "nirmaan"
    for path in (src / "regmap.py", src / "models" / "regmap.py", src / "integrations" / "regmap.py",
                 src / "integrations" / "firmware.py"):
        tree = ast.parse(path.read_text())
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(n.startswith("veritriage") for n in names), path
