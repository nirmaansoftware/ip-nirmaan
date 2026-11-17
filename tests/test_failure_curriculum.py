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
