"""Python testbenches through cocotb (M72): ``simulator.run``'s ``cocotb`` backend, a real run or an honest refusal.

cocotb (BSD-3-Clause, installed from PyPI as this package's pinned ``cocotb`` extra and never
vendored here) runs testbenches written in Python against HDL in a simulator. This backend
compiles the given sources with Icarus Verilog, with the design (``top``) as the top level,
and runs them under ``vvp`` with cocotb loaded, so the given test modules drive the design.

A run passes only on cocotb's own verdict (``eda_parsers.parse_cocotb``): the JUnit file cocotb
writes into the run's own directory says every test passed, at least one, and its totals line
in the log agrees. The test modules run over copies in the run's directory, so cocotb writes
nothing beside the submitted files. Every HDL source is design here (the testbench is the
Python), so none may end the simulation, read its arguments, open a file or reach outside the
language (M53's testbench-only constructs), and the run is refused before anything runs if one
does.

It runs only when named (``backend: cocotb``), so every run records it: the other
``simulator.run`` backends run HDL testbenches, and ``ToolRun.answers`` (``VERDICT_BACKENDS``)
lets a cocotb run meet only a requirement that fixes this backend, never a gate that reads an
HDL testbench's verdict. This module adds a backend and nothing else (docs/COCOTB.md): no EDA
core change.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path

from nirmaan.integrations.eda import TESTBENCH_ONLY, Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import EdaResult, parse_cocotb
from nirmaan.models import list_values, text_value

#: Where a run keeps the copies of its test modules (on the testbench's ``PYTHONPATH``).
TESTS_DIR = "cocotb_tests"
#: The JUnit file cocotb writes, in the run's own directory.
RESULTS = "results.xml"
#: The time unit and precision for a source that declares no ``timescale``, as cocotb's own Icarus runner sets.
TIMESCALE = "+timescale+1ns/1ps"
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_USES_RE = re.compile(r"(?<![\w$])(?:" + "|".join(re.escape(t) for t in TESTBENCH_ONLY) + r")(?![\w$])")
#: Strings and comments, removed together before the scan, so a "//" inside a string cannot hide what follows it.
_TEXT_RE = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def _environment(params: object) -> str | None:
    """Why this Python cannot run cocotb, or None."""
    if any(importlib.util.find_spec(m) is None for m in ("cocotb", "cocotb_tools", "find_libpython")):
        return "cocotb is not installed in this Python (pip install 'ip-nirmaan[cocotb]')"
    import find_libpython

    if not find_libpython.find_libpython():
        return f"no shared libpython found for {sys.executable}, which cocotb embeds"
    return None


def _tests(job: Job) -> list[Path]:
    return [Path(f).resolve() for f in list_values(job.params.get("cocotb", ""))]


def _check(job: Job) -> str | None:
    """Refuse, before anything runs, what this backend cannot judge by cocotb's verdict."""
    if text_value(job.params.get("backend")).strip() != "cocotb":  # so the run records it (ToolRun.answers, M72)
        return "the cocotb backend runs only when named (backend: cocotb) (refused, nothing ran)"
    expect = text_value(job.params.get("expect")).strip()
    if expect not in ("", "pass"):
        return f"expect {expect!r}: the cocotb backend judges passing runs only (refused, nothing ran)"
    tests = _tests(job)
    names = [t.stem for t in tests]
    bad = [t.name for t in tests if t.suffix != ".py" or not _MODULE_RE.match(t.stem)]
    if bad:
        return f"cocotb test modules must be Python files named as modules, not {', '.join(bad)} (refused, nothing ran)"
    if len(set(names)) != len(names):
        return "two cocotb test modules have the same name (refused, nothing ran)"
    found = []
    for source in job.sources:
        text = _TEXT_RE.sub(" ", Path(source).read_text(encoding="utf-8", errors="replace"))
        used = sorted(set(_USES_RE.findall(text)))
        if used:
            found.append(f"{Path(source).name} uses {', '.join(used)}")
        if "`" in text and "``" in text:
            found.append(f"{Path(source).name} pastes tokens (``), which could build any of them")
    if found:
        return (f"with cocotb every HDL source is design, which may not end the simulation, read its arguments, open "
                f"a file or reach outside the language, and {'; '.join(found)}; nothing was simulated")
    return None


def _cocotb(job: Job) -> list[list[str]]:
    """Compile the sources with Icarus, then run them under vvp with cocotb driving the copied test modules."""
    from cocotb_tools import config
    import find_libpython

    tests = job.workdir / TESTS_DIR
    tests.mkdir(parents=True, exist_ok=True)
    for test in _tests(job):
        shutil.copyfile(test, tests / test.name)  # the file's content, never a link to it
    (job.workdir / "cmds.f").write_text(TIMESCALE + "\n", encoding="utf-8")
    env = ["env", f"GPI_USERS={find_libpython.find_libpython()};{config.pygpi_entry_point()}",
           f"PYGPI_PYTHON_BIN={sys.executable}", f"PYTHONPATH={tests}", "TOPLEVEL_LANG=verilog",
           f"COCOTB_TOPLEVEL={job.top}", f"COCOTB_TEST_MODULES={','.join(t.stem for t in _tests(job))}",
           f"COCOTB_RESULTS_FILE={job.workdir / RESULTS}"]
    return [["iverilog", "-g2012", "-o", "sim.vvp", "-s", str(job.top), "-f", "cmds.f", *job.sources],
            [*env, "vvp", "-m", config.lib_entry("vpi", "icarus"), "sim.vvp", "-none"]]


def _cocotb_parse(run: RunRecord) -> EdaResult:
    """cocotb's verdict; its results file is one of the run's outputs (M44), kept beside the log."""
    results = run.workdir / RESULTS
    result = parse_cocotb(run.log, run.returncodes,
                          results.read_text(encoding="utf-8", errors="replace") if results.is_file() else None)
    if results.is_file():
        result.metrics["outputs"] = {"results": str(results)}
    return result


register_backend(Backend("cocotb", "simulator.run", ("iverilog", "vvp"), _cocotb, _cocotb_parse,
                         ("sources", "top", "cocotb"), files=("cocotb",), environment=_environment, check=_check))
