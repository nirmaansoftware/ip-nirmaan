"""Evidence levels come only from committed records (M63).

On main no record exists, so the generator reports zero Knowledge, zero
Practised and zero Proven, and the committed capability/levels.json says so.
Fixture repositories show each rule: 5 of 5 tool-judged trials with a clean
re-judge and a must-fail control make a skill Practised; 4 of 5 do not; a
changed skill card makes the group stale; replays, attestations and trials not
judged by a tool never count; only a case's own skills get credit; Knowledge
needs a check record by a different session that names the current document.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import skill_digest
from nirmaan.evals.levels import (CHECKS, KNOWLEDGE_CHECK_FORMAT, LEVELS, REJUDGE, REJUDGE_FORMAT, compute,
                                  render)
from nirmaan.evals.records import MANIFEST, trial_path
from nirmaan.models import EvalResult, EvalRunManifest, EvalTrial, JudgeRun, Score, ScoreStatus

ROOT = Path(__file__).resolve().parent.parent
SKILL = "rtl_design"
OTHER = "systemverilog"
MODEL = "claude-opus-5-5"
AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _case(repo: Path, *, must_fail: bool = True, scorer: str = "held-out-run", case_id: str = "rtl/fixture") -> str:
    check = {"name": "reference testbench", "scorer": scorer, "tool": "simulator.run",
             "seat_files": {"sources": ["rtl_source"]}, "case_files": {"sources": ["tb.v"]}}
    if must_fail:
        check["mutants"] = {"tb.v": ["tb_mutant.v"]}
    case = {"id": case_id, "request": "Create a parameterizable synchronous FIFO.", "seat": "rtl-implementation",
            "skills": [SKILL], "held_out": [check]}
    path = repo / "evals" / f"{case_id.replace('/', '_')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(case), encoding="utf-8")
    return case_id


def _record(org, repo: Path, outcomes: list[bool], *, name: str = "run1", case_id: str = "rtl/fixture",
            replay: bool = False, attest: bool = False, rejudge: bool | None = True,
            digest: str | None = None, judged: bool = True) -> Path:
    record = repo / "evals" / "results" / name
    record.mkdir(parents=True)
    manifest = EvalRunManifest(id=name, runtime="claude-code", model=MODEL, replay=replay, nirmaan_version="t",
                               started_at=AT, finished_at=AT, trials=len(outcomes), cases=(case_id,),
                               seats=("rtl-implementation",), head_sha="0" * 40)
    (record / MANIFEST).write_text(manifest.model_dump_json(), encoding="utf-8")
    digest = digest or skill_digest(org, SKILL, repo)
    for number, passed in enumerate(outcomes, start=1):
        status = ScoreStatus.PASSED if passed else ScoreStatus.FAILED
        result = EvalResult(case=case_id, case_digest="sha256:x", runtime="claude-code", replay=replay, version="t",
                            started_at=AT, duration_s=1.0, seat="rtl-implementation", seat_status="done",
                            submitted=True, attempts=1, passed=passed, audit_ok=True, sandbox="s",
                            attestations=("dv_ran",) if attest else (),
                            scores=(Score(scorer="held-out-run", name="reference testbench", status=status),))
        runs = (JudgeRun(check="reference testbench", run=f"run-{number}", tool="simulator.run",
                         succeeded=passed),) if judged else ()
        trial = EvalTrial(record=name, trial=number, stage="rtl-implementation", model=MODEL,
                          skills={SKILL: digest}, result=result, judge_runs=runs)
        path = trial_path(record, case_id, number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trial.model_dump_json(), encoding="utf-8")
    if rejudge is not None:
        trials = [{"case": case_id, "trial": n, "same": rejudge, "differences": []}
                  for n in range(1, len(outcomes) + 1)]
        (record / REJUDGE).write_text(json.dumps({"format": REJUDGE_FORMAT, "record": name, "trials": trials}),
                                      encoding="utf-8")
    return record


def _level(org, repo: Path, skill: str = SKILL):
    return compute(org, repo)["skills"].get(skill)


# --- Main -------------------------------------------------------------------------------------


def test_on_main_nothing_is_practised_or_proven_and_the_file_says_so(org):
    levels = compute(org, ROOT)
    assert levels["totals"]["practised"] == 0 and levels["totals"]["proven"] == 0
    # Knowledge comes only from committed check records, and every committed record counts.
    at_knowledge = {s for s, v in levels["skills"].items() if v["level"] == "knowledge"}
    assert at_knowledge == {p.stem for p in (ROOT / CHECKS).glob("*.json")}
    assert (ROOT / LEVELS).read_text(encoding="utf-8") == render(levels)


def test_the_script_checks_the_committed_file():
    spec = importlib.util.spec_from_file_location("capability_levels", ROOT / "scripts" / "capability_levels.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0


def test_every_level_names_committed_record_paths(org):
    for skill, entry in compute(org, ROOT)["skills"].items():
        if entry["level"] == "practised":
            assert all((ROOT / r).is_dir() for g in entry["practised"] if g["counts"] for r in g["records"]), skill
        if entry["level"] == "knowledge":
            assert (ROOT / entry["knowledge"]["check_record"]).is_file(), skill


# --- Practised --------------------------------------------------------------------------------


def test_five_of_five_with_a_clean_rejudge_and_a_must_fail_control_is_practised(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    entry = _level(org, tmp_path)
    assert entry["level"] == "practised", entry
    group = entry["practised"][0]
    assert group["model"] == MODEL and group["n"] == 5 and group["records"] == ["evals/results/run1"]


def test_four_of_five_is_not_practised(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True, True, True, True, False])
    entry = _level(org, tmp_path)
    assert entry["level"] is None and any("Wilson lower bound" in r for r in entry["practised"][0]["reasons"])


def test_fewer_than_five_trials_is_not_practised(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 4)
    assert any("fewer than 5" in r for r in _level(org, tmp_path)["practised"][0]["reasons"])


@pytest.mark.parametrize("rejudge, why", [(None, "without a clean re-judge"), (False, "without a clean re-judge")])
def test_no_clean_rejudge_is_not_practised(org, tmp_path, rejudge, why):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, rejudge=rejudge)
    entry = _level(org, tmp_path)
    assert entry["level"] is None and any(why in r for r in entry["practised"][0]["reasons"])


def test_a_design_skill_without_a_must_fail_control_is_not_practised(org, tmp_path):
    _case(tmp_path, must_fail=False)
    _record(org, tmp_path, [True] * 5)
    entry = _level(org, tmp_path)
    assert entry["level"] is None and any("no must-fail control" in r for r in entry["practised"][0]["reasons"])


def test_a_changed_skill_card_makes_the_level_stale(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    changed = org.skills[SKILL].model_copy(update={"procedures": (*org.skills[SKILL].procedures, "One more.")})
    org2 = build_organization()
    org2.skills[SKILL] = changed
    entry = _level(org2, tmp_path)
    assert entry["level"] is None and any(r.startswith("stale") for r in entry["practised"][0]["reasons"])


def test_a_knowledge_document_added_after_the_trials_makes_them_stale(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    doc = tmp_path / "knowledge" / "design" / f"{SKILL}.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("Practising: lint and simulation back this.\n", encoding="utf-8")
    assert _level(org, tmp_path)["level"] is None


def test_replays_and_attestations_never_raise_a_level(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, name="replayed", replay=True)
    _record(org, tmp_path, [True] * 5, name="attested", attest=True)
    levels = compute(org, tmp_path)
    assert SKILL not in levels["skills"]
    assert len(levels["refused_records"]) == 2


def test_a_trial_no_tool_judged_is_listed_apart_and_never_counts(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, judged=False)
    levels = compute(org, tmp_path)
    assert SKILL not in levels["skills"] and len(levels["not_tool_judged"]) == 5


def test_only_the_cases_own_skills_get_credit(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    assert _level(org, tmp_path, OTHER) is None


def test_nothing_is_ever_proven(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    assert compute(org, tmp_path)["totals"]["proven"] == 0


# --- Knowledge --------------------------------------------------------------------------------


def _document(repo: Path) -> Path:
    doc = repo / "knowledge" / "software" / "c_programming.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    # The M62 good fixture: a document that passes every file check.
    doc.write_text((ROOT / "tests" / "fixtures" / "knowledge" / "software" / "c_programming.md").read_text(
        encoding="utf-8"), encoding="utf-8")
    return doc


def _check(repo: Path, doc: Path, **override) -> None:
    data = {"format": KNOWLEDGE_CHECK_FORMAT, "skill": "c_programming",
            "knowledge_document": "knowledge/software/c_programming.md",
            "document_sha256": "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest(),
            "writer": "session a", "checker": "session b", "sources_read": ["SEI CERT C"], **override}
    path = repo / "capability" / "records" / "knowledge" / "c_programming.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_a_checked_document_is_knowledge(org, tmp_path):
    doc = _document(tmp_path)
    _check(tmp_path, doc)
    entry = _level(org, tmp_path, "c_programming")
    assert entry["level"] == "knowledge" and entry["knowledge"]["check_record"].endswith("c_programming.json")


def test_a_document_without_a_check_record_is_no_level(org, tmp_path):
    _document(tmp_path)
    entry = _level(org, tmp_path, "c_programming")
    assert entry["level"] is None and "no check record" in entry["knowledge"]["problems"]


@pytest.mark.parametrize("override, why", [
    ({"checker": "session a"}, "different checker"),
    ({"sources_read": []}, "no source"),
    ({"document_sha256": "sha256:" + "0" * 64}, "stale"),
])
def test_a_bad_check_record_is_no_level(org, tmp_path, override, why):
    doc = _document(tmp_path)
    _check(tmp_path, doc, **override)
    entry = _level(org, tmp_path, "c_programming")
    assert entry["level"] is None and any(why in p for p in entry["knowledge"]["problems"])


def test_rejudge_write_records_each_trial_and_feeds_the_level(org, tmp_path):
    from types import SimpleNamespace

    from nirmaan.evals.levels import write_rejudge
    from nirmaan.evals.records import load_record

    _case(tmp_path)
    record = _record(org, tmp_path, [True] * 5, rejudge=None)
    assert _level(org, tmp_path)["level"] is None
    outcomes = [SimpleNamespace(trial=t, same=True, differences=()) for t in load_record(record).trials]
    path = write_rejudge(record, "run1", outcomes)
    assert json.loads(path.read_text())["format"] == REJUDGE_FORMAT
    assert _level(org, tmp_path)["level"] == "practised"


def test_a_document_that_fails_its_file_checks_is_no_level(org, tmp_path):
    doc = _document(tmp_path)
    doc.write_text(doc.read_text(encoding="utf-8").replace("checker: fixture checker\n", ""), encoding="utf-8")
    _check(tmp_path, doc)
    entry = _level(org, tmp_path, "c_programming")
    assert entry["level"] is None and any("missing front matter field 'checker'" in p for p in entry["knowledge"]["problems"])
