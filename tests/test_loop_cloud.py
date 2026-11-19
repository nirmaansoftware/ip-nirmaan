"""R7: the review loop in GitHub Actions (scripts/loop_cloud.py, .github/workflows/review-loop.yml).

The state repository is a local bare repository here; two writers (the cloud
IP loop and a second loop) share it the way docs/REVIEW_MECHANISM.md says.
"""

from __future__ import annotations

import importlib.util
import json
import re
import os
import subprocess
import types
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("loop_cloud", ROOT / "scripts" / "loop_cloud.py")
loop_cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop_cloud)
import pr_loop  # noqa: E402
import pr_review  # noqa: E402

REPO, PREFIX, WRITER = loop_cloud.REPO, loop_cloud.PREFIX, loop_cloud.WRITER
WORKFLOW = (ROOT / ".github" / "workflows" / "review-loop.yml").read_text(encoding="utf-8")


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def remote(tmp_path):
    """A state repository with main and a README, as the founder creates it."""
    bare = tmp_path / "state.git"
    sh(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "init"
    sh(tmp_path, "clone", "-q", str(bare), str(seed))
    (seed / "README.md").write_text("loop state\n")
    sh(seed, *loop_cloud.COMMITTER, "checkout", "-q", "-b", "main")
    sh(seed, "add", "-A")
    sh(seed, *loop_cloud.COMMITTER, "commit", "-qm", "init")
    sh(seed, "push", "-q", "origin", "main")
    return bare


def mac_state(root: Path, until_minutes: float | None = None) -> Path:
    """A Mac state folder holding both repositories' files, as ~/.nirmaan/pr-review is."""
    (root / "loop").mkdir(parents=True)
    (root / "loop" / f"{PREFIX}-pr-7.json").write_text(json.dumps({"pr": 7, "done": None}))
    (root / "loop" / "nirmaansoftware_Nirmaan-pr-7.json").write_text(json.dumps({"pr": 7}))
    (root / "verdicts" / PREFIX / "pr-7").mkdir(parents=True)
    (root / "verdicts" / PREFIX / "pr-7" / "abc-def-k1-eda-lead.json").write_text("{}")
    (root / "verdicts" / "nirmaansoftware_Nirmaan" / "pr-7").mkdir(parents=True)
    (root / "calls.jsonl").write_text(json.dumps({"time": "2026-11-01T00:00:00+00:00", "repo": REPO}) + "\n")
    if until_minutes is not None:
        until = (datetime.now(timezone.utc) + timedelta(minutes=until_minutes)).isoformat()
        (root / "loop" / "rate-limit-pause.json").write_text(json.dumps({"until": until, "repo": REPO, "pr": 7}))
    return root


def seeded(tmp_path, remote) -> Path:
    clone = tmp_path / "seed-clone"
    loop_cloud.clone_state(clone, str(remote))
    loop_cloud.export_state(clone, mac_state(tmp_path / "mac"), calls=False, runner="seed")
    assert loop_cloud.commit_and_push(clone, message="seed")
    return clone


def test_pull_refuses_an_unseeded_state_repository(tmp_path, remote):
    clone = tmp_path / "c"
    loop_cloud.clone_state(clone, str(remote))
    with pytest.raises(loop_cloud.SyncError, match="not seeded"):
        loop_cloud.import_state(clone, tmp_path / "state")


def test_seed_takes_only_this_repositorys_files_and_pull_lays_them_out(tmp_path, remote):
    seeded(tmp_path, remote)
    clone, state = tmp_path / "c", tmp_path / "state"
    loop_cloud.clone_state(clone, str(remote))
    files = sorted(str(p.relative_to(clone)) for p in clone.rglob("*") if p.is_file() and ".git" not in p.parts)
    assert files == ["README.md", f"{WRITER}/loop/{PREFIX}-pr-7.json",
                     f"{WRITER}/verdicts/{PREFIX}/pr-7/abc-def-k1-eda-lead.json", f"{WRITER}/writer.json"]
    loop_cloud.import_state(clone, state)
    assert (state / "loop" / f"{PREFIX}-pr-7.json").is_file()
    assert (state / "verdicts" / PREFIX / "pr-7" / "abc-def-k1-eda-lead.json").is_file()
    assert not (state / "calls.jsonl").exists(), "the run's call log starts empty"
    assert not (state / "loop" / "rate-limit-pause.json").exists()


def test_push_mirrors_this_loop_appends_calls_by_month_and_touches_no_other_folder(tmp_path, remote):
    seeded(tmp_path, remote)
    other = tmp_path / "other"
    loop_cloud.clone_state(other, str(remote))
    (other / "Nirmaan").mkdir()
    (other / "Nirmaan" / "pause.json").write_text("{}")
    (other / "Nirmaan" / "writer.json").write_text("{}")
    loop_cloud.commit_and_push(other, writer="Nirmaan")

    clone, state = tmp_path / "c", tmp_path / "state"
    loop_cloud.clone_state(clone, str(remote))
    loop_cloud.import_state(clone, state)
    (state / "loop" / f"{PREFIX}-pr-8.json").write_text(json.dumps({"pr": 8}))
    (state / "loop" / "nirmaansoftware_Nirmaan-pr-9.json").write_text("{}")
    lines = [{"time": "2026-11-30T23:59:00+00:00", "repo": REPO, "n": 1}, {"time": "2026-12-01T00:00:01+00:00", "repo": REPO, "n": 2},
             {"time": "2026-12-01T00:00:02+00:00", "repo": "nirmaansoftware/Nirmaan"}]
    (state / "calls.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines) + "not json\n")
    loop_cloud.export_state(clone, state)
    assert loop_cloud.commit_and_push(clone)
    changed = sh(clone, "show", "--name-only", "--format=", "HEAD").split()
    assert changed and all(p.startswith(f"{WRITER}/") for p in changed), changed
    assert not (clone / WRITER / "loop" / "nirmaansoftware_Nirmaan-pr-9.json").exists()
    assert [json.loads(x)["n"] for x in (clone / WRITER / "calls" / "2026-11.jsonl").read_text().splitlines()] == [1]
    assert [json.loads(x)["n"] for x in (clone / WRITER / "calls" / "2026-12.jsonl").read_text().splitlines()] == [2]
    assert (clone / "Nirmaan" / "pause.json").read_text() == "{}"

    # A second run appends to the month file; an unchanged run commits nothing.
    state2 = tmp_path / "state2"
    loop_cloud.import_state(clone, state2)
    (state2 / "calls.jsonl").write_text(json.dumps({"time": "2026-12-02T00:00:00+00:00", "repo": REPO, "n": 3}) + "\n")
    loop_cloud.export_state(clone, state2)
    assert loop_cloud.commit_and_push(clone)
    assert [json.loads(x)["n"] for x in (clone / WRITER / "calls" / "2026-12.jsonl").read_text().splitlines()] == [2, 3]
    state3 = tmp_path / "state3"
    loop_cloud.import_state(clone, state3)
    loop_cloud.export_state(clone, state3)
    assert loop_cloud.commit_and_push(clone) is False


def test_the_shared_pause_is_the_latest_in_force_and_only_this_loops_own_is_written_back(tmp_path, remote):
    seeded(tmp_path, remote)
    clone = tmp_path / "c"
    loop_cloud.clone_state(clone, str(remote))
    now = datetime.now(timezone.utc)
    late = json.dumps({"until": (now + timedelta(minutes=20)).isoformat(), "repo": "nirmaansoftware/Nirmaan", "pr": 1})
    (clone / "Nirmaan").mkdir()
    (clone / "Nirmaan" / "pause.json").write_text(late)
    (clone / WRITER / "pause.json").write_text(json.dumps({"until": (now + timedelta(minutes=5)).isoformat(), "repo": REPO, "pr": 2}))
    (clone / "old").mkdir()
    (clone / "old" / "pause.json").write_text(json.dumps({"until": (now - timedelta(minutes=50)).isoformat()}))
    assert loop_cloud.shared_pause(clone) == late
    state = tmp_path / "state"
    loop_cloud.import_state(clone, state)
    assert pr_loop.read_pause(state)["repo"] == "nirmaansoftware/Nirmaan", "the loop pauses for the other loop's limit"
    mine_before = (clone / WRITER / "pause.json").read_text()
    loop_cloud.export_state(clone, state)
    assert (clone / WRITER / "pause.json").read_text() == mine_before, "another loop's pause is never copied into this folder"
    assert (clone / "Nirmaan" / "pause.json").read_text() == late

    mine = json.dumps({"until": (now + timedelta(minutes=30)).isoformat(), "repo": REPO, "pr": 3})
    (state / "loop" / "rate-limit-pause.json").write_text(mine)
    loop_cloud.export_state(clone, state)
    assert (clone / WRITER / "pause.json").read_text() == mine


def test_a_push_that_loses_the_race_rebases_onto_the_other_loop_and_keeps_both(tmp_path, remote):
    seeded(tmp_path, remote)
    ours, theirs = tmp_path / "ours", tmp_path / "theirs"
    loop_cloud.clone_state(ours, str(remote))
    loop_cloud.clone_state(theirs, str(remote))
    state = tmp_path / "state"
    loop_cloud.import_state(ours, state)
    (state / "calls.jsonl").write_text(json.dumps({"time": "2026-11-14T00:00:00+00:00", "repo": REPO}) + "\n")
    loop_cloud.export_state(ours, state)
    (theirs / "Nirmaan" / "calls").mkdir(parents=True)
    (theirs / "Nirmaan" / "calls" / "2026-11.jsonl").write_text("{}\n")
    assert loop_cloud.commit_and_push(theirs, writer="Nirmaan")
    slept = []
    assert loop_cloud.commit_and_push(ours, sleep=slept.append)
    assert slept == [1], "one rejected push, then a rebase and a retry"
    check = tmp_path / "check"
    loop_cloud.clone_state(check, str(remote))
    assert (check / "Nirmaan" / "calls" / "2026-11.jsonl").is_file() and (check / WRITER / "calls" / "2026-11.jsonl").is_file()


def test_a_second_writer_for_the_same_folder_stops_loudly(tmp_path, remote):
    seeded(tmp_path, remote)
    a, b = tmp_path / "a", tmp_path / "b"
    loop_cloud.clone_state(a, str(remote))
    loop_cloud.clone_state(b, str(remote))
    (a / WRITER / "pause.json").write_text("one")
    (b / WRITER / "pause.json").write_text("two")
    assert loop_cloud.commit_and_push(a)
    with pytest.raises(loop_cloud.SyncError, match="one writer per folder"):
        loop_cloud.commit_and_push(b, sleep=lambda s: None)
    assert sh(b, "status", "--porcelain") == "", "the rebase was aborted"


def _pull(n, **kw):
    return {"number": n, "draft": False, "head_repo": REPO, "base_ref": "main", "author": "patel-om", "labels": [], "head_sha": f"h{n}", **kw}


def test_has_work_follows_the_loops_skip_rules(tmp_path):
    state = tmp_path / "state"
    (state / "loop").mkdir(parents=True)
    assert loop_cloud.has_work([], state) is False
    assert loop_cloud.has_work([_pull(1, draft=True), _pull(2, author="someone"), _pull(3, head_repo="fork/x"),
                                _pull(4, labels=["needs-founder"]), _pull(5, labels=["hold"]), _pull(6, labels=["loop-stalled"])], state) is False
    assert loop_cloud.has_work([_pull(4, labels=["needs-founder"]), _pull(7, labels=["author-fix"])], state) is True
    pr_loop._save_state(state, REPO, {"pr": 4, "stopped": {"visible": False, "head": "h4"}})
    assert loop_cloud.has_work([_pull(4, labels=["needs-founder"])], state) is True, "a stop still to post"
    pr_loop._save_state(state, REPO, {"pr": 9, "done": {"outcome": "auto-merge"}})
    assert loop_cloud.has_work([], state) is True, "a finished pull request to note merged"
    pr_loop._save_state(state, REPO, {"pr": 9, "done": {"outcome": "auto-merge"}, "closed": {"merged_at": "x"}})
    pr_loop._save_state(state, REPO, {"pr": 4, "stopped": None})
    assert loop_cloud.has_work([], state) is False



class ReadyGitHub:
    """Reads only: each pull request's mergeable fields and its required CI conclusion."""

    def __init__(self, pulls: dict, ci: dict):
        self.pulls, self.ci = pulls, ci

    def get_pull(self, n):
        return {"head_sha": f"h{n}", "mergeable": True, "mergeable_state": "clean", **self.pulls.get(n, {})}

    def list_check_runs(self, sha):
        c = self.ci.get(sha, "success")
        return [{"id": i, "name": name, "status": "in_progress" if c == "pending" else "completed",
                 "conclusion": None if c == "pending" else c, "started_at": "2026-11-19T00:00:00Z"}
                for i, name in enumerate(pr_review.CONFIG["required_ci"])]


def test_ready_now_names_only_steps_a_pass_would_take_now(tmp_path):
    state = tmp_path / "state"
    (state / "loop").mkdir(parents=True)
    now = "2026-11-19T12:00:00+00:00"
    pulls = [_pull(n) for n in range(1, 10)] + [_pull(10, labels=["needs-founder"]), _pull(11, draft=True)]
    pr_loop._save_state(state, REPO, {"pr": 2, "done": {"head": "h2", "outcome": "auto-merge"}})
    pr_loop._save_state(state, REPO, {"pr": 3, "done": {"head": "h3", "outcome": "auto-merge"}})
    pr_loop._save_state(state, REPO, {"pr": 5, "stopped": {"head": "h5", "labeled": False, "visible": True}})
    pr_loop._save_state(state, REPO, {"pr": 6, "transient": {"head": "h6", "count": 1, "next_at": "2026-11-19T12:04:00+00:00"}})
    pr_loop._save_state(state, REPO, {"pr": 7, "author_fix": {"head": "h7"}})
    pr_loop._save_state(state, REPO, {"pr": 8, "last_fix_head": "h8"})
    pr_loop._save_state(state, REPO, {"pr": 10, "stopped": {"head": "h10", "labeled": True, "visible": False}})
    github = ReadyGitHub({3: {"mergeable_state": "behind"}, 9: {"mergeable": False, "mergeable_state": "dirty"}},
                         {"h4": "pending", "h8": "failure", "h1": "success"})
    ready = loop_cloud.ready_now(pulls, state, github, now=now)
    assert ready == [(1, "h1", "CI green: a review is due"), (3, "h3", "behind main"),
                     (8, "h8", "CI failed after a fix round"), (9, "h9", "a merge conflict to handle"),
                     (10, "h10", "a stop to post")], ready
    # Not ready: 2 finished on this head, 4 CI running, 5 stopped on this head, 6 in backoff, 7 waits for the author.
    assert loop_cloud.ready_now(pulls, state, github, now="2026-11-19T12:05:00+00:00")[1] == (3, "h3", "behind main")
    assert (6, "h6", "CI green: a review is due") in loop_cloud.ready_now(pulls, state, github, now="2026-11-19T12:05:00+00:00")
    # A failed CI with no fix round on this head is the author's: no step.
    pr_loop._save_state(state, REPO, {"pr": 8, "last_fix_head": None})
    assert all(r[0] != 8 for r in loop_cloud.ready_now(pulls, state, github, now=now))
    # A rate-limit pause in force: nothing is ready.
    pr_loop.pause_path(state).write_text(json.dumps({"until": "2026-11-19T12:30:00+00:00"}))
    assert loop_cloud.ready_now(pulls, state, github, now=now) == []


def test_next_chain_is_bounded_and_needs_progress():
    ready = [(1, "h1", "CI green: a review is due")]
    first = loop_cloud.next_chain("", ready)
    assert first == f"1:{loop_cloud.ready_digest(ready)}"
    assert loop_cloud.next_chain("0", []) is None, "nothing ready: the dispatcher's tick"
    assert loop_cloud.next_chain(first, ready) is None, "the same ready set again: the last pass made no progress on it"
    other = [(2, "h2", "behind main")]
    assert loop_cloud.next_chain(first, other) == f"2:{loop_cloud.ready_digest(other)}"
    assert loop_cloud.next_chain(f"{loop_cloud.CHAIN_MAX}:{'0' * 12}", other) is None, "at most CHAIN_MAX in a row"
    for bad in ("x", "1:zz", "-1", "1;rm", "1:" + "a" * 13, "1234"):
        assert loop_cloud.next_chain(bad, other) is None, bad


def test_run_chained_runs_the_next_pass_at_once_while_a_step_is_ready_and_stops_safely():
    lines, codes = [], []
    ready_sets = iter([[(1, "h1", "CI green: a review is due")], [(2, "h2", "behind main")], []])

    def once():
        codes.append(0)
        return 0
    assert loop_cloud.run_chained(once, lambda: next(ready_sets), out=lines.append) == 0
    assert len(codes) == 3 and lines[-1] == "loop-cloud: no chained pass"
    # The same ready set twice: the pass before made no progress, so no further pass.
    same = [(1, "h1", "CI green: a review is due")]
    codes.clear()
    assert loop_cloud.run_chained(once, lambda: same, out=lines.append) == 0
    assert len(codes) == 2
    # Never more than chain_max chained passes after the first.
    k = iter(range(100))
    codes.clear()
    assert loop_cloud.run_chained(once, lambda: [(next(k), "h", "behind main")], out=lines.append, chain_max=3) == 0
    assert len(codes) == 4
    # The time budget: no pass starts after it is spent.
    t = iter([0.0, 2000.0])
    codes.clear()
    assert loop_cloud.run_chained(once, lambda: same, clock=lambda: next(t), out=lines.append) == 0
    assert len(codes) == 1 and "time budget" in lines[-1]
    # A read error ends the chain without failing the job.
    def down():
        raise OSError("network down")
    codes.clear()
    assert loop_cloud.run_chained(once, down, out=lines.append) == 0 and len(codes) == 1 and "no chained pass" in lines[-1]
    # The first pass's exit code is the job's; a chained pass refused because the loop
    # scripts changed on main (exit 4) ends the chain quietly; any other failure fails.
    assert loop_cloud.run_chained(lambda: 4, lambda: same, out=lines.append) == 4
    results = iter([0, 4])
    assert loop_cloud.run_chained(lambda: next(results), lambda: [(9, "h9", "behind main")], out=lines.append) == 0
    results = iter([0, 1])
    assert loop_cloud.run_chained(lambda: next(results), lambda: [(9, "h9", "behind main")], out=lines.append) == 1


def test_the_run_subcommand_chains_and_shadow_runs_one_pass(monkeypatch):
    seen = []
    monkeypatch.setattr(loop_cloud, "SECRETS_FD_ENV", "NIRMAAN_TEST_NO_FD")
    monkeypatch.setenv("NIRMAAN_TEST_NO_FD", "x")
    monkeypatch.setattr(loop_cloud, "take_secrets", lambda: None)
    monkeypatch.setattr(pr_loop, "main", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(loop_cloud, "_ready_from_github", lambda: [])
    assert loop_cloud.main(["run"]) == 0 and seen == [["--once"]]
    assert loop_cloud.main(["run", "--shadow", "7"]) == 0 and seen[-1] == ["--once", "--no-post", "--pr", "7"]


def _simulate(chained: bool, phase: float, opens=(0.0, 3.0, 6.0, 30.0), ci=12.0, review=8.0, setup=3.0, tick=4.0,
              strict: bool = True) -> list[float]:
    """Open-to-merge minutes for pull requests opened at `opens`, on a model of the
    cloud loop: the dispatcher starts a run every `tick` minutes when none runs or
    waits; a run with open pull requests installs for `setup` minutes, then one
    pass steps them in order: a branch behind main is updated (CI runs again), a
    head whose CI finished is reviewed for `review` minutes and auto-merged (GitHub
    merges at once; with `strict`, every other open pull request is then behind
    main; the pass ends either way, as Loop._tick halts after an auto-merge), CI
    still running is skipped. With `chained`, the end of a run
    starts the next one at once when next_chain says so (the real function)."""
    prs = [{"n": i + 1, "open": t, "ci_done": t + ci, "head": 0, "behind": False, "merged": None} for i, t in enumerate(opens)]
    t, chain, queued, nxt_tick, job = 0.0, "", None, phase, 0.0
    while any(p["merged"] is None for p in prs) and t < 1000:
        if queued is not None:  # the same job: no new setup
            now, chain, queued = t, queued, None
        else:
            while nxt_tick < t:  # a tick while a run is going sees it busy and skips
                nxt_tick += tick
            job, chain, nxt_tick = nxt_tick + 0.2, "", nxt_tick + tick
            if not [p for p in prs if p["open"] <= job and p["merged"] is None]:
                t = job + 0.2  # has-work: nothing to step, the run ends
                continue
            now = job + setup
        for p in [p for p in prs if p["open"] <= now and p["merged"] is None]:
            if p["behind"]:
                p.update(behind=False, head=p["head"] + 1, ci_done=now + ci)
            elif now >= p["ci_done"]:
                now += review
                p["merged"] = now
                for q in prs if strict else []:
                    if q is not p and q["merged"] is None and q["open"] <= now:
                        q["behind"] = True
                break
        t = now
        ready = [(p["n"], f"h{p['n']}.{p['head']}", "behind main" if p["behind"] else "CI green")
                 for p in prs if p["open"] <= t and p["merged"] is None and (p["behind"] or t >= p["ci_done"])]
        if chained and t - (job + setup) < loop_cloud.CHAIN_BUDGET_S / 60:
            queued = loop_cloud.next_chain(chain, ready)
    return [p["merged"] - p["open"] for p in prs]


def test_a_simulated_timeline_merges_sooner_with_chained_passes():
    """Chained passes never make a pull request merge later. With the Mac's
    dispatcher (a tick every 4 minutes) they save a few minutes a pull request
    (no wait for the tick and no second setup); with no dispatcher tick for an
    hour (the Mac asleep, GitHub's schedule late) they keep the queue moving and
    cut open-to-merge by about half. A pass that ends after the chain budget is
    never chained. Means and medians over 16 dispatcher phases each."""
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    median = lambda xs: sorted(xs)[len(xs) // 2]  # noqa: E731
    for tick, strict, opens, review in [(4, False, (0.0, 3.0, 6.0, 30.0), 8.0), (4, False, (0.0, 1.0, 2.0, 3.0, 4.0), 12.0),
                                        (4, True, (0.0, 3.0, 6.0, 30.0), 8.0), (60, False, (0.0, 3.0, 6.0, 30.0), 8.0),
                                        (60, True, (0.0, 1.0, 2.0, 3.0, 4.0), 12.0), (4, False, (0.0, 1.0, 2.0, 3.0, 4.0), 25.0)]:
        phases = [k * tick / 16 for k in range(16)]
        runs = [(_simulate(False, ph, opens, review=review, tick=tick, strict=strict),
                 _simulate(True, ph, opens, review=review, tick=tick, strict=strict)) for ph in phases]
        assert all(a <= b for before, after in runs for a, b in zip(after, before)), "never later"
        before, after = [m for b, _ in runs for m in b], [m for _, a in runs for m in a]
        print(f"tick {tick} strict {strict} opens {opens} review {review}: open-to-merge mean "
              f"{mean(before):.1f} -> {mean(after):.1f}, median {median(before):.1f} -> {median(after):.1f} minutes")
        if review >= loop_cloud.CHAIN_BUDGET_S / 60:
            assert after == before, "a pass that ends after the budget is never chained"
        elif not strict or tick == 60:
            assert mean(after) < mean(before)
        if tick == 60:
            assert mean(after) < 0.7 * mean(before)


FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
fd = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR")
token = os.read(int(fd), 4096).decode() if fd else None
with open(LOG, "a") as log:
    log.write(json.dumps({"args": sys.argv[1:3], "env": sorted(os.environ), "token": token}) + "\\n")
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": token is not None, "authMethod": "oauth_token" if token else "none"}))
else:
    print(json.dumps({"subtype": "success", "is_error": token is None, "result": "" if token else "Not logged in",
                      "structured_output": {"ok": True}}))
"""


def _fake_claude(tmp_path) -> str:
    """A claude that logs (to tmp_path/log.jsonl: claude gets only the allowlisted environment) what it was given."""
    path = tmp_path / "claude"
    path.write_text(FAKE_CLAUDE.replace("open(LOG,", f"open({str(tmp_path / 'log.jsonl')!r},"))
    path.chmod(0o755)
    return str(path)


def test_the_plan_token_reaches_claude_only_through_a_pipe(tmp_path, monkeypatch):
    fake, log = _fake_claude(tmp_path), tmp_path / "log.jsonl"
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "from-env")
    pr_review.set_plan_token("plan-token")
    try:
        assert loop_cloud.auth_status(fake) == (True, "logged in with the OAuth token")
        assert loop_cloud.login_call(fake, str(tmp_path))[0] is True
        assert pr_review.run_once(fake, ["-p"], "x", str(tmp_path), 30)["kind"] == "ok"
    finally:
        pr_review.set_plan_token(None)
    calls = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(calls) == 3 and all(c["token"] == "plan-token" for c in calls)
    assert not any("CLAUDE_CODE_OAUTH_TOKEN" in c["env"] for c in calls), "never in a claude environment"
    assert loop_cloud.auth_status(fake)[0] is False, "no token handed over"
    assert pr_review.run_once(fake, ["-p"], "x", str(tmp_path), 30)["kind"] == "error"


def test_handoff_moves_the_secrets_out_of_the_environment_before_anything_runs(tmp_path):
    seen = {}
    env = {"PATH": "/p", "CLAUDE_CODE_OAUTH_TOKEN": "c", "GH_TOKEN": "g", pr_review.APP_TOKEN_ENV: "a"}
    loop_cloud.handoff(["run"], env, execve=lambda path, argv, e: seen.update(argv=argv, env=e))
    assert seen["argv"][1:] == [str(ROOT / "scripts" / "loop_cloud.py"), "run"]
    assert not set(loop_cloud.SECRET_NAMES) & set(seen["env"])
    with open(int(seen["env"][loop_cloud.SECRETS_FD_ENV]), encoding="utf-8") as handle:
        assert json.load(handle) == {"CLAUDE_CODE_OAUTH_TOKEN": "c", "GH_TOKEN": "g", pr_review.APP_TOKEN_ENV: "a"}


def test_auth_check_end_to_end_re_executes_without_the_secrets(tmp_path):
    fake, log = _fake_claude(tmp_path), tmp_path / "log.jsonl"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "NIRMAAN_CLAUDE_CODE": fake,
           "CLAUDE_CODE_OAUTH_TOKEN": "plan", "GH_TOKEN": "gh"}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "loop_cloud.py"), "auth-check"], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "the plan answered" in proc.stdout and "plan" not in proc.stderr
    calls = [json.loads(x) for x in log.read_text().splitlines()]
    assert [c["token"] for c in calls] == ["plan", "plan"] and not any("GH_TOKEN" in c["env"] for c in calls)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN")
    assert subprocess.run([sys.executable, str(ROOT / "scripts" / "loop_cloud.py"), "auth-check"], env=env,
                          capture_output=True, text=True).returncode == 1


def test_reviewers_and_the_fixer_hold_no_token_and_proc_is_denied():
    env = {"HOME": "/h", "PATH": "/p", "CLAUDE_CODE_OAUTH_TOKEN": "t", "GH_TOKEN": "x", pr_review.APP_TOKEN_ENV: "y"}
    assert sorted(pr_review.reviewer_env(env)) == ["HOME", "PATH"]
    for args in (pr_review.claude_args("m", "s", []), pr_loop.fixer_args("m", "s", [])):
        assert "Read(//proc/**)" in args[args.index("--disallowedTools") + 1].split(",")
        assert "--bare" not in args, "--bare never reads the OAuth token"


def test_checks_run_as_the_check_account_with_exactly_their_environment():
    env = {"PATH": "/p", "HOME": "/h2"}
    assert pr_loop.check_argv(["python", "-m", "pytest"], env, None) == ["python", "-m", "pytest"]
    assert pr_loop.check_argv(["python"], env, "loopcheck") == ["sudo", "-n", "-u", "loopcheck", "--", "env", "-i", "PATH=/p", "HOME=/h2", "python"]
    assert pr_loop.loop_defaults({"NIRMAAN_LOOP_CHECK_USER": "loopcheck"})["check_user"] == "loopcheck"
    assert pr_loop.loop_defaults({})["check_user"] is None


def _concurrent_checks(monkeypatch, tmp_path, user):
    """Two workers' checks at once (parallel_reviews 2); subprocess and sudo are faked.
    Returns the events and the most check commands seen running at once."""
    state = {"running": 0, "most": 0, "events": []}
    guard = threading.Lock()
    # Without the check account both checks must be running together before either finishes, so the
    # peak is exact on a slow runner. With it they are serialised and must never meet.
    meet = threading.Barrier(2, timeout=30) if user is None else None

    def fake_run(argv, **kw):
        if "pkill" in argv or ("chown" in argv and "-R" in argv):
            with guard:
                state["events"].append(("cleanup", state["running"]))
        elif argv[-1] == "suite":
            with guard:
                state["running"] += 1
                state["most"] = max(state["most"], state["running"])
            if meet is not None:
                meet.wait()
            time.sleep(0.2)
            with guard:
                state["running"] -= 1
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pr_loop.subprocess, "run", fake_run)
    monkeypatch.setattr(pr_loop.pwd, "getpwnam", lambda name: types.SimpleNamespace(pw_gid=os.getgid()))
    results = []
    threads = [threading.Thread(target=lambda d=d: results.append(pr_loop._run_commands(
        [["suite"]], str(d), None, {}, 5, user))) for d in (tmp_path / "a", tmp_path / "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert results == [(True, ""), (True, "")]
    return state["events"], state["most"]


def test_check_account_runs_never_overlap_so_cleanup_cannot_kill_another_check(monkeypatch, tmp_path):
    # Actions run 43629454383: ip#205 and ip#204 died at exit -9 when the other worker's pkill ran.
    events, most = _concurrent_checks(monkeypatch, tmp_path, "loopcheck")
    assert most == 1
    assert len(events) == 4 and all(running == 0 for _, running in events)


def test_checks_without_the_check_account_still_run_in_parallel(monkeypatch, tmp_path):
    events, most = _concurrent_checks(monkeypatch, tmp_path, None)
    assert most == 2 and events == []


def test_the_cli_is_pinned_with_its_integrity_hashes():
    lock = json.loads((ROOT / ".github" / "review-loop" / "package-lock.json").read_text())
    pkgs = lock["packages"]
    assert pkgs["node_modules/@anthropic-ai/claude-code"]["version"] == "2.1.325"
    for name in ("node_modules/@anthropic-ai/claude-code", "node_modules/@anthropic-ai/claude-code-linux-x64"):
        assert pkgs[name]["integrity"].startswith("sha512-") and pkgs[name]["version"] == "2.1.325"


def test_the_loop_posts_with_a_minted_app_token(monkeypatch):
    github, post = pr_loop.github_client(REPO, False, {pr_review.APP_TOKEN_ENV: "minted"})
    assert post == "app" and github.token == "minted"
    monkeypatch.setattr(pr_review, "_gh_token", lambda: "gh")
    assert pr_loop.github_client(REPO, True, {pr_review.APP_TOKEN_ENV: "minted"})[1] == "none"
    assert pr_loop.github_client(REPO, False, {})[1] == "dry-run"


def test_the_workflow_lands_off_runs_from_main_only_and_keeps_secrets_in_the_environment():
    on = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in on and "workflow_dispatch:" in on
    assert "pull_request" not in WORKFLOW and "push:" not in on
    assert re.search(r"^concurrency:\n  group: review-loop\n  cancel-in-progress: false$", WORKFLOW, re.MULTILINE)
    job_if = WORKFLOW.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
    assert "github.ref == 'refs/heads/main'" in job_if
    assert "vars.REVIEW_LOOP_CLOUD == 'on' && (github.event_name == 'schedule' || inputs.mode == 'loop')" in job_if
    assert "    environment: review-loop\n" in WORKFLOW
    assert "npm ci --prefix .github/review-loop" in WORKFLOW and "npm install" not in WORKFLOW
    assert "NIRMAAN_LOOP_CHECK_USER: loopcheck" in WORKFLOW and "useradd --system" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    for tool in ("verilator iverilog yosys gcc-riscv64-unknown-elf", "tools: sby yices-smt2 eqy"):
        assert tool in WORKFLOW
    assert 'sudo mv "$RUNNER_TEMP/oss-cad-suite" /opt/oss-cad-suite' in WORKFLOW and "echo /opt/cad-bin >> \"$GITHUB_PATH\"" in WORKFLOW, \
        "the check account cannot enter $RUNNER_TEMP, so the formal tools move where it can run them"
    steps = WORKFLOW.split("\n      - ")[1:]
    holders = {s: sorted(set(re.findall(r"secrets\.(\w+)", s))) for s in steps if "secrets." in s}
    by_name = {re.search(r"name: (.+)", s).group(1).strip(): v for s, v in holders.items()}
    assert by_name == {
        "Mint the review App token": ["REVIEW_APP_ID", "REVIEW_APP_INSTALLATION_ID", "REVIEW_APP_PRIVATE_KEY"],
        "Pull the loop state": ["LOOP_STATE_DEPLOY_KEY"],
        "Check the Claude login": ["CLAUDE_CODE_OAUTH_TOKEN"],
        "Run the loop once": ["CLAUDE_CODE_OAUTH_TOKEN", "LOOP_GH_TOKEN"],
        "Push the loop state": ["LOOP_STATE_DEPLOY_KEY"],
    }, "no step that holds the deploy key or the App key runs a model"
    run_step = next(s for s in steps if s.startswith("name: Run the loop once"))
    login_step = next(s for s in steps if s.startswith("name: Check the Claude login"))
    for step in (run_step, login_step):
        runs = [line.strip() for line in step.split("run: |", 1)[1].splitlines() if "loop_cloud.py" in line]
        assert runs and all("exec python scripts/loop_cloud.py" in line for line in runs), "the secrets leave the shell's environment"
    assert 'run --shadow "$SHADOW_PR"' in run_step
    for s in steps:
        if "run: " in s:
            assert "${{" not in s.split("run: ", 1)[1], "inputs and outputs reach a script only through env"


def test_a_missing_argument_prints_usage_and_exits_2(capsys):
    for argv in ([], ["seed", "--clone", "x"], ["push", "--clone", "x"], ["pull"], ["has-work"], ["nope"]):
        assert loop_cloud.main(argv) == 2, argv
        assert "usage: python scripts/loop_cloud.py" in capsys.readouterr().err


SCAN_CLAUDE = """#!/usr/bin/env python3
import glob, json, os, sys
fd = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR")
token = os.read(int(fd), 4096).decode() if fd else ""
hits = []
for path in glob.glob("/proc/[0-9]*/environ"):
    try:
        data = open(path, "rb").read()
    except OSError:
        continue
    hits += [path for s in SECRETS if s.encode() in data]
with open(LOG, "a") as log:
    log.write(json.dumps({"token": token, "hits": hits}) + "\\n")
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True, "authMethod": "oauth_token"}))
else:
    print(json.dumps({"subtype": "success", "is_error": False, "result": "", "structured_output": {"ok": True}}))
"""


@pytest.mark.skipif(not Path("/proc/self/environ").exists(), reason="Linux only: /proc/<pid>/environ (CI runs it on every head)")
def test_on_linux_no_readable_process_environment_holds_a_secret_after_the_handoff(tmp_path):
    secrets = {"CLAUDE_CODE_OAUTH_TOKEN": "plan-" + "P" * 30, "GH_TOKEN": "gh-" + "G" * 30, pr_review.APP_TOKEN_ENV: "app-" + "A" * 30}
    log = tmp_path / "log.jsonl"
    fake = tmp_path / "claude"
    fake.write_text(SCAN_CLAUDE.replace("SECRETS", repr(list(secrets.values()))).replace("open(LOG,", f"open({str(log)!r},"))
    fake.chmod(0o755)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "NIRMAAN_CLAUDE_CODE": str(fake), **secrets}
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "loop_cloud.py"), "auth-check"], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    calls = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(calls) == 2
    assert all(c["token"] == secrets["CLAUDE_CODE_OAUTH_TOKEN"] for c in calls), "the token came through the pipe"
    assert all(c["hits"] == [] for c in calls), calls


def test_the_check_clone_has_its_own_objects_and_leaves_the_worktree_alone(tmp_path):
    repo = tmp_path / "repo"
    sh(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "a.txt").write_text("one\n")
    sh(repo, "add", "-A")
    sh(repo, *loop_cloud.COMMITTER, "commit", "-qm", "one")
    sha = sh(repo, "rev-parse", "HEAD").strip()
    root = pr_loop.check_clone(str(repo), sha)
    try:
        clone = root / "repo"
        assert root.parent == Path(tempfile.gettempdir()).resolve() or str(root).startswith(tempfile.gettempdir())
        assert sh(clone, "rev-parse", "HEAD").strip() == sha and (clone / "a.txt").read_text() == "one\n"
        assert not (clone / ".git" / "objects" / "info" / "alternates").exists(), "no alternates back to the loop's objects"
        (clone / ".git" / "config").write_text("[core]\n\tsshCommand = evil\n")
        (clone / "a.txt").write_text("changed\n")
        assert "evil" not in (repo / ".git" / "config").read_text() and (repo / "a.txt").read_text() == "one\n"
    finally:
        pr_review._rmtree(root)


def test_the_isolation_check_needs_linux_and_the_check_account():
    if not Path("/proc/self/environ").exists():
        assert loop_cloud.isolation_check("loopcheck")[0] is False
    loop_cloud._HELD[:] = []
    assert loop_cloud.environ_holders([]) == []
