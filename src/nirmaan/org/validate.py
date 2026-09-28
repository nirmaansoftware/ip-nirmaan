"""Organization integrity: every reference resolves, every chain terminates.

Validation is what makes the organization trustworthy as data. It is run on
every build, so a department whose roles cannot be routed to, a workflow stage
no role can own, or a gate nobody is authorized to approve is a build error,
not a surprise at planning time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nirmaan.models import (
    CapabilityKind,
    Criticality,
    DecisionKind,
    EscalationKind,
    Level,
    UnitKind,
    UnitStatus,
)

if TYPE_CHECKING:
    from nirmaan.org.organization import Organization


def validate_organization(org: "Organization") -> list[str]:
    issues: list[str] = []
    issues += [f"duplicate id {d}" for d in org.duplicate_ids]
    issues += _units(org)
    if issues:
        return issues  # everything below assumes a well-formed tree
    issues += _roles(org)
    issues += _skills(org)
    issues += _coverage(org)
    issues += _workflows(org)
    issues += _governance(org)
    issues += _vocabulary(org)
    return issues


def _units(org: "Organization") -> list[str]:
    issues: list[str] = []
    roots = [u for u in org.units.values() if u.parent is None]
    if len(roots) != 1:
        issues.append(f"expected exactly one root unit, found {len(roots)}")
    for unit in org.units.values():
        if unit.parent is not None and unit.parent not in org.units:
            issues.append(f"unit {unit.id}: unknown parent {unit.parent}")
            continue
        seen, current = set(), unit.id
        while current is not None:
            if current in seen:
                issues.append(f"unit {unit.id}: parent cycle")
                break
            seen.add(current)
            current = org.units[current].parent if current in org.units else None
        for skill in unit.skills:
            if skill not in org.skills:
                issues.append(f"unit {unit.id}: unknown skill {skill}")
        for tool in unit.tools:
            if tool not in org.tools:
                issues.append(f"unit {unit.id}: unknown tool {tool}")
        if unit.head_role and unit.head_role not in org.roles:
            issues.append(f"unit {unit.id}: unknown head role {unit.head_role}")
        if unit.sponsor_role and unit.sponsor_role not in org.roles:
            issues.append(f"unit {unit.id}: unknown sponsor role {unit.sponsor_role}")
        is_leaf = not org.children(unit.id)
        if (
            is_leaf
            and unit.status is UnitStatus.ACTIVE
            and unit.kind in (UnitKind.DIVISION, UnitKind.OFFICE)
            and not unit.head_role
        ):
            issues.append(f"unit {unit.id}: an active {unit.kind.value} with no children has no staff")
    return issues


def _roles(org: "Organization") -> list[str]:
    issues: list[str] = []
    for role in org.roles.values():
        if role.unit not in org.units:
            issues.append(f"role {role.id}: unknown unit {role.unit}")
        for skill in role.skills:
            if skill not in org.skills:
                issues.append(f"role {role.id}: unknown skill {skill}")
        for tool in role.tools:
            if tool not in org.tools:
                issues.append(f"role {role.id}: unknown tool {tool}")
        for cap in role.extra_capabilities:
            if cap not in org.capabilities:
                issues.append(f"role {role.id}: unknown capability {cap}")
        for attr in ("reports_to", "escalates_to"):
            target = getattr(role, attr)
            if target is None:
                if role.level is not Level.BOARD:
                    issues.append(f"role {role.id}: no {attr}")
                continue
            if target not in org.roles:
                issues.append(f"role {role.id}: {attr} unknown role {target}")
                continue
            if org.roles[target].level.rank <= role.level.rank:
                issues.append(
                    f"role {role.id} ({role.level.value}): {attr} {target} "
                    f"({org.roles[target].level.value}) is not senior"
                )
    return issues


def _skills(org: "Organization") -> list[str]:
    issues: list[str] = []
    for skill in org.skills.values():
        for ref in (*skill.includes, *skill.prerequisites):
            if ref not in org.skills:
                issues.append(f"skill {skill.id}: unknown skill {ref}")
        for cap in skill.provides:
            if cap not in org.capabilities:
                issues.append(f"skill {skill.id}: unknown capability {cap}")
        for tool in skill.tools:
            if tool not in org.tools:
                issues.append(f"skill {skill.id}: unknown tool {tool}")
        if not skill.validation_criteria:
            issues.append(f"skill {skill.id}: no validation criteria")
        # Composition must terminate.
        frontier, seen = list(skill.includes), set()
        while frontier:
            current = frontier.pop()
            if current == skill.id:
                issues.append(f"skill {skill.id}: includes itself")
                break
            if current in seen or current not in org.skills:
                continue
            seen.add(current)
            frontier.extend(org.skills[current].includes)
    return issues


def _coverage(org: "Organization") -> list[str]:
    """Every capability the company declares can actually be performed."""
    issues: list[str] = []
    for cap in org.capabilities.values():
        if not org.providers_of(cap.id) and not any(
            cap.id in r.extra_capabilities for r in org.roles.values()
        ):
            issues.append(f"capability {cap.id}: no skill provides it")
    return issues


def _held_by_active(org: "Organization", capability: str, min_level: Level = Level.INTERN) -> bool:
    return any(
        org.is_active(r.id) and r.level.at_least(min_level) for r in org.roles_with(capability)
    )


def _workflows(org: "Organization") -> list[str]:
    issues: list[str] = []
    for wf in org.workflows.values():
        ids = [s.id for s in wf.stages]
        if len(ids) != len(set(ids)):
            issues.append(f"workflow {wf.id}: duplicate stage IDs")
        for stage in wf.stages:
            where = f"workflow {wf.id} stage {stage.id}"
            if stage.capability not in org.capabilities:
                issues.append(f"{where}: unknown capability {stage.capability}")
            elif not _held_by_active(org, stage.capability):
                issues.append(f"{where}: no active role holds {stage.capability}")
            if stage.criticality.rank >= Criticality.HIGH.rank and stage.review is None:
                issues.append(f"{where}: {stage.criticality.value} work must declare an independent review (P6)")
            if stage.review:
                if stage.review.capability not in org.capabilities:
                    issues.append(f"{where}: unknown review capability {stage.review.capability}")
                elif org.capabilities[stage.review.capability].kind is not CapabilityKind.REVIEW:
                    issues.append(f"{where}: {stage.review.capability} is not a review capability")
                elif not _held_by_active(org, stage.review.capability, stage.review.min_level):
                    issues.append(f"{where}: no active reviewer holds {stage.review.capability}")
            for dep in stage.depends_on:
                if dep not in ids:
                    issues.append(f"{where}: unknown dependency {dep}")
            if stage.owner_from and stage.owner_from not in ids:
                issues.append(f"{where}: owner_from names unknown stage {stage.owner_from}")
            if stage.gate and stage.gate not in org.gates:
                issues.append(f"{where}: unknown gate {stage.gate}")
            for skill in (*stage.skills, *(s for v in stage.variants for s in v.skills)):
                if skill not in org.skills:
                    issues.append(f"{where}: unknown skill {skill}")
            if stage.branch:
                decision = wf.stage(stage.branch[0])
                if decision is None or stage.branch[1] not in decision.outcomes:
                    issues.append(f"{where}: branch {stage.branch} names no declared outcome")
            for req in stage.evidence:
                if "claim" in {k.value for k in req.accepts}:
                    issues.append(f"{where}: an evidence requirement may not accept a bare claim")
                for tool in req.tools:
                    if tool not in org.tools:
                        issues.append(f"{where}: evidence names unknown tool {tool}")
        # Stage dependencies must be acyclic.
        deps = {s.id: set(s.depends_on) for s in wf.stages}
        while deps:
            free = [k for k, v in deps.items() if not (v & deps.keys())]
            if not free:
                issues.append(f"workflow {wf.id}: dependency cycle among {sorted(deps)}")
                break
            for k in free:
                deps.pop(k)
        for cap in (wf.lead_capability, wf.workstream_capability):
            if cap not in org.capabilities:
                issues.append(f"workflow {wf.id}: unknown capability {cap}")
    for gate in org.gates.values():
        if gate.approver_capability not in org.capabilities:
            issues.append(f"gate {gate.id}: unknown capability {gate.approver_capability}")
        elif not _held_by_active(org, gate.approver_capability, gate.min_level):
            issues.append(f"gate {gate.id}: nobody at {gate.min_level.value}+ can approve it")
    return issues


def _governance(org: "Organization") -> list[str]:
    issues: list[str] = []
    for decision in DecisionKind:
        for crit in Criticality:
            if (decision.value, crit.value) not in org.authority:
                issues.append(f"authority matrix: no rule for {decision.value}/{crit.value}")
    for kind in EscalationKind:
        route = org.escalation.get(kind.value)
        if route is None:
            issues.append(f"escalation: no route for {kind.value}")
        elif route.resolver_role and route.resolver_role not in org.roles:
            issues.append(f"escalation {kind.value}: unknown resolver {route.resolver_role}")
    if not org.principles:
        issues.append("constitution: no principles")
    return issues


def _vocabulary(org: "Organization") -> list[str]:
    issues: list[str] = []
    intents = {r.intent for r in org.intents}
    features = {r.feature for r in org.features}
    for rule in org.features:
        for implied in rule.implies:
            if implied not in features:
                issues.append(f"feature {rule.feature}: implies unknown feature {implied}")
        for skill in rule.skills:
            if skill not in org.skills:
                issues.append(f"feature {rule.feature}: unknown skill {skill}")
    for wf in org.workflows.values():
        for intent in wf.intents:
            if intent not in intents:
                issues.append(f"workflow {wf.id}: unknown intent {intent}")
        for stage in wf.stages:
            conds = [stage.when, *(v.when for v in stage.variants)]
            for cond in conds:
                for f in (*cond.all_of, *cond.any_of, *cond.none_of):
                    if f not in features:
                        issues.append(f"workflow {wf.id} stage {stage.id}: unknown feature {f}")
    for intent in intents:
        if not any(intent in wf.intents for wf in org.workflows.values()):
            issues.append(f"intent {intent}: no workflow serves it")
    for rule in org.assumptions:
        for f in (*rule.assume_features, *rule.when.all_of, *rule.when.any_of, *rule.when.none_of):
            if f not in features:
                issues.append(f"assumption {rule.id}: unknown feature {f}")
        for intent in rule.applies_to_intents:
            if intent not in intents:
                issues.append(f"assumption {rule.id}: unknown intent {intent}")
    return issues
