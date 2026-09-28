"""Milestone 19: authority, escalation routing, tool permissions, the constitution.

Authority is a table lookup scoped to the org chart; escalation is a route
walked up the technical chain; tools are capability-granted and honestly
refused when they cannot run; and every article of the constitution is backed
by a registered check.
"""

from __future__ import annotations

import pytest

from nirmaan.models import Criticality, DecisionKind, EscalationKind, Level
from nirmaan.org import AuthorityService, route_escalation
from nirmaan.work import PolicyEngine, available_checks

D, C = DecisionKind, Criticality


@pytest.fixture(scope="module")
def authority(nirmaan_org):
    return AuthorityService(nirmaan_org)


def test_permitted_action(authority):
    verdict = authority.check("design.rtl.design.tech_lead", D.APPROVE_ARTIFACT, C.HIGH, "design.rtl.design.fsm")
    assert verdict.allowed


def test_denied_by_level_names_who_can(authority):
    verdict = authority.check("design.rtl.design.fsm.engineer", D.APPROVE_ARTIFACT, C.HIGH, "design.rtl.design.fsm")
    assert not verdict.allowed
    assert verdict.required_level is Level.TECH_LEAD
    assert verdict.escalate_to == "design.rtl.design.tech_lead"


def test_denied_outside_authority_domain(authority):
    # A tech lead's approval authority stops at the edge of their own team.
    verdict = authority.check("design.rtl.design.tech_lead", D.APPROVE_ARTIFACT, C.HIGH, "verification.debug.triage")
    assert not verdict.allowed and "outside" in verdict.reason


def test_review_crosses_teams_within_a_division(authority):
    assert authority.check("design.rtl.cdc.senior", D.REVIEW_ARTIFACT, C.HIGH, "design.rtl.design.fsm").allowed
    assert not authority.check("design.rtl.cdc.senior", D.REVIEW_ARTIFACT, C.HIGH, "verification.cdc").allowed


def test_criticality_raises_the_bar(authority):
    role = "verification.debug.triage.junior"
    assert authority.check(role, D.EXECUTE_TASK, C.MEDIUM).allowed
    assert not authority.check(role, D.EXECUTE_TASK, C.HIGH).allowed


def test_major_decisions_need_executives(authority):
    assert not authority.check("design.vp", D.ARCHITECTURE_DECISION, C.CRITICAL).allowed
    assert authority.check("exec.chief_architect", D.ARCHITECTURE_DECISION, C.CRITICAL).allowed
    assert not authority.check("verification.vp", D.RELEASE, C.CRITICAL).allowed


@pytest.mark.parametrize("kind, raiser, expected", [
    (EscalationKind.UNCERTAINTY, "verification.debug.triage.intern", "verification.debug.triage.junior"),
    (EscalationKind.TECHNICAL, "verification.debug.triage.engineer", "verification.debug.tech_lead"),
    (EscalationKind.ARCHITECTURAL, "design.rtl.design.fsm.senior", "design.rtl.design.tech_lead"),
    (EscalationKind.CROSS_TEAM, "design.rtl.design.fsm.senior", "design.rtl.design.manager"),
    (EscalationKind.STRATEGIC, "design.rtl.design.fsm.senior", "design.rtl.director"),
    (EscalationKind.MAJOR_ARCHITECTURAL, "design.rtl.director", "exec.chief_architect"),
])
def test_escalation_routes_by_kind(nirmaan_org, kind, raiser, expected):
    assert route_escalation(nirmaan_org, raiser, kind) == expected


def test_escalation_never_lands_below_the_raiser(nirmaan_org):
    for kind in EscalationKind:
        for raiser in ("verification.debug.tech_lead", "design.rtl.director", "verification.vp"):
            target = route_escalation(nirmaan_org, raiser, kind)
            assert nirmaan_org.roles[target].level.rank > nirmaan_org.roles[raiser].level.rank, (kind, raiser)


def test_tools_are_refused_honestly(authority):
    ok, _ = authority.may_use_tool("verification.debug.triage.engineer", "veritriage.investigate")
    assert ok
    ok, why = authority.may_use_tool("verification.debug.triage.engineer", "simulator.run")
    assert not ok and "not granted" in why
    ok, why = authority.may_use_tool("design.rtl.design.fsm.engineer", "simulator.run")
    assert not ok and "contract-only" in why


def test_every_article_of_the_constitution_is_enforced(nirmaan_org):
    PolicyEngine(nirmaan_org)  # raises if an article names an unregistered check
    assert [p.id for p in nirmaan_org.principles.values()] == [f"P{i}" for i in range(1, 13)]
    named = {c for p in nirmaan_org.principles.values() for c in p.checks}
    assert named <= set(available_checks())
