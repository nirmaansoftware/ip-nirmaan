"""The records-only fast lane of the review (pr_review CONFIG "fast_lane", docs/REVIEW_MECHANISM.md).

The founder, in session, 2026-11-23: approved a records-only fast lane so generated eval record PRs merge
on green CI and schema tests without the two agent review keys. Each condition has a passing case and a
failing case; a failed condition, or any error, is the normal two-key path. No model is called and nothing
touches the network: the fakes are those of tests/test_pr_review.py and tests/test_pr_loop.py.
"""

from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path

import pytest

import test_pr_loop as tl
import test_pr_review as tr

pr_review = tr.pr_review
pr_loop = tl.pr_loop
# The review module the loop calls (each test module loads its own copy of scripts/pr_review.py).
loop_review = pr_loop.pr_review
ROOT = Path(__file__).resolve().parents[1]
LANE = pr_review.CONFIG["fast_lane"]
REQUIRED = pr_review.CONFIG["required_ci"]
RECORD = "evals/results/2026-11-23-claude-code-claude-opus-5-5-1/rtl_sync-fifo/trial-01.json"
GREEN = {"state": "green", "jobs": [{"name": n, "conclusion": "success"} for n in REQUIRED]}


def inputs(**over):
    """A pull request that qualifies; each test changes one thing."""
    files = [{"status": "A", "path": RECORD, "old": None},
             {"status": "A", "path": RECORD.replace("rtl_sync-fifo/trial-01.json", "manifest.json"), "old": None},
             {"status": "M", "path": "capability/levels.json", "old": None}]
    base = {"lane": LANE, "pull": {"author": "patel-om", "head_ref": "evals/w2-records-01", "draft": False, "labels": []},
            "files": files, "modes": {f["path"]: "100644" for f in files}, "tracked_head": set(LANE["record_tests"]),
            "ci_now": copy.deepcopy(GREEN), "required": list(REQUIRED), "diff_bytes": 5000, "max_diff_bytes": 200_000,
            "founder": {}, "diff": f"+++ b/{RECORD}\n+{{\"trial\": 1}}\n"}
    base.update(over)
    return base


def conditions(**over):
    return pr_review.fast_lane(**inputs(**over))


def failed(**over) -> list[str]:
    c = conditions(**over)
    assert not pr_review.fast_lane_ok(c)
    return [x["condition"] for x in c if not x["ok"]]


# --- The configuration is the one the founder approved, and tight ------------------------------


def test_the_lane_is_on_with_the_approved_conditions():
    assert LANE["author"] == "patel-om" and pr_loop.LOOP["authors"] == ["patel-om"]
    assert LANE["branch_prefix"] == "evals/"
    assert LANE["records"] == "evals/results/"
    assert LANE["may_modify"] == ["capability/levels.json"]
    assert LANE["needs_founder_label"] == pr_loop.LOOP["needs_founder_label"]
    assert LANE["ci_job"] in REQUIRED


# What in each record test reads the committed records or the levels file.
READS = {
    "tests/test_capability_levels.py": ['module.main(["--check"])', "LEVELS"],
    "tests/test_whole_flow.py": ['EVALS / "results"'],
    "tests/test_eval_purpose.py": ['(EVALS / "results")'],
    "tests/test_failure_curriculum.py": ['ROOT / "evals" / "results"'],
    "tests/test_nirmaan_evals.py": ["def test_every_shipped_case_is_valid"],
}


def test_every_record_test_is_a_test_file_on_this_tree_that_reads_the_committed_records():
    assert sorted(LANE["record_tests"]) == sorted(READS)
    for rel, needles in READS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"{rel} no longer holds {needle!r}"


def test_the_required_test_job_runs_the_whole_suite_so_the_record_tests_are_in_it():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    shard = re.search(r"python -m pytest -q -rs --shard \"\$SHARD/4\" --shard-profile test\b", ci)
    assert shard, "the test job's shards run pytest on the whole suite, with no path or -k filter"
    assert "scripts/shards.py shards/*.json" in ci, "the test job checks the shards ran every collected test once"


def test_the_fixer_may_not_change_the_lane_or_its_tests():
    for path in ("scripts/pr_review.py", "scripts/pr_loop.py", "tests/test_fast_lane.py", "docs/REVIEW_MECHANISM.md"):
        assert pr_loop.forbidden_changes([path], pr_loop.LOOP["fixer_forbidden"]), path


# --- Each condition: pass, and each way it fails ----------------------------------------------


def test_a_records_only_pull_request_meets_every_condition():
    c = conditions()
    assert pr_review.fast_lane_ok(c)
    assert [x["condition"] for x in c] == ["author", "branch", "draft", "paths", "regular files", "size", "ci",
                                          "record tests", "labels", "founder classes", "credentials"]


def test_records_alone_without_the_levels_file_qualify():
    files = [{"status": "A", "path": RECORD, "old": None}]
    assert pr_review.fast_lane_ok(conditions(files=files, modes={RECORD: "100644"}))


@pytest.mark.parametrize("author", ["nirmaansoftware", "someone-else", None])
def test_author_other_than_the_agents_account_fails(author):
    assert failed(pull={**inputs()["pull"], "author": author}) == ["author"]


@pytest.mark.parametrize("ref", ["feature", "evals", "evals/", "results/evals/x", "eval/x", None])
def test_branch_not_starting_evals_fails(ref):
    assert failed(pull={**inputs()["pull"], "head_ref": ref}) == ["branch"]


def test_a_draft_fails():
    assert failed(pull={**inputs()["pull"], "draft": True}) == ["draft"]


@pytest.mark.parametrize("change", [
    {"status": "M", "path": RECORD, "old": None},  # a modified record
    {"status": "D", "path": RECORD, "old": None},  # a deleted record
    {"status": "R", "path": RECORD, "old": RECORD.replace("trial-01", "trial-09")},  # a renamed record
    {"status": "C", "path": RECORD, "old": RECORD.replace("trial-01", "trial-09")},  # a copied record
    {"status": "A", "path": "capability/levels.json", "old": None},  # the levels file added, not modified
    {"status": "D", "path": "capability/levels.json", "old": None},  # or deleted
    {"status": "A", "path": "evals/results", "old": None},  # the folder itself, not a file under it
    {"status": "A", "path": "evals/results/../flow/case.json", "old": None},  # a path that leaves the folder
    {"status": "A", "path": "evals/resultsX/x.json", "old": None},  # a folder that only starts the same
    {"status": "A", "path": "evals/flow/new_case.json", "old": None},  # a case file
    {"status": "A", "path": "tests/test_new.py", "old": None},  # any other path
    {"status": "M", "path": "scripts/pr_review.py", "old": None},
    {"status": "T", "path": RECORD, "old": None},  # a type change
])
def test_any_path_but_added_records_and_the_modified_levels_file_fails(change):
    files = [f for f in inputs()["files"] if f["path"] != change["path"]] + [change]
    modes = {f["path"]: "100644" for f in files}
    assert failed(files=files, modes=modes) == ["paths"]


def test_only_the_levels_file_and_no_record_fails():
    files = [{"status": "M", "path": "capability/levels.json", "old": None}]
    assert failed(files=files, modes={"capability/levels.json": "100644"}) == ["paths"]


def test_no_changed_file_fails():
    assert failed(files=[], modes={}) == ["paths", "regular files"]


@pytest.mark.parametrize("mode", ["120000", "100755", "160000 commit", None])
def test_a_symlink_executable_submodule_or_missing_file_at_the_head_fails(mode):
    modes = {**inputs()["modes"], RECORD: mode}
    if mode is None:
        del modes[RECORD]
    assert failed(modes=modes) == ["regular files"]


@pytest.mark.parametrize("size", [0, 200_001, 10 ** 7])
def test_a_diff_empty_or_over_the_size_limit_fails(size):
    assert failed(diff_bytes=size) == ["size"]


def test_the_size_limit_itself_passes():
    assert pr_review.fast_lane_ok(conditions(diff_bytes=200_000))


@pytest.mark.parametrize("ci_now", [
    {"state": "pending", "jobs": [{"name": n, "conclusion": "in_progress" if n == "test" else "success"} for n in REQUIRED]},
    {"state": "failed", "jobs": [{"name": n, "conclusion": "failure" if n == "test" else "success"} for n in REQUIRED]},
    {"state": "green", "jobs": [{"name": n, "conclusion": "success"} for n in REQUIRED if n != "test"]},  # a job missing
    {"state": "green", "jobs": [{"name": n, "conclusion": "skipped" if n == "dashes" else "success"} for n in REQUIRED]},
    {},  # nothing read
])
def test_required_ci_not_all_success_on_the_head_fails(ci_now):
    assert failed(ci_now=ci_now) == ["ci"]


def test_a_lane_job_that_is_not_required_fails():
    assert "ci" in failed(required=[n for n in REQUIRED if n != LANE["ci_job"]])


@pytest.mark.parametrize("missing", LANE["record_tests"])
def test_a_record_test_missing_at_the_head_fails(missing):
    assert failed(tracked_head=set(LANE["record_tests"]) - {missing}) == ["record tests"]


def test_an_empty_record_test_list_fails():
    assert failed(lane={**LANE, "record_tests": []}) == ["record tests"]


@pytest.mark.parametrize("label", ["needs-founder", "hold"])
def test_needs_founder_or_hold_label_fails(label):
    assert failed(pull={**inputs()["pull"], "labels": ["other", label]}) == ["labels"]


def test_an_unrelated_label_passes():
    assert pr_review.fast_lane_ok(conditions(pull={**inputs()["pull"], "labels": ["evals"]}))


def test_any_founder_class_from_the_review_map_fails():
    assert failed(founder={"control-plane": [f"content in {RECORD}"]}) == ["founder classes"]


def test_an_added_line_in_a_credential_format_fails():
    token = "AKIA" + "Q" * 16
    assert failed(diff=f"+++ b/{RECORD}\n+{{\"note\": \"{token}\"}}\n") == ["credentials"]


def test_a_credential_only_on_a_removed_line_passes():
    token = "AKIA" + "Q" * 16
    assert pr_review.fast_lane_ok(conditions(diff=f"--- a/capability/levels.json\n-{token}\n+{{}}\n"))


def test_the_lane_turned_off_never_qualifies():
    assert failed(lane=None) == ["lane"]


def test_any_error_while_checking_fails_closed():
    assert failed(lane={"author": "patel-om"}) == ["evaluated"]  # a malformed lane
    assert failed(ci_now={"state": "green", "jobs": [{"conclusion": "success"}]}) == ["evaluated"]  # a malformed CI read


def test_one_failure_among_many_is_still_the_normal_path():
    c = conditions(pull={**inputs()["pull"], "author": "x", "labels": ["needs-founder"]}, diff_bytes=0)
    assert not pr_review.fast_lane_ok(c)
    assert {x["condition"] for x in c if not x["ok"]} == {"author", "labels", "size"}
    assert not pr_review.fast_lane_ok([])


# --- The review: no model call, both checks named for the lane, one comment ---------------------


@pytest.fixture
def repo(tmp_path):
    def make(responses=None, change=None, gh=None, main_extra=None):
        return tr.Repo(tmp_path, responses or [{"type": "verdict", "verdict": "pass"}], change, gh or {}, main_extra)
    return make


@pytest.fixture
def loop_repo(tmp_path):
    def make(change=None, gh=None):
        return tl.Repo(tmp_path, [{"verdict": "pass"}], [{"edits": {"src/app.py": "fixed\n"}}], change, gh or {})
    return make


def _main_with_record_tests(work):
    for rel in LANE["record_tests"]:
        tr.write(work, rel, "def test_x():\n    pass\n")
    tr.write(work, "capability/levels.json", "{}\n")


def _records(extra=None, levels=True):
    def change(work):
        tr.write(work, RECORD, '{"trial": 1}\n')
        tr.write(work, RECORD.replace("rtl_sync-fifo/trial-01.json", "manifest.json"), '{"run": 1}\n')
        if levels:
            tr.write(work, "capability/levels.json", '{"levels": []}\n')
        if extra:
            extra(work)
    return change


def _review_repo(repo, change, gh=None, ref="evals/w2-records-01"):
    r = repo(change=change, gh=gh, main_extra=_main_with_record_tests)
    get_pull = r.github.get_pull
    r.github.get_pull = lambda n: {**get_pull(n), "head_ref": ref, "draft": False}
    return r


def test_a_qualifying_pull_request_gets_both_checks_and_one_comment_and_no_model_call(repo):
    r = _review_repo(repo, _records())
    result = r.run()
    assert result["exit"] == pr_review.EXIT_OK and pr_review.fast_lane_ok(result["fast_lane"])
    assert r.calls() == [], "no key, chair or Founder Proxy process ran"
    for name in ("review/team-lead", "review/executive"):
        check = r.check(name)
        assert check["state"] == "success" and "records fast lane" in check["title"] and "no agent review" in check["title"]
    (comment,) = r.comments()
    body = comment["body"]
    assert "Records fast lane: qualified" in body and r.head in body
    for c in result["fast_lane"]:
        assert f"| {c['condition']} | yes |" in body
    assert "2026-11-23" in body and "not a sign-off" in body


def test_the_same_head_reviewed_again_posts_nothing_new(repo):
    r = _review_repo(repo, _records())
    r.run()
    before = len(r.github.posts)
    r.run()
    assert len(r.github.posts) == before and r.calls() == []


def test_a_symlinked_record_takes_the_normal_path(repo):
    def link(work):
        (work / "evals/results/2026-11-23-claude-code-claude-opus-5-5-1/link.json").symlink_to("../../../src/app.py")
    r = _review_repo(repo, _records(link))
    result = r.run()
    assert "fast_lane" not in result and len(r.calls()) >= 2  # key 1 per owning team, then key 2
    assert "records fast lane" not in r.check("review/executive")["title"]


@pytest.mark.parametrize("why, kw", [
    ("a modified record", {"change": "modified"}),
    ("another path", {"change": "other"}),
    ("not an evals/ branch", {"ref": "feature"}),
    ("a founder class detected on a record's content", {"change": "founder"}),
    ("needs-founder", {"gh": {"labels": ["needs-founder"]}}),
    ("another author", {"gh": {"author": "nirmaansoftware"}}),
])
def test_a_pull_request_that_fails_a_condition_gets_the_normal_two_key_review(repo, why, kw):
    def main_and_record(work):
        _main_with_record_tests(work)
        tr.write(work, RECORD, '{"trial": 0}\n')

    def main_with_a_content_founder_class(work):
        # main's map with a founder class that a marker in any changed line raises.
        _main_with_record_tests(work)
        plane = "  - id: control-plane\n    title: Control plane\n    paths: [.github/**, CLAUDE.md]\n"
        assert plane in tr.MAP
        tr.write(work, ".github/review-teams.yml", tr.MAP.replace(
            plane, plane + "    content:\n      - pattern: 'FOUNDER-CLASS-MARKER'\n        example: 'FOUNDER-CLASS-MARKER'\n"))

    extra = {"modified": None, "other": lambda w: tr.write(w, "src/app.py", "changed\n"),
             "founder": lambda w: tr.write(w, RECORD.replace("trial-01", "trial-02"), '{"note": "FOUNDER-CLASS-MARKER"}\n')}
    which = kw.get("change")
    main = {"modified": main_and_record, "founder": main_with_a_content_founder_class}.get(which, _main_with_record_tests)
    r = repo(change=_records(extra.get(which)), gh=kw.get("gh"), main_extra=main)
    get_pull = r.github.get_pull
    r.github.get_pull = lambda n: {**get_pull(n), "head_ref": kw.get("ref", "evals/w2-records-01"), "draft": False}
    result = r.run()
    assert "fast_lane" not in result, why
    if which == "founder":
        assert list(result["classification"]["founder"]) == ["control-plane"]
    assert len(r.calls()) >= 2, f"{why}: key 1 and key 2 ran"
    assert not any("Records fast lane" in c["body"] for c in r.comments())


def test_ci_not_green_waits_and_never_takes_the_lane(repo):
    runs = [tr.ci_run(n, conclusion=None, status="in_progress") if n == "test" else tr.ci_run(n) for n in REQUIRED]
    r = _review_repo(repo, _records(), gh={"check_runs": runs})
    result = r.run()
    assert result.get("waiting") and "fast_lane" not in result and r.calls() == []
    assert r.check("review/executive")["state"] == "pending"


def test_an_unreadable_file_mode_takes_the_normal_path(repo, monkeypatch):
    real = pr_review._git

    def git(root, *args):
        if "ls-tree" in args and "--literal-pathspecs" in args:
            raise subprocess.CalledProcessError(1, ["git", *args])
        return real(root, *args)

    monkeypatch.setattr(pr_review, "_git", git)
    r = _review_repo(repo, _records())
    result = r.run()
    assert "fast_lane" not in result and len(r.calls()) >= 2  # key 1 per owning team, then key 2


def test_a_dry_run_never_posts_a_green_check_for_the_lane(repo):
    r = _review_repo(repo, _records())
    result = r.run(post="dry-run")
    assert pr_review.fast_lane_ok(result["fast_lane"]) and r.calls() == []
    r.no_success()


# --- The loop: the merge path, with no key and no fix round ------------------------------------


def _loop_repo(loop_repo, ref="evals/w2-records-01", **kw):
    r = loop_repo(change=lambda w: tl.write(w, RECORD, '{"trial": 1}\n'), **kw)
    get_pull = r.github.get_pull
    r.github.get_pull = lambda n: {**get_pull(n), "head_ref": ref}
    return r


# The loop fixture's main has no tests/ folder: its CLAUDE.md stands in for the record test files.
LOOP_CONFIG = {**tl.CONFIG, "fast_lane": {**LANE, "record_tests": ["CLAUDE.md"]}}


def test_the_loop_turns_on_auto_merge_for_a_qualifying_pull_request_with_no_model_call(loop_repo):
    r = _loop_repo(loop_repo)
    assert r.tick(config=LOOP_CONFIG) == ["auto-merge"]
    assert r.calls() == []
    assert r.github.merges == [["pr", "merge", "1", "--repo", tl.CONFIG["repo"], "--auto", "--merge", "--match-head-commit", r.first_head]]
    assert any("Records fast lane: qualified" in c for c in r.comments())
    assert "the records fast lane qualified" in r.comments()[-1] and "Agent review only" not in r.comments()[-1]
    assert any(line.get("event") == "fast-lane" for line in r.log())
    assert r.tick(config=LOOP_CONFIG) == ["skip"]


def test_the_loop_reviews_a_non_qualifying_pull_request_with_both_keys(loop_repo):
    r = _loop_repo(loop_repo, ref="feature")
    assert r.tick(config=LOOP_CONFIG) == ["auto-merge"]
    assert len(r.calls()) == 2 and not any("Records fast lane" in c for c in r.comments())


def test_the_loop_skips_a_needs_founder_pull_request_before_any_lane_check(loop_repo):
    r = _loop_repo(loop_repo, gh={"labels": ["needs-founder"]})
    assert r.tick(config=LOOP_CONFIG) == ["skip"]
    assert r.github.merges == [] and r.calls() == []


def test_a_label_added_after_the_lane_was_checked_drops_the_merge(loop_repo, monkeypatch):
    r = _loop_repo(loop_repo)
    real = loop_review.run_review

    def review_then_label(*a, **k):
        out = real(*a, **k)
        r.github.labels.append("needs-founder")
        return out

    monkeypatch.setattr(loop_review, "run_review", review_then_label)
    assert r.tick(config=LOOP_CONFIG) == ["skip"]
    assert r.github.merges == []


def test_a_lane_result_with_a_failed_condition_is_never_merged(loop_repo, monkeypatch):
    r = _loop_repo(loop_repo)
    monkeypatch.setattr(loop_review, "run_review", lambda *a, **k: {
        "exit": pr_review.EXIT_OK, "fast_lane": [{"condition": "ci", "ok": False, "detail": "x"}], "key1": []})
    assert r.tick(config=LOOP_CONFIG) == ["stopped"]
    assert r.github.merges == [] and r.labeled()
