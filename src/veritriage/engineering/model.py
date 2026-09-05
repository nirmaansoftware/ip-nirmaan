"""Normalized, tool-independent engineering context models (Milestone 7).

This module is the boundary between "tool-aware" and "tool-agnostic" code.
Providers (which know git, CI exports, trackers) fill in
:class:`EngineeringContext`; everything downstream reads only these models and
never learns which tool produced them.

All models are immutable (frozen) and carry the milestone's provenance spine:
a deterministic ``id``, a ``timestamp`` where the source has one, a ``source``
(provider name), a ``confidence``, and open ``metadata``. Relationships are
expressed later as Evidence Graph edges, not object references, so the models
stay flat and serializable.

Deliberately absent: diffs, patch text, file contents. Providers may read them
to compute categories and module mappings, but only summaries survive
normalization (the same lossy-by-design rule as waveform adapters): VeriTriage
must not drift into being a code browser, and the graph must stay small.

This module imports nothing from :mod:`veritriage.graph` or the providers.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextCapability(str, Enum):
    """What a provider is able to resolve from its engineering system.

    Declared per provider and carried on each :class:`EngineeringContext`. An
    analysis that needs a capability no contributing provider declared is
    reported as unavailable, never silently skipped.
    """

    COMMITS = "commits"
    CHANGED_FILES = "changed_files"
    CHANGE_RANGE = "change_range"
    CI_RUNS = "ci_runs"
    OWNERSHIP = "ownership"
    ISSUES = "issues"
    REVIEWS = "reviews"


class ChangeCategory(str, Enum):
    """Where a changed file lives in the engineering world.

    Categories drive the reasoning bridge (an RTL change near a failure weighs
    differently than a testbench change) and are computed deterministically
    from paths by providers, or declared explicitly by a manifest.
    """

    RTL = "rtl"
    TESTBENCH = "testbench"
    CONSTRAINT = "constraint"
    ASSERTION = "assertion"
    BUILD = "build"
    DOCS = "docs"
    OTHER = "other"


def make_context_id(*parts: str) -> str:
    """Deterministic ID for a context object from its identifying content.

    Same engineering state always yields the same IDs, byte for byte, keeping
    the whole context stage reproducible like the rest of the platform.
    """
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"eng-{digest[:12]}"


class ChangedFile(BaseModel):
    """One file touched by a commit, reduced to a summary."""

    model_config = ConfigDict(frozen=True)

    path: str
    category: ChangeCategory = ChangeCategory.OTHER
    lines_added: int = Field(default=0, ge=0)
    lines_deleted: int = Field(default=0, ge=0)
    modules: tuple[str, ...] = Field(
        default=(), description="Design/testbench modules this path maps to, when known."
    )


class Commit(BaseModel):
    """One engineering change, normalized away from any version-control tool."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Deterministic content-derived ID (see make_context_id).")
    revision: str = Field(description="Tool-native revision: sha, changelist, review number.")
    timestamp: datetime | None = None
    author: str | None = None
    title: str = Field(description="First line of the change description.")
    files: tuple[ChangedFile, ...] = Field(default=())
    source: str = Field(description="Provider that produced this, e.g. 'git'.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def files_in_category(self, *categories: ChangeCategory) -> tuple[ChangedFile, ...]:
        """Changed files in the given categories, in declaration order."""
        wanted = set(categories)
        return tuple(f for f in self.files if f.category in wanted)


class CIRun(BaseModel):
    """One CI execution, normalized away from any CI system."""

    model_config = ConfigDict(frozen=True)

    id: str
    pipeline: str | None = None
    build_number: str | None = None
    timestamp: datetime | None = None
    simulator: str | None = None
    compiler: str | None = None
    configuration: dict[str, str] = Field(
        default_factory=dict, description="Tool versions, defines, environment markers."
    )
    environment_changes: tuple[str, ...] = Field(
        default=(),
        description="Declared drift vs the previous run (new tool version, new host image...).",
    )
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Ownership(BaseModel):
    """Who owns a scope. Informs recommendations only, never ranking."""

    model_config = ConfigDict(frozen=True)

    scope: str = Field(description="Module, path prefix, or protocol the owner covers.")
    role: str = Field(description="'rtl', 'verification', 'protocol', 'subsystem', ...")
    owner: str
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IssueRef(BaseModel):
    """A linked ticket, normalized thinly (reference material, not evidence)."""

    model_config = ConfigDict(frozen=True)

    id: str
    tracker_id: str = Field(description="Tool-native issue key, e.g. 'PROJ-123'.")
    title: str
    status: str | None = None
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EngineeringContext(BaseModel):
    """Everything the providers learned, merged and normalized.

    This is the only object the tool-agnostic core ever sees. Commits are
    bounded (recent-N, newest first) by the providers.
    """

    model_config = ConfigDict(frozen=True)

    sources: tuple[str, ...] = Field(default=(), description="Provider names that contributed.")
    capabilities: frozenset[ContextCapability] = Field(default_factory=frozenset)
    commits: tuple[Commit, ...] = Field(default=())
    ci_run: CIRun | None = None
    ownership: tuple[Ownership, ...] = Field(default=())
    issues: tuple[IssueRef, ...] = Field(default=())

    @property
    def is_empty(self) -> bool:
        return not self.commits and self.ci_run is None and not self.ownership and not self.issues

    def changed_modules(self) -> list[str]:
        """Every module named by any changed file, de-duplicated, in order."""
        seen: dict[str, None] = {}
        for commit in self.commits:
            for file in commit.files:
                for module in file.modules:
                    seen.setdefault(module, None)
        return list(seen)

    def merge(self, other: "EngineeringContext") -> "EngineeringContext":
        """Combine two provider contexts into one (frozen models: returns new).

        Commits are concatenated and de-duplicated by id; the first non-None
        CI run wins; ownership and issues concatenate.
        """
        seen: dict[str, Commit] = {c.id: c for c in self.commits}
        for commit in other.commits:
            seen.setdefault(commit.id, commit)
        return EngineeringContext(
            sources=tuple(dict.fromkeys((*self.sources, *other.sources))),
            capabilities=self.capabilities | other.capabilities,
            commits=tuple(seen.values()),
            ci_run=self.ci_run or other.ci_run,
            ownership=(*self.ownership, *other.ownership),
            issues=(*self.issues, *other.issues),
        )


class HistoricalRegression(BaseModel):
    """The thin slice of one recorded regression that impact analysis needs.

    Impact analysis deliberately does not import the storage layer; the CLI
    maps stored records into these, keeping the engineering package free of
    any downstream dependency.
    """

    model_config = ConfigDict(frozen=True)

    regression_id: str
    test_name: str | None = None
    failing_modules: tuple[str, ...] = Field(default=())
    classification: str = "unknown_failure"
    created_at: datetime | None = None


class RegressionDiff(BaseModel):
    """What changed between this run's commit and the last green run's.

    The question every verification engineer asks first and the platform
    could not answer: the regression database knew the commit each run was
    built from, and the provider seam could list commits, but nothing joined
    the two. This is that join.

    Lossy by design like everything else a provider emits: normalized commit
    summaries and module names, never diff text or patch content.
    """

    base_regression_id: str = Field(description="The last green run this compares against.")
    base_commit: str = Field(description="Commit that run was built from.")
    head_regression_id: str = Field(description="The failing run being explained.")
    head_commit: str = Field(description="Commit the failing run was built from.")
    commits: list[Commit] = Field(
        default_factory=list, description="Commits in (base, head], newest first."
    )
    changed_modules: list[str] = Field(
        default_factory=list, description="Every module touched across the range."
    )
    suspect_commits: list[str] = Field(
        default_factory=list,
        description="SHAs touching a module the failure implicates; the place to look first.",
    )
    provider: str = Field(default="", description="Provider that resolved the range.")
    truncated: bool = Field(
        default=False,
        description="The range held more commits than were collected, so changed_modules "
        "and suspect_commits are computed over a prefix and may omit the culprit.",
    )

    @property
    def is_empty(self) -> bool:
        return not self.commits


class UnavailableContextAnalysis(BaseModel):
    """An analysis that could not run because no provider had the capability.

    Surfaced in the report so degradation is honest, not silent.
    """

    model_config = ConfigDict(frozen=True)

    analysis: str
    required_capability: ContextCapability
    sources: tuple[str, ...] = Field(default=())
    reason: str
