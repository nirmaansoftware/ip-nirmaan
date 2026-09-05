"""The context provider interface: the ONLY tool-aware code in the platform.

A provider's whole and only job is to turn one engineering system's state (a
git repository, a CI export, a review system, a tracker) into normalized
:class:`~veritriage.engineering.model.EngineeringContext`. It may shell out to
a tool binary or read tool exports, but under the lossy-by-design law it may
only emit normalized summaries: no diff text, no patch content, no raw tool
payloads survive outside the provider. Providers never touch the Evidence
Graph, reasoning, or AI.

Add a new engineering system (GitHub, GitLab, Perforce, Gerrit, Jenkins,
Jira, DOORS, internal tooling) by writing a new ``ContextProvider`` subclass
and registering it. Nothing else in the platform changes; the architecture
tests in ``tests/test_engineering.py`` prove it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from veritriage.engineering.model import (
    Commit,
    ContextCapability,
    EngineeringContext,
)


class ContextProviderError(RuntimeError):
    """Raised when a provider cannot read the system it fronts."""


class ContextProvider(ABC):
    """Base class for every engineering context provider.

    Subclasses set :attr:`name`, :attr:`source`, and :attr:`capabilities`,
    implement :meth:`available` and :meth:`collect`, and register with
    ``@register_provider``.
    """

    #: Unique provider name (used in provenance and the ``context`` CLI table).
    name: ClassVar[str]

    #: Provenance tag stamped on every model this provider emits, e.g. "git".
    source: ClassVar[str]

    #: What this provider can resolve. Analyses needing a missing capability
    #: are reported unavailable rather than silently skipped.
    capabilities: ClassVar[frozenset[ContextCapability]] = frozenset()

    @classmethod
    @abstractmethod
    def available(cls, root: Path) -> bool:
        """Whether this provider can produce context for ``root``."""
        raise NotImplementedError

    def changes_between(
        self, root: Path, base_commit: str, head_commit: str, max_commits: int = 50
    ) -> list["Commit"] | None:
        """Normalized commits in ``(base_commit, head_commit]``, newest first.

        Optional. The default returns None, meaning "this system cannot answer
        a range query", so every existing provider keeps working untouched and
        a caller can tell "no commits between them" (an empty list) from "I
        cannot tell you" (None). A provider that implements this must also
        declare :attr:`ContextCapability.CHANGE_RANGE`.
        """
        return None

    @abstractmethod
    def collect(self, root: Path, max_commits: int = 10) -> EngineeringContext:
        """Gather and normalize context for ``root``.

        Implementations must stamp ``source`` and ``capabilities`` on the
        returned context and must degrade to an empty context rather than
        raising when the system is reachable but has nothing to report.
        """
        raise NotImplementedError
