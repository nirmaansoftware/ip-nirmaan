"""Milestone 30 (working name): the register map as data, validated, lowered, and judging RTL.

A register map that lives only as a table in a specification cannot be checked
or turned into code. As a ``RegisterMap`` it is validated, lowered (a C header,
the specification's own table), and used to generate a test that runs on the
RTL through the AXI4-Lite co-simulation harness, so the map itself judges
whether the RTL implements it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import human, tid
from test_nirmaan_design_agents import needs

from nirmaan.cli import app
from nirmaan.models import RegisterMap, Unmapped
from nirmaan.orchestrator import Orchestrator
from nirmaan.regmap import load_map, lower, lowerings, register_lowering, unregister_lowering, validate
from nirmaan.runtime import ToolBroker

AXI = Path(__file__).parent / "fixtures" / "rtl" / "axi4_lite"
FW = Path(__file__).parent / "fixtures" / "fw" / "axi4_lite"
MAP = AXI / "register_map.json"
COSIM = ("cc", "verilator", "make")


def _map(**changes) -> RegisterMap:
    return load_map(MAP).model_copy(update=changes)


def _with_register(index: int, **changes) -> RegisterMap:
    base = load_map(MAP)
    regs = list(base.registers)
    regs[index] = regs[index].model_copy(update=changes)
    return base.model_copy(update={"registers": tuple(regs)})


@pytest.fixture()
def rtl_seat(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    task = engine.task(tid(engine, "rtl-implementation"))
    return engine, human(task.owner), task.id


def _verify(seat, tmp_path, rtl_text: str | None = None, regmap: RegisterMap | None = None):
    engine, actor, task = seat
    rtl = AXI / "axi4_lite_regs.v"
    if rtl_text is not None:
        rtl = tmp_path / "axi4_lite_regs.v"
        rtl.write_text(rtl_text)
    map_path = MAP
    if regmap is not None:
        map_path = tmp_path / "register_map.json"
        map_path.write_text(regmap.model_dump_json())
    return ToolBroker(engine).invoke(actor, "regmap.verify", {
        "map": str(map_path), "rtl": [str(rtl)], "top": "axi4_lite_regs", "workdir": str(tmp_path / "work")}, task)


# --- The representation and its validation ------------------------------------------------


def test_the_fixture_map_is_clean_and_is_its_specification_table():
    regmap = load_map(MAP)
    assert validate(regmap) == []
    table = lower(regmap, "markdown")
    spec = (AXI / "interface_spec.md").read_text()
    for line in table.strip().splitlines():
        assert line in spec, line  # the specification's table, line for line


@pytest.mark.parametrize("regmap,problem", [
    (_map(data_width=16), "data width"),
    (_with_register(1, offset=6), "aligned"),
    (_with_register(3, offset=16), "address space"),
    (_with_register(2, offset=4), "offset 0x4"),
    (_with_register(2, name="REG1"), "twice"),
    (_with_register(0, name="reg 0"), "C identifier"),
    (_with_register(0, reset=1 << 32), "wider"),
    (_map(registers=()), "no registers"),
])
def test_validation_names_each_problem(regmap, problem):
    problems = validate(regmap)
    assert any(problem in p for p in problems), problems


# --- Lowerings ------------------------------------------------------------------------------


def _defines(text: str) -> dict[str, int]:
    return {name: int(value.rstrip("uU"), 0) for name, value in
            re.findall(r"#define (\w+) (0x[0-9A-Fa-f]+u|\d+u)", text)}


@needs("cc")
def test_the_c_header_compiles_strict_and_agrees_with_the_hand_written_one(tmp_path):
    header = lower(load_map(MAP), "c-header")
    (tmp_path / "regs.h").write_text(header)
    (tmp_path / "use.c").write_text('#include "regs.h"\nint main(void) { return (int)AXI4_LITE_REGS_COUNT - 4; }\n')
    built = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-o", str(tmp_path / "use"),
                            str(tmp_path / "use.c")], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    generated, written = _defines(header), _defines((FW / "axi4_lite_regs_map.h").read_text())
    for n in range(4):
        assert generated[f"AXI4_LITE_REGS_REG{n}_OFFSET"] == written[f"AXIL_REGS_REG{n}_OFFSET"]
        assert generated[f"AXI4_LITE_REGS_REG{n}_RESET"] == written["AXIL_REGS_RESET_VALUE"]
    assert generated["AXI4_LITE_REGS_COUNT"] == written["AXIL_REGS_COUNT"]


# --- The map judges the RTL -----------------------------------------------------------------


@needs(*COSIM)
def test_the_map_passes_on_the_rtl_that_implements_it(rtl_seat, tmp_path):
    run, outcome = _verify(rtl_seat, tmp_path)
    assert run.succeeded, run.summary
    assert "0 failed" in run.summary or "passed" in run.summary


@needs(*COSIM)
@pytest.mark.parametrize("old,new,check", [
    ("reg3 <= {DATA_WIDTH{1'b0}};", "reg3 <= {DATA_WIDTH{1'b1}};", "reset"),
    ("2'd2: reg2 <= merge(reg2, wr_data, wr_strb);", "2'd2: reg1 <= merge(reg1, wr_data, wr_strb);", "write_then_read"),
])
def test_the_map_fails_rtl_that_does_not_implement_it(rtl_seat, tmp_path, old, new, check):
    original = (AXI / "axi4_lite_regs.v").read_text()
    assert old in original
    run, _ = _verify(rtl_seat, tmp_path, rtl_text=original.replace(old, new))
    assert not run.succeeded and check in run.summary, run.summary


@needs(*COSIM)
def test_a_map_that_misstates_the_unmapped_response_fails(rtl_seat, tmp_path):
    run, _ = _verify(rtl_seat, tmp_path, regmap=_map(unmapped=Unmapped.OKAY))
    assert not run.succeeded and "unmapped" in run.summary, run.summary


@needs(*COSIM)
def test_a_bus_with_no_harness_is_a_recorded_failure_not_a_simulation(rtl_seat, tmp_path):
    engine = rtl_seat[0]
    run, _ = _verify(rtl_seat, tmp_path, regmap=_map(bus="apb"))
    assert not run.succeeded and "harness" in run.summary and "apb" in run.summary
    assert run.id in engine.state.tool_runs


def test_regmap_check_records_validation_as_a_run(rtl_seat, tmp_path):
    engine, actor, task = rtl_seat
    good, _ = ToolBroker(engine).invoke(actor, "regmap.check", {"map": str(MAP)}, task)
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(_with_register(2, offset=4).model_dump_json())
    bad, _ = ToolBroker(engine).invoke(actor, "regmap.check", {"map": str(bad_path)}, task)
    assert good.succeeded and not bad.succeeded and "0x4" in bad.summary


def test_the_axi4_lite_evaluation_case_holds_the_map_out():
    case = json.loads((Path(__file__).parents[1] / "evals" / "rtl" / "axi4_lite_regs.json").read_text())
    tools = [check.get("tool") for check in case["held_out"]]
    assert tools == ["simulator.run", "regmap.verify"]


# --- CLI and the crown jewel ----------------------------------------------------------------


def test_the_cli_checks_and_lowers(tmp_path):
    ok = CliRunner().invoke(app, ["regmap", "check", str(MAP)])
    assert ok.exit_code == 0 and "4 registers" in ok.output
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(_with_register(2, offset=4).model_dump_json())
    bad = CliRunner().invoke(app, ["regmap", "check", str(bad_path)])
    assert bad.exit_code == 1 and "0x4" in bad.output
    header = CliRunner().invoke(app, ["regmap", "lower", str(MAP), "--to", "c-header"])
    assert header.exit_code == 0 and "#define AXI4_LITE_REGS_REG3_OFFSET 0xCu" in header.output


def test_a_new_lowering_needs_no_core_changes():
    @register_lowering("python-constants")
    def python_constants(regmap: RegisterMap) -> str:
        return "".join(f"{r.name} = {r.offset:#x}\n" for r in regmap.registers)

    try:
        assert "python-constants" in lowerings()
        out = CliRunner().invoke(app, ["regmap", "lower", str(MAP), "--to", "python-constants"])
        assert out.exit_code == 0 and "REG3 = 0xc" in out.output
    finally:
        unregister_lowering("python-constants")
    assert "python-constants" not in lowerings()
