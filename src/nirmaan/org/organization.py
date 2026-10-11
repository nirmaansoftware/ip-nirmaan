"""The organization: a validated, immutable, queryable model of the company.

Built in two steps. A :class:`CompanyDefinition` is the declarative input
(units, skills, workflows, the constitution: plain data, JSON-exportable).
:class:`OrganizationBuilder` derives staffing from structure, applies
registered extensions, validates everything, and freezes the result into an
:class:`Organization`.

Staffing is derived, never hand-written per team: a division is headed by a
VP, a department by a director, a team by a manager with a tech lead, and every
leaf carries the individual-contributor ladder. Adding a department is
therefore adding one unit record; its roles, reporting lines, escalation
chain, skills, and tools follow from the rules below.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import MutableMapping
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from nirmaan.models import (
    AgentProfile,
    AssumptionRule,
    AuthorityRule,
    Capability,
    CapabilityKind,
    EscalationRoute,
    FeatureRule,
    GateSpec,
    IntentRule,
    Level,
    LevelProfile,
    OrgUnit,
    ParameterRule,
    Principle,
    Proficiency,
    Role,
    Skill,
    ToolRisk,
    ToolSpec,
    Track,
    UnitKind,
    UnitStatus,
    WorkflowTemplate,
)
from nirmaan.registry import Registry

#: The individual-contributor ladder every leaf unit carries unless it overrides.
DEFAULT_LADDER: tuple[Level, ...] = (Level.SENIOR, Level.ENGINEER, Level.JUNIOR, Level.INTERN)

#: Proficiency an individual contributor holds in inherited skills, by level.
_IC_PROFICIENCY = {
    Level.INTERN: Proficiency.AWARENESS,
    Level.JUNIOR: Proficiency.WORKING,
    Level.ENGINEER: Proficiency.PROFICIENT,
    Level.SENIOR: Proficiency.EXPERT,
    Level.TECH_LEAD: Proficiency.EXPERT,
    Level.STAFF: Proficiency.EXPERT,
}

_HEAD_LEVEL = {
    UnitKind.DIVISION: Level.VP,
    UnitKind.DEPARTMENT: Level.DIRECTOR,
    UnitKind.TEAM: Level.MANAGER,
}


class OrganizationError(ValueError):
    """The definition does not describe a coherent organization."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        preview = "\n  ".join(issues[:20])
        more = f"\n  ... and {len(issues) - 20} more" if len(issues) > 20 else ""
        super().__init__(f"{len(issues)} organization issue(s):\n  {preview}{more}")


class CompanyDefinition(BaseModel):
    """Everything that defines a company, as plain data."""

    name: str
    units: list[OrgUnit] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list, description="Explicit (non-derived) roles.")
    level_profiles: list[LevelProfile] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    workflows: list[WorkflowTemplate] = Field(default_factory=list)
    gates: list[GateSpec] = Field(default_factory=list)
    principles: list[Principle] = Field(default_factory=list)
    authority: list[AuthorityRule] = Field(default_factory=list)
    escalation: list[EscalationRoute] = Field(default_factory=list)
    intents: list[IntentRule] = Field(default_factory=list)
    features: list[FeatureRule] = Field(default_factory=list)
    parameters: list[ParameterRule] = Field(default_factory=list)
    assumptions: list[AssumptionRule] = Field(default_factory=list)
    agents: list[AgentProfile] = Field(
        default_factory=list, description="Explicit seats; every other role gets a default one."
    )


Extension = Callable[["OrganizationBuilder"], None]

_EXTENSIONS: MutableMapping[str, Extension] = Registry("org.extensions")


def register_extension(name: str) -> Callable[[Extension], Extension]:
    """Decorator: a function that adds units, skills, workflows, or policies.

    Registered extensions are applied by :meth:`OrganizationBuilder.build` to
    every organization built with ``extensions=True`` (the default), which is
    how a new engineering domain plugs in without editing the company core.
    """

    def _register(fn: Extension) -> Extension:
        if name in _EXTENSIONS and _EXTENSIONS[name] is not fn:
            raise ValueError(f"Organization extension {name!r} is already registered")
        _EXTENSIONS[name] = fn
        return fn

    return _register


def unregister_extension(name: str) -> None:
    _EXTENSIONS.pop(name, None)


def available_extensions() -> list[str]:
    return sorted(_EXTENSIONS)


class OrganizationBuilder:
    """Collects a definition, applies extensions, derives staffing, validates."""

    def __init__(self, definition: CompanyDefinition) -> None:
        self.definition = definition.model_copy(deep=True)

    # --- Adding things (used by extensions and JSON overlays) -----------------

    _LISTS = {
        OrgUnit: "units",
        Role: "roles",
        LevelProfile: "level_profiles",
        Skill: "skills",
        Capability: "capabilities",
        ToolSpec: "tools",
        WorkflowTemplate: "workflows",
        GateSpec: "gates",
        Principle: "principles",
        AuthorityRule: "authority",
        EscalationRoute: "escalation",
        IntentRule: "intents",
        FeatureRule: "features",
        ParameterRule: "parameters",
        AssumptionRule: "assumptions",
        AgentProfile: "agents",
    }

    def add(self, *items: BaseModel) -> "OrganizationBuilder":
        for item in items:
            field = self._LISTS.get(type(item))
            if field is None:
                raise TypeError(f"Cannot add {type(item).__name__} to an organization")
            getattr(self.definition, field).append(item)
        return self

    def load_json(self, path: Path) -> "OrganizationBuilder":
        """Overlay a JSON file shaped like a (partial) CompanyDefinition."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        overlay = CompanyDefinition.model_validate({"name": self.definition.name, **data})
        for field in self._LISTS.values():
            getattr(self.definition, field).extend(getattr(overlay, field))
        return self

    # --- Building --------------------------------------------------------------

    def build(self, extensions: bool = True, validate: bool = True) -> "Organization":
        if extensions:
            for name in sorted(_EXTENSIONS):
                _EXTENSIONS[name](self)
        org = Organization(self.definition, _derive_roles(self.definition))
        if validate:
            from nirmaan.org.validate import validate_organization

            issues = validate_organization(org)
            if issues:
                raise OrganizationError(issues)
        return org


# --- Staffing derivation --------------------------------------------------------


def _derive_roles(definition: CompanyDefinition) -> dict[str, Role]:
    units = {u.id: u for u in definition.units}
    children: dict[str, list[str]] = {}
    for unit in definition.units:
        if unit.parent:
            children.setdefault(unit.parent, []).append(unit.id)
    profiles = {p.level: p for p in definition.level_profiles}
    roles: dict[str, Role] = {r.id: r for r in definition.roles}

    def ancestors_or_self(unit_id: str) -> list[OrgUnit]:
        chain, seen, current = [], set(), unit_id
        while current and current in units and current not in seen:
            seen.add(current)
            chain.append(units[current])
            current = units[current].parent
        return chain

    def inherited(unit_id: str, attr: str) -> list[str]:
        values: list[str] = []
        for unit in reversed(ancestors_or_self(unit_id)):
            values.extend(v for v in getattr(unit, attr) if v not in values)
        return values

    head: dict[str, str] = {}
    lead: dict[str, str] = {}
    for unit in _topological(definition.units):
        if unit.head_role:
            head[unit.id] = unit.head_role
        elif unit.kind in _HEAD_LEVEL:
            head[unit.id] = f"{unit.id}.{_HEAD_LEVEL[unit.kind].value}"
        if unit.kind is UnitKind.TEAM and unit.status is UnitStatus.ACTIVE:
            lead[unit.id] = f"{unit.id}.{Level.TECH_LEAD.value}"

    def nearest(unit_id: str | None, table: dict[str, str], skip_self: bool = False) -> str | None:
        chain = ancestors_or_self(unit_id) if unit_id else []
        for unit in chain[1:] if skip_self else chain:
            if unit.id in table:
                return table[unit.id]
        return None

    def make(unit: OrgUnit, level: Level, title: str, reports_to: str | None, escalates_to: str | None) -> Role:
        profile = profiles.get(level)
        skills = inherited(unit.id, "skills")
        tools = inherited(unit.id, "tools")
        responsibilities: tuple[str, ...] = ()
        extra_caps: tuple[str, ...] = ()
        if profile:
            skills += [s for s in profile.skills if s not in skills]
            tools += [t for t in profile.tools if t not in tools]
            responsibilities = tuple(r.replace("{unit}", unit.name) for r in profile.responsibilities)
            extra_caps = profile.capabilities
        return Role(
            id=f"{unit.id}.{level.value}",
            title=title,
            unit=unit.id,
            level=level,
            reports_to=reports_to,
            escalates_to=escalates_to or reports_to,
            skills=tuple(skills),
            extra_capabilities=extra_caps,
            tools=tuple(tools),
            responsibilities=responsibilities,
        )

    for unit in _topological(definition.units):
        noun = unit.noun or f"{unit.name} Engineer"
        above = unit.sponsor_role or nearest(unit.parent, head)
        # Unit head.
        if not unit.head_role and unit.kind in _HEAD_LEVEL:
            level = _HEAD_LEVEL[unit.kind]
            title = {
                Level.VP: f"VP, {unit.name}",
                Level.DIRECTOR: f"Director, {unit.name}",
                Level.MANAGER: f"{unit.name} Manager",
            }[level]
            role = make(unit, level, title, above, None)
            roles.setdefault(role.id, role)
        if unit.status is UnitStatus.PLACEHOLDER:
            continue
        own_head = head.get(unit.id) or above
        # Tech lead.
        if unit.kind is UnitKind.TEAM:
            role = make(unit, Level.TECH_LEAD, f"{unit.name} Tech Lead", own_head, own_head)
            roles.setdefault(role.id, role)
        # Leaf individual-contributor ladder, escalating one rung at a time.
        if unit.id not in children and unit.kind in (UnitKind.TEAM, UnitKind.PRACTICE, UnitKind.DEPARTMENT):
            # A ladder override applies to the whole subtree below the unit declaring it.
            declared = next((u.ladder for u in ancestors_or_self(unit.id) if u.ladder is not None), None)
            ladder = sorted(declared if declared is not None else DEFAULT_LADDER, key=lambda l: -l.rank)
            team_lead = nearest(unit.id, lead)
            manager = nearest(unit.id, head) or above
            previous: str | None = None
            for level in ladder:
                # The top rung escalates to the team's tech lead when the lead is
                # senior to it, else straight to the manager (a staff engineer
                # never escalates down to a tech lead).
                top_target = (
                    team_lead if team_lead and Level.TECH_LEAD.rank > level.rank else manager
                )
                title = {
                    Level.STAFF: f"Staff {noun}",
                    Level.SENIOR: f"Senior {noun}",
                    Level.ENGINEER: noun,
                    Level.JUNIOR: f"Junior {noun}",
                    Level.INTERN: f"{noun} Intern",
                }.get(level, f"{level.display_name} {noun}")
                role = make(unit, level, title, manager, previous or top_target)
                roles.setdefault(role.id, role)
                previous = role.id
    return roles


def _topological(units: Iterable[OrgUnit]) -> list[OrgUnit]:
    """Parents before children, siblings in declaration order."""
    units = list(units)
    by_id = {u.id: u for u in units}
    placed: set[str] = set()
    ordered: list[OrgUnit] = []

    def place(unit: OrgUnit, trail: frozenset[str]) -> None:
        if unit.id in placed or unit.id in trail:
            return
        if unit.parent in by_id:
            place(by_id[unit.parent], trail | {unit.id})
        placed.add(unit.id)
        ordered.append(unit)

    for unit in units:
        place(unit, frozenset())
    return ordered


# --- The organization -----------------------------------------------------------


class Organization:
    """Immutable after build. Every question about the company is a lookup here."""

    def __init__(self, definition: CompanyDefinition, roles: dict[str, Role]) -> None:
        self._definition = definition
        self.name = definition.name
        self.units: dict[str, OrgUnit] = {u.id: u for u in definition.units}
        self.roles: dict[str, Role] = dict(sorted(roles.items()))
        self.skills: dict[str, Skill] = {s.id: s for s in definition.skills}
        self.capabilities: dict[str, Capability] = {c.id: c for c in definition.capabilities}
        self.tools: dict[str, ToolSpec] = {t.id: t for t in definition.tools}
        self.workflows: dict[str, WorkflowTemplate] = {w.id: w for w in definition.workflows}
        self.gates: dict[str, GateSpec] = {g.id: g for g in definition.gates}
        self.principles: dict[str, Principle] = {p.id: p for p in definition.principles}
        self.level_profiles: dict[Level, LevelProfile] = {p.level: p for p in definition.level_profiles}
        self.authority: dict[tuple[str, str], AuthorityRule] = {
            (r.decision.value, r.criticality.value): r for r in definition.authority
        }
        self.escalation: dict[str, EscalationRoute] = {r.kind.value: r for r in definition.escalation}
        self.intents = list(definition.intents)
        self.features = list(definition.features)
        self.parameters = list(definition.parameters)
        self.assumptions = list(definition.assumptions)
        self._children: dict[str, list[str]] = {}
        for unit in definition.units:
            if unit.parent:
                self._children.setdefault(unit.parent, []).append(unit.id)
        explicit = {a.role: a for a in definition.agents}
        self.agents: dict[str, AgentProfile] = {}
        for role in self.roles.values():
            agent = explicit.get(role.id) or AgentProfile(
                id=f"agent:{role.id}", name=role.title, role=role.id
            )
            self.agents[agent.id] = agent
        self._duplicates = _duplicates(definition)
        # Immutable after construction, so derived answers are memoized.
        self._skill_cache: dict[str, list[str]] = {}
        self._cap_cache: dict[str, dict[str, str]] = {}
        self._tool_cache: dict[str, list[str]] = {}

    # --- Definition -------------------------------------------------------------

    @property
    def definition(self) -> CompanyDefinition:
        return self._definition.model_copy(deep=True)

    @property
    def duplicate_ids(self) -> list[str]:
        return list(self._duplicates)

    @cached_property
    def fingerprint(self) -> str:
        """Content digest of the whole organization, derived roles included."""
        payload = json.dumps(self.export(), sort_keys=True, separators=(",", ":"), default=str)
        return "org-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def export(self) -> dict[str, Any]:
        """The machine-readable company: definition plus derived staffing."""
        data = self._definition.model_dump(mode="json")
        data["roles"] = [r.model_dump(mode="json") for r in self.roles.values()]
        return data

    # --- Chart --------------------------------------------------------------------

    @cached_property
    def root(self) -> OrgUnit:
        return next(u for u in self.units.values() if u.parent is None)

    def children(self, unit_id: str) -> list[OrgUnit]:
        return [self.units[c] for c in self._children.get(unit_id, [])]

    def ancestors(self, unit_id: str, include_self: bool = False) -> list[OrgUnit]:
        chain: list[OrgUnit] = []
        seen = {unit_id}
        current = unit_id if include_self else self.units[unit_id].parent
        while current is not None and current in self.units:
            chain.append(self.units[current])
            current = self.units[current].parent
            if current in seen:
                break  # a cycle: validation reports it; queries must still terminate
            seen.add(current)
        return chain

    def subtree(self, unit_id: str) -> list[OrgUnit]:
        found, frontier = [], [unit_id]
        while frontier:
            current = frontier.pop(0)
            found.append(self.units[current])
            frontier.extend(self._children.get(current, []))
        return found

    def is_within(self, unit_id: str, ancestor_id: str) -> bool:
        return any(u.id == ancestor_id for u in self.ancestors(unit_id, include_self=True))

    def division_of(self, unit_id: str) -> OrgUnit:
        """The top-level branch of the company a unit belongs to."""
        chain = self.ancestors(unit_id, include_self=True)
        return chain[-2] if len(chain) >= 2 else self.root

    def roles_in(self, unit_id: str, recursive: bool = True) -> list[Role]:
        units = {u.id for u in self.subtree(unit_id)} if recursive else {unit_id}
        return [r for r in self.roles.values() if r.unit in units]

    def head_of(self, unit_id: str) -> Role | None:
        unit = self.units[unit_id]
        if unit.head_role:
            return self.roles.get(unit.head_role)
        level = _HEAD_LEVEL.get(unit.kind)
        return self.roles.get(f"{unit_id}.{level.value}") if level else None

    def lead_of(self, unit_id: str) -> Role | None:
        return self.roles.get(f"{unit_id}.{Level.TECH_LEAD.value}")

    def line_chain(self, role_id: str) -> list[Role]:
        """reports_to, all the way up. Excludes the role itself."""
        return self._walk(role_id, "reports_to")

    def escalation_chain(self, role_id: str) -> list[Role]:
        """escalates_to, all the way up. Excludes the role itself."""
        return self._walk(role_id, "escalates_to")

    def _walk(self, role_id: str, attr: str) -> list[Role]:
        chain: list[Role] = []
        seen = {role_id}
        current = getattr(self.roles[role_id], attr)
        while current and current not in seen and current in self.roles:
            seen.add(current)
            chain.append(self.roles[current])
            current = getattr(self.roles[current], attr)
        return chain

    def authority_domain(self, role_id: str) -> str:
        """The unit subtree a role is responsible for."""
        role = self.roles[role_id]
        if role.level.track is Track.EXECUTIVE:
            return self.root.id
        return role.unit

    # --- Skills and capabilities ------------------------------------------------

    def effective_skills(self, role_id: str) -> list[str]:
        """Held skills plus everything they compose, in stable order."""
        if role_id in self._skill_cache:
            return list(self._skill_cache[role_id])
        found: list[str] = []
        frontier = list(self.roles[role_id].skills)
        while frontier:
            skill_id = frontier.pop(0)
            if skill_id in found or skill_id not in self.skills:
                continue
            found.append(skill_id)
            frontier.extend(self.skills[skill_id].includes)
        self._skill_cache[role_id] = found
        return list(found)

    def proficiency(self, role_id: str, skill_id: str) -> Proficiency | None:
        role = self.roles[role_id]
        if skill_id not in self.effective_skills(role_id):
            return None
        profile = self.level_profiles.get(role.level)
        if profile and skill_id in self._closure(profile.skills):
            return Proficiency.EXPERT
        if role.level.track is Track.INDIVIDUAL:
            return _IC_PROFICIENCY[role.level]
        return Proficiency.PROFICIENT

    def _closure(self, skill_ids: Iterable[str]) -> set[str]:
        found: set[str] = set()
        frontier = list(skill_ids)
        while frontier:
            current = frontier.pop()
            if current in found or current not in self.skills:
                continue
            found.add(current)
            frontier.extend(self.skills[current].includes)
        return found

    def capabilities_of(self, role_id: str) -> dict[str, str]:
        """Capability ID -> the skill (or grant) it comes from."""
        if role_id in self._cap_cache:
            return dict(self._cap_cache[role_id])
        role = self.roles[role_id]
        held: dict[str, str] = {}
        for skill_id in self.effective_skills(role_id):
            prof = self.proficiency(role_id, skill_id)
            for cap_id in self.skills[skill_id].provides:
                cap = self.capabilities.get(cap_id)
                if (
                    cap
                    and prof is not None
                    and prof.rank >= cap.min_proficiency.rank
                    and (cap.min_level is None or role.level.at_least(cap.min_level))
                ):
                    held.setdefault(cap_id, f"skill:{skill_id}")
        for cap_id in role.extra_capabilities:
            held.setdefault(cap_id, f"level:{role.level.value}")
        self._cap_cache[role_id] = dict(sorted(held.items()))
        return dict(self._cap_cache[role_id])

    def holds(self, role_id: str, capability_id: str) -> bool:
        return capability_id in self.capabilities_of(role_id)

    def roles_with(self, capability_id: str) -> list[Role]:
        return [r for r in self.roles.values() if self.holds(r.id, capability_id)]

    def tools_of(self, role_id: str) -> list[str]:
        """Granted tools: the role's own, plus those its skills use (capability-based).

        Read tools come with any holding of a skill; write, execute, and approve
        tools need at least WORKING proficiency, so an intern reads but does not run.
        """
        if role_id in self._tool_cache:
            return list(self._tool_cache[role_id])
        granted = list(self.roles[role_id].tools)
        for skill_id in self.effective_skills(role_id):
            prof = self.proficiency(role_id, skill_id)
            for tool_id in self.skills[skill_id].tools:
                tool = self.tools.get(tool_id)
                if tool is None or tool_id in granted:
                    continue
                if tool.risk is ToolRisk.READ or (prof and prof.rank >= Proficiency.WORKING.rank):
                    granted.append(tool_id)
        self._tool_cache[role_id] = granted
        return list(granted)

    def providers_of(self, capability_id: str) -> list[Skill]:
        return [s for s in self.skills.values() if capability_id in s.provides]

    def is_active(self, role_id: str) -> bool:
        unit = self.units.get(self.roles[role_id].unit)
        return unit is not None and all(
            u.status is UnitStatus.ACTIVE for u in self.ancestors(unit.id, include_self=True)
        )

    # --- Agent cards ----------------------------------------------------------------

    def agent_card(self, role_id: str) -> dict[str, Any]:
        """The spec's agent metadata, entirely derived from the role."""
        role = self.roles[role_id]
        caps = self.capabilities_of(role_id)
        agent = next((a for a in self.agents.values() if a.role == role_id), None)
        produces = sorted({k for c in caps for k in self.capabilities[c].produces})
        return {
            "id": agent.id if agent else f"agent:{role_id}",
            "name": role.title,
            "kind": agent.kind.value if agent else "ai_agent",
            "runtime": agent.runtime if agent else "unbound",
            "role": role.id,
            "level": role.level.value,
            "department": role.unit,
            "division": self.division_of(role.unit).id,
            "manager": role.reports_to,
            "skills": {s: self.proficiency(role_id, s).value for s in self.effective_skills(role_id)},
            "capabilities": caps,
            "responsibilities": list(role.responsibilities),
            "authority": [
                {"decision": r.decision.value, "criticality": r.criticality.value}
                for r in self.authority.values()
                if role.level.at_least(r.min_level)
            ],
            "inputs": ["requirement", "task_context", "upstream_artifacts", "scoped_knowledge"],
            "outputs": produces,
            "tools": self.tools_of(role_id),
            "policies": sorted(self.principles),
            "review_requirements": sorted(
                c for c in caps if self.capabilities[c].kind is CapabilityKind.REVIEW
            ),
            "escalation_targets": [r.id for r in self.escalation_chain(role_id)],
            "quality_gates": sorted(
                g.id for g in self.gates.values() if g.approver_capability in caps
                and role.level.at_least(g.min_level)
            ),
        }

    # --- Counting ----------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        active = [r for r in self.roles.values() if self.is_active(r.id)]
        return {
            "units": len(self.units),
            "divisions": sum(1 for u in self.units.values() if u.kind is UnitKind.DIVISION),
            "departments": sum(1 for u in self.units.values() if u.kind is UnitKind.DEPARTMENT),
            "teams": sum(1 for u in self.units.values() if u.kind is UnitKind.TEAM),
            "practices": sum(1 for u in self.units.values() if u.kind is UnitKind.PRACTICE),
            "roles": len(self.roles),
            "active_roles": len(active),
            "skills": len(self.skills),
            "capabilities": len(self.capabilities),
            "tools": len(self.tools),
            "workflows": len(self.workflows),
            "gates": len(self.gates),
            "principles": len(self.principles),
        }


def _duplicates(definition: CompanyDefinition) -> list[str]:
    found: list[str] = []
    for field in OrganizationBuilder._LISTS.values():
        seen: set[str] = set()
        for item in getattr(definition, field):
            key = getattr(item, "id", None) or getattr(item, "feature", None) or getattr(
                item, "name", None
            )
            if field == "level_profiles":
                key = item.level.value
            elif field == "authority":
                key = f"{item.decision.value}/{item.criticality.value}"
            elif field == "escalation":
                key = item.kind.value
            elif field == "intents":
                key = f"{item.intent}/{'|'.join(item.patterns)}"
            if key is None:
                continue
            if key in seen:
                found.append(f"{field}:{key}")
            seen.add(key)
    return found
