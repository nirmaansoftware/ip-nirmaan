"""Authority and escalation: table lookups over the org chart.

Two questions, both answered from data. *May this role make this decision
about this part of the company?* is the authority matrix plus the role's
authority domain. *Who should hear about this problem?* is the escalation
route for its kind, walked up the role's technical chain.
"""

from __future__ import annotations

from nirmaan.models import (
    AuthorityScope,
    AuthorityVerdict,
    Criticality,
    DecisionKind,
    EscalationKind,
    Role,
    ToolStatus,
)
from nirmaan.org.organization import Organization


class AuthorityService:
    def __init__(self, org: Organization) -> None:
        self._org = org

    def check(
        self,
        role_id: str,
        decision: DecisionKind,
        criticality: Criticality,
        subject_unit: str | None = None,
    ) -> AuthorityVerdict:
        org = self._org
        rule = org.authority[(decision.value, criticality.value)]
        role = org.roles[role_id]
        base = {
            "decision": decision,
            "criticality": criticality,
            "actor_role": role_id,
            "required_level": rule.min_level,
        }
        problem = self._problem(role, rule.min_level, rule.scope, subject_unit)
        if problem is None:
            return AuthorityVerdict(
                allowed=True,
                reason=(
                    f"{role.title} ({role.level.display_name}) holds "
                    f"{decision.value}/{criticality.value} (needs {rule.min_level.display_name}, "
                    f"scope {rule.scope.value})"
                ),
                **base,
            )
        target = next(
            (
                r.id
                for r in org.escalation_chain(role_id)
                if self._problem(r, rule.min_level, rule.scope, subject_unit) is None
            ),
            None,
        )
        return AuthorityVerdict(allowed=False, reason=problem, escalate_to=target, **base)

    def _problem(self, role: Role, min_level, scope: AuthorityScope, subject_unit: str | None) -> str | None:
        org = self._org
        if not role.level.at_least(min_level):
            return (
                f"{role.title} is {role.level.display_name}; this needs "
                f"{min_level.display_name} or above"
            )
        if subject_unit is None or scope is AuthorityScope.COMPANY:
            return None
        domain = org.authority_domain(role.id)
        if scope is AuthorityScope.DIVISION:
            domain = org.division_of(domain).id if domain != org.root.id else domain
        if not org.is_within(subject_unit, domain):
            return f"{subject_unit} is outside {role.title}'s authority ({domain}, scope {scope.value})"
        return None

    def may_use_tool(self, role_id: str, tool_id: str) -> tuple[bool, str]:
        org = self._org
        tool = org.tools.get(tool_id)
        if tool is None:
            return False, f"unknown tool {tool_id!r}"
        if tool_id not in org.tools_of(role_id):
            return False, f"{org.roles[role_id].title} is not granted {tool_id}"
        if tool.status is ToolStatus.CONTRACT_ONLY:
            return False, f"{tool_id} is contract-only: declared, not implemented, never executable"
        return True, "granted"


def route_escalation(org: Organization, raised_by: str, kind: EscalationKind) -> str | None:
    """The role an escalation of this kind from this role lands on."""
    route = org.escalation[kind.value]
    raiser = org.roles[raised_by]
    chain = org.escalation_chain(raised_by)
    if route.resolver_role and route.resolver_role != raised_by:
        resolver = org.roles[route.resolver_role]
        if resolver.level.rank > raiser.level.rank:
            return resolver.id
    if route.one_step or route.min_level is None:
        return chain[0].id if chain else None
    for role in chain:
        if role.level.at_least(route.min_level) and role.level.rank > raiser.level.rank:
            return role.id
    return chain[-1].id if chain else None
