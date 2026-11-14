"""Logic equivalence through eqy (M69): ``equivalence.run``, a real run or an honest refusal.

eqy (YosysHQ's equivalence checker, ISC licence, installed beside Yosys and never
vendored here) reads a gold and a gate design with the Yosys scripts of an ``.eqy``
setup, matches their signals, cuts the combined design into partitions, and proves
each partition equivalent. A run passes only when eqy proved every partition, and at
least one (``eda_parsers.parse_eqy``).

The setup runs as given, over copies: the files its scripts read are copied, under
the names it uses, into the run's own directory, and eqy runs there. So a script that
writes a file (``write_verilog counter.v``) writes the copy, never the approved file it
compares, and the result names the files each side read. Before anything runs, the
setup is refused when a script reaches outside Yosys (a shell, Tcl, Python, a plugin,
another script) or writes a file, when it reads a file outside its own folder or one that is not there,
when the gold and gate scripts are the same (a design compared with itself), or, given
``sources``, when it does not read each of them.

This module adds a backend and nothing else (docs/EQUIVALENCE.md): no core change.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from nirmaan.integrations.eda import Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import EdaResult, parse_eqy
from nirmaan.models import text_value

#: The sections of a setup whose lines are Yosys commands; ``script`` lines go to both sides.
SCRIPT_SECTIONS = ("gold", "gate", "script")
#: Yosys commands that reach outside Yosys, so could change the files a run compares or what it reports.
OUTSIDE = frozenset({"exec", "tcl", "python", "script", "plugin"})
#: Yosys commands besides ``write_*`` that write a file a script could then read (eqy writes its own outputs).
WRITES = frozenset({"tee", "dump"})
#: Options of a read command that take a value, which is not a file.
VALUE_OPTIONS = frozenset({"-D", "-U", "-I", "-setattr"})
#: Where a run records the files each side read, for the parser.
COMPARED = "compared.json"
#: The folder in a run's directory that holds the copies eqy runs over.
SETUP_DIR = "setup"


def _commands(eqy: Path) -> dict[str, list[list[str]]]:
    """Each script section's commands, as words; a line may hold several, split by ``;``."""
    out: dict[str, list[list[str]]] = {s: [] for s in SCRIPT_SECTIONS}
    section = None
    for line in eqy.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1].split()[0] if text[1:-1].split() else None
            continue
        if section in out:
            out[section] += [cmd.split() for cmd in text.split(";") if cmd.split()]
    return out


def _reads(words: list[str]) -> list[str]:
    """The files one read command names."""
    if not words[0].startswith("read"):
        return []
    files, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif word in VALUE_OPTIONS:
            skip = True
        elif not word.startswith("-"):
            files.append(word)
    return files


def setup_files(eqy: Path) -> tuple[dict[str, list[str]], str | None]:
    """The files each side reads (``script`` lines count for both), or why the setup cannot be run."""
    commands = _commands(eqy)
    for words in (w for cmds in commands.values() for w in cmds):
        if words[0].startswith("!") or words[0] in OUTSIDE:
            return {}, (f"{eqy.name} uses {words[0]}, which reaches outside Yosys and could change the files it "
                        "compares (refused, nothing ran)")
        if words[0].startswith("write") or words[0] in WRITES:
            return {}, (f"{eqy.name} uses {words[0]}, which writes a file, so one side could read what the other "
                        "wrote (refused, nothing ran)")
    gold = commands["gold"] + commands["script"]
    gate = commands["gate"] + commands["script"]
    if not commands["gold"] or not commands["gate"]:
        return {}, f"{eqy.name} needs a [gold] and a [gate] section (refused, nothing ran)"
    if commands["gold"] == commands["gate"]:
        return {}, (f"{eqy.name} reads gold and gate with the same script, so it compares a design with itself "
                    "(refused, nothing ran)")
    sides = {"gold": [f for w in gold for f in _reads(w)], "gate": [f for w in gate for f in _reads(w)]}
    for name in dict.fromkeys(f for files in sides.values() for f in files):
        # By name, not by where a link points: an approved file is linked beside the setup (M68's ``beside``).
        if Path(name).is_absolute() or os.path.normpath(name).split(os.sep)[0] == "..":
            return {}, f"{eqy.name} reads {name}, outside its own folder (refused, nothing ran)"
        if not (eqy.parent / name).is_file():
            return {}, f"{eqy.name} reads {name}, which is not there (refused, nothing ran)"
    return sides, None


def _setup_path(job: Job) -> Path:
    """The setup, as given: a link is not followed, so the files beside it are the ones it names."""
    return Path(os.path.abspath(text_value(job.params.get("eqy"))))


def _check(job: Job) -> str | None:
    eqy = _setup_path(job)
    sides, problem = setup_files(eqy)
    if problem:
        return problem
    # By resolved path on both sides (``execute`` resolves ``sources``), so a linked approved file matches itself.
    read = {str((eqy.parent / f).resolve()) for files in sides.values() for f in files}
    unread = [Path(src).name for src in job.sources if src not in read]
    return f"{eqy.name} does not read {', '.join(unread)}" if unread else None


def _eqy(job: Job) -> list[list[str]]:
    """Copy the setup and every file it reads into the run's directory, and run eqy over the copies."""
    eqy = _setup_path(job)
    sides, _ = setup_files(eqy)
    setup = job.workdir / SETUP_DIR
    for name in dict.fromkeys(f for files in sides.values() for f in files):
        copy = setup / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(eqy.parent / name, copy)  # the file's content, never a link to it
    setup.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(eqy, setup / eqy.name)
    (job.workdir / COMPARED).write_text(json.dumps(sides) + "\n", encoding="utf-8")
    return [["eqy", "-f", "-d", str(job.workdir / "eqy"), str(setup / eqy.name)]]


def _eqy_dir(job: Job) -> Path:
    """eqy's scripts name their files relative to the directory it runs in: the copies' folder."""
    return job.workdir / SETUP_DIR


def _eqy_parse(run: RunRecord) -> EdaResult:
    compared = run.workdir / COMPARED
    sides = json.loads(compared.read_text(encoding="utf-8")) if compared.is_file() else {}
    return parse_eqy(run.log, run.returncode, sides.get("gold", ()), sides.get("gate", ()))


register_backend(Backend("eqy", "equivalence.run", ("eqy", "yosys", "make"), _eqy, _eqy_parse, ("eqy",), _eqy_dir,
                         files=("eqy",), check=_check))
