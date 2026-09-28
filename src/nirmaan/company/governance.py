"""IP Nirmaan governance: authority matrix, escalation routes, gates, constitution."""

from __future__ import annotations

from nirmaan.models import (
    AuthorityRule,
    AuthorityScope,
    Criticality,
    DecisionKind,
    Enforcement,
    EscalationKind,
    EscalationRoute,
    GateSpec,
    Level,
    Principle,
)

L, M, H, C = Criticality.LOW, Criticality.MEDIUM, Criticality.HIGH, Criticality.CRITICAL
OWN, DIV, CO = AuthorityScope.OWN_UNIT, AuthorityScope.DIVISION, AuthorityScope.COMPANY


def _matrix(decision: DecisionKind, scope: AuthorityScope, low: Level, med: Level, high: Level, crit: Level,
            cross_functional_from: Criticality | None = None) -> list[AuthorityRule]:
    return [
        AuthorityRule(
            decision=decision,
            criticality=crit_level,
            min_level=level,
            scope=scope,
            cross_functional_review=(
                cross_functional_from is not None and crit_level.rank >= cross_functional_from.rank
            ),
        )
        for crit_level, level in ((L, low), (M, med), (H, high), (C, crit))
    ]


D = DecisionKind
AUTHORITY: list[AuthorityRule] = [
    *_matrix(D.EXECUTE_TASK, OWN, Level.INTERN, Level.JUNIOR, Level.ENGINEER, Level.SENIOR),
    *_matrix(D.MODIFY_ARTIFACT, OWN, Level.INTERN, Level.JUNIOR, Level.ENGINEER, Level.SENIOR),
    *_matrix(D.REVIEW_ARTIFACT, DIV, Level.ENGINEER, Level.SENIOR, Level.SENIOR, Level.TECH_LEAD),
    *_matrix(D.APPROVE_ARTIFACT, OWN, Level.SENIOR, Level.TECH_LEAD, Level.TECH_LEAD, Level.MANAGER),
    *_matrix(D.APPROVE_GATE, OWN, Level.MANAGER, Level.MANAGER, Level.DIRECTOR, Level.VP),
    *_matrix(D.CREATE_TASK, OWN, Level.TECH_LEAD, Level.TECH_LEAD, Level.MANAGER, Level.DIRECTOR),
    *_matrix(D.ASSIGN_TASK, OWN, Level.TECH_LEAD, Level.TECH_LEAD, Level.MANAGER, Level.DIRECTOR),
    *_matrix(D.CANCEL_TASK, OWN, Level.TECH_LEAD, Level.MANAGER, Level.DIRECTOR, Level.VP),
    *_matrix(D.ARCHITECTURE_DECISION, DIV, Level.SENIOR, Level.STAFF, Level.DIRECTOR, Level.EXECUTIVE, H),
    *_matrix(D.CROSS_TEAM_DECISION, DIV, Level.MANAGER, Level.MANAGER, Level.DIRECTOR, Level.VP, H),
    *_matrix(D.WAIVE_REQUIREMENT, CO, Level.DIRECTOR, Level.DIRECTOR, Level.VP, Level.EXECUTIVE, M),
    *_matrix(D.RELEASE, CO, Level.VP, Level.VP, Level.EXECUTIVE, Level.EXECUTIVE, M),
]

E = EscalationKind
ESCALATION: list[EscalationRoute] = [
    EscalationRoute(kind=E.UNCERTAINTY, one_step=True,
                    description="Not sure: ask the next person up the technical chain."),
    EscalationRoute(kind=E.TECHNICAL, min_level=Level.TECH_LEAD,
                    description="A technical question the owner cannot settle."),
    EscalationRoute(kind=E.ARCHITECTURAL, min_level=Level.TECH_LEAD,
                    description="An issue that questions the microarchitecture."),
    EscalationRoute(kind=E.CONFLICT, min_level=Level.TECH_LEAD,
                    description="Conflicting outputs or review verdicts (constitution article 7)."),
    EscalationRoute(kind=E.CROSS_TEAM, min_level=Level.MANAGER,
                    description="Needs another team to act or agree."),
    EscalationRoute(kind=E.RESOURCE, min_level=Level.MANAGER,
                    description="Staffing, compute, or schedule."),
    EscalationRoute(kind=E.STRATEGIC, min_level=Level.DIRECTOR,
                    description="Scope, priority, or strategy conflict."),
    EscalationRoute(kind=E.POLICY, min_level=Level.DIRECTOR,
                    description="A request to act against, or waive, the constitution."),
    EscalationRoute(kind=E.MAJOR_ARCHITECTURAL, resolver_role="exec.chief_architect",
                    description="A conflict that changes architecture across teams or products."),
]

GATES: list[GateSpec] = [
    GateSpec(id="gate.requirements", name="Requirements baseline",
             description="Requirements are complete, testable, and approved.",
             approver_capability="signoff.requirements", min_level=Level.DIRECTOR),
    GateSpec(id="gate.architecture", name="Architecture approval",
             description="Architecture and microarchitecture are reviewed and approved.",
             approver_capability="signoff.architecture", min_level=Level.DIRECTOR, human_required=True),
    GateSpec(id="gate.rtl", name="RTL baseline",
             description="RTL is implemented, lint-clean, reviewed, and quality-checked.",
             approver_capability="signoff.rtl", min_level=Level.MANAGER),
    GateSpec(id="gate.verification", name="Verification signoff",
             description="Verification is complete against the plan, with evidence.",
             approver_capability="signoff.verification", min_level=Level.DIRECTOR, human_required=True),
    GateSpec(id="gate.implementation", name="Implementation signoff",
             description="Timing, power, and physical criteria are met, with evidence.",
             approver_capability="signoff.implementation", min_level=Level.DIRECTOR),
    GateSpec(id="gate.release", name="Release approval",
             description="The deliverable may leave the company.",
             approver_capability="signoff.release", min_level=Level.VP, human_required=True),
]

B, W = Enforcement.BLOCK, Enforcement.WARN
CONSTITUTION: list[Principle] = [
    Principle(id="P1", title="Traceability", enforcement=B, checks=("traceable-to-requirement",),
              statement="Requirements must be traceable: every task traces to the requirement it serves."),
    Principle(id="P2", title="Evidence for decisions", enforcement=B, checks=("decision-needs-evidence",),
              statement="Important engineering decisions require evidence."),
    Principle(id="P3", title="Explicit uncertainty", enforcement=B, checks=("uncertainty-declared",),
              statement="Agents must explicitly represent uncertainty."),
    Principle(id="P4", title="No fabricated work", enforcement=B, checks=("no-fabricated-completion",),
              statement="Agents must not fabricate completed work."),
    Principle(id="P5", title="No fabricated tool runs", enforcement=B, checks=("tool-claims-need-runs",),
              statement="Agents must not claim a tool was executed if it was not."),
    Principle(id="P6", title="Independent review", enforcement=B, checks=("independent-review",),
              statement="Critical work requires independent review; nobody approves their own work."),
    Principle(id="P7", title="Conflicts escalate", enforcement=B, checks=("conflicts-escalate",),
              statement="Conflicting outputs require escalation before approval."),
    Principle(id="P8", title="Provenance", enforcement=B, checks=("provenance", "approved-inputs"),
              statement="Changes must preserve provenance: who, what, from which inputs."),
    Principle(id="P9", title="Evidence for signoff", enforcement=B,
              checks=("signoff-needs-evidence", "evidence-before-review"),
              statement="Signoff requires evidence."),
    Principle(id="P10", title="No hidden state changes", enforcement=B, checks=("state-changes-audited",),
              statement="No hidden state changes: every change goes through the engine and the audit trail."),
    Principle(id="P11", title="Auditability", enforcement=B, checks=("audit-chain-intact",),
              statement="Work must remain auditable: the audit trail is append-only and hash-chained."),
    Principle(id="P12", title="Human gates", enforcement=B, checks=("human-gates",),
              statement="Human approval can be required at configurable gates."),
]
