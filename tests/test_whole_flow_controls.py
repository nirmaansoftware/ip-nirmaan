"""The whole-flow judge controls (G3, council record 2026-11-17, decision 2; gates WF4 and WF5), by replay.

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

What waits for the whole-flow runner: replaying the reference flow through every seated stage, a flow with a
planted upstream fault, and check 5 (the held-out test on the flow's own RTL), which takes the RTL from another
stage.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import ReplayLLM, load_case, load_cases
from nirmaan.evals.runner import evaluate
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
REFERENCE_RTL = "tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v"
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
        if "rtl" in spec:
            check["case_files"] = {**check.get("case_files", {}), "rtl": [spec["rtl"]]}
        if "mutants" in spec:
            check["mutants"] = {REFERENCE_RTL: spec["mutants"]}
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
            for path in [spec.get("rtl", REFERENCE_RTL), *spec.get("mutants", [])]:
                assert (REPO / path).is_file(), path
        assert _checks(control, flow)


def _uses(control: dict, path: str) -> bool:
    return any(f["path"] == path for f in control["seat"])


def test_the_controls_cover_what_the_record_rules(flows):
    """WF4 and WF5: the reference passes, each planted fault fails, the conforming RTL passes the checks on the
    flow's RTL, the range-accepting reference tests pass on both RTLs and a test written to one choice fails."""
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


def test_the_record_names_a_ci_run_and_every_control_once():
    if not RECORD.is_file():
        pytest.skip("no CI run recorded yet")
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
    with capsys.disabled():
        print(f"\nFLOW-CONTROL {json.dumps(line, sort_keys=True)}")
    assert got == [s["expect"] for s in control["checks"]], line
    transcripts: dict[str, list[list[str]]] = {}
    for spec, score in zip(control["checks"], result.scores):
        if "transcript" in spec:
            transcripts.setdefault(spec["transcript"], []).append(_bus(engine, score.runs))
    for runs in transcripts.values():  # the same bus transfers on both RTLs: latency is not visible to the test
        assert runs[0] and all(r == runs[0] for r in runs), runs
    if RECORD.is_file():
        recorded = {c["id"]: c["verdicts"] for c in json.loads(RECORD.read_text(encoding="utf-8"))["controls"]}
        assert recorded[control["id"]] == got
