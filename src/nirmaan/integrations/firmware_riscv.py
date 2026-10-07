"""The driver on a RISC-V core: a bare-metal RV32I image, run on PicoRV32 against the real RTL (M27).

Two tools register through M21's :func:`register_backend`, so the broker, the
engine, and the policy do not change:

* ``fw.cross_build`` compiles the driver and its tests under the strict flags
  for bare-metal RV32I, links them with the SoC runtime in ``firmware_soc/``
  (``crt0.S``, ``link.ld``, the HAL, a small libc) into an ELF, and reports
  its code size.
* ``fw.soc_test`` builds the same image, then a Verilator model of
  ``firmware_soc/nirmaan_soc.v``: a RISC-V core with RAM and the approved RTL
  behind a bridge for its bus. The driver's register accesses are the CPU's
  own loads and stores, and every one is a real bus transfer on the design.

M29 (docs/RISCV_NEXT.md) makes the core and the bus data. ``core=`` picks one
of :data:`CORES` (PicoRV32 or SERV, both vendored unmodified, ISC; a new one
is a :func:`register_core` call), and the design's ports pick one of
:data:`BUSES` (AXI4-Lite or APB). A design with an ``irq`` output has it
wired to the core's interrupt input. ``text_bytes`` is reported for M26's
generic ``max_text_bytes`` limit.

A run either happened, with its log and parsed result on disk, or the broker
refused it and said why. A compile or link error, a failed check, a CPU trap,
or a bus timeout is a recorded run with ``succeeded=False``, never an
exception. This module never imports VeriTriage.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from nirmaan.integrations.eda import Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import Diagnostic, EdaResult
from nirmaan.integrations.firmware import (
    HARNESS,
    STRICT_FLAGS,
    _c_diagnostics,
    _compile,
    _first,
    _plural,
    copy_rtl,
    parse_fw_test,
)
from nirmaan.models import list_values

#: The SoC: the core, the bridge, the clock, and the firmware runtime.
SOC = Path(__file__).parent / "firmware_soc"

#: RISC-V GCC as Ubuntu (``gcc-riscv64-unknown-elf``) and Homebrew (``riscv64-elf-gcc``) name it.
RISCV_GCC = ("riscv64-unknown-elf-gcc", "riscv64-elf-gcc")

#: Bare-metal RV32I, the ISA PicoRV32 is built with here. ``-Os`` for size; the last flag keeps GCC
#: from turning the libc's own loops into calls to themselves.
ARCH_FLAGS = ("-march=rv32i", "-mabi=ilp32")
TARGET_FLAGS = (*ARCH_FLAGS, "-ffreestanding", "-Os", "-fno-tree-loop-distribute-patterns")
LINK_FLAGS = ("-nostdlib", "-nostartfiles", "-Wl,--no-warn-rwx-segments")

#: The runtime linked into every image: the HAL and reporting, and the libc.
RUNTIME = ("soc_runtime.c", "libc/nirmaan_libc.c")

#: The class name Verilator gives the SoC model.
MODEL = "Vsoc"


@dataclass(frozen=True)
class Core:
    """A RISC-V core the SoC can run, as data (docs/RISCV_NEXT.md, section 4).

    ``module`` is its wrapper, which presents the SoC's memory interface, a
    ``trap`` output, and an ``irq`` input; ``verilog`` is the wrapper's file
    first, then the core's own. ``runtime`` is the assembly file that defines
    ``nirmaan_core_init``, ``nirmaan_core_irq_set``, and ``nirmaan_core_trap``
    (entered from the vector at 0x10), assembled with ``-march=<march>``.
    """

    name: str
    module: str
    verilog: tuple[Path, ...]
    runtime: Path
    march: str = "rv32i"


#: SERV 1.4.0's ``rtl/``, as ``serv_rf_top`` uses it (``firmware_soc/serv/``, unmodified).
SERV_FILES = ("serv_rf_top.v", "serv_rf_ram_if.v", "serv_rf_ram.v", "serv_top.v", "serv_state.v",
              "serv_decode.v", "serv_immdec.v", "serv_bufreg.v", "serv_bufreg2.v", "serv_ctrl.v", "serv_alu.v",
              "serv_rf_if.v", "serv_mem_if.v", "serv_csr.v", "serv_compdec.v", "serv_aligner.v", "serv_debug.v")

#: The cores ``core=`` can name; the first is the default.
CORES: dict[str, Core] = {}


def register_core(core: Core) -> Core:
    """Add a core the SoC can run. Nothing else changes: the SoC and the backends read this registry."""
    if core.name in CORES:
        raise ValueError(f"a core named {core.name!r} is already registered")
    CORES[core.name] = core
    return core


def unregister_core(name: str) -> None:
    CORES.pop(name, None)


register_core(Core("picorv32", "nirmaan_core_picorv32", (SOC / "core_picorv32.v", SOC / "picorv32.v"),
                   SOC / "irq_picorv32.S"))
register_core(Core("serv", "nirmaan_core_serv", (SOC / "core_serv.v", *(SOC / "serv" / f for f in SERV_FILES)),
                   SOC / "irq_serv.S", "rv32i_zicsr"))


@dataclass(frozen=True)
class Bus:
    """A bus the SoC can bridge to, recognized by the ports a design's top module declares."""

    name: str
    module: str
    verilog: Path
    ports: tuple[str, ...]


#: The buses the SoC bridges to, tried in order.
BUSES: dict[str, Bus] = {}


def register_bus(bus: Bus) -> Bus:
    if bus.name in BUSES:
        raise ValueError(f"a bus named {bus.name!r} is already registered")
    BUSES[bus.name] = bus
    return bus


def unregister_bus(name: str) -> None:
    BUSES.pop(name, None)


register_bus(Bus("axi4-lite", "nirmaan_bridge_axil", SOC / "bridge_axil.v", ("s_axil_awaddr", "s_axil_araddr")))
register_bus(Bus("apb", "nirmaan_bridge_apb", SOC / "bridge_apb.v", ("psel", "penable", "paddr")))

#: The port that carries a design's interrupt to the core (active high, level sensitive).
IRQ_PORT = "irq"


def toolchain() -> str | None:
    """The prefix of the first RISC-V GCC on PATH whose objcopy and size are there too, or None."""
    for gcc in RISCV_GCC:
        prefix = gcc.removesuffix("gcc")
        if all(shutil.which(prefix + t) for t in ("gcc", "objcopy", "size")):
            return prefix
    return None


def _needs_toolchain(params: dict[str, str]) -> str | None:
    if toolchain():
        return None
    return f"no RISC-V GCC on PATH ({' or '.join(RISCV_GCC)}, with its objcopy and size)"


# --- Parsing ---------------------------------------------------------------------------------

#    text	   data	    bss	    dec	    hex	filename
#    9332	      4	    168	   9504	   2520	rv32/firmware.elf
_SIZE_RE = re.compile(r"^\s*(?P<text>\d+)\s+(?P<data>\d+)\s+(?P<bss>\d+)\s+\d+\s+[0-9a-fA-F]+\s+\S")
_LD_WARNING_RE = re.compile(r"^\S*ld(?:\.\w+)?: warning: (?P<msg>.*)$")


def _size(log: str) -> dict[str, int]:
    for line in log.splitlines():
        if m := _SIZE_RE.match(line):
            text, data, bss = int(m["text"]), int(m["data"]), int(m["bss"])
            # text_bytes is text under the name the max_text_bytes limit reads (M29).
            return {"text": text, "data": data, "bss": bss, "image_bytes": text + data, "text_bytes": text}
    return {}


def _compiles(log: str) -> int:
    """Compiler runs: the steps the runner echoed that compile one file with ``-c`` (C files and crt0)."""
    return sum(1 for line in log.splitlines() if line.startswith("$ ") and " -c " in line)


def parse_cross_build(log: str, returncodes: tuple[int, ...]) -> EdaResult:
    """Clean means every step exited 0, nothing warned, and ``size`` measured the linked ELF."""
    diags = _c_diagnostics(log)
    diags += [Diagnostic("warning", m["msg"].strip(), "link") for line in log.splitlines()
              if (m := _LD_WARNING_RE.match(line.strip()))]
    errors = [d for d in diags if d.severity == "error"]
    warnings = [d for d in diags if d.severity == "warning"]
    size = _size(log)
    compiled = _compiles(log)
    exited_clean = bool(returncodes) and all(c == 0 for c in returncodes)
    passed = exited_clean and not diags and bool(size) and compiled > 0
    counts = f"{_plural(compiled, 'compiler run')}, {_plural(len(errors), 'error')}, {_plural(len(warnings), 'warning')}"
    if passed:
        summary = (f"cross-built clean for RV32I: {counts}; "
                   f"firmware.elf text {size['text']}, data {size['data']}, bss {size['bss']} bytes")
    else:
        summary = f"cross build failed: {counts}{_first(errors or warnings)}"
        if not diags:
            status = returncodes[-1] if returncodes else -1
            summary += f" (exit status {status})" if not exited_clean else " (no image was measured)"
    return EdaResult(passed, summary, tuple(diags),
                     {**size, "compiled": compiled, "errors": len(errors), "warnings": len(warnings),
                      "exit_statuses": list(returncodes)})


def parse_soc_test(log: str, returncodes: tuple[int, ...]) -> EdaResult:
    """The fw.test verdict (every check passed, the firmware finished), plus the image's code size."""
    result = parse_fw_test(log, returncodes, what="SoC run")
    size = _size(log)
    summary = result.summary
    if result.passed and size:
        summary += f"; image text {size['text']}, data {size['data']}, bss {size['bss']} bytes"
    return EdaResult(result.passed, summary, result.diagnostics, {**result.metrics, **size})


# --- The steps -------------------------------------------------------------------------------


def _core(job: Job) -> Core | None:
    return CORES.get(job.params.get("core") or next(iter(CORES)))


def _core_check(job: Job) -> str | None:
    if _core(job):
        return None
    return f"unknown core {job.params['core']!r}; known cores: {', '.join(CORES)}"


def _image_steps(job: Job, soc: Path, out: Path, runtime: Path, march: str) -> list[list[str]]:
    """Compile the driver, its tests, and the runtime for RV32I; link them into ``out/firmware.elf``; size it.

    ``runtime`` is the core's part of the runtime (its trap entry), assembled with ``-march=<march>``.
    """
    prefix = toolchain() or RISCV_GCC[0].removesuffix("gcc")
    sources = (*job.sources, *(str(soc / r) for r in RUNTIME))
    steps, objects = _compile(prefix + "gcc", TARGET_FLAGS, sources, HARNESS, out, headers=False)
    crt0 = str(out / "crt0.o")
    core = str(out / "core.o")
    elf = str(out / "firmware.elf")
    steps.append([prefix + "gcc", *ARCH_FLAGS, "-c", str(soc / "crt0.S"), "-o", crt0])
    steps.append([prefix + "gcc", f"-march={march}", "-mabi=ilp32", "-c", str(runtime), "-o", core])
    steps.append([prefix + "gcc", *ARCH_FLAGS, *LINK_FLAGS, "-T", str(soc / "link.ld"), "-o", elf, crt0, core,
                  *objects, "-lgcc"])
    steps.append([prefix + "size", elf])
    return steps


def _cross_build_steps(job: Job) -> list[list[str]]:
    core = _core(job)
    return _image_steps(job, SOC, job.workdir / "rv32", core.runtime, core.march)


_MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_]\w*)", re.MULTILINE)


def top_module(rtl: list[str]) -> str | None:
    """The one module the RTL declares that no other module instantiates, or None if not exactly one."""
    text = "\n".join(Path(f).read_text(encoding="utf-8", errors="replace") for f in rtl if Path(f).is_file())
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.DOTALL)
    declared = list(dict.fromkeys(_MODULE_RE.findall(text)))
    bodies = re.sub(r"\bmodule\s+[A-Za-z_]\w*", "", text)
    tops = [m for m in declared if not re.search(rf"\b{m}\b\s*(?:#\s*\(|[A-Za-z_]\w*\s*\()", bodies)]
    return tops[0] if len(tops) == 1 else None


def design_ports(rtl: list[str], top: str) -> set[str]:
    """The port names in the header of module ``top``, ANSI or not, or an empty set if it is not there."""
    text = "\n".join(Path(f).read_text(encoding="utf-8", errors="replace") for f in rtl if Path(f).is_file())
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.DOTALL)
    m = re.search(rf"\bmodule\s+{re.escape(top)}\b\s*", text)
    if not m:
        return set()
    rest = text[m.end():]
    if rest.startswith("#"):  # skip the parameter list
        rest = rest[_closing(rest, rest.index("(")) + 1:].lstrip()
    if not rest.startswith("("):
        return set()
    header = re.sub(r"\[[^\]]*\]", " ", rest[1:_closing(rest, 0)])
    return {words[-1] for item in header.split(",") if (words := re.findall(r"[A-Za-z_]\w*", item))}


def _closing(text: str, start: int) -> int:
    """The index of the parenthesis that closes the one at ``start``."""
    depth = 0
    for i in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return i
    return len(text)


def bus_of(ports: set[str]) -> Bus | None:
    """The first registered bus whose identifying ports the design declares."""
    return next((b for b in BUSES.values() if set(b.ports) <= ports), None)


def _rtl_files(job: Job) -> list[str]:
    return [str(Path(s).resolve()) for s in list_values(job.params["rtl"])]


def _soc_check(job: Job) -> str | None:
    problem = _core_check(job)
    if problem:
        return problem
    top = job.top or top_module(_rtl_files(job))
    if not top:
        return "cannot tell the design's top module from the RTL; name it with top="
    if not bus_of(design_ports(_rtl_files(job), top)):
        known = "; ".join(f"{b.name} needs {', '.join(b.ports)}" for b in BUSES.values())
        return f"the design {top} has no bus the SoC knows ({known})"
    return None


def _local(path: Path, soc: Path, workdir: Path) -> str:
    """Where a SoC or core file is in the working directory: in the SoC copy, or copied beside it."""
    if path.is_relative_to(SOC):
        return str(soc / path.relative_to(SOC))
    copy = workdir / "cores" / path.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, copy)
    return str(copy)


def _soc_steps(job: Job) -> list[list[str]]:
    """Build the image for the core, then the SoC model around the core and the RTL, and run the image on it.

    Verilator's ``--build`` drives make, which cannot take a space in a path, so
    the SoC sources, the core's, and the RTL are copied, byte for byte, into the
    working directory first. The run records the paths it was given.
    """
    top = job.top or top_module(_rtl_files(job))
    ports = design_ports(_rtl_files(job), top)
    core, bus = _core(job), bus_of(ports)
    soc = job.workdir / "soc_src"
    shutil.copytree(SOC, soc, dirs_exist_ok=True)
    rtl = copy_rtl(job)
    out = job.workdir / "rv32"
    steps = _image_steps(job, soc, out, Path(_local(core.runtime, soc, job.workdir)), core.march)
    prefix = toolchain() or RISCV_GCC[0].removesuffix("gcc")
    image = str(out / "firmware.hex")
    steps.append([prefix + "objcopy", "-O", "verilog", str(out / "firmware.elf"), image])
    model = job.workdir / "soc"
    defines = [f"+define+NIRMAAN_CORE={core.module}", f"+define+NIRMAAN_BRIDGE={bus.module}",
               f"+define+NIRMAAN_DUT={top}", *(["+define+NIRMAAN_DUT_IRQ"] if IRQ_PORT in ports else [])]
    steps.append(["verilator", "--cc", "--exe", "--build", "-j", "0", "-Wno-fatal", "--prefix", MODEL,
                  "--top-module", "nirmaan_soc", "-Mdir", str(model), *defines,
                  str(soc / "nirmaan_soc.v"), _local(bus.verilog, soc, job.workdir),
                  *(_local(v, soc, job.workdir) for v in core.verilog), *rtl, str(soc / "soc_main.cpp")])
    steps.append([str(model / MODEL), f"+firmware={image}"])
    return steps


def _parse_cross(run: RunRecord) -> EdaResult:
    return parse_cross_build(run.log, run.returncodes)


def _parse_soc(run: RunRecord) -> EdaResult:
    return parse_soc_test(run.log, run.returncodes)


register_backend(Backend("rv32-gcc", "fw.cross_build", (), _cross_build_steps, _parse_cross,
                         environment=_needs_toolchain, check=_core_check))
register_backend(Backend("picorv32-verilator", "fw.soc_test", ("verilator", "make"), _soc_steps, _parse_soc,
                         ("sources", "rtl"), environment=_needs_toolchain, check=_soc_check))
