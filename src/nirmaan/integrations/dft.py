"""Design for test through open-source EDA: scan, rule checks, chain simulation, ATPG, and MBIST.

Five tools, each an M21 backend behind the tool broker:

* ``dft.scan_insert`` (Yosys): synthesize, turn every flop into a mux-D scan
  flop with a techmap, and stitch balanced chains (``chains``,
  ``max_chain_length``; never mixing clock domains) from ``scan_in`` to
  ``scan_out`` under ``scan_en``. It writes the scan netlist and a chain report.
* ``dft.check`` (Yosys): testability rules over the synthesized netlist. The
  rules are a registry (:func:`register_rule`): a new rule is a function of
  the netlist, and needs no change here or in the core.
* ``dft.scan_sim`` (Yosys, Icarus): a generated, self-checking testbench
  shifts a known pattern through the chain, then captures once and shifts the
  result out, and Icarus runs it.
* ``dft.atpg`` (Yosys, Icarus, M27): stuck-at patterns from ``dft_atpg.py``
  (random, then PODEM), graded by an Icarus fault simulation through the scan
  protocol. The coverage is what that simulation measured; a pattern set that
  claims a fault the simulation does not detect fails the run.
* ``dft.mbist`` (Yosys, Icarus, M27): a March C- controller from
  ``dft_mbist.py``, run against the memory in Icarus. M29: with no memory as
  top, every memory in the hierarchy, at its declared and measured latency.
* ``dft.atpg_transition`` (Yosys, Icarus, M29): slow-to-rise and slow-to-fall
  pattern pairs (launch on capture), graded by a fault simulation with a
  one-cycle delay at each site in the at-speed cycle.

M29 also lets ``dft.scan_insert`` cross clock domains (``cross_domains=lockup``)
with a lockup latch at each crossing, which the chain rule requires and the
chain simulation proves with skewed clocks.

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
from nirmaan.models import text_value

HELPER = Path(__file__).with_name("dft_scan.py")
ATPG_HELPER = Path(__file__).with_name("dft_atpg.py")
MBIST_HELPER = Path(__file__).with_name("dft_mbist.py")
SCAN_NETLIST = "scan.v"
CHAIN_REPORT = "chain.json"
DESIGN_JSON = "design.json"
TESTBENCH = "scan_tb.v"
TB_TOP = "nirmaan_scan_tb"
PATTERNS = "patterns.json"
FAULTS = "faults.json"
ATPG_CONFIG = "atpg_config.json"
MBIST_CONTROLLER = "nirmaan_mbist.v"

_HELPER_ERROR_RE = re.compile(r"^DFT-ERROR:\s*(?P<msg>.*)$", re.M)
_SCAN_RESULT_RE = re.compile(r"DFT-SCAN: (?:(?P<chains>\d+) chains, (?P<flops>\d+) flops, )?chain length "
                             r"(?P<length>\d+), shift errors (?P<shift>\d+), capture errors (?P<capture>\d+)"
                             r"(?:, skew passes (?P<skew>\d+))?")
_FAULT_RE = re.compile(r"^DFT-FAULT (?P<index>\d+) (?P<pattern>-?\d+)$", re.M)
_ATPG_CHECK_RE = re.compile(r"DFT-ATPG-CHECK: patterns (?P<patterns>\d+), response errors (?P<response>\d+), "
                            r"injection errors (?P<injection>\d+)")
_ATPG_DONE_RE = re.compile(r"DFT-ATPG: (?P<faults>\d+) faults simulated")
_MBIST_GEN_RE = re.compile(r"DFT-MBIST-GEN: March C- for (?P<top>\S+),")
_MBIST_RE = re.compile(r"DFT-MBIST: (?P<top>\S+) march C-, latency (?P<latency>\d+), measured (?P<measured>\d+), "
                       r"words (?P<words>\d+), width (?P<width>\d+), reads (?P<reads>\d+), "
                       r"writes (?P<writes>\d+), cycles (?P<cycles>\d+), x reads (?P<x>\d+), done (?P<done>\d+), "
                       r"fail (?P<fail>\d+), element (?P<element>\d+), address (?P<address>\d+)")


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
    found = [f"latch {name} ({kind}): a latch cannot be scanned" for _, kind, name in design.latches]
    try:  # M29: a lockup latch on a scan crossing is not a design latch, unless capture logic reads it
        leaks = design.lockup_leaks()
    except NetlistError:
        leaks = []
    return found + [f"latch {design.names.get(lk.q, lk.cell)} ({lk.type}) looks like a lockup latch but reaches "
                    f"capture-mode logic: a latch cannot be scanned" for lk in leaks]


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


def _known_cells(design: Design) -> list[str]:
    return [f"cell {cell} of type {kind} is not a gate or flop the checker can evaluate"
            for cell, kind in design.unknown]


def _chain_complete(design: Design) -> list[str]:
    chain = design.trace_chain()
    return chain.problems + chain.hazards


for _rule in (
    DftRule("no-latches", "No latches: every storage element is an edge-triggered flop.", _no_latches),
    DftRule("no-combinational-loops", "No combinational feedback loops.", _no_loops),
    DftRule("scannable-flops", "Every flop has a mux-D scan equivalent.", _scannable),
    DftRule("clock-from-input", "Every flop is clocked directly by a module input (no gated or "
            "generated clocks).", _clock_from_input),
    DftRule("reset-from-input", "Every asynchronous reset or set comes directly from a module input.",
            _reset_from_input),
    DftRule("recognized-cells", "Every cell is a gate or flop the checker can evaluate.", _known_cells),
    DftRule("scan-chain-complete", "With scan_en high, every flop is on a chain from a scan_in bit to the "
            "matching scan_out bit, every clock crossing on a chain has a lockup latch, and no second-edge flop "
            "loads a first-edge one.",
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
            _helper("stitch", DESIGN_JSON, "stitched.json", CHAIN_REPORT, str(job.top),
                    text_value(job.params.get("chains")) or "1", text_value(job.params.get("max_chain_length")) or "0",
                    job.params.get("cross_domains", "").strip() or "none"),
            ["yosys", "-s", "stitch.ys"]]


def _chain_params(job: Job) -> str | None:
    """Why ``chains`` or ``max_chain_length`` cannot be used as given, if so."""
    for name in ("chains", "max_chain_length"):
        value = text_value(job.params.get(name)).strip()
        if value and not (value.isdigit() and int(value) > 0):
            return f"{name} must be a positive integer, not {value!r}"
    cross = job.params.get("cross_domains", "").strip()
    if cross and cross != "lockup":
        return f"cross_domains must be 'lockup' (chains cross clock domains through lockup latches), not {cross!r}"
    return None


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
        lengths = [c["length"] for c in report["chains"]]
        lockups = len(report.get("lockups", []))
        metrics.update(chain_length=report["length"], chains=len(lengths), chain_lengths=lengths, lockups=lockups,
                       flops=report["flops"], clock=report["clock"], clocks=report["clocks"], ports=report["ports"],
                       order=[f["flop"] for f in report["order"]], scan_netlist=str(netlist),
                       chain_report=str(run.workdir / CHAIN_REPORT))
        clocks = "; ".join(f"{c['edge']} {c['port']}" for c in report["clocks"])
        if report.get("cross_domains"):
            clocks += f"; across clock domains, {lockups} lockup latch{'es' if lockups != 1 else ''}"
        if len(lengths) == 1:
            return EdaResult(True, f"scan inserted: {report['length']} flops on one mux-D chain ({clocks}), "
                                   f"netlist {SCAN_NETLIST}", tuple(errors), metrics)
        return EdaResult(True, f"scan inserted: {report['flops']} flops on {len(lengths)} balanced mux-D chains "
                               f"(lengths {', '.join(map(str, lengths))}; {clocks}), netlist {SCAN_NETLIST}",
                         tuple(errors), metrics)
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
    chain = ", no scan ports (chain rule not applicable)"
    if design.has_scan_ports() and verdicts.get("scan-chain-complete") == "pass":
        lengths = [len(c) for c in design.trace_chain().chains]
        metrics.update(chain_length=max(lengths), chains=len(lengths), chain_lengths=lengths)
        chain = (f", chain complete ({len(design.flops)} flops)" if len(lengths) == 1 else
                 f", {len(lengths)} chains complete ({len(design.flops)} flops, longest {max(lengths)})")
    applied = sum(v != "not applicable" for v in verdicts.values())
    if not diags:
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
        metrics.update(shift_errors=int(found["shift"]), capture_errors=int(found["capture"]),
                       chains=int(found["chains"] or 1), chain_length=int(found["length"]),
                       skew_passes=int(found["skew"] or 0))
    clean = found is not None and found["shift"] == "0" and found["capture"] == "0"
    if sim.passed and clean:
        length = int(found["length"])
        skew = "; shift also passed with skewed clocks in both orders" if found["skew"] else ""
        if found["chains"] is None:
            return EdaResult(True, f"scan chain passed: {length} flops, {2 * length} bits shifted through, "
                                   f"one capture checked, 0 mismatches{skew}", sim.diagnostics, metrics)
        return EdaResult(True, f"scan chains passed: {found['chains']} chains, {found['flops']} flops, longest "
                               f"{length}, {2 * length} bits shifted through each, one capture checked, "
                               f"0 mismatches{skew}", sim.diagnostics, metrics)
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


# --- ATPG (M27) ---------------------------------------------------------------------------------


def atpg_helper(*args: str) -> list[str]:
    """A step that runs ``dft_atpg.py``."""
    return [sys.executable, str(ATPG_HELPER), *args]


def atpg_analysis_steps(job: Job) -> list[list[str]]:
    """Yosys synthesizes the scan netlist flat, as ``dft.check`` does, into ``design.json``."""
    return [["yosys", "-s", _analysis_script(job, "atpg_analyze.ys")]]


def atpg_grading_steps(job: Job, patterns: str, fault_model: str = "stuck-at") -> list[list[str]]:
    """Grade ``patterns`` by fault simulation: the fault netlist, Yosys writes it, Icarus runs both machines."""
    work = job.workdir
    limits = {k[4:]: v for k, v in job.params.items() if k.startswith("min_")}
    (work / ATPG_CONFIG).write_text(json.dumps({"min": limits}) + "\n", encoding="utf-8")
    script = ["read_json faulty.json", "hierarchy -check -top nirmaan_faulty", "check -assert",
              "write_verilog -noattr fault_netlist.v"]
    (work / "fault.ys").write_text("\n".join(script) + "\n", encoding="utf-8")
    for stale in (FAULTS, "faulty.json", "fault_netlist.v", "atpg_tb.v", "atpg.vvp"):
        (work / stale).unlink(missing_ok=True)
    return [atpg_helper("inject", DESIGN_JSON, patterns, "faulty.json", FAULTS, "atpg_tb.v", str(job.top),
                        "--sample", text_value(job.params.get("fault_sample")) or "0",
                        "--seed", text_value(job.params.get("seed")) or "1",
                        "--model", fault_model),
            ["yosys", "-s", "fault.ys"],
            ["iverilog", "-g2012", "-o", "atpg.vvp", "-s", "nirmaan_atpg_tb", *job.sources, "fault_netlist.v",
             "atpg_tb.v"],
            ["vvp", "-n", "atpg.vvp"]]


def _atpg_steps(job: Job, fault_model: str = "stuck-at") -> list[list[str]]:
    given = job.params.get("patterns", "").strip()
    steps = atpg_analysis_steps(job)
    if given:
        return steps + atpg_grading_steps(job, str(Path(given).resolve()), fault_model)
    (job.workdir / PATTERNS).unlink(missing_ok=True)
    steps.append(atpg_helper("generate", DESIGN_JSON, PATTERNS, str(job.top),
                             "--seed", text_value(job.params.get("seed")) or "1", "--model", fault_model))
    return steps + atpg_grading_steps(job, PATTERNS, fault_model)


def _transition_steps(job: Job) -> list[list[str]]:
    return _atpg_steps(job, "transition")


def _atpg_params(job: Job) -> str | None:
    """Why the ATPG parameters cannot be used as given, if so."""
    for name in ("fault_sample", "seed"):
        value = text_value(job.params.get(name)).strip()
        if value and not value.isdigit():
            return f"{name} must be a non-negative integer, not {value!r}"
    for name, value in job.params.items():
        if name.startswith("min_"):
            try:
                float(value)
            except (TypeError, ValueError):
                return f"{name} {value!r} is not a number"
    return None


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def parse_atpg(run: RunRecord) -> EdaResult:
    """Coverage from the fault simulation's own detections; claims and expected responses are checked."""
    metrics: dict = {"exit_statuses": list(run.returncodes)}
    helper = _HELPER_ERROR_RE.search(run.log)
    doc = _json(run.workdir / FAULTS)
    if helper or doc is None:
        errors = _yosys_errors(run)
        reason = helper["msg"].strip() if helper else (errors[0].message if errors else
                                                       _step_failed(run, 6) or "no fault list was written")
        return EdaResult(False, f"ATPG failed before fault simulation: {reason}",
                         tuple(errors or [Diagnostic("error", reason)]), metrics)
    check, done = _ATPG_CHECK_RE.search(run.log), _ATPG_DONE_RE.search(run.log)
    if check is None or done is None or any(rc != 0 for rc in run.returncodes):
        errors = _yosys_errors(run)
        reason = errors[0].message if errors else (_step_failed(run, len(run.returncodes)) or "no result line")
        return EdaResult(False, f"fault simulation did not complete: {reason}",
                         tuple(errors or [Diagnostic("error", reason)]), metrics)
    faults = doc["faults"]
    detected_at = {int(m["index"]): int(m["pattern"]) for m in _FAULT_RE.finditer(run.log)}
    if sorted(detected_at) != list(range(len(faults))):
        reason = f"the fault simulation reported {len(detected_at)} of {len(faults)} faults"
        return EdaResult(False, f"fault simulation did not complete: {reason}", (Diagnostic("error", reason),),
                         metrics)
    untestable, claims = set(doc["untestable"]), doc["claims"]
    listing = []
    for i, fault in enumerate(faults):
        at = detected_at[i]
        kind = "detected" if at >= 0 else ("undetectable" if fault["name"] in untestable else "undetected")
        listing.append({"name": fault["name"], "class": kind, "pattern": at if at >= 0 else None,
                        "claimed": claims.get(fault["name"])})
    by_name = {f["name"]: f for f in listing}
    total = len(listing)
    detected = sum(f["class"] == "detected" for f in listing)
    undetectable = sum(f["class"] == "undetectable" for f in listing)
    missed = [n for n in claims if by_name[n]["class"] != "detected"]
    testable = total - undetectable
    metrics.update(
        faults_total=total, faults_detected=detected, faults_undetectable=undetectable,
        faults_undetected=total - detected - undetectable,
        fault_coverage=round(100.0 * detected / total, 2) if total else 100.0,
        test_coverage=round(100.0 * detected / testable, 2) if testable else 100.0,
        patterns=int(check["patterns"]), chains=doc["chains"], claimed=len(claims), claims_not_detected=len(missed),
        response_errors=int(check["response"]), injection_errors=int(check["injection"]),
        fault_model=doc.get("fault_model", "stuck-at"),
        faults_in_universe=doc["universe"], sampled=doc["sampled"], aborted=len(doc["aborted"]),
        patterns_file=str(run.workdir / PATTERNS) if (run.workdir / PATTERNS).is_file() else None,
        fault_list=listing)
    diags: list[Diagnostic] = []
    if metrics["injection_errors"]:
        diags.append(Diagnostic("error", f"with no fault enabled, the fault netlist differed from the design "
                                         f"{metrics['injection_errors']} times", "ATPG-INJECTION"))
    if metrics["response_errors"]:
        diags.append(Diagnostic("error", f"{metrics['response_errors']} expected responses in the pattern set "
                                         f"differ from the good machine's", "ATPG-RESPONSE"))
    if missed:
        diags.append(Diagnostic("error", f"the pattern set claims {_plural(len(missed), 'fault')} the fault "
                                         f"simulation did not detect: {', '.join(missed[:5])}", "ATPG-CLAIM"))
    if diags:
        return EdaResult(False, "ATPG refused: " + "; ".join(d.message for d in diags), tuple(diags), metrics)
    sample = (f"; a seeded sample of {total} of {doc['universe']} faults" if doc["sampled"] else "")
    transition = metrics["fault_model"] == "transition"
    summary = (f"ATPG: {detected} of {total} {'transition ' if transition else ''}faults detected in fault simulation "
               f"({metrics['fault_coverage']:.2f}% fault coverage, {metrics['test_coverage']:.2f}% test coverage; "
               f"{undetectable} proven undetectable, {metrics['faults_undetected']} undetected), "
               f"{_plural(metrics['patterns'], 'pattern pair' if transition else 'pattern')}"
               f"{', launch on capture,' if transition else ''} over {_plural(doc['chains'], 'chain')}{sample}")
    limits = (_json(run.workdir / ATPG_CONFIG) or {}).get("min", {})
    short = []
    for metric, bound in sorted(limits.items()):
        measured = metrics.get(metric)
        if isinstance(measured, bool) or not isinstance(measured, (int, float)):
            short.append(f"{metric} was not reported, so min_{metric} cannot be checked")
        elif measured < float(bound):
            short.append(f"{metric} {measured} is below min_{metric} {text_value(bound)}")
    if short:
        return EdaResult(False, f"limit not met: {'; '.join(short)} (the tool reported: {summary})",
                         tuple(Diagnostic("error", m, "LIMIT") for m in short), metrics)
    return EdaResult(True, summary, (), metrics)


# --- MBIST (M27) ---------------------------------------------------------------------------------


def _mbist_steps(job: Job) -> list[list[str]]:
    work = job.workdir
    # M29: with no top, the design's own top is found, and its memories with it.
    hierarchy = f"hierarchy -check -top {job.top}" if job.top else "hierarchy -check -auto-top"
    read = [*(f'read_verilog -sv "{src}"' for src in job.sources), hierarchy]
    (work / "mbist_ports.ys").write_text("\n".join([*read, "proc", "write_json mbist_ports.json"]) + "\n",
                                         encoding="utf-8")
    for stale in ("mbist_ports.json", MBIST_CONTROLLER, "mbist_tb.v", "mbist.vvp"):
        (work / stale).unlink(missing_ok=True)
    return [["yosys", "-s", "mbist_ports.ys"],
            [sys.executable, str(MBIST_HELPER), "generate", "mbist_ports.json", MBIST_CONTROLLER, "mbist_tb.v",
             str(job.top or "")],
            ["iverilog", "-g2012", "-o", "mbist.vvp", "-s", "nirmaan_mbist_tb", *job.sources, MBIST_CONTROLLER,
             "mbist_tb.v"],
            ["vvp", "-n", "mbist.vvp"]]


def _one_memory(found: re.Match) -> tuple[dict, list[str], str | None]:
    """One memory's result line: its metrics, what is wrong with the run, and its failure (if March C- failed)."""
    from nirmaan.integrations.dft_mbist import MARCH_C_MINUS

    top, words, width = found["top"], int(found["words"]), int(found["width"])
    latency, measured = int(found["latency"]), int(found["measured"])
    reads, writes, cycles = int(found["reads"]), int(found["writes"]), int(found["cycles"])
    metrics = {"module": top, "depth": words, "width": width, "read_latency": latency, "measured_latency": measured,
               "reads": reads, "writes": writes, "operations": reads + writes, "cycles": cycles,
               "x_reads": int(found["x"]), "done": found["done"] == "1", "fail": found["fail"] == "1"}
    failure = None
    if metrics["fail"]:
        element = int(found["element"])
        direction, ops = MARCH_C_MINUS[element] if element < len(MARCH_C_MINUS) else ("?", "?")
        metrics.update(fail_element=element, fail_address=int(found["address"]))
        failure = (f"March C- failed on {top}: first mismatch in element {element} ({direction} {ops}) at "
                   f"address {found['address']}")
    problems = []
    if measured != latency:
        seen = f"measured {measured}" if measured else f"measured no word within {8} cycles"
        problems.append(f"{top} declares a read latency of {latency}, but the testbench {seen}")
    if not metrics["done"]:
        problems.append(f"the controller for {top} never finished")
    if reads != 5 * words or writes != 5 * words:
        problems.append(f"{top}: {reads} reads and {writes} writes, not {5 * words} of each")
    if cycles != (10 + 5 * latency) * words:
        problems.append(f"{top}: {cycles} cycles, not {(10 + 5 * latency) * words}")
    if metrics["x_reads"]:
        problems.append(f"{top}: {metrics['x_reads']} reads returned unknown bits")
    return metrics, problems, failure


def parse_mbist(run: RunRecord) -> EdaResult:
    """Pass means every memory's controller ran March C- to the end, at its measured latency, with no mismatch."""
    metrics: dict = {"exit_statuses": list(run.returncodes)}
    helper = _HELPER_ERROR_RE.search(run.log)
    lines = list(_MBIST_RE.finditer(run.log))
    if helper or not lines:
        errors = _yosys_errors(run)
        sim_log = "".join(f"$ {c}\n{t}" for c, t in _sections(run.log) if c.startswith(("iverilog", "vvp")))
        errors += list(parse_simulation(sim_log, run.returncodes[2:]).diagnostics) if len(run.returncodes) > 2 else []
        reason = helper["msg"].strip() if helper else (errors[0].message if errors else
                                                       _step_failed(run, 4) or "no MBIST result")
        return EdaResult(False, f"MBIST did not run: {reason}", tuple(errors or [Diagnostic("error", reason)]),
                         metrics)
    memories, problems, failures = [], [], []
    for found in lines:
        one, wrong, failure = _one_memory(found)
        memories.append(one)
        problems += wrong
        failures += [failure] if failure else []
    metrics.update(memories=memories, controller=str(run.workdir / MBIST_CONTROLLER),
                   testbench=str(run.workdir / "mbist_tb.v"))
    if len(memories) == 1:
        metrics.update({k: v for k, v in memories[0].items() if k != "module"})
    else:
        metrics.update(operations=sum(m["operations"] for m in memories), fail=bool(failures))
    if failures:
        message = "; ".join(failures)
        return EdaResult(False, message, tuple(Diagnostic("error", f, "MBIST-FAIL") for f in failures), metrics)
    if problems:
        message = f"March C- did not run to completion: {'; '.join(problems)}"
        return EdaResult(False, message, (Diagnostic("error", message, "MBIST-INCOMPLETE"),), metrics)
    parts = [f"{m['depth']} words of {m['width']} bits, {m['operations']} operations, {m['cycles']} cycles"
             + (f", read latency {m['read_latency']}" if m["read_latency"] != 1 else "") for m in memories]
    if len(memories) == 1:
        return EdaResult(True, f"March C- passed on {memories[0]['module']}: {parts[0]}", (), metrics)
    return EdaResult(True, f"March C- passed on {len(memories)} memories: "
                           + "; ".join(f"{m['module']} ({p})" for m, p in zip(memories, parts)), (), metrics)


register_backend(Backend("yosys-scan", "dft.scan_insert", ("yosys",), _insert_steps, parse_scan_insert,
                         ("sources", "top"), check=_chain_params))
register_backend(Backend("yosys-dft", "dft.check", ("yosys",), _check_steps, parse_dft_check, ("sources", "top")))
register_backend(Backend("icarus-scan", "dft.scan_sim", ("yosys", "iverilog", "vvp"), _sim_steps, parse_scan_sim,
                         ("sources", "top")))
register_backend(Backend("icarus-atpg", "dft.atpg", ("yosys", "iverilog", "vvp"), _atpg_steps, parse_atpg,
                         ("sources", "top"), files=("patterns",), check=_atpg_params))
register_backend(Backend("icarus-atpg-transition", "dft.atpg_transition", ("yosys", "iverilog", "vvp"),
                         _transition_steps, parse_atpg, ("sources", "top"), files=("patterns",), check=_atpg_params))
register_backend(Backend("icarus-mbist", "dft.mbist", ("yosys", "iverilog", "vvp"), _mbist_steps, parse_mbist,
                         ("sources",)))

__all__ = ["SCAN_PORTS", "DftRule", "atpg_analysis_steps", "atpg_grading_steps", "atpg_helper", "check_design",
           "parse_atpg", "parse_mbist", "register_rule", "rules", "unregister_rule"]
