"""Governance vocabulary: authority, escalation, policy, and gates.

Authority is a table, not code. Who may approve, modify, waive, or release is a
lookup of (decision, criticality) against a level, scoped to the part of the
org chart the actor is responsible for.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from nirmaan.models.org import Level


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return list(Criticality).index(self)


class DecisionKind(str, Enum):
    EXECUTE_TASK = "execute_task"
    MODIFY_ARTIFACT = "modify_artifact"
    REVIEW_ARTIFACT = "review_artifact"
    APPROVE_ARTIFACT = "approve_artifact"
    APPROVE_GATE = "approve_gate"
    CREATE_TASK = "create_task"
    ASSIGN_TASK = "assign_task"
    CANCEL_TASK = "cancel_task"
    ARCHITECTURE_DECISION = "architecture_decision"
    CROSS_TEAM_DECISION = "cross_team_decision"
    WAIVE_REQUIREMENT = "waive_requirement"
    RELEASE = "release"


class AuthorityScope(str, Enum):
    """How far from their own unit an actor's authority reaches."""

    #: The actor's own unit subtree.
    OWN_UNIT = "own_unit"
    #: Anywhere in the actor's division.
    DIVISION = "division"
    #: Anywhere in the company.
    COMPANY = "company"


class AuthorityRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: DecisionKind
    criticality: Criticality
    min_level: Level
    scope: AuthorityScope = AuthorityScope.OWN_UNIT
    cross_functional_review: bool = Field(
        default=False,
        description="Also requires sign-off from a second function (recorded, not inferred).",
    )


class AuthorityVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    decision: DecisionKind
    criticality: Criticality
    actor_role: str
    required_level: Level
    reason: str
    escalate_to: str | None = Field(
        default=None, description="Nearest role in the chain that holds the authority."
    )


class EscalationKind(str, Enum):
    UNCERTAINTY = "uncertainty"
    TECHNICAL = "technical"
    ARCHITECTURAL = "architectural"
    CROSS_TEAM = "cross_team"
    RESOURCE = "resource"
    STRATEGIC = "strategic"
    MAJOR_ARCHITECTURAL = "major_architectural"
    POLICY = "policy"
    CONFLICT = "conflict"


class EscalationRoute(BaseModel):
    """Where one kind of escalation lands. Data, so it is inspectable and testable."""

    model_config = ConfigDict(frozen=True)

    kind: EscalationKind
    min_level: Level | None = Field(
        default=None, description="Resolve at the first chain role at or above this level."
    )
    one_step: bool = Field(
        default=False, description="Resolve at the next role up the chain, whatever its level."
    )
    resolver_role: str | None = Field(
        default=None, description="A fixed resolver (e.g. the Chief Architect) instead of the chain."
    )
    description: str = ""


class Enforcement(str, Enum):
    #: The action is refused.
    BLOCK = "block"
    #: The action proceeds and the violation is written to the audit trail.
    WARN = "warn"


class Principle(BaseModel):
    """One article of the company constitution."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    statement: str
    enforcement: Enforcement = Enforcement.BLOCK
    checks: tuple[str, ...] = Field(default=(), description="Registered policy check IDs.")


class GateSpec(BaseModel):
    """A review gate: a point work may not pass without an authorized approval."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    approver_capability: str = Field(description="Capability the approver must hold.")
    min_level: Level
    human_required: bool = Field(
        default=False, description="Default; projects may override per gate."
    )
