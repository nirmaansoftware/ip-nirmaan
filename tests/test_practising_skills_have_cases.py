"""Practising skills have evals: the closed list of exceptions (wave 2 close, gate W2C10).

A Verification skill that computes as practising (one of its tools is available) must have an eval case that names
it, unless it is one of three named exceptions. The list is closed: it lives here and in
``docs/EVAL_SKILLS_MUST_FAIL.md`` section 6, and the test fails when the two disagree, so adding a skill is a
change to both that a reviewer sees. Skills of other divisions belong to their own waves' exits.
"""

from __future__ import annotations

import re
from pathlib import Path

from nirmaan.evals import load_cases
from nirmaan.org.knowledge_files import Tier, skill_tier

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "EVAL_SKILLS_MUST_FAIL.md"
DIVISION = "verification"

#: Tool available, no eval case, not measured, at Knowledge. Closed: see the module docstring.
CLOSED_EXCEPTIONS = frozenset({"log_analysis", "regression_management", "regression_intelligence"})

#: Named exceptions that are not practising skills without a case: no knowledge document, or another wave's.
NAMED_EXCEPTIONS = frozenset({"waveform_debug", "systemverilog", "security_verification"})
NO_KNOWLEDGE_DOCUMENT = ("waveform_debug", "systemverilog")


def _practising(org) -> set[str]:
    return {s.id for s in org.skills.values()
            if s.domain == DIVISION and skill_tier(s, org.tools) is Tier.PRACTISING}


def _cased() -> set[str]:
    return {skill for case in load_cases(REPO / "evals") for skill in case.skills}


def _section() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index('## 6. Named exceptions to "Practising skills have evals"')
    end = text.index("\n## ", start + 1)
    return text[start:end]


def _table_skills(chunk: str) -> list[str]:
    return re.findall(r"^\| ([a-z_]+) \|", chunk, flags=re.M)


def test_every_practising_verification_skill_has_a_case_or_is_a_closed_exception(nirmaan_org):
    uncovered = _practising(nirmaan_org) - _cased() - CLOSED_EXCEPTIONS
    assert not uncovered, (
        f"practising skills with no eval case: {sorted(uncovered)}. Add a case that names each, or (only by a "
        "council ruling) change CLOSED_EXCEPTIONS and docs/EVAL_SKILLS_MUST_FAIL.md section 6 together")


def test_a_closed_exception_is_still_practising_by_tool_and_still_has_no_case(nirmaan_org):
    practising, cased = _practising(nirmaan_org), _cased()
    assert CLOSED_EXCEPTIONS <= practising, sorted(CLOSED_EXCEPTIONS - practising)
    gained = CLOSED_EXCEPTIONS & cased
    assert not gained, f"{sorted(gained)} now have a case: remove them from the closed list and the page"


def test_the_closed_list_is_three_skills():
    assert len(CLOSED_EXCEPTIONS) == 3 and not CLOSED_EXCEPTIONS & NAMED_EXCEPTIONS


def test_the_page_lists_exactly_the_closed_and_the_named_exceptions():
    section = _section()
    closed, named = section.split("Three more skills", 1)
    assert set(_table_skills(closed)) == CLOSED_EXCEPTIONS
    assert set(_table_skills(named)) == NAMED_EXCEPTIONS
    for words in ("tool available, no eval case, not measured, at Knowledge", "The list is closed."):
        assert words in section


def test_the_named_exceptions_are_what_the_page_says(nirmaan_org):
    for skill in NAMED_EXCEPTIONS:
        assert skill in nirmaan_org.skills, skill
    for skill in NO_KNOWLEDGE_DOCUMENT:
        document = REPO / "knowledge" / nirmaan_org.skills[skill].domain / f"{skill}.md"
        other = list((REPO / "knowledge").glob(f"*/{skill}.md"))
        assert not document.exists() and not other, f"{skill} now has a document: revisit its exception"
    assert "security_verification" not in _practising(nirmaan_org)
