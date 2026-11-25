"""G5 (M86): every model-labelled failed live trial is answered in the batch's PR."""

import importlib.util
import sys
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("failure_curriculum", ROOT / "scripts" / "failure_curriculum.py")
fc = importlib.util.module_from_spec(spec)
sys.modules["failure_curriculum"] = fc
spec.loader.exec_module(fc)


def _batch(tmp_path, cause="model (not further established)"):
    rec = tmp_path / "results" / "2026-01-01-x-m"
    (rec / "rtl_a").mkdir(parents=True)
    for n, passed in ((1, True), (2, False), (3, False)):
        (rec / "rtl_a" / f"trial-{n:02d}.json").write_text(json.dumps(
            {"trial": n, "purpose": "evidence", "result": {"passed": passed, "replay": False}}))
    (rec / "causes.md").write_text(
        "| Trial | Outcome | Cause | Shows |\n|---|---|---|---|\n"
        f"| 2 | not passed | {cause} | x |\n| 3 | not passed | plan limit, not the model | y |\n")
    return tmp_path / "results"


def _run(results, answers, **kw):
    out = io.StringIO()
    code = fc.run(results, ROOT, None, answers, kw.get("require", False), kw.get("strict", False), out)
    return code, out.getvalue()


def test_only_model_labels_need_an_answer(tmp_path):
    rows, _ = fc.labels(_batch(tmp_path))
    assert [f.id for f in rows if f.is_model] == ["2026-01-01-x-m:trial-02"]
    assert len(rows) == 2


def test_an_unanswered_model_failure_fails_and_a_dry_run_only_lists(tmp_path):
    results = _batch(tmp_path)
    assert _run(results, "")[0] == 1
    assert _run(results, None)[0] == 0
    assert _run(results, None, require=True)[0] == 1


def test_each_kind_of_answer(tmp_path):
    results = _batch(tmp_path)
    fid = "2026-01-01-x-m:trial-02"
    assert _run(results, f"- {fid}: note: knowledge/design/rtl_design.md")[0] == 0
    assert _run(results, f"- {fid}: must-fail: knowledge/design/nope.md")[0] == 1
    assert _run(results, f"- {fid}: no: the case itself is under-specified, fixed in the case")[0] == 0
    assert _run(results, f"- {fid}: no: later")[0] == 1


def test_a_cause_other_than_model_needs_nothing(tmp_path):
    assert _run(_batch(tmp_path, cause="harness: input rule"), "")[0] == 0


def test_unlabelled_failures_are_listed_and_fail_only_when_strict(tmp_path):
    results = _batch(tmp_path)
    (results / "2026-01-01-x-m" / "causes.md").write_text("no table\n")
    code, text = _run(results, "", strict=False)
    assert code == 0 and "failed trials with no label in any causes.md: 2" in text
    assert _run(results, "", strict=True)[0] == 1


def test_the_committed_records_parse_without_unplaced_rows():
    rows, problems = fc.labels(ROOT / "evals" / "results")
    assert problems == []
    assert any(f.is_model for f in rows)


def test_a_row_with_a_missing_cause_or_record_is_skipped_not_a_crash(tmp_path):
    results = _batch(tmp_path)
    (results / "2026-01-01-x-m" / "causes.md").write_text(
        "| Record | Trial | Outcome |\n|---|---|---|\n| this | 2 | no cause column |\n\n"
        "| Trial | Cause |\n|---|---|\n| | model |\n")
    rows, problems = fc.labels(results)
    assert rows == [] and len(problems) == 1


def test_main_survives_a_missing_module_docstring(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "__doc__", None)
    assert fc.main(["--results", str(_batch(tmp_path))]) == 0


# --- Nested slot records (evals/results/g3-timer/slot-NN/<name>) ------------------------------------------------


def _nested(tmp_path, slots=(1, 2), name="2026-01-01-x-m"):
    """Two slots of one arm on one day: both folders carry the SAME record name, one per slot folder."""
    results = tmp_path / "results"
    for n in slots:
        rec = results / "g3-timer" / f"slot-{n:02d}" / name
        (rec / "flow_timer").mkdir(parents=True)
        (rec / "flow_timer" / "trial-01.json").write_text(json.dumps(
            {"trial": 1, "purpose": "evidence", "result": {"passed": False, "replay": False}}))
        (rec / "causes.md").write_text(
            "| Trial | Outcome | Cause | Shows |\n|---|---|---|---|\n| 1 | not passed | model (not further established) | x |\n")
    return results


def test_nested_records_with_one_name_get_distinct_keys(tmp_path):
    rows, problems = fc.labels(_nested(tmp_path))
    assert problems == []
    assert [f.id for f in rows] == ["g3-timer/slot-01/2026-01-01-x-m:trial-01",
                                    "g3-timer/slot-02/2026-01-01-x-m:trial-01"]
    assert [f.source for f in rows] == ["g3-timer/slot-01/2026-01-01-x-m/causes.md",
                                        "g3-timer/slot-02/2026-01-01-x-m/causes.md"]


def test_each_nested_failure_needs_its_own_answer(tmp_path):
    results = _nested(tmp_path)
    first = "g3-timer/slot-01/2026-01-01-x-m:trial-01"
    code, out = _run(results, f"- {first}: no: the case itself is under-specified, fixed in the case")
    assert code == 1 and "unanswered: 1 of 2" in out
    both = f"- {first}: no: the case itself is under-specified, fixed in the case\n" + \
           "- g3-timer/slot-02/2026-01-01-x-m:trial-01: no: the case itself is under-specified, fixed in the case"
    assert _run(results, both)[0] == 0


def test_a_nested_failed_trial_with_no_label_is_listed_by_its_key_and_scope_follows_the_key(tmp_path):
    results = _nested(tmp_path, slots=(1,))
    (results / "g3-timer" / "slot-01" / "2026-01-01-x-m" / "causes.md").unlink()
    code, out = _run(results, None, strict=True)
    assert code == 1 and "  g3-timer/slot-01/2026-01-01-x-m:trial-01" in out
    scoped = io.StringIO()
    assert fc.run(results, ROOT, ["2026-01-01-x-m"], None, False, True, scoped) == 0  # a bare name is no key
    assert fc.run(results, ROOT, ["g3-timer/slot-01/2026-01-01-x-m"], None, False, True, io.StringIO()) == 1


def test_flat_and_nested_records_read_together_and_the_flat_key_is_unchanged(tmp_path):
    _nested(tmp_path, slots=(1,))
    results = _batch(tmp_path)
    rows, _ = fc.labels(results)
    assert {f.id for f in rows if f.is_model} == {"2026-01-01-x-m:trial-02", "g3-timer/slot-01/2026-01-01-x-m:trial-01"}


def test_a_sibling_row_is_placed_inside_its_own_slot_folder(tmp_path):
    results = _nested(tmp_path, slots=(1,))
    slot = results / "g3-timer" / "slot-01"
    (slot / "2026-01-01-x-m-2" / "flow_timer").mkdir(parents=True)
    (slot / "2026-01-01-x-m" / "causes.md").write_text(
        "| Record | Trial | Outcome | Cause | Shows |\n|---|---|---|---|---|\n"
        "| -2 | 1 | not passed | model (not further established) | x |\n")
    rows, problems = fc.labels(results)
    assert problems == [] and [f.id for f in rows] == ["g3-timer/slot-01/2026-01-01-x-m-2:trial-01"]


def test_the_committed_w2_l1_answers_answer_every_model_failure_of_that_batch():
    """Wave 2 close, decision M8: the thirteen answers are a committed file the script itself can read."""
    results = ROOT / "evals" / "results"
    keys = sorted(p.name for p in results.iterdir() if p.is_dir() and p.name.startswith(("2026-11-18-", "2026-11-19-")))
    text = (ROOT / "evals" / "plans" / "2026-11-25-w2-l1-curriculum-answers.md").read_text()
    out = io.StringIO()
    assert fc.run(results, ROOT, keys, text, True, True, out) == 0, out.getvalue()
    assert "model-labelled failures in scope: 13" in out.getvalue()
    assert "unanswered: 0 of 13" in out.getvalue()
    assert len(fc.parse_answers(text)) == 13
    # The script must also fail on this batch when the answers are missing, or the test proves nothing.
    assert fc.run(results, ROOT, keys, "", True, True, io.StringIO()) == 1


def test_the_committed_w2_remeasure_answers_answer_every_model_failure_of_that_batch():
    """Wave 2 close, Part 2 (Carried): the sixteen answers of the re-measure batch, a committed file the script reads."""
    results = ROOT / "evals" / "results"
    keys = sorted(p.parent.relative_to(results).as_posix()
                  for p in (results / "w2-remeasure").glob("slot-*/*/manifest.json"))
    assert len(keys) == 117
    text = (ROOT / "evals" / "plans" / "2026-11-25-w2-remeasure-curriculum-answers.md").read_text()
    out = io.StringIO()
    assert fc.run(results, ROOT, keys, text, True, True, out) == 0, out.getvalue()
    assert "model-labelled failures in scope: 16" in out.getvalue()
    assert "unanswered: 0 of 16" in out.getvalue()
    assert len(fc.parse_answers(text)) == 16
    # The script must also fail on this batch when the answers are missing, or the test proves nothing.
    assert fc.run(results, ROOT, keys, "", True, True, io.StringIO()) == 1
