"""What a gate refuses to run (M84, docs/GATE_INPUTS.md): input that could reach the host outside its run.

A gate runs tools over files a seat wrote, and several of those tools run a shell command, or other code, on
the machine that runs the gate when a file asks them to: a Yosys script line that starts with ``!`` or calls
``exec``, an SBY setup's ``--pycode-begin--`` block, its engine and option values (SBY builds shell command
lines from them), a testbench's ``$system``, ``$fopen`` or ``$c``, a Verilator `` `systemc_`` block, a Tcl
``exec`` in timing constraints, and a ``top`` that is not a name (it reaches Yosys and Tcl scripts as text,
where a ``;`` or a new line starts a command of its own).

M85 adds reads: every file a setup names (an SBY ``[files]`` entry, a file or include folder a Yosys read command
names) is inside the run's own folder, or one of the files the run was given, so a setup cannot copy a file of the
host into its run, where a tool's log, and so what a seat reads, could carry part of it.

Every check here is an allow list: a construct it does not name is refused, so a tool's next release that adds
a way out does not open one here. The backends call these before any step runs, and a refused input is a
recorded failed run with the reason, never an exception. Code that is code by design (a cocotb test module, a
firmware driver) is not checked here: docs/GATE_INPUTS.md, section 4, says where it runs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

#: The files a run reads as Verilog.
HDL_SUFFIXES = (".v", ".sv", ".vh", ".svh")
#: Parameters naming Verilog a run compiles or simulates; every one is checked (``check_inputs``).
HDL_PARAMS = ("sources", "rtl", "design")
#: How a refusal ends.
REFUSED = "(refused, nothing ran)"

# --- Names and paths ------------------------------------------------------------------------

#: What ``top`` may be: a plain Verilog module name.
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
#: What a file path may not carry into a script: a quote ends the quoted name there, a line break starts a new line.
_PATH_BAD_RE = re.compile(r'["\x00-\x1f\x7f]')


def name_problem(top: object) -> str | None:
    """Why ``top`` cannot be given to a tool, or None (an empty ``top`` is the backend's own matter)."""
    text = "" if top is None else str(top)
    if not text or _NAME_RE.match(text):
        return None
    return f"top must be a plain module name (letters, digits, _ and $), not {text!r} {REFUSED}"


#: M85: a file name a setup may give: relative, ordinary characters, no parent folder (``runtime.files.safe_path``).
#: So no ``/`` or ``~`` at the start (Yosys reads ``~/`` as the home folder, ``+/`` as its own share folder), no
#: ``..``, no glob, no quote.
_RELATIVE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*$")
#: How a read refusal ends.
_OUTSIDE = ("a setup reads no file outside its own folder but the files its run is given "
            "(docs/GATE_INPUTS.md, section 2)")


def relative_problem(name: str, where: str) -> str | None:
    """Why a file name a setup gives could lead outside its run's folder by itself, or None (M85)."""
    if _RELATIVE_RE.match(name) and ".." not in name.split("/"):
        return None
    return (f"{where} names {name!r}, not a relative file name of ordinary characters with no '..'; "
            f"{_OUTSIDE} {REFUSED}")


def inside_problem(path: Path, folder: Path, given: Iterable[str | Path], where: str, name: str) -> str | None:
    """Why ``path`` is outside the run (M85): through a link it leads out of ``folder`` and is none of the files the
    run was given (``sources``, an approved file the platform links beside the setup, M68), or None.

    The reason never names where the link leads, and nothing here reads the file.
    """
    real = path.resolve()
    if real.is_relative_to(folder.resolve()) or real in {Path(g).resolve() for g in given}:
        return None
    return f"{where} names {name!r}, which leads outside the run's own folder; {_OUTSIDE} {REFUSED}"


def path_problem(paths: Iterable[str]) -> str | None:
    """Why one of these paths cannot be written into a tool's script, or None."""
    bad = [p for p in paths if _PATH_BAD_RE.search(p)]
    if not bad:
        return None
    return f"a file path may not hold a quote or a control character, and {bad[0]!r} does {REFUSED}"


# --- Verilog ----------------------------------------------------------------------------------

#: The system tasks and functions a gated Verilog file may use: none opens, reads or writes a file, or runs
#: anything outside the simulation. Which file may end a simulation or read a plusarg is the testbench rule's
#: matter (``eda.TESTBENCH_ONLY``); ``$dumpfile`` is allowed only with a plain file name (``_DUMPFILE_RE``).
SAFE_SYSTEM = frozenset({
    # output to the simulator's own log
    "$display", "$displayb", "$displayh", "$displayo", "$write", "$writeb", "$writeh", "$writeo",
    "$strobe", "$strobeb", "$strobeh", "$strobeo", "$monitor", "$monitorb", "$monitorh", "$monitoro",
    "$monitoron", "$monitoroff", "$sformat", "$sformatf", "$swrite", "$swriteb", "$swriteh", "$swriteo",
    "$error", "$fatal", "$warning", "$info",
    # ending the run, and its arguments
    "$finish", "$stop", "$exit", "$value$plusargs", "$test$plusargs",
    # time
    "$time", "$stime", "$realtime", "$timeformat", "$printtimescale",
    # values and types
    "$signed", "$unsigned", "$clog2", "$bits", "$size", "$high", "$low", "$left", "$right", "$increment",
    "$dimensions", "$unpacked_dimensions", "$cast", "$typename", "$isunknown", "$countones", "$countbits",
    "$onehot", "$onehot0", "$itor", "$rtoi", "$realtobits", "$bitstoreal", "$shortrealtobits", "$bitstoshortreal",
    "$ln", "$log10", "$exp", "$sqrt", "$pow", "$floor", "$ceil", "$sin", "$cos", "$tan", "$asin", "$acos", "$atan",
    "$atan2", "$hypot", "$sinh", "$cosh", "$tanh", "$asinh", "$acosh", "$atanh",
    # random numbers
    "$random", "$urandom", "$urandom_range", "$dist_uniform", "$dist_normal", "$dist_exponential",
    "$dist_poisson", "$dist_chi_square", "$dist_t", "$dist_erlang",
    # assertions and formal
    "$past", "$rose", "$fell", "$stable", "$changed", "$sampled", "$past_gclk", "$rose_gclk", "$fell_gclk",
    "$stable_gclk", "$changed_gclk", "$initstate", "$anyconst", "$anyseq", "$allconst", "$allseq", "$global_clock",
    "$asserton", "$assertoff", "$assertkill", "$root", "$unit",
    # waveforms, into the run's own directory
    "$dumpvars", "$dumpon", "$dumpoff", "$dumpall", "$dumpflush", "$dumplimit",
})
#: Strings and comments, matched together, so a "//" inside a string cannot hide what follows it. A string ends on
#: its own line: Yosys reads a string on across a line break, so a quote left open is refused (``_lexical``).
_TEXT_RE = re.compile(r'"(?:\\[^\n]|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)
_SYSTEM_RE = re.compile(r"(?<![\w$])\$[A-Za-z_][\w$]*")
#: ``$dumpfile`` with a plain file name, which lands in the run's own directory.
_DUMPFILE_RE = re.compile(r'\$dumpfile\s*\(\s*"[A-Za-z0-9_][A-Za-z0-9_.\-]*"\s*\)')
_INCLUDE_RE = re.compile(r'`include\b\s*(?:"([^"\n]*)")?')
_DPI_RE = re.compile(r'"DPI')
#: Verilator copies these blocks into the C++ model it compiles and runs.
_SYSTEMC_RE = re.compile(r"`systemc_\w*")


def _without_comments(text: str) -> str:
    return _TEXT_RE.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", text)


# ET1 (council/records/2026-11-22-eda-tools-seat-account.md): the checks above read a file's comments and strings
# by ``_TEXT_RE``, and a tool reads them by its own rules. Where the two readings differ, text the check skips as a
# comment or a string is code to the tool. So a file is checked only if it is written in forms every tool splits
# into code, comments and strings the way ``_TEXT_RE`` does, and a name is checked only if no tool can build a
# longer one around it. Each rule below is an allow list of forms; what it does not name is refused.

#: The compiler directives a gated file may use. Every directive of IEEE 1800 and of Icarus, Verilator and Yosys is
#: lower case but ``__FILE__`` and ``__LINE__``, so any other backtick name with a lower case letter must be a macro
#: the run's own files define (``verilog_problem``): so no `` `line `` (which names another file as the source),
#: `` `uselib `` or `` `pragma ``, and no directive a tool adds in a later release. A name with no lower case
#: letter is a macro (an undefined one is the tool's error).
DIRECTIVES = frozenset({
    "define", "undef", "undefineall", "ifdef", "ifndef", "elsif", "else", "endif", "include", "timescale",
    "default_nettype", "resetall", "celldefine", "endcelldefine", "unconnected_drive", "nounconnected_drive",
    "begin_keywords", "end_keywords", "__FILE__", "__LINE__",
})
#: A conditional directive. Icarus skips the text of a branch it does not take without reading its strings or
#: comments, so a quote or a comment mark there is nothing to Icarus and opens a string or a comment to the check.
_CONDITIONAL_RE = re.compile(r"`(?:ifdef|ifndef|elsif|else|endif)\b")
#: The one form a conditional directive may take: alone on its line, a trailing ``//`` comment aside.
_CONDITIONAL_LINE_RE = re.compile(
    r"^[ \t]*`(?:(?:ifdef|ifndef|elsif)[ \t]+[A-Za-z_][\w$]*|else|endif)[ \t]*(?://[^\n]*)?$")
#: A backtick name: a directive or a macro.
_MACRO_RE = re.compile(r"`([A-Za-z_][\w$]*)")
_DEFINE_RE = re.compile(r"`define[ \t]+([A-Za-z_][\w$]*)")
#: The suffixes Verilator compiles as C++ rather than reading as Verilog.
C_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
#: The control characters a gated file may hold: tab, line feed, and a carriage return before a line feed.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]|\r(?!\n)")


def _blank(text: str) -> str:
    """``text`` with every comment and string blanked to spaces, line breaks kept: what the checks read as code."""
    return _TEXT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _lexical(raw: str, text: str, suffix: str = "") -> set[str]:
    """Where a tool could read code that the checks read as a comment or a string, or build a name they never see.

    ``raw`` is the file as stored (its line ends unchanged), ``text`` as the checks read it, ``suffix`` its name's.
    """
    found: set[str] = set()
    control = _CONTROL_RE.search(raw)
    if control:
        found.add(f"the control character {control.group(0)!r}")
    code = _blank(text)
    # A C character literal ('\0', '"') breaks both rules below. A file Verilator compiles as C++ by its suffix, with
    # no $ or DPI anywhere in it and a backtick only around a word (`bytes` in a comment), holds nothing a Verilog
    # tool acts on to read a file or run anything, however it splits the text; so the two are left to the compiler.
    c_source = suffix in C_SUFFIXES and not re.search(r"[`$]|DPI", re.sub(r"`[A-Za-z_][\w$]*`", "", text))
    if '"' in code and not c_source:
        found.add("a quote that does not close a string on its own line")
    if re.search(r"\\(?!\n)", code) and not c_source:  # \/* or \" is a name to every tool, and a comment or string mark here
        found.add("a backslash outside a string (an escaped identifier)")
    lines, coded = text.split("\n"), code.split("\n")
    if any(_CONDITIONAL_RE.search(c) and not _CONDITIONAL_LINE_RE.match(t) for t, c in zip(lines, coded)):
        found.add("a conditional directive that is not alone on its line")
    if len(_CONDITIONAL_RE.findall(text)) != len(_CONDITIONAL_RE.findall(code)):
        found.add("a conditional directive inside a comment or a string")
    # Icarus reads a block comment opened on a directive's line (or a macro's continued line) as ending there, and
    # what follows as code: `define C /* is "Unterminated comment in define", `undef X /* is not a comment at all.
    for m in _TEXT_RE.finditer(text):
        if m.group(0).startswith("/*") and "\n" in m.group(0):
            row = text.count("\n", 0, m.start())
            column = m.start() - (text.rfind("\n", 0, m.start()) + 1)
            if coded[row][:column].lstrip().startswith("`") or (row and lines[row - 1].endswith("\\")):
                found.add("a block comment opened on a directive's line and closed on a later one")
    # A name the preprocessor assembles: a bare $ before a macro, a macro glued to the name before it, or a macro
    # call glued to the name after it (`P($write)memh is $writememh to Icarus and Verilator).
    if re.search(r"(?<![\w$])\$(?![A-Za-z_])", code):
        found.add("a $ that does not start a name (a macro could supply the name)")
    if re.search(r"[\w$]`", code):
        found.add("a macro glued to the name before it")
    if re.search(r"`[\"\\]", _without_comments(text)):
        found.add("a macro quote (`\" or `\\)")
    unquoted = _TEXT_RE.sub(lambda m: m.group(0) if m.group(0).startswith("/") else re.sub(r"[^\n]", " ", m.group(0)),
                            text)
    for m in re.finditer(r"`[A-Za-z_][\w$]*[ \t]*\(", code):
        depth, i = 1, m.end()
        while i < len(code) and depth:
            depth += {"(": 1, ")": -1}.get(code[i], 0)
            i += 1
        if i < len(code) and re.match(r"[\w$`]", code[i]):
            found.add("a macro call glued to the name after it")
        if re.search(r"//|/\*", unquoted[m.end():i]):  # a preprocessor collects arguments its own way
            found.add("a comment inside a macro call's arguments")
    return found


def verilog_uses(text: str) -> tuple[set[str], list[str]]:
    """What one Verilog file uses that a gate does not run, and the files it includes (as written)."""
    code = _without_comments(text)
    used, included = set(), []
    for m in _INCLUDE_RE.finditer(code):
        name = m.group(1)
        if name is None:
            used.add("`include without a quoted file name")
        elif Path(name).is_absolute() or ".." in Path(name).parts:
            used.add(f'`include "{name}" (outside its own folder)')
        else:
            included.append(name)
    if _DPI_RE.search(code):
        used.add("DPI")
    used |= set(_SYSTEMC_RE.findall(code))
    bare = _TEXT_RE.sub(" ", _DUMPFILE_RE.sub(" ", code))
    if "``" in bare:
        used.add("`` (token pasting, which could build any name)")
    used |= {name for name in _SYSTEM_RE.findall(bare) if name not in SAFE_SYSTEM}
    return used, included


def verilog_problem(files: Iterable[str | Path]) -> str | None:
    """Why these Verilog files (and every file they include beside them) cannot be run by a gate, or None.

    An included file is read only when, through any link, it is inside the folder of one of ``files`` (the run's
    own folders). One that leads anywhere else is refused by the name it is included as, and is
    never read, so a refusal quotes nothing of a file outside the run (ip#309's follow-up).
    """
    found, seen = [], set()
    given = [Path(f).resolve() for f in files]
    folders = {path.parent for path in given}
    todo = list(given)
    defined: set[str] = set()
    macros: dict[Path, set[str]] = {}
    while todo:
        path = todo.pop(0)
        if path in seen or not path.is_file():  # an absent file is the run's own failure
            continue
        seen.add(path)
        raw = path.read_bytes().decode("utf-8", errors="replace")
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        used, included = verilog_uses(text)
        used |= _lexical(raw, text, path.suffix)
        code = _blank(text)
        defined |= set(_DEFINE_RE.findall(code))
        macros[path] = {m for m in _MACRO_RE.findall(code) if m not in DIRECTIVES and m != m.upper()}
        for name in included:
            target = (path.parent / name).resolve()
            if any(target.is_relative_to(folder) for folder in folders):
                todo.append(target)
            else:
                return (f"{path.name} includes {name!r}, which leads outside the sandbox; a gate reads no included "
                        f"file outside the run's own folders (docs/GATE_INPUTS.md, section 2) {REFUSED}")
        if used:
            found.append(f"{path.name} uses {', '.join(sorted(used))}")
    for path, names in macros.items():
        unknown = sorted(f"`{m}" for m in names - defined)
        if unknown:
            found.append(f"{path.name} uses {', '.join(unknown)}, a directive a gate does not run and no macro the run's "
                         f"files define")
    if not found:
        return None
    return ("a gate runs no Verilog that could open a file or reach outside the simulation (docs/GATE_INPUTS.md), "
            f"and {'; '.join(found)} {REFUSED}")


# --- Yosys scripts ----------------------------------------------------------------------------

#: The Yosys commands a seat's script (an SBY ``[script]``, an eqy ``[gold]``, ``[gate]`` or ``[script]``) may
#: use: each reads designs or transforms the one in memory, and none writes a file or runs anything.
YOSYS_SAFE = frozenset({
    "read", "read_verilog", "verilog_defaults", "verilog_defines", "hierarchy", "prep", "proc", "flatten", "opt",
    "opt_clean", "opt_expr", "opt_merge", "chparam", "setparam", "setattr", "memory", "memory_nordff",
    "memory_map", "async2sync", "dffunmap", "clk2fflogic", "chformal", "rename", "check", "wreduce", "peepopt",
})


#: M85: the allowed Yosys commands that read files, and the options of theirs whose value is not a file: one word
#: after each of ``_VALUE``, every word after ``-define`` and ``-undef``. A ``-I`` or ``-incdir`` folder is checked
#: as a file name is; ``-f`` and ``-F`` (a command file, naming files this check never sees) are refused.
_READS = frozenset({"read", "read_verilog", "verilog_defaults", "verilog_defines"})
_VALUE = frozenset({"-D", "-U", "-setattr"})


def _read_names(words: list[str]) -> list[str] | None:
    """The files and include folders one Yosys command names, or None when it names a command file."""
    command, rest, names, i = words[0], words[1:], [], 0
    if command == "hierarchy":
        return [rest[k + 1] if k + 1 < len(rest) else "" for k, w in enumerate(rest) if w == "-libdir"]
    if command not in _READS:
        return []
    while i < len(rest):
        word = rest[i]
        if word in ("-f", "-F"):
            return None
        if word in ("-define", "-undef"):
            break
        if word == "-incdir":
            names += rest[i + 1:] or [""]
            break
        if word == "-I":
            names.append(rest[i + 1] if i + 1 < len(rest) else "")
            i += 1
        elif word in _VALUE:
            i += 1
        elif word.startswith("-I"):
            names.append(word[2:])
        elif not word.startswith("-"):
            names.append(word)
        i += 1
    return names


def yosys_problem(lines: Iterable[str], where: str) -> str | None:
    """Why these Yosys script lines cannot run, or None. A line may hold several commands, split by ``;``.

    M85: a command that reads names its files and include folders by relative names only (``relative_problem``):
    the script runs where the setup's files are copied, so such a name reaches nothing else.
    """
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("!"):
            return f"{where} runs a shell command ({text[:60]!r}) {REFUSED}"
        for command in text.split(";"):
            words = command.split()
            if words and words[0] not in YOSYS_SAFE:
                return (f"{where} uses the Yosys command {words[0]!r}, which is not one a gate runs (it may write a "
                        f"file or run a program; allowed: {', '.join(sorted(YOSYS_SAFE))}) {REFUSED}")
            names = _read_names(words) if words else []
            if names is None:
                return f"{where} gives {words[0]} a command file (-f or -F), whose files a gate never checks {REFUSED}"
            for name in names:
                problem = relative_problem(name, f"{where}'s {words[0]}")
                if problem:
                    return problem
    return None


# --- SBY setups -------------------------------------------------------------------------------

#: The sections an SBY setup may have (``[tasks]`` is refused by the formal backends themselves).
SBY_SECTIONS = frozenset({"options", "engines", "script", "files", "tasks"})
#: The ``[options]`` an SBY setup may set, and the values each takes. SBY writes some option values into shell
#: command lines, so a value is a plain word too.
SBY_OPTIONS = {
    "mode": re.compile(r"^(bmc|prove|cover|live)$"),
    **{key: re.compile(r"^\d+$") for key in ("depth", "append", "skip", "timeout")},
    **{key: re.compile(r"^(on|off)$")
       for key in ("multiclock", "wait", "cover_assert", "assume_early", "vcd", "vcd_sim", "fst")},
    "expect": re.compile(r"^(pass|fail|unknown|error|timeout)(,(pass|fail|unknown|error|timeout))*$"),
}
#: The engines an SBY setup (or an eqy ``sby`` strategy) may name, and the words each may take after its name.
#: SBY joins these words into the solver's shell command line unquoted.
_SMTBMC_FLAGS = {"--nomem", "--syn", "--stbv", "--stdt", "--presat", "--nopresat", "--unroll", "--nounroll",
                 "--noincr", "--dumpsmt2", "--progress", "--basecase", "--induction", "--keep-going"}
SBY_ENGINES = {
    "smtbmc": frozenset({*_SMTBMC_FLAGS, "yices", "z3", "boolector", "bitwuzla", "cvc4", "cvc5", "mathsat"}),
    "abc": frozenset({"bmc3", "pdr", "sim3"}),
    "btor": frozenset({"btormc", "pono"}),
    "aiger": frozenset({"suprove", "avy", "aigbmc", "rIC3"}),
    "none": frozenset(),
}
_SEED_RE = re.compile(r"^--seed=\d+$")


def engine_problem(words: list[str], where: str) -> str | None:
    """Why one engine line cannot run, or None."""
    if not words:
        return None
    allowed = SBY_ENGINES.get(words[0])
    if allowed is None:
        return f"{where} names the engine {words[0]!r}; a gate runs {', '.join(sorted(SBY_ENGINES))} {REFUSED}"
    bad = [w for w in words[1:] if w not in allowed and not (words[0] == "smtbmc" and _SEED_RE.match(w))]
    if bad:
        return (f"{where} gives the {words[0]} engine {bad[0]!r}, which is not a solver or option a gate passes on "
                f"(SBY writes it into a shell command line) {REFUSED}")
    return None


def _header(text: str) -> tuple[str, str] | None:
    """A section header's name and argument, or None for any other line."""
    if text.startswith("[") and text.endswith("]"):
        name, _, args = text[1:-1].strip().partition(" ")
        return name, args.strip()
    return None


def sby_problem(sby: Path, given: Iterable[str | Path] = ()) -> str | None:
    """Why an SBY setup cannot be run by a gate, or None (docs/GATE_INPUTS.md, section 2).

    M85: each ``[files]`` entry is a relative name, and its file is in the setup's folder or one of ``given`` (the
    run's ``sources``); this is checked before any file it names is read.
    """
    section, script, sources = None, [], []
    for line in sby.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if text.startswith("--pycode"):
            return f"{sby.name} has a --pycode-begin-- block, Python that SBY runs as it reads the file {REFUSED}"
        header = _header(text)
        if header:
            section = header[0]
            if section not in SBY_SECTIONS:
                return (f"{sby.name} has a [{text[1:-1].strip()}] section; a gate runs setups with "
                        f"{', '.join(f'[{s}]' for s in sorted(SBY_SECTIONS))} only {REFUSED}")
            continue
        if not text or text.startswith("#"):
            continue
        words = text.split()
        if section == "options":
            rule = SBY_OPTIONS.get(words[0])
            if rule is None or len(words) != 2 or not rule.match(words[1]):
                return (f"{sby.name} sets the option {text!r}; a gate runs the options "
                        f"{', '.join(sorted(SBY_OPTIONS))}, each with a plain value {REFUSED}")
        elif section == "engines":
            problem = engine_problem(words, sby.name)
            if problem:
                return problem
        elif section == "script":
            script.append(text)
        elif section == "files":
            *dest, src = words
            for name in dest:
                if Path(name).is_absolute() or ".." in Path(name).parts:
                    return f"{sby.name} copies a file to {name!r}, outside the run's own folder {REFUSED}"
            where = f"{sby.name}'s [files]"
            for name in (*dest, src):
                problem = relative_problem(name, where)
                if problem:
                    return problem
            problem = inside_problem(sby.parent / src, sby.parent, given, where, src)
            if problem:
                return problem
            path = (sby.parent / src).resolve()
            if path.is_dir():
                return f"{sby.name} copies the folder {src!r}; a gate copies files only, each one checked {REFUSED}"
            sources.append(path)
    return yosys_problem(script, f"{sby.name}'s [script]") or verilog_problem(sources)


# --- eqy setups -------------------------------------------------------------------------------

#: The sections an eqy setup may have; ``gold``, ``gate`` and ``script`` hold Yosys commands.
EQY_SECTIONS = frozenset({"options", "gold", "gate", "script", "match", "collect", "partition", "recode", "strategy"})
EQY_SCRIPTS = ("gold", "gate", "script")
#: eqy's own ``[options]``, each on or off.
EQY_OPTIONS = frozenset({"splitnets", "insbuf"})
#: What a ``[strategy]`` may set, and the values each takes; ``engine`` is checked as an SBY engine line (eqy writes
#: it into the ``.sby`` it runs). A strategy's ``option`` lines would go into that ``.sby``'s ``[options]``
#: unchecked, so a gate does not take them.
EQY_STRATEGY = {
    "use": re.compile(r"^(sat|sby)$"),
    "depth": re.compile(r"^\d+$"),
    "timeout": re.compile(r"^\d+$"),
    "xprop": re.compile(r"^(on|off)$"),
}


def eqy_problem(eqy: Path) -> str | None:
    """Why an eqy setup cannot be run by a gate, or None (docs/GATE_INPUTS.md, section 2)."""
    section, scripts = None, []
    for line in eqy.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        header = _header(text)
        if header:
            section = header[0]
            if section not in EQY_SECTIONS:
                return (f"{eqy.name} has a [{text[1:-1].strip()}] section; a gate runs setups with "
                        f"{', '.join(f'[{s}]' for s in sorted(EQY_SECTIONS))} only {REFUSED}")
            continue
        words = text.split()
        if section in EQY_SCRIPTS:
            scripts.append(text)
        elif section == "options" and not (len(words) == 2 and words[0] in EQY_OPTIONS and words[1] in ("on", "off")):
            return f"{eqy.name} sets the option {text!r}; a gate runs {', '.join(sorted(EQY_OPTIONS))} on or off {REFUSED}"
        elif section == "strategy" and words[0] == "engine":
            problem = engine_problem(words[1:], f"{eqy.name}'s strategy")
            if problem:
                return problem
        elif section == "strategy":
            rule = EQY_STRATEGY.get(words[0])
            if rule is None or len(words) != 2 or not rule.match(words[1]):
                return (f"{eqy.name}'s strategy sets {text!r}; a gate takes {', '.join(sorted(EQY_STRATEGY))} and "
                        f"engine, each with a plain value {REFUSED}")
    return yosys_problem(scripts, eqy.name)


# --- Timing constraints (SDC, which OpenSTA and OpenROAD read as Tcl) -------------------------

#: The Tcl commands a constraints file may use: SDC's own, the object queries, and plain variables, lists and
#: arithmetic. None opens a file, runs a program, or defines or evaluates a script.
SDC_COMMANDS = frozenset({
    "set", "expr", "list", "llength", "lindex", "lsearch", "concat",
    "current_design", "set_units", "get_ports", "get_pins", "get_cells", "get_nets", "get_clocks", "all_inputs",
    "all_outputs", "all_clocks", "all_registers", "create_clock", "create_generated_clock", "set_clock_uncertainty",
    "set_clock_latency", "set_clock_transition", "set_clock_groups", "set_propagated_clock", "set_input_delay",
    "set_output_delay", "set_input_transition", "set_load", "set_driving_cell", "set_false_path",
    "set_multicycle_path", "set_max_delay", "set_min_delay", "set_max_fanout", "set_max_transition",
    "set_max_capacitance", "set_case_analysis", "set_disable_timing", "set_timing_derate", "set_wire_load_model",
    "set_operating_conditions", "set_ideal_network", "group_path", "set_clock_gating_check", "set_max_area",
})
#: Every ``[`` opens a command substitution here, wherever it is (inside braces too: ``expr`` evaluates them).
_SUBST_RE = re.compile(r"\[\s*([^\s\]]*)")
#: A brace that is not at a word's edge, where Tcl takes it as a plain character rather than a quote.
_MID_BRACE_RE = re.compile(r"[^\s\[{]\{|\}[^\s\]};]")


def _tcl_commands(text: str) -> tuple[list[str], str]:
    """The first word of each command a Tcl script could run, and the script without its comments.

    Sound only for a script with no quote, no backslash but a line continuation, and no brace inside a word
    (``sdc_problem`` refuses the rest): then braces are Tcl's only quoting, and a new line or a ``;`` outside
    them starts a command. Inside a ``[...]`` it starts one too, so a substitution's commands are all seen.
    """
    firsts, kept, i, n = [], [], 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n;":
            i += 1
        if i < n and text[i] == "#":  # a comment, to the end of its line, braces and all
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        start, depth = i, 0
        while i < n and not (text[i] in "\n;" and depth == 0):
            depth = depth + 1 if text[i] == "{" else max(depth - 1, 0) if text[i] == "}" else depth
            i += 1
        if text[start:i].split():
            firsts.append(text[start:i].split()[0])
            kept.append(text[start:i])
    return firsts, "\n".join(kept)


def sdc_problem(sdc: Path) -> str | None:
    """Why a constraints file cannot be read by a timer, or None (docs/GATE_INPUTS.md, section 2)."""
    text = sdc.read_text(encoding="utf-8", errors="replace").replace("\\\n", " ")
    lexical = ('a quote' if '"' in text else 'a backslash' if "\\" in text
               else 'a brace inside a word' if _MID_BRACE_RE.search(text) else None)
    if lexical:
        return (f"{sdc.name} has {lexical}; a timer reads constraints quoted with braces only, so what runs is "
                f"what the check reads {REFUSED}")
    names, code = _tcl_commands(text)
    for found in _SUBST_RE.finditer(code):
        name = found.group(1)
        if not name or not (name[0].isdigit() or name[0] == "*"):  # data[0], data[*]: a bus index, not a command
            names.append(name)
    bad = [name for name in names if name not in SDC_COMMANDS]
    if not bad:
        return None
    return (f"{sdc.name} uses the Tcl command {bad[0]!r}; a timer reads constraints that use SDC commands, object "
            f"queries, variables, lists and arithmetic only {REFUSED}")


# --- One run's inputs -------------------------------------------------------------------------


def check_inputs(top: object, params_files: dict[str, list[str]]) -> str | None:
    """Every run's own check (``eda.execute``): ``top`` is a name, and what it compiles is runnable Verilog.

    Every file in ``sources``, ``rtl`` and ``design`` is checked as Verilog whatever its name: Icarus and Verilator
    read a file of any other name as Verilog. ``rtl`` and ``design`` name Verilog files only, since Verilator
    compiles a C or C++ file given there into the program the run then starts (``fw.test``, ``regmap.verify``).
    """
    files = [f for param in HDL_PARAMS for f in params_files.get(param, [])]
    other = [Path(f).name for param in ("rtl", "design") for f in params_files.get(param, [])
             if Path(f).suffix not in HDL_SUFFIXES]
    if other:
        return f"rtl and design take Verilog files only, and {', '.join(other)} is not Verilog {REFUSED}"
    return name_problem(top) or path_problem(files) or verilog_problem(files)
