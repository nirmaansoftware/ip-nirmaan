"""The compile screen (M91, gate SC1): what the C a job compiles may pull in, refused before anything compiles.

Council record ``council/records/2026-11-19-seat-c-live-refusal.md``, decision 4, items 2 and 3: an include by an
absolute path, an include with ``..``, the assembler route and a ``#line`` line are recorded refused in CI, and a
run with a runner-only canary shows the canary in no log, excerpt or record. The record is the CI test job's JUnit
file (GCC, ubuntu-24.04), which names each fixture's test and its outcome; each tool-backed test also prints one
``COMPILE-SCREEN`` line, seen with ``pytest -s``.
Decision 4, item 4: every committed fixture, reference answer and held-out test passes the screen, so its build
runs exactly as before (``test_every_committed_c_file_passes_the_screen``).
"""

from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import object_screen
from nirmaan.integrations import compile_screen, firmware
from nirmaan.integrations.compile_screen import REFUSED, directive_problem, make_dependencies
from nirmaan.integrations.eda import execute, select_backend

REPO = Path(__file__).resolve().parents[1]
FW = REPO / "tests" / "fixtures" / "fw"
FIXTURES = FW / "compile_screen"
REFERENCE = FW / "axi4_lite" / "axi4_lite_regs_drv.c"
RTL = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite" / "axi4_lite_regs.v"

#: Each must-refuse fixture, and the words its refusal must hold.
MUST_REFUSE = {
    "include_dotdot.c": "an absolute path or a path with '..'",
    "include_computed.c": "outside the run's source folders",
    "incbin.c": "asm statement",
    "incbin_pasted.c": "asm statement",
    "incbin_label.c": "the directive .incbin",
    "line_directive.c": "#line",
    "line_marker.c": "a directive that is not a name",
    "line_spelled.c": "#line",
    "line_trigraph.c": "a trigraph",
}


def _gcc() -> bool:
    """The CI toolchain: ``cc`` is GCC, which writes an asm label into its assembly as it is written."""
    try:
        return "Free Software Foundation" in subprocess.run(["cc", "--version"], capture_output=True,
                                                            text=True).stdout
    except OSError:
        return False


def _build(sources: list[Path], workdir: Path | None = None):
    backend, why = select_backend("fw.build", {"backend": "host-cc"})
    assert backend is not None, why
    params = {"backend": "host-cc", "sources": ",".join(map(str, sources))}
    if workdir is not None:
        params["workdir"] = str(workdir)
    return execute(backend, params)


def _record(kind: str, **fields) -> None:
    print(f"\nCOMPILE-SCREEN-{kind} {json.dumps(fields, sort_keys=True)}")


# --- The directive rules, on text --------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    '#include "nirmaan_hal.h"\n#include <stdint.h>\n#pragma once\n#if defined(X) && X > 1\n#elif 0\n#endif\n',
    '#define LINE "#line 1"\nstatic const char *s = "__has_include(x) _Pragma ??";\n',
    "/* #line 1 \"x\" and asm */\n// #include \"/etc/passwd\"\nint x;\n",
    '#include "sub/inner.h"\n#define CAT(a, b) a##b\n#  \n#\n',
    "extern int f(void) __asm__(\"g\");\n",  # an asm label renames a symbol; the assembly is checked, not this
])
def test_what_a_driver_uses_passes_the_directive_rules(text):
    assert directive_problem(text) is None


@pytest.mark.parametrize(("text", "words"), [
    ('#include "/home/runner/work/x/held_out_test.c"\n', "absolute path"),
    ("#include </etc/passwd>\n", "absolute path"),
    ('#include "../../ref/drv.c"\n', "'..'"),
    ('#include "a/../../b.h"\n', "'..'"),
    ('#line 3 "x.c"\n', "#line"),
    ('# 3 "x.c" 1 3\n', "not a name"),
    ('%:line 3\n', "#line"),
    ('#/**/line 3\n', "#line"),
    ('#li\\\nne 3\n', "#line"),
    ('#li\\  \r\nne 3\n', "#line"),
    ("int x;\r#line 3\n", "#line"),
    ("??=line 3\n", "trigraph"),
    ("#include_next <stdio.h>\n", "#include_next"),
    ('#import "x.h"\n', "#import"),
    ('#embed "/etc/passwd"\n', "#embed"),
    ('#ident "x"\n', "#ident"),
    ('#pragma GCC dependency "/etc/passwd"\n', "#pragma other than"),
    ("#if __has_include(\"/etc/passwd\")\n#endif\n", "__has_include"),
    ('_Pragma("GCC system_header")\n', "_Pragma"),
    ("#\\u006cine 3\n", "not a name"),
])
def test_each_refused_directive_is_refused_however_it_is_spelled(text, words):
    problem = directive_problem(text)
    assert problem is not None and words in problem, problem


def test_the_dependency_list_is_read_as_the_compiler_escapes_it():
    rule = "nirmaan-compile-screen: /a/b.c /x\\ y/z.h \\\n /usr/include/stdio.h /p/$$q.h /h/\\#x.h\n"
    assert make_dependencies(rule) == ["/a/b.c", "/x y/z.h", "/usr/include/stdio.h", "/p/$q.h", "/h/#x.h"]
    assert make_dependencies("other: /a.c\n") == []


# --- The must-refuse fixtures, through the real backends (recorded in CI) -----------------------------------------


@needs("cc")
@pytest.mark.parametrize("name", sorted(MUST_REFUSE))
def test_each_must_refuse_fixture_is_refused_and_nothing_is_compiled(name, tmp_path):
    if name == "incbin_label.c" and not _gcc():
        pytest.skip("Clang writes an asm label as a quoted symbol name, so it never reaches the assembler as a "
                    "directive; the CI toolchain is GCC")
    outcome = _build([FIXTURES / name], tmp_path / "run")
    _record("REFUSED", fixture=name, tool="fw.build", succeeded=outcome.succeeded, summary=outcome.summary)
    assert not outcome.succeeded and REFUSED in outcome.summary and MUST_REFUSE[name] in outcome.summary
    assert not outcome.references  # refused before any step: nothing compiled, no log
    assert not list((tmp_path / "run").rglob("*.o")) and not list((tmp_path / "run").rglob("*.log"))


@needs("cc")
@pytest.mark.parametrize("bracket", ['"{}"', "<{}>"])
def test_an_include_of_the_reference_driver_by_absolute_path_is_refused(bracket, tmp_path):
    seat = tmp_path / "seat" / "drv.c"
    seat.parent.mkdir()
    seat.write_text(f'#include "nirmaan_hal.h"\n#include {bracket.format(REFERENCE)}\n', encoding="utf-8")
    outcome = _build([seat], tmp_path / "run")
    _record("REFUSED", fixture=f"absolute include {bracket.format('<reference driver>')}", tool="fw.build",
            succeeded=outcome.succeeded, summary=outcome.summary.replace(str(REPO), "<checkout>"))
    assert not outcome.succeeded and "an absolute path" in outcome.summary and not outcome.references


@needs("cc", "verilator", "make")
def test_fw_test_refuses_before_it_compiles_or_runs_anything(tmp_path):
    backend, why = select_backend("fw.test", {})
    assert backend is not None, why
    outcome = execute(backend, {"sources": str(FIXTURES / "include_dotdot.c"), "rtl": str(RTL),
                                "top": "axi4_lite_regs", "workdir": str(tmp_path / "run")})
    _record("REFUSED", fixture="include_dotdot.c", tool="fw.test", succeeded=outcome.succeeded,
            summary=outcome.summary)
    assert not outcome.succeeded and REFUSED in outcome.summary and not outcome.references
    assert not (tmp_path / "run" / "cosim").exists()


@needs("cc")
def test_a_runner_only_canary_reaches_no_log_excerpt_or_record(tmp_path):
    """Decision 4, item 3: a run with a runner-only canary, by each route; the canary is in nothing it leaves."""
    value = secrets.token_hex(16)
    canary = tmp_path / "canary" / "credential"
    canary.parent.mkdir()
    canary.write_text(f'"{value}"\n', encoding="utf-8")
    canary.chmod(0o600)
    routes = {"absolute": f'#include "{canary}"\n',
              "computed": f'#define WHERE "{canary}"\n#include WHERE\n',
              "assembler": f'__asm__(".incbin \\"{canary}\\"");\n'}
    seen = []
    for route, line in routes.items():
        seat = tmp_path / route / "drv.c"
        seat.parent.mkdir()
        seat.write_text(f'#include "nirmaan_hal.h"\n{line}int seat_driver_ok(void);\nint seat_driver_ok(void) {{ return 0; }}\n', encoding="utf-8")
        run = tmp_path / route / "run"
        outcome = _build([seat], run)
        left = [p for p in run.rglob("*") if p.is_file() and value in p.read_text(encoding="utf-8", errors="replace")]
        text = json.dumps({"summary": outcome.summary, "data": outcome.data}, default=str)
        seen.append({"route": route, "refused": REFUSED in outcome.summary, "canary_in_files": len(left),
                     "canary_in_record": value in text})
        assert REFUSED in outcome.summary and not outcome.references
        assert not left and value not in text
    _record("CANARY", routes=seen)


@needs("cc")
def test_the_object_screen_runs_the_compile_screen_first(tmp_path):
    hits = object_screen.screen([FIXTURES / "include_dotdot.c"], {FIXTURES / "include_dotdot.c"}, tmp_path / "s")
    assert [h.rule for h in hits] == ["reach"] and REFUSED in hits[0].detail
    assert not list((tmp_path / "s").rglob("*.o"))


# --- Decision 4, item 4: every committed C file the backends compile keeps its build --------------------------------


def _groups() -> list[list[Path]]:
    """Every committed C file and header the backends compile, grouped as their jobs name them: each folder's
    files together, a held-out test with the reference driver it is compiled with."""
    folders = sorted({p.parent for p in [*FW.rglob("*.[ch]"), *(REPO / "evals").rglob("*.[ch]"),
                                         *(REPO / "tests" / "fixtures" / "gate_integrity").glob("*.c")]}
                     - {FIXTURES, FW / "screen"})  # the screen fixtures: must-refuse inputs, never built
    groups = []
    for folder in folders:
        files = sorted(folder.glob("*.[ch]"))
        if folder.parts[-2:] in (("firmware", "axi4_lite"), ("flow", "axi4_lite")):
            files += sorted((FW / "axi4_lite").glob("axi4_lite_regs_drv.[ch]"))
            files.append(FW / "axi4_lite" / "axi4_lite_regs_map.h")
        groups.append(files)
    return groups


@needs("cc")
def test_every_committed_c_file_passes_the_screen(tmp_path):
    """So no committed fixture, reference answer or held-out test changes its result: the screen lets each one
    through, and the build then runs exactly the steps it ran before."""
    passed = []
    for n, files in enumerate(_groups()):
        names = tuple(map(str, files))
        flags = firmware.compile_flags("cc", (), names, firmware.HARNESS)
        work = tmp_path / str(n)
        work.mkdir()
        problem = compile_screen.screen(flags, names, names, (firmware.HARNESS,), work)
        assert problem is None, (names, problem)
        passed += [str(f.relative_to(REPO)) for f in files]
    _record("PASSED", files=len(set(passed)))
    assert any("held_out_test.c" in f for f in passed) and any(f.endswith("axi4_lite_regs_drv.c") for f in passed)


def test_the_screen_changes_no_fingerprint():
    """Decision 4, item 4 (gate WF25): the screen sits in no file a fingerprint digests and in no tool definition,
    so the default and whole-flow fingerprints are what they were; the gate changed without a fingerprint change
    (docs/GATE_INTEGRITY.md, section 3)."""
    from nirmaan.company.tools import TOOLS
    from nirmaan.runtime import harness

    digested = {*harness.CODE, *harness.LOOP_CODE, *harness.FLOW_CODE}
    for rel in ("nirmaan/integrations/compile_screen.py", "nirmaan/integrations/firmware.py",
                "nirmaan/integrations/firmware_riscv.py", "nirmaan/evals/object_screen.py"):
        assert rel not in digested, rel
    assert not any("compile screen" in json.dumps(spec.model_dump(mode="json")) for spec in TOOLS)


# --- Gate SC9 (council record 2026-11-19, decision 2, items 1 and 2): the register block flow ------------------------
#
# Item 1: the compile reach is closed for every check that compiles seat C in that flow, the firmware stage's own
# before-review checks included. Item 2: the object screen of gate WF16 is not called met until the #line route of
# fact 9 is tested and, if open, closed. The author's proposed conditions for staying with the screen (pending a security record)
# (docs/COMPILE_SCREEN.md, "Decision 4, item 5: the register block") add the two routes a seat header can carry into
# the held-out test's own compile in checks 5 and 6.

REGS_FLOW = "flow/axi4-lite-regs-driver"
FLOW_HELD_OUT = REPO / "evals" / "flow" / "axi4_lite" / "held_out_test.c"
#: Every tool that compiles seat-written C (the driver, the driver test).
C_TOOLS = ("fw.build", "fw.test", "fw.cross_build", "fw.soc_test")
#: The two routes a seat's driver header can carry into the held-out test's compile, and the words of the refusal.
HEADER_ROUTES = {"seat_header_incbin.h": "asm statement", "seat_header_line.h": "#line"}


def _register_block_tools() -> tuple[set[str], set[str]]:
    """The tools of the flow's held-out checks, and of its firmware stage's before-review checks (the workflow it
    plans, ``nirmaan.company.workflows``), as data, not as a list typed here."""
    from nirmaan.company.workflows import WORKFLOWS
    from nirmaan.evals import load_cases

    [case] = [c for c in load_cases(REPO / "evals", flow="whole") if c.id == REGS_FLOW]
    stage = {t for wf in WORKFLOWS for s in wf.stages if s.id == "firmware" for e in s.evidence
             if e.before_review for t in e.tools}
    return {h.tool for h in case.held_out}, stage


def test_every_check_that_compiles_seat_c_in_the_register_block_flow_runs_the_screen(tmp_path):
    """Decision 2, item 1: each backend of each tool the flow's held-out checks and its firmware stage's own checks
    run, among the tools that compile seat C, refuses an include of the reference driver by an absolute path in its
    check, before any step. Without a tool's compiler the screen refuses too (it cannot list the compiler's folders),
    so the check fails closed; CI has every compiler."""
    from nirmaan.integrations import firmware_riscv  # noqa: F401  (registers the RISC-V backends)
    from nirmaan.integrations.eda import Job, backends_for

    held_out, stage = _register_block_tools()
    assert {"fw.build", "fw.test"} <= held_out and set(C_TOOLS) <= stage  # the flow's seat C, judged and staged
    assert not (held_out | stage) - set(C_TOOLS) - {"simulator.run", "regmap.verify"}  # no other tool in the flow
    seat = tmp_path / "seat" / "drv.c"
    seat.parent.mkdir()
    seat.write_text(f'#include "nirmaan_hal.h"\n#include "{REFERENCE}"\n', encoding="utf-8")
    seen = []
    for tool in C_TOOLS:
        assert backends_for(tool), tool
        for backend in backends_for(tool):
            assert backend.check is not None, (tool, backend.name)
            work = tmp_path / f"{tool}-{backend.name}"
            work.mkdir()
            job = Job(tool, {"sources": str(seat), "rtl": str(RTL)}, work, (str(seat),), "axi4_lite_regs")
            problem = backend.check(job)
            seen.append({"tool": tool, "backend": backend.name, "refused": bool(problem and REFUSED in problem)})
            assert problem and REFUSED in problem, (tool, backend.name, problem)
            assert not list(work.rglob("*.o")), (tool, backend.name)
    _record("FLOW-TOOLS", checks=seen)


def test_the_line_route_of_fact_9_is_refused_before_the_object_screen_compiles(tmp_path):
    """Decision 2, item 2: a #line line followed by asm would make the asm look like another file's, which the
    object screen's own asm rule skips. The compile screen the object screen runs first refuses the #line line,
    so nothing is compiled and the asm rule is never asked."""
    fixture = FIXTURES / "line_asm.c"
    hits = object_screen.screen([fixture], {fixture}, tmp_path / "s")
    _record("REFUSED", fixture="line_asm.c", tool="object screen", hits=[h.rule for h in hits],
            summary=hits[0].detail if hits else "")
    assert [h.rule for h in hits] == ["reach"] and REFUSED in hits[0].detail and "#line" in hits[0].detail
    assert not list((tmp_path / "s").rglob("*.o"))


def _seat_with_header(tmp_path: Path, header: str) -> list[Path]:
    """A seat's driver for the register block flow: the reference driver and map, with ``header`` as its driver
    header, and the flow's held-out test beside them, as checks 5 and 6 name them."""
    seat = tmp_path / "seat"
    seat.mkdir()
    for name in ("axi4_lite_regs_drv.c", "axi4_lite_regs_map.h"):
        (seat / name).write_bytes((FW / "axi4_lite" / name).read_bytes())
    (seat / "axi4_lite_regs_drv.h").write_bytes((FIXTURES / header).read_bytes())
    return [seat / "axi4_lite_regs_drv.c", seat / "axi4_lite_regs_drv.h", seat / "axi4_lite_regs_map.h",
            FLOW_HELD_OUT]


@needs("cc", "verilator", "make")
@pytest.mark.parametrize("header", sorted(HEADER_ROUTES))
def test_a_seat_header_route_into_the_held_out_tests_compile_is_refused(header, tmp_path):
    """The author's proposed condition for the screen (pending a security record): each route a seat header can carry into the held-out test's own compile
    (checks 5 and 6 compile the held-out test with the seat's header) is refused by fw.test before it compiles or
    runs anything, and by the object screen the screened scorers run first."""
    sources = _seat_with_header(tmp_path, header)
    backend, why = select_backend("fw.test", {})
    assert backend is not None, why
    outcome = execute(backend, {"sources": ",".join(map(str, sources)), "rtl": str(RTL), "top": "axi4_lite_regs",
                                "workdir": str(tmp_path / "run")})
    seat = set(sources[:3])
    hits = object_screen.screen(sources, seat, tmp_path / "s")
    # The held-out test's own compile alone (the header, the map and the test, no seat C file): refused there too.
    alone = tuple(map(str, sources[1:]))
    (tmp_path / "alone").mkdir()
    held_out_only = compile_screen.screen(firmware.compile_flags("cc", (), alone, firmware.HARNESS), alone, alone,
                                          (firmware.HARNESS,), tmp_path / "alone")
    _record("REFUSED", fixture=header, tool="fw.test and object screen", succeeded=outcome.succeeded,
            summary=outcome.summary.replace(str(REPO), "<checkout>"), hits=[h.rule for h in hits],
            held_out_only=(held_out_only or "").replace(str(REPO), "<checkout>"))
    assert held_out_only and REFUSED in held_out_only and HEADER_ROUTES[header] in held_out_only
    assert not list((tmp_path / "alone").rglob("*.o"))
    assert not outcome.succeeded and REFUSED in outcome.summary and HEADER_ROUTES[header] in outcome.summary
    assert not outcome.references and not (tmp_path / "run" / "cosim").exists()
    assert not list((tmp_path / "run").rglob("*.o"))
    # The object screen leaves asm statements to its own rule (``statements=False``), so the asm route may stop
    # there instead of in the compile screen it runs first; either is a refusal before anything is linked or run.
    assert hits and hits[0].rule in ("reach", "asm"), hits
    assert hits[0].rule == "asm" or REFUSED in hits[0].detail
