"""Organizational vocabulary: units, levels, roles, skills, capabilities, tools.

Plain, frozen data. Nothing here imports an engine, a registry, or VeriTriage,
which is what lets the organization exist independently of any LLM: a role is
a record of responsibility and authority, not a prompt.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Function(str, Enum):
    """Which part of the company a unit belongs to."""

    EXECUTIVE = "executive"
    PRODUCT = "product"
    ENGINEERING = "engineering"
    QUALITY = "quality"
    INFRASTRUCTURE = "infrastructure"
    BUSINESS = "business"


class UnitKind(str, Enum):
    """Structural depth of an organizational unit.

    Staffing is derived from the kind, so a new unit needs no role written by
    hand: a division gets a VP, a department a director, a team a manager and a
    tech lead, and every leaf gets the individual-contributor ladder.
    """

    COMPANY = "company"
    OFFICE = "office"
    DIVISION = "division"
    DEPARTMENT = "department"
    TEAM = "team"
    PRACTICE = "practice"


class UnitStatus(str, Enum):
    ACTIVE = "active"
    #: Declared so the company is structurally whole (finance, legal, sales),
    #: but not staffed for engineering work yet.
    PLACEHOLDER = "placeholder"


class Track(str, Enum):
    INDIVIDUAL = "individual"
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


class Level(str, Enum):
    """The role ladder. ``rank`` is the only thing authority ever compares."""

    INTERN = "intern"
    JUNIOR = "junior"
    ENGINEER = "engineer"
    SENIOR = "senior"
    TECH_LEAD = "tech_lead"
    STAFF = "staff"
    MANAGER = "manager"
    SENIOR_MANAGER = "senior_manager"
    DIRECTOR = "director"
    VP = "vp"
    EXECUTIVE = "executive"
    CEO = "ceo"
    BOARD = "board"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @property
    def track(self) -> Track:
        if self in (Level.EXECUTIVE, Level.CEO, Level.BOARD):
            return Track.EXECUTIVE
        if self in (Level.MANAGER, Level.SENIOR_MANAGER, Level.DIRECTOR, Level.VP):
            return Track.MANAGEMENT
        return Track.INDIVIDUAL

    @property
    def display_name(self) -> str:
        return _DISPLAY[self]

    def at_least(self, other: "Level") -> bool:
        return self.rank >= other.rank


_RANK = {
    Level.INTERN: 10,
    Level.JUNIOR: 20,
    Level.ENGINEER: 30,
    Level.SENIOR: 40,
    Level.TECH_LEAD: 50,
    Level.STAFF: 55,
    Level.MANAGER: 60,
    Level.SENIOR_MANAGER: 65,
    Level.DIRECTOR: 70,
    Level.VP: 80,
    Level.EXECUTIVE: 90,
    Level.CEO: 95,
    Level.BOARD: 100,
}

_DISPLAY = {
    Level.INTERN: "Intern",
    Level.JUNIOR: "Junior Engineer",
    Level.ENGINEER: "Engineer",
    Level.SENIOR: "Senior Engineer",
    Level.TECH_LEAD: "Tech Lead",
    Level.STAFF: "Staff / Principal",
    Level.MANAGER: "Manager",
    Level.SENIOR_MANAGER: "Senior Manager",
    Level.DIRECTOR: "Director",
    Level.VP: "VP",
    Level.EXECUTIVE: "Executive",
    Level.CEO: "Chief Executive",
    Level.BOARD: "Board / Owner",
}


class Proficiency(str, Enum):
    """How deeply a role holds a skill. Derived from level, never hand-set."""

    AWARENESS = "awareness"
    WORKING = "working"
    PROFICIENT = "proficient"
    EXPERT = "expert"

    @property
    def rank(self) -> int:
        return list(Proficiency).index(self)


class CapabilityKind(str, Enum):
    """What sort of work a capability names."""

    EXECUTION = "execution"
    ANALYSIS = "analysis"
    REVIEW = "review"
    MANAGEMENT = "management"
    SIGNOFF = "signoff"


class KnowledgeSourceKind(str, Enum):
    #: A registered VeriTriage Knowledge Pack, validated to exist.
    VERITRIAGE_PACK = "veritriage_pack"
    SPECIFICATION = "specification"
    COMPANY_STANDARD = "company_standard"
    METHODOLOGY = "methodology"


class KnowledgeSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: KnowledgeSourceKind
    ref: str = Field(description="Pack ID, spec name, or standard ID.")
    title: str = ""


class Capability(BaseModel):
    """A unit of work the organization can perform: what a task requires."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: CapabilityKind
    description: str
    min_proficiency: Proficiency = Field(
        default=Proficiency.PROFICIENT,
        description="The proficiency a role needs in a providing skill to hold it.",
    )
    produces: tuple[str, ...] = Field(default=(), description="Artifact kinds it yields.")
    min_level: "Level | None" = Field(
        default=None,
        description="Seniority also required (signoff): skill alone is not enough.",
    )
    approved_inputs: bool = Field(
        default=False,
        description="Work of this kind builds only on approved upstream artifacts.",
    )
    model_needs: tuple[str, ...] = Field(
        default=(), description="What a model must offer to serve this work, beyond what the work implies (M31).",
    )
    max_attempts: int = Field(
        default=1, ge=1,
        description="Attempts per review round when the engine refuses a submission (M26); 1 means no repair.",
    )
    max_review_rounds: int = Field(
        default=1, ge=1,
        description="Submissions that may go to independent review (M27); 1 means no repair after review.",
    )


class Skill(BaseModel):
    """Reusable engineering know-how. Held by roles, never copied into them."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    domain: str
    subdomain: str = ""
    provides: tuple[str, ...] = Field(default=(), description="Capability IDs.")
    includes: tuple[str, ...] = Field(
        default=(), description="Composed skills: holding this implies holding these."
    )
    prerequisites: tuple[str, ...] = ()
    knowledge_sources: tuple[KnowledgeSource, ...] = ()
    procedures: tuple[str, ...] = ()
    tools: tuple[str, ...] = Field(default=(), description="Tool IDs the skill uses.")
    constraints: tuple[str, ...] = ()
    common_failure_modes: tuple[str, ...] = ()
    validation_criteria: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


class ToolStatus(str, Enum):
    #: Backed by a real binding in this repository; invocations execute.
    AVAILABLE = "available"
    #: An interface the organization plans around. It cannot be executed, and
    #: nothing may claim that it was.
    CONTRACT_ONLY = "contract_only"


class ToolRisk(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    APPROVE = "approve"


class ParamKind(str, Enum):
    TEXT = "text"
    #: One file path.
    PATH = "path"
    #: Several file paths, a tuple (M39). Its text form joins them with commas, so no element may contain one.
    PATHS = "paths"
    INTEGER = "integer"
    NUMBER = "number"


#: A parameter value as a binding receives it and a ToolRun stores it (M39): text for text and path, a tuple
#: for paths, an int for integer, a float for number. A run saved before M39 stores text, also a ParamValue.
ParamValue = str | int | float | tuple[str, ...]



class ParamSpec(BaseModel):
    """One parameter a tool takes (M28)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="The parameter, or with prefix=True the start of a family, e.g. 'max_'.")
    kind: ParamKind = ParamKind.TEXT
    required: bool = Field(
        default=False,
        description="The tool cannot do its job without it. A run missing it is a recorded failed run.",
    )
    description: str = ""
    prefix: bool = Field(default=False, description="Names every parameter that starts with ``name``.")

    @property
    def label(self) -> str:
        return f"{self.name}<metric>" if self.prefix else self.name

    def covers(self, param: str) -> bool:
        return param.startswith(self.name) if self.prefix else param == self.name

    def parse(self, raw: Any, param: str | None = None) -> ParamValue | None:
        """``raw`` as this kind's type (M39), or ValueError saying why; None for an empty integer or number.

        ``raw`` is a value's text form (the CLI, a task input, a workflow's fixed parameters), a number, or a
        list. A list is several values only for ``paths``; for another kind a one-element list is its element.
        """
        name = param or self.name
        if isinstance(raw, (list, tuple)):
            items = [str(v) for v in raw]
            commas = [v for v in items if "," in v]
            if commas:
                raise ValueError(f"{name}: {', '.join(repr(v) for v in commas)} contains a comma, "
                                 "so it cannot be told apart from two paths")
            if self.kind is ParamKind.PATHS:
                return tuple(list_values(tuple(items)))
            if len(items) > 1:
                raise ValueError(f"{name} takes one {'path' if self.kind is ParamKind.PATH else 'value'}, not a list")
            raw = items[0] if items else ""
        if self.kind is ParamKind.PATHS:
            return tuple(list_values(raw))
        if self.kind in (ParamKind.TEXT, ParamKind.PATH):
            return str(raw)
        if isinstance(raw, str) and not raw.strip():
            return None
        if self.kind is ParamKind.INTEGER:
            if isinstance(raw, int) and not isinstance(raw, bool):
                return raw
            if isinstance(raw, str) and raw.strip().removeprefix("-").isdigit():
                return int(raw.strip())
            raise ValueError(f"{name} must be a whole number, not {raw!r}")
        try:
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                raise ValueError(raw)
            return float(raw)
        except ValueError:
            raise ValueError(f"{name} must be a number, not {raw!r}") from None


def list_values(value: Any) -> list[str]:
    """A parameter's elements, without blanks: a tuple's, or a saved text value's (comma-joined)."""
    if value is None:
        return []
    parts = value if isinstance(value, (list, tuple)) else text_value(value).split(",")
    return [str(part).strip() for part in parts if str(part).strip()]


def text_value(value: Any) -> str:
    """A parameter value's text form (M39): a tuple joined with commas, ``40`` for 40.0; "" for None.

    For a value of the kind's type, :meth:`ParamSpec.parse` of this text gives the value back.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def param_matches(stored: Any, wanted: str) -> bool:
    """Whether a run's stored value is the value a requirement's fixed text names (M39).

    Compared by value: ``"60"`` matches 60, ``"a.v,b.v"`` matches ``("a.v", "b.v")``, text matches as text.
    """
    if stored is None:
        return False
    if isinstance(stored, (list, tuple)):
        return list_values(stored) == list_values(wanted)
    if isinstance(stored, (int, float)) and not isinstance(stored, bool):
        try:
            return float(wanted) == stored
        except ValueError:
            return False
    return stored == wanted


class ToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: str
    risk: ToolRisk
    status: ToolStatus = ToolStatus.CONTRACT_ONLY
    description: str = ""
    params: tuple[ParamSpec, ...] | None = Field(
        default=None,
        description="The parameters it takes (M28). None: no contract declared, parameters taken as given.",
    )

    def param(self, name: str) -> ParamSpec | None:
        """The declared parameter covering ``name``, if any."""
        return next((p for p in self.params or () if p.covers(name)), None)


class OrgUnit(BaseModel):
    """One node of the org chart: company, office, division, ..., practice."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: UnitKind
    function: Function
    parent: str | None = None
    mission: str = ""
    status: UnitStatus = UnitStatus.ACTIVE
    noun: str = Field(default="", description="Role noun for generated titles.")
    skills: tuple[str, ...] = Field(
        default=(), description="Baseline skills every role in this subtree holds."
    )
    tools: tuple[str, ...] = Field(
        default=(), description="Baseline tools every role in this subtree may use."
    )
    ladder: tuple[Level, ...] | None = Field(
        default=None, description="Override the leaf individual-contributor ladder."
    )
    head_role: str | None = Field(
        default=None, description="An existing role heading this unit instead of a generated one."
    )
    sponsor_role: str | None = Field(
        default=None, description="Executive role the unit head reports to (divisions)."
    )


class Role(BaseModel):
    """Responsibility, authority, and expertise. Not an LLM, not a person."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    unit: str
    level: Level
    reports_to: str | None = Field(default=None, description="Line manager role.")
    escalates_to: str | None = Field(
        default=None, description="Technical escalation target (may differ from line)."
    )
    skills: tuple[str, ...] = Field(default=(), description="Directly held skill IDs.")
    extra_capabilities: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    responsibilities: tuple[str, ...] = ()
    generated: bool = Field(default=True, description="Derived from unit staffing rules.")

    @property
    def track(self) -> Track:
        return self.level.track


class ActorKind(str, Enum):
    HUMAN = "human"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"


class AgentProfile(BaseModel):
    """A worker filling a role: a human, an AI agent, or the system itself.

    Everything the spec's agent card lists (skills, authority, tools, policies,
    escalation targets) is derived from the role. The profile only says who is
    sitting in the seat and which runtime, if any, powers them.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    role: str
    kind: ActorKind = ActorKind.AI_AGENT
    runtime: str = Field(default="unbound", description="Registered runtime ID.")


class LevelProfile(BaseModel):
    """What every role at one level holds, whatever unit it sits in.

    This is how "a tech lead reviews and a manager delegates" is written once
    instead of once per team.
    """

    model_config = ConfigDict(frozen=True)

    level: Level
    responsibilities: tuple[str, ...] = Field(
        default=(), description="'{unit}' is replaced with the unit name."
    )
    skills: tuple[str, ...] = Field(
        default=(), description="Skills held at EXPERT proficiency: the level's core competence."
    )
    tools: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
