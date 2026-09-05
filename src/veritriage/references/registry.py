"""The reference-resolver plugin table.

``Reference.uri`` has existed since Milestone 5 as a hook with nothing behind
it: packs cite a specification by name and section, and the report prints the
citation as text. Section 5.2 of the project context names the two things
that would use the hook, and they pull in opposite directions.

A company wants its internal spec database or wiki to answer, and that
adapter cannot ship here: it is site-specific and often behind
authentication. The public specifications have stable, well-known landing
pages, but fetching them at analysis time would put a network call in the
middle of a deterministic pipeline, which the platform does not do anywhere
else and will not start doing here.

A registry settles both. A resolver is a small class that claims some
sources and returns a URI for them. The built-in one is an offline catalogue,
so resolution stays a pure function. A company adds its own by registering a
class, exactly as it would add a Knowledge Pack, a learner, or a parser, and
``test_new_resolver_needs_only_registration`` proves nothing else changes.

No resolver in this package performs I/O.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

from veritriage.knowledge.model import Reference

_R = TypeVar("_R", bound=type["ReferenceResolver"])

_REGISTRY: dict[str, type["ReferenceResolver"]] = {}


class ReferenceResolver(ABC):
    """Turns a cited specification into a link, when it recognizes one."""

    #: Unique registered resolver ID.
    resolver_id: ClassVar[str]

    #: Lower runs first. Site-specific resolvers should sit below the
    #: built-in catalogue so an internal mirror wins over a public page.
    priority: ClassVar[int] = 100

    @abstractmethod
    def resolve(self, reference: Reference) -> str | None:
        """The URI for this reference, or None to defer to the next resolver.

        Must be pure: no network, no filesystem, no clock. A resolver that
        needs to reach a live system should be given its data up front, at
        construction, by whoever registers it.
        """
        raise NotImplementedError


def register_resolver(resolver_cls: _R) -> _R:
    """Class decorator adding a resolver to the registry.

    Raises:
        ValueError: If another resolver already registered the same ID.
    """
    existing = _REGISTRY.get(resolver_cls.resolver_id)
    if existing is not None and existing is not resolver_cls:
        raise ValueError(
            f"Reference resolver ID {resolver_cls.resolver_id!r} is already "
            f"registered by {existing!r}"
        )
    _REGISTRY[resolver_cls.resolver_id] = resolver_cls
    return resolver_cls


def unregister_resolver(resolver_id: str) -> None:
    """Remove a resolver (used by tests to clean up throwaway resolvers)."""
    _REGISTRY.pop(resolver_id, None)


def available_resolvers() -> dict[str, type[ReferenceResolver]]:
    """All registered resolvers, keyed by ID."""
    _ensure_builtin_resolvers()
    return dict(_REGISTRY)


def default_resolvers() -> list[ReferenceResolver]:
    """One instance of every registered resolver, in resolution order.

    Sorted by priority then ID, so the order is deterministic and a caller
    can predict which resolver wins without reading the registry.
    """
    _ensure_builtin_resolvers()
    return [
        cls()
        for cls in sorted(_REGISTRY.values(), key=lambda c: (c.priority, c.resolver_id))
    ]


def _ensure_builtin_resolvers() -> None:
    """Import the built-in resolver module so its decorator runs."""
    from veritriage.references import catalogue  # noqa: F401  (import for side effect)
