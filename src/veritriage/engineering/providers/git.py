"""Local git provider: the only module in the platform allowed to run git.

Reads the repository's recent history (no network, no remotes) and normalizes
it into :class:`EngineeringContext`: bounded recent commits with per-file
change summaries, categorized by deterministic path heuristics. Raw diffs are
read by git, summarized by ``--numstat``, and discarded; no patch text ever
leaves this module (lossy-by-design law).

This module also hosts :func:`execution_snapshot`, the single git call site
the history layer (M4's ``capture_execution_metadata``) delegates to, so the
"no git outside providers" architecture law holds repo-wide.

Capabilities: COMMITS and CHANGED_FILES only. Raw git has no CI runs, no
ownership, no issues; declaring less keeps degradation honest.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from veritriage.engineering.model import (
    ChangeCategory,
    ChangedFile,
    Commit,
    ContextCapability,
    EngineeringContext,
    make_context_id,
)
from veritriage.engineering.providers.base import ContextProvider
from veritriage.engineering.providers.registry import register_provider

#: Record and field separators for one-pass `git log` parsing.
_REC = "\x1e"
_FIELD = "\x1f"

#: Path fragments marking verification code, checked before RTL extensions.
_TB_MARKERS = ("/tb/", "/tb_", "/testbench", "/verif", "/tests/", "/test/", "/env/", "/seq")
_TB_SUFFIXES = ("_test", "_tb", "_seq", "_env", "_agent", "_driver", "_monitor_tb", "_scoreboard")


def _run_git_raw(root: Path | None, *args: str) -> tuple[bool, str]:
    """Run one git command, returning (succeeded, stdout).

    :func:`_run_git` collapses "succeeded with no output" into None, which is
    the right default for context collection but wrong for a range query:
    "no commits between these two" and "I cannot resolve these two" must not
    look alike.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return True, out
    except (OSError, subprocess.SubprocessError):
        return False, ""


def _run_git(root: Path | None, *args: str) -> str | None:
    """Run one git command, returning stdout or None on any failure.

    Every failure mode (git missing, not a repo, timeout) degrades to None:
    engineering context is auxiliary and must never break an analysis.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return out if out.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def execution_snapshot(cwd: Path | None = None) -> tuple[str | None, str | None, str | None]:
    """(commit, branch, author) of HEAD, best-effort.

    The history layer's ``capture_execution_metadata`` delegates here so this
    module remains the platform's only git call site.
    """
    return (
        (_run_git(cwd, "rev-parse", "HEAD") or "").strip() or None,
        (_run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "").strip() or None,
        (_run_git(cwd, "log", "-1", "--format=%an") or "").strip() or None,
    )


def categorize_path(path: str) -> ChangeCategory:
    """Deterministic path-to-category heuristic shared by providers.

    Order matters: verification markers beat RTL extensions (a ``.sv`` file
    under ``/tb/`` is testbench, not RTL), and assertion/constraint markers
    beat both.
    """
    lowered = "/" + path.lower().lstrip("/")
    name = lowered.rsplit("/", maxsplit=1)[-1]
    stem, _, ext = name.rpartition(".")

    if ext in ("sdc", "xdc"):
        return ChangeCategory.CONSTRAINT
    if ext == "sva" or "_sva" in stem or "/sva/" in lowered or "assert" in stem:
        return ChangeCategory.ASSERTION
    if ext in ("md", "rst", "txt") or "/docs/" in lowered or "/doc/" in lowered:
        return ChangeCategory.DOCS
    if (
        name in ("makefile", "cmakelists.txt")
        or ext in ("mk", "f", "yml", "yaml", "toml", "cfg", "ini")
    ):
        return ChangeCategory.BUILD
    is_hdl = ext in ("sv", "svh", "v", "vh", "vhd", "vhdl")
    is_tb = any(m in lowered for m in _TB_MARKERS) or any(stem.endswith(s) for s in _TB_SUFFIXES)
    if is_tb:
        return ChangeCategory.TESTBENCH
    if is_hdl:
        return ChangeCategory.RTL
    return ChangeCategory.OTHER


def modules_for_path(path: str) -> tuple[str, ...]:
    """Map a file path to candidate module names (the stem, conservatively)."""
    name = path.rsplit("/", maxsplit=1)[-1]
    stem = name.rsplit(".", maxsplit=1)[0].lower()
    return (stem,) if len(stem) >= 3 else ()


@register_provider
class GitProvider(ContextProvider):
    """Collects recent-commit context from a local git repository."""

    name = "git"
    source = "git"
    capabilities = frozenset(
        {
            ContextCapability.COMMITS,
            ContextCapability.CHANGED_FILES,
            ContextCapability.CHANGE_RANGE,
        }
    )

    @classmethod
    def available(cls, root: Path) -> bool:
        return _run_git(root, "rev-parse", "--is-inside-work-tree") is not None

    def collect(self, root: Path, max_commits: int = 10) -> EngineeringContext:
        log = _run_git(
            root,
            "log",
            f"-n{max_commits}",
            "--numstat",
            "--no-merges",
            f"--format={_REC}%H{_FIELD}%an{_FIELD}%aI{_FIELD}%s",
        )
        commits = tuple(self._parse_log(log)) if log else ()
        return EngineeringContext(
            sources=(self.name,),
            capabilities=self.capabilities,
            commits=commits,
        )

    def changes_between(
        self, root: Path, base_commit: str, head_commit: str, max_commits: int = 50
    ) -> list[Commit] | None:
        """Commits in ``(base_commit, head_commit]``, newest first.

        Returns None when either commit is unknown to this clone, which is a
        real and common case: the regression database may hold a commit from
        a shallow CI checkout, or from a branch that has since been pruned.
        An empty list means the two runs were built from the same code, which
        is a genuine and useful answer, so it must not look like a failure.
        """
        for commit in (base_commit, head_commit):
            ok, _ = _run_git_raw(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
            if not ok:
                return None
        ok, log = _run_git_raw(
            root,
            "log",
            f"-n{max_commits}",
            "--numstat",
            "--no-merges",
            f"--format={_REC}%H{_FIELD}%an{_FIELD}%aI{_FIELD}%s",
            f"{base_commit}..{head_commit}",
        )
        if not ok:
            return None
        return self._parse_log(log) if log.strip() else []

    def _parse_log(self, log: str) -> list[Commit]:
        commits: list[Commit] = []
        for record in log.split(_REC):
            record = record.strip("\n")
            if not record:
                continue
            header, _, body = record.partition("\n")
            parts = header.split(_FIELD)
            if len(parts) != 4:
                continue
            sha, author, date_iso, title = parts
            files: list[ChangedFile] = []
            for line in body.splitlines():
                cols = line.split("\t")
                if len(cols) != 3:
                    continue
                added, deleted, path = cols
                files.append(
                    ChangedFile(
                        path=path,
                        category=categorize_path(path),
                        lines_added=int(added) if added.isdigit() else 0,
                        lines_deleted=int(deleted) if deleted.isdigit() else 0,
                        modules=modules_for_path(path),
                    )
                )
            timestamp: datetime | None
            try:
                timestamp = datetime.fromisoformat(date_iso)
            except ValueError:
                timestamp = None
            commits.append(
                Commit(
                    id=make_context_id(self.source, sha),
                    revision=sha,
                    timestamp=timestamp,
                    author=author or None,
                    title=title,
                    files=tuple(files),
                    source=self.source,
                )
            )
        return commits
