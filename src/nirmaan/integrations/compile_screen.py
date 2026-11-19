"""The compile screen: what C a job compiles may pull in, checked before anything is compiled (M91, gate SC1).

Council record ``council/records/2026-11-19-seat-c-live-refusal.md``, decision 4: seat C is compiled, assembled
and linked as the runner, so whatever the compiler or the assembler reads for it, it reads as the runner. A seat
file could include the committed reference driver or the held-out test by an absolute path or a path with ``..``,
or have the assembler copy any file the runner can read into its own program (``.incbin``). The council chose
between a screen and compiling as the seat account; this is the screen (``docs/COMPILE_SCREEN.md`` says why).

Every backend that compiles the C a job names runs it in its check, before any step (``fw.build`` on the host and
for RISC-V, ``fw.test``, ``fw.cross_build`` and ``fw.soc_test``), over the job's C files and headers, the seat's and
the case's alike, and the object screen of gate WF16 runs it before it compiles. It refuses when:

* ``directive``: a file the job compiles, or one it pulls in from the run's source folders or the run's own
  directory, uses a preprocessor directive outside ``DIRECTIVES`` (so ``#line``, a line marker such as
  ``# 1 "file"``, ``#include_next``, ``#import``, ``#embed``, ``#ident``, any ``#pragma`` but ``#pragma once``), a
  trigraph, one of ``REFUSED_NAMES``, or an ``#include`` whose written name is absolute or has a ``..`` part.
  The text is read as the preprocessor reads it: lines joined at a backslash and a newline, comments removed,
  digraphs (``%:``) counted as ``#``;
* ``outside``: a file the compiler pulls in resolves outside the run's source folders (the folder of each file
  the job names), the harness, the run's own directory (the harness copy, the header generated from a map) and
  the compiler's own include folders. The list is the compiler's own (``-M -MG``), so a name a macro builds is in
  it too;
* ``assembler``: the compiler's assembly for a C file (``-S``, compiled exactly as the build compiles it) holds
  an asm statement, inline or at file scope, however it was written (the compiler marks each one, so a macro that
  builds one is caught), or an assembler directive that reads a file or could spell one (``AS_DIRECTIVES``,
  anywhere in the text, so an asm label that carries one is caught too). An asm label that only renames a
  symbol reads no file and is not refused here; the object screen refuses it in the whole-flow checks.

A refusal is the check's reason (``eda.execute``): the run is recorded as failed with that reason, and nothing of
the job is compiled. The screen's own compiler runs write nothing the build or a log reads: their output is
parsed here and dropped.

What it is not. It is not confinement. The preprocessor that lists the files runs as the runner, so it opens what
the seat names before the list is checked; only the list (file names) is read back, and a failure there is
refused with the seat's own first error and nothing of another file. It does not stop a seat header from breaking
the compile of the held-out test it is included in, so that a diagnostic quotes the held-out test's lines, and
the program ``fw.test`` builds holds the held-out test it is linked with. ``docs/COMPILE_SCREEN.md`` lists these.
"""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

#: The first words of every refusal: a verdict of the screen, before anything was compiled.
REFUSED = "refused by the compile screen"

#: The directives a file the job compiles may use (C11's, less ``#line``), and ``#pragma once``.
DIRECTIVES = frozenset({"include", "define", "undef", "if", "ifdef", "ifndef", "elif", "else", "endif", "error",
                        "pragma"})
#: Names that test for or reach a file, or make a pragma, wherever they are used.
REFUSED_NAMES = ("__has_include_next", "__has_include", "__has_embed", "_Pragma")
#: Assembler directives that read a file (``.incbin``, ``.include``) or could spell one (the macro directives).
AS_DIRECTIVES = ("incbin", "include", "macro", "irpc", "irp", "rept", "altmacro", "purgem", "exitm", "endm",
                 "endr")

_TRIGRAPH = re.compile(r"\?\?[=(/)'<!>\-]")
_DIRECTIVE = re.compile(r"[ \t\f\v]*(?:#|%:)[ \t\f\v]*")
_NAME = re.compile(r"[A-Za-z_]\w*")
_HEADER_NAME = re.compile(r'\s*(?:"(?P<q>[^"\n]*)"|<(?P<a>[^>\n]*)>)')
_REFUSED_NAME = re.compile(r"\b(?:" + "|".join(REFUSED_NAMES) + r")\b")
#: How a compiler marks an asm statement in its assembly: GCC (and Clang for ELF) ``#APP``; Clang elsewhere a
#: comment, ``InlineAsm Start`` or ``Start of file scope inline assembly``, after its target's comment mark.
_ASM_STATEMENT = re.compile(r"^[ \t]*(?:#|;|//|@)+[ \t]*(?:APP\b|InlineAsm Start\b|Start of file scope inline assembly)",
                            re.MULTILINE)
_AS_DIRECTIVE = re.compile(r"(?<![\w.$])\.(?:" + "|".join(AS_DIRECTIVES) + r")\b", re.IGNORECASE)
_C_DIAG = re.compile(r"^(?P<file>[^\s:][^:]*?):(?P<line>\d+):(?:\d+:)?\s*(?:fatal error|error):\s*(?P<msg>.*)$")
_TARGET = "nirmaan-compile-screen"
_TIMEOUT = 60


def _logical_lines(text: str) -> tuple[list[str], list[str]]:
    """The text as the preprocessor's directives see it: lines joined at a backslash and a newline, comments
    replaced by a space. Returned twice: with string and character literals as written, and with them emptied."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\\[ \t]*\n", "", text)
    kept: list[str] = []
    blank: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            kept.append(" ")
            blank.append(" ")
            i = n if end < 0 else end + 2
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            closed = j < n and text[j] == c
            kept.append(text[i:j + 1] if closed else text[i:j])
            blank.append(c + c)
            i = j + 1 if closed else j
        else:
            kept.append(c)
            blank.append(c)
            i += 1
    return "".join(kept).split("\n"), "".join(blank).split("\n")


def directive_problem(text: str) -> str | None:
    """Why this C text uses a directive, a name or an include the screen refuses, or None (``directive``)."""
    if _TRIGRAPH.search(text):
        return "a trigraph (??), which can spell a directive"
    kept, blank = _logical_lines(text)
    for number, (line, plain) in enumerate(zip(kept, blank), start=1):
        if found := _REFUSED_NAME.search(plain):
            return f"line {number}: {found[0]}"
        start = _DIRECTIVE.match(line)
        if not start:
            continue
        rest = line[start.end():]
        if not rest.strip():
            continue  # the null directive
        name = _NAME.match(rest)
        after = rest[name.end():name.end() + 1] if name else ""
        if not name or (after and not after.isspace() and after not in '<"('):
            return f"line {number}: a directive that is not a name ({line.strip()[:40]!r}), such as a line marker"
        word = name[0]
        if word not in DIRECTIVES:
            return f"line {number}: #{word}"
        if word == "pragma" and rest[name.end():].strip() != "once":
            return f"line {number}: #pragma other than #pragma once"
        if word == "include" and (header := _HEADER_NAME.match(rest[name.end():])):
            written = header["q"] if header["q"] is not None else header["a"]
            parts = re.split(r"[/\\]+", written)
            if written.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", written) or ".." in parts:
                return f"line {number}: #include of {written!r}, an absolute path or a path with '..'"
    return None


def make_dependencies(text: str) -> list[str]:
    """The files of a ``-M -MT <target>`` rule, unescaped as the compiler escapes them."""
    text = text.replace("\\\n", " ")
    head, _, rest = text.partition(f"{_TARGET}:")
    if head.strip():
        return []
    return [re.sub(r"\\(.)", r"\1", tok).replace("$$", "$") for tok in re.findall(r"(?:\\.|[^\s\\])+", rest)]


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "HOME", "TMPDIR", "SDKROOT")}
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, errors="replace",
                          timeout=_TIMEOUT, stdin=subprocess.DEVNULL)


@functools.lru_cache(maxsize=16)
def system_includes(compiler: str, extra: tuple[str, ...] = ()) -> tuple[Path, ...]:
    """The compiler's own include folders, and the system root it was given (``-isysroot``, Clang on macOS, whose
    dependency list names the SDK's settings file), from its ``-v`` report; empty if it cannot say."""
    try:
        report = _run([compiler, *extra, "-E", "-v", "-x", "c", os.devnull], Path(tempfile.gettempdir())).stderr
    except (OSError, subprocess.TimeoutExpired):
        return ()
    folders, inside = [], False
    for line in report.splitlines():
        if line.startswith("#include <...> search starts here:") or line.startswith('#include "..." search starts'):
            inside = True
        elif line.startswith("End of search list."):
            inside = False
        elif inside and line.startswith(" "):
            folder = Path(line.strip().removesuffix(" (framework directory)"))
            if folder.is_dir():
                folders.append(folder.resolve())
    if folders:
        folders += [Path(m[1]).resolve() for m in re.finditer(r'"?-isysroot"?\s+"?([^"\s]+)', report)
                    if Path(m[1]).is_dir() and Path(m[1]).resolve() != Path("/")]
    return tuple(dict.fromkeys(folders))


def _inside(path: Path, roots: Sequence[Path]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


def screen(flags: Sequence[str], files: Sequence[str], sources: Sequence[str], harness: Sequence[Path],
           workdir: Path, statements: bool = True) -> str | None:
    """Why the C ``files`` may not be compiled with ``flags`` (the compiler, its options and include folders, as
    the build gives them), or None. ``sources`` are every file the build names, whose folders the files may pull
    from; ``harness`` the harness's folders; ``workdir`` the run's own directory. ``statements``: refuse an asm
    statement too (the backends); the object screen, which refuses asm in the seat's lines itself, leaves it out."""
    compiler, options = flags[0], tuple(a for a in flags[1:] if not a.startswith("-I"))
    system = system_includes(compiler, tuple(a for a in options if a.startswith(("-m", "-f", "--sysroot"))))
    if not system:
        return f"{REFUSED}: {compiler} did not report its own include folders, so nothing could be checked"
    harness = [Path(h).resolve() for h in harness]
    screened_roots = [*{Path(s).resolve().parent for s in sources}, Path(workdir).resolve()]
    roots = [*screened_roots, *harness, *system]
    out = Path(tempfile.mkdtemp(prefix="compile-screen-", dir=workdir))
    try:  # the screen's own assembly is removed whatever it found: a compiler may write a file it read into it
        return _screen(flags, files, roots, screened_roots, harness, workdir, out, statements)
    finally:
        shutil.rmtree(out, ignore_errors=True)


def _screen(flags: Sequence[str], files: Sequence[str], roots: list[Path], screened_roots: list[Path],
            harness: list[Path], workdir: Path, out: Path, statements: bool) -> str | None:
    compiler = flags[0]
    seen: set[Path] = set()
    for given in files:  # the written text first: nothing is opened for a refused include
        path = Path(given).resolve()
        seen.add(path)
        problem = directive_problem(path.read_text(encoding="utf-8", errors="replace"))
        if problem:
            return f"{REFUSED}: {path.name}, {problem}; nothing was compiled"
    for given in files:
        path = Path(given).resolve()
        name = path.name
        header = path.suffix == ".h"
        try:
            listed = _run([*flags, *(["-x", "c"] if header else []), "-M", "-MG", "-MT", _TARGET, str(path)], workdir)
        except subprocess.TimeoutExpired:
            return f"{REFUSED}: {name}: listing the files it pulls in did not finish; nothing was compiled"
        except OSError as exc:
            return f"{REFUSED}: {name}: {compiler} could not run ({exc}); nothing was compiled"
        if listed.returncode != 0:
            own = next((f"; first: {Path(m['file']).name}:{m['line']}: {m['msg'][:160]}"
                        for m in map(_C_DIAG.match, listed.stderr.splitlines())
                        if m and Path(m["file"]).resolve() == path), "")
            return (f"{REFUSED}: {name}: the preprocessor could not list the files it pulls in (exit "
                    f"{listed.returncode}){own}; nothing was compiled")
        for dep in make_dependencies(listed.stdout):
            found = Path(workdir) / dep  # a relative name is the compiler's, from the folder it ran in
            if not found.exists():
                continue  # a header not found (-MG): the build reports it, and reads nothing for it
            real = found.resolve()
            if not _inside(real, roots):
                return (f"{REFUSED}: {name} pulls in {dep}, outside the run's source folders, the harness and the "
                        "compiler's own include folders; nothing was compiled")
            if real not in seen and _inside(real, screened_roots) and not _inside(real, harness):
                seen.add(real)
                problem = directive_problem(real.read_text(encoding="utf-8", errors="replace"))
                if problem:
                    return f"{REFUSED}: {real.name}, {problem}; nothing was compiled"
    for n, given in enumerate(f for f in files if f.endswith(".c")):
        path = Path(given).resolve()
        assembly = out / f"{n}_{path.stem}.s"
        try:
            compiled = _run([*flags, "-S", "-o", str(assembly), str(path)], workdir)
        except subprocess.TimeoutExpired:
            return f"{REFUSED}: {path.name}: compiling it to assembly did not finish; nothing was compiled"
        if compiled.returncode != 0 or not assembly.is_file():
            continue  # the build's own compile of it fails the same way, before the assembler runs
        text = assembly.read_text(encoding="utf-8", errors="replace")
        if statements and _ASM_STATEMENT.search(text):
            return f"{REFUSED}: {path.name} holds an asm statement; nothing was compiled"
        if found := _AS_DIRECTIVE.search(text):
            return f"{REFUSED}: {path.name}: its assembly holds the directive {found[0]}; nothing was compiled"
    return None
