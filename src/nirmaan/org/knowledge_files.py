"""Knowledge files: the computed tier, the skill card, and the checks every knowledge document passes (M62).

The capability build-out council record of 2026-10-18 (section 9) sets the
rules; ``knowledge/README.md`` states the schema. This module is the one place
the rules are written as code, so a test can run them over every document in
``knowledge/`` and over good and bad fixtures alike.

* **Tier** (section 9.4) is computed, never declared: a skill is *practising*
  when one of its tools is ``AVAILABLE``, otherwise *knowledge only*. A
  ``CONTRACT_ONLY`` tool gives knowledge only.
* **Skill card** (section 9.2): the skill's catalog entry as sorted JSON, at
  most ``CARD_MAX`` characters.
* **Knowledge document** (sections 9.2, 9.11, 9.12): front matter with the
  fields in ``REQUIRED``, sources only of an open or purchasable access type, at
  most ``DOCUMENT_MAX`` characters, no em or en dash, no level word or readiness
  claim, and a first body line that states the computed tier.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from nirmaan.models import Skill, ToolStatus

CARD_MAX = 2_000
DOCUMENT_MAX = 12_000
REQUIRED = ("id", "skill", "as_of", "review_by", "sources", "licence_check", "export_screen", "writer", "checker")
#: Source access types a document may cite. Member-only specifications never are sources.
ACCESS = ("open", "purchasable")
EXPORT_SCREEN = ("clear", "flagged")
DASHES = (chr(0x2014), chr(0x2013))
#: Level words and readiness claims (section 9.12): a document or card never uses them.
FORBIDDEN = re.compile(
    r"(?i)\b(expert|industry[ -]level|robust|signoff[ -]clean|timing[ -]closed|tapeout[ -]ready|foundry[ -]ready)\b")


class Tier(str, Enum):
    PRACTISING = "practising"
    KNOWLEDGE_ONLY = "knowledge only"


#: How a document's first body line opens, by tier.
TIER_LINE = {Tier.PRACTISING: "Practising:", Tier.KNOWLEDGE_ONLY: "Knowledge only:"}


def skill_tier(skill: Skill, tools: dict) -> Tier:
    """Practising when one of the skill's tools is AVAILABLE, else knowledge only."""
    available = any(t in tools and tools[t].status is ToolStatus.AVAILABLE for t in skill.tools)
    return Tier.PRACTISING if available else Tier.KNOWLEDGE_ONLY


def card_text(skill: Skill) -> str:
    """The skill card as rendered for its size check: the catalog entry as sorted JSON."""
    return json.dumps(skill.model_dump(mode="json"), sort_keys=True)


def card_problems(skill: Skill) -> list[str]:
    text = card_text(skill)
    problems = []
    if len(text) > CARD_MAX:
        problems.append(f"skill card {skill.id} renders {len(text)} characters, over {CARD_MAX}")
    if any(d in text for d in DASHES):
        problems.append(f"skill card {skill.id} has an em or en dash")
    problems += [f"skill card {skill.id} uses {m.group(0)!r}" for m in FORBIDDEN.finditer(text)]
    return problems


@dataclass(frozen=True)
class Source:
    access: str
    title: str
    where: str


@dataclass
class Document:
    path: Path
    fields: dict[str, str] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
    body: str = ""
    problems: list[str] = field(default_factory=list)


def parse(path: Path) -> Document:
    """Split a document into its front matter and body; a malformed file is a problem, not an exception."""
    doc = Document(Path(path))
    text = doc.path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---" or "---" not in (line.strip() for line in lines[1:]):
        doc.problems.append("no front matter between --- lines")
        doc.body = text
        return doc
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    in_sources = False
    for raw in lines[1:end]:
        if in_sources and raw.startswith(("  -", "- ")):
            parts = [p.strip() for p in raw.strip()[1:].split("|")]
            if len(parts) != 3 or not all(parts):
                doc.problems.append(f"source line is not '- <access> | <title> | <where>': {raw.strip()}")
            else:
                doc.sources.append(Source(*parts))
            continue
        in_sources = False
        if not raw.strip():
            continue
        key, sep, value = raw.partition(":")
        if not sep:
            doc.problems.append(f"front matter line is not 'key: value': {raw.strip()}")
            continue
        key, value = key.strip(), value.strip()
        doc.fields[key] = value
        in_sources = key == "sources"
    doc.body = "\n".join(lines[end + 1:])
    return doc


def _date(value: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


def check_document(path: Path, skills: dict, tools: dict, today: _dt.date | None = None,
                   held_out: tuple[str, ...] = ()) -> tuple[list[str], list[str]]:
    """Every problem with one knowledge document, and every warning. A document passes with no problems.

    ``path`` is ``.../<division>/<skill_id>.md``; ``held_out`` are the lines of held-out eval inputs that may
    never appear in a document.
    """
    doc = parse(path)
    problems, warnings = list(doc.problems), []
    text = doc.path.read_text(encoding="utf-8")
    division, skill_id = doc.path.parent.name, doc.path.stem
    problems += [f"missing front matter field {k!r}" for k in REQUIRED if k not in doc.fields]
    if doc.fields.get("id", f"{division}/{skill_id}") != f"{division}/{skill_id}":
        problems.append(f"id {doc.fields['id']!r} is not {division}/{skill_id}, its path")
    if doc.fields.get("skill", skill_id) != skill_id:
        problems.append(f"skill {doc.fields['skill']!r} is not {skill_id}, its file name")
    skill = skills.get(skill_id)
    if skill is None:
        problems.append(f"no skill {skill_id!r} in the catalog")
    if "sources" in doc.fields and not doc.sources:
        problems.append("no source: every claim cites a source")
    problems += [f"source {s.title!r} has access {s.access!r}; only {', '.join(ACCESS)} may be cited"
                 for s in doc.sources if s.access not in ACCESS]
    if "export_screen" in doc.fields and doc.fields["export_screen"] not in EXPORT_SCREEN:
        problems.append(f"export_screen is {doc.fields['export_screen']!r}, not one of {', '.join(EXPORT_SCREEN)}")
    for key in ("licence_check", "writer", "checker"):
        if key in doc.fields and not doc.fields[key]:
            problems.append(f"{key} is empty")
    if doc.fields.get("writer") and doc.fields.get("writer") == doc.fields.get("checker"):
        problems.append("the checker is the writer: a check record comes from a different session")
    for key in ("as_of", "review_by"):
        if key in doc.fields and _date(doc.fields[key]) is None:
            problems.append(f"{key} is not a date (YYYY-MM-DD): {doc.fields[key]!r}")
    review_by = _date(doc.fields.get("review_by", ""))
    if review_by is not None and review_by < (today or _dt.date.today()):
        warnings.append(f"review_by {review_by} has passed: the document is due for review")
    if len(text) > DOCUMENT_MAX:
        problems.append(f"{len(text)} characters, over {DOCUMENT_MAX}: split the topic")
    if any(d in text for d in DASHES):
        problems.append("an em or en dash")
    problems += [f"uses {m.group(0)!r}" for m in FORBIDDEN.finditer(text)]
    first = next((line.strip() for line in doc.body.split("\n") if line.strip()), "")
    if skill is not None:
        tier = skill_tier(skill, tools)
        if not first.startswith(TIER_LINE[tier]):
            problems.append(f"the first body line must state the tier: {TIER_LINE[tier]!r} ({tier.value})")
    problems += [f"held-out eval input appears in the document: {line[:60]!r}" for line in held_out if line in text]
    return problems, warnings


def held_out_lines(cases, repo: Path, minimum: int = 30) -> tuple[str, ...]:
    """The lines of every held-out input and reference answer the eval cases name, long enough to matter."""
    from nirmaan.evals.cases import resolve

    paths = {p for case in cases for check in case.held_out for files in check.case_files.values() for p in files}
    paths |= {f.path for case in cases for f in case.reference}
    lines: set[str] = set()
    for path in sorted(paths):
        target = resolve(repo, path)
        if target.is_file():
            lines |= {line.strip() for line in target.read_text(encoding="utf-8", errors="replace").splitlines()
                      if len(line.strip()) >= minimum}
    return tuple(sorted(lines))
