"""Knowledge documents enter the work packet, within a budget (M61).

A skill may cite a long-form knowledge document (``KnowledgeSourceKind.
KNOWLEDGE_DOCUMENT``, ref ``<division>/<skill_id>``), one file per skill at
``knowledge/<division>/<skill_id>.md`` in the repository. Until M61 only a
source's name reached the prompt; now a cited document's text enters the
packet's domain scope, so the seat reads it.

Two budgets, and no silent cut:

* the domain scope's documents together hold at most ``DOMAIN_CAP``
  characters (capability build-out council record of 2026-10-18, section 9.3;
  pull request #118, waiting for the founder);
* the rendered prompt must fit the seat's model (``context_limit`` in
  :mod:`nirmaan.runtime.model`).

A seat over either budget, or whose cited document is missing or unreadable,
declines the task with the reason; nothing is truncated and no model is called.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from nirmaan.models import KnowledgeSourceKind, Skill

#: Where knowledge documents live: ``knowledge/`` at the repository root.
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "knowledge"
#: The most characters of knowledge documents one packet's domain scope carries.
DOMAIN_CAP = 40_000

_REF = re.compile(r"[a-z0-9_]+/[a-z0-9_]+")


def valid_ref(ref: str) -> bool:
    """A document ref is ``<division>/<skill_id>``: two plain segments, no path tricks."""
    return _REF.fullmatch(ref) is not None


def document_path(ref: str, root: Path | None = None) -> Path:
    return (root or KNOWLEDGE_ROOT) / f"{ref}.md"


def cited(skill: Skill) -> tuple[str, ...]:
    """The knowledge documents a skill cites, by ref, in its order."""
    return tuple(k.ref for k in skill.knowledge_sources if k.kind is KnowledgeSourceKind.KNOWLEDGE_DOCUMENT)


def read_document(ref: str, root: Path | None = None) -> tuple[str | None, str | None, str | None]:
    """A cited document's (text, sha256, problem): the text when it can be read, else why not."""
    if not valid_ref(ref):
        return None, None, f"knowledge document ref {ref!r} is not <division>/<skill_id>"
    path = document_path(ref, root)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"knowledge document {ref} is cited but missing ({path.name} not found)"
    except OSError as exc:
        return None, None, f"knowledge document {ref} cannot be read: {exc.strerror or exc}"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, None, f"knowledge document {ref} is not UTF-8 text"
    return text, "sha256:" + hashlib.sha256(data).hexdigest(), None


def over_domain_cap(characters: int) -> str | None:
    if characters <= DOMAIN_CAP:
        return None
    return (f"the cited knowledge documents total {characters} characters, over the domain cap of "
            f"{DOMAIN_CAP}; the seat declines rather than cut them")
