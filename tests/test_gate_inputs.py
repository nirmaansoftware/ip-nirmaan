"""M84 (docs/GATE_INPUTS.md): a gate runs nothing a seat's file asks of the host outside its run.

Must-fail: each construct that reached a shell (or other code) through a gate is refused before any step runs,
and the marker file its payload would create is never there. Three controls show the payloads are live: with the
check bypassed, the marker appears. Must-pass: every committed gate input still passes the checks, and an
ordinary testbench still simulates.

Every payload only creates a marker file inside the test's own temporary directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from laws import needs

from nirmaan.integrations import dft, eda, eda_guard, firmware, regmap  # noqa: F401  (their backends)
from nirmaan.integrations.eda import backends_for, execute
from nirmaan.integrations.eda_guard import (
    SAFE_SYSTEM,
    check_inputs,
    eqy_problem,
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


def test_rtl_and_design_refuse_non_verilog_files():
    for param in ("rtl", "design"):
        for name in ("/tmp/evil.cpp", "/tmp/regs.txt", "/tmp/x.c"):
            assert "not Verilog" in check_inputs("m", {param: ["/tmp/regs.v", name]})

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
    regmap_map = str(FIXTURES / "rtl" / "axi4_lite" / "register_map.json")
    cpp = write(tmp_path / "regs.cpp", f'#include <cstdlib>\nstatic int x = std::system("touch {marker}");\n')
    renamed = write(tmp_path / "regs.txt", rtl.read_text())
    for given, words in ((cpp, "regs.cpp is not"), (renamed, "regs.txt is not")):
        for tool, name in (("regmap.verify", "regmap-cosim"), ("fw.test", "verilator-cosim")):
            params = {"map": regmap_map, "rtl": str(given), "sources": str(FIXTURES / "fw" / "axi4_lite" /
                                                                           "axi4_lite_regs_test.c")}
            refused(execute(backend(tool, name), params if tool == "fw.test" else {"map": regmap_map,
                                                                                   "rtl": str(given)}),
                    marker, words)


def test_a_source_of_any_name_is_checked_as_verilog(tmp_path):
    """Icarus reads a file of any name as Verilog, so dft.scan_sim would simulate a tb.txt."""
    marker = tmp_path / "MARKER"
    renamed = write(tmp_path / "design.txt", "module m;\n  initial $system(\"touch " + str(marker) + "\");\nendmodule\n")
    outcome = execute(backend("dft.scan_sim", "icarus-scan"), {"sources": str(renamed), "top": "m"})
    refused(outcome, marker, "design.txt uses $system")


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
                                           ("read_verilog -sv m.v", "engine smtbmc yices;touch"),
                                           ("read_verilog -sv m.v", "engine smtbmc\noption tbtop m;touch"),
                                           ("read_verilog -sv m.v", "engine smtbmc\n[pycode x]")])
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


# --- ET1: forms the check and a tool read differently ------------------------------------------------
# council/records/2026-11-22-eda-tools-seat-account.md, decision 4: each file of fact 9 (and four of the same two
# classes found while building the repair) is refused through every gate that reads Verilog, and a control per
# fixture shows, with the check bypassed, a tool acting on it. Each fixture reaches only a canary file (or writes a
# marker) in the test's own temporary directory, outside the run's folder; three judge files are reached too.

BYPASS = FIXTURES / "screen_bypass"
CANARY = "canary_et1_7f3a"
#: The gates whose tools read seat Verilog on the timer path (record, fact 5), and dft.scan_sim, which reads a source
#: of any name as Verilog.
VERILOG_GATES = [("lint.run", "verilator-lint"), ("simulator.run", "icarus"), ("simulator.run", "verilator-sim"),
                 ("synth.run", "yosys")]
FORMAL_GATES = [("formal.run", "symbiyosys"), ("formal.cover", "symbiyosys-cover")]
#: For each fixture, the backends whose tool acts on it with the check bypassed: it reads the canary (its name or
#: content reaches the run's output), changes the synthesized result with the canary's content (yosys, readmem
#: fixtures), or writes the marker (glued_macro_call). Found on Icarus 13, Verilator 5.052 and Yosys 0.69.
LIVE = {
    "define_comment": ["icarus"],
    "dollar_macro": ["icarus", "verilator-sim", "yosys"],
    "esc_block": ["verilator-lint", "verilator-sim", "yosys"],
    "esc_line": ["verilator-lint", "verilator-sim", "yosys"],
    "esc_quote": ["verilator-lint", "icarus", "verilator-sim", "yosys"],
    "glued_macro_call": ["icarus", "verilator-sim"],
    "ifdef_continued_quote_include": ["icarus"],
    "ifdef_continued_quote_readmem": ["icarus"],
    "ifdef_lone_quote_include": ["yosys"],
    "ifdef_lone_quote_readmem": ["yosys"],
    "ifdef_quote_include": ["icarus"],
    "split_macro": ["icarus", "verilator-sim", "yosys"],
    "undef_comment": ["icarus"],
}
JUDGE = ["tests/fixtures/rtl/axil_timer/axil_timer.v", "evals/flow/axil_timer/axil_timer_tb.v",
         "tests/fixtures/rtl/axil_timer/mutants/axil_timer_stop_ignored.v"]
TOOL = {"verilator-lint": ("verilator",), "icarus": ("iverilog", "vvp"), "verilator-sim": ("verilator", "make"),
        "yosys": ("yosys",)}
GATE_OF = {name: tool for tool, name in VERILOG_GATES}


def bypass_file(tmp_path: Path, fixture: str, bit: str = CANARY, include: str | None = None) -> tuple[Path, Path]:
    """The fixture as a seat's ``run/m.v``, its canaries in ``outside/``: the file and the marker it may write."""
    (tmp_path / "run").mkdir(exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    vh = write(outside / "CANARY_ET1.vh", f"{CANARY} ! ;\n")
    hexfile = write(outside / "CANARY_ET1.hex", f"{bit}\n")
    marker = outside / "MARKER"
    text = (BYPASS / f"{fixture}.v.tpl").read_text(encoding="utf-8")
    text = text.replace("{canary_vh}", include or str(vh)).replace("{canary_hex}", str(hexfile))
    return write(tmp_path / "run" / "m.v", text.replace("{marker}", str(marker))), marker


def printed(outcome) -> str:
    return outcome.summary + "".join(Path(r).read_text(encoding="utf-8", errors="replace")
                                     for r in outcome.references if Path(r).is_file())


def test_every_bypass_fixture_has_a_control():
    assert sorted(p.name.removesuffix(".v.tpl") for p in BYPASS.glob("*.v.tpl")) == sorted(LIVE)


@pytest.mark.parametrize("tool,name", VERILOG_GATES + [("dft.scan_sim", "icarus-scan")])
@pytest.mark.parametrize("fixture", sorted(LIVE))
def test_a_form_the_check_and_a_tool_read_differently_is_refused(tmp_path, tool, name, fixture):
    source, marker = bypass_file(tmp_path, fixture)
    outcome = execute(backend(tool, name), {"sources": str(source), "top": "m", "workdir": str(tmp_path / "wd")})
    refused(outcome, marker)
    assert CANARY not in outcome.summary


@pytest.mark.parametrize("tool,name", FORMAL_GATES)
@pytest.mark.parametrize("fixture", sorted(LIVE))
def test_a_form_the_check_and_a_tool_read_differently_is_refused_in_a_formal_setup(tmp_path, tool, name, fixture):
    source, marker = bypass_file(tmp_path, fixture)
    setup = write(source.parent / "f.sby", "[options]\nmode bmc\ndepth 1\n\n[engines]\nsmtbmc\n\n[script]\n"
                                           "read -formal m.v\nprep -top m\n\n[files]\nm.v\n")
    refused(execute(backend(tool, name), {"sby": str(setup), "workdir": str(tmp_path / "wd")}), marker)


@pytest.mark.parametrize("fixture,name", [pytest.param(f, n, marks=needs(*TOOL[n]))
                                          for f, names in sorted(LIVE.items()) for n in names])
def test_control_without_the_check_a_tool_acts_on_the_form(tmp_path, monkeypatch, fixture, name):
    """The fixtures are live: with the check bypassed, the tool reads the canary, or writes the marker."""
    monkeypatch.setattr(eda, "check_inputs", lambda *a: None)
    gate = backend(GATE_OF[name], name)
    if fixture == "glued_macro_call":
        source, marker = bypass_file(tmp_path, fixture)
        execute(gate, {"sources": str(source), "top": "m", "workdir": str(tmp_path / "wd")})
        assert marker.exists()
    elif name == "yosys" and "{canary_hex}" in (BYPASS / f"{fixture}.v.tpl").read_text(encoding="utf-8"):
        cells = []
        for bit in ("1", "0"):  # y = a ^ r[0]: one cell when the canary holds 1, none when it holds 0
            (tmp_path / bit).mkdir()
            source, _ = bypass_file(tmp_path / bit, fixture, bit)
            cells.append(execute(gate, {"sources": str(source), "top": "m"}).metrics.get("cells"))
        assert cells == [1, 0]
    else:
        source, _ = bypass_file(tmp_path, fixture)
        assert "CANARY_ET1" in printed(execute(gate, {"sources": str(source), "top": "m",
                                                      "workdir": str(tmp_path / "wd")}))


@pytest.mark.parametrize("judge", JUDGE)
@pytest.mark.parametrize("tool,name", VERILOG_GATES)
def test_a_seat_file_that_reaches_a_judge_file_is_refused(tmp_path, judge, tool, name):
    """Decision 4, item 3: the reference RTL, the held-out testbench and a mutant, through every gate."""
    for fixture in ("esc_block", "ifdef_quote_include"):
        source, marker = bypass_file(tmp_path, fixture, include=str(ROOT / judge))
        outcome = execute(backend(tool, name), {"sources": str(source), "top": "m"})
        refused(outcome, marker)
        assert Path(judge).name not in outcome.summary


@pytest.mark.parametrize("judge", JUDGE)
@pytest.mark.parametrize("fixture,name", [pytest.param(f, n, marks=needs(*TOOL[n])) for f, n in (
    ("esc_block", "verilator-lint"), ("esc_block", "verilator-sim"), ("esc_block", "yosys"),
    ("ifdef_quote_include", "icarus"))])
def test_control_without_the_check_a_seat_file_reaches_a_judge_file(tmp_path, monkeypatch, judge, fixture, name):
    monkeypatch.setattr(eda, "check_inputs", lambda *a: None)
    source, _ = bypass_file(tmp_path, fixture, include=str(ROOT / judge))
    outcome = execute(backend(GATE_OF[name], name), {"sources": str(source), "top": "m",
                                                     "workdir": str(tmp_path / "wd")})
    assert Path(judge).name in printed(outcome)


@pytest.mark.parametrize("text,why", [
    ('module m;\n  wire \\x ;\nendmodule\n', "a backslash outside a string"),
    ('module m;\n  initial $display("a\\\nb");\nendmodule\n', "a quote that does not close"),
    ("`ifdef A\n`define B 1\n`endif // ok\n`ifdef A `define C 2\n`endif\n", "not alone on its line"),
    ('module m;\n  // `endif\nendmodule\n', "inside a comment or a string"),
    ('module m;\n  initial $display("`else");\nendmodule\n', "inside a comment or a string"),
    ("`define D $\n", "a $ that does not start a name"),
    ("`define W $write\nmodule m; initial x`W; endmodule\n", "a macro glued to the name before it"),
    ("`define S(x) `\"x`\"\n", "a macro quote"),
    ("`define P(x) x\nmodule m; initial `P(1)z; endmodule\n", "a macro call glued to the name after it"),
    ("`define P(x) x\nmodule m; initial `P(1 /* c */); endmodule\n", "a comment inside a macro call's arguments"),
    ("`define C /*\nmodule m; endmodule\n// */\n", "a block comment opened on a directive's line"),
    ("`define C a \\\n  b /*\nmodule m; endmodule\n// */\n", "a block comment opened on a directive's line"),
    ('`line 1 "/etc/hosts" 0\nmodule m; endmodule\n', "`line, a directive a gate does not run"),
    ("`uselib file=/etc/hosts\nmodule m; endmodule\n", "`uselib"),
    ("module m;\x0c endmodule\n", "the control character"),
    ("module m;\x00 endmodule\n", "the control character"),
])
def test_each_rule_of_the_repair_refuses_its_form(tmp_path, text, why):
    path = tmp_path / "t.v"
    path.write_bytes(text.encode("utf-8"))
    problem = verilog_problem([path])
    assert problem and why in problem, problem


def test_ordinary_forms_still_pass(tmp_path):
    text = ("`timescale 1ns/1ps\n`default_nettype none\n`define WIDTH 8\n`define CHECK(c, m) \\\n"
            "  if (!(c)) begin $error(\"%0s\", m); end\n`ifdef FORMAL\n  `define F 1\n`elsif SIM // a note\n`else\n"
            "`endif\nmodule m(input wire [`WIDTH-1:0] a, output wire y); /* a comment\n  across lines, with \" and "
            "/* in it */\n  assign y = ^a; // \"quoted\" \\ `x\n  initial begin\n"
            "    `CHECK(1, \"tab\\t quote\\\" slash\\\\\")\n    $display(\"%0d $readmemh //\", `WIDTH);\n"
            "`ifdef NIRMAAN_NONCE\n    $display(`NIRMAAN_NONCE);\n`endif\n  end\nendmodule\n")
    assert verilog_problem([write(tmp_path / "m.v", text)]) is None
    crlf = tmp_path / "w.v"
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert verilog_problem([crlf]) is None


# --- Must-pass: every committed gate input -------------------------------------------------------------


def committed(*suffixes: str) -> list[Path]:
    return sorted(p for s in suffixes for p in (ROOT / "tests" / "fixtures").rglob(f"*{s}"))


def test_every_committed_design_and_testbench_passes():
    paths = committed(".v", ".sv", ".vh") + sorted((ROOT / "evals").rglob("*.v"))
    assert paths
    assert [p for p in paths if verilog_problem([p])] == []


def test_every_committed_c_file_passes_as_gate_sources():
    """A firmware driver in ``sources`` is checked as Verilog too (docs/GATE_INPUTS.md, section 2)."""
    roots = [ROOT / "tests" / "fixtures", ROOT / "evals", ROOT / "src" / "nirmaan" / "integrations"]
    paths = sorted(p for root in roots for s in ("*.c", "*.h", "*.S", "*.cpp") for p in root.rglob(s))
    assert paths and [p for p in paths if verilog_problem([p])] == []


def test_every_committed_single_task_setup_and_constraints_file_passes():
    setups = [p for p in committed(".sby") if "[tasks]" not in p.read_text()]
    assert setups and [p for p in setups if sby_problem(p)] == []
    constraints = committed(".sdc")
    assert constraints and [p for p in constraints if sdc_problem(p)] == []


def test_every_committed_equivalence_setup_passes():
    setups = committed(".eqy")
    assert setups and [p for p in setups if eqy_problem(p)] == []


def test_the_yosys_allow_list_writes_nothing_and_runs_nothing():
    for command in ("exec", "tcl", "python", "script", "plugin", "tee", "show", "select", "abc", "abc9", "bugpoint",
                    "write_verilog", "dump", "log", "design", "sat", "sim"):
        assert command not in eda_guard.YOSYS_SAFE
        assert yosys_problem([f"{command} x"], "s")


# --- The history scan and the harness -----------------------------------------------------------------


def test_the_history_scan_counts_and_reports_what_the_checks_refuse(tmp_path):
    """scripts/gate_input_history.py, the scan behind docs/GATE_INPUTS.md, section 3, on records made here."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gate_input_history", ROOT / "scripts" / "gate_input_history.py")
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    answer = ('{"files": [{"path": "m.v", "entry": "m"}, {"path": "tb.v", "entry": "tb; exec x"}]}\n'
              f"=== FILE: m.v ===\n{DESIGN}=== END FILE ===\n"
              "=== FILE: tb.v ===\n" + tb('    $system("x");') + "=== END FILE ===\n"
              "=== FILE: f.sby ===\n[options]\nmode bmc\n[script]\n!touch x\n=== END FILE ===\n")
    trial = tmp_path / "evals" / "results" / "run" / "case" / "trial-01.json"
    trial.parent.mkdir(parents=True)
    trial.write_text(json.dumps({"answers": [{"text": answer}]}), encoding="utf-8")
    found = history.scan(tmp_path)
    assert (found["answers"], found["files"], found["verilog"], found["setups"], found["entries"]) == (1, 3, 2, 1, 2)
    assert [line.split(": ")[1] for line in found["refused"]] == ["entry 'tb; exec x'", "tb.v", "f.sby"]


def test_no_file_this_milestone_changes_is_harness_code():
    """docs/GATE_INPUTS.md, section 5: the gate files are not in the harness fingerprint, so it is unchanged."""
    from nirmaan.runtime import harness

    changed = {"nirmaan/integrations/eda_guard.py", "nirmaan/integrations/eda.py",
               "nirmaan/integrations/equivalence.py", "nirmaan/integrations/physical.py"}
    assert not changed & set(harness.CODE) and not changed & set(harness.LOOP_CODE)
