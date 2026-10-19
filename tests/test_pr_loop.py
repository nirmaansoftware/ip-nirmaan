"""The automated review loop (scripts/pr_loop.py): review, fix, review again, merge path.

Runs against a fake `claude` that plays both the reviewers and the fixer
(tests/fixtures/pr_loop/fake_claude.py), a local bare repository as origin, and
a fake GitHub. No model is called and nothing touches the network.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("pr_loop", ROOT / "scripts" / "pr_loop.py")
pr_loop = importlib.util.module_from_spec(_spec)
sys.modules["pr_loop"] = pr_loop
_spec.loader.exec_module(pr_loop)
pr_review = sys.modules["pr_review"]
CONFIG = pr_review.CONFIG

# The real loop settings, with a local check the tests can make fail.
LOOP = {**pr_loop.LOOP, "checks": [{"name": "dashes", "when": ["**"], "run": [
    ["{python}", "-c", "import os, sys; sys.exit(1 if os.path.exists('FAIL_CHECK') else 0)"]]}]}

MAP = """version: 1
teams:
  council:
    name: Council
    key2: chair
    leads: [security]
    members: []
  eda-platform:
    name: EDA and Platform
    leads: [eda-tooling]
    members: []
rules:
  - team: eda-platform
    paths: ['**']
  - team: council
    lead: security
    paths: [CLAUDE.md, .github/**]
sections: []
ledger:
  paths: []
  sections: []
content_rules: []
founder_classes:
  - id: control-plane
    title: Control plane
    paths: [.github/**, CLAUDE.md]
"""
SEATS = ["chair", "security", "eda-tooling", "founder-proxy"]
RECORD = "council/records/2026-10-17-teams-and-pr-review.md"


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(root: Path, rel: str, text: str):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)


class FakeGitHub:
    def __init__(self, origin: Path, gh: dict):
        self.origin, self.posts, self.merges, self.reviews, self.api_calls = origin, [], [], [], []
        self.auto_merge_allowed, self.settings_error = gh.get("auto_merge_allowed", "true"), gh.get("settings_error")
        self.labels = list(gh.get("labels", []))
        self.merge_error, self.body = gh.get("merge_error"), "Changes line two."
        self.ci = gh.get("ci", lambda sha: "success")
        self.draft, self.author, self.mergeable = gh.get("draft", False), gh.get("author", "patel-om"), gh.get("mergeable", True)
        # GitHub's mergeable_state "behind" (main has commits the branch lacks
        # and GitHub reports it as blocking). behind_when() can turn it on
        # mid-run; update_error makes the update fail the way gh does;
        # before_update() runs first (a person's push); update_async leaves the
        # branch as it was (GitHub has not made the merge commit yet).
        self.behind, self.behind_when, self.update_error, self.before_update, self.update_async = False, None, None, None, False
        self.updates = []

    def head(self):
        return sh(self.origin, "rev-parse", "refs/heads/feature")

    def get_pull(self, n):
        head = self.head()
        sh(self.origin, "update-ref", "refs/pull/1/head", head)  # GitHub keeps this in step with the branch
        return {"number": 1, "state": "open", "draft": self.draft, "title": "Change app", "body": self.body, "author": self.author,
                "labels": list(self.labels), "head_sha": head, "head_ref": "feature", "head_repo": CONFIG["repo"],
                "base_ref": "main", "base_repo": CONFIG["repo"], "mergeable": self.mergeable,
                "mergeable_state": "dirty" if self.mergeable is False else
                "behind" if self.behind or (self.behind_when and self.behind_when()) else "clean"}

    def list_open_pulls(self):
        return [self.get_pull(1)]

    def update_pull_body(self, n, body):
        self.posts.append({"type": "body", "body": body})
        self.body = body

    def run_gh(self, args):
        """gh with the gh login. `gh api repos/<repo>` answers the repository's
        allow_auto_merge field (or fails when the test sets settings_error);
        `gh pr merge` records the call, and fails the way the loop's real runner
        does (CalledProcessError, message on stderr) when the test sets
        merge_error."""
        if args[0] == "api" and "PUT" in args:
            return self.update_branch(args)
        if args[0] == "api":
            self.api_calls.append(args)
            if self.settings_error:
                raise subprocess.CalledProcessError(1, ["gh", *args], output="", stderr=self.settings_error)
            return f"{self.auto_merge_allowed}\n"
        self.merges.append(args)
        if self.merge_error:
            raise subprocess.CalledProcessError(1, ["gh", *args], output="", stderr=self.merge_error)

    def update_branch(self, args):
        """What GitHub's update-branch does: merge main into the pull request
        branch (a merge commit) when the branch head is still the expected one."""
        self.updates.append(args)
        if self.before_update:
            self.before_update()
        expected = next(a for a in args if a.startswith("expected_head_sha=")).split("=", 1)[1]
        if self.update_error or self.head() != expected:
            raise subprocess.CalledProcessError(1, ["gh", *args], output="",
                                                stderr=self.update_error or "gh: expected head sha did not match current head ref (HTTP 422)")
        if self.update_async:
            return '{"message":"Updating pull request branch."}'
        tmpw = self.origin.parent / f"upd-{len(self.updates)}"
        sh(self.origin.parent, "clone", "-q", "-b", "feature", str(self.origin), str(tmpw))
        sh(tmpw, "config", "user.email", "gh@example.com")
        sh(tmpw, "config", "user.name", "GitHub")
        sh(tmpw, "merge", "-q", "--no-ff", "--no-edit", "origin/main")
        sh(tmpw, "push", "-q", "origin", "feature")
        shutil.rmtree(tmpw)
        self.behind = False
        return '{"message":"Updating pull request branch."}'

    def add_labels(self, n, labels):
        self.posts.append({"type": "label", "labels": labels})
        self.labels += labels

    def list_reviews(self, n):
        return self.reviews

    def list_check_runs(self, sha):
        c = self.ci(sha)
        return [{"name": name, "status": "in_progress" if c == "pending" else "completed",
                 "conclusion": None if c == "pending" else c, "url": None, "completed_at": "x"} for name in CONFIG["required_ci"]]

    def list_comments(self, n):
        return []

    def create_comment(self, n, body):
        self.posts.append({"type": "comment", "body": body})
        return f"https://github.example/pr/1#c{len(self.posts)}"

    def create_check_run(self, name, head_sha, state, title, summary, details_url=None):
        self.posts.append({"type": "check", "name": name, "state": state, "title": title})

    def create_status(self, sha, context, state, description, target_url=None):
        self.posts.append({"type": "status", "name": context, "state": state, "title": description})


class Repo:
    def __init__(self, tmp: Path, reviews, fixes, change, gh):
        self.origin, self.work = tmp / "origin.git", tmp / "work"
        sh(tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh(tmp, "init", "-q", "-b", "main", str(self.work))
        w = self.work
        sh(w, "config", "user.email", "agent@example.com")
        sh(w, "config", "user.name", "Agent")
        sh(w, "remote", "add", "origin", str(self.origin))
        write(w, ".github/review-teams.yml", MAP)
        write(w, "CLAUDE.md", "# CLAUDE.md\nRULES-MARKER-FROM-MAIN\n")
        for seat in SEATS:
            write(w, f"council/{seat}.md", f"# {seat}\nSEAT-MARKER-{seat}\n\n## In a review (key 1)\nREVIEW-MARKER-{seat}\n")
        write(w, RECORD, "# Record\n\n### Every key 1 (base)\nBASE-MARKER\n")
        write(w, "src/app.py", "one\ntwo\nthree\n")
        sh(w, "add", "-A")
        sh(w, "commit", "-qm", "main")
        sh(w, "push", "-q", "origin", "main")
        sh(w, "checkout", "-qb", "feature")
        (change or (lambda x: write(x, "src/app.py", "one\ntwo changed\nthree\n")))(w)
        sh(w, "add", "-A")
        sh(w, "commit", "-qm", "Change app")
        sh(w, "push", "-q", "origin", "feature")
        self.first_head = sh(w, "rev-parse", "HEAD")
        sh(w, "checkout", "-q", "main")
        self.fake = tmp / "fake"
        self.fake.mkdir()
        self.bin = self.fake / "claude.py"
        shutil.copy(ROOT / "tests" / "fixtures" / "pr_loop" / "fake_claude.py", self.bin)
        self.bin.chmod(self.bin.stat().st_mode | stat.S_IEXEC)
        self.scenario(reviews, fixes)
        self.state = tmp / "state"
        self.github = FakeGitHub(self.origin, gh)

    def scenario(self, reviews, fixes):
        (self.fake / "scenario.json").write_text(json.dumps({"reviews": reviews, "fixes": fixes}))

    def loop(self, **extra):
        kwargs = dict(repo_root=str(self.work), github=self.github, post="app", claude_bin=str(self.bin), state_dir=self.state,
                      models={"key1": "k1", "key2": "k2", "proxy": "proxy-model"}, timeout_s=30, backoff_s=0, fixer_model="fixer-model",
                      fixer_timeout_s=30, check_timeout_s=30, sleep=lambda s: None, out=lambda s: None,
                      run_gh=self.github.run_gh, loop=LOOP)
        kwargs.update(extra)
        return pr_loop.Loop(**kwargs)

    def tick(self, **extra):
        return [r["outcome"] for r in self.loop(**extra).tick()]

    def origin_head(self):
        return self.github.head()

    def calls(self):
        f = self.fake / "calls.jsonl"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def log(self):
        f = self.state / "calls.jsonl"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def comments(self):
        return [p["body"] for p in self.github.posts if p["type"] == "comment"]

    def labeled(self):
        return any(p["type"] == "label" and "needs-founder" in p["labels"] for p in self.github.posts)

    def st(self):
        return pr_loop.load_state(self.state, CONFIG["repo"], 1)

    def advance_main(self, rel="src/other.py"):
        """A new commit on main in origin, so the branch is really behind."""
        w = self.work
        sh(w, "checkout", "-q", "main")
        sh(w, "pull", "-q", "origin", "main")
        write(w, rel, f"main moved {len(sh(w, 'rev-list', 'HEAD').split())}\n")
        sh(w, "add", "-A")
        sh(w, "commit", "-qm", "main moves")
        sh(w, "push", "-q", "origin", "main")
        self.github.behind = True


@pytest.fixture
def repo(tmp_path):
    def make(reviews=None, fixes=None, change=None, gh=None):
        return Repo(tmp_path, reviews or [{"verdict": "pass"}], fixes or [{"edits": {"src/app.py": "fixed\n"}}], change, gh or {})
    return make


def fail(text, line=1, file="src/app.py"):
    return {"verdict": "fail", "findings": [{"file": file, "line": line, "severity": "critical", "text": text}]}


# --- Merge path ------------------------------------------------------------------


def test_both_keys_pass_auto_merge_with_the_app_and_the_setting_then_nothing_more_on_that_head(repo):
    r = repo()
    assert r.tick() == ["auto-merge"]
    assert r.github.api_calls == [["api", f"repos/{CONFIG['repo']}", "--jq", ".allow_auto_merge"]]
    assert r.github.merges == [["pr", "merge", "1", "--repo", CONFIG["repo"], "--auto", "--merge", "--match-head-commit", r.first_head]]
    assert "Auto-merge is on" in r.comments()[-1]
    assert len(r.calls()) == 2
    before = len(r.github.posts)
    assert r.tick() == ["skip"]
    assert len(r.github.posts) == before and len(r.calls()) == 2


def test_both_keys_pass_and_the_setting_is_off_posts_ready_without_a_merge_call_or_a_stop(repo):
    r = repo(gh={"auto_merge_allowed": "false"})
    assert r.tick() == ["ready"]
    assert r.github.api_calls == [["api", f"repos/{CONFIG['repo']}", "--jq", ".allow_auto_merge"]], "the setting is read with the gh login"
    assert r.github.merges == [], "no merge is asked for when the setting is off"
    assert "waiting for the founder's merge settings" in r.comments()[-1] and "does not allow auto-merge" in r.comments()[-1]
    assert not r.labeled()
    assert r.tick() == ["skip"]


def test_the_merge_decision_does_not_depend_on_gh_error_wording_a_not_allowed_message_stops(repo):
    r = repo(gh={"merge_error": "GraphQL: Pull request Auto merge is not allowed for this repository (enablePullRequestAutoMerge)"})
    assert r.tick() == ["stopped"]
    assert len(r.github.merges) == 1
    assert r.labeled(), "fails safe: needs-founder, never ready and never merged"
    assert not any("Auto-merge is on" in c or "### Automated loop: ready" in c for c in r.comments())


def test_both_keys_pass_and_any_other_merge_error_stops_with_needs_founder(repo):
    r = repo(gh={"merge_error": "GraphQL: Head branch was modified. Review and try the merge again. (enablePullRequestAutoMerge)"})
    assert r.tick() == ["stopped"]
    assert len(r.github.merges) == 1
    assert r.labeled()
    last = r.comments()[-1]
    assert "Automated loop stopped" in last and "gh pr merge --auto failed (exit 1)" in last and "Head branch was modified" in last
    assert not any("Auto-merge is on" in c or "### Automated loop: ready" in c for c in r.comments())


@pytest.mark.parametrize("gh", [{"settings_error": "gh: Not Found (HTTP 404)"}, {"auto_merge_allowed": "null"}])
def test_an_unreadable_auto_merge_setting_stops_with_needs_founder_and_no_merge_call(repo, gh):
    r = repo(gh=gh)
    assert r.tick() == ["stopped"]
    assert r.github.merges == []
    assert r.labeled()
    assert "could not read the repository's auto-merge setting" in r.comments()[-1]


def test_gh_error_text_is_redacted_before_it_is_posted_or_saved(repo):
    token = "ghs_" + "A1b2" * 9
    pat = "github_pat_" + "x9" * 30
    r = repo(gh={"merge_error": f"fatal: https://x-access-token:{token}@github.com/o/r.git refused; Authorization: Bearer {pat}; header token {token}"})
    assert r.tick() == ["stopped"]
    last = r.comments()[-1]
    assert token not in last and pat not in last and "x-access-token:" not in last
    assert "[redacted]" in last
    assert token not in json.dumps(r.st()), "the state file keeps the redacted reason too"
    assert token not in json.dumps(r.log())


def test_the_real_gh_runner_returns_standard_output_so_the_setting_can_be_read(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, 0, stdout="true\n", stderr="")
    monkeypatch.setattr(pr_loop.subprocess, "run", fake_run)
    assert pr_loop.run_gh(["api", "repos/o/r", "--jq", ".allow_auto_merge"]) == "true\n"
    assert seen["cmd"] == ["gh", "api", "repos/o/r", "--jq", ".allow_auto_merge"]
    assert seen["kw"]["check"] is True and seen["kw"]["timeout"] == 300


def test_a_dry_run_posts_ready_and_never_calls_gh(repo):
    r = repo()
    assert r.tick(post="dry-run") == ["ready"]
    assert r.github.merges == [] and r.github.api_calls == []
    assert "waiting for the founder's merge settings" in r.comments()[-1] and "review App is not configured" in r.comments()[-1]


# --- The fix loop ----------------------------------------------------------------


def test_fail_fix_pass_runs_a_separate_fixer_then_commits_checks_pushes_and_reviews_again(repo, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "must-not-leak")
    r = repo(reviews=[fail("Line two lost its test"), {"verdict": "pass"}, {"verdict": "pass"}],
             fixes=[{"edits": {"src/app.py": "one\ntwo fixed\nthree\n"}}])
    assert r.tick() == ["fixed"]
    new = r.origin_head()
    assert new != r.first_head and sh(r.origin, "rev-parse", f"{new}^") == r.first_head
    msg = sh(r.origin, "log", "-1", "--format=%B", new)
    assert msg.startswith(f"Fix round 1: address review findings on {r.first_head[:7]}")
    assert "F1 [critical] src/app.py:1: Line two lost its test" in msg
    assert msg.endswith("Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    assert sh(r.origin, "log", "-1", "--format=%an", new) == "Agent"
    comment = r.comments()[-1]
    assert "fix round 1 of 3" in comment and "| F1 | 1 (eda-platform) | critical | `src/app.py:1` |" in comment
    assert "dashes: pass" in comment and "voids both keys" in comment

    fixer = next(c for c in r.calls() if c["kind"] == "fixes")
    assert fixer["cwd"].endswith("/head") and not fixer["cwd"].startswith(str(r.work))
    a = fixer["argv"]
    assert a[a.index("--tools") + 1] == "Read,Grep,Glob,Edit,Write"
    assert a[a.index("--allowedTools") + 1] == "Read,Grep,Glob,Edit(./**),Write(./**)"
    denied = a[a.index("--disallowedTools") + 1].split(",")
    for d in ("Bash", "WebFetch", "Edit(./.github/**)", "Write(./council/**)", "Edit(./pyproject.toml)"):
        assert d in denied
    assert a[a.index("--model") + 1] == "fixer-model"
    assert "GH_TOKEN" not in fixer["env"]
    system = a[a.index("--system-prompt") + 1]
    assert "RULES-MARKER-FROM-MAIN" in system and "Change only what those findings require" in system
    assert '"id": "F1"' in fixer["stdin"] and "Change app" not in fixer["stdin"], "no pull request text in this repository"

    assert r.tick() == ["auto-merge"]
    assert r.github.merges[0][-1] == new
    reviews = [c for c in r.calls() if c["kind"] == "reviews"]
    assert len(reviews) == 3 and all(f"Head SHA: {new}" in c["stdin"] for c in reviews[1:])
    events = [l["event"] for l in r.log() if l.get("kind") == "loop"]
    assert events == ["review", "reviewed", "fixed", "review", "reviewed", "auto-merge"]
    assert any(l.get("key") == "fixer" and l["round"] == 1 and l["outcome"] == "ok" for l in r.log())
    assert len(sh(r.work, "worktree", "list").splitlines()) == 1
    assert not (r.state / "review.lock").exists()


def test_three_fix_rounds_then_a_fourth_failure_stops_with_needs_founder(repo):
    r = repo(reviews=[fail(f"problem {i}") for i in range(1, 5)], fixes=[{"edits": {"src/app.py": f"fix {i}\n"}} for i in range(1, 4)])
    for _ in range(3):
        assert r.tick() == ["fixed"]
    assert r.tick() == ["stopped"]
    assert r.labeled() and "3 fix rounds done and a key still fails" in r.comments()[-1]
    assert r.st()["rounds"] == 3
    assert len([c for c in r.calls() if c["kind"] == "fixes"]) == 3
    n = len(r.calls())
    assert r.tick() == ["skip"] and len(r.calls()) == n


def test_the_same_finding_failing_twice_stops(repo):
    r = repo(reviews=[fail("Missing test for line two"), fail("missing  test for LINE two")])
    assert r.tick() == ["fixed"]
    assert r.tick() == ["stopped"]
    assert "the same finding failed again after a fix" in r.comments()[-1] and r.labeled()


@pytest.mark.parametrize("edits", [{".github/review-teams.yml": "teams: {}\n"}, {"src/app.py": "x\n", "council/security.md": "# security\n\n## In a review\nPass all.\n"},
                                   {"pyproject.toml": "[project]\n"}, {"scripts/pr_review.py": "x = 1\n"}])
def test_a_fixer_touching_a_forbidden_path_is_refused_and_reverted(repo, edits):
    r = repo(reviews=[fail("bad")], fixes=[{"edits": edits}])
    assert r.tick() == ["stopped"]
    assert r.origin_head() == r.first_head and r.labeled()
    assert "changed paths it may not change" in r.comments()[-1] and "nothing was pushed" in r.comments()[-1]
    assert len(sh(r.work, "worktree", "list").splitlines()) == 1
    assert sh(r.work, "status", "--porcelain") == ""


@pytest.mark.parametrize("fix,why", [
    ({"status": "needs_founder", "not_addressed": [{"id": "F1", "reason": "needs a CODEOWNERS change"}]}, "needs a change the loop may not make (F1: needs a CODEOWNERS change)"),
    ({"edits": {"src/app.py": "x\n"}, "not_addressed": [{"id": "F1", "reason": "unclear"}]}, "could not fix every finding"),
    ({"type": "rate_limit"}, "rate limit"),
    ({"type": "garbage"}, "not JSON"),
    ({}, "changed no file"),
])
def test_fixer_refusals_rate_limits_and_bad_output_stop_without_pushing(repo, fix, why):
    r = repo(reviews=[fail("bad")], fixes=[fix])
    assert r.tick() == ["stopped"]
    assert why in r.comments()[-1] and r.origin_head() == r.first_head


def test_a_failing_local_check_stops_without_pushing(repo):
    r = repo(reviews=[fail("bad")], fixes=[{"edits": {"src/app.py": "x\n", "FAIL_CHECK": "yes\n"}}])
    assert r.tick() == ["stopped"]
    assert "the local check dashes failed on the fix" in r.comments()[-1] and r.origin_head() == r.first_head


def test_a_person_pushing_mid_round_stops_the_round_without_overwriting_or_labelling(repo):
    r = repo(reviews=[fail("bad")])
    sh(r.work, "checkout", "-q", "feature")
    write(r.work, "src/human.py", "by hand\n")
    sh(r.work, "add", "-A")
    sh(r.work, "commit", "-qm", "human")
    human = sh(r.work, "rev-parse", "HEAD")
    sh(r.work, "push", "-q", "origin", "HEAD:refs/heads/human")
    sh(r.work, "checkout", "-q", "main")
    r.scenario([fail("bad")], [{"edits": {"src/app.py": "x\n"}, "human_move": {"git_dir": str(r.origin), "ref": "refs/heads/feature", "sha": human}}])
    assert r.tick() == ["head-moved"]
    assert r.origin_head() == human and not r.labeled()
    assert "fix round 1 not pushed" in r.comments()[-1] and r.st()["rounds"] == 0


def test_ci_failing_after_a_fix_stops_but_on_an_author_head_only_waits(repo, tmp_path):
    r = repo(reviews=[fail("bad")])
    r.github.ci = lambda sha: "success" if sha == r.first_head else "failure"
    assert r.tick() == ["fixed"]
    assert r.tick() == ["stopped"]
    assert "CI failed after fix round 1 (test failure" in r.comments()[-1] and r.labeled()


def test_ci_failing_on_the_author_head_waits_without_a_call(repo):
    r = repo(gh={"ci": lambda sha: "failure"})
    assert r.tick() == ["skip"]
    assert r.calls() == [] and r.github.posts == []


# --- Founder, hold and skips -----------------------------------------------------


def _change_github(w):
    write(w, ".github/workflows/x.yml", "name: x\n")


def _sys(call):
    return call["argv"][call["argv"].index("--system-prompt") + 1]


NEEDS = {"verdict": "needs-founder", "extra": {"founder_reasons": ["adds a paid runner"]}}


def test_founder_class_both_keys_and_the_proxy_pass_and_the_loop_takes_the_merge_path(repo):
    r = repo(change=_change_github)
    assert r.tick() == ["auto-merge"]
    assert r.github.merges and r.github.merges[0][-1] == r.first_head
    assert r.github.body == ("<!-- review:founder-class -->Founder class: control-plane (Control plane); the Founder Proxy (agent) "
                             "reviews it after key 2.<!-- /review:founder-class -->\n\nChanges line two."), "the driver declared the class in the body"
    reviews = [c for c in r.calls() if c["kind"] == "reviews"]
    assert len(reviews) == 3, "key 1, key 2, then the Founder Proxy"
    assert "SEAT-MARKER-founder-proxy" in _sys(reviews[2])
    assert reviews[2]["argv"][reviews[2]["argv"].index("--model") + 1] == "proxy-model"
    assert [p for p in r.github.posts if p["type"] == "check" and p["name"] == "review/executive"][-1]["state"] == "success"
    assert "both keys and the Founder Proxy (agent) passed" in r.comments()[-1]
    assert not any("waits for the founder's GitHub approval" in c for c in r.comments())
    assert next(l for l in r.log() if l.get("event") == "reviewed")["proxy"] == "pass"
    assert r.tick() == ["skip"]


def test_a_pull_request_in_no_founder_class_never_calls_the_proxy(repo):
    r = repo()
    assert r.tick() == ["auto-merge"]
    assert len(r.calls()) == 2
    assert not any("SEAT-MARKER-founder-proxy" in _sys(c) for c in r.calls())
    assert next(l for l in r.log() if l.get("event") == "reviewed")["proxy"] == "not run"


def test_proxy_fail_sends_its_findings_to_the_fixer_and_the_new_head_is_reviewed_again(repo):
    r = repo(change=_change_github, reviews=[{"verdict": "pass"}, {"verdict": "pass"}, fail("Attribution names a person, not Nirmaan"), {"verdict": "pass"}],
             fixes=[{"edits": {"src/app.py": "one by Nirmaan\n"}}])
    assert r.tick() == ["fixed"]
    fixer = next(c for c in r.calls() if c["kind"] == "fixes")
    assert '"key": "proxy"' in fixer["stdin"] and '"team": "founder-proxy"' in fixer["stdin"]
    assert "Attribution names a person" in fixer["stdin"]
    assert not r.labeled()
    assert r.tick() == ["auto-merge"]
    reviews = [c for c in r.calls() if c["kind"] == "reviews"]
    assert "SEAT-MARKER-founder-proxy" in _sys(reviews[-1]), "the proxy reviews the new head too"


def test_proxy_needs_founder_labels_and_stops_then_the_founders_approval_and_label_removal_merge_without_new_calls(repo):
    r = repo(change=_change_github, reviews=[{"verdict": "pass"}, {"verdict": "pass"}, NEEDS])
    assert r.tick() == ["stopped"]
    assert r.labeled() and r.github.merges == []
    assert not [c for c in r.calls() if c["kind"] == "fixes"], "what the founder keeps never goes to the fixer"
    assert "the Founder Proxy (agent) returned needs-founder: adds a paid runner" in r.comments()[-1]
    assert [p for p in r.github.posts if p["type"] == "check" and p["name"] == "review/executive"][-1]["state"] == "pending"
    n = len(r.calls())
    assert r.tick() == ["skip"]
    r.github.labels = []
    assert r.tick() == ["stopped"], "label removed without the founder's approval: stops again"
    r.github.labels = []
    r.github.reviews.append({"login": "nirmaansoftware", "state": "APPROVED", "commit_id": r.first_head})
    assert r.tick() == ["auto-merge"]
    assert len(r.calls()) == n, "cached verdicts: no new model call"
    assert [p for p in r.github.posts if p["type"] == "check" and p["name"] == "review/executive"][-1]["state"] == "success"
    assert "the founder's own GitHub review approves the changes the Founder Proxy (agent) sent to the founder" in r.comments()[-1]


def test_proxy_deferred_without_its_seat_on_main_stops_and_never_merges(repo):
    r = repo(change=_change_github)
    sh(r.work, "rm", "-q", "council/founder-proxy.md")
    sh(r.work, "commit", "-qm", "drop proxy seat")
    sh(r.work, "push", "-q", "origin", "main")
    assert r.tick() == ["stopped"]
    assert r.labeled() and r.github.merges == []
    assert "review deferred (Founder Proxy: seat file missing on main" in r.comments()[-1]


@pytest.mark.parametrize("gh", [{"labels": ["hold"]}, {"labels": ["needs-founder"]}, {"draft": True}, {"author": "nirmaansoftware"},
                                {"ci": lambda sha: "pending"}])
def test_hold_needs_founder_drafts_other_authors_and_pending_ci_call_nothing_and_post_nothing(repo, gh):
    r = repo(gh=gh)
    assert r.tick()[0] in ("skip", "wait")
    assert r.calls() == [] and r.github.posts == []


def test_a_merge_conflict_stops_and_removing_the_label_resumes(repo):
    r = repo(gh={"mergeable": False})
    assert r.tick() == ["stopped"]
    assert "merge conflict" in r.comments()[-1]
    r.github.mergeable, r.github.labels = True, []
    assert r.tick() == ["auto-merge"]


def test_one_pull_request_at_a_time_under_the_shared_lock(repo):
    r = repo()
    release, _ = pr_review.acquire_lock(r.state, {"repo": "nirmaansoftware/Nirmaan", "pr": 9})
    assert r.tick() == ["busy"] and r.calls() == []
    release()
    assert r.tick() == ["auto-merge"]


def test_the_shared_lock_is_held_for_each_review_call_and_free_during_the_fixer_and_local_checks(repo, monkeypatch):
    r = repo(reviews=[fail("bad"), {"verdict": "pass"}], fixes=[{"edits": {"src/app.py": "fixed\n"}}])
    lock = r.state / "review.lock"
    seen, original = [], pr_review.run_once

    def watched(binary, args, stdin, cwd, timeout_s):
        seen.append(("fixer" if "Edit(./**)" in " ".join(args) else "review", lock.exists()))
        return original(binary, args, stdin, cwd, timeout_s)
    monkeypatch.setattr(pr_review, "run_once", watched)
    check = {"name": "lock", "when": ["**"], "run": [["{python}", "-c", f"import os, sys; sys.exit(1 if os.path.exists({str(lock)!r}) else 0)"]]}
    assert r.tick(loop={**LOOP, "checks": [check]}) == ["fixed"], "the local check ran with the lock free"
    assert r.tick() == ["auto-merge"]
    assert seen == [("review", True), ("fixer", False), ("review", True), ("review", True)]
    assert not lock.exists()


def test_a_lock_held_elsewhere_between_key1_and_key2_ends_the_step_and_the_next_pass_reuses_key1(repo, monkeypatch):
    r = repo()
    original, other = pr_review.run_once, {}

    def then_taken(binary, args, stdin, cwd, timeout_s):
        out = original(binary, args, stdin, cwd, timeout_s)
        if not other:
            other["release"] = None  # taken once the call has released it
        return out
    monkeypatch.setattr(pr_review, "run_once", then_taken)
    real_acquire = pr_review.acquire_lock

    def acquire(state_dir, owner, *a, **kw):
        if other.get("release") is None and "release" in other and kw.get("name", "review.lock") == "review.lock":
            other["release"], _ = real_acquire(state_dir, {"repo": "nirmaansoftware/Nirmaan", "pr": 9})
        return real_acquire(state_dir, owner, *a, **kw)
    monkeypatch.setattr(pr_review, "acquire_lock", acquire)
    assert r.tick() == ["busy"] and len(r.calls()) == 1, "key 1 ran; key 2 met the lock held elsewhere"
    other["release"]()
    monkeypatch.setattr(pr_review, "acquire_lock", real_acquire)
    assert r.tick() == ["auto-merge"]
    assert len(r.calls()) == 2, "key 1 reused from the cache, key 2 called once"
    assert any(l.get("key") == 1 and l["outcome"] == "reused" for l in r.log())


def test_one_pass_at_a_time_per_repository(repo):
    r = repo()
    release, _ = pr_review.acquire_lock(r.state, {"repo": CONFIG["repo"], "by": "another pass"},
                                        name=f"loop-{CONFIG['repo'].replace('/', '_')}.lock")
    assert r.tick() == [] and r.calls() == []
    release()
    assert r.tick() == ["auto-merge"]


def test_no_post_commits_the_fix_locally_and_never_pushes(repo):
    r = repo(reviews=[fail("bad")])
    assert r.tick(post="none") == ["fixed-not-pushed"]
    assert r.origin_head() == r.first_head and r.github.posts == []


# --- Behind main -----------------------------------------------------------------


def update_args(head):
    return ["api", "-X", "PUT", f"repos/{CONFIG['repo']}/pulls/1/update-branch", "-f", f"expected_head_sha={head}"]


def is_merge_of(r, sha, head):
    parents = sh(r.origin, "rev-list", "--parents", "-n", "1", sha).split()[1:]
    return parents == [head, sh(r.origin, "rev-parse", "refs/heads/main")]


def test_a_branch_behind_main_is_updated_with_a_merge_commit_before_the_review_then_the_new_head_is_reviewed(repo):
    r = repo()
    r.advance_main()
    assert r.tick() == ["updated"]
    assert r.github.updates == [update_args(r.first_head)], "update-branch with the gh login, pinned to the head it saw"
    assert r.calls() == [], "no review of the stale head"
    new = r.origin_head()
    assert is_merge_of(r, new, r.first_head), "main merged into the branch"
    assert "Automated loop: branch updated" in r.comments()[-1] and "behind `main`" in r.comments()[-1]
    assert not r.labeled()
    assert r.tick() == ["auto-merge"]
    assert r.github.merges[0][-1] == new
    assert [l["event"] for l in r.log() if l.get("kind") == "loop"] == ["updated", "review", "reviewed", "auto-merge"]


def test_while_github_makes_the_merge_commit_the_next_pass_waits_and_does_not_ask_again(repo):
    r = repo()
    r.advance_main()
    r.github.update_async = True
    assert r.tick() == ["updated"]
    assert r.tick() == ["wait"]
    assert len(r.github.updates) == 1 and r.calls() == []


def test_founder_class_behind_main_is_updated_first_then_both_keys_and_the_proxy_review_the_new_head(repo):
    r = repo(change=_change_github)
    r.advance_main()
    assert r.tick() == ["updated"]
    assert r.calls() == [], "no review of the stale head"
    new = r.origin_head()
    assert r.tick() == ["auto-merge"]
    assert r.github.merges[0][-1] == new
    reviews = [c for c in r.calls() if c["kind"] == "reviews"]
    assert len(reviews) == 3 and all(f"Head SHA: {new}" in c["stdin"] for c in reviews)


def test_founder_class_main_moves_during_the_review_so_the_loop_updates_instead_of_merging(repo):
    r = repo(change=_change_github)
    moved = []

    def when():
        if not moved and len(r.calls()) >= 3:
            moved.append(1)
            r.advance_main()
        return False
    r.github.behind_when = when
    assert r.tick() == ["updated"]
    assert len(r.calls()) == 3, "both keys and the proxy ran on the old head"
    assert r.github.merges == []
    r.github.behind_when = None
    assert r.tick() == ["auto-merge"]
    assert r.github.merges[0][-1] == r.origin_head()


def test_a_failed_update_stops_with_needs_founder(repo):
    r = repo()
    r.advance_main()
    r.github.update_error = "gh: merge conflict between base and head (HTTP 422)"
    assert r.tick() == ["stopped"]
    assert r.labeled() and "could not update the branch with main" in r.comments()[-1]
    assert r.origin_head() == r.first_head and r.calls() == []


def test_a_push_just_before_the_update_drops_the_step_without_a_label(repo, tmp_path):
    r = repo()
    r.advance_main()

    def human():
        w = tmp_path / "human"
        sh(tmp_path, "clone", "-q", "-b", "feature", str(r.origin), str(w))
        sh(w, "config", "user.email", "h@example.com")
        sh(w, "config", "user.name", "Human")
        write(w, "src/human.py", "by hand\n")
        sh(w, "add", "-A")
        sh(w, "commit", "-qm", "human")
        sh(w, "push", "-q", "origin", "feature")
        r.github.before_update = None
    r.github.before_update = human
    assert r.tick() == ["head-moved"]
    assert r.origin_head() != r.first_head
    assert not r.labeled() and not any("stopped" in c for c in r.comments())


def test_no_post_never_updates_a_branch(repo):
    r = repo()
    r.advance_main()
    r.tick(post="none")
    assert r.github.updates == [] and r.origin_head() == r.first_head


# --- Every pull request each pass ---------------------------------------------------


def test_one_pass_steps_every_pull_request_and_a_review_fix_wait_or_busy_lock_never_ends_it(repo):
    r = repo()
    loop = r.loop()
    pulls = [{"number": n} for n in (6, 5, 4, 3, 2, 1)]
    loop.o["github"] = type("G", (), {"list_open_pulls": lambda self: pulls})()
    # Pull request 3 is in a fix round, so it goes first; the rest by number.
    pr_loop._save_state(r.state, CONFIG["repo"], {"pr": 3, "rounds": 1, "seen": {}, "last_fix_head": "abc", "done": None, "stopped": None})
    outcome = {1: "ready", 2: "wait", 3: "fixed", 4: "busy", 5: "updated", 6: "stopped"}
    seen = []

    def step(p):
        seen.append(p["number"])
        return {"outcome": outcome[p["number"]]}
    loop.step = step
    results = loop.tick()
    assert seen == [3, 1, 2, 4, 5, 6]
    assert [f"{x['pr']}:{x['outcome']}" for x in results] == ["3:fixed", "1:ready", "2:wait", "4:busy", "5:updated", "6:stopped"]


def test_an_auto_merge_ends_the_pass_so_the_rest_are_stepped_against_the_new_main_next_pass(repo):
    # Auto-merge can merge main while the pass goes on; the pull requests after
    # it wait for the next pass, which refetches main and checks this copy again.
    r = repo()
    loop = r.loop()
    pulls = [{"number": n} for n in (1, 2, 3)]
    loop.o["github"] = type("G", (), {"list_open_pulls": lambda self: pulls})()
    outcome = {1: "skip", 2: "auto-merge", 3: "wait"}
    seen = []

    def step(p):
        seen.append(p["number"])
        return {"outcome": outcome[p["number"]]}
    loop.step = step
    assert [f"{x['pr']}:{x['outcome']}" for x in loop.tick()] == ["1:skip", "2:auto-merge"]
    assert seen == [1, 2], "pull request 3 is not stepped against the main the pass started with"
    outcome[2] = "skip"
    assert [f"{x['pr']}:{x['outcome']}" for x in loop.tick()] == ["1:skip", "2:skip", "3:wait"]


def test_a_merge_from_outside_the_loop_mid_pass_ends_the_pass_before_the_next_step(repo):
    # Someone else merges into main while pull request 1 is stepped (not an
    # auto-merge of this pass): pull request 2 waits for the next pass.
    r = repo()
    loop = r.loop()
    pulls = [{"number": n} for n in (1, 2)]
    loop.o["github"] = type("G", (), {"list_open_pulls": lambda self: pulls})()
    seen = []

    def step(p):
        seen.append(p["number"])
        if p["number"] == 1 and len(seen) == 1:
            r.advance_main()
        return {"outcome": "wait"}
    loop.step = step
    assert [f"{x['pr']}:{x['outcome']}" for x in loop.tick()] == ["1:wait"]
    assert seen == [1], "pull request 2 is not stepped once main moved"
    assert [f"{x['pr']}:{x['outcome']}" for x in loop.tick()] == ["1:wait", "2:wait"], "the next pass starts from the new main"


def test_a_pass_whose_start_main_is_already_stale_steps_nothing(repo):
    # main moved between the fetch the copy was checked against and the pass.
    r = repo()
    loop = r.loop()
    loop.o["github"] = type("G", (), {"list_open_pulls": lambda self: [{"number": 1}]})()
    loop.step = lambda p: {"outcome": "wait"}
    stale = sh(r.work, "rev-parse", "main")
    r.advance_main()
    assert loop.tick(main_at_start=stale) == []


# --- Related tests for the fixer's local check --------------------------------------


def _tree(root: Path, files: dict[str, str]):
    for rel, text in files.items():
        write(root, rel, text)


def test_related_tests_map_changed_files_to_the_tests_that_use_them(tmp_path):
    _tree(tmp_path, {
        "src/nirmaan/alpha.py": "x = 1\n",
        "src/nirmaan/beta/core.py": "y = 2\n",
        "src/nirmaan/beta/__init__.py": "",
        "src/nirmaan/lonely.py": "z = 3\n",
        "src/nirmaan/gamma/inner.py": "w = 4\n",
        "tests/test_gamma_pkg.py": "from nirmaan.gamma import W\n",
        "scripts/check_union.py": "",
        "tests/conftest.py": "",
        "tests/laws.py": "",
        "tests/test_laws.py": "import laws\n",
        "tests/test_alpha_use.py": "from nirmaan.alpha import x\n",
        "tests/test_multi.py": "from nirmaan import (\n    other,\n    alpha,\n)\n",
        "tests/test_beta.py": "import nirmaan.beta.core\n",
        "tests/test_nirmaan_core.py": "pass\n",
        "tests/test_union.py": 'SCRIPT = ROOT / "scripts" / "check_union.py"\n',
        "tests/test_fixture_user.py": 'fixture_log("sample.log")\n',
        "tests/fixtures/eda/sample.log": "log\n",
        "tests/test_other.py": "pass\n",
    })
    rel = pr_loop.related_tests
    assert rel(tmp_path, ["src/nirmaan/alpha.py"]) == ["tests/test_alpha_use.py", "tests/test_laws.py", "tests/test_multi.py"]
    assert rel(tmp_path, ["src/nirmaan/beta/core.py"]) == ["tests/test_beta.py", "tests/test_laws.py", "tests/test_nirmaan_core.py"]
    assert rel(tmp_path, ["src/nirmaan/gamma/inner.py"]) == ["tests/test_gamma_pkg.py", "tests/test_laws.py"], "re-exported by its package"
    assert rel(tmp_path, ["tests/test_other.py"]) == ["tests/test_other.py"]
    assert rel(tmp_path, ["scripts/check_union.py"]) == ["tests/test_union.py"]
    assert rel(tmp_path, ["tests/fixtures/eda/sample.log"]) == ["tests/test_fixture_user.py"]
    assert rel(tmp_path, ["tests/laws.py"]) == ["tests/test_laws.py"]
    assert rel(tmp_path, ["tests/test_other.py", "tests/test_gone.py"]) == ["tests/test_other.py"], "a deleted test file is not run"
    # No test is known to cover it, or it reaches every test: the whole suite.
    assert rel(tmp_path, ["tests/conftest.py"]) is None
    assert rel(tmp_path, ["src/nirmaan/lonely.py"]) is None
    assert rel(tmp_path, ["tests/test_other.py", "src/nirmaan/lonely.py"]) is None
    assert rel(tmp_path, ["tests/test_gone.py"]) is None


def test_the_fixers_test_check_runs_only_the_related_tests(repo, tmp_path):
    record = tmp_path / "pytest-args.json"
    loop = {**LOOP, "checks": [{"name": "test", "when": ["src/**", "tests/**"], "select": "related_tests", "env": {"RECORD": str(record)},
                                "run": [["{python}", "-c", "import json, os, sys; json.dump(sys.argv[1:], open(os.environ['RECORD'], 'w'))"]]}]}

    def change(w):
        write(w, "src/app.py", "one\ntwo changed\nthree\n")
        write(w, "tests/test_app.py", "from app import one\n")
        write(w, "tests/test_unrelated.py", "pass\n")
    r = repo(reviews=[fail("Line two lost its test"), {"verdict": "pass"}], fixes=[{"edits": {"src/app.py": "one\ntwo fixed\nthree\n"}}], change=change)
    assert r.tick(loop=loop) == ["fixed"]
    assert json.loads(record.read_text()) == ["tests/test_app.py"]
    assert "test (1 related file): pass" in r.comments()[-1]


# --- The plist -------------------------------------------------------------------


def test_the_plist_reads_its_settings_from_the_sourced_env_file_and_holds_none_itself():
    plist = (ROOT / "docs" / "pr-loop.plist").read_text(encoding="utf-8")
    assert '. "$HOME/.nirmaan/pr-loop/env"' in plist, "the command sources the env file"
    assert "<key>EnvironmentVariables</key>" not in plist, "no EnvironmentVariables block to lose or to hold a value"
    assert "NIRMAAN_REVIEW_APP_ID=" not in plist and "PRIVATE_KEY_FILE=" not in plist
    import re as _re
    cmd = _re.search(r"<string>(mkdir[^<]*)</string>", plist).group(1)
    assert cmd.index("pr-loop/env") < cmd.index("pr_loop.py"), "sourced before the loop starts"
    assert "ip-loop.log" in cmd
    assert _re.search(r"<key>StartInterval</key>\s*<integer>60</integer>", plist), "a pass every minute"


# --- Units -----------------------------------------------------------------------


def test_fingerprint_findings_output_and_forbidden_paths():
    fp = pr_loop.fingerprint
    assert fp({"key": 1, "team": "x", "file": "a", "text": "Foo  bar"}) == fp({"key": 1, "team": "x", "file": "a", "text": "foo bar", "line": 9})
    assert fp({"key": 1, "team": "x", "file": "a", "text": "foo"}) != fp({"key": 1, "team": "x", "file": "b", "text": "foo"})
    found = pr_loop.findings_to_fix({"key1": [
        {"key": 1, "team": "eda", "role": "eda-tooling", "status": "fail", "verdict": {"findings": [
            {"file": "a", "line": 1, "severity": "minor", "text": "m"}, {"file": "a", "line": 2, "severity": "critical", "text": "c"}]}},
        {"key": 1, "team": "v", "status": "pass", "verdict": {"findings": [{"file": "b", "line": 1, "severity": "critical", "text": "x"}]}}], "key2": None})
    assert [(f["id"], f["text"]) for f in found] == [("F1", "c")]
    fs = [{"id": "F1"}, {"id": "F2"}]
    assert pr_loop.validate_fixer_output({"status": "fixed", "addressed": ["F1", "F2"], "not_addressed": [], "summary": "s"}, fs)[1] is None
    assert "F2 not accounted for" in pr_loop.validate_fixer_output({"status": "fixed", "addressed": ["F1"], "not_addressed": [], "summary": "s"}, fs)[1]
    assert "unknown finding id" in pr_loop.validate_fixer_output({"status": "fixed", "addressed": ["F9"], "not_addressed": [], "summary": "s"}, fs)[1]
    proxy = pr_loop.findings_to_fix({"key1": [], "key2": None, "proxy": {"key": "proxy", "team": None, "role": "founder-proxy", "status": "fail",
                                     "verdict": {"findings": [{"file": "a", "line": 3, "severity": "blocker", "text": "p"}]}}})
    assert [(f["id"], f["key"], f["team"]) for f in proxy] == [("F1", "proxy", "founder-proxy")], "a failed proxy's findings go to the fixer"
    for path in (".github/workflows/ci.yml", ".claude/skills/pr-review/SKILL.md", "CLAUDE.md", "council/chair.md", "council/founder-proxy.md",
                 "council/records/x.md", "scripts/check_dashes.py", "scripts/pr_loop.py", "tests/test_pr_loop.py", "pyproject.toml",
                 "docs/REVIEW_MECHANISM.md", "docs/pr-loop.plist"):
        assert pr_loop.forbidden_changes([path], pr_loop.LOOP["fixer_forbidden"]), path
    assert pr_loop.forbidden_changes(["src/nirmaan/x.py", "docs/OTHER.md"], pr_loop.LOOP["fixer_forbidden"]) == []
    assert pr_loop.ci_state(["a", "b"], [{"name": "a", "status": "completed", "conclusion": "success"}])[0] == "pending"
    assert pr_loop.ci_state(["a"], [{"name": "a", "status": "completed", "conclusion": "cancelled"}])[0] == "failed"


def test_ci_state_takes_the_newest_run_and_a_rerun_in_progress_is_pending():
    def run(i, started, status, conclusion, completed):
        return {"id": i, "name": "a", "status": status, "conclusion": conclusion, "started_at": started, "completed_at": completed}
    req = ["a"]
    # A rerun has no completed_at while it runs; an older success must not win.
    assert pr_loop.ci_state(req, [run(1, "2026-10-17T00:00:00Z", "completed", "success", "2026-10-17T00:05:00Z"),
                                  run(2, "2026-10-17T01:00:00Z", "in_progress", None, None)])[0] == "pending"
    assert pr_loop.ci_state(req, [run(2, "2026-10-17T01:00:00Z", "queued", None, None),
                                  run(1, "2026-10-17T00:00:00Z", "completed", "failure", "2026-10-17T00:05:00Z")])[0] == "pending"
    # Newest by start time (then id), not by completion time.
    assert pr_loop.ci_state(req, [run(1, "2026-10-17T00:00:00Z", "completed", "success", "2026-10-17T02:00:00Z"),
                                  run(2, "2026-10-17T01:00:00Z", "completed", "failure", "2026-10-17T01:05:00Z")])[0] == "failed"
    assert pr_loop.ci_state(req, [run(1, "2026-10-17T00:00:00Z", "completed", "failure", "2026-10-17T02:00:00Z"),
                                  run(2, "2026-10-17T01:00:00Z", "completed", "success", "2026-10-17T01:05:00Z")])[0] == "green"
    assert pr_loop.ci_state(req, [run(5, "2026-10-17T00:00:00Z", "completed", "failure", None),
                                  run(6, "2026-10-17T00:00:00Z", "completed", "success", None)])[0] == "green", "same start: higher id"
