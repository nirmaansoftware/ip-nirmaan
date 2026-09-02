"""Cross-regression diffing: what changed since the last run that passed.

Section 5.6 of the project context, and the question a verification engineer
asks before any other one: it worked yesterday, what landed since?

Both halves of the answer already existed and had never been introduced. The
regression database has recorded ``execution.git_commit`` for every run since
v0.4.0, so it knows which commit each result was built from. The M7 provider
seam can list normalized commits from whatever version-control system a site
uses. This module is the join, and it stays behind the seam: it asks a
provider for a range and never runs a tool itself, so a Perforce or Gerrit
shop gets the same analysis by registering a provider.

Lossy by design, like everything a provider emits. Commit summaries and
module names cross the boundary; diff text never does.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from veritriage.engineering.model import (
    ContextCapability,
    RegressionDiff,
)
from veritriage.engineering.providers import ContextProvider

if TYPE_CHECKING:  # pragma: no cover - typing only
    from veritriage.history.record import RegressionRecord


def last_green_before(
    records: Sequence["RegressionRecord"], target: "RegressionRecord"
) -> "RegressionRecord | None":
    """The newest passing run recorded before ``target``, if any.

    Ordered by recorded time and tie-broken by regression ID so the answer is
    the same however the rows came back from the database.
    """
    candidates = [
        r
        for r in records
        if not r.is_failure
        and r.execution.git_commit
        and (r.created_at, r.regression_id) < (target.created_at, target.regression_id)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.created_at, r.regression_id))


def diff_against_last_green(
    records: Sequence["RegressionRecord"],
    target: "RegressionRecord",
    provider: ContextProvider,
    root: Path,
    max_commits: int = 50,
) -> RegressionDiff | None:
    """What landed between the last green run and ``target``.

    Returns None, rather than an empty diff, whenever the question cannot be
    answered: no green run recorded, either run missing a commit, the
    provider unable to resolve a range, or the commits unknown to this
    checkout. An empty ``commits`` list is a real answer and means the two
    runs were built from the same code, which points the investigation at the
    environment rather than the RTL.
    """
    if ContextCapability.CHANGE_RANGE not in provider.capabilities:
        return None
    head_commit = target.execution.git_commit
    if not head_commit:
        return None
    base = last_green_before(records, target)
    if base is None or not base.execution.git_commit:
        return None

    commits = provider.changes_between(
        root, base.execution.git_commit, head_commit, max_commits=max_commits
    )
    if commits is None:
        return None

    changed_modules = sorted({m for c in commits for f in c.files for m in f.modules})
    # A commit is suspect when it touched a module this failure implicates.
    # Deliberately a name overlap and nothing cleverer: it narrows where to
    # look, it does not claim to have found the bug.
    implicated = {m.lower() for m in target.signature.modules}
    suspects = sorted(
        {
            c.revision
            for c in commits
            if implicated & {m.lower() for f in c.files for m in f.modules}
        }
    )
    return RegressionDiff(
        base_regression_id=base.regression_id,
        base_commit=base.execution.git_commit,
        head_regression_id=target.regression_id,
        head_commit=head_commit,
        commits=commits,
        changed_modules=changed_modules,
        suspect_commits=suspects,
        provider=provider.name,
    )
