"""R7: the review loop in GitHub Actions (scripts/loop_cloud.py, .github/workflows/review-loop.yml).

The state repository is a local bare repository here; two writers (the cloud
IP loop and a second loop) share it the way docs/REVIEW_MECHANISM.md says.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
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


def _fake_claude(tmp_path, status: dict) -> str:
    path = tmp_path / "claude"
    path.write_text(f"#!/bin/sh\necho '{json.dumps(status)}'\n")
    path.chmod(0o755)
    return str(path)


def test_auth_check_needs_the_oauth_token_and_no_api_key(tmp_path):
    good = _fake_claude(tmp_path, {"loggedIn": True, "authMethod": "oauth_token"})
    assert loop_cloud.auth_status(good, {"PATH": "/usr/bin:/bin"})[0] is True
    assert loop_cloud.auth_status(good, {"PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": "x"})[0] is False
    other = _fake_claude(tmp_path, {"loggedIn": True, "authMethod": "claude.ai"})
    assert loop_cloud.auth_status(other, {"PATH": "/usr/bin:/bin"})[0] is False


def test_only_the_claude_process_gets_the_plan_token_and_proc_is_denied(monkeypatch):
    env = {"HOME": "/h", "PATH": "/p", "CLAUDE_CODE_OAUTH_TOKEN": "t", "GH_TOKEN": "x", pr_review.APP_TOKEN_ENV: "y", "ANTHROPIC_API_KEY": "k"}
    assert sorted(pr_review.model_env(env)) == ["CLAUDE_CODE_OAUTH_TOKEN", "HOME", "PATH"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in pr_review.reviewer_env(env), "the loop's local checks run without it"
    for args in (pr_review.claude_args("m", "s", []), pr_loop.fixer_args("m", "s", [])):
        assert "Read(//proc/**)" in args[args.index("--disallowedTools") + 1].split(",")
        assert "--bare" not in args, "--bare never reads the OAuth token"


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
    assert "npm install -g @anthropic-ai/claude-code@2.1.325" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    for tool in ("verilator iverilog yosys gcc-riscv64-unknown-elf", "tools: sby yices-smt2 eqy"):
        assert tool in WORKFLOW
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
    assert "python scripts/pr_loop.py --once --no-post --pr \"$SHADOW_PR\"" in run_step
    for s in steps:
        if "run: " in s:
            assert "${{" not in s.split("run: ", 1)[1], "inputs and outputs reach a script only through env"
