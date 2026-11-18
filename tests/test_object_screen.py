"""Gate WF16: the object screen, a tripwire on seat-written C before a whole-flow check links it.

Council record ``council/records/2026-11-17-g3-whole-flow-cases.md``, second addendum (2026-11-18), decision 2,
items 2 to 5. The screen (``nirmaan.evals.object_screen``) runs in the whole-flow judge path only: a check that
names a screened scorer (``scorers.SCREENED``) runs the unchanged ``held-out-run`` or ``must-fail`` scorer only
when the screen finds nothing. This pull request adds the screen and its scorers; the register block case's checks
take them in the next one. No tool definition, no ``harness.CODE`` file and no harness code changes, so no
fingerprint moves, and no single-seat case is screened.

What this file holds, and what ``evals/flow/object_screen_record.json`` records from one CI run (Linux, the
toolchain the trials use; each tool-backed test prints one ``OBJECT-SCREEN`` line into the CI log):

* the allow list: the undefined symbols of every committed host fixture, reference answer and held-out test, read
  with the screen's own compile (``OBJECT-SCREEN-SYMBOLS``);
* one must-refuse fixture per refused construct, and the simulator clock probe, each refused
  (``OBJECT-SCREEN-REFUSED``); and the clock probe refused through the judge path, as the seat's driver test under
  the register block case's check 7 with the screened scorer, with nothing linked or run in the judge
  (``OBJECT-SCREEN-JUDGE``);
* the address-arithmetic probe, which the screen passes, with what it really read under ``fw.test``
  (``ADDRESS-PROBE``): the screen is a tripwire, not confinement.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import load_cases, object_screen, scorers
from nirmaan.evals.object_screen import HARNESS_CALLS, LIBRARY_CALLS, REFUSED, Hit, screen
from nirmaan.integrations.eda import execute, run_nonce, select_backend
from nirmaan.models import HeldOutCheck, Score, ScoreStatus
from nirmaan.regmap import load_map, lower
from nirmaan.runtime import harness

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
RECORD = EVALS / "flow" / "object_screen_record.json"
FW = REPO / "tests" / "fixtures" / "fw"
SCREEN_FIXTURES = FW / "screen"
CLOCK_PROBE = FW / "reach" / "simulator_clock_probe.c"
ADDRESS_PROBE = FW / "reach" / "address_arithmetic_probe.c"
RTL = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
LINUX = pytest.mark.skipif(sys.platform != "linux", reason="the allow list and the record are the CI toolchain's "
                                                            "(Linux); another host's C library names differ")


def _answers(folder: Path) -> list[Path]:
    """A fixture folder's C, less the strict fixtures of gate WF15, which reach outside the HAL on purpose."""
    return sorted(p for p in folder.glob("*.c") if "_strict_" not in p.name)


#: The committed host C the allow list is taken from, as groups linked together: each fixture folder's drivers and
#: tests, with the held-out tests beside the register block driver they include. (The gate-integrity fixtures are
#: the gate's own must-fail inputs, the reach probes are probes, and the strict fixtures of gate WF15 reach outside
#: the HAL on purpose: none is an answer.)
BASIS = {
    "axi4_lite": [*_answers(FW / "axi4_lite"), EVALS / "firmware" / "axi4_lite" / "held_out_test.c",
                  EVALS / "flow" / "axi4_lite" / "held_out_test.c"],
    "apb_regs": sorted((FW / "apb_regs").glob("*.c")),
    "apb_csr": sorted((FW / "apb_csr").glob("*.c")),
    "axil_timer": sorted((FW / "axil_timer").glob("*.c")),
}
#: Each must-refuse input, and the rules it must hit (more may hit).
REFUSES = {
    "undefined_fopen.c": {"undefined"},
    "weak_reference.c": {"undefined"},
    "asm_label.c": {"asm", "undefined"},
    "inline_asm.c": {"asm"},
    "asm_macro.c": {"asm"},
    "collision_library.c": {"collision"},
    "collision_harness.c": {"collision"},
    "constructor.c": {"before-main"},
    "init_array_section.c": {"before-main"},
    "indirect_function.c": {"before-main"},
    "destructor.c": {"after-main"},
    "simulator_clock_probe.c": {"asm", "undefined"},
}
C_TOOLS = ("fw.build", "fw.test")


def _record() -> dict | None:
    return json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.is_file() else None


def _refused_path(name: str) -> Path:
    return CLOCK_PROBE if name == CLOCK_PROBE.name else SCREEN_FIXTURES / name


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO))


# --- Where the screen sits (no tools) --------------------------------------------------------------------------


def test_no_single_seat_case_is_screened():
    """Committed single-seat cases keep the scorers they had, so they are judged as before."""
    cases = load_cases(EVALS)
    assert cases
    assert not [(c.id, k.name) for c in cases for k in c.held_out if k.scorer in scorers.SCREENED]


def test_the_screened_scorers_wrap_the_unchanged_ones():
    assert scorers.SCREENED == {"screened-held-out-run": "held-out-run", "screened-must-fail": "must-fail"}
    specs = {name: scorers.scorer_spec(name) for name in (*scorers.SCREENED, *scorers.SCREENED.values())}
    missing = [name for name, spec in specs.items() if spec is None]
    assert not missing, f"scorers not registered: {missing}"
    assert specs["held-out-run"].fn is scorers.held_out_run  # type: ignore[union-attr]
    assert specs["must-fail"].fn is scorers.must_fail  # type: ignore[union-attr]
    assert all(spec.requires_tool for spec in specs.values())  # type: ignore[union-attr]


def test_no_fingerprint_reads_the_screen(monkeypatch):
    """The screen's code is in no fingerprint list, and the default, attempts-3 and tools-in-loop fingerprints (and
    their whole-flow forms) read only those lists and the tool definitions, which WF16 leaves alone. The values on
    ``main`` and on this branch are compared in the pull request."""
    mine = {"nirmaan/evals/object_screen.py", "nirmaan/evals/scorers.py"}
    assert not mine & {*harness.CODE, *harness.LOOP_CODE, *harness.FLOW_CODE}
    read: list[tuple[str, ...] | None] = []
    real = harness.code_digests

    def spy(files=None):
        read.append(files)
        return real(files)

    monkeypatch.setattr(harness, "code_digests", spy)
    monkeypatch.setattr(harness, "tool_pins", lambda: {})
    for variant in ("default", "attempts-3", "tools-in-loop"):
        for flow in ("seat", "whole"):
            harness.fingerprint(cli="2.1.325", variant=variant, flow=flow)
    files = {f for listed in read for f in (harness.CODE if listed is None else listed)}
    assert files and not files & mine


class _Ctx:
    """Just what the screened scorers read of a ScoreContext."""

    def __init__(self, check: HeldOutCheck, seat: list[Path], work: Path):
        self.check, self.repo, self.work, self._seat = check, REPO, work, seat

    def seat_files(self, kinds):
        class _Art:
            def __init__(self, path: Path):
                self.location = str(path)
        return [_Art(p) for p in self._seat]


def _check(tool: str = "fw.test") -> HeldOutCheck:
    return HeldOutCheck(name="7. a check", scorer="screened-must-fail", tool=tool,
                        seat_files={"sources": ("driver", "driver_test")},
                        case_files={"rtl": ("tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v",)})


def test_a_refusal_is_the_checks_failed_verdict_and_nothing_runs(tmp_path, monkeypatch):
    seat = [FW / "axi4_lite" / "axi4_lite_regs_drv.c", CLOCK_PROBE]
    monkeypatch.setattr(object_screen, "screen", lambda *a, **k: [Hit("undefined", "x.c", "names y")])

    def inner(ctx):
        raise AssertionError("a refused check must run nothing")

    for staged in (False, True):
        score = scorers._screened(inner, staged)(_Ctx(_check(), seat, tmp_path / str(staged)))
        assert score.status is ScoreStatus.FAILED and score.runs == () and score.failed_runs == ()
        assert score.summary.startswith(REFUSED) and "x.c: undefined: names y" in score.summary
        assert "tripwire" in score.summary and "not confinement" in score.summary


def test_a_clean_screen_returns_the_inner_score_unchanged(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(object_screen, "screen", lambda sources, mine, where, **k: seen.append((sources, mine)) or [])
    given = Score(scorer="screened-must-fail", name="7. a check", status=ScoreStatus.PASSED, summary="ran",
                  runs=("run-1",))
    seat = [FW / "axi4_lite" / "axi4_lite_regs_drv.c", FW / "axi4_lite" / "axi4_lite_regs_test.c"]
    assert scorers._screened(lambda ctx: given, False)(_Ctx(_check(), seat, tmp_path / "a")) is given
    assert scorers._screened(lambda ctx: given, True)(_Ctx(_check(), seat, tmp_path / "b")) is given
    in_place, staged = seen
    assert in_place == (seat, set(seat))  # as held-out-run passes them
    assert [p.name for p in staged[0]] == [p.name for p in seat] and all(p.parent.name == "src" for p in staged[0])
    # A check the seat gives no C is not screened at all.
    rtl = [RTL / "axi4_lite_regs.v"]
    assert scorers._screened(lambda ctx: given, False)(_Ctx(_check("simulator.run"), rtl, tmp_path / "c")) is given
    assert len(seen) == 2


def test_asm_is_found_by_the_preprocessors_line_markers_only_in_the_seats_files(tmp_path):
    mine, theirs = (tmp_path / "mine.c").resolve(), (tmp_path / "theirs.h").resolve()
    text = (f'# 1 "{mine}"\nint a;\n# 1 "{theirs}" 1\n__asm__("x");\n# 3 "{mine}" 2\nint b = 1;\n'
            f'static const char *s = "asm";\n  __asm__ __volatile__("");\n')
    assert object_screen.asm_lines(text, {mine}) == [5]


# --- The record (no tools) -------------------------------------------------------------------------------------


def _basis_library(symbols: dict[str, dict[str, list[str]]]) -> set[str]:
    """The C library names the basis leaves undefined: every undefined name no object of its group defines,
    less the harness's functions."""
    names: set[str] = set()
    for group, files in BASIS.items():
        defined = {s for f in files for s in symbols[_rel(f)]["defined"]}
        names |= {s for f in files for s in symbols[_rel(f)]["undefined"]} - defined
    return names - HARNESS_CALLS


def test_the_allow_list_is_the_recorded_runs():
    """Gate WF16: the allow list from a recorded run; every must-refuse input recorded refused; check 7 recorded
    refusing the clock probe; the address-arithmetic probe recorded with its real result."""
    record = _record()
    assert record is not None, "the screen's recorded CI run is missing (evals/flow/object_screen_record.json)"
    assert record["format"] == "nirmaan.object-screen-record"
    assert re.fullmatch(r"https://github\.com/\S+/actions/runs/\d+", record["run"])
    assert re.fullmatch(r"[0-9a-f]{40}", record["head"])
    assert set(record["symbols"]) == {_rel(f) for files in BASIS.values() for f in files}
    assert set(LIBRARY_CALLS) == _basis_library(record["symbols"])
    assert set(record["refused"]) == set(REFUSES)
    for name, hits in record["refused"].items():
        assert REFUSES[name] <= {h["rule"] for h in hits}, name
    judge = record["judge"]
    assert judge["submitted"] and judge["status"] == "failed" and judge["runs"] == []
    assert judge["summary"].startswith(REFUSED)
    assert set(record["address_probe"]) == {"axi4_lite_regs.v", "axi4_lite_regs_lat2.v"}


# --- On the CI toolchain (tools) -------------------------------------------------------------------------------


def _include(group: str, work: Path) -> tuple[str, ...]:
    """The include folders a group's files are built with: the driver headers, or the generated map header."""
    if group != "apb_csr":
        return (str(FW / "axi4_lite"),)
    generated = work / "regmap"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / "apb_csr_map.h").write_text(
        lower(load_map(REPO / "tests" / "fixtures" / "rtl" / "apb_csr" / "register_map.json"), "c-header"),
        encoding="utf-8")
    return (str(generated),)


@LINUX
@needs("cc")
@pytest.mark.parametrize("group", sorted(BASIS))
def test_the_basis_passes_and_its_symbols_are_recorded(group, tmp_path, capsys):
    """The allow list's source: each file's undefined and defined names, from the screen's own compile. Each file
    is then screened as a seat's would be, with the driver interface its group defines (a group holds alternative
    drivers and tests, which are never linked all together)."""
    files, include = BASIS[group], _include(group, tmp_path)
    symbols, tables = {}, {}
    for n, f in enumerate(files):
        where = tmp_path / f"read-{n}"
        screen([f], {f}, where, include=include, allowed=frozenset())  # builds the object; the verdict is below
        objects = list((where / "obj").glob("*.o"))
        assert len(objects) == 1, f"{_rel(f)} did not build"
        tables[f] = object_screen.read_object(objects[0], where)
        symbols[_rel(f)] = {"undefined": sorted(tables[f].undefined | tables[f].weak_undefined),
                            "defined": sorted(tables[f].defined)}
    with capsys.disabled():
        print(f"\nOBJECT-SCREEN-SYMBOLS {json.dumps({'group': group, 'symbols': symbols}, sort_keys=True)}")
    interface = frozenset(s for t in tables.values() for s in t.defined) - {"nirmaan_fw_test"}
    for n, f in enumerate(files):
        hits = screen([f], {f}, tmp_path / f"screen-{n}", include=include, allowed=object_screen.ALLOWED | interface)
        assert not hits, [h.text() for h in hits]
    record = _record()
    if record is not None:
        assert {k: record["symbols"][k] for k in symbols} == symbols


@LINUX
@needs("cc")
@pytest.mark.parametrize("name", sorted(REFUSES))
def test_each_must_refuse_input_is_refused(name, tmp_path, capsys):
    path = _refused_path(name)
    hits = screen([path], {path}, tmp_path)
    line = {"input": _rel(path), "hits": [{"rule": h.rule, "detail": h.detail} for h in hits]}
    with capsys.disabled():
        print(f"\nOBJECT-SCREEN-REFUSED {json.dumps(line, sort_keys=True)}")
    assert REFUSES[name] <= {h.rule for h in hits}, line
    record = _record()
    if record is not None:
        assert record["refused"][name] == line["hits"]


JUDGE_TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make")


@LINUX
@JUDGE_TOOLS
def test_check_7_refuses_the_clock_probe_as_the_seats_driver_test(nirmaan_org, fixed_clock, tmp_path, capsys):
    """The judge path itself: the whole-flow case's check 7 under the screened scorer, with the reference driver and
    the simulator clock probe as the seat's driver test, fails by the screen's refusal and runs no fw.test of the
    judge's."""
    import test_whole_flow_controls as controls
    from nirmaan.evals.runner import evaluate

    fw = "tests/fixtures/fw/axi4_lite"
    control = {"id": "screen-clock-probe", "case": "flow/axi4-lite-regs-driver", "what": "WF16",
               "seat": [{"path": f"{fw}/axi4_lite_regs_map.h", "kind": "driver", "as": "axi4_lite_regs_map.h"},
                        {"path": f"{fw}/axi4_lite_regs_drv.h", "kind": "driver"},
                        {"path": f"{fw}/axi4_lite_regs_drv.c", "kind": "driver", "as": "axi4_lite_regs_drv.c"},
                        {"path": _rel(CLOCK_PROBE), "kind": "driver_test", "as": "axi4_lite_regs_test.c"}],
               "checks": []}
    flow = {c.id: c for c in load_cases(EVALS, flow="whole")}[control["case"]]
    check7 = {**flow.held_out[6].model_dump(mode="json"), "scorer": "screened-must-fail"}
    control["checks"] = [{"inline": check7, "expect": "failed"}]
    case = controls._stand_in(control, flow, tmp_path)
    result, engine = evaluate(nirmaan_org, case, controls._seat(control), replay=False, repo=REPO,
                              sandbox=tmp_path / "box", clock=fixed_clock)
    [score] = result.scores
    line = {"submitted": result.submitted, "status": score.status.value, "summary": score.summary,
            "runs": list(score.runs)}
    with capsys.disabled():
        print(f"\nOBJECT-SCREEN-JUDGE {json.dumps(line, sort_keys=True)}")
    assert result.submitted, result.detail
    assert score.status is ScoreStatus.FAILED and score.summary.startswith(REFUSED) and not score.runs, line
    runs = list(engine.state.tool_runs.values())
    judged = [r for r in runs if "eval-scorer" in r.actor]  # Actor.label: "<name>@<role>"
    assert runs and not judged, [r.id for r in judged]  # the seat's own gate ran; the judge ran nothing
    record = _record()
    if record is not None:
        assert record["judge"] == line


_PROBE_LINE = re.compile(r"PASS (address_probe,\S+)$", re.M)


@LINUX
@needs("cc", "verilator", "make")
def test_the_address_arithmetic_probe_passes_the_screen_and_its_reach_is_recorded(tmp_path, capsys):
    """Decision 2, item 3: the screen stops names, not address arithmetic. The probe passes the screen; under
    fw.test it reads, from the harness's own code addresses, whatever it can. Its result is recorded as it is."""
    hits = screen([ADDRESS_PROBE], {ADDRESS_PROBE}, tmp_path / "screen")
    assert not hits, [h.text() for h in hits]
    chosen, why = select_backend("fw.test", {})
    assert chosen, why
    got = {}
    for rtl in (RTL / "axi4_lite_regs.v", RTL / "variants" / "axi4_lite_regs_lat2.v"):
        run = execute(chosen, {"sources": str(ADDRESS_PROBE), "rtl": str(rtl), "top": "axi4_lite_regs"})
        log = Path(run.references[0]).read_text(encoding="utf-8", errors="replace") if run.references else ""
        m = _PROBE_LINE.search(log)
        fields = dict(kv.split("=", 1) for kv in m[1].split(",")[1:]) if m else {}
        nonce = run_nonce(log) or ""
        found = fields.pop("nonce8", "none")
        fields["nonce8_is_the_runs"] = str(bool(nonce) and found == nonce[:8]).lower()
        got[rtl.name] = {"succeeded": run.succeeded, "summary": re.sub(r"\S*/", "", run.summary), **fields}
        with capsys.disabled():
            print(f"\nADDRESS-PROBE {json.dumps({'rtl': rtl.name, **got[rtl.name]}, sort_keys=True)}")
        assert m or not run.succeeded, run.summary
    record = _record()
    if record is not None:
        assert record["address_probe"] == got
