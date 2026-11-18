"""Whole-flow cases: the label, the reader and the case checks (M87, council record 2026-11-17).

A whole-flow trial seats every work stage and judges only the final block. It credits no skill and no level:
the levels list it under ``whole_flow`` (tests/test_capability_levels.py). Here: a single-seat case, manifest and
trial dump exactly as before the label existed, so no case digest and no record file changes; a whole-flow case
is in no default case set and never runs as a single-seat case; and a whole-flow case names no skill in
``skills``, fixes no upstream stage, and lists the skills it exercises instead.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import EvalError, load_cases, record_run, validate_case
from nirmaan.evals.records import flow_labels, is_whole_flow, load_record
from nirmaan.models import EvalCase, EvalResult, EvalRunManifest, EvalStage, EvalTrial
from nirmaan.runtime import harness

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
AT = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
TIMER = "Create an AXI4-Lite timer peripheral with an interrupt."
#: What each seated stage of the timer request is given (the planner's tasks and their seats' skills).
EXERCISED = {"requirements": ["requirements_engineering"], "interface-spec": ["interface_specification"],
             "microarchitecture": ["rtl_microarchitecture"], "rtl-implementation": ["axi", "fsm_design", "rtl_design"]}


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _whole(**overrides) -> EvalCase:
    data = {"id": "flow/timer", "request": TIMER, "seat": "rtl-implementation", "flow": "whole",
            "exercised": EXERCISED, **overrides}
    return EvalCase.model_validate(data)


def _trial(flow: str = "seat", **extra) -> EvalTrial:
    result = EvalResult(case="c", case_digest="sha256:x", runtime="claude-code", replay=False, version="t",
                        started_at=AT, duration_s=1.0, seat="rtl-implementation", seat_status="done",
                        submitted=True, attempts=1, passed=True, audit_ok=True, sandbox="s")
    return EvalTrial(record="r", trial=1, stage="rtl-implementation", result=result, flow=flow, **extra)


def _manifest(flow: str = "seat") -> EvalRunManifest:
    return EvalRunManifest(id="r", runtime="claude-code", replay=False, nirmaan_version="t", started_at=AT,
                           finished_at=AT, trials=1, cases=("c",), seats=("rtl-implementation",), flow=flow)


# --- Nothing changes for a single-seat case, manifest or trial ------------------------------------------------


def test_a_single_seat_case_dumps_as_before_so_no_case_digest_changes():
    for case in load_cases(EVALS):
        dumped = case.model_dump(mode="json")
        assert "flow" not in dumped and "exercised" not in dumped, case.id
        assert set(dumped) == set(EvalCase.model_fields) - {"flow", "exercised"}, case.id


def test_a_single_seat_trial_and_manifest_are_written_as_before():
    assert not {"flow", "stages", "flow_digest"} & set(_trial().model_dump(mode="json"))
    assert "flow" not in _manifest().model_dump(mode="json")


def test_a_whole_flow_case_trial_and_manifest_carry_the_label():
    assert _whole().model_dump(mode="json")["flow"] == "whole"
    assert _whole().model_dump(mode="json")["exercised"] == EXERCISED
    stage = EvalStage(stage="requirements", task="t1", status="not run")
    trial = _trial("whole", stages=(stage,), flow_digest="sha256:f").model_dump(mode="json")
    assert trial["flow"] == "whole" and trial["flow_digest"] == "sha256:f" and trial["stages"][0]["status"] == "not run"
    assert _manifest("whole").model_dump(mode="json")["flow"] == "whole"
    assert EvalTrial.model_validate_json(_trial("whole").model_dump_json()).flow == "whole"


def test_every_committed_record_still_loads_and_none_is_whole_flow():
    manifests = sorted((EVALS / "results").rglob("manifest.json"))
    assert manifests
    for path in manifests:
        record = load_record(path.parent)
        assert not is_whole_flow(record), path
        assert all(t.flow == "seat" and t.stages == () and t.flow_digest is None for t in record.trials)


def test_either_label_is_enough_and_the_name_is_never_read():
    assert flow_labels(_manifest("whole"), _trial()) == ("the run manifest",)
    assert flow_labels(_manifest(), _trial("whole")) == ("the trial",)
    assert flow_labels(_manifest(), _trial()) == ()


def test_the_label_reader_and_the_list_are_outside_the_harness_code():
    # Editing these files never restarts a harness group: none is in harness.CODE (docs/HARNESS.md).
    for rel in ("nirmaan/models/evaluation.py", "nirmaan/evals/records.py", "nirmaan/evals/levels.py",
                "nirmaan/evals/cases.py"):
        assert rel not in harness.CODE


# --- Default case sets never hold a whole-flow case -----------------------------------------------------------


def _write(root: Path, name: str, case: EvalCase) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(case.model_dump_json(), encoding="utf-8")


def test_a_whole_flow_case_is_in_no_default_case_set(tmp_path):
    single = EvalCase(id="spec/x", request=TIMER, seat="interface-spec")
    _write(tmp_path, "single.json", single)
    _write(tmp_path / "flow", "timer.json", _whole())
    assert [c.id for c in load_cases(tmp_path)] == ["spec/x"]
    assert [c.id for c in load_cases(tmp_path, flow="whole")] == ["flow/timer"]
    assert [c.id for c in load_cases(tmp_path, flow=None)] == ["flow/timer", "spec/x"]


def test_one_id_is_one_case_across_both_flows(tmp_path):
    _write(tmp_path, "single.json", EvalCase(id="flow/timer", request=TIMER, seat="interface-spec"))
    _write(tmp_path / "flow", "timer.json", _whole())
    with pytest.raises(EvalError, match="two cases are named"):
        load_cases(tmp_path)


def test_a_run_never_mixes_whole_flow_and_single_seat_cases(org, tmp_path):
    out = tmp_path / "results"
    single = EvalCase(id="spec/x", request=TIMER, seat="interface-spec")
    with pytest.raises(EvalError, match="one record never mixes whole-flow and single-seat"):
        record_run(org, [_whole(), single], None, trials=1, repo=ROOT, out=out)
    assert not out.exists()  # refused before anything was written


# --- The case checks -------------------------------------------------------------------------------------------


def test_a_whole_flow_case_that_credits_nothing_and_fixes_nothing_is_valid(org):
    assert validate_case(org, _whole(), ROOT) == []


@pytest.mark.parametrize("overrides, why", [
    ({"skills": ["rtl_design"]}, "a whole-flow case credits no skill, so it names none in skills"),
    ({"upstream": {"interface-spec": [{"path": "evals/spec/axi4_lite/requirements.md", "kind": "interface_spec"}]}},
     "a whole-flow case fixes no upstream stage"),
    ({"exercised": {}}, "lists the skills each stage exercises in exercised"),
    ({"exercised": {"rtl-implementation": ["no_such_skill"]}}, "exercised skill 'no_such_skill'"),
    ({"exercised": {"firmware": ["device_drivers"]}}, "exercised skills for stage 'firmware', which is not in"),
])
def test_a_whole_flow_case_is_refused_when(org, overrides, why):
    problems = validate_case(org, _whole(**overrides), ROOT)
    assert any(why in p for p in problems), problems


def test_a_single_seat_case_lists_nothing_exercised(org):
    case = EvalCase(id="spec/x", request=TIMER, seat="interface-spec", exercised={"interface-spec": ("x",)})
    assert "only a whole-flow case lists exercised skills" in validate_case(org, case, ROOT)


def test_the_shipped_whole_flow_cases_are_valid(org):
    for case in load_cases(EVALS, flow="whole"):
        assert validate_case(org, case, ROOT) == [], case.id
        assert case.skills == () and case.upstream == {}
        assert json.loads(case.model_dump_json())["flow"] == "whole"
