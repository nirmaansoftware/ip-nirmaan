"""The object screen: a tripwire on the C a seat writes, before a whole-flow check links it (G3, gate WF16).

Council record ``council/records/2026-11-17-g3-whole-flow-cases.md``, second addendum (2026-11-18), decision 2,
items 2 to 5. In a whole-flow register block trial the model writes the driver and the driver test, and checks 4
to 7 build them, or link them into one image with the host harness and Verilator's runtime (``fw.build``,
``fw.test``). Before such a check runs, this screen compiles every C file of the check exactly as ``fw.test``
does (``firmware._compile``: the host ``cc``, ``STRICT_FLAGS``, the same include path) into objects of
its own, and refuses the check when any of these holds:

* ``undefined``: an object leaves a symbol undefined that is not on ``ALLOWED`` and is not defined by another
  object of the same check, however it was declared (a plain name, an asm label, a weak reference, a mangled
  C++ name). ``ALLOWED`` is the harness's own functions and the C library names that the committed fixtures,
  reference answers and held-out tests leave undefined, from the recorded CI run in
  ``evals/flow/object_screen_record.json``;
* ``collision``: an object defines a global that the harness or the C library defines, a reserved name (``__``
  or ``_`` and a capital, which covers every mangled C++ name), or a global another object of the check
  defines too;
* ``before-main`` / ``after-main``: an object carries code that runs outside the tests: a constructor or
  anything placed in ``.init_array``, ``.preinit_array``, ``.ctors`` or ``.init`` (before ``main``, so before
  the run's nonce is taken), an indirect function (its resolver runs while the image loads), or a destructor
  (``.fini_array``, ``.dtors``, ``.fini``);
* ``asm``: a line of the preprocessed source that comes from one of the seat's own files holds ``asm``,
  ``__asm`` or ``__asm__`` (by the preprocessor's line markers, so a macro that expands to asm in the seat's
  line is caught and the C library's own headers are not);
* ``build``: the screen could not build or read the objects. It never lets through C it could not inspect.

A hit is the check's verdict, decided in advance: the check fails with the reasons, and nothing is linked or run.
It is never a removed or repeated trial.

What it is: a TRIPWIRE. It stops reach by name. It is not confinement, and it does not stop address arithmetic
from an allowed pointer (``hal->read32`` is an address in the harness's own code, and the harness's counters and
the run's nonce sit in the same image), a memory scan, what the allowed C library calls can do, a system call
made through an allowed function, or anything the account the run executes as may do. ``docs/GATE_INTEGRITY.md``
(section 3) states this, with the recorded probes that show it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from nirmaan.integrations import firmware
from nirmaan.integrations.eda import run_environment

#: The first words of every refusal's summary: a verdict of the screen, distinct from a failed test.
REFUSED = "refused by the object screen"

#: The functions the host harness defines for a driver test (``nirmaan_hal.h``, ``nirmaan_irq.h``).
HARNESS_CALLS = frozenset({
    "nirmaan_bus_fault_attach", "nirmaan_bus_fault_count", "nirmaan_irq_attach", "nirmaan_irq_count",
    "nirmaan_irq_wait", "nirmaan_test_result",
})

#: The C library names the committed fixtures, reference answers and held-out tests leave undefined, compiled
#: by ``fw.test``'s own compile on the CI toolchain (ubuntu-24.04): ``evals/flow/object_screen_record.json``.
LIBRARY_CALLS = frozenset({"__stack_chk_fail", "snprintf"})

#: Every name a seat's object may leave undefined, beyond what another object of the same check defines.
ALLOWED = HARNESS_CALLS | LIBRARY_CALLS

#: Names the harness image defines that no seat object may define: the harness's functions and ``main``.
HARNESS_DEFINES = HARNESS_CALLS | {"main"}

#: The C library names the harness reports through, refused as a definition where the C library's own export
#: list cannot be read (a host without ``libc.so.6``).
LIBRARY_DEFINES = frozenset({
    "_exit", "abort", "atexit", "calloc", "exit", "fflush", "fprintf", "fputc", "fputs", "free", "fwrite",
    "malloc", "memcpy", "memset", "printf", "putc", "putchar", "puts", "realloc", "snprintf", "sprintf",
    "strlen", "strncmp", "vfprintf", "vprintf", "vsnprintf", "write",
})

#: Sections whose code runs before ``main`` (and so before the harness takes the run's nonce out of argv), or
#: after the tests: ELF names and their relocation sections, and the Mach-O names.
_BEFORE_MAIN = re.compile(r"^(\.rela?)?\.(init_array|preinit_array|ctors|init)(\..*)?$"
                          r"|^__(mod_init_func|init_offsets)$")
_AFTER_MAIN = re.compile(r"^(\.rela?)?\.(fini_array|dtors|fini)(\..*)?$|^__mod_term_func$")
_ASM = re.compile(r"\b(?:asm|__asm|__asm__)\b")
_LITERAL = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
_MARKER = re.compile(r'^#(?:line)?\s*(\d+)\s+"((?:\\.|[^"\\])*)"')
_RESERVED = re.compile(r"^(?:__|_[A-Z])")
_TIMEOUT = 120
_TOOLS = ("cc", "nm", "objdump")


@dataclass(frozen=True)
class Hit:
    """One reason the screen refuses: the rule, the file it was found in, and what was found."""

    rule: str
    file: str
    detail: str

    def text(self) -> str:
        return f"{self.file}: {self.rule}: {self.detail}"


@dataclass(frozen=True)
class Symbols:
    """What one object leaves undefined and defines (global names only), and its section names."""

    undefined: frozenset[str]
    weak_undefined: frozenset[str]
    defined: frozenset[str]
    indirect: frozenset[str]
    sections: tuple[str, ...]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT,
                          stdin=subprocess.DEVNULL, env=run_environment(cwd))


def _mach_o(sections_text: str) -> bool:
    return "mach-o" in sections_text.lower()


def read_object(obj: Path, cwd: Path) -> Symbols:
    """The global symbols and section names of one object, read with ``nm -P`` and ``objdump -h``."""
    head = _run(["objdump", "-h", str(obj)], cwd)
    if head.returncode != 0:
        raise OSError(f"objdump -h failed: {(head.stderr or head.stdout).strip()[:200]}")
    sections = tuple(m[1] for m in re.finditer(r"^\s*\d+\s+(\S+)\s+[0-9a-fA-F]+\s", head.stdout, re.M))
    table = _run(["nm", "-P", str(obj)], cwd)
    if table.returncode != 0:
        raise OSError(f"nm -P failed: {(table.stderr or table.stdout).strip()[:200]}")
    strip = _mach_o(head.stdout)  # a Mach-O C name carries one leading underscore
    undefined, weak, defined, indirect = set(), set(), set(), set()
    for line in table.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0].endswith(":"):
            continue
        name, kind = parts[0], parts[1]
        if strip and name.startswith("_"):
            name = name[1:]
        if kind == "U":
            undefined.add(name)
        elif kind in ("w", "v"):  # weak and not defined here: the link resolves it, or leaves it null
            weak.add(name)
        elif kind == "i":
            indirect.add(name)
        elif kind.isupper():  # a global definition (T, D, B, R, C, W, V, S, ...)
            defined.add(name)
    return Symbols(frozenset(undefined), frozenset(weak), frozenset(defined), frozenset(indirect), sections)


def library_names() -> frozenset[str]:
    """The names the C library and the maths library export, read from the host's shared objects with
    ``nm -D``; ``LIBRARY_DEFINES`` where they cannot be read."""
    names: set[str] = set()
    for lib in ("libc.so.6", "libm.so.6"):
        try:
            found = subprocess.run(["cc", f"-print-file-name={lib}"], capture_output=True, text=True,
                                   timeout=_TIMEOUT, stdin=subprocess.DEVNULL).stdout.strip()
            if not found or not Path(found).is_file():
                continue
            table = subprocess.run(["nm", "-D", "--defined-only", found], capture_output=True, text=True,
                                   timeout=_TIMEOUT, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            continue
        names |= {ln.split()[-1].split("@")[0] for ln in table.stdout.splitlines() if ln.split()}
    return frozenset(names) | LIBRARY_DEFINES


def asm_lines(preprocessed: str, seat: set[Path]) -> list[int]:
    """The line numbers, in the seat's own files, of preprocessed lines that hold asm."""
    hits: list[int] = []
    current: Path | None = None
    line = 0
    for text in preprocessed.splitlines():
        marker = _MARKER.match(text)
        if marker:
            line = int(marker[1])
            name = marker[2]
            current = None if name.startswith("<") else Path(name.encode().decode("unicode_escape")).resolve()
            continue
        if current is not None and current in seat and _ASM.search(_LITERAL.sub('""', text)):
            hits.append(line)
        line += 1
    return hits


def screen(sources: list[Path], seat: set[Path], work: Path, include: tuple[str, ...] = (),
           allowed: frozenset[str] = ALLOWED) -> list[Hit]:
    """Every reason to refuse the C of one check. Empty: the check may build and run.

    ``sources`` are the check's ``sources`` as ``fw.test`` gets them (the seat's files and the case's, C files and
    headers); ``seat`` the resolved paths of those the seat wrote. Every C file is compiled and read, the judge's
    own too, since a seat header can put code into a held-out test's object.
    """
    missing = [tool for tool in _TOOLS if shutil.which(tool) is None]
    if missing:
        return [Hit("build", "-", f"the screen's tools are not on PATH: {', '.join(missing)}; nothing was inspected")]
    work.mkdir(parents=True, exist_ok=True)
    sources = [Path(p).resolve() for p in sources]  # the steps run in ``work``
    include = tuple(str(Path(d).resolve()) for d in include)
    steps, objects = firmware._compile("cc", (), tuple(str(p) for p in sources), firmware.HARNESS, work / "obj",
                                       headers=False, include=include)
    c_files = [Path(p) for p in firmware._split(tuple(str(p) for p in sources))[0]]
    seat_paths = {p.resolve() for p in seat}
    hits: list[Hit] = []
    tables: dict[str, Symbols] = {}
    for n, (step, obj, source) in enumerate(zip(steps, objects, c_files)):
        alone = [c.name for c in c_files].count(source.name) == 1
        label = source.name if alone else f"{source.name} (input {n + 1})"
        compiled = _run(step, work)
        if compiled.returncode != 0:
            first = next((ln for ln in (compiled.stderr or compiled.stdout).splitlines() if ln.strip()), "")
            hits.append(Hit("build", source.name, f"cc failed, so nothing could be inspected: {first[:200]}"))
            continue
        pre = _run([a for a in step if a not in ("-c", "-o", obj)] + ["-E"], work)
        if pre.returncode != 0:
            hits.append(Hit("build", source.name, "the preprocessor failed, so the asm check could not run"))
        else:
            lines = asm_lines(pre.stdout, seat_paths)
            if lines:
                hits.append(Hit("asm", source.name, f"asm in the seat's own lines (preprocessed line "
                                                    f"{', '.join(map(str, lines[:5]))})"))
        try:
            tables[label] = read_object(Path(obj), work)  # keyed so two files of one name never merge
        except (OSError, subprocess.TimeoutExpired) as exc:
            hits.append(Hit("build", source.name, f"the object could not be read: {exc}"))
    if not tables:
        return hits
    library = library_names()
    owners: dict[str, list[str]] = {}
    for name, table in tables.items():
        for symbol in table.defined | table.indirect:
            owners.setdefault(symbol, []).append(name)
    defined_here = set(owners)
    for name, table in tables.items():
        off = sorted((table.undefined | table.weak_undefined) - allowed - defined_here)
        if off:
            weak = [s for s in off if s in table.weak_undefined]
            hits.append(Hit("undefined", name, f"undefined symbols not on the allow list: {', '.join(off)}"
                                               + (f" (weak: {', '.join(weak)})" if weak else "")))
        clash = sorted(s for s in table.defined if s in HARNESS_DEFINES or s in library or _RESERVED.match(s)
                       or len(owners.get(s, ())) > 1)
        if clash:
            hits.append(Hit("collision", name, f"defines a global the harness, the C library or another object "
                                               f"defines, or a reserved name: {', '.join(clash)}"))
        before = [s for s in table.sections if _BEFORE_MAIN.match(s)]
        if before or table.indirect:
            found = before + [f"indirect function {s}" for s in sorted(table.indirect)]
            hits.append(Hit("before-main", name, f"code that runs before main: {', '.join(found)}"))
        after = [s for s in table.sections if _AFTER_MAIN.match(s)]
        if after:
            hits.append(Hit("after-main", name, f"code that runs after the tests: {', '.join(after)}"))
    return hits


def summary(hits: list[Hit]) -> str:
    """A refusal's summary: what the screen is, then each reason."""
    return (f"{REFUSED} (a tripwire: it stops reach by name; it is not confinement); nothing was linked or run: "
            + "; ".join(h.text() for h in hits))
