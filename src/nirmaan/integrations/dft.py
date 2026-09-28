"""Design for test through open-source EDA: scan insertion, rule checks, chain simulation.

Three tools, each an M21 backend behind the tool broker:

* ``dft.scan_insert`` (Yosys): synthesize, turn every flop into a mux-D scan
  flop with a techmap, and stitch one chain from ``scan_in`` to ``scan_out``
  under ``scan_en``. It writes the scan netlist and a chain report.
* ``dft.check`` (Yosys): testability rules over the synthesized netlist. The
  rules are a registry (:func:`register_rule`): a new rule is a function of
  the netlist, and needs no change here or in the core.
* ``dft.scan_sim`` (Yosys, Icarus): a generated, self-checking testbench
  shifts a known pattern through the chain, then captures once and shifts the
  result out, and Icarus runs it.

A tool that cannot run here is refused with a reason (the M21 probe); a design
that fails is a recorded run with ``succeeded=False``. The steps between tool
invocations (stitching the chain, writing the testbench) run
``dft_scan.py``, which reads only what Yosys wrote. Nothing is simulated in
the sense of pretended.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nirmaan.integrations.dft_scan import SCAN_PORTS, Design, NetlistError, techmap_file
from nirmaan.integrations.eda import Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import Diagnostic, EdaResult, parse_simulation, parse_yosys

HELPER = Path(__file__).with_name("dft_scan.py")
SCAN_NETLIST = "scan.v"
CHAIN_REPORT = "chain.json"
DESIGN_JSON = "design.json"
TESTBENCH = "scan_tb.v"
TB_TOP = "nirmaan_scan_tb"

_HELPER_ERROR_RE = re.compile(r"^DFT-ERROR:\s*(?P<msg>.*)$", re.M)
_SCAN_RESULT_RE = re.compile(r"DFT-SCAN: chain length (?P<length>\d+), shift errors (?P<shift>\d+), "
                             r"capture errors (?P<capture>\d+)")


# --- Testability rules: a registry ----------------------------------------------------------


@dataclass(frozen=True)
class DftRule:
    """One testability rule: a function of the synthesized netlist returning its violations."""

    id: str
    description: str
    check: Callable[[Design], list[str]]
    #: When set, the rule applies only to designs for which this returns True.
    applies: Callable[[Design], bool] | None = None


_RULES: dict[str, DftRule] = {}


def register_rule(rule: DftRule) -> DftRule:
    if rule.id in _RULES:
        raise ValueError(f"DFT rule {rule.id!r} is already registered")
    _RULES[rule.id] = rule
    return rule


def unregister_rule(rule_id: str) -> None:
    _RULES.pop(rule_id, None)


def rules() -> list[DftRule]:
    return list(_RULES.values())


def check_design(design: Design) -> tuple[list[Diagnostic], dict[str, str]]:
    """Every registered rule over ``design``: the violations, and each rule's verdict."""
    diagnostics: list[Diagnostic] = []
    verdicts: dict[str, str] = {}
    for rule in rules():
        if rule.applies and not rule.applies(design):
            verdicts[rule.id] = "not applicable"
            continue
        try:
            found = rule.check(design)
        except NetlistError as exc:
            found = [str(exc)]
        verdicts[rule.id] = "fail" if found else "pass"
        diagnostics += [Diagnostic("error", msg, rule.id) for msg in found]
    return diagnostics, verdicts


def _no_latches(design: Design) -> list[str]:
    return [f"latch {name} ({kind}): a latch cannot be scanned" for _, kind, name in design.latches]


def _no_loops(design: Design) -> list[str]:
    return [f"combinational loop through {', '.join(group)}" for group in design.combinational_loops()]


def _scannable(design: Design) -> list[str]:
    return [f"flop {name} ({kind}) has no mux-D scan equivalent" for _, kind, name in design.others]


def _clock_from_input(design: Design) -> list[str]:
    inputs = design.input_bits()
    return [f"flop {f.name} is clocked by {design.describe(f.clock)}, not a module input: the tester "
            f"cannot control it" for f in design.flops if f.clock not in inputs]


def _reset_from_input(design: Design) -> list[str]:
    inputs = design.input_bits()
    return [f"flop {f.name} has its asynchronous reset from {design.describe(f.reset)}, not a module input"
            for f in design.flops if f.reset is not None and f.reset not in inputs]


def _one_clock(design: Design) -> list[str]:
    domains = sorted({f"{f.edge} {design.describe(f.clock)}" for f in design.flops})
    if len(domains) <= 1:
        return []
    return [f"{len(domains)} clock domains or edges ({'; '.join(domains)}): one chain covers one"]


def _known_cells(design: Design) -> list[str]:
    return [f"cell {cell} of type {kind} is not a gate or flop the checker can evaluate"
            for cell, kind in design.unknown]


def _chain_complete(design: Design) -> list[str]:
    return design.trace_chain().problems


for _rule in (
    DftRule("no-latches", "No latches: every storage element is an edge-triggered flop.", _no_latches),
    DftRule("no-combinational-loops", "No combinational feedback loops.", _no_loops),
    DftRule("scannable-flops", "Every flop has a mux-D scan equivalent.", _scannable),
    DftRule("clock-from-input", "Every flop is clocked directly by a module input (no gated or "
            "generated clocks).", _clock_from_input),
    DftRule("reset-from-input", "Every asynchronous reset or set comes directly from a module input.",
            _reset_from_input),
    DftRule("one-clock-domain", "All flops share one clock and edge, so one chain covers them.", _one_clock),
    DftRule("recognized-cells", "Every cell is a gate or flop the checker can evaluate.", _known_cells),
    DftRule("scan-chain-complete", "With scan_en high, every flop is on one chain from scan_in to scan_out.",
            _chain_complete, applies=Design.has_scan_ports),
):
    register_rule(_rule)


# --- Steps -----------------------------------------------------------------------------------


def _read(job: Job) -> list[str]:
    return [*(f'read_verilog -sv "{src}"' for src in job.sources), f"hierarchy -check -top {job.top}"]


def _analysis_script(job: Job, name: str) -> str:
    """Synthesize to Yosys gates, flattened, with enables and sync resets unmapped into logic."""
    script = [*_read(job), f"synth -flatten -top {job.top}", "dffunmap", "opt_clean", f"write_json {DESIGN_JSON}"]
    (job.workdir / name).write_text("\n".join(script) + "\n", encoding="utf-8")
    (job.workdir / DESIGN_JSON).unlink(missing_ok=True)
    return name


def _helper(*args: str) -> list[str]:
    return [sys.executable, str(HELPER), *args]


def _insert_steps(job: Job) -> list[list[str]]:
    work = job.workdir
    _analysis_script(job, "prep.ys")
    (work / "scan_map.v").write_text(techmap_file(), encoding="utf-8")
    stitch = ["read_json stitched.json", "techmap -map scan_map.v", "opt_clean",
              f"hierarchy -check -top {job.top}", "check -assert", f"write_verilog -noattr {SCAN_NETLIST}",
              "tee -q -o scan_stat.json stat -json"]
    (work / "stitch.ys").write_text("\n".join(stitch) + "\n", encoding="utf-8")
    for stale in (SCAN_NETLIST, CHAIN_REPORT, "stitched.json", "scan_stat.json"):
        (work / stale).unlink(missing_ok=True)
    return [["yosys", "-s", "prep.ys"],
            _helper("stitch", DESIGN_JSON, "stitched.json", CHAIN_REPORT, str(job.top)),
            ["yosys", "-s", "stitch.ys"]]


def _check_steps(job: Job) -> list[list[str]]:
    return [["yosys", "-s", _analysis_script(job, "dft_check.ys")]]


def _sim_steps(job: Job) -> list[list[str]]:
    for stale in (TESTBENCH, "scan_expect.json", "scan_sim.vvp"):
        (job.workdir / stale).unlink(missing_ok=True)
    return [["yosys", "-s", _analysis_script(job, "dft_analyze.ys")],
            _helper("testbench", DESIGN_JSON, TESTBENCH, "scan_expect.json", str(job.top)),
            ["iverilog", "-g2012", "-o", "scan_sim.vvp", "-s", TB_TOP, *job.sources, TESTBENCH],
            ["vvp", "-n", "scan_sim.vvp"]]


# --- Parsing -----------------------------------------------------------------------------------


def _sections(log: str) -> list[tuple[str, str]]:
    """The log split per step: (the command echoed by the runner, what it printed)."""
    parts = re.split(r"^\$ (.*)\n", log, flags=re.M)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def _step_failed(run: RunRecord, steps: int) -> str | None:
    """Why the run did not get through all its steps, if it did not."""
    helper = _HELPER_ERROR_RE.search(run.log)
    if helper:
        return helper["msg"].strip()
    if len(run.returncodes) < steps or any(rc != 0 for rc in run.returncodes):
        return f"step {len(run.returncodes)} of {steps} exited with status {run.returncode}"
    return None


def _yosys_errors(run: RunRecord) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    for command, text in _sections(run.log):
        if command.startswith("yosys"):
            diags += parse_yosys(text, 0).errors
    return diags


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_scan_insert(run: RunRecord) -> EdaResult:
    """Pass means all three steps ran and a scan netlist and chain report were written."""
    failed = _step_failed(run, 3)
    errors = _yosys_errors(run)
    report = _json(run.workdir / CHAIN_REPORT)
    netlist = run.workdir / SCAN_NETLIST
    metrics: dict = {"exit_statuses": list(run.returncodes)}
    if failed is None and report is not None and netlist.is_file():
        metrics.update(chain_length=report["length"], chains=1, clock=report["clock"], ports=report["ports"],
                       order=[f["flop"] for f in report["order"]], scan_netlist=str(netlist),
                       chain_report=str(run.workdir / CHAIN_REPORT))
        clock = report["clock"]
        return EdaResult(True, f"scan inserted: {report['length']} flops on one mux-D chain "
                               f"({clock['edge']} {clock['port']}), netlist {SCAN_NETLIST}", tuple(errors), metrics)
    reason = failed or "no scan netlist was written"
    if errors and not _HELPER_ERROR_RE.search(run.log):
        reason = errors[0].message
    diags = errors or [Diagnostic("error", reason)]
    return EdaResult(False, f"scan insertion failed: {reason}", tuple(diags), metrics)


def parse_dft_check(run: RunRecord) -> EdaResult:
    """Pass means Yosys synthesized the design and every applicable rule holds on its netlist."""
    failed = _step_failed(run, 1)
    netlist = run.workdir / DESIGN_JSON
    if failed or not netlist.is_file():
        errors = _yosys_errors(run)
        reason = errors[0].message if errors else (failed or "Yosys wrote no netlist")
        return EdaResult(False, f"dft check did not run: {reason}", tuple(errors or [Diagnostic("error", reason)]),
                         {"exit_statuses": list(run.returncodes)})
    top = _top_of(run)
    try:
        design = Design.load(netlist, top)
    except NetlistError as exc:
        return EdaResult(False, f"dft check did not run: {exc}", (Diagnostic("error", str(exc)),))
    diags, verdicts = check_design(design)
    metrics = {
        "flip_flops": len(design.flops), "latches": len(design.latches), "rules": verdicts,
        "scan_ports": design.has_scan_ports(), "exit_statuses": list(run.returncodes),
    }
    if design.has_scan_ports() and verdicts.get("scan-chain-complete") == "pass":
        metrics["chain_length"] = len(design.flops)
    applied = sum(v != "not applicable" for v in verdicts.values())
    if not diags:
        chain = (f", chain complete ({len(design.flops)} flops)" if metrics.get("chain_length") is not None
                 else ", no scan ports (chain rule not applicable)")
        return EdaResult(True, f"dft check passed: {applied} rules, {len(design.flops)} flip-flops{chain}",
                         (), metrics)
    broken = sorted({d.code for d in diags})
    first = diags[0]
    return EdaResult(False, f"dft check failed: {len(diags)} violation{'s' if len(diags) != 1 else ''} of "
                            f"{', '.join(broken)}; first: [{first.code}] {first.message}", tuple(diags), metrics)


def parse_scan_sim(run: RunRecord) -> EdaResult:
    """Pass means the testbench was generated, compiled, and ran to $finish with no mismatch."""
    helper = _HELPER_ERROR_RE.search(run.log)
    expect = _json(run.workdir / "scan_expect.json") or {}
    metrics: dict = {"exit_statuses": list(run.returncodes), "chain_length": expect.get("length")}
    if helper or len(run.returncodes) < 2:
        reason = helper["msg"].strip() if helper else (_step_failed(run, 4) or "no testbench")
        errors = _yosys_errors(run)
        if errors and not helper:
            reason = errors[0].message
        return EdaResult(False, f"scan simulation failed before simulating: {reason}",
                         tuple(errors or [Diagnostic("error", reason)]), metrics)
    sim_log = "".join(f"$ {c}\n{t}" for c, t in _sections(run.log) if c.startswith(("iverilog", "vvp")))
    sim = parse_simulation(sim_log, run.returncodes[2:])
    found = _SCAN_RESULT_RE.search(run.log)
    metrics.update(sim.metrics, testbench=str(run.workdir / TESTBENCH))
    if found:
        metrics.update(shift_errors=int(found["shift"]), capture_errors=int(found["capture"]))
    clean = found is not None and found["shift"] == "0" and found["capture"] == "0"
    if sim.passed and clean:
        length = int(found["length"])
        return EdaResult(True, f"scan chain passed: {length} flops, {2 * length} bits shifted through, "
                               f"one capture checked, 0 mismatches", sim.diagnostics, metrics)
    detail = (f"{found['shift']} shift and {found['capture']} capture mismatches" if found
              else sim.summary)
    return EdaResult(False, f"scan chain failed: {detail}", sim.diagnostics, metrics)


def _top_of(run: RunRecord) -> str | None:
    """The top module the run elaborated, from the script it ran."""
    try:
        script = (run.workdir / "dft_check.ys").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^hierarchy -check -top (\S+)$", script, re.M)
    return m[1] if m else None


register_backend(Backend("yosys-scan", "dft.scan_insert", ("yosys",), _insert_steps, parse_scan_insert,
                         ("sources", "top")))
register_backend(Backend("yosys-dft", "dft.check", ("yosys",), _check_steps, parse_dft_check, ("sources", "top")))
register_backend(Backend("icarus-scan", "dft.scan_sim", ("yosys", "iverilog", "vvp"), _sim_steps, parse_scan_sim,
                         ("sources", "top")))

__all__ = ["SCAN_PORTS", "DftRule", "check_design", "register_rule", "rules", "unregister_rule"]
