"""The whole-flow judge controls (G3, council record 2026-11-17, decision 2; gates WF4, WF5 and WF14), by replay.

Each control in ``evals/flow/controls.json`` is a seat answer made of committed files (a reference, a mutant, a
conforming variant or a deliberately wrong fixture) and the whole-flow case's own held-out checks it must pass or
fail. It runs as a single-seat case through the real runner, gates, scorers and broker (``evaluate``), with no
model call and no change to ``runner.py``: the seat replays the files, its own before-review checks run, and the
judge rules. A control's seat reaches review, so a check that fails it is the judge's verdict, never a gate's; the
one exception is stated in the manifest (``reaches_review: false``): a mutant the seat's own gate already refuses.

Where it runs: the tool-backed tests need the EDA tools. CI's test job names every one of them in
``NIRMAAN_REQUIRE_EDA``, so there a missing tool fails the test rather than skipping it. Each control prints one
``FLOW-CONTROL`` line (its verdicts and run summaries) into the CI log; ``evals/flow/controls_record.json`` keeps
those lines from a named CI run, and the test holds every later run to the verdicts it records.

A control may also say which RTL the flow's RTL stage ended in (``upstream_rtl``): the base case's upstream RTL is
replaced by a copy of it under the name of the file it stands in for, so the seat's own checks run on it before
review, as they would in a whole flow. Check 5 runs here only on an RTL a control puts in place (``rtl``).

Gate WF15 (council record 2026-11-17, second addendum 2026-11-18, decision 1): the strict fixtures print what they
timed on lines of their own (``STRICT-FIXTURE ...``); the ``FLOW-CONTROL`` line carries those lines per check, a
check may name the counts it expects (``timing``) and the one check of a driver test it must fail by
(``fails_by``), and a control that never reaches review may name what refused it (``refused_by``, its gate runs are
on the line). The record keeps the counts, and later runs are held to them.

Gate WF16 (the same addendum, decision 2): the register block's checks 4 to 7 run after the object screen. A check
that names ``screen_refuses`` must fail by the screen's refusal, with no run; every other check must not be refused,
so a refusal never stands in for a failure a control expects. The strict fixtures on the simulator's clock are
refused there; their siblings on the address-arithmetic route, which the screen leaves open, are the live controls.

What waits for the whole-flow runner: replaying the reference flow through every seated stage, a flow with a
planted upstream fault, and check 5 on the RTL another stage made.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import ReplayLLM, load_case, load_cases
from nirmaan.evals.object_screen import REFUSED
from nirmaan.evals.runner import evaluate
from nirmaan.integrations.eda import run_nonce
from nirmaan.integrations.firmware import parse_fw_test
from nirmaan.models import EvalCase, HeldOutCheck
from nirmaan.runtime import ModelRuntime

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
MANIFEST = EVALS / "flow" / "controls.json"
RECORD = EVALS / "flow" / "controls_record.json"
#: The single-seat case each control stands in for: its request, seat, upstream documents and gates.
BASES = {("flow/axil-timer", "rtl"): EVALS / "rtl" / "axil_timer.json",
         ("flow/axi4-lite-regs-driver", "rtl"): EVALS / "rtl" / "axi4_lite_regs.json",
         ("flow/axi4-lite-regs-driver", "driver"): EVALS / "firmware" / "axi4_lite_driver.json"}
#: The firmware seat reads the whole-flow case's own copy of the programming interface.
DRIVER_API = ("evals/firmware/axi4_lite/driver_api.md", "evals/flow/axi4_lite/driver_api.md")
TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make")


def _manifest() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["format"] == "nirmaan.flow-controls"
    return data["controls"]


CONTROLS = _manifest()


@pytest.fixture(scope="module")
def flows() -> dict[str, EvalCase]:
    return {c.id: c for c in load_cases(EVALS, flow="whole")}


def _checks(control: dict, flow: EvalCase) -> list[HeldOutCheck]:
    """The control's checks: the whole-flow case's own, with the RTL or mutants it names in their place."""
    out = []
    for n, spec in enumerate(control["checks"], start=1):
        check = dict(spec["inline"]) if "inline" in spec else flow.held_out[spec["check"] - 1].model_dump(mode="json")
        # The file a mutant stands in for: the RTL the control puts in place, else the one the check's mutants name.
        original = spec.get("rtl") or next(iter(check.get("mutants") or {}), None)
        if "rtl" in spec:
            check["case_files"] = {**check.get("case_files", {}), "rtl": [spec["rtl"]]}
            # A check that takes the flow's RTL from the seat (check 5) takes the one the control puts in place.
            check["seat_files"] = {k: v for k, v in check.get("seat_files", {}).items() if k != "rtl"}
            check["seat_entries"] = {k: v for k, v in check.get("seat_entries", {}).items()
                                     if tuple(v) != ("rtl_source",)}
        mutants = spec.get("mutants", [m for files in (check.get("mutants") or {}).values() for m in files])
        if mutants:
            assert original, f"{control['id']}: mutants with no file to stand in for"
            check["mutants"] = {original: mutants}
        check["name"] = f"{check['name']} [{control['id']} {n}]"
        out.append(HeldOutCheck.model_validate(check))
    return out


def _stand_in(control: dict, flow: EvalCase, tmp_path: Path) -> EvalCase:
    """A single-seat case: the base case's request, seat and upstream, the control's checks, no skill."""
    kind = "driver" if any(f["kind"] == "driver" for f in control["seat"]) else "rtl"
    data = json.loads(BASES[(control["case"], kind)].read_text(encoding="utf-8"))
    for files in data.get("upstream", {}).values():
        for f in files:
            if f["path"] == DRIVER_API[0]:
                f["path"] = DRIVER_API[1]
            elif f["kind"] == "rtl_source" and "upstream_rtl" in control:
                # The flow's RTL stage ended in this RTL: a copy under the name of the file it stands in for.
                staged = tmp_path / "upstream-rtl" / Path(f["path"]).name
                staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / control["upstream_rtl"], staged)
                f["path"] = str(staged)
    data.update(id=f"control/{control['id']}", skills=[], reference=[],
                held_out=[c.model_dump(mode="json") for c in _checks(control, flow)])
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_case(path)


def _seat(control: dict) -> ModelRuntime:
    files = [(f.get("as", Path(f["path"]).name), f["kind"], (REPO / f["path"]).read_text(encoding="utf-8"),
              f.get("entry")) for f in control["seat"]]
    return ModelRuntime(ReplayLLM(files), runtime_id="flow-control")


def _bus(engine, run_ids) -> list[str]:
    """The bus transfers a fw.test run's log shows, without the run's nonce."""
    lines = []
    for run_id in run_ids:
        run = engine.state.tool_runs[run_id]
        log = Path(run.references[0]).read_text(encoding="utf-8", errors="replace") if run.references else ""
        lines += [re.sub(r"^FWTEST:\S+ ", "", ln) for ln in log.splitlines() if " BUS " in ln]
    return lines


def _logs(engine, run_ids) -> list[str]:
    out = []
    for run_id in run_ids:
        run = engine.state.tool_runs[run_id]
        out.append(Path(run.references[0]).read_text(encoding="utf-8", errors="replace") if run.references else "")
    return out


def _timings(engine, run_ids) -> list[str]:
    """What a strict fixture timed, from the lines of its own it printed (gate WF15), sorted."""
    return sorted(m for log in _logs(engine, run_ids) for m in re.findall(r"^STRICT-FIXTURE (.+)$", log, re.M))


def _how_it_failed(engine, run_id) -> dict:
    """A fw.test run's failed checks, its other errors (build, harness, forged lines), and whether it finished."""
    [log] = _logs(engine, [run_id])
    result = parse_fw_test(log, (1,))
    failed = [c["name"] for c in result.metrics["checks"] if not c["passed"]]
    nonce = re.escape(run_nonce(log) or "-")
    finished = bool(re.search(rf"FWTEST:{nonce} SUMMARY ", log) and re.search(rf"FWTEST:{nonce} END ", log))
    return {"failed": failed, "errors": [d.message for d in result.diagnostics if d.code not in failed],
            "finished": finished}


# --- The manifest (no tools) ------------------------------------------------------------------------------------


def test_every_control_names_a_whole_flow_case_its_checks_and_committed_files(flows):
    assert len({c["id"] for c in CONTROLS}) == len(CONTROLS)
    for control in CONTROLS:
        flow = flows[control["case"]]
        assert control["what"] and control["checks"]
        for f in control["seat"]:
            assert (REPO / f["path"]).is_file(), f["path"]
        for spec in control["checks"]:
            assert spec["expect"] in (("passed", "failed") if control.get("reaches_review", True) else ("not_run",))
            assert "inline" in spec or 1 <= spec["check"] <= len(flow.held_out)
            for path in [*([spec["rtl"]] if "rtl" in spec else []), *spec.get("mutants", [])]:
                assert (REPO / path).is_file(), path
        assert "upstream_rtl" not in control or (REPO / control["upstream_rtl"]).is_file()
        assert "refused_by" not in control or not control.get("reaches_review", True)
        assert _checks(control, flow)


def _uses(control: dict, path: str) -> bool:
    return any(f["path"] == path for f in control["seat"])


def test_the_controls_cover_what_the_record_rules(flows):
    """WF4, WF5 and WF14: the reference passes, each planted fault fails, the conforming RTL passes the checks on the
    flow's RTL, the range-accepting reference tests pass on both RTLs, a testbench written to one choice fails, and
    the wait probe passes on both RTLs."""
    def expects(path: str, check: int, verdict: str, **where) -> bool:
        return any(_uses(c, path) and any(s.get("check") == check and s["expect"] == verdict
                                          and all(s.get(k) == v for k, v in where.items()) for s in c["checks"])
                   for c in CONTROLS)

    for case_id in ("flow/axil-timer", "flow/axi4-lite-regs-driver"):
        flow = flows[case_id]
        mutants = {m for c in flow.held_out for files in c.mutants.values() for m in files}
        for mutant in mutants:  # every planted RTL fault fails the flow: the reference testbench, or its own gate
            assert expects(mutant, 1, "failed") or expects(mutant, 1, "not_run"), mutant
    rtl = "tests/fixtures/rtl/axi4_lite"
    lat2 = f"{rtl}/variants/axi4_lite_regs_lat2.v"
    assert expects(lat2, 1, "passed") and expects(lat2, 2, "passed")  # the conforming RTL, checks 1 and 2
    assert expects(f"{rtl}/axi4_lite_regs_tb.v", 3, "passed")  # the reference testbench on the reference RTL
    assert expects(f"{rtl}/variants/axi4_lite_regs_tb_strict2.v", 3, "failed")
    assert expects("tests/fixtures/rtl/axil_timer/axil_timer_tb_weak.v", 2, "failed")
    fw = "tests/fixtures/fw/axi4_lite"
    for wrong in ("axi4_lite_regs_map_wrong.h", "axi4_lite_regs_drv_swallowed_error.c",
                  "axi4_lite_regs_drv_all_strobes.c", "axi4_lite_regs_drv_sticky_response.c"):
        assert expects(f"{fw}/{wrong}", 6, "failed"), wrong
    ref = f"{fw}/axi4_lite_regs_drv.c"
    assert expects(ref, 6, "passed") and expects(ref, 6, "passed", rtl=lat2) and expects(ref, 7, "passed")
    for mutant in ("wstrb_ignored", "okay_unmapped"):
        assert expects(ref, 6, "failed", rtl=f"{rtl}/mutants/axi4_lite_regs_{mutant}.v"), mutant
    # WF14 (addendum 2026-11-18): the wait probe passes on both RTLs, with one transcript name for both runs.
    probe = [s for c in CONTROLS if _uses(c, f"{fw}/axi4_lite_regs_test_wait_probe.c") for s in c["checks"]]
    assert sorted((s.get("rtl"), s["expect"]) for s in probe) == [(f"{rtl}/axi4_lite_regs.v", "passed"),
                                                                  (lat2, "passed")]
    assert len({s.get("transcript") for s in probe} - {None}) == 1 and all(s.get("transcript") for s in probe)


def test_the_strict_fixtures_follow_every_route_to_a_cycle_count():
    """WF15 (second addendum 2026-11-18, decision 1, item 3: the control follows the channel) with WF16 in force.

    Each route by which a recorded probe reads a cycle count is either refused (recorded), or used by strict fixtures
    recorded failing: on a flow whose RTL stage ended in the conforming RTL, the strict driver test passes there and
    fails check 7 on the reference RTL by its one added check, with the same bus transfers, and the strict driver
    passes check 5 there and fails check 6. The simulator's clock: refused by the object screen in checks 4 to 7
    (the files stay). Address arithmetic from ``hal->read32``: open, so its strict fixtures are the live controls.
    The SoC's CYCLES register: refused before review."""
    rtl, fw = "tests/fixtures/rtl/axi4_lite", "tests/fixtures/fw/axi4_lite"
    lat2 = f"{rtl}/variants/axi4_lite_regs_lat2.v"
    strict = "read32_and_write32_take_the_conforming_rtls_cycles"

    def control(path: str) -> dict:
        [found] = [c for c in CONTROLS if _uses(c, path)]
        assert found["upstream_rtl"] == lat2, found["id"]
        return found

    # The simulator's clock: the screen refuses it in every screened check; the files and their lat2 pass stay.
    test = control(f"{fw}/axi4_lite_regs_test_strict_latency.c")
    [on_lat2] = [s for s in test["checks"] if "inline" in s]
    [check7] = [s for s in test["checks"] if s.get("check") == 7]
    assert (on_lat2["rtl"], on_lat2["expect"], on_lat2["timing"]) == (lat2, "passed",
                                                                      ["test read32 3 cycles, write32 3 cycles"])
    assert (check7["expect"], check7.get("screen_refuses")) == ("failed", True) and "fails_by" not in check7
    driver = control(f"{fw}/axi4_lite_regs_drv_strict_latency.c")
    assert {(s["check"], s["expect"], s.get("screen_refuses")) for s in driver["checks"]} == {
        (4, "failed", True), (5, "failed", True), (6, "failed", True)}

    # Address arithmetic: open, so the strict fixtures on it must fail as decision 1, items 1 and 2, ask.
    test = control(f"{fw}/axi4_lite_regs_test_strict_address.c")
    assert _uses(test, f"{fw}/axi4_lite_regs_drv.c")
    [on_lat2] = [s for s in test["checks"] if "inline" in s]
    [check7] = [s for s in test["checks"] if s.get("check") == 7]
    assert (on_lat2["rtl"], on_lat2["expect"]) == (lat2, "passed")
    assert (check7["expect"], check7["fails_by"]) == ("failed", strict) and not check7.get("screen_refuses")
    assert on_lat2["transcript"] == check7["transcript"]
    driver = control(f"{fw}/axi4_lite_regs_drv_strict_address.c")
    assert _uses(driver, f"{fw}/axi4_lite_regs_test.c")
    got = {(s["check"], s.get("rtl"), s["expect"]) for s in driver["checks"] if not s.get("screen_refuses")}
    assert {(4, None, "passed"), (5, lat2, "passed"), (6, None, "failed")} == got

    # The SoC's CYCLES register (refused or unreadable here).
    for path in (f"{fw}/axi4_lite_regs_test_strict_soc_cycles.c", f"{fw}/axi4_lite_regs_test_strict_soc_address.c"):
        soc = control(path)
        assert soc.get("reaches_review") is False and soc["refused_by"], soc["id"]


def test_the_record_names_a_ci_run_and_every_control_once():
    assert RECORD.is_file(), "the controls' recorded CI run is missing (evals/flow/controls_record.json)"
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    assert data["format"] == "nirmaan.flow-controls-record"
    assert re.fullmatch(r"https://github\.com/\S+/actions/runs/\d+(/job/\d+)?", data["run"])
    assert re.fullmatch(r"[0-9a-f]{40}", data["head"])
    assert sorted(c["id"] for c in data["controls"]) == sorted(c["id"] for c in CONTROLS)


# --- The controls (tools) --------------------------------------------------------------------------------------


@TOOLS
@pytest.mark.parametrize("control", CONTROLS, ids=[c["id"] for c in CONTROLS])
def test_the_control_gets_the_verdict_it_expects(nirmaan_org, fixed_clock, flows, tmp_path, capsys, control):
    case = _stand_in(control, flows[control["case"]], tmp_path)
    result, engine = evaluate(nirmaan_org, case, _seat(control), replay=False, repo=REPO, sandbox=tmp_path / "box",
                              clock=fixed_clock)
    # The seat reached review, so whatever fails below is the judge's verdict; a control that says it does not is a
    # flow stopped at that stage by its own gate: no check runs and the trial fails.
    assert result.submitted is control.get("reaches_review", True), result.detail
    assert result.submitted or not result.passed
    got = [s.status.value for s in result.scores]
    line = {"id": control["id"], "submitted": result.submitted, "verdicts": got,
            "scores": [{"check": s.name, "status": s.status.value, "summary": s.summary} for s in result.scores]}
    timings = [_timings(engine, s.runs) for s in result.scores]
    if any(timings):
        for entry, timed in zip(line["scores"], timings):
            entry["timing"] = timed
    if not result.submitted:
        line["gates"] = [{"tool": g.tool, "succeeded": g.succeeded, "summary": g.summary} for g in result.gate_runs]
    with capsys.disabled():
        print(f"\nFLOW-CONTROL {json.dumps(line, sort_keys=True)}")
    assert got == [s["expect"] for s in control["checks"]], line
    for spec, score, timed in zip(control["checks"], result.scores, timings):
        if "timing" in spec:  # the counts a strict fixture measured
            assert timed == spec["timing"], (score.name, timed)
        if spec.get("screen_refuses"):  # WF16: refused before any build or link, with nothing run
            assert score.summary.startswith(REFUSED) and not score.runs, (score.name, score.summary)
        else:
            assert not score.summary.startswith(REFUSED), (score.name, score.summary)
        if "fails_by" in spec:  # that one check failed, and nothing else went wrong: no build, harness or crash
            assert _how_it_failed(engine, score.runs[0]) == {"failed": [spec["fails_by"]], "errors": [],
                                                             "finished": True}, score.summary
    if "refused_by" in control:  # what refused the seat before review
        assert any(not g.succeeded and re.search(control["refused_by"], g.summary) for g in result.gate_runs), line
    transcripts: dict[str, list[list[str]]] = {}
    for spec, score in zip(control["checks"], result.scores):
        if "transcript" in spec:
            transcripts.setdefault(spec["transcript"], []).append(_bus(engine, score.runs))
    for runs in transcripts.values():  # the same bus transfers on both RTLs
        assert runs[0] and all(r == runs[0] for r in runs), runs
    recorded = {c["id"]: c for c in json.loads(RECORD.read_text(encoding="utf-8"))["controls"]}
    assert recorded[control["id"]]["verdicts"] == got
    for entry, timed in zip(recorded[control["id"]]["scores"], timings):  # the recorded counts hold
        assert entry.get("timing", []) == timed, (entry["check"], timed)
