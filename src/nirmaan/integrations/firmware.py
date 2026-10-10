"""Firmware behind the tool broker: a strict C build, and a driver run on the real RTL.

Two tools register through M21's :func:`register_backend`, so the broker, the
engine, and the policy do not change:

* ``fw.build`` compiles C sources under ``-std=c11 -Wall -Wextra -Werror
  -pedantic``. Headers are compiled on their own too (``-fsyntax-only``).
* ``fw.test`` compiles the driver and its tests the same way, builds a
  Verilator model of the RTL around ``firmware_harness/axil_manager.cpp`` (an
  AXI4-Lite manager implementing the ``nirmaan_hal`` bus), and runs it: every
  register access the driver makes is a real transaction on the model.

M41 (docs/REGISTER_MAP_ADOPTION.md): the bus manager is chosen as data, from a
registry by bus name (``axi4-lite`` and ``apb`` ship), by the ``bus``
parameter or the bus the ``map`` names. With a ``map``, the header generated
from it is on the include path as ``<block>_map.h``, and an agreement unit
fails the build when the header the driver includes disagrees with the map.

As in M21, a run either happened, with its log and parsed result on disk, or
the broker refused it and said why. A compile error, a failed check, or a bus
timeout is a recorded run with ``succeeded=False``, never an exception. This
module never imports VeriTriage.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from nirmaan.integrations.eda import Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import Diagnostic, EdaResult
from nirmaan.models import RegisterMap, list_values
from nirmaan.regmap import load_map, lower, validate

#: The harness sources and the HAL header every driver includes.
HARNESS = Path(__file__).parent / "firmware_harness"

#: A warning is an error: the driver goes to review warning-free or not at all.
STRICT_FLAGS = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic")

#: The class name Verilator gives the model, so the harness names no design.
MODEL = "Vdut"

_C_SUFFIXES = (".c",)
_HEADER_SUFFIXES = (".h",)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _first(diags: list[Diagnostic]) -> str:
    if not diags:
        return ""
    d = diags[0]
    where = f"{d.where}: " if d.where else ""
    code = f"[{d.code}] " if d.code else ""
    return f"; first: {where}{code}{d.message}"


# --- Parsing: C compiler output (GCC and Clang) ----------------------------------------------

# bad.c:3:9: error: unused variable 'unused' [-Werror,-Wunused-variable]      (Clang)
# drv.c:12:14: error: comparison of ... [-Werror=sign-compare]                 (GCC)
# inc.c:1:10: fatal error: nothere.h: No such file or directory
_C_DIAG_RE = re.compile(
    r"^(?P<file>[^\s:][^:]*?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<sev>fatal error|error|warning|note):\s*(?P<msg>.*?)(?:\s+\[(?P<flag>-W[^\]]*)\])?$"
)
_LINK_RE = re.compile(r"undefined reference to|Undefined symbols|^collect2: error:|^\S*ld: error:")
_VERILATOR_ERROR_RE = re.compile(
    r"^%Error(?:-(?P<code>[A-Z0-9_]+))?:\s*(?:(?P<file>[^\s:]+):(?P<line>\d+):(?:\d+:)?\s*)?(?P<msg>.*)$"
)
_VERILATOR_NOISE = ("Exiting due to", "Command Failed")


def _code(flag: str | None) -> str:
    """The warning a diagnostic came from: ``-Werror,-Wfoo`` and ``-Werror=foo`` both give ``-Wfoo``."""
    if not flag:
        return ""
    last = flag.split(",")[-1]
    return "-W" + last.removeprefix("-Werror=") if last.startswith("-Werror=") else last


def _c_diagnostics(log: str) -> list[Diagnostic]:
    found = []
    for raw in log.splitlines():
        line = raw.strip()
        if not line or line.startswith("$ "):  # the runner's own command echo
            continue
        if m := _C_DIAG_RE.match(line):
            if m["sev"] == "note":
                continue
            sev = "warning" if m["sev"] == "warning" else "error"
            found.append(Diagnostic(sev, m["msg"].strip(), _code(m["flag"]), m["file"], int(m["line"]),
                                    int(m["col"]) if m["col"] else None))
        elif _LINK_RE.search(line):
            found.append(Diagnostic("error", line, "link"))
    return found


def _compiler_runs(log: str) -> int:
    return sum(1 for line in log.splitlines() if line.startswith("$ "))


def parse_c_build(log: str, returncodes: tuple[int, ...]) -> EdaResult:
    """Clean means every compiler run exited 0 and printed no error and no warning."""
    diags = _c_diagnostics(log)
    errors = [d for d in diags if d.severity == "error"]
    warnings = [d for d in diags if d.severity == "warning"]
    runs = _compiler_runs(log)
    status = returncodes[-1] if returncodes else -1
    passed = bool(returncodes) and all(c == 0 for c in returncodes) and runs > 0 and not diags
    if passed:
        summary = f"built clean: {_plural(runs, 'compiler run')}, 0 errors, 0 warnings"
    elif runs == 0:
        summary = "build failed: no C sources or headers to compile"
    else:
        summary = (f"build failed: {_plural(len(errors), 'error')}, {_plural(len(warnings), 'warning')}"
                   f"{_first(errors or warnings)}")
        if not diags:
            summary += f" (exit status {status})"
    return EdaResult(passed, summary, tuple(diags),
                     {"errors": len(errors), "warnings": len(warnings), "compiled": runs,
                      "exit_statuses": list(returncodes)})


# --- Parsing: the co-simulation -------------------------------------------------------------

_CHECK_RE = re.compile(r"^FWTEST (?P<verdict>PASS|FAIL) (?P<name>\S+?)(?::\s*(?P<detail>.*))?$")
_SUMMARY_RE = re.compile(r"^FWTEST SUMMARY (?P<passed>\d+) passed, (?P<failed>\d+) failed, (?P<cycles>\d+) cycles$")


def parse_fw_test(log: str, returncodes: tuple[int, ...], what: str = "co-simulation") -> EdaResult:
    """Pass means the build and the run exited 0, the harness finished, and every check passed.

    At least one check must have passed: tests that report nothing prove nothing.
    ``what`` names the run in the summary (M27's SoC run shares this parser).
    """
    checks: list[dict[str, object]] = []
    harness: list[Diagnostic] = []
    build: list[Diagnostic] = []
    transfers = 0
    cycles: int | None = None
    finished = False
    for raw in log.splitlines():
        line = raw.strip()
        if not line or line.startswith("$ "):
            continue
        if line.startswith("FWTEST BUS "):
            transfers += 1
        elif m := _CHECK_RE.match(line):
            ok = m["verdict"] == "PASS"
            checks.append({"name": m["name"], "passed": ok, "detail": (m["detail"] or "").strip()})
            if not ok:
                harness.append(Diagnostic("error", (m["detail"] or "check failed").strip(), m["name"]))
        elif line.startswith("FWTEST ERROR "):
            harness.append(Diagnostic("error", line.removeprefix("FWTEST ERROR ").strip(), "harness"))
        elif m := _SUMMARY_RE.match(line):
            finished, cycles = True, int(m["cycles"])
        elif m := _VERILATOR_ERROR_RE.match(line):
            if not m["msg"].startswith(_VERILATOR_NOISE):
                build.append(Diagnostic("error", m["msg"].strip(), m["code"] or "", m["file"] or "",
                                        int(m["line"]) if m["line"] else None))
        elif (m := _C_DIAG_RE.match(line)) and m["sev"] in ("error", "fatal error"):
            build.append(Diagnostic("error", m["msg"].strip(), _code(m["flag"]), m["file"], int(m["line"]),
                                    int(m["col"]) if m["col"] else None))
        elif _LINK_RE.search(line):
            build.append(Diagnostic("error", line, "link"))
    passed_checks = sum(1 for c in checks if c["passed"])
    failed_checks = len(checks) - passed_checks
    ran = bool(checks or harness or finished)
    status = returncodes[-1] if returncodes else -1
    exited_clean = bool(returncodes) and all(c == 0 for c in returncodes)
    passed = exited_clean and finished and passed_checks > 0 and not failed_checks and not harness and not build
    if passed:
        summary = (f"{what} passed: {_plural(passed_checks, 'check')}, 0 failed "
                   f"({cycles} cycles, {_plural(transfers, 'bus transfer')})")
    elif not ran:
        summary = f"build failed before {what}: {_plural(len(build), 'error')}{_first(build)}"
        if not build:
            summary += f" (exit status {status})"
    elif failed_checks:
        first = next(c for c in checks if not c["passed"])
        summary = (f"{what} failed: {failed_checks} of {_plural(len(checks), 'check')} failed; "
                   f"first: {first['name']}: {first['detail'] or 'check failed'}")
    elif harness:
        summary = f"{what} failed: {harness[0].message}"
    elif not finished:
        summary = f"{what} did not finish: the harness printed no summary"
    else:
        summary = f"{what} failed (exit status {status})"
    return EdaResult(passed, summary, tuple(build + harness),
                     {"checks": checks, "passed": passed_checks, "failed": failed_checks, "cycles": cycles,
                      "bus_transfers": transfers, "exit_statuses": list(returncodes)})


# --- The backends ----------------------------------------------------------------------------


def _split(paths: tuple[str, ...]) -> tuple[list[str], list[str]]:
    return ([p for p in paths if p.endswith(_C_SUFFIXES)], [p for p in paths if p.endswith(_HEADER_SUFFIXES)])


def _includes(paths: tuple[str, ...], hal: Path) -> list[str]:
    """The sources' own directories, then the directory that holds ``nirmaan_hal.h``."""
    dirs = dict.fromkeys(str(Path(p).parent) for p in paths)
    return [f"-I{d}" for d in (*dirs, str(hal))]


def _compile(compiler: str, extra: tuple[str, ...], sources: tuple[str, ...], hal: Path, out: Path,
             headers: bool, include: tuple[str, ...] = ()) -> tuple[list[list[str]], list[str]]:
    """The strict compile steps, and the objects they write. ``include`` is searched after the sources' directories."""
    c_files, h_files = _split(sources)
    includes = _includes(sources, hal)
    flags = [compiler, *STRICT_FLAGS, *extra, *includes[:-1], *(f"-I{d}" for d in include), includes[-1]]
    out.mkdir(parents=True, exist_ok=True)
    steps = []
    for i, header in enumerate(h_files if headers else ()):
        # A file that includes only this header: it must compile on its own. The declaration
        # keeps a macro-only header from being an empty translation unit, which -pedantic rejects.
        alone = out / f"header_{i}_{Path(header).stem}.c"
        alone.write_text(f'#include "{header}"\ntypedef int nirmaan_header_check;\n', encoding="utf-8")
        steps.append([*flags, "-fsyntax-only", str(alone)])
    objects = [str(out / f"{i}_{Path(c).stem}.o") for i, c in enumerate(c_files)]
    steps += [[*flags, "-c", c, "-o", o] for c, o in zip(c_files, objects)]
    return steps, objects


# --- The register map in the firmware build (M41) ---------------------------------------------

_MACRO_RE = re.compile(r"^#define (\w+) (0x[0-9A-F]+u|\d+u)$", re.MULTILINE)


def _map_path(job: Job) -> str:
    return job.params.get("map", "").strip()


def _job_map(job: Job) -> RegisterMap | None:
    return load_map(_map_path(job)) if _map_path(job) else None


def map_problem(job: Job) -> str | None:
    """Why the ``map`` parameter cannot be used (a recorded failed run), or None."""
    if not _map_path(job):
        return None
    try:
        regmap = load_map(_map_path(job))
    except (OSError, ValueError) as exc:
        return f"cannot read the register map {_map_path(job)}: {type(exc).__name__}: {exc}".splitlines()[0]
    problems = validate(regmap)
    return f"the register map has problems: {'; '.join(problems)}" if problems else None


def agreement_unit(regmap: RegisterMap, header: str) -> str:
    """C that includes ``header`` as the driver does and fails to compile where it disagrees with the map.

    Every register's offset macro must be defined; every other numeric macro of the
    generated header (count, resets, field shifts, masks, and resets) must have the
    map's value wherever the driver's header defines it.
    """
    lines = [f"/* Generated by IP Nirmaan: {header} must agree with the register map of {regmap.block}. */",
             f'#include "{header}"']
    for name, value in _MACRO_RE.findall(lower(regmap, "c-header")):
        if name.endswith("_OFFSET"):
            lines += [f"#ifndef {name}", f'#error "{header} does not define {name} (the register map: {value})"',
                      f"#elif ({name}) != {value}",
                      f'#error "{name} disagrees with the register map: it should be {value}"', "#endif"]
        else:
            lines += [f"#if defined({name}) && ({name}) != {value}",
                      f'#error "{name} disagrees with the register map: it should be {value}"', "#endif"]
    return "\n".join([*lines, "typedef int nirmaan_regmap_agreement;", ""])


def register_map_sources(job: Job) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """With a ``map``: the agreement unit to compile, and the directory holding the generated header."""
    regmap = _job_map(job)
    if regmap is None:
        return (), ()
    header = f"{regmap.block}_map.h"
    generated = job.workdir / "regmap"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / header).write_text(lower(regmap, "c-header"), encoding="utf-8")
    agree = job.workdir / "regmap_agree" / "regmap_agree.c"
    agree.parent.mkdir(parents=True, exist_ok=True)
    agree.write_text(agreement_unit(regmap, header), encoding="utf-8")
    return (str(agree),), (str(generated),)


def build_steps(compiler: str, *extra: str):
    """``fw.build`` steps for one compiler: headers checked alone, then each C file compiled."""
    def steps(job: Job) -> list[list[str]]:
        added, include = register_map_sources(job)
        return _compile(compiler, extra, (*job.sources, *added), HARNESS, job.workdir / "obj", headers=True,
                        include=include)[0]

    return steps


def _parse_build(run: RunRecord) -> EdaResult:
    return parse_c_build(run.log, run.returncodes)


def copy_rtl(job: Job) -> list[str]:
    """The ``rtl`` files, copied byte for byte into the working directory (make cannot take a space)."""
    rtl = []
    for i, given in enumerate(list_values(job.params["rtl"])):
        source = Path(given).resolve()
        if not source.is_file():  # Verilator reports it, and the run is recorded as failed
            rtl.append(str(source))
            continue
        copy = job.workdir / "rtl" / str(i) / source.name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, copy)
        rtl.append(str(copy))
    return rtl


# --- The host co-simulation's bus managers (M41) -----------------------------------------------

#: Bus name to the manager source that implements ``nirmaan_hal`` over that bus on the model.
_COSIM_BUSES: dict[str, Path] = {}
#: The bus when neither the ``bus`` parameter nor a ``map`` names one (every M25 call).
DEFAULT_BUS = "axi4-lite"


def register_cosim_bus(bus: str, manager: Path) -> Path:
    if bus in _COSIM_BUSES and _COSIM_BUSES[bus] != Path(manager):
        raise ValueError(f"the host co-simulation already has a manager for {bus!r}")
    _COSIM_BUSES[bus] = Path(manager)
    return Path(manager)


def unregister_cosim_bus(bus: str) -> None:
    _COSIM_BUSES.pop(bus, None)


def cosim_buses() -> dict[str, Path]:
    return dict(_COSIM_BUSES)


def cosim_bus(job: Job) -> tuple[str, str | None]:
    """The bus the run drives (the ``bus`` parameter, else the map's, else the default), and why it cannot."""
    given = job.params.get("bus", "").strip()
    regmap = _job_map(job) if not map_problem(job) else None
    if given and regmap and given != regmap.bus:
        return given, f"bus {given} contradicts the register map, whose bus is {regmap.bus}; nothing was simulated"
    bus = given or (regmap.bus if regmap else DEFAULT_BUS)
    if bus not in _COSIM_BUSES:
        return bus, (f"no host co-simulation harness for a {bus} bus (the host harness drives "
                     f"{', '.join(sorted(_COSIM_BUSES))}; fw.soc_test reaches other buses through a RISC-V core); "
                     "nothing was simulated")
    return bus, None


def _cosim_check(job: Job) -> str | None:
    return map_problem(job) or cosim_bus(job)[1]


def _cosim_steps(job: Job) -> list[list[str]]:
    """Compile the driver and its tests, build the model with the harness, and run it.

    Verilator's ``--build`` drives make, which cannot handle a space in a path,
    so the harness and the RTL are copied, byte for byte, into the working
    directory first. The run records the paths it was given.
    """
    harness = job.workdir / "harness"
    shutil.copytree(HARNESS, harness, dirs_exist_ok=True)
    manager = _COSIM_BUSES[cosim_bus(job)[0]]
    shutil.copyfile(manager, harness / manager.name)  # a registered manager may live outside HARNESS
    rtl = copy_rtl(job)
    added, include = register_map_sources(job)
    steps, objects = _compile("cc", (), (*job.sources, *added), harness, job.workdir / "cobj", headers=False,
                              include=include)
    model = job.workdir / "cosim"
    steps.append(["verilator", "--cc", "--exe", "--build", "-j", "0", "-Wno-fatal", "--prefix", MODEL,
                  "-Mdir", str(model), *job.top_args("--top-module"), *rtl, str(harness / manager.name),
                  *objects, "-CFLAGS", f"-I{harness}"])
    steps.append([str(model / MODEL)])
    return steps


def _parse_cosim(run: RunRecord) -> EdaResult:
    return parse_fw_test(run.log, run.returncodes)


register_cosim_bus("axi4-lite", HARNESS / "axil_manager.cpp")
register_cosim_bus("apb", HARNESS / "apb_manager.cpp")

register_backend(Backend("host-cc", "fw.build", ("cc",), build_steps("cc"), _parse_build, files=("map",),
                         check=map_problem))
register_backend(Backend("riscv-gcc", "fw.build", ("riscv64-unknown-elf-gcc",),
                         build_steps("riscv64-unknown-elf-gcc", "-march=rv32imac_zicsr", "-mabi=ilp32",
                                     "-ffreestanding"), _parse_build, files=("map",), check=map_problem))
register_backend(Backend("verilator-cosim", "fw.test", ("cc", "verilator", "make"), _cosim_steps, _parse_cosim,
                         ("sources", "rtl"), files=("map",), check=_cosim_check))
