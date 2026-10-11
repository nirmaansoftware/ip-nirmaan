"""Applying the registered resolvers to a citation.

Two rules make resolution predictable. A reference that already carries a
URI keeps it, because whoever minted the pack knew more than the catalogue
does. Otherwise the registered resolvers are tried in priority order and the
first one to claim the source wins, so a site-specific resolver placed above
the public catalogue shadows it for the sources it knows.
"""

from __future__ import annotations

from veritriage.knowledge.model import Reference
from veritriage.references.registry import ReferenceResolver, default_resolvers


def resolve_reference(
    reference: Reference, resolvers: list[ReferenceResolver] | None = None
) -> str | None:
    """The URI for one citation, or None when nothing recognizes it."""
    if reference.uri:
        return reference.uri
    for resolver in resolvers if resolvers is not None else default_resolvers():
        uri = resolver.resolve(reference)
        if uri:
            return uri
    return None


def resolve_references(
    references: list[Reference], resolvers: list[ReferenceResolver] | None = None
) -> list[Reference]:
    """Copies of the citations with ``uri`` filled in where one was found.

    The inputs are never mutated: packs are module-level constants shared by
    every analysis in the process, so resolution returns copies.
    """
    active = resolvers if resolvers is not None else default_resolvers()
    out: list[Reference] = []
    for reference in references:
        uri = resolve_reference(reference, active)
        out.append(reference if uri == reference.uri else reference.model_copy(update={"uri": uri}))
    return out
