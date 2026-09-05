"""Reference resolution: cited specifications become links.

The seam Milestone 5 left open. Packs cite a document and a section; a
resolver turns that citation into a URI when it recognizes the document.
Built-in resolution is a static offline catalogue of public standards, so
the pipeline stays deterministic and offline; a company plugs its internal
spec database or wiki in by registering one class.
"""

from veritriage.references.catalogue import CATALOGUE, PublicSpecificationCatalogue
from veritriage.references.registry import (
    ReferenceResolver,
    available_resolvers,
    default_resolvers,
    register_resolver,
    unregister_resolver,
)
from veritriage.references.resolve import resolve_reference, resolve_references

__all__ = [
    "CATALOGUE",
    "PublicSpecificationCatalogue",
    "ReferenceResolver",
    "available_resolvers",
    "default_resolvers",
    "register_resolver",
    "resolve_reference",
    "resolve_references",
    "unregister_resolver",
]
