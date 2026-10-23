"""The turnaround report (scripts/turnaround_report.py) on synthetic GitHub data
and call log lines. Nothing touches the network; the report writes no file."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("turnaround_report", ROOT / "scripts" / "turnaround_report.py")
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

REQ = ["test", "dashes"]


def runs(conclusion, done):
    return [{"id": i, "name": n, "status": "completed", "conclusion": conclusion, "started_at": "2026-10-19T09:00:00Z",
             "completed_at": done if n == "dashes" else "2026-10-19T09:30:00Z"} for i, n in enumerate(REQ, 1)]


def at(hhmm, **line):
    return {"time": f"2026-10-19T{hhmm}:00+00:00", "repo": "o/r", "pr": 7, **line}


LOG = [
    at("09:59", key=1, outcome="ok", duration_ms=900_000),  # before the first green head: not in T
    at("10:02", key=1, outcome="ok", duration_ms=30_000),
    at("10:03", key=2, outcome="ok", duration_ms=60_000),
    at("10:03", key=1, outcome="reused", attempt=0),
    at("10:10", key="fixer", outcome="ok", duration_ms=120_000, round=1),
    at("10:15", kind="loop", event="fixed", round=1),
    at("10:20", kind="loop", event="stopped", reason="needs-founder"),
    at("10:40", kind="loop", event="resumed"),
    at("10:45", kind="loop", event="updated"),
    at("10:50", kind="loop", event="ci-green-seen"),
    at("10:55", key="proxy", outcome="ok", duration_ms=30_000),
    {**at("10:30", key=1, outcome="ok", duration_ms=999_000), "pr": 8},  # another pull request
    at("11:30", key=2, outcome="ok", duration_ms=999_000),  # after the merge
]
PULL = {"number": 7, "merged_at": "2026-10-19T11:00:00Z", "body": "Text."}
SHAS = {"a": runs("failure", "2026-10-19T09:40:00Z"), "b": runs("success", "2026-10-19T10:00:00Z")}


def test_t_runs_from_the_first_all_green_head_to_the_merge_and_is_split_from_the_log():
    r = report.turnaround(PULL, SHAS, LOG, REQ)
    assert r["start"] == datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc), "head a failed; head b's last required job"
    assert r["t"] == 3600
    assert r["review"] == 120, "key 1, key 2 and the proxy inside T; reused, other pull requests and outside T do not count"
    assert r["fix"] == 7 * 60, "fixer start (10:08) to the fixed event (10:15)"
    assert r["wait"] == 20 * 60, "stopped to resumed"
    assert r["update"] == 5 * 60, "updated to the next ci-green-seen"
    assert r["queue"] == 3600 - 120 - 420 - 1200 - 300
    assert r["founder_class"] is False


def test_a_stop_with_no_resume_waits_until_the_merge_and_no_green_head_means_no_row():
    log = [at("10:20", kind="loop", event="stopped")]
    assert report.turnaround(PULL, SHAS, log, REQ)["wait"] == 40 * 60
    assert report.turnaround(PULL, {"a": SHAS["a"]}, LOG, REQ) is None
    assert report.turnaround({**PULL, "merged_at": None}, SHAS, LOG, REQ) is None
    running = [{**SHAS["b"][0], "status": "in_progress", "conclusion": None}, SHAS["b"][1]]
    assert report.turnaround(PULL, {"b": running}, LOG, REQ) is None, "a run in progress is never green"


def test_founder_class_pull_requests_are_reported_on_their_own_line():
    body = "<!-- review:founder-class -->Founder class: control-plane.<!-- /review:founder-class -->\n\nText."
    plain = report.turnaround(PULL, SHAS, LOG, REQ)
    founder = report.turnaround({**PULL, "number": 9, "body": body}, SHAS, [], REQ)
    assert founder["founder_class"] is True
    text = report.render([plain, founder])
    assert "#7     not founder class" in text and "#9     founder class" in text
    assert "not founder class: n=1, median T 60.0m, p90 T 60.0m" in text
    assert "\nfounder class: n=1, median T 60.0m" in text
    assert report.render([]).splitlines() == ["not founder class: n=0", "founder class: n=0"]


def test_percentile_is_nearest_rank():
    values = [float(v) for v in range(1, 11)]
    assert report.percentile(values, 50) == 5 and report.percentile(values, 90) == 9 and report.percentile([4.0], 90) == 4


def test_collect_reads_merged_pull_requests_since_the_date_from_github():
    calls = []

    def gh(args):
        calls.append(args[0])
        path = args[0]
        if "/pulls?" in path:
            return [{"number": 7, "merged_at": "2026-10-19T11:00:00Z", "updated_at": "2026-10-19T11:00:00Z", "body": "Text."},
                    {"number": 6, "merged_at": None, "updated_at": "2026-10-19T11:00:00Z"},
                    {"number": 5, "merged_at": "2026-10-01T11:00:00Z", "updated_at": "2026-10-01T11:00:00Z"}]
        if path.endswith("/commits?per_page=100"):
            return [{"sha": "a"}, {"sha": "b"}]
        sha = path.split("/commits/")[1].split("/")[0]
        return {"check_runs": [{**r, "app": "x"} for r in SHAS[sha]]}

    rows = report.collect("o/r", datetime(2026, 10, 18, tzinfo=timezone.utc), REQ, LOG, gh=gh)
    assert [r["pr"] for r in rows] == [7] and rows[0]["t"] == 3600
    assert not any("/pulls/6/" in c or "/pulls/5/" in c for c in calls), "unmerged and older pull requests are not read"


def test_read_log_skips_lines_that_are_not_json(tmp_path):
    (tmp_path / "calls.jsonl").write_text('{"pr": 1}\nnot json\n{"pr": 2}\n')
    assert [l["pr"] for l in report.read_log(tmp_path)] == [1, 2]
    assert report.read_log(tmp_path / "missing") == []
