"""Parsers for open-source EDA output: pure functions of captured text.

Each parser turns what a tool printed (and the exit codes it returned) into an
:class:`EdaResult`: pass or fail, diagnostics, and metrics. They never run a
tool, so they are tested against captured outputs with no tool installed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    severity: str  # "error" or "warning"
    message: str
    code: str = ""
    file: str = ""
    line: int | None = None
    column: int | None = None

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}" if self.file and self.line else self.file


@dataclass(frozen=True)
class EdaResult:
    passed: bool
    summary: str
    diagnostics: tuple[Diagnostic, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "summary": self.summary, "metrics": self.metrics,
                "diagnostics": [asdict(d) for d in self.diagnostics]}


def _int(value: str | None) -> int | None:
    return int(value) if value else None


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _first(diags: list[Diagnostic]) -> str:
    if not diags:
        return ""
    d = diags[0]
    where = f"{d.where}: " if d.where else ""
    code = f"[{d.code}] " if d.code else ""
    return f"; first: {where}{code}{d.message}"


# --- Verilator -------------------------------------------------------------------------

# %Warning-WIDTHTRUNC: bad.v:7:29: message   /   %Error: bad2.v:3:1: syntax error
# Simulation prefixes the time: [100000] %Error: tb.v:23: Assertion failed in ...
_VERILATOR_RE = re.compile(
    r"^(?:\[\S+\]\s*)?%(?P<sev>Error|Warning)(?:-(?P<code>[A-Z0-9_]+))?:\s*"
    r"(?:(?P<file>[^\s:]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s*)?(?P<msg>.*)$"
)
_VERILATOR_NOISE = ("Exiting due to", "Cannot continue")


def _verilator_diagnostics(log: str) -> list[Diagnostic]:
    found = []
    for line in log.splitlines():
        m = _VERILATOR_RE.match(line.strip())
        if not m or m["msg"].startswith(_VERILATOR_NOISE):
            continue
        found.append(Diagnostic("error" if m["sev"] == "Error" else "warning", m["msg"].strip(),
                                m["code"] or "", m["file"] or "", _int(m["line"]), _int(m["col"])))
    return found


def parse_verilator_lint(log: str, returncode: int) -> EdaResult:
    """Lint-clean means exit 0 with no errors and no warnings (waivers live in the RTL)."""
    diags = _verilator_diagnostics(log)
    errors = [d for d in diags if d.severity == "error"]
    warnings = [d for d in diags if d.severity == "warning"]
    passed = returncode == 0 and not errors and not warnings
    if passed:
        summary = "lint clean: 0 errors, 0 warnings"
    else:
        summary = (f"lint failed: {_plural(len(errors), 'error')}, {_plural(len(warnings), 'warning')}"
                   f"{_first(errors or warnings)}")
        if not diags:
            summary += f" (exit status {returncode})"
    return EdaResult(passed, summary, tuple(diags),
                     {"errors": len(errors), "warnings": len(warnings), "exit_status": returncode})


# --- Simulation (Icarus Verilog, Verilator) --------------------------------------------

# Icarus: "ERROR: tb.v:23: message" for $error, FATAL for $fatal, WARNING for $warning.
_SIM_MSG_RE = re.compile(
    r"^(?P<sev>ERROR|FATAL|WARNING|Error|Fatal|Warning):\s*"
    r"(?:(?P<file>[^\s:]+):(?P<line>\d+):\s*)?(?P<msg>.*)$"
)
# Icarus compile: "bad2.v:3: syntax error", "tb.v:5: error: ...", "tb.v:5: warning: ..."
_ICARUS_COMPILE_RE = re.compile(
    r"^(?P<file>[^\s:]+):(?P<line>\d+):\s*(?:(?P<sev>error|warning):\s*)?(?P<msg>.*)$"
)
_ICARUS_BARE_ERROR_RE = re.compile(r"^error:\s*(?P<msg>.*)$")
_ICARUS_FINISH_RE = re.compile(r"\$finish called at (?P<time>\d+)")
_VERILATOR_FINISH_RE = re.compile(r"(?:Verilog \$finish|\$finish at (?P<time>[^\s;]+))")


def parse_simulation(log: str, returncodes: tuple[int, ...]) -> EdaResult:
    """Pass means every step exited 0, no error or fatal message, and $finish was reached."""
    diags: list[Diagnostic] = []
    finished = False
    end_time: str | None = None
    for raw in log.splitlines():
        line = raw.strip()
        if not line or line.startswith("$ "):  # the runner's own command echo
            continue
        if m := _ICARUS_FINISH_RE.search(line):
            finished, end_time = True, m["time"]
            continue
        if m := _VERILATOR_FINISH_RE.search(line):
            finished = True
            end_time = m["time"] or end_time
            continue
        if line.startswith("%") or (line.startswith("[") and "%" in line):
            m = _VERILATOR_RE.match(line)
            if m and not m["msg"].startswith(_VERILATOR_NOISE):
                sev = "error" if m["sev"] == "Error" else "warning"
                diags.append(Diagnostic(sev, m["msg"].strip(), m["code"] or "", m["file"] or "", _int(m["line"])))
            continue
        if m := _SIM_MSG_RE.match(line):
            sev = "warning" if m["sev"].lower() == "warning" else "error"
            code = "FATAL" if m["sev"].lower() == "fatal" else ""
            diags.append(Diagnostic(sev, m["msg"].strip(), code, m["file"] or "", _int(m["line"])))
            continue
        if m := _ICARUS_BARE_ERROR_RE.match(line):
            diags.append(Diagnostic("error", m["msg"].strip()))
            continue
        m = _ICARUS_COMPILE_RE.match(line)
        if m and (m["sev"] or "error" in m["msg"].lower()):
            sev = m["sev"] or "error"
            diags.append(Diagnostic(sev, m["msg"].strip(), "", m["file"], _int(m["line"])))
    errors = [d for d in diags if d.severity == "error"]
    exit_ok = bool(returncodes) and all(rc == 0 for rc in returncodes)
    passed = exit_ok and not errors and finished
    if passed:
        at = f" at time {end_time}" if end_time else ""
        summary = f"simulation passed: $finish reached{at}, 0 errors"
    else:
        reasons = []
        if errors:
            reasons.append(_plural(len(errors), "error"))
        if not exit_ok:
            reasons.append(f"exit status {returncodes[-1] if returncodes else 'none'}")
        if not finished:
            reasons.append("$finish never reached")
        summary = f"simulation failed: {', '.join(reasons)}{_first(errors)}"
    return EdaResult(passed, summary, tuple(diags), {
        "errors": len(errors), "warnings": len(diags) - len(errors),
        "finished": finished, "end_time": end_time, "exit_statuses": list(returncodes),
    })


# --- Yosys -----------------------------------------------------------------------------

_YOSYS_ERROR_RE = re.compile(r"^ERROR:\s*(?P<msg>.*)$")
_YOSYS_WARNING_RE = re.compile(r"^Warning:\s*(?P<msg>.*)$")


def parse_yosys(log: str, returncode: int, stat_json: str | None = None) -> EdaResult:
    """Pass means exit 0 and no ERROR; the cell statistics come from ``stat -json``."""
    diags = []
    for raw in log.splitlines():
        if m := _YOSYS_ERROR_RE.match(raw.strip()):
            diags.append(Diagnostic("error", m["msg"].strip()))
        elif m := _YOSYS_WARNING_RE.match(raw.strip()):
            diags.append(Diagnostic("warning", m["msg"].strip()))
    metrics: dict[str, Any] = {"exit_status": returncode}
    if stat_json:
        try:
            design = json.loads(stat_json).get("design", {})
        except json.JSONDecodeError:
            design = {}
        by_type = design.get("num_cells_by_type", {})
        metrics.update(
            cells=design.get("num_cells"),
            wires=design.get("num_wires"),
            cells_by_type=by_type,
            flip_flops=sum(n for t, n in by_type.items() if "FF" in t.upper()),
            latches=sum(n for t, n in by_type.items() if "LATCH" in t.upper()),
        )
    errors = [d for d in diags if d.severity == "error"]
    warnings = [d for d in diags if d.severity == "warning"]
    passed = returncode == 0 and not errors
    if passed:
        cells = metrics.get("cells")
        stats = (f"{cells} cells, {metrics['flip_flops']} flip-flops, {metrics['latches']} latches"
                 if cells is not None else "no statistics")
        summary = f"synthesis passed: {stats}, {_plural(len(warnings), 'warning')}"
    else:
        summary = f"synthesis failed: {_plural(len(errors), 'error')}{_first(errors)}"
        if not errors:
            summary += f" (exit status {returncode})"
    return EdaResult(passed, summary, tuple(diags), metrics)


# --- SymbiYosys ------------------------------------------------------------------------

_SBY_DONE_RE = re.compile(r"DONE \((?P<status>[A-Z]+), rc=(?P<rc>\d+)\)")
_SBY_FAILED_RE = re.compile(
    r"summary:\s+failed assertion (?P<name>\S+) at (?P<file>[^\s:]+):(?P<line>\d+)\S*(?: step (?P<step>\d+))?"
)
_SBY_TRACE_RE = re.compile(r"summary:\s+counterexample trace(?: \[(?P<kind>\w+)\])?: (?P<path>\S+)")
_SBY_ERROR_RE = re.compile(r"\bERROR:\s*(?P<msg>.*)$")


def parse_sby(log: str, returncode: int) -> EdaResult:
    """Pass means SymbiYosys reported DONE (PASS)."""
    status = "UNKNOWN"
    diags: list[Diagnostic] = []
    traces: list[str] = []
    seen: set[tuple[str, str]] = set()
    for line in log.splitlines():
        if m := _SBY_DONE_RE.search(line):
            status = m["status"]
        elif m := _SBY_FAILED_RE.search(line):
            key = (m["name"], m["line"])
            if key not in seen:
                seen.add(key)
                step = f" at step {m['step']}" if m["step"] else ""
                diags.append(Diagnostic("error", f"assertion {m['name']} failed{step}", "ASSERT",
                                        m["file"], _int(m["line"])))
        elif m := _SBY_TRACE_RE.search(line):
            traces.append(m["path"])
        elif m := _SBY_ERROR_RE.search(line):
            diags.append(Diagnostic("error", m["msg"].strip()))
    passed = status == "PASS" and returncode == 0
    if passed:
        summary = "formal passed: every property proven"
    elif status == "UNKNOWN" and not diags:
        last = next((ln.strip() for ln in reversed(log.splitlines()) if ln.strip()), "no output")
        summary = f"formal did not finish (exit status {returncode}): {last}"
    else:
        summary = f"formal {status.lower()}: {_plural(len(diags), 'error')}{_first(diags)}"
    return EdaResult(passed, summary, tuple(diags),
                     {"status": status, "exit_status": returncode, "traces": traces})


# SBY 21:59:10 [c] engine_0: ##   0:00:00  Reached cover statement in step 2 at c: c.v:6.13-6.29 (_witness_.x)
# SBY 21:59:10 [c] engine_0: ##   0:00:00  Unreached cover statement at c: c.v:7.13-7.29 (_witness_.y)
# (The summary repeats both in lower case; only the engine's lines are counted.)
_SBY_COVER_RE = re.compile(r"\b(?:(?P<un>Unr)|R)eached cover statement (?:in step (?P<step>\d+) )?at (?P<what>.+?)\s*$")
_SBY_WHERE_RE = re.compile(r"(?P<file>[^\s:]+):(?P<line>\d+)\.(?P<column>\d+)")


def _cover_site(what: str) -> tuple[str, int, int] | None:
    """Where a cover statement is: its file's name, line, and column."""
    where = _SBY_WHERE_RE.search(what)
    return (where["file"].rsplit("/", 1)[-1], int(where["line"]), int(where["column"])) if where else None


def parse_sby_cover(log: str, returncode: int, antecedents: Sequence[Mapping[str, Any]] = ()) -> EdaResult:
    """Pass means a cover-mode run reached every cover statement, and there was at least one (M27).

    A proof whose assumptions contradict each other, or whose properties can
    never fire, still passes in prove mode. In cover mode the solver must build
    a trace, under those same assumptions, to each ``cover``: an unreachable
    cover fails the run, and a setup with no covers proves nothing about its
    assumptions, so it fails too.

    ``antecedents`` are the covers derived for the assertions (M29, from
    :mod:`nirmaan.integrations.eda_antecedents`), each with its file, line, and
    column. They are counted apart from the seat's own covers: one that is
    never reached means its assertion is never checked, and the run fails. A
    derived cover that is not in the elaborated design at all (a generate
    branch not taken, a task never called) is listed as a warning.
    """
    base = parse_sby(log, returncode)
    derived = {(Path(a["file"]).name, int(a["line"]), int(a["column"])): a for a in antecedents}
    reached: dict[str, None] = {}
    unreached: dict[str, None] = {}
    ante_reached: dict[str, tuple] = {}
    ante_unreached: dict[str, tuple] = {}
    for line in log.splitlines():
        if m := _SBY_COVER_RE.search(line):
            site = _cover_site(m["what"])
            if site in derived:
                (ante_unreached if m["un"] else ante_reached)[m["what"]] = site
            else:
                (unreached if m["un"] else reached)[m["what"]] = None
    missed = [w for w in unreached if w not in reached]
    ante_missed = [w for w in ante_unreached if w not in ante_reached]
    seen = {*ante_reached.values(), *ante_unreached.values()}
    diags = list(base.diagnostics)
    for what in missed:
        where = _SBY_WHERE_RE.search(what)
        diags.append(Diagnostic("error", f"cover statement never reached: {what}", "COVER",
                                where["file"] if where else "", _int(where["line"]) if where else None))
    never = []
    for what in ante_missed:
        a = derived[ante_unreached[what]]
        never.append(Diagnostic("error", f"assertion never checked, its antecedent is never reached: "
                                         f"{a['assertion']}", "ANTECEDENT", a["file"], int(a["line"])))
    unelaborated = [a for key, a in derived.items() if key not in seen]
    diags += never
    diags += [Diagnostic("warning", f"assertion not in the elaborated design, so no proof checks it: "
                                    f"{a['assertion']}", "ANTECEDENT", a["file"], int(a["line"]))
              for a in unelaborated]
    metrics = {**base.metrics, "covers_reached": len(reached), "covers_unreached": len(missed)}
    if antecedents:
        metrics.update(antecedents_reached=len(ante_reached), antecedents_unreached=len(ante_missed),
                       antecedents_unelaborated=len(unelaborated))
    total = len(reached) + len(missed)
    if missed:
        summary = (f"vacuous: {len(missed)} of {_plural(total, 'cover')} never reached under the "
                   f"assumptions{_first(diags[len(base.diagnostics):])}")
        return EdaResult(False, summary, tuple(diags), metrics)
    if never:
        first = never[0]
        summary = (f"vacuous: {len(never)} of {_plural(len(ante_reached) + len(never), 'assertion antecedent')} "
                   f"never reached under the assumptions, so the assertion at {first.where} is never checked")
        return EdaResult(False, summary, tuple(diags), metrics)
    if not base.passed:
        return EdaResult(False, base.summary.replace("formal", "cover run", 1), tuple(diags), metrics)
    if not reached:
        return EdaResult(False, "no cover statement was reached: a setup with nothing to reach says "
                                "nothing about its assumptions", tuple(diags), metrics)
    also = (f"; every assertion antecedent reached ({len(ante_reached)} of {len(ante_reached)})"
            if ante_reached else "")
    return EdaResult(True, f"not vacuous: every cover reached ({len(reached)} of {len(reached)}){also}",
                     tuple(diags), metrics)
