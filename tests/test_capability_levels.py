"""Evidence levels come only from committed records (M63).

On main no record exists, so the generator reports zero Knowledge, zero
Practised and zero Proven, and the committed capability/levels.json says so.
Fixture repositories show each rule: 5 of 5 tool-judged trials with a clean
re-judge and a must-fail control make a skill Practised; 4 of 5 do not; a
changed skill card makes the group stale; replays, attestations, trials of a
case not judged by a tool and trials run without knowledge documents (M67)
never count, while a blocked trial of a tool-judged case counts as failed;
a changed harness makes the group stale and a trial with no harness recorded
never counts (M73); only a case's own skills get credit; Knowledge
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
from nirmaan.evals.scorers import register_scorer, unregister_scorer
from nirmaan.models import EvalResult, EvalRunManifest, EvalTrial, JudgeRun, RecordedAnswer, Score, ScoreStatus
from nirmaan.runtime import harness
from nirmaan.runtime.harness import harness_sha256

ROOT = Path(__file__).resolve().parent.parent
SKILL = "rtl_design"
OTHER = "systemverilog"
MODEL = "claude-opus-5-5"
AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
#: ``_record``'s default harness: the one ``record_run`` would record now.
CURRENT = object()


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
            digest: str | None = None, judged: bool = True, knowledge: str = "on",
            trial_knowledge: str | None = None, harness_digest=CURRENT,
            answer_harness=CURRENT, blocked: frozenset[int] = frozenset(), cli: str | None = None) -> Path:
    record = repo / "evals" / "results" / name
    record.mkdir(parents=True)
    manifest = EvalRunManifest(id=name, runtime="claude-code", model=MODEL, replay=replay, nirmaan_version="t",
                               started_at=AT, finished_at=AT, trials=len(outcomes), cases=(case_id,),
                               seats=("rtl-implementation",), head_sha="0" * 40, knowledge=knowledge)
    (record / MANIFEST).write_text(manifest.model_dump_json(), encoding="utf-8")
    trial_knowledge = trial_knowledge or knowledge
    # As record_run writes it (M67): with knowledge off, the digest of the card alone.
    digest = digest or skill_digest(org, SKILL, repo, knowledge=trial_knowledge == "on")
    # M73: as record_run writes it, on the result and on every answer.
    if harness_digest is CURRENT:
        harness_digest = harness_sha256(knowledge=trial_knowledge == "on", cli=cli)
    if answer_harness is CURRENT:
        answer_harness = harness_digest
    for number, passed in enumerate(outcomes, start=1):
        # A blocked trial, as evaluate records it: the work never reached review, so no judge ran.
        stopped = number in blocked
        status = ScoreStatus.NOT_RUN if stopped else ScoreStatus.PASSED if passed else ScoreStatus.FAILED
        result = EvalResult(case=case_id, case_digest="sha256:x", runtime="claude-code", replay=replay, version="t",
                            started_at=AT, duration_s=1.0, seat="rtl-implementation",
                            seat_status="blocked" if stopped else "done", submitted=not stopped, attempts=1,
                            passed=passed and not stopped, audit_ok=True, sandbox="s",
                            attestations=("dv_ran",) if attest else (),
                            scores=(Score(scorer="held-out-run", name="reference testbench", status=status),),
                            harness=harness_digest, cli=cli)
        runs = (JudgeRun(check="reference testbench", run=f"run-{number}", tool="simulator.run",
                         succeeded=passed),) if judged and not stopped else ()
        trial = EvalTrial(record=name, trial=number, stage="rtl-implementation", model=MODEL,
                          skills={SKILL: digest}, knowledge=trial_knowledge, result=result, judge_runs=runs,
                          answers=(RecordedAnswer(mode="work", model=MODEL, prompt_sha256="p", packet_sha256="k",
                                                  harness=answer_harness),))
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


@pytest.fixture()
def rubric():
    """A scorer that needs no tool, so a case judged by it is not tool-judged."""
    @register_scorer("rubric-fixture")
    def _rubric(ctx):
        return Score(scorer="rubric-fixture", name=ctx.check.name, status=ScoreStatus.PASSED)

    yield "rubric-fixture"
    unregister_scorer("rubric-fixture")


def test_a_trial_of_a_case_not_tool_judged_is_listed_apart_and_never_counts(org, tmp_path, rubric):
    _case(tmp_path, scorer=rubric)
    _record(org, tmp_path, [True] * 5)
    levels = compute(org, tmp_path)
    assert SKILL not in levels["skills"] and len(levels["not_tool_judged"]) == 5
    assert all(t["passed"] for t in levels["not_tool_judged"])


def test_four_passes_and_one_blocked_trial_are_five_trials_four_passed_and_not_practised(org, tmp_path):
    # The pilot's first live case: the blocked trial once dropped out and the group read 4 of 4.
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, blocked=frozenset({3}))
    levels = compute(org, tmp_path)
    entry = levels["skills"][SKILL]
    [group] = entry["practised"]
    assert (group["n"], group["passed"], group["unjudged"]) == (5, 4, 1)
    assert entry["level"] is None and not group["counts"] and not levels["not_tool_judged"]
    assert group["reasons"] == [f"Wilson lower bound {group['lower']:.3f}, under 0.5"]
    # Five more clean passes beside it: 9 of 10 clears the bound, so the blocked trial costs a pass, no more.
    _record(org, tmp_path, [True] * 5, name="run2")
    [group] = _level(org, tmp_path)["practised"]
    assert (group["n"], group["passed"], group["unjudged"]) == (10, 9, 1) and group["counts"]


def test_a_trial_on_a_tool_judged_case_with_no_judge_run_is_a_failure_whatever_it_claims(org, tmp_path):
    # A result that says passed with no judge run behind it is never a pass, and never drops out.
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, judged=False)
    levels = compute(org, tmp_path)
    [group] = levels["skills"][SKILL]["practised"]
    assert (group["n"], group["passed"], group["unjudged"]) == (5, 0, 5) and not group["counts"]
    assert levels["skills"][SKILL]["level"] is None and not levels["not_tool_judged"]


# --- Without knowledge (M67) -------------------------------------------------------------------


def test_trials_without_knowledge_never_count_and_are_listed_with_the_reason(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, name="ablation", knowledge="off")
    levels = compute(org, tmp_path)
    assert SKILL not in levels["skills"] and levels["totals"]["practised"] == 0
    listed = levels["without_knowledge"]
    assert [(t["record"], t["trial"], t["passed"]) for t in listed] == [("evals/results/ablation", n, True)
                                                                         for n in range(1, 6)]
    assert all("knowledge: off in the run manifest and the trial" in t["reason"]
               and "never counts toward a level" in t["reason"] for t in listed)
    # Beside a record that counts, the ablation adds nothing and takes nothing away.
    _record(org, tmp_path, [True] * 5, name="run1")
    [group] = _level(org, tmp_path)["practised"]
    assert group["counts"] and group["n"] == 5 and group["records"] == ["evals/results/run1"]


@pytest.mark.parametrize("manifest, trial, where", [("on", "off", "the trial"),
                                                    ("off", "on", "the run manifest")])
def test_one_label_edited_back_to_on_never_relabels_an_ablation_trial(org, tmp_path, manifest, trial, where):
    # Either the manifest or the trial saying off is enough: editing a different field changes nothing.
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, name="ablation", knowledge=manifest, trial_knowledge=trial)
    levels = compute(org, tmp_path)
    assert SKILL not in levels["skills"] and len(levels["without_knowledge"]) == 5
    assert all(f"knowledge: off in {where}):" in t["reason"] for t in levels["without_knowledge"])


def test_both_labels_edited_still_leave_the_trials_stale_when_the_skill_has_a_document(org, tmp_path):
    # The trial's digest is the card alone (what the seat was given), so it is never the skill's current digest.
    _case(tmp_path)
    doc = tmp_path / "knowledge" / "design" / f"{SKILL}.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("Practising: lint and simulation back this.\n", encoding="utf-8")
    record = _record(org, tmp_path, [True] * 5, name="ablation", knowledge="off")
    for path in [record / MANIFEST, *record.rglob("trial-*.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["knowledge"] = "on"
        path.write_text(json.dumps(data), encoding="utf-8")
    entry = _level(org, tmp_path)
    assert entry["level"] is None
    assert any(r.startswith("stale") for r in entry["practised"][0]["reasons"])


# --- The harness (M73) -------------------------------------------------------------------------


def test_a_changed_harness_setting_makes_the_level_stale(org, tmp_path, monkeypatch):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5)
    assert _level(org, tmp_path)["level"] == "practised"
    monkeypatch.setattr(harness, "DOMAIN_CAP", harness.DOMAIN_CAP // 2)
    entry = _level(org, tmp_path)
    [group] = entry["practised"]
    assert entry["level"] is None and not group["counts"]
    assert group["reasons"] == ["stale: the harness changed after these trials (docs/HARNESS.md)"]


def test_trials_from_two_harnesses_are_two_groups_and_only_the_current_one_counts(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, name="before", harness_digest="sha256:" + "1" * 64)
    _record(org, tmp_path, [True] * 3, name="now")
    groups = {g["harness"]: g for g in _level(org, tmp_path)["practised"]}
    assert set(groups) == {"sha256:" + "1" * 64, harness_sha256()}
    # Five old trials and three current ones are never pooled into eight.
    assert groups[harness_sha256()]["n"] == 3 and not groups[harness_sha256()]["counts"]
    assert groups["sha256:" + "1" * 64]["reasons"][0].startswith("stale: the harness changed")


def test_a_run_option_other_than_the_default_harness_is_stale(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, harness_digest=harness_sha256(attempts=3))
    assert _level(org, tmp_path)["level"] is None


@pytest.mark.parametrize("result, answer", [(None, None), (None, CURRENT), (CURRENT, None),
                                            (CURRENT, "sha256:" + "2" * 64)])
def test_a_trial_with_no_harness_recorded_never_counts(org, tmp_path, result, answer):
    # A record written before M73 has none; a result and an answer that disagree are no record either.
    _case(tmp_path)
    current = harness_sha256()
    _record(org, tmp_path, [True] * 5, harness_digest=current if result is CURRENT else result,
            answer_harness=current if answer is CURRENT else answer)
    entry = _level(org, tmp_path)
    [group] = entry["practised"]
    assert entry["level"] is None and group["harness"] is None
    assert group["reasons"] == ["harness not recorded: the trials carry no harness, or their answers disagree"]


def test_trials_on_two_cli_versions_are_two_groups_never_pooled(org, tmp_path):
    # The claude-code runtime's Claude Code version is in the harness: three trials on 2.1.311 and three on
    # 2.1.325 are two groups of three, never six, so neither counts.
    _case(tmp_path)
    _record(org, tmp_path, [True] * 3, name="old-cli", cli="2.1.311")
    _record(org, tmp_path, [True] * 3, name="new-cli", cli="2.1.325")
    entry = _level(org, tmp_path)
    groups = {g["cli"]: g for g in entry["practised"]}
    assert set(groups) == {"2.1.311", "2.1.325"} and entry["level"] is None
    assert groups["2.1.311"]["harness"] == harness_sha256(cli="2.1.311") != groups["2.1.325"]["harness"]
    assert all(g["n"] == 3 and g["reasons"][0] == "3 trials, fewer than 5" for g in groups.values())
    # Five more on the new version make that group count on its own; the old group stays apart.
    _record(org, tmp_path, [True] * 2, name="new-cli-more", cli="2.1.325")
    groups = {g["cli"]: g for g in _level(org, tmp_path)["practised"]}
    assert groups["2.1.325"]["n"] == 5 and groups["2.1.325"]["counts"] and groups["2.1.311"]["n"] == 3


def test_a_cli_version_edited_on_the_trials_is_stale(org, tmp_path):
    # The version is checked through the harness it entered: editing the field leaves the harness of the other.
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, cli="2.1.325", harness_digest=harness_sha256(cli="2.1.311"))
    [group] = _level(org, tmp_path)["practised"]
    assert not group["counts"] and group["reasons"] == ["stale: the harness changed after these trials "
                                                        "(docs/HARNESS.md)"]


def test_a_cli_version_that_could_not_be_read_never_counts(org, tmp_path):
    _case(tmp_path)
    _record(org, tmp_path, [True] * 5, cli="unknown")
    [group] = _level(org, tmp_path)["practised"]
    assert not group["counts"] and group["reasons"] == ["the CLI version the trials ran was not read"]


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
