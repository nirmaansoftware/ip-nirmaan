"""Knowledge files follow the schema in knowledge/README.md (M62).

Every document under knowledge/ passes ``nirmaan.org.knowledge_files``; every
skill card fits 2,000 characters with no dash, level word or readiness claim;
the tier is computed from tool status. A good fixture passes, and each rule has
a bad variant that fails on exactly that rule.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import load_cases
from nirmaan.org import knowledge_files as kf
from nirmaan.org.knowledge_files import Tier, card_problems, check_document, held_out_lines, skill_tier

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
GOOD = Path(__file__).parent / "fixtures" / "knowledge" / "software" / "c_programming.md"
TODAY = dt.date(2026, 10, 19)


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _check(org, path: Path, held_out: tuple[str, ...] = ()):
    return check_document(path, org.skills, org.tools, today=TODAY, held_out=held_out)


def _variant(tmp_path: Path, old: str, new: str, name: str = "c_programming", division: str = "software") -> Path:
    text = GOOD.read_text(encoding="utf-8")
    assert old in text, old
    path = tmp_path / division / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


# --- The repository -----------------------------------------------------------------------------


def test_every_knowledge_document_passes(org):
    held = held_out_lines(load_cases(ROOT / "evals"), ROOT)
    docs = sorted(p for p in KNOWLEDGE.rglob("*.md") if p.name != "README.md")
    failures = {str(p.relative_to(ROOT)): _check(org, p, held)[0] for p in docs}
    assert {k: v for k, v in failures.items() if v} == {}


def test_every_skill_card_fits_and_keeps_the_writing_rules(org):
    assert len(org.skills) >= 140
    assert [p for s in org.skills.values() for p in card_problems(s)] == []
    assert max(len(kf.card_text(s)) for s in org.skills.values()) <= kf.CARD_MAX


def test_the_tier_is_computed_from_tool_status(org):
    # c_programming's only tool, compiler.run, is CONTRACT_ONLY: its static-analysis criterion is knowledge only.
    assert org.tools["compiler.run"].status.value == "contract_only"
    assert skill_tier(org.skills["c_programming"], org.tools) is Tier.KNOWLEDGE_ONLY
    practising = [s for s in org.skills.values() if skill_tier(s, org.tools) is Tier.PRACTISING]
    assert practising and all(any(org.tools[t].status.value == "available" for t in s.tools) for s in practising)
    assert skill_tier(org.skills["c_programming"].model_copy(update={"tools": ()}), org.tools) is Tier.KNOWLEDGE_ONLY


def test_held_out_eval_inputs_are_found():
    held = held_out_lines(load_cases(ROOT / "evals"), ROOT)
    assert held, "the eval cases name held-out inputs"


# --- Fixtures: one good, one bad per rule -------------------------------------------------------


def test_the_good_fixture_passes(org):
    assert _check(org, GOOD) == ([], [])


@pytest.mark.parametrize("old, new, expected", [
    ("checker: fixture checker\n", "", "missing front matter field 'checker'"),
    ("as_of: 2026-10-19\n", "", "missing front matter field 'as_of'"),
    ("  - open | SEI CERT", "  - member-only | SEI CERT", "access 'member-only'"),
    ("checker: fixture checker", "checker: fixture writer", "the checker is the writer"),
    ("export_screen: clear", "export_screen: maybe", "export_screen is 'maybe'"),
    ("review_by: 2099-01-01", "review_by: next year", "review_by is not a date"),
    ("id: software/c_programming", "id: software/other", "is not software/c_programming"),
    ("Knowledge only: no tool run backs this.", "Practising: a tool backs this.", "must state the tier"),
    ("Embedded C", "Expert embedded C", "uses 'Expert'"),
    ("Embedded C", "Tapeout ready embedded C", "uses 'Tapeout ready'"),
    ("Embedded C", "Embedded C " + chr(0x2014) + " for drivers", "an em or en dash"),
    ("## Failure modes", "## Failure modes\n\n" + "x" * kf.DOCUMENT_MAX, "over 12000"),
    ("---\nid:", "id:", "no front matter"),
])
def test_each_rule_has_a_failing_fixture(org, tmp_path, old, new, expected):
    problems, _ = _check(org, _variant(tmp_path, old, new))
    assert any(expected in p for p in problems), problems


def test_a_document_for_an_unknown_skill_fails(org, tmp_path):
    path = _variant(tmp_path, "c_programming", "no_such_skill", name="no_such_skill")
    assert any("no skill 'no_such_skill'" in p for p in _check(org, path)[0])


def test_a_held_out_input_in_a_document_fails(org, tmp_path):
    line = "assert property (@(posedge clk) full |-> !wr_en_accepted);"
    path = _variant(tmp_path, "## Failure modes", f"## Failure modes\n\n{line}")
    assert any("held-out eval input" in p for p in _check(org, path, held_out=(line,))[0])


def test_a_past_review_date_warns_and_does_not_fail(org, tmp_path):
    path = _variant(tmp_path, "review_by: 2099-01-01", "review_by: 2026-01-01")
    problems, warnings = _check(org, path)
    assert problems == [] and warnings == ["review_by 2026-01-01 has passed: the document is due for review"]


def test_an_oversized_skill_card_fails(org):
    skill = org.skills["c_programming"]
    big = skill.model_copy(update={"procedures": ("Write MISRA-aware embedded C. " * 100,)})
    assert any("over 2000" in p for p in card_problems(big))
