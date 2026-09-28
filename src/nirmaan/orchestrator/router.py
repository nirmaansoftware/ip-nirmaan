"""The router: capability in, owner and reviewer out, with the reasons.

Routing is a scored join over organizational data, never a branch on a domain
name. A candidate owner must hold the capability, be active, sit on the
individual-contributor track (managers delegate; they do not absorb the work),
and hold execution authority for the task's criticality. Among those, the
score prefers the level the criticality calls for, the refining skills the
stage names, and roles whose own unit (not an ancestor) carries the providing
skill. Ties break on role ID, so the same organization always routes the same
way. Every decision keeps its candidate list, so "why this owner?" has an
answer.
"""

from __future__ import annotations

from nirmaan.models import (
    CapabilityKind,
    Criticality,
    DecisionKind,
    GateSpec,
    Level,
    ReviewRequirement,
    Role,
    RoutingCandidate,
    RoutingDecision,
    Track,
)
from nirmaan.org import AuthorityService, Organization

#: The level each criticality calls for when choosing an owner.
_TARGET_LEVEL = {
    Criticality.LOW: Level.JUNIOR,
    Criticality.MEDIUM: Level.ENGINEER,
    Criticality.HIGH: Level.SENIOR,
    Criticality.CRITICAL: Level.STAFF,
}

_SHORTLIST = 5

#: Requirement context refines routing but must never outweigh what the stage
#: itself asks for: each context skill is worth a little, and the total is capped.
_CONTEXT_WEIGHT, _CONTEXT_CAP = 0.25, 1.0
_REVIEW_CONTEXT_WEIGHT, _REVIEW_CONTEXT_CAP = 0.75, 2.25


class Router:
    def __init__(self, org: Organization) -> None:
        self._org = org
        self._authority = AuthorityService(org)

    # --- Owners ----------------------------------------------------------------

    def owner(
        self,
        capability: str,
        criticality: Criticality,
        skills: tuple[str, ...] = (),
        context: tuple[str, ...] = (),
    ) -> RoutingDecision:
        """``skills`` are what the stage asks for; ``context`` what the requirement is about."""
        org = self._org
        kind = org.capabilities[capability].kind
        management = kind is CapabilityKind.MANAGEMENT
        target = _TARGET_LEVEL[criticality]
        scored: list[RoutingCandidate] = []
        for role in org.roles_with(capability):
            if not org.is_active(role.id):
                continue
            if not management and role.track is not Track.INDIVIDUAL:
                continue  # managers delegate execution; they do not absorb it
            if not management and not self._authority.check(
                role.id, DecisionKind.EXECUTE_TASK, criticality
            ).allowed:
                continue
            score, reasons = self._fit(role, capability, skills, context, target)
            scored.append(RoutingCandidate(role=role.id, score=score, reasons=tuple(reasons)))
        return self._decide(capability, scored, "owner")

    def _fit(
        self,
        role: Role,
        capability: str,
        skills: tuple[str, ...],
        context: tuple[str, ...],
        target: Level,
    ) -> tuple[float, list[str]]:
        org = self._org
        held = set(org.effective_skills(role.id))
        reasons: list[str] = []
        score = 0.0
        own = set(org.units[role.unit].skills)
        matched = [s for s in skills if s in held]
        if matched:
            specialist = [s for s in matched if s in own]
            score += 2.0 * len(matched) + 1.0 * len(specialist)
            reasons.append(f"holds {', '.join(matched)}")
        relevant = [s for s in context if s in held and s not in matched]
        if relevant:
            score += min(_CONTEXT_CAP, _CONTEXT_WEIGHT * len(relevant))
            reasons.append(f"knows {', '.join(relevant)} (from the requirement)")
        specificity, where = self._specificity(role, capability)
        if specificity:
            score += specificity
            reasons.append(f"{capability} is a specialty of {where}")
        focus = [s for s in context if s in own]
        if focus:
            score += min(1.5, 0.75 * len(focus))
            reasons.append(f"its unit specializes in {', '.join(focus)}")
        distance = abs(role.level.rank - target.rank) / 10.0
        score -= distance
        reasons.append(f"{role.level.display_name} vs {target.display_name} wanted")
        return round(score, 3), reasons

    def _specificity(self, role: Role, capability: str) -> tuple[float, str]:
        """How close to the role the capability is a unit's declared specialty.

        1.5 in its own unit, 1.0 one level up, 0.5 two levels up; half that when
        the providing skill is only composed (``includes``) rather than direct.
        """
        org = self._org
        best, where = 0.0, ""
        for depth, unit in enumerate(org.ancestors(role.unit, include_self=True)[:3]):
            weight = (1.5, 1.0, 0.5)[depth]
            declared = set(unit.skills)
            if any(capability in org.skills[s].provides for s in declared if s in org.skills):
                value = weight
            elif any(capability in org.skills[s].provides for s in _closure(org, declared)):
                value = weight / 2
            else:
                continue
            if value > best:
                best, where = value, unit.name
        return best, where

    # --- Reviewers ---------------------------------------------------------------

    def reviewer(
        self,
        requirement: ReviewRequirement,
        owner: str,
        criticality: Criticality,
        unit: str,
        skills: tuple[str, ...] = (),
        context: tuple[str, ...] = (),
    ) -> RoutingDecision:
        org = self._org
        chain = [r.id for r in org.escalation_chain(owner)]
        owner_role = org.roles[owner]
        scored: list[RoutingCandidate] = []
        for role in org.roles_with(requirement.capability):
            if requirement.independent and role.id == owner:
                continue
            if not org.is_active(role.id) or not role.level.at_least(requirement.min_level):
                continue
            if not self._authority.check(
                role.id, DecisionKind.REVIEW_ARTIFACT, criticality, unit
            ).allowed:
                continue
            reasons: list[str] = []
            score = 0.0
            if role.id in chain:
                score += 3.0 - 0.1 * chain.index(role.id)
                reasons.append("in the owner's escalation chain")
            if org.is_within(role.unit, org.units[owner_role.unit].parent or owner_role.unit):
                score += 1.0
                reasons.append("same team")
            held = set(org.effective_skills(role.id))
            matched = [s for s in skills if s in held]
            if matched:
                score += 1.0 * len(matched)
                reasons.append(f"holds {', '.join(matched)}")
            relevant = [s for s in context if s in held and s not in matched]
            if relevant:
                score += min(_REVIEW_CONTEXT_CAP, _REVIEW_CONTEXT_WEIGHT * len(relevant))
                reasons.append(f"knows {', '.join(relevant)} (from the requirement)")
            if role.level.rank > owner_role.level.rank:
                score += 0.5
                reasons.append("senior to the owner")
            score -= role.level.rank / 1000.0  # prefer the nearest qualified level
            scored.append(RoutingCandidate(role=role.id, score=round(score, 3), reasons=tuple(reasons)))
        return self._decide(requirement.capability, scored, "reviewer")

    # --- Approvers -------------------------------------------------------------------

    def approver(self, owner: str, criticality: Criticality, unit: str) -> str | None:
        """First role up the owner's chain with approval authority over the unit."""
        for role in self._org.escalation_chain(owner):
            if self._authority.check(role.id, DecisionKind.APPROVE_ARTIFACT, criticality, unit).allowed:
                return role.id
        return None

    def gate_approver(self, gate: GateSpec, criticality: Criticality, stage_owner: str | None) -> RoutingDecision:
        org = self._org
        chain = [r.id for r in org.escalation_chain(stage_owner)] if stage_owner else []
        scored: list[RoutingCandidate] = []
        for role in org.roles_with(gate.approver_capability):
            if not org.is_active(role.id) or not role.level.at_least(gate.min_level):
                continue
            if not self._authority.check(role.id, DecisionKind.APPROVE_GATE, criticality).allowed:
                continue
            reasons, score = [], 0.0
            if role.id in chain:
                score += 3.0 - 0.1 * chain.index(role.id)
                reasons.append("in the stage owner's chain")
            score -= role.level.rank / 100.0
            reasons.append(f"{role.level.display_name} holds {gate.approver_capability}")
            scored.append(RoutingCandidate(role=role.id, score=round(score, 3), reasons=tuple(reasons)))
        return self._decide(gate.approver_capability, scored, "gate approver")

    # --- Managers ---------------------------------------------------------------------

    def unit_manager(self, units: list[str], capability: str) -> RoutingDecision:
        """The manager of the deepest unit containing all the given units.

        ``units`` has one entry per task, so a unit doing more of the work weighs more.
        """
        org = self._org
        chains = [[u.id for u in reversed(org.ancestors(uid, include_self=True))] for uid in units]
        common: list[str] = []
        for level in zip(*chains):
            if len(set(level)) != 1:
                break
            common.append(level[0])
        if len(common) <= 1 and units:
            # Spans divisions: the division owning the most of this work leads it;
            # on a tie, the division doing the work that closes the phase.
            counts: dict[str, int] = {}
            for uid in units:
                div = org.division_of(uid).id
                counts[div] = counts.get(div, 0) + 1
            best = max(counts.values())
            leader = next(org.division_of(u).id for u in reversed(units) if counts[org.division_of(u).id] == best)
            return self.unit_manager([u for u in units if org.division_of(u).id == leader], capability)
        for unit_id in reversed(common):
            head = org.head_of(unit_id)
            if head and org.holds(head.id, capability) and org.is_active(head.id):
                return RoutingDecision(
                    capability=capability,
                    chosen=head.id,
                    rationale=f"head of {org.units[unit_id].name}, the narrowest unit containing this work",
                    candidates=(RoutingCandidate(role=head.id, score=1.0, reasons=("unit head",)),),
                )
        return RoutingDecision(capability=capability, chosen=None, rationale="no managing head found")

    # --- Shared ---------------------------------------------------------------------

    @staticmethod
    def _decide(capability: str, scored: list[RoutingCandidate], what: str) -> RoutingDecision:
        if not scored:
            return RoutingDecision(
                capability=capability,
                chosen=None,
                rationale=f"no eligible {what} holds {capability}; escalate for staffing",
            )
        ranked = sorted(scored, key=lambda c: (-c.score, c.role))
        best = ranked[0]
        return RoutingDecision(
            capability=capability,
            chosen=best.role,
            rationale=f"best-scoring {what} of {len(ranked)}: " + "; ".join(best.reasons),
            candidates=tuple(ranked[:_SHORTLIST]),
        )


def _closure(org: Organization, skill_ids: set[str]) -> set[str]:
    found: set[str] = set()
    frontier = list(skill_ids)
    while frontier:
        current = frontier.pop()
        if current in found or current not in org.skills:
            continue
        found.add(current)
        frontier.extend(org.skills[current].includes)
    return found
