"""Milestone 19, Phase 1: the organizational foundation of IP Nirmaan.

Covers the organization as data: the hierarchy exists and is whole, staffing
is derived from structure, chains of command and escalation terminate and rise
in seniority, capabilities are inherited through skills (never copied), signoff
needs seniority as well as skill, and validation turns an incoherent company
into a build error rather than a planning surprise.
"""

from __future__ import annotations

import json

import pytest

from nirmaan.company import builder, nirmaan_definition
from nirmaan.models import (
    Capability,
    CapabilityKind,
    Function,
    Level,
    OrgUnit,
    Proficiency,
    Skill,
    Track,
    UnitKind,
    UnitStatus,
)
from nirmaan.org import OrganizationBuilder, OrganizationError


# --- Hierarchy -------------------------------------------------------------------


def test_the_company_builds_and_validates(nirmaan_org):
    stats = nirmaan_org.stats()
    assert nirmaan_org.name == "IP Nirmaan"
    assert stats["divisions"] >= 15
    assert stats["roles"] >= 600
    assert stats["skills"] >= 120
    assert stats["workflows"] >= 7
    assert stats["principles"] == 12


@pytest.mark.parametrize(
    "role",
    ["exec.board", "exec.ceo", "exec.cto", "exec.coo", "exec.chief_architect", "exec.cpo",
     "exec.chief_of_staff", "design.vp", "verification.vp"],
)
def test_the_executive_layer_exists(nirmaan_org, role):
    assert role in nirmaan_org.roles


@pytest.mark.parametrize(
    "unit",
    [
        "product.management.requirements", "product.programs.tpm", "product.projects.status",
        "architecture.system.interconnect", "architecture.micro.noc", "architecture.interface.axi",
        "architecture.interface.cxl", "design.rtl.design.fsm", "design.rtl.cdc", "design.rtl.quality.lint",
        "verification.simulation.uvm", "verification.formal.equivalence", "verification.coverage.functional",
        "verification.debug.triage", "verification.signoff", "implementation.pd.sta.mcmm",
        "implementation.pd.power.ir", "implementation.pd.signoff.lvs", "implementation.dft.engineering.atpg",
        "software.firmware.boot", "software.tools.compiler", "security.secure_boot",
        "infrastructure.build.ci", "documentation.writing.registers", "quality.engineering.traceability",
    ],
)
def test_every_specified_domain_is_a_unit(nirmaan_org, unit):
    assert unit in nirmaan_org.units


@pytest.mark.parametrize("unit", ["finance", "legal", "hr", "procurement", "sales", "marketing",
                                  "customer_success", "partnerships", "operations"])
def test_business_functions_are_structural_placeholders(nirmaan_org, unit):
    u = nirmaan_org.units[unit]
    assert u.function is Function.BUSINESS and u.status is UnitStatus.PLACEHOLDER
    # A placeholder has a head (the company is whole) but no engineering staff.
    assert [r.level for r in nirmaan_org.roles_in(unit)] == [Level.VP]
    assert not any(nirmaan_org.is_active(r.id) for r in nirmaan_org.roles_in(unit))


def test_one_root_and_no_orphans(nirmaan_org):
    roots = [u for u in nirmaan_org.units.values() if u.parent is None]
    assert [u.id for u in roots] == ["nirmaan"]
    for unit in nirmaan_org.units.values():
        assert nirmaan_org.ancestors(unit.id, include_self=True)[-1].id == "nirmaan"


# --- Derived staffing ------------------------------------------------------------------


def test_staffing_is_derived_from_unit_kind(nirmaan_org):
    org = nirmaan_org
    assert org.head_of("verification").level is Level.VP
    assert org.head_of("design.rtl").level is Level.DIRECTOR
    assert org.head_of("verification.debug").level is Level.MANAGER
    assert org.lead_of("verification.debug").level is Level.TECH_LEAD
    ladder = sorted((r.level for r in org.roles_in("verification.debug.triage", recursive=False)),
                    key=lambda level: level.rank)
    assert ladder == [Level.INTERN, Level.JUNIOR, Level.ENGINEER, Level.SENIOR]


def test_ladder_overrides_inherit_down_the_subtree(nirmaan_org):
    levels = {r.level for r in nirmaan_org.roles_in("architecture.system.ip", recursive=False)}
    assert levels == {Level.STAFF, Level.SENIOR, Level.ENGINEER}


@pytest.mark.parametrize("level", [Level.VP, Level.DIRECTOR, Level.MANAGER, Level.STAFF, Level.TECH_LEAD,
                                   Level.SENIOR, Level.ENGINEER, Level.JUNIOR, Level.INTERN])
def test_every_role_level_is_staffed_somewhere(nirmaan_org, level):
    assert any(r.level is level for r in nirmaan_org.roles.values())


def test_the_escalation_chain_matches_the_spec(nirmaan_org):
    chain = [r.level for r in nirmaan_org.escalation_chain("design.rtl.design.interconnect.intern")]
    assert chain[:8] == [Level.JUNIOR, Level.ENGINEER, Level.SENIOR, Level.TECH_LEAD, Level.MANAGER,
                         Level.DIRECTOR, Level.VP, Level.EXECUTIVE]
    assert nirmaan_org.escalation_chain("design.rtl.design.interconnect.intern")[7].id == "exec.cto"


def test_every_chain_rises_strictly_and_terminates_at_the_board(nirmaan_org):
    for role in nirmaan_org.roles.values():
        for chain in (nirmaan_org.line_chain(role.id), nirmaan_org.escalation_chain(role.id)):
            ranks = [role.level.rank, *(r.level.rank for r in chain)]
            assert ranks == sorted(set(ranks)), role.id
            if role.id != "exec.board":
                assert chain[-1].id == "exec.board", role.id


def test_staff_never_escalates_down_to_a_tech_lead(nirmaan_org):
    staff = nirmaan_org.roles["verification.architecture.staff"]
    assert nirmaan_org.roles[staff.escalates_to].level.rank > staff.level.rank


def test_managers_are_on_the_management_track(nirmaan_org):
    assert nirmaan_org.roles["verification.debug.manager"].track is Track.MANAGEMENT
    assert nirmaan_org.roles["verification.debug.tech_lead"].track is Track.INDIVIDUAL


# --- Skills and capabilities --------------------------------------------------------------


def test_capabilities_are_inherited_through_unit_skills(nirmaan_org):
    # rtl_design is an RTL Engineering baseline skill, not a practice skill, yet
    # every practice below inherits the capability it provides.
    role = "design.rtl.design.fsm.senior"
    assert "rtl_design" not in nirmaan_org.units["design.rtl.design.fsm"].skills
    assert nirmaan_org.holds(role, "rtl.implement")
    assert nirmaan_org.capabilities_of(role)["rtl.implement"] == "skill:rtl_design"


def test_skills_compose_through_includes(nirmaan_org):
    skills = nirmaan_org.effective_skills("design.rtl.design.interconnect.senior")
    for composed in ("rtl_design", "systemverilog", "arbitration", "buffering_flow_control", "noc_protocol"):
        assert composed in skills


def test_proficiency_is_derived_from_level(nirmaan_org):
    p = nirmaan_org.proficiency
    assert p("verification.debug.triage.intern", "failure_triage") is Proficiency.AWARENESS
    assert p("verification.debug.triage.junior", "failure_triage") is Proficiency.WORKING
    assert p("verification.debug.triage.engineer", "failure_triage") is Proficiency.PROFICIENT
    assert p("verification.debug.triage.senior", "failure_triage") is Proficiency.EXPERT
    # A manager holds inherited domain skills, but not at expert depth.
    assert p("verification.debug.manager", "debugging") is Proficiency.PROFICIENT
    # Level-granted skills are the level's core competence.
    assert p("verification.debug.manager", "engineering_management") is Proficiency.EXPERT


def test_review_capabilities_need_expertise(nirmaan_org):
    assert nirmaan_org.holds("design.rtl.design.control.senior", "rtl.review")
    assert not nirmaan_org.holds("design.rtl.design.control.engineer", "rtl.review")
    assert nirmaan_org.holds("design.rtl.design.control.engineer", "rtl.implement")
    assert not nirmaan_org.holds("design.rtl.design.control.intern", "rtl.implement")


def test_signoff_needs_seniority_not_just_skill(nirmaan_org):
    # Everyone in Verification holds the signoff skill; only directors and up sign off.
    assert "verification_signoff" in nirmaan_org.effective_skills("verification.simulation.uvm.senior")
    assert not nirmaan_org.holds("verification.simulation.uvm.senior", "signoff.verification")
    assert nirmaan_org.holds("verification.vp", "signoff.verification")


def test_skills_are_never_duplicated_into_roles(nirmaan_org):
    for role in nirmaan_org.roles.values():
        assert len(role.skills) == len(set(role.skills)), role.id
    assert all(isinstance(s, str) for r in nirmaan_org.roles.values() for s in r.skills)


def test_every_capability_is_performable(nirmaan_org):
    for cap in nirmaan_org.capabilities.values():
        assert any(nirmaan_org.is_active(r.id) for r in nirmaan_org.roles_with(cap.id)), cap.id


def test_skills_reuse_veritriage_knowledge_packs(nirmaan_org):
    from nirmaan.integrations.veritriage import missing_packs

    cited = {s.ref for sk in nirmaan_org.skills.values() for s in sk.knowledge_sources
             if s.kind.value == "veritriage_pack"}
    assert {"axi", "noc", "uvm", "sva", "cdc", "formal", "dft", "coverage"} <= cited
    assert missing_packs(nirmaan_org) == []


# --- Agent cards ----------------------------------------------------------------------------


def test_agent_cards_carry_the_specified_metadata(nirmaan_org):
    card = nirmaan_org.agent_card("design.rtl.design.interconnect.senior")
    for key in ("id", "name", "role", "department", "manager", "skills", "responsibilities", "authority",
                "inputs", "outputs", "tools", "policies", "review_requirements", "escalation_targets",
                "quality_gates"):
        assert key in card
    assert "rtl.review" in card["review_requirements"]
    assert card["runtime"] == "unbound"
    assert "git.write" in card["tools"] and "approval.grant" not in card["tools"]


def test_tools_are_granted_by_capability_not_to_everyone(nirmaan_org):
    tools = nirmaan_org.tools_of
    assert "veritriage.investigate" in tools("verification.debug.triage.engineer")
    assert "veritriage.investigate" not in tools("product.management.roadmap.engineer")
    # Tools follow skills: RTL designers may run the simulator; interns only read.
    assert "simulator.run" in tools("design.rtl.design.fsm.engineer")
    assert "simulator.run" not in tools("design.rtl.design.fsm.intern")
    assert "git.read" in tools("design.rtl.design.fsm.intern")
    assert "task.assign" in tools("verification.debug.manager")
    assert "task.assign" not in tools("verification.debug.triage.engineer")
    assert "approval.grant" in tools("verification.debug.tech_lead")


# --- Export and determinism --------------------------------------------------------------


def test_the_organization_is_machine_readable_and_deterministic(nirmaan_org):
    exported = nirmaan_org.export()
    assert json.loads(json.dumps(exported)) == exported
    assert len(exported["roles"]) == len(nirmaan_org.roles)
    assert builder().build().fingerprint == nirmaan_org.fingerprint


def test_a_json_overlay_extends_the_company_without_code(tmp_path):
    overlay = {
        "units": [OrgUnit(id="verification.debug.ml", name="ML Triage", kind=UnitKind.PRACTICE,
                          function=Function.ENGINEERING, parent="verification.debug", noun="ML Triage Engineer",
                          skills=("failure_triage",)).model_dump(mode="json")],
    }
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(overlay), encoding="utf-8")
    org = builder().load_json(path).build()
    assert "verification.debug.ml.senior" in org.roles
    assert org.holds("verification.debug.ml.engineer", "debug.triage")


# --- Validation catches incoherent companies ---------------------------------------------


def _issues(mutate) -> list[str]:
    definition = nirmaan_definition()
    mutate(definition)
    with pytest.raises(OrganizationError) as err:
        OrganizationBuilder(definition).build(extensions=False)
    return err.value.issues


def test_validation_rejects_an_unknown_skill():
    def mutate(d):
        d.units[5] = d.units[5].model_copy(update={"skills": ("no_such_skill",)})

    assert any("unknown skill no_such_skill" in i for i in _issues(mutate))


def test_validation_rejects_a_parent_cycle():
    def mutate(d):
        units = {u.id: u for u in d.units}
        d.units[d.units.index(units["design"])] = units["design"].model_copy(update={"parent": "design.rtl"})

    assert any("cycle" in i or "root" in i for i in _issues(mutate))


def test_validation_rejects_an_incomplete_authority_matrix():
    def mutate(d):
        d.authority.pop()

    assert any("authority matrix" in i for i in _issues(mutate))


def test_validation_rejects_a_stage_nobody_can_own():
    def mutate(d):
        d.capabilities.append(Capability(id="quantum.entangle", name="Entangle", kind=CapabilityKind.EXECUTION,
                                         description="Nobody can do this."))
        d.skills.append(Skill(id="quantum", name="Quantum", domain="x", provides=("quantum.entangle",),
                              validation_criteria=("n/a",)))
        wf = d.workflows[0]
        stage = wf.stages[0].model_copy(update={"id": "entangle", "capability": "quantum.entangle"})
        d.workflows[0] = wf.model_copy(update={"stages": (*wf.stages, stage)})

    issues = _issues(mutate)
    assert any("no active role holds quantum.entangle" in i for i in issues)


def test_validation_requires_review_on_critical_work():
    def mutate(d):
        wf = d.workflows[0]
        stages = tuple(s.model_copy(update={"review": None}) if s.id == "microarchitecture" else s
                       for s in wf.stages)
        d.workflows[0] = wf.model_copy(update={"stages": stages})

    assert any("must declare an independent review (P6)" in i for i in _issues(mutate))


def test_validation_rejects_bare_claims_as_evidence():
    from nirmaan.models import EvidenceKind, EvidenceRequirement

    def mutate(d):
        wf = d.workflows[0]
        bad = EvidenceRequirement(description="trust me", accepts=(EvidenceKind.CLAIM,))
        stages = (wf.stages[0].model_copy(update={"evidence": (bad,)}), *wf.stages[1:])
        d.workflows[0] = wf.model_copy(update={"stages": stages})

    assert any("bare claim" in i for i in _issues(mutate))
