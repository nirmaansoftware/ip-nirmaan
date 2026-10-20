"""Milestone 60: the span, depth and activation rules of the capability build-out council record.

Record section 3: every unit with child units has 3 to 8 of them (placeholders
count; leaves and staff executives are exempt), no role sits more than 6
layers below the Board, an exception is data with a reason and a review date
and fails once it is not needed or its date has passed, and a placeholder
declares a mission. Record section 2, item 10: a unit made ACTIVE after the
record must show one of its skills using an AVAILABLE tool and an eval case
judged by that tool. Each negative fixture below breaks one rule and must fail.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import pytest

from nirmaan.company import nirmaan_definition
from nirmaan.evals.cases import load_cases
from nirmaan.models import Function, Level, OrgUnit, Role, SpanException, ToolStatus, UnitKind, UnitStatus
from nirmaan.org import OrganizationBuilder, shape_issues
from nirmaan.org.validate import MAX_DEPTH, executive_span

REPO = Path(__file__).resolve().parents[1]
ACTIVE_AT_M60 = frozenset(
    line.strip()
    for line in (REPO / "tests" / "fixtures" / "org" / "active-units-m60.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
)
TODAY = date.today()


def _build(mutate=None):
    definition = nirmaan_definition()
    if mutate:
        mutate(definition)
    return OrganizationBuilder(definition).build(extensions=False)


def _replace(definition, unit_id, **update):
    i = next(i for i, u in enumerate(definition.units) if u.id == unit_id)
    definition.units[i] = definition.units[i].model_copy(update=update)


def _add(definition, uid, kind, parent, **kw):
    noun = kw.pop("noun", "Fixture Engineer")
    definition.units.append(OrgUnit(id=uid, name=uid.rsplit(".", 1)[1].title(), kind=kind,
                                    function=Function.ENGINEERING, parent=parent, noun=noun, **kw))


def _judged_tools(case) -> set[str]:
    return {t for check in case.held_out for t in (check.tool, check.cover_tool) if t}


def unbacked_active_units(org, cases) -> list[str]:
    """ACTIVE units outside the frozen list with no skill of their own that uses an AVAILABLE tool and is named by
    an eval case judged by that tool."""
    unbacked = []
    for unit in org.units.values():
        if unit.status is not UnitStatus.ACTIVE or unit.id in ACTIVE_AT_M60:
            continue
        backed = any(
            org.tools[tool].status is ToolStatus.AVAILABLE
            and any(skill in case.skills and tool in _judged_tools(case) for case in cases)
            for skill in unit.skills
            for tool in org.skills[skill].tools
        )
        if not backed:
            unbacked.append(unit.id)
    return unbacked


# --- The shipped chart ---------------------------------------------------------------------


def test_the_chart_passes_with_zero_exceptions(nirmaan_org):
    assert [u.id for u in nirmaan_org.units.values() if u.span_exception] == []
    assert shape_issues(nirmaan_org, today=TODAY) == []


def test_executive_spans_count_units_and_explicit_reports(nirmaan_org):
    spans = {r: len(executive_span(nirmaan_org, r)) for r in
             ("exec.ceo", "exec.cto", "exec.coo", "exec.cpo", "exec.chief_architect", "exec.chief_of_staff")}
    assert spans == {"exec.ceo": 5, "exec.cto": 5, "exec.coo": 7, "exec.cpo": 5, "exec.chief_architect": 4,
                     "exec.chief_of_staff": 0}


def test_no_role_is_more_than_six_layers_below_the_board(nirmaan_org):
    assert max(len(nirmaan_org.line_chain(r)) for r in nirmaan_org.roles) == MAX_DEPTH


def test_every_active_unit_is_in_the_frozen_list_or_backed(nirmaan_org):
    assert unbacked_active_units(nirmaan_org, load_cases(REPO / "evals")) == []


def test_the_frozen_list_names_only_units_that_exist(nirmaan_org):
    assert ACTIVE_AT_M60 <= set(nirmaan_org.units)


def test_the_frozen_list_is_pinned():
    # Never extended by hand: a unit made ACTIVE later passes by its eval case, not by joining the list. Any edit
    # to the fixture fails here, so it has to change this pin in the same pull request, where review sees it.
    digest = hashlib.sha256("\n".join(sorted(ACTIVE_AT_M60)).encode()).hexdigest()
    assert (len(ACTIVE_AT_M60), digest) == (
        205, "dca031f484116a7f0f3e776b3536c69349e111e7bba0309212a202314347bb63"
    )


# --- Negative fixtures: each must fail -----------------------------------------------------


def test_a_unit_with_nine_child_units_fails():
    def mutate(d):
        for slug in ("x1", "x2"):
            _add(d, f"design.rtl.design.{slug}", UnitKind.PRACTICE, "design.rtl.design", skills=("rtl_design",))

    assert shape_issues(_build(mutate)) == ["unit design.rtl.design: 9 child units, outside 3 to 8"]


def test_a_unit_with_two_child_units_fails():
    def mutate(d):
        d.units[:] = [u for u in d.units if u.id != "commercial.marketing.web"]

    assert shape_issues(_build(mutate)) == ["unit commercial.marketing: 2 child units, outside 3 to 8"]


def test_a_chain_seven_layers_below_the_board_fails():
    # Strict seniority already stops a nested unit from adding a layer, so the fixture adds an explicit role below
    # a leaf's senior engineer: Board, CEO, CTO, VP, director, manager, senior, then this role.
    def mutate(d):
        boss = "design.integration.packaging.senior"
        d.roles.append(Role(id="design.integration.packaging.apprentice", title="Packaging Apprentice",
                            unit="design.integration.packaging", level=Level.INTERN, reports_to=boss,
                            escalates_to=boss, generated=False))

    assert shape_issues(_build(mutate)) == [
        f"role design.integration.packaging.apprentice: 7 layers below the Board, more than {MAX_DEPTH}"
    ]


def test_an_executive_outside_the_range_fails():
    def mutate(d):
        for slug in ("lab1", "lab2", "lab3", "lab4"):
            d.units.append(OrgUnit(id=slug, name=slug.title(), kind=UnitKind.DIVISION, function=Function.ENGINEERING,
                                   parent="nirmaan", sponsor_role="exec.cto", status=UnitStatus.PLACEHOLDER,
                                   mission="A fixture area."))

    assert shape_issues(_build(mutate)) == ["role exec.cto: span 9, outside 3 to 8"]


def test_an_exception_that_is_no_longer_needed_fails():
    def mutate(d):
        _replace(d, "design.rtl.design",
                 span_exception=SpanException(reason="Waiting for the wave.", review_by=TODAY + timedelta(days=90)))

    assert shape_issues(_build(mutate), today=TODAY) == [
        "unit design.rtl.design: span exception not needed (7 child units)"
    ]


def test_an_exception_past_its_review_date_fails_and_a_current_one_passes():
    def nine(review_by):
        def mutate(d):
            for slug in ("x1", "x2"):
                _add(d, f"design.rtl.design.{slug}", UnitKind.PRACTICE, "design.rtl.design", skills=("rtl_design",))
            _replace(d, "design.rtl.design",
                     span_exception=SpanException(reason="Split in the RTL wave.", review_by=review_by))
        return mutate

    past = TODAY - timedelta(days=1)
    assert shape_issues(_build(nine(past)), today=TODAY) == [
        f"unit design.rtl.design: span exception review date {past.isoformat()} has passed"
    ]
    assert shape_issues(_build(nine(TODAY + timedelta(days=30))), today=TODAY) == []


def test_an_exception_needs_a_reason():
    with pytest.raises(ValueError):
        SpanException(reason="", review_by=TODAY)


def test_a_placeholder_without_a_mission_fails():
    def mutate(d):
        _replace(d, "design.fpga", mission="")

    assert shape_issues(_build(mutate)) == ["unit design.fpga: a placeholder declares no mission"]


def test_an_unbacked_active_unit_fails():
    def mutate(d):
        _add(d, "design.rtl.design.x1", UnitKind.PRACTICE, "design.rtl.design", skills=("threat_modeling",))

    assert unbacked_active_units(_build(mutate), load_cases(REPO / "evals")) == ["design.rtl.design.x1"]


def test_an_active_unit_backed_by_a_tool_judged_case_passes():
    def mutate(d):
        _add(d, "design.rtl.design.x1", UnitKind.PRACTICE, "design.rtl.design", skills=("rtl_design",))

    assert unbacked_active_units(_build(mutate), load_cases(REPO / "evals")) == []
