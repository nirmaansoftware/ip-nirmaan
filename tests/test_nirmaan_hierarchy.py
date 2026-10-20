"""Milestone 57: the hierarchy fixes from the capability build-out council record.

The council record of 2026-10-18 (section 4) sets the target tree. These tests
check the changes it decided: the CEO spans 5, every unit with child units has
3 to 8 of them, the Commercial placeholder sits under the CPO, each capability
has one home (no duplicate security units), and every new area is a declared
placeholder with a mission, a head, and no staff. The span counted here is on
child units, never on generated ladder roles (record section 3).
"""

from __future__ import annotations

import pytest

from nirmaan.models import Function, Level, UnitKind, UnitStatus


def _children(org, unit_id):
    return [u.id for u in org.children(unit_id)]


# --- Spans --------------------------------------------------------------------------


def test_the_ceo_spans_five(nirmaan_org):
    execs = [r.id for r in nirmaan_org.roles.values() if r.reports_to == "exec.ceo" and r.unit == "executive"]
    sponsored = [u.id for u in nirmaan_org.units.values() if u.sponsor_role == "exec.ceo"]
    assert sorted(execs) == ["exec.chief_architect", "exec.chief_of_staff", "exec.coo", "exec.cpo", "exec.cto"]
    assert sponsored == []


def test_every_unit_with_children_has_three_to_eight(nirmaan_org):
    outside = {
        uid: len(_children(nirmaan_org, uid))
        for uid, unit in nirmaan_org.units.items()
        if unit.kind is not UnitKind.COMPANY and _children(nirmaan_org, uid)
        and not 3 <= len(_children(nirmaan_org, uid)) <= 8
    }
    assert outside == {}


def test_the_cpo_heads_product_and_sponsors_documentation_and_commercial(nirmaan_org):
    assert nirmaan_org.units["product"].head_role == "exec.cpo"
    sponsored = sorted(u.id for u in nirmaan_org.units.values() if u.sponsor_role == "exec.cpo")
    assert sponsored == ["commercial", "documentation"]


# --- Commercial ------------------------------------------------------------------------


def test_commercial_replaces_the_ceo_level_business_placeholders(nirmaan_org):
    for gone in ("sales", "marketing", "customer_success", "partnerships"):
        assert gone not in nirmaan_org.units
    assert _children(nirmaan_org, "commercial") == [
        "commercial.sales", "commercial.marketing", "commercial.customer_success", "commercial.applications",
    ]
    assert _children(nirmaan_org, "commercial.marketing") == [
        "commercial.marketing.brand", "commercial.marketing.web", "commercial.marketing.research",
    ]
    assert nirmaan_org.roles["commercial.vp"].reports_to == "exec.cpo"
    assert nirmaan_org.roles["commercial.sales.director"].title == "Director, Sales and Partnerships"


def test_the_commercial_tree_is_a_placeholder_with_heads_only(nirmaan_org):
    for unit in nirmaan_org.subtree("commercial"):
        assert unit.function is Function.BUSINESS and unit.status is UnitStatus.PLACEHOLDER, unit.id
        roles = nirmaan_org.roles_in(unit.id, recursive=False)
        assert [r.level for r in roles] in ([Level.VP], [Level.DIRECTOR], [Level.MANAGER]), unit.id
        assert not any(nirmaan_org.is_active(r.id) for r in roles)


# --- One home per capability -------------------------------------------------------------


def test_security_architecture_and_verification_live_in_security_only(nirmaan_org):
    assert "architecture.system.security" not in nirmaan_org.units
    assert "verification.security" not in nirmaan_org.units
    for skill in ("security_architecture", "security_verification"):
        homes = [u.id for u in nirmaan_org.units.values() if skill in u.skills]
        assert all(h.startswith("security.") for h in homes), (skill, homes)


def test_place_and_route_is_one_team_with_three_practices(nirmaan_org):
    for gone in ("placement", "cts", "routing"):
        assert f"implementation.pd.{gone}" not in nirmaan_org.units
    assert _children(nirmaan_org, "implementation.pd.place_and_route") == [
        "implementation.pd.place_and_route.placement",
        "implementation.pd.place_and_route.cts",
        "implementation.pd.place_and_route.routing",
    ]


# --- Splits -------------------------------------------------------------------------------


def test_interface_architecture_splits_into_on_chip_and_external(nirmaan_org):
    on_chip = [u.rsplit(".", 1)[1] for u in _children(nirmaan_org, "architecture.interface")]
    external = [u.rsplit(".", 1)[1] for u in _children(nirmaan_org, "architecture.io")]
    assert on_chip == ["axi", "ace", "chi", "apb", "ahb", "noc", "custom"]
    assert external == ["pcie", "cxl", "ddr", "usb", "ethernet"]
    assert "architecture.micro.noc" in nirmaan_org.units  # the public hero's NoC microarchitect


@pytest.mark.parametrize(
    ("unit", "teams"),
    [
        ("implementation.dft", ["scan_atpg", "memory_bist", "test_access"]),
        ("documentation", ["specifications", "engineering", "product"]),
        ("quality", ["reviews", "process", "configuration"]),
        ("design.integration", ["packaging", "qualification", "kits"]),
    ],
)
def test_a_one_team_unit_becomes_three_teams(nirmaan_org, unit, teams):
    assert _children(nirmaan_org, unit) == [f"{unit}.{t}" for t in teams]


def test_dft_keeps_every_practice_and_its_review_skill(nirmaan_org):
    practices = sorted(
        u.id.rsplit(".", 1)[1] for u in nirmaan_org.subtree("implementation.dft") if u.kind is UnitKind.PRACTICE
    )
    assert practices == sorted(
        ["scan", "atpg", "faults", "mbist", "memory_test", "lbist", "jtag", "compression", "verification"]
    )
    for team in _children(nirmaan_org, "implementation.dft"):
        assert "dft_architecture" in nirmaan_org.units[team].skills


# --- New areas ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unit", ["design.fpga", "implementation.foundation", "design.integration.qualification", "design.integration.kits"]
)
def test_new_engineering_areas_enter_as_placeholders(nirmaan_org, unit):
    u = nirmaan_org.units[unit]
    assert u.status is UnitStatus.PLACEHOLDER and u.mission
    assert len(nirmaan_org.roles_in(unit)) == 1
    assert not any(nirmaan_org.is_active(r.id) for r in nirmaan_org.roles_in(unit))


@pytest.mark.parametrize(
    ("unit", "manager"),
    [("infrastructure.ai", "AI Platform Manager"), ("security.platform", "Platform and Product Security Manager")],
)
def test_seats_with_no_unit_gain_active_teams(nirmaan_org, unit, manager):
    assert nirmaan_org.units[unit].status is UnitStatus.ACTIVE
    assert nirmaan_org.roles[f"{unit}.manager"].title == manager
    assert nirmaan_org.is_active(f"{unit}.engineer")


def test_every_placeholder_declares_a_mission(nirmaan_org):
    missing = [u.id for u in nirmaan_org.units.values() if u.status is UnitStatus.PLACEHOLDER and not u.mission]
    assert missing == []
