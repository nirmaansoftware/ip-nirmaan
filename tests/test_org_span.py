"""Milestone 60: the span, depth and activation rules of the capability build-out council record.

Record section 3: every unit with child units has 3 to 8 of them (placeholders
count; leaves and staff executives are exempt), no role sits more than 6
layers below the Board, an exception is data with a reason and a review date
and fails once it is not needed or its date has passed, and a placeholder
declares a mission. Record section 2, item 10 (amended by council record
2026-11-14-g13-grouping-units): a unit made ACTIVE after the record must show
(a) one of its skills using an AVAILABLE tool and an eval case judged by that
tool, or (b) that it is a grouping unit (no skills, tools, ladder or explicit
roles of its own; every ACTIVE child frozen or backed by (a), at least one; a
head that holds nothing its parent's head does not). The frozen list never
gains a unit: it changes only by removals and renames, and grouping units pass
by this test, not by the list. Each negative fixture below breaks one rule and
must fail.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import pytest

from nirmaan.company import nirmaan_definition
from nirmaan.company.org_chart import KNOWLEDGE_LADDER
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


def _backed(org, unit, cases) -> bool:
    """Item 10 (a): one of the unit's own skills uses an AVAILABLE tool and is named by an eval case judged by it."""
    return any(
        org.tools[tool].status is ToolStatus.AVAILABLE
        and any(skill in case.skills and tool in _judged_tools(case) for case in cases)
        for skill in unit.skills
        for tool in org.skills[skill].tools
    )


def _own_additions(org, unit) -> list[str]:
    """What a unit adds of its own: any of these and it is not a grouping unit, so it must meet (a)."""
    own = [f"own {what}" for what, value in (("skill", unit.skills), ("tool", unit.tools), ("ladder", unit.ladder))
           if value]
    own += [f"explicit role {r.id}" for r in org.roles_in(unit.id, recursive=False) if not r.generated]
    return own


def _head_grants(org, unit_id) -> set[str]:
    head = org.head_of(unit_id) if unit_id else None
    if head is None:
        return set()
    return {f"capability {c}" for c in org.capabilities_of(head.id)} | {f"tool {t}" for t in org.tools_of(head.id)}


def unbacked_active_units(org, cases) -> list[str]:
    """Each ACTIVE unit outside the frozen list that meets neither (a) nor (b) of record item 10, with the condition
    it fails ("unit: reason"). (a): one of its own skills uses an AVAILABLE tool and is named by an eval case judged
    by that tool. (b) a grouping unit: no skills, tools, ladder or explicit roles of its own; at least one ACTIVE
    child, and every ACTIVE child frozen or meeting (a), so a new grouping unit never counts as the ACTIVE child of
    another; its head holds no capability or tool that its parent unit's head does not. PLACEHOLDER children are
    allowed. Council record 2026-11-14-g13-grouping-units."""
    issues = []
    for unit in org.units.values():
        if unit.status is not UnitStatus.ACTIVE or unit.id in ACTIVE_AT_M60 or _backed(org, unit, cases):
            continue
        own = _own_additions(org, unit)
        if own:
            issues += [f"{unit.id}: {reason}, not backed" for reason in own]
            continue
        active = [c for c in org.children(unit.id) if c.status is UnitStatus.ACTIVE]
        if not active:
            issues.append(f"{unit.id}: no ACTIVE child")
        for child in active:
            if child.id in ACTIVE_AT_M60 or _backed(org, child, cases):
                continue
            kind = "is a new grouping unit" if not _own_additions(org, child) else "neither frozen nor backed"
            issues.append(f"{unit.id}: ACTIVE child {child.id} {kind}")
        extra = _head_grants(org, unit.id) - _head_grants(org, unit.parent)
        issues += [f"{unit.id}: head holds {grant}, which its parent's head does not" for grant in sorted(extra)]
    return issues


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
    # The list never gains a unit: a unit made ACTIVE later passes by its eval case or as a grouping unit, not by
    # joining the list. It changes only when a unit in it is removed or moved (renamed), and an id reused for a
    # different unit leaves it; wave 2 (M77) renamed the 26 verification units and added none. Any edit to the
    # fixture fails here, so it has to change this pin in the same pull request, where review sees it.
    digest = hashlib.sha256("\n".join(sorted(ACTIVE_AT_M60)).encode()).hexdigest()
    assert (len(ACTIVE_AT_M60), digest) == (
        205, "30905852b486f1f2aa6ebf5c767f61f8056f4ff8a4b25626c705053316b3ab43"
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

    assert unbacked_active_units(_build(mutate), load_cases(REPO / "evals")) == [
        "design.rtl.design.x1: own skill, not backed"
    ]


def test_an_active_unit_backed_by_a_tool_judged_case_passes():
    def mutate(d):
        _add(d, "design.rtl.design.x1", UnitKind.PRACTICE, "design.rtl.design", skills=("rtl_design",))

    assert unbacked_active_units(_build(mutate), load_cases(REPO / "evals")) == []


# --- Grouping units (record item 10 (b)): the four Verification departments pass; N1 to N9 each break one condition --
#
# The fixtures are the council record 2026-11-14-g13-grouping-units, decision 3.4, built on the shipped chart.

GROUPING = ("verification.methodology", "verification.dynamic", "verification.formal", "verification.debug")


def _unbacked(mutate=None):
    return unbacked_active_units(_build(mutate), load_cases(REPO / "evals"))


def test_the_four_verification_departments_pass_as_grouping_units(nirmaan_org):
    for uid in GROUPING:
        unit = nirmaan_org.units[uid]
        assert unit.status is UnitStatus.ACTIVE and uid not in ACTIVE_AT_M60, uid
        assert _own_additions(nirmaan_org, unit) == [], uid
    assert _unbacked() == []


def test_n1_a_grouping_unit_with_a_skill_of_its_own_fails():
    def mutate(d):
        _replace(d, "verification.methodology", skills=("debugging",))

    assert _unbacked(mutate) == ["verification.methodology: own skill, not backed"]


def test_n2_a_grouping_unit_with_a_tool_of_its_own_fails():
    def mutate(d):
        _replace(d, "verification.methodology", tools=("git.read",))

    assert _unbacked(mutate) == ["verification.methodology: own tool, not backed"]


def test_n3_a_grouping_unit_with_a_ladder_of_its_own_fails():
    def mutate(d):
        _replace(d, "verification.methodology", ladder=KNOWLEDGE_LADDER)

    assert _unbacked(mutate) == ["verification.methodology: own ladder, not backed"]


def test_n4_a_grouping_unit_with_an_explicit_role_fails():
    def mutate(d):
        boss = "verification.methodology.director"
        d.roles.append(Role(id="verification.methodology.fixture", title="Methodology Fixture Engineer",
                            unit="verification.methodology", level=Level.SENIOR, reports_to=boss,
                            escalates_to=boss, generated=False))

    assert _unbacked(mutate) == [
        "verification.methodology: explicit role verification.methodology.fixture, not backed"
    ]


def test_n5_a_grouping_unit_with_only_placeholder_children_fails():
    def mutate(d):
        _add(d, "verification.fixture", UnitKind.DEPARTMENT, "verification")
        for slug in ("p1", "p2"):
            _add(d, f"verification.fixture.{slug}", UnitKind.TEAM, "verification.fixture",
                 status=UnitStatus.PLACEHOLDER, mission="A fixture area.")

    assert _unbacked(mutate) == ["verification.fixture: no ACTIVE child"]


def test_n6_a_grouping_unit_with_no_children_fails():
    def mutate(d):
        _add(d, "verification.fixture", UnitKind.DEPARTMENT, "verification")

    assert _unbacked(mutate) == ["verification.fixture: no ACTIVE child"]


def test_n7_a_grouping_unit_over_an_unbacked_new_unit_fails():
    def mutate(d):
        _add(d, "verification.fixture", UnitKind.DEPARTMENT, "verification")
        _add(d, "verification.fixture.team", UnitKind.TEAM, "verification.fixture", skills=("functional_coverage",))

    assert _unbacked(mutate) == [
        "verification.fixture: ACTIVE child verification.fixture.team neither frozen nor backed",
        "verification.fixture.team: own skill, not backed",
    ]


def test_n8_a_grouping_unit_over_a_new_grouping_unit_fails():
    def mutate(d):
        _add(d, "verification.fixture", UnitKind.DEPARTMENT, "verification")
        _add(d, "verification.fixture.group", UnitKind.TEAM, "verification.fixture")
        for uid in ("verification.dynamic.coverage.code", "verification.dynamic.coverage.functional"):
            _replace(d, uid, parent="verification.fixture.group")

    # The team itself passes: both its ACTIVE children are frozen.
    assert _unbacked(mutate) == ["verification.fixture: ACTIVE child verification.fixture.group is a new grouping unit"]


def test_n9_a_grouping_unit_whose_head_holds_more_than_its_parents_head_fails():
    # In today's code a grouping unit's head can exceed its parent's only through a level profile (record decision 2b).
    def mutate(d):
        i = next(i for i, p in enumerate(d.level_profiles) if p.level is Level.DIRECTOR)
        profile = d.level_profiles[i]
        d.level_profiles[i] = profile.model_copy(
            update={"capabilities": (*profile.capabilities, "signoff.implementation")})

    assert _unbacked(mutate) == [
        f"{uid}: head holds capability signoff.implementation, which its parent's head does not" for uid in GROUPING
    ]
