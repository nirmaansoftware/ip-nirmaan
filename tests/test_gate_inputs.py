"""M84 (docs/GATE_INPUTS.md): a gate runs nothing a seat's file asks of the host outside its run.

Must-fail: each construct that reached a shell (or other code) through a gate is refused before any step runs,
and the marker file its payload would create is never there. Two controls show the payload is live: with the
check bypassed, the marker appears. Must-pass: every committed gate input still passes the checks, and an
ordinary testbench still simulates.

Every payload only creates a marker file inside the test's own temporary directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from nirmaan.integrations import dft, eda, eda_guard, regmap  # noqa: F401  (dft, regmap: their backends)
from nirmaan.integrations.eda import backends_for, execute
from nirmaan.integrations.eda_guard import (
    SAFE_SYSTEM,
    check_inputs,
    name_problem,
    sby_problem,
    sdc_problem,
    verilog_problem,
    yosys_problem,
)
from nirmaan.integrations.equivalence import setup_files
from nirmaan.integrations.physical import _sta_inputs

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DESIGN = "module m(input a, output b);\n  assign b = a;\nendmodule\n"


def backend(tool: str, name: str):
    return next(b for b in backends_for(tool) if b.name == name)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def refused(outcome, marker: Path, *words: str) -> None:
    """The run was refused before any step (no log was written) and the payload never ran."""
    assert not outcome.succeeded
    assert "refused, nothing ran" in outcome.summary or "nothing was simulated" in outcome.summary, outcome.summary
    assert not outcome.references, "a refused run writes no log: no step ran"
    for word in words:
        assert word in outcome.summary, outcome.summary
    assert not marker.exists(), f"the payload ran: {marker} exists"


# --- top: Yosys and Tcl scripts take it as text ------------------------------------------------


@pytest.mark.parametrize("tool,name", [("synth.run", "yosys"), ("lint.run", "verilator-lint"),
                                       ("simulator.run", "icarus"), ("dft.check", "yosys-dft")])
@pytest.mark.parametrize("payload", ["m\n!touch {marker}", "m; exec -- touch {marker}", "m;!touch {marker}"])
def test_a_top_that_is_not_a_name_is_refused_before_any_tool_runs(tmp_path, tool, name, payload):
    marker = tmp_path / "MARKER"
    src = write(tmp_path / "m.v", DESIGN)
    outcome = execute(backend(tool, name), {"sources": str(src), "top": payload.format(marker=marker),
                                             "workdir": str(tmp_path / "run")})
    refused(outcome, marker, "top must be a plain module name")


@pytest.mark.skipif(shutil.which("yosys") is None, reason="needs yosys")
def test_control_without_the_check_a_top_reaches_the_shell(tmp_path, monkeypatch):
    """The payload above is live: with the check bypassed, Yosys runs it."""
    marker = tmp_path / "MARKER"
    src = write(tmp_path / "m.v", DESIGN)
    monkeypatch.setattr(eda, "check_inputs", lambda *a: None)
    execute(backend("synth.run", "yosys"), {"sources": str(src), "top": f"m; exec -- touch {marker}"})
    assert marker.exists()


@pytest.mark.skipif(shutil.which("yosys") is None, reason="needs yosys")
def test_a_plain_top_still_synthesizes(tmp_path):
    src = write(tmp_path / "m.v", DESIGN)
    outcome = execute(backend("synth.run", "yosys"), {"sources": str(src), "top": "m"})
    assert outcome.succeeded, outcome.summary


def test_names_and_paths():
    assert name_problem("sync_fifo_tb") is None and name_problem("a$b") is None and name_problem("") is None
    for bad in ("m;x", "m\nx", "m x", "1m", "m\"", "../m"):
        assert name_problem(bad)
    assert check_inputs("m", {"sources": ['/tmp/a".v']})


# --- Verilog: what a simulation runs ---------------------------------------------------------------


def tb(body: str, name: str = "tb") -> str:
    return f"module {name};\n  integer fd;\n  initial begin\n{body}\n    $finish;\n  end\nendmodule\n"


PAYLOADS = {
    "system": '    $system("touch {marker}");',
    "fopen": '    fd = $fopen("{marker}", "w"); $fwrite(fd, "x"); $fclose(fd);',
    "dumpfile": '    $dumpfile("{marker}"); $dumpvars;',
    "writememh": '    $writememh("{marker}", mem);',
    "c": '    $c("system(\\"touch {marker}\\");");',
    "dpi": '    end\n  import "DPI-C" function int system(input string c);\n  initial begin\n'
           '    fd = system("touch {marker}");',
    "paste": "`define CALL(x) $sys``x\n    `CALL(tem)(\"touch {marker}\");",
}


@pytest.mark.parametrize("backend_name", ["icarus", "verilator-sim"])
@pytest.mark.parametrize("construct", sorted(PAYLOADS))
def test_a_testbench_that_reaches_outside_the_simulation_is_refused(tmp_path, backend_name, construct):
    marker = tmp_path / "MARKER"
    source = write(tmp_path / "tb.v", tb(PAYLOADS[construct].format(marker=marker)))
    outcome = execute(backend("simulator.run", backend_name), {"sources": str(source), "top": "tb"})
    refused(outcome, marker)


@pytest.mark.skipif(shutil.which("verilator") is None, reason="needs verilator")
def test_control_without_the_check_a_testbench_reaches_the_shell(tmp_path, monkeypatch):
    """Verilator runs a testbench's $system (Homebrew's Icarus 13 defines none; other builds do)."""
    marker = tmp_path / "MARKER"
    source = write(tmp_path / "tb.v", tb(PAYLOADS["system"].format(marker=marker)))
    monkeypatch.setattr(eda, "check_inputs", lambda *a: None)
    execute(backend("simulator.run", "verilator-sim"), {"sources": str(source), "top": "tb"})
    assert marker.exists()


def test_an_included_file_is_checked_whatever_its_name(tmp_path):
    marker = tmp_path / "MARKER"
    write(tmp_path / "calls.inc", f'    $system("touch {marker}");\n')
    source = write(tmp_path / "tb.v", tb('`include "calls.inc"'))
    outcome = execute(backend("simulator.run", "icarus"), {"sources": str(source), "top": "tb"})
    refused(outcome, marker, "calls.inc uses $system")
    for include in ('`include "/etc/hosts"', '`include "../x.vh"', "`include `FILE"):
        assert verilog_problem([write(tmp_path / "t.v", tb(include))])


def test_verilator_systemc_blocks_and_c_sources_are_refused(tmp_path):
    marker = tmp_path / "MARKER"
    systemc = write(tmp_path / "tb.v", tb("") + f'`systemc_imp_header\nint x = system("touch {marker}");\n`verilog\n')
    refused(execute(backend("simulator.run", "verilator-sim"), {"sources": str(systemc), "top": "tb"}), marker,
            "`systemc_imp_header")
    cpp = write(tmp_path / "evil.cpp", f'#include <cstdlib>\nstatic int x = std::system("touch {marker}");\n')
    plain = write(tmp_path / "ok.v", tb(""))
    outcome = execute(backend("simulator.run", "verilator-sim"), {"sources": f"{plain},{cpp}", "top": "tb"})
    refused(outcome, marker, "evil.cpp is not")


def test_the_rtl_a_cosimulation_compiles_is_checked(tmp_path):
    """regmap.verify and fw.test compile the approved RTL (``rtl``) into the program they run."""
    marker = tmp_path / "MARKER"
    rtl = write(tmp_path / "regs.v", "module regs;\n  initial $system(\"touch " + str(marker) + "\");\nendmodule\n")
    outcome = execute(backend("regmap.verify", "regmap-cosim"),
                      {"map": str(FIXTURES / "rtl" / "axi4_lite" / "register_map.json"), "rtl": str(rtl)})
    refused(outcome, marker, "regs.v uses $system")


def test_strings_and_comments_hold_no_construct_and_plain_dumpfiles_pass(tmp_path):
    text = tb('    $display("$system $fopen // ok"); // $system("x")\n    /* $c("x") */\n'
              '    $dumpfile("waves.vcd"); $dumpvars(0, tb);')
    assert verilog_problem([write(tmp_path / "tb.v", text)]) is None
    assert verilog_problem([write(tmp_path / "tb.v", tb('    $dumpfile("../waves.vcd");'))])
    assert "$readmemh" in verilog_problem([write(tmp_path / "tb.v", tb('    $readmemh("/etc/hosts", m);'))])


def test_every_system_task_in_the_allow_list_touches_no_file():
    """The allow list names no task that opens, reads or writes a file, or runs anything."""
    for name in ("$system", "$c", "$fopen", "$fwrite", "$fdisplay", "$readmemh", "$readmemb", "$writememh",
                 "$sdf_annotate", "$fgets", "$fscanf", "$fread", "$cpure", "$save", "$restart"):
        assert name not in SAFE_SYSTEM


@pytest.mark.skipif(shutil.which("iverilog") is None, reason="needs iverilog")
def test_an_ordinary_testbench_still_simulates(tmp_path):
    source = write(tmp_path / "tb.v", tb('    if (!$value$plusargs("nirmaan_nonce=%s", nonce)) $fatal(1, "no nonce");\n'
                                         '    $dumpfile("waves.vcd"); $dumpvars(0, tb);\n'
                                         '    $display("NIRMAAN-SIM %0s 1 passed, 0 failed", nonce);').replace(
        "integer fd;", "reg [255:0] nonce;"))
    outcome = execute(backend("simulator.run", "icarus"), {"sources": str(source), "top": "tb"})
    assert outcome.succeeded, outcome.summary


# --- SBY setups -------------------------------------------------------------------------------------


def sby(tmp_path: Path, *, options="mode bmc\ndepth 2", engines="smtbmc", script="read -formal m.v\nprep -top m",
        extra="", files="m.v") -> Path:
    write(tmp_path / "m.v", DESIGN)
    return write(tmp_path / "f.sby", f"[options]\n{options}\n\n[engines]\n{engines}\n\n[script]\n{script}\n\n"
                                     f"[files]\n{files}\n{extra}")


SBY_PAYLOADS = {
    "bang": dict(script="!touch {marker}\nread -formal m.v\nprep -top m"),
    "exec": dict(script="read -formal m.v; exec -- touch {marker}\nprep -top m"),
    "script": dict(script="read -formal m.v\nscript evil.ys\nprep -top m"),
    "tee": dict(script="read -formal m.v\ntee -q -o {marker} stat\nprep -top m"),
    "show": dict(script="read -formal m.v\nshow -viewer touch\nprep -top m"),
    "pycode": dict(extra="--pycode-begin--\nimport os; os.system('touch {marker}')\n--pycode-end--\n"),
    "engine": dict(engines="smtbmc yices;touch {marker}"),
    "engine-pass": dict(engines="smtbmc yices -- --dummy {marker}"),
    "option": dict(options="mode bmc\ndepth 2\ntbtop m;touch {marker}"),
    "file-section": dict(extra="[file evil.ys]\n!touch {marker}\n"),
    "dest": dict(files="../../MARKER m.v"),
    "verilog": dict(files="m.v\ntb.v"),
}


@pytest.mark.parametrize("tool,name", [("formal.run", "symbiyosys"), ("formal.cover", "symbiyosys-cover")])
@pytest.mark.parametrize("construct", sorted(SBY_PAYLOADS))
def test_a_formal_setup_that_reaches_outside_yosys_is_refused(tmp_path, tool, name, construct):
    marker = tmp_path / "MARKER"
    write(tmp_path / "tb.v", tb(PAYLOADS["system"].format(marker=marker)))
    setup = sby(tmp_path, **{k: v.format(marker=marker) for k, v in SBY_PAYLOADS[construct].items()})
    refused(execute(backend(tool, name), {"sby": str(setup), "workdir": str(tmp_path / "run")}), marker)


@pytest.mark.skipif(shutil.which("sby") is None, reason="needs sby")
def test_control_without_the_check_a_setup_reaches_the_shell(tmp_path, monkeypatch):
    marker = tmp_path / "MARKER"
    setup = sby(tmp_path, **{k: v.format(marker=marker) for k, v in SBY_PAYLOADS["bang"].items()})
    monkeypatch.setattr(eda, "sby_problem", lambda *a: None)
    execute(backend("formal.run", "symbiyosys"), {"sby": str(setup)})
    assert marker.exists()


@pytest.mark.skipif(shutil.which("sby") is None, reason="needs sby")
def test_an_ordinary_setup_still_proves(tmp_path):
    outcome = execute(backend("formal.run", "symbiyosys"), {"sby": str(sby(tmp_path, engines="smtbmc yices"))})
    assert outcome.succeeded, outcome.summary


# --- eqy setups ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("gold,strategy", [("read_verilog -sv m.v; abc -exe touch", "engine smtbmc"),
                                           ("read_verilog -sv m.v\nshow -viewer touch", "engine smtbmc"),
                                           ("read_verilog -sv m.v", "engine smtbmc yices;touch")])
def test_an_equivalence_setup_that_reaches_outside_yosys_is_refused(tmp_path, gold, strategy):
    write(tmp_path / "m.v", DESIGN)
    write(tmp_path / "n.v", DESIGN.replace("module m", "module n"))
    eqy = write(tmp_path / "s.eqy", f"[gold]\n{gold}\nprep -top m\n\n[gate]\nread_verilog -sv n.v\nprep -top n\n\n"
                                    f"[strategy sby]\nuse sby\n{strategy}\ndepth 10\n")
    sides, problem = setup_files(eqy)
    assert problem and "refused, nothing ran" in problem and not sides


# --- Timing constraints ------------------------------------------------------------------------------


@pytest.mark.parametrize("line", ["exec touch MARKER", "set x [exec touch MARKER]", "source evil.tcl",
                                  "set f [open MARKER w]", "proc get_ports {a} {exec touch MARKER}",
                                  "set c exec; $c touch MARKER", "set x [$c touch MARKER]",
                                  "create_clock -period [expr {[exec touch MARKER]}] clk", "eval exec touch MARKER",
                                  "set_input_delay 1 [::exec touch MARKER]", "uplevel #0 {exec touch MARKER}",
                                  'set x "{"\nexec touch MARKER', "set x a{\nexec touch MARKER",
                                  "set x \\\\[exec touch MARKER]", "{*}$c touch MARKER"])
def test_constraints_that_run_tcl_outside_sdc_are_refused(tmp_path, line):
    sdc = write(tmp_path / "c.sdc", f"create_clock -name clk -period 10 [get_ports clk]\n{line}\n")
    assert sdc_problem(sdc), line
    job = eda.Job("sta.run", {"sdc": str(sdc), "netlist": str(sdc)}, tmp_path, (), "top")
    assert _sta_inputs(job)


def test_ordinary_constraints_pass(tmp_path):
    sdc = write(tmp_path / "c.sdc", "# a comment; with [exec x] in it\nset period 10.0\n"
                                    "set_input_delay [expr $period * 0.2] -clock clk {data[0] data[*]}\n"
                                    "set_clock_groups -asynchronous -group {\n  clk_a\n} -group {clk_b}\n"
                                    "set_load 0.01 [all_outputs]; set_false_path -from [get_ports rst_n]\n")
    assert sdc_problem(sdc) is None


# --- Must-pass: every committed gate input -------------------------------------------------------------


def committed(*suffixes: str) -> list[Path]:
    return sorted(p for s in suffixes for p in (ROOT / "tests" / "fixtures").rglob(f"*{s}"))


def test_every_committed_design_and_testbench_passes():
    paths = committed(".v", ".sv", ".vh") + sorted((ROOT / "evals").rglob("*.v"))
    assert paths
    assert [p for p in paths if verilog_problem([p])] == []


def test_every_committed_single_task_setup_and_constraints_file_passes():
    setups = [p for p in committed(".sby") if "[tasks]" not in p.read_text()]
    assert setups and [p for p in setups if sby_problem(p)] == []
    constraints = committed(".sdc")
    assert constraints and [p for p in constraints if sdc_problem(p)] == []


def test_the_yosys_allow_list_writes_nothing_and_runs_nothing():
    for command in ("exec", "tcl", "python", "script", "plugin", "tee", "show", "select", "abc", "abc9", "bugpoint",
                    "write_verilog", "dump", "log", "design", "sat", "sim"):
        assert command not in eda_guard.YOSYS_SAFE
        assert yosys_problem([f"{command} x"], "s")
