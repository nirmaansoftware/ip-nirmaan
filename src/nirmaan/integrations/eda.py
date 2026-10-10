"""Open-source EDA behind the tool broker: real runs, or an honest refusal.

A :class:`Backend` declares the executables it needs, the commands it runs,
and how its output is parsed. ``register_backend`` is the extension point: the
first backend for a tool also registers the tool's broker binding, with a probe
that refuses the invocation (and says why) when no backend's executables are
on PATH. Nothing here simulates a tool: a run either happened, and its log and
parsed result are on disk, or the broker refused it.

A failing tool (lint errors, a failing test, a counterexample, a missing
source, a timeout) is a recorded run with ``succeeded=False``, never an
exception. A ``max_<metric>`` parameter is a limit on the parsed metric of that
name: a run over it, or one whose backend did not report the metric, fails.
A ``min_<metric>`` parameter (M34) is the same limit from below.
Simulation logs reach VeriTriage through :func:`triage_simulation`, which invokes ``veritriage.investigate`` through the same broker. This module
never imports VeriTriage.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from nirmaan.integrations.eda_antecedents import DERIVED, Definitions, definitions, derive
from nirmaan.integrations.eda_parsers import (
    Diagnostic,
    EdaResult,
    parse_sby,
    parse_sby_cover,
    parse_simulation,
    parse_verilator_lint,
    parse_yosys,
)
from nirmaan.models import list_values
from nirmaan.runtime.tools import ToolOutcome, register_binding, unregister_binding
from nirmaan.work.engine import TaskEngine

if TYPE_CHECKING:
    from nirmaan.models import Actor, ToolRun
    from nirmaan.runtime.tools import ToolBroker

DEFAULT_TIMEOUT = 300

#: The files a cover run derives antecedent covers in (M29).
HDL_SUFFIXES = (".v", ".sv", ".vh", ".svh")


@dataclass(frozen=True)
class Job:
    """One invocation: the parameters, resolved, and a working directory."""

    tool: str
    params: dict[str, str]
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
    environment: Callable[[dict[str, str]], str | None] | None = None
    #: Asked before any step: why these inputs cannot be run as given (a recorded failed run), or None.
    check: Callable[[Job], str | None] | None = None


_BACKENDS: dict[str, list[Backend]] = {}
_BOUND: set[str] = set()

#: Tools whose runs produce a simulation log VeriTriage can investigate.
SIMULATION_TOOLS = ("simulator.run", "test.run")


def register_backend(backend: Backend) -> Backend:
    """Add a backend. The first one for a tool also binds the tool in the broker."""
    backends = _BACKENDS.setdefault(backend.tool, [])
    if any(b.name == backend.name for b in backends):
        raise ValueError(f"{backend.tool} already has a backend named {backend.name!r}")
    backends.append(backend)
    if backend.tool not in _BOUND:
        register_binding(backend.tool, probe=_probe(backend.tool))(_binding(backend.tool))
        _BOUND.add(backend.tool)
    return backend


def unregister_backend(tool: str, name: str) -> None:
    backends = [b for b in _BACKENDS.get(tool, []) if b.name != name]
    _BACKENDS[tool] = backends
    if not backends and tool in _BOUND:
        unregister_binding(tool)
        _BOUND.discard(tool)


def backends_for(tool: str) -> list[Backend]:
    return list(_BACKENDS.get(tool, []))


def _missing(backend: Backend) -> list[str]:
    return [exe for exe in backend.executables if shutil.which(exe) is None]


def select_backend(tool: str, params: dict[str, str]) -> tuple[Backend | None, str]:
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


def _probe(tool: str) -> Callable[[dict[str, str]], str | None]:
    def probe(params: dict[str, str]) -> str | None:
        backend, why = select_backend(tool, params)
        return None if backend else why

    return probe


def _binding(tool: str) -> Callable[[dict[str, str], TaskEngine], ToolOutcome]:
    def run(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
        backend, why = select_backend(tool, params)
        if backend is None:  # the executable vanished after the probe
            return ToolOutcome(False, why)
        return execute(backend, params)

    return run


def execute(backend: Backend, params: dict[str, str]) -> ToolOutcome:
    """Run the backend's steps for real, parse what they printed, and write both to disk."""
    missing = [p for p in backend.required if not params.get(p, "").strip()]
    if missing:
        return ToolOutcome(False, f"{backend.name}: missing parameter {', '.join(missing)}")
    sources = tuple(str(Path(s).resolve()) for s in list_values(params.get("sources", "")))
    files = [*sources, *([str(Path(params["sby"]).resolve())] if params.get("sby") else [])]
    files += [str(Path(f).resolve()) for p in backend.files for f in list_values(params.get(p, ""))]
    absent = [f for f in files if not Path(f).is_file()]
    if absent:
        return ToolOutcome(False, f"{backend.name}: not found: {', '.join(absent)}")
    workdir = Path(params["workdir"]) if params.get("workdir") else Path(tempfile.mkdtemp(prefix="nirmaan-eda-"))
    workdir.mkdir(parents=True, exist_ok=True)
    workdir = workdir.resolve()
    job = Job(backend.tool, params, workdir, sources, params.get("top") or None)
    problem = backend.check(job) if backend.check else None
    if problem:
        return ToolOutcome(False, f"{backend.name}: {problem}")
    timeout = int(params.get("timeout") or DEFAULT_TIMEOUT)

    chunks: list[str] = []
    codes: list[int] = []
    commands: list[list[str]] = []
    timed_out = None
    cwd = backend.cwd(job) if backend.cwd else workdir
    for argv in backend.steps(job):
        commands.append(argv)
        chunks.append(f"$ {shlex.join(argv)}\n")
        try:
            proc = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            out = exc.output.decode(errors="replace") if isinstance(exc.output, bytes) else (exc.output or "")
            chunks.append(out)
            timed_out = argv[0]
            break
        except OSError as exc:  # not executable, vanished mid-run
            chunks.append(f"{type(exc).__name__}: {exc}\n")
            codes.append(-1)
            break
        chunks.append(proc.stdout)
        codes.append(proc.returncode)
        if proc.returncode != 0:
            break
    log = "".join(chunks)
    log_path = workdir / f"{backend.name}.log"
    log_path.write_text(log, encoding="utf-8")

    result = backend.parse(RunRecord(log, tuple(codes), workdir))
    if timed_out:
        result = EdaResult(False, f"timed out after {timeout}s in {timed_out}", result.diagnostics, result.metrics)
    result = _within_limits(result, params)
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
    return ToolOutcome(result.passed, f"{backend.name}: {result.summary}",
                       references=(str(log_path), str(result_path)), data=record)


def _within_limits(result: EdaResult, params: dict[str, str]) -> EdaResult:
    """Fail a passing result that breaks a ``max_<metric>`` or (M34) ``min_<metric>`` limit, or whose metric
    was never measured."""
    over = []
    for key, limit in params.items():
        bound_kind = key[:4]
        if bound_kind not in ("max_", "min_") or not result.passed:
            continue
        metric, measured = key[4:], result.metrics.get(key[4:])
        try:
            bound = float(limit)
        except ValueError:
            over.append(f"{key} {limit!r} is not a number")
            continue
        if isinstance(measured, bool) or not isinstance(measured, (int, float)):
            over.append(f"{metric} was not reported, so {key} cannot be checked")
        elif bound_kind == "max_" and measured > bound:
            over.append(f"{metric} {measured} exceeds {key} {limit}")
        elif bound_kind == "min_" and measured < bound:
            over.append(f"{metric} {measured} is below {key} {limit}")
    if not over:
        return result
    diags = (*result.diagnostics, *(Diagnostic("error", m, "LIMIT") for m in over))
    return EdaResult(False, f"limit not met: {'; '.join(over)} (the tool reported: {result.summary})",
                     diags, result.metrics)


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


def _icarus(job: Job) -> list[list[str]]:
    return [["iverilog", "-g2012", "-o", "sim.vvp", "-s", str(job.top), *job.sources],
            ["vvp", "-n", "sim.vvp"]]


def _verilator_sim(job: Job) -> list[list[str]]:
    return [["verilator", "--binary", "-Wno-fatal", "-j", "0", "--top-module", str(job.top),
             "-Mdir", "obj", *job.sources],
            [str(job.workdir / "obj" / f"V{job.top}")]]


def _yosys(job: Job) -> list[list[str]]:
    script = [*(f'read_verilog -sv "{src}"' for src in job.sources),
              f"synth -top {job.top}", "tee -q -o stat.json stat -json"]
    (job.workdir / "synth.ys").write_text("\n".join(script) + "\n", encoding="utf-8")
    (job.workdir / "stat.json").unlink(missing_ok=True)
    return [["yosys", "-s", "synth.ys"]]


def _yosys_parse(run: RunRecord) -> EdaResult:
    stat = run.workdir / "stat.json"
    return parse_yosys(run.log, run.returncode, stat.read_text(encoding="utf-8") if stat.is_file() else None)


def _sby(job: Job) -> list[list[str]]:
    return [["sby", "-f", "-d", str(job.workdir / "sby"), str(Path(job.params["sby"]).resolve())]]


def _sby_dir(job: Job) -> Path:
    """sby resolves its [files] against the directory it runs in: the .sby file's own."""
    return Path(job.params["sby"]).resolve().parent


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
    return parse_simulation(run.log, run.returncodes)


def _sby_parse(run: RunRecord) -> EdaResult:
    return parse_sby(run.log, run.returncode)


def _sby_cover_parse(run: RunRecord) -> EdaResult:
    manifest = run.workdir / "antecedents.json"
    sites = json.loads(manifest.read_text(encoding="utf-8"))["sites"] if manifest.is_file() else []
    return parse_sby_cover(run.log, run.returncode, [s for s in sites if s["kind"] in DERIVED])


register_backend(Backend("verilator-lint", "lint.run", ("verilator",), _verilator_lint, _lint_parse))
for _tool in SIMULATION_TOOLS:
    register_backend(Backend("icarus", _tool, ("iverilog", "vvp"), _icarus, _sim_parse, ("sources", "top")))
    register_backend(Backend("verilator-sim", _tool, ("verilator",), _verilator_sim, _sim_parse, ("sources", "top")))
register_backend(Backend("yosys", "synth.run", ("yosys",), _yosys, _yosys_parse, ("sources", "top")))
register_backend(Backend("symbiyosys", "formal.run", ("sby", "yosys"), _sby, _sby_parse, ("sby",), _sby_dir,
                         check=_sby_reads))
register_backend(Backend("symbiyosys-cover", "formal.cover", ("sby", "yosys"), _sby_cover, _sby_cover_parse,
                         ("sby",), check=_sby_cover_check))
