"""Milestone 19: cross-regression diffing.

"It worked yesterday, what landed since?" is the first question a
verification engineer asks and the one the platform could not answer. Both
halves existed and had never been introduced: the regression database has
recorded each run's commit since v0.4.0, and the M7 provider seam can list
commits. These tests cover the join, and the honesty rules that matter more
than the feature: an unanswerable question returns None, and "nothing
changed" is a real answer that must not look like a failure.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from veritriage.engineering import diff_against_last_green, last_green_before
from veritriage.engineering.model import ContextCapability, RegressionDiff
from veritriage.engineering.providers import ContextProvider, GitProvider
from veritriage.history import ExecutionMetadata, HistoryEngine
from veritriage.pipeline import analyze
from veritriage.storage import RegressionStore
from veritriage.workspace import WorkspaceServices


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    """A tiny repository with three commits, one touching an axi module."""
    root = tmp_path / "dut"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "dv@example.test")
    _git(root, "config", "user.name", "DV Engineer")
    shas = []
    for name, body in [
        ("rtl/unrelated_block.sv", "module unrelated_block; endmodule\n"),
        ("rtl/axi_scoreboard.sv", "module axi_scoreboard; endmodule\n"),
        ("docs/notes.md", "notes\n"),
    ]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", f"touch {name}")
        shas.append(_git(root, "rev-parse", "HEAD"))
    return root, shas


def _record(store, path, *, commit, when):
    """Record one analysis into the store at a chosen time and commit."""
    outcome = analyze(path)
    record, _ = HistoryEngine(store).record(
        outcome, execution=ExecutionMetadata(git_commit=commit), now=when
    )
    return record


# --- Picking the baseline ---------------------------------------------------


def test_last_green_is_the_newest_pass_before_the_failure(tmp_path, fixture_log):
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        old_pass = _record(store, fixture_log("uvm_pass.log"), commit="a" * 40, when=now - timedelta(hours=3))
        new_pass = _record(store, fixture_log("uvm_pass.log"), commit="b" * 40, when=now - timedelta(hours=2))
        fail = _record(store, fixture_log("axi_timeout.log"), commit="c" * 40, when=now - timedelta(hours=1))
        records = store.all_records()

    base = last_green_before(records, fail)
    assert base is not None
    assert base.regression_id == new_pass.regression_id
    assert base.regression_id != old_pass.regression_id


def test_a_pass_recorded_after_the_failure_is_not_a_baseline(tmp_path, fixture_log):
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        fail = _record(store, fixture_log("axi_timeout.log"), commit="c" * 40, when=now - timedelta(hours=2))
        _record(store, fixture_log("uvm_pass.log"), commit="d" * 40, when=now)
        records = store.all_records()
    assert last_green_before(records, fail) is None


def test_no_green_run_means_no_baseline(tmp_path, fixture_log):
    db = tmp_path / "r.db"
    with RegressionStore(db) as store:
        fail = _record(store, fixture_log("axi_timeout.log"), commit="c" * 40, when=datetime.now(timezone.utc))
        records = store.all_records()
    assert last_green_before(records, fail) is None


# --- The join ---------------------------------------------------------------


def test_diff_lists_what_landed_between_the_two_runs(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)
        records = store.all_records()

    diff = diff_against_last_green(records, fail, GitProvider(), root)
    assert diff is not None
    assert diff.base_commit == shas[0]
    assert diff.head_commit == shas[2]
    assert len(diff.commits) == 2, "the two commits after the green one"
    assert diff.provider == "git"
    assert "axi_scoreboard" in diff.changed_modules


def test_commits_touching_the_failing_module_are_flagged_suspect(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("uvm_scoreboard.log"), commit=shas[2], when=now)
        records = store.all_records()

    diff = diff_against_last_green(records, fail, GitProvider(), root)
    assert diff is not None
    # Suspects are always a subset of the range, never invented, and every one
    # of them touched a module the failure signature implicates.
    revisions = {c.revision for c in diff.commits}
    assert set(diff.suspect_commits) <= revisions
    implicated = {m.lower() for m in fail.signature.modules}
    for sha in diff.suspect_commits:
        commit = next(c for c in diff.commits if c.revision == sha)
        touched = {m.lower() for f in commit.files for m in f.modules}
        assert implicated & touched


def test_same_commit_is_an_empty_diff_not_a_failure(repo, tmp_path, fixture_log):
    """'Nothing changed' points at the environment. It must be sayable."""
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[2], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)
        records = store.all_records()

    diff = diff_against_last_green(records, fail, GitProvider(), root)
    assert diff is not None, "an answerable question must not return None"
    assert diff.commits == []
    assert diff.is_empty
    assert diff.base_commit == diff.head_commit


def test_commits_unknown_to_this_checkout_return_none(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit="0" * 40, when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)
        records = store.all_records()

    assert diff_against_last_green(records, fail, GitProvider(), root) is None


def test_a_run_without_a_commit_cannot_be_diffed(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=None, when=now)
        records = store.all_records()

    assert diff_against_last_green(records, fail, GitProvider(), root) is None


# --- The seam ---------------------------------------------------------------


def test_a_provider_without_the_capability_is_never_asked(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)
        records = store.all_records()

    class _NoRange(ContextProvider):
        name = "no-range"
        source = "no-range"
        capabilities = frozenset({ContextCapability.COMMITS})

        @classmethod
        def available(cls, root: Path) -> bool:
            return True

        def collect(self, root: Path, max_commits: int = 10):
            raise AssertionError("collect must not be called")

        def changes_between(self, root, base_commit, head_commit, max_commits=50):
            raise AssertionError("a provider without CHANGE_RANGE must not be asked")

    assert diff_against_last_green(records, fail, _NoRange(), root) is None


def test_the_default_provider_cannot_answer_a_range():
    """Every pre-existing provider keeps working, answering 'I cannot tell'."""

    class _Old(ContextProvider):
        name = "old-style"
        source = "old-style"
        capabilities = frozenset({ContextCapability.COMMITS})

        @classmethod
        def available(cls, root: Path) -> bool:
            return True

        def collect(self, root: Path, max_commits: int = 10):
            raise NotImplementedError

    assert _Old().changes_between(Path("."), "a", "b") is None


def test_git_provider_declares_the_capability():
    assert ContextCapability.CHANGE_RANGE in GitProvider.capabilities


def test_diffing_emits_no_patch_text(repo, tmp_path, fixture_log):
    """Lossy by design: summaries cross the provider boundary, diffs do not."""
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)
        records = store.all_records()

    diff = diff_against_last_green(records, fail, GitProvider(), root)
    blob = diff.model_dump_json()
    for leak in ("+++", "---", "@@", "diff --git", "endmodule"):
        assert leak not in blob, f"patch content leaked: {leak}"


# --- Through the workspace --------------------------------------------------


def test_workspace_answers_the_question_end_to_end(repo, tmp_path, fixture_log):
    root, shas = repo
    db = tmp_path / "r.db"
    now = datetime.now(timezone.utc)
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit=shas[0], when=now - timedelta(hours=1))
        fail = _record(store, fixture_log("axi_timeout.log"), commit=shas[2], when=now)

    diff = services.changes_since_last_green(fail.regression_id, root=root)
    assert isinstance(diff, RegressionDiff)
    assert len(diff.commits) == 2


def test_workspace_returns_none_for_an_unknown_regression(repo, tmp_path, fixture_log):
    root, _ = repo
    db = tmp_path / "r.db"
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    with RegressionStore(db) as store:
        _record(store, fixture_log("uvm_pass.log"), commit="a" * 40, when=datetime.now(timezone.utc))
    assert services.changes_since_last_green("nope", root=root) is None


def test_workspace_without_a_database_returns_none(tmp_path, repo):
    root, _ = repo
    services = WorkspaceServices(session_root=tmp_path / "s")
    assert services.changes_since_last_green("anything", root=root) is None
