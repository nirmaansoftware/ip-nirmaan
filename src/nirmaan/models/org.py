"""Organizational vocabulary: units, levels, roles, skills, capabilities, tools.

Plain, frozen data. Nothing here imports an engine, a registry, or VeriTriage,
which is what lets the organization exist independently of any LLM: a role is
a record of responsibility and authority, not a prompt.
"""

from __future__ import annotations

from enum import Enum

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


class ToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: str
    risk: ToolRisk
    status: ToolStatus = ToolStatus.CONTRACT_ONLY
    description: str = ""


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
