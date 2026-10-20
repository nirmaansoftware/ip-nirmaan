"""The seat map (council/seat-map.yml) and the derived key data in .github/review-teams.yml.

Capability build-out council record of 2026-10-18, sections 5 and 6 (proposed
in pull request #118), as corrected by the review-loop council record of
2026-10-18 (proposed in pull request #123): each council
seat maps to one org role or one shared role; each review team stores `unit:`
(the lowest common unit of its lead seats' roles and covers, or `shared`) and
`key2:`; this test recomputes both from the seat map and build_organization(),
so a chart or seat change that moves a derived value fails until the stored
value changes too. A derived key 2 that would be the founder or report to the
founder is the chair. Nothing that picks a reviewer reads the chart.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.models import UnitKind

ROOT = Path(__file__).resolve().parents[1]
FOUNDER = "founder"
BOARD = "exec.board"

_spec = importlib.util.spec_from_file_location("review_map", ROOT / "scripts" / "review_map.py")
review_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review_map)


def _load(path: Path) -> dict:
    return review_map.load_map(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seat_map() -> dict:
    return _load(ROOT / "council" / "seat-map.yml")


@pytest.fixture(scope="module")
def teams() -> dict:
    return _load(ROOT / ".github" / "review-teams.yml")["teams"]


@pytest.fixture(scope="module")
def org():
    return build_organization()


# --- The derivation (record section 5, items 2 and 4, plus the review-loop fallback) ---


def _shared(seat_map: dict) -> dict[str, dict]:
    return {r["id"]: r for r in seat_map["shared_roles"]}


def _lowest_common_unit(org, units: list[str]) -> str:
    chains = [[u.id for u in org.ancestors(unit, include_self=True)] for unit in units]
    common = set(chains[0]).intersection(*chains[1:])
    return next(u for u in chains[0] if u in common)


def role_scope(org, role_id: str) -> str:
    """The unit a role answers for: its own unit, or for an executive the lowest common unit of what it heads or
    sponsors (not the executive office)."""
    role = org.roles[role_id]
    if not role.generated:
        units = [u.id for u in org.units.values() if (u.head_role == role_id or u.sponsor_role == role_id)
                 and u.kind is not UnitKind.OFFICE]
        if units:
            return _lowest_common_unit(org, units)
    return role.unit


def team_unit(org, seat_map: dict, team: dict) -> str:
    seats, shared = seat_map["seats"], _shared(seat_map)
    if any(seats[lead]["role"] in shared for lead in team["leads"]):
        return "shared"
    units = [role_scope(org, seats[lead]["role"]) for lead in team["leads"]]
    units += [cover for lead in team["leads"] for cover in seats[lead].get("covers", [])]
    return _lowest_common_unit(org, units)


def derive_key2(org, seat_map: dict, team: dict) -> str:
    """The nearest role above the team's unit held by a key-2 seat that holds no key 1 on the team; the chair when
    there is none, and when that role is the founder or reports to the founder."""
    unit = team_unit(org, seat_map, team)
    if unit == "shared":
        return "chair"  # a shared role reports to the founder: nothing in the chart sits above it
    holder = {s["role"]: name for name, s in seat_map["seats"].items()}
    head = org.head_of(unit)
    for role in [head, *org.line_chain(head.id)]:
        seat = holder.get(role.id)
        if seat in seat_map["key2_seats"] and seat not in team["leads"]:
            if role.id == BOARD or role.reports_to == BOARD:
                return "chair"
            return seat
    return "chair"


# --- The stored values match the derivation -----------------------------------------------


def test_every_team_stores_its_derived_unit_and_key2(org, seat_map, teams):
    stored = {tid: (t.get("unit"), t.get("key2")) for tid, t in teams.items()}
    derived = {tid: (team_unit(org, seat_map, t), derive_key2(org, seat_map, t)) for tid, t in teams.items()}
    assert stored == derived


def test_today_every_key2_is_the_chair(teams, seat_map):
    assert {t["key2"] for t in teams.values()} == {"chair"}
    assert seat_map["key2_seats"] == ["chair"]


def test_a_key2_seat_above_the_unit_is_derived(org, seat_map):
    fixture = {**seat_map, "key2_seats": ["chair", "eda-tooling"]}
    team = {"leads": ["ai-engineer"]}  # AI Platform reports to the Engineering Infrastructure VP
    assert team_unit(org, fixture, team) == "infrastructure.ai"
    assert derive_key2(org, fixture, team) == "eda-tooling"


def test_a_key1_holder_is_never_key2(org, seat_map):
    fixture = {**seat_map, "key2_seats": ["chair", "eda-tooling"]}
    assert derive_key2(org, fixture, {"leads": ["eda-tooling"]}) == "chair"


def test_a_derived_key2_that_reports_to_the_founder_is_the_chair(org, seat_map):
    # A seat on the CEO's role with a key-2 set would be derived for any engineering team; it reports to the
    # founder, so key 2 is the chair (review-loop record, pull request #123).
    seats = {**seat_map["seats"], "chair": {"role": "exec.cto"}, "stand-in": {"role": "exec.ceo"}}
    fixture = {**seat_map, "seats": seats, "key2_seats": ["stand-in"]}
    assert derive_key2(org, fixture, {"leads": ["design-architect"]}) == "chair"


def test_a_team_led_from_a_shared_role_is_shared_and_keeps_the_chair(org, seat_map, teams):
    assert team_unit(org, seat_map, teams["business"]) == "shared"
    assert derive_key2(org, {**seat_map, "key2_seats": ["chair", "finance-licensing"]}, teams["business"]) == "chair"


# --- The seat map itself (record section 6) --------------------------------------------------


def test_every_seat_file_maps_once(seat_map):
    files = {p.stem for p in (ROOT / "council").glob("*.md") if p.name != "README.md"}
    seats, unplaced = set(seat_map["seats"]), set(seat_map.get("unplaced", {}))
    assert not seats & unplaced
    assert seats | unplaced == files
    assert unplaced == {"founder-proxy"}  # its place in the chart is the founder's decision


def test_every_role_exists_once(org, seat_map):
    shared = _shared(seat_map)
    roles = [s["role"] for s in seat_map["seats"].values()]
    assert len(roles) == len(set(roles)), "a role holds two seats"
    for role in roles:
        assert role in org.roles or role in shared, role
    for role_id, role in shared.items():
        assert role_id not in org.roles and role["reports_to"] == FOUNDER


def test_legal_compliance_is_not_the_quality_compliance_practice(org, seat_map):
    role = seat_map["seats"]["legal-compliance"]["role"]
    assert role not in org.roles or not org.is_within(org.roles[role].unit, "quality.process.compliance")


def test_every_key1_lead_maps_to_a_head_role(org, seat_map, teams):
    seats, shared = seat_map["seats"], _shared(seat_map)
    for team in teams.values():
        for lead in team["leads"]:
            role = seats[lead]["role"]
            if role in shared:
                continue
            headed = [u.id for u in org.units.values() if org.head_of(u.id) and org.head_of(u.id).id == role]
            assert headed, f"{lead} holds key 1 but {role} heads no unit"


def test_covers_name_units(org, seat_map):
    for seat in seat_map["seats"].values():
        for unit in seat.get("covers", []):
            assert unit in org.units, unit


def test_every_deputy_shares_a_review_team(seat_map, teams):
    def teams_of(seat):
        return {tid for tid, t in teams.items() if seat in t["leads"] or seat in t["members"]}

    for name, seat in seat_map["seats"].items():
        deputy = seat.get("deputy")
        if deputy is None:
            continue
        if deputy == FOUNDER:
            assert name == "chair"  # above the chair is the founder
            continue
        assert deputy in seat_map["seats"] and deputy != name
        assert teams_of(name) & teams_of(deputy), (name, deputy)


def test_votes(seat_map):
    votes = {name: s["vote"] for name, s in seat_map["seats"].items()}
    assert votes.pop("chair") == "chairs"
    assert set(votes.values()) <= {"yes", "no"}


# --- Nothing that picks a reviewer reads the chart ------------------------------------------


@pytest.mark.parametrize("script", ["scripts/pr_review.py", "scripts/review_map.py", "scripts/pr_loop.py"])
def test_the_review_scripts_never_read_the_chart_or_the_seat_map(script):
    text = (ROOT / script).read_text(encoding="utf-8")
    for needle in ("org_chart", "build_organization", "nirmaan.company", "seat-map", "seat_map"):
        assert needle not in text, (script, needle)


def test_every_key2_floor_glob_matches_a_tracked_file():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    files = [p for p in out.decode().split("\0") if p]
    for glob in _load(ROOT / ".github" / "review-teams.yml")["key2_floor"]:
        assert any(review_map.matches(glob, path) for path in files), f"dead key-2 floor glob: {glob}"
