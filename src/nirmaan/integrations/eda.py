"""Open-source EDA behind the tool broker: real runs, or an honest refusal.

A :class:`Backend` declares the executables it needs, the commands it runs,
and how its output is parsed. ``register_backend`` is the extension point: the
first backend for a tool also registers the tool's broker binding, with a probe
that refuses the invocation (and says why) when no backend's executables are
on PATH. Nothing here simulates a tool: a run either happened, and its log and
parsed result are on disk, or the broker refused it.

A failing tool (lint errors, a failing test, a counterexample, a missing
source, a timeout) is a recorded run with ``succeeded=False``, never an
exception. The parsed metrics go back with the outcome, and the broker checks
them against a requirement's bounds (M48); a parameter is only ever a
parameter, whatever its name.
Simulation logs reach VeriTriage through :func:`triage_simulation`, which invokes ``veritriage.investigate`` through the same broker. This module
never imports VeriTriage.

M53 (docs/GATE_INTEGRITY.md): each run gets its own new directory, under
``workdir`` when one is given; its steps see an environment with no
credential in it. The timeout covers the
whole run, and stops every process a step started, not only the first. A
simulation passes only on the testbench's own verdict, which carries a nonce
the run passed in.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from nirmaan.integrations.eda_antecedents import DERIVED, Definitions, definitions, derive
from nirmaan.integrations.eda_parsers import (
    Diagnostic,
    EdaResult,
    parse_coverage,
    parse_reproduction,
    parse_sby,
    parse_sby_cover,
    parse_simulation,
    parse_verilator_lint,
    parse_yosys,
)
from nirmaan.models import list_values, text_value
from nirmaan.registry import Registry
from nirmaan.runtime.tools import Params, ToolOutcome, register_binding, unregister_binding
from nirmaan.work.engine import TaskEngine

if TYPE_CHECKING:
    from nirmaan.models import Actor, ToolRun
    from nirmaan.runtime.tools import ToolBroker

DEFAULT_TIMEOUT = 300

#: Environment variables no tool run sees (M53): code a seat wrote runs in these steps, and what it prints
#: lands in logs and records, so a credential in its environment could be copied out.
SECRET_ENV_RE = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|PRIVATE_KEY|^ANTHROPIC_", re.IGNORECASE)
#: A value shorter than this is not redacted from what a run printed: it would match ordinary text.
_REDACT_MIN = 16

#: How a run passes its nonce to the program that reports the verdict (M53): a simulator plusarg.
NONCE_ARG = "+nirmaan_nonce="
_NONCE_ECHO_RE = re.compile(r"^\$ .*" + re.escape(NONCE_ARG) + r"(?P<nonce>[0-9a-f]+)\b", re.MULTILINE)

#: The files a cover run derives antecedent covers in (M29).
HDL_SUFFIXES = (".v", ".sv", ".vh", ".svh")


@dataclass(frozen=True)
class Job:
    """One invocation: the parameters, resolved, and a working directory."""

    tool: str
    params: Params
    workdir: Path
    sources: tuple[str, ...]
    top: str | None

    def top_args(self, flag: str) -> list[str]:
        return [flag, self.top] if self.top else []


@dataclass(frozen=True)
class RunRecord:
    """What the executables did: their combined output and exit statuses."""

    log: str
    returncodes: tuple[int, ...]
    workdir: Path

    @property
    def returncode(self) -> int:
        return self.returncodes[-1] if self.returncodes else -1


@dataclass(frozen=True)
class Backend:
    name: str
    tool: str
    executables: tuple[str, ...]
    steps: Callable[[Job], list[list[str]]]
    parse: Callable[[RunRecord], EdaResult]
    required: tuple[str, ...] = ("sources",)
    #: Where the steps run; the job's working directory unless the tool needs another.
    cwd: Callable[[Job], Path] | None = None
    #: Parameters naming files (comma separated) that must exist before any step runs.
    files: tuple[str, ...] = ()
    #: Asked with the executables: why this machine's environment (a PDK) cannot serve the job, or None.
    environment: Callable[[Params], str | None] | None = None
    #: Asked before any step: why these inputs cannot be run as given (a recorded failed run), or None.
    check: Callable[[Job], str | None] | None = None


_BACKENDS: MutableMapping[str, list[Backend]] = Registry("eda.backends")
#: Tools whose broker binding a backend created (a registry of ``True``, so a scope has its own).
_BOUND: MutableMapping[str, bool] = Registry("eda.bound")

#: Tools whose runs produce a simulation log VeriTriage can investigate.
SIMULATION_TOOLS = ("simulator.run", "test.run")
#: M71: where a simulation records the ``expect`` it ran with, for the parser (docs/REPRO_GATES.md).
SIM_EXPECT = "expect.txt"


def register_backend(backend: Backend) -> Backend:
    """Add a backend. The first one for a tool also binds the tool in the broker."""
    backends = _BACKENDS.get(backend.tool, [])
    if any(b.name == backend.name for b in backends):
        raise ValueError(f"{backend.tool} already has a backend named {backend.name!r}")
    _BACKENDS[backend.tool] = [*backends, backend]  # a new list: in a scope, the defaults' list is left alone
    if backend.tool not in _BOUND:
        register_binding(backend.tool, probe=_probe(backend.tool))(_binding(backend.tool))
        _BOUND[backend.tool] = True
    return backend


def unregister_backend(tool: str, name: str) -> None:
    backends = [b for b in _BACKENDS.get(tool, []) if b.name != name]
    _BACKENDS[tool] = backends
    if not backends and tool in _BOUND:
        unregister_binding(tool)
        _BOUND.pop(tool, None)


def backends_for(tool: str) -> list[Backend]:
    return list(_BACKENDS.get(tool, []))


def _missing(backend: Backend) -> list[str]:
    return [exe for exe in backend.executables if shutil.which(exe) is None]


def select_backend(tool: str, params: Params) -> tuple[Backend | None, str]:
    """The backend that will run, or None and the reason none can run here."""
    wanted = params.get("backend")
    candidates = [b for b in _BACKENDS.get(tool, []) if not wanted or b.name == wanted]
    if not candidates:
        return None, f"{tool} has no backend named {wanted!r}"
    reasons = []
    for backend in candidates:
        missing = _missing(backend)
        lacking = backend.environment(params) if backend.environment else None
        if not missing and not lacking:
            return backend, ""
        if missing:
            reasons.append(f"{backend.name} needs {', '.join(missing)} on PATH, not found")
        if lacking:
            reasons.append(f"{backend.name}: {lacking}")
    return None, f"{tool} cannot run here: {'; '.join(reasons)} (refused, never simulated)"


def timeout_problem(params: Params) -> str | None:
    """Why the ``timeout`` given cannot bound a run (M53), or None."""
    given = text_value(params.get("timeout")).strip()
    if not given:
        return None
    try:
        seconds = int(given)
    except ValueError:
        return f"timeout must be a whole number of seconds, not {given!r}"
    return None if seconds >= 1 else f"timeout must be at least 1 second, not {seconds}"


def _probe(tool: str) -> Callable[[Params], str | None]:
    def probe(params: Params) -> str | None:
        too_short = timeout_problem(params)
        if too_short:
            return f"{tool}: {too_short} (refused, nothing ran)"
        backend, why = select_backend(tool, params)
        return None if backend else why

    return probe


def _binding(tool: str) -> Callable[[Params, TaskEngine], ToolOutcome]:
    def run(params: Params, engine: TaskEngine) -> ToolOutcome:
        backend, why = select_backend(tool, params)
        if backend is None:  # the executable vanished after the probe
            return ToolOutcome(False, why)
        return execute(backend, params)

    return run


def execute(backend: Backend, params: Params) -> ToolOutcome:
    """Run the backend's steps for real, parse what they printed, and write both to disk."""
    missing = [p for p in backend.required if not text_value(params.get(p)).strip()]
    if missing:
        return ToolOutcome(False, f"{backend.name}: missing parameter {', '.join(missing)}")
    sources = tuple(str(Path(s).resolve()) for s in list_values(params.get("sources", "")))
    files = [*sources, *([str(Path(params["sby"]).resolve())] if params.get("sby") else [])]
    files += [str(Path(f).resolve()) for p in backend.files for f in list_values(params.get(p, ""))]
    absent = [f for f in files if not Path(f).is_file()]
    if absent:
        return ToolOutcome(False, f"{backend.name}: not found: {', '.join(absent)}")
    too_short = timeout_problem(params)
    if too_short:
        return ToolOutcome(False, f"{backend.name}: {too_short}")
    workdir = run_directory(backend.name, params.get("workdir"))
    job = Job(backend.tool, params, workdir, sources, params.get("top") or None)
    problem = backend.check(job) if backend.check else None
    if problem:
        return ToolOutcome(False, f"{backend.name}: {problem}")
    timeout = int(text_value(params.get("timeout")).strip() or DEFAULT_TIMEOUT)

    chunks: list[str] = []
    codes: list[int] = []
    commands: list[list[str]] = []
    timed_out = None
    cwd = backend.cwd(job) if backend.cwd else workdir
    env = run_environment(workdir)
    deadline = time.monotonic() + timeout  # M53: one deadline for the whole run, not one per step
    for argv in backend.steps(job):
        commands.append(argv)
        chunks.append(f"$ {shlex.join(argv)}\n")
        output, code = _run_step(argv, cwd, env, deadline)
        chunks.append(output)
        if code is None:
            timed_out = argv[0]
            break
        codes.append(code)
        if code != 0:
            break
    log = redact("".join(chunks))
    log_path = workdir / f"{backend.name}.log"
    log_path.write_text(log, encoding="utf-8")

    result = backend.parse(RunRecord(log, tuple(codes), workdir))
    if timed_out:
        result = EdaResult(False, f"timed out after {timeout}s in {timed_out}", result.diagnostics, result.metrics)
    result = EdaResult(result.passed, redact(result.summary), result.diagnostics, result.metrics)
    record = {
        "tool": backend.tool,
        "backend": backend.name,
        "executables": {exe: shutil.which(exe) for exe in backend.executables},
        "commands": commands,
        "exit_statuses": codes,
        "log": str(log_path),
        "result": result.to_dict(),
    }
    result_path = workdir / f"{backend.name}.result.json"
    result_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # M44: what the run wrote, by name: its log, and the files its backend reports under ``outputs``.
    reported = result.metrics.get("outputs")
    outputs = {"log": str(log_path), **{str(k): str(v) for k, v in (reported or {}).items()
                                        if isinstance(reported, dict) and v and Path(str(v)).is_file()}}
    return ToolOutcome(result.passed, f"{backend.name}: {result.summary}",
                       references=(str(log_path), str(result_path)), data=record, outputs=outputs,
                       metrics=dict(result.metrics))


#: The file a run claims an empty ``workdir`` with (M53), so a second run there gets a directory of its own.
RUN_CLAIM = ".nirmaan-run"


def run_directory(name: str, under: object = None) -> Path:
    """The directory one run works in (M53).

    Without ``under``, a new one in the system's temporary directory. With it, ``under``
    itself when it is new or empty and this run claims it first (an exclusive create of
    :data:`RUN_CLAIM`); otherwise a new directory inside it. So a run never deletes or
    overwrites a file it did not put there, and two runs given the same directory, at
    once or one after the other, never share one.
    """
    root = Path(text_value(under).strip()) if text_value(under).strip() else None
    if root is None:
        return Path(tempfile.mkdtemp(prefix=f"nirmaan-{name}-")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not any(root.iterdir()):
        try:
            os.close(os.open(root / RUN_CLAIM, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return root.resolve()
        except FileExistsError:
            pass
    return Path(tempfile.mkdtemp(prefix=f"nirmaan-{name}-", dir=root)).resolve()


def run_environment(workdir: Path) -> dict[str, str]:
    """What a run's steps see (M53): this process's environment with no credential in it.

    ``TMPDIR`` is left as it is: pointed into the run's directory, Yosys's ABC step hung in the
    OpenROAD-flow-scripts image (docs/GATE_INTEGRITY.md, section 4).
    """
    return {k: v for k, v in os.environ.items() if not SECRET_ENV_RE.search(k)}


def redact(text: str) -> str:
    """``text`` with the value of every credential in this process's environment replaced (M53)."""
    for key, value in os.environ.items():
        if SECRET_ENV_RE.search(key) and len(value) >= _REDACT_MIN and value in text:
            text = text.replace(value, f"[{key} redacted]")
    return text


def _descendants(root: int) -> set[int]:
    """Every live process below ``root``, from one ``ps`` snapshot."""
    try:
        listing = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout
    except OSError:  # no ps (a minimal container): the step's own process group is still killed
        return set()
    children: dict[int, list[int]] = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit():
            children.setdefault(int(fields[1]), []).append(int(fields[0]))
    found, todo = set(), [root]
    while todo:
        for child in children.get(todo.pop(), ()):
            if child not in found:
                found.add(child)
                todo.append(child)
    return found


def _signal(pid: int, sig: int, group: bool = False) -> None:
    try:
        (os.killpg if group else os.kill)(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _stop_tree(proc: subprocess.Popen) -> None:
    """Stop a step and every process it started (M53).

    The step leads a new process group, but a tool may put its own children in
    groups of their own (``sby`` does, for each solver). So the whole tree is
    frozen first, while every process still has its parent, then killed with
    every group in it.
    """
    frozen: set[int] = set()
    for _ in range(3):  # a process forked while the tree was being frozen is caught on the next pass
        found = ({proc.pid} | _descendants(proc.pid)) - frozen
        if not found:
            break
        for pid in found:
            _signal(pid, signal.SIGSTOP)
        frozen |= found
    groups = set()
    for pid in frozen:
        try:
            groups.add(os.getpgid(pid))
        except (ProcessLookupError, PermissionError):
            pass
    for group in groups - {os.getpgrp()}:
        _signal(group, signal.SIGKILL, group=True)
    for pid in frozen:
        _signal(pid, signal.SIGKILL)


def _run_step(argv: list[str], cwd: Path, env: dict[str, str], deadline: float) -> tuple[str, int | None]:
    """Run one step in its own process group; its output and exit status, or None when the deadline passed."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return "", None
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", start_new_session=True)
    except OSError as exc:  # not executable, vanished mid-run
        return f"{type(exc).__name__}: {exc}\n", -1
    try:
        output, _ = proc.communicate(timeout=remaining)
    except subprocess.TimeoutExpired:
        _stop_tree(proc)
        try:
            output, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # a process outside the group still holds the output open
            output = ""
        return output or "", None
    return output or "", proc.returncode


def new_nonce() -> str:
    """A fresh nonce for one run (M53): the program under test cannot know it, so cannot print it."""
    return secrets.token_hex(16)


def run_nonce(log: str) -> str | None:
    """The nonce the run passed, read from the runner's own echo of the step that took it."""
    found = _NONCE_ECHO_RE.search(log)
    return found["nonce"] if found else None


def triage_simulation(broker: ToolBroker, actor: Actor, run: ToolRun, task_id: str | None = None,
                      workspace: str | None = None):
    """Hand a recorded simulation's log to ``veritriage.investigate``, as its own brokered run."""
    if run.tool not in SIMULATION_TOOLS or not run.references:
        raise ValueError(f"{run.id} is not a simulation run with a log")
    params = {"paths": run.references[0]}
    if workspace:
        params["workspace"] = workspace
    return broker.invoke(actor, "veritriage.investigate", params, task_id or run.task)


# --- The built-in backends --------------------------------------------------------------


def _verilator_lint(job: Job) -> list[list[str]]:
    return [["verilator", "--lint-only", "-Wall", *job.top_args("--top-module"), *job.sources]]


def _expect(job: Job) -> None:
    """Record what this simulation's pass means (M71), for the parser; only ``fail`` changes it."""
    (job.workdir / SIM_EXPECT).write_text(text_value(job.params.get("expect")).strip() or "pass", encoding="utf-8")


def _icarus(job: Job) -> list[list[str]]:
    _expect(job)
    return [["iverilog", "-g2012", "-o", "sim.vvp", "-s", str(job.top), *job.sources],
            ["vvp", "-n", "sim.vvp", NONCE_ARG + new_nonce()]]


def _verilator_sim(job: Job) -> list[list[str]]:
    _expect(job)
    return [["verilator", "--binary", "-Wno-fatal", "-j", "0", "--top-module", str(job.top),
             "-Mdir", "obj", *job.sources],
            [str(job.workdir / "obj" / f"V{job.top}"), NONCE_ARG + new_nonce()]]


#: What only the testbench, the file that declares the top module, may use (M53, docs/GATE_INTEGRITY.md).
#: A design that ends the run, or reads the run's nonce, could stand in for the testbench's verdict.
TESTBENCH_ONLY = ("$finish", "$stop", "$exit", "$value$plusargs", "$test$plusargs", "$fopen", "$system", "$c",
                  "DPI")
_TESTBENCH_ONLY_RE = re.compile(r"(?<![\w$])(?:" + "|".join(re.escape(t) for t in TESTBENCH_ONLY) + r")(?![\w$])")
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def simulation_problem(job: Job) -> str | None:
    """Why a simulation cannot run as given: an ``expect`` other than pass or fail (M71), or a design that could
    stand in for its testbench's verdict (M53)."""
    expect = text_value(job.params.get("expect")).strip()
    if expect not in ("", "pass", "fail"):
        return f"expect must be pass or fail, not {expect!r}; nothing was simulated"
    return testbench_only_problem(job)


def _code(source: str) -> str:
    """A source file's text without its comments."""
    return _COMMENT_RE.sub("", Path(source).read_text(encoding="utf-8", errors="replace"))


def _top_re(job: Job) -> re.Pattern[str]:
    """Matches the declaration of the run's top module: the file that has it is the testbench."""
    return re.compile(rf"\bmodule\s+{re.escape(str(job.top))}\b")


def testbench_only_problem(job: Job) -> str | None:
    """Why a simulation's sources cannot be judged by their testbench's verdict (M53), or None.

    The file that declares the top module is the testbench. No other file may end
    the simulation, read a plusarg, open a file, or reach outside the language.
    """
    top = _top_re(job)
    found = []
    for source in job.sources:
        text = _code(source)
        if top.search(text):
            continue
        used = sorted(set(_TESTBENCH_ONLY_RE.findall(text)))
        if used:
            found.append(f"{Path(source).name} uses {', '.join(used)}")
        if "`" in text and "``" in text:
            found.append(f"{Path(source).name} pastes tokens (``), which could build any of them")
    if not found:
        return None
    return (f"only the testbench (the file that declares {job.top}) may end the simulation or read its "
            f"arguments, and {'; '.join(found)}; nothing was simulated")


#: M70 (docs/COVERAGE_READ.md): where a coverage run records the files whose coverage it measures, for the
#: parser, and the files it writes: the data the simulation wrote, that data as ``verilator_coverage`` writes
#: it back, and the same as an lcov report.
COVERAGE_DESIGN = "coverage_design.json"
COVERAGE_RAW = "coverage_sim.dat"
COVERAGE_DATA = "coverage.dat"
COVERAGE_INFO = "coverage.info"
#: What no source of a coverage run may use (M70), the testbench included: each could write the coverage file
#: the run reads, or change the counts, from outside the design.
COVERAGE_FORBIDDEN = ("$fopen", "$system", "$c", "DPI")
_COVERAGE_FORBIDDEN_RE = re.compile(r"(?<![\w$])(?:" + "|".join(re.escape(t) for t in COVERAGE_FORBIDDEN)
                                    + r")(?![\w$])")
#: What only a design file may carry (M70): a Verilator configuration or a coverage pragma turns points off in any
#: file, and an included file is text the check never read. In the approved RTL they are there for its reviewer.
_COVERAGE_CONFIG_RE = re.compile(r"`verilator_config|`include\b|\bcoverage_(?:block_)?off\b")


def coverage_design(job: Job) -> list[str]:
    """The files whose coverage a run measures: ``design`` when given, else every source but the testbench."""
    given = [str(Path(f).resolve()) for f in list_values(job.params.get("design", ""))]
    if given:
        return given
    top = _top_re(job)
    return [s for s in job.sources if not top.search(_code(s))]


def coverage_problem(job: Job) -> str | None:
    """Why a coverage run cannot be judged as given (M70), or None.

    The sources are judged as a simulation's are (M53), every one is Verilog, and none uses what could forge
    the coverage data. The design files are sources, none of them the testbench, and only they may carry a
    Verilator configuration, a coverage pragma or an include.
    """
    problem = testbench_only_problem(job)
    if problem:
        return problem
    other = [Path(s).name for s in job.sources if Path(s).suffix not in HDL_SUFFIXES]
    if other:
        return f"coverage runs read Verilog sources only, and {', '.join(other)} is not; nothing was simulated"
    design = coverage_design(job)
    top = _top_re(job)
    if not design:
        return "no design file to measure: every source is the testbench; nothing was simulated"
    absent = [Path(f).name for f in design if f not in job.sources]
    if absent:
        return f"design files must be among the sources, and {', '.join(absent)} is not; nothing was simulated"
    found = []
    for source in job.sources:
        raw = Path(source).read_text(encoding="utf-8", errors="replace")
        text = _COMMENT_RE.sub("", raw)
        if top.search(text) and source in design:
            return f"{Path(source).name} declares {job.top}: the testbench is never measured; nothing was simulated"
        used = sorted(set(_COVERAGE_FORBIDDEN_RE.findall(text)))
        if source not in design:  # a pragma is a comment, so the whole text is read
            used += sorted(set(_COVERAGE_CONFIG_RE.findall(raw)))
        if used:
            found.append(f"{Path(source).name} uses {', '.join(used)}")
    if found:
        return (f"a coverage run reads only the counts the design's own code reached, and {'; '.join(found)}; "
                "nothing was simulated")
    return None


def _verilator_coverage(job: Job) -> list[list[str]]:
    """Build the simulation with line and toggle coverage, run it, then have ``verilator_coverage`` read the data
    the run wrote and write it back, as data and as an lcov report (M70)."""
    (job.workdir / COVERAGE_DESIGN).write_text(json.dumps({"design": coverage_design(job)}) + "\n", encoding="utf-8")
    raw, data = job.workdir / COVERAGE_RAW, job.workdir / COVERAGE_DATA
    return [["verilator", "--binary", "--coverage-line", "--coverage-toggle", "-Wno-fatal", "-j", "0",
             "--top-module", str(job.top), "-Mdir", "obj", *job.sources],
            [str(job.workdir / "obj" / f"V{job.top}"), NONCE_ARG + new_nonce(), f"+verilator+coverage+file+{raw}"],
            ["verilator_coverage", "--write", str(data), str(raw)],
            ["verilator_coverage", "--write-info", str(job.workdir / COVERAGE_INFO), str(data)]]


def _yosys(job: Job) -> list[list[str]]:
    script = [*(f'read_verilog -sv "{src}"' for src in job.sources),
              f"synth -top {job.top}", "tee -q -o stat.json stat -json"]
    (job.workdir / "synth.ys").write_text("\n".join(script) + "\n", encoding="utf-8")
    (job.workdir / "stat.json").unlink(missing_ok=True)
    return [["yosys", "-s", "synth.ys"]]


def _yosys_parse(run: RunRecord) -> EdaResult:
    stat = run.workdir / "stat.json"
    return parse_yosys(run.log, run.returncode, stat.read_text(encoding="utf-8") if stat.is_file() else None)


#: sby's depth when ``[options]`` names none.
SBY_DEFAULT_DEPTH = 20
#: Where a ``formal.run`` records the mode and depth it ran, for the parser (M53).
FORMAL_OPTIONS = "formal_options.json"


def sby_options(sby: Path) -> dict[str, object]:
    """The ``mode`` and ``depth`` a single-task setup runs with."""
    mode, depth = None, SBY_DEFAULT_DEPTH
    for section, line in _sby_sections(sby):
        words = line.split()
        if section == "options" and len(words) >= 2 and words[0] == "mode":
            mode = words[1]
        elif section == "options" and len(words) >= 2 and words[0] == "depth" and words[1].isdigit():
            depth = int(words[1])
    return {"mode": mode, "depth": depth}


def _sby(job: Job) -> list[list[str]]:
    sby = Path(job.params["sby"]).resolve()
    (job.workdir / FORMAL_OPTIONS).write_text(json.dumps(sby_options(sby)) + "\n", encoding="utf-8")
    return [["sby", "-f", "-d", str(job.workdir / "sby"), str(sby)]]


def _sby_dir(job: Job) -> Path:
    """sby resolves its [files] against the directory it runs in: the .sby file's own."""
    return Path(job.params["sby"]).resolve().parent


def _sby_tasks(job: Job) -> str | None:
    """A setup with ``[tasks]`` runs one task per invocation, so none of them would be the one judged (M53)."""
    sby = Path(job.params["sby"]).resolve()
    if any(section == "tasks" for section, _ in _sby_sections(sby)):
        return f"{sby.name} declares [tasks]; formal runs single-task setups only (refused, nothing ran)"
    return None


def _sby_check(job: Job) -> str | None:
    """``formal.run`` takes a single-task setup, over the sources it is given."""
    return _sby_tasks(job) or _sby_reads(job)


def _sby_reads(job: Job) -> str | None:
    """With ``sources``, the proof must read those very files: each is listed in the .sby's [files]."""
    if not job.sources:
        return None
    sby = Path(job.params["sby"]).resolve()
    listed, section = set(), None
    for line in sby.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1].strip()
        elif section == "files" and text and not text.startswith("#"):
            listed.add(str((sby.parent / text.split()[-1]).resolve()))
    unread = [Path(src).name for src in job.sources if src not in listed]
    return f"{sby.name} does not read {', '.join(unread)} (not in its [files])" if unread else None


def _sby_sections(sby: Path) -> list[tuple[str | None, str]]:
    """Each line of a .sby, with the section it is in."""
    out, section = [], None
    for line in sby.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1].strip()
        out.append((section, line))
    return out


def _hdl_files(sby: Path) -> list[tuple[str, Path]]:
    """The Verilog the setup reads: each [files] entry's name in the run, and the file itself."""
    files = []
    for section, line in _sby_sections(sby):
        text = line.strip()
        if section == "files" and text and not text.startswith("[") and not text.startswith("#"):
            *dest, src = text.split()
            path = (sby.parent / src).resolve()
            if path.suffix in HDL_SUFFIXES:
                files.append((dest[0] if dest else path.name, path))
    return files


def _definitions(sby: Path) -> Definitions:
    """The macros and named properties of every Verilog file the setup reads (M37): one may use another's."""
    return definitions(path.read_text(encoding="utf-8", errors="replace") for _, path in _hdl_files(sby))


def _sby_cover(job: Job) -> list[list[str]]:
    """Run the seat's own setup in cover mode (M27), from a copy written into the run's directory.

    The copy differs only in ``mode cover`` and in naming each ``[files]`` entry
    by absolute path, so the script, the engines, the depth, and the
    assumptions are exactly the ones the proof used, and nothing is written next
    to the submitted files. Each Verilog file it reads is itself a copy with a
    cover derived for every assertion (M29, ``eda_antecedents``); the derived
    covers are listed in ``antecedents.json`` beside the run, for the parser.
    """
    sby = Path(job.params["sby"]).resolve()
    copies, sites = {}, []
    defs = _definitions(sby)
    for name, path in _hdl_files(sby):
        derivation = derive(path.read_text(encoding="utf-8", errors="replace"), name, defs)
        copy = job.workdir / "antecedents" / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text(derivation.text, encoding="utf-8")
        copies[path] = copy
        sites += [{**s.to_dict(), "source": str(path)} for s in derivation.sites]
    (job.workdir / "antecedents.json").write_text(json.dumps({"sites": sites}, indent=2) + "\n", encoding="utf-8")
    out = []
    for section, line in _sby_sections(sby):
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            out.append(line)
            if section == "options":
                out.append("mode cover")
            continue
        if section == "options" and text.split()[:1] == ["mode"]:
            continue
        if section == "files" and text and not text.startswith("#"):
            *dest, src = text.split()
            path = (sby.parent / src).resolve()
            line = " ".join([*dest, str(copies.get(path, path))])
        out.append(line)
    cover = job.workdir / f"{sby.stem}_cover.sby"
    cover.write_text("\n".join(out) + "\n", encoding="utf-8")
    return [["sby", "-f", "-d", str(job.workdir / "sby_cover"), str(cover)]]


def _sby_cover_check(job: Job) -> str | None:
    """The cover run needs a single-task setup with options to rewrite, over the RTL it claims to cover,
    with an antecedent cover derivable for every assertion it reads (M29)."""
    sby = Path(job.params["sby"])
    text = sby.read_text(encoding="utf-8", errors="replace")
    sections = {ln.strip()[1:-1].strip() for ln in text.splitlines()
                if ln.strip().startswith("[") and ln.strip().endswith("]")}
    if "tasks" in sections:
        return f"{sby.name} declares [tasks]; the cover check runs single-task setups only"
    if "options" not in sections:
        return f"{sby.name} has no [options] section to run in cover mode"
    unread = _sby_reads(job)
    if unread:
        return unread
    defs = _definitions(sby.resolve())
    underived = [s for name, path in _hdl_files(sby.resolve())
                 for s in derive(path.read_text(encoding="utf-8", errors="replace"), name, defs).underived]
    if underived:
        listed = "; ".join(f"{s.where} ({s.reason})" for s in underived)
        return (f"cannot derive the antecedent of {len(underived)} assertion{'s' if len(underived) > 1 else ''}: "
                f"{listed}. A proof whose antecedents cannot be covered is not known to check anything")
    return None


def _lint_parse(run: RunRecord) -> EdaResult:
    return parse_verilator_lint(run.log, run.returncode)


def _sim_parse(run: RunRecord) -> EdaResult:
    expect = run.workdir / SIM_EXPECT
    if expect.is_file() and expect.read_text(encoding="utf-8").strip() == "fail":  # M71: a reproduction
        return parse_reproduction(run.log, run.returncodes, nonce=run_nonce(run.log) or "")
    return parse_simulation(run.log, run.returncodes, nonce=run_nonce(run.log) or "")


def _coverage_parse(run: RunRecord) -> EdaResult:
    data = run.workdir / COVERAGE_DATA
    manifest = run.workdir / COVERAGE_DESIGN
    design = json.loads(manifest.read_text(encoding="utf-8"))["design"] if manifest.is_file() else []
    result = parse_coverage(run.log, run.returncodes, nonce=run_nonce(run.log) or "",
                            data=data.read_text(encoding="utf-8", errors="replace") if data.is_file() else None,
                            design=design)
    if not result.passed:
        return result
    outputs = {"coverage": str(data), "info": str(run.workdir / COVERAGE_INFO)}
    return EdaResult(True, result.summary, result.diagnostics, {**result.metrics, "outputs": outputs})


def _sby_parse(run: RunRecord) -> EdaResult:
    options = run.workdir / FORMAL_OPTIONS
    ran = json.loads(options.read_text(encoding="utf-8")) if options.is_file() else {}
    return parse_sby(run.log, run.returncode, mode=ran.get("mode"), depth=ran.get("depth"))


def _sby_cover_parse(run: RunRecord) -> EdaResult:
    manifest = run.workdir / "antecedents.json"
    sites = json.loads(manifest.read_text(encoding="utf-8"))["sites"] if manifest.is_file() else []
    return parse_sby_cover(run.log, run.returncode, [s for s in sites if s["kind"] in DERIVED])


register_backend(Backend("verilator-lint", "lint.run", ("verilator",), _verilator_lint, _lint_parse))
for _tool in SIMULATION_TOOLS:
    register_backend(Backend("icarus", _tool, ("iverilog", "vvp"), _icarus, _sim_parse, ("sources", "top"),
                             check=simulation_problem))
    register_backend(Backend("verilator-sim", _tool, ("verilator",), _verilator_sim, _sim_parse, ("sources", "top"),
                             check=simulation_problem))
register_backend(Backend("verilator-coverage", "coverage.read", ("verilator", "verilator_coverage"),
                         _verilator_coverage, _coverage_parse, ("sources", "top"), files=("design",),
                         check=coverage_problem))
register_backend(Backend("yosys", "synth.run", ("yosys",), _yosys, _yosys_parse, ("sources", "top")))
register_backend(Backend("symbiyosys", "formal.run", ("sby", "yosys"), _sby, _sby_parse, ("sby",), _sby_dir,
                         check=_sby_check))
register_backend(Backend("symbiyosys-cover", "formal.cover", ("sby", "yosys"), _sby_cover, _sby_cover_parse,
                         ("sby",), check=_sby_cover_check))
