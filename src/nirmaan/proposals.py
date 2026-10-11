"""Learning proposals (M33): recurring failures propose skill changes; only a person adopts one.

``learning_proposals`` reads the failure records (M29) of several projects and,
through a registry of rules, proposes changes to the skills that provide the
work that keeps failing the same way. A proposal cites every record it rests
on, and its ID depends only on its rule, capability, and subject, so it is the
same proposal as evidence grows. Nothing here stores, edits, or calls a model.

``decide_proposal`` records a person's decision to adopt or reject one, as a
cross-team decision through the engine (authority matrix, audit trail, shown by
``nirmaan decisions``). Adopting changes no skill by itself: skills are company
data, changed by a person in a pull request, with the decision as its reason.
"""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from nirmaan.models import Actor, ActorKind, Criticality, Decision, DecisionKind, ProjectState
from nirmaan.org import Organization
from nirmaan.records import FailureCategory, FailureRecord, failure_records
from nirmaan.registry import Registry
from nirmaan.work import TaskEngine

#: A rule needs the same failure in at least this many different tasks: one occurrence proposes nothing.
MIN_TASKS = 2
_PREFIX = "Learning proposal"


class ProposalError(RuntimeError):
    """A decision on a proposal that cannot be recorded honestly. Nothing was recorded."""


@dataclass(frozen=True)
class Proposal:
    id: str
    rule: str
    capability: str | None
    subject: str
    targets: tuple[str, ...]
    statement: str
    suggestion: str
    count: int
    projects: int
    evidence: tuple[dict[str, Any], ...]
    status: str = "open"
    #: Where the evidence comes from: failure records in projects (M33) or recorded evaluation runs (M42).
    source: str = "failures"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Observed = list[tuple[ProjectState, FailureRecord]]
Rule = Callable[[Organization, Observed], list[Proposal]]
_RULES: MutableMapping[str, Rule] = Registry("proposals.rules")


def register_proposal_rule(rule_id: str) -> Callable[[Rule], Rule]:
    def _register(fn: Rule) -> Rule:
        if rule_id in _RULES and _RULES[rule_id] is not fn:
            raise ValueError(f"Proposal rule {rule_id!r} is already registered")
        _RULES[rule_id] = fn
        return fn

    return _register


def unregister_proposal_rule(rule_id: str) -> None:
    _RULES.pop(rule_id, None)


def proposal_id(rule: str, capability: str | None, subject: str) -> str:
    return "lp-" + hashlib.sha256(f"{rule}|{capability}|{subject}".encode("utf-8")).hexdigest()[:10]


def providers(org: Organization, capability: str | None) -> tuple[str, ...]:
    """The skills that provide a capability: where a proposal about its work belongs."""
    return tuple(sorted(s.id for s in org.providers_of(capability))) if capability else ()


def _evidence(state: ProjectState, record: FailureRecord) -> dict[str, Any]:
    return {"project": state.project.id, "task": record.task, "attempt": record.attempt, "runs": list(record.runs),
            "evidence": list(record.evidence), "summary": record.summary}


def _grouped(observed: Observed, category: FailureCategory, by_subject: bool) -> dict[tuple, Observed]:
    groups: dict[tuple, Observed] = {}
    for state, record in observed:
        task = state.tasks.get(record.task or "")
        if record.category is category and task is not None:
            groups.setdefault((task.capability, record.subject if by_subject else None), []).append((state, record))
    return {key: rows for key, rows in groups.items() if len({(s.project.id, r.task) for s, r in rows}) >= MIN_TASKS}


def _proposal(rule: str, org: Organization, capability: str | None, subject: str, rows: Observed,
              statement: str, suggestion: str) -> Proposal:
    return Proposal(id=proposal_id(rule, capability, subject), rule=rule, capability=capability, subject=subject,
                    targets=providers(org, capability), statement=statement, suggestion=suggestion, count=len(rows),
                    projects=len({s.project.id for s, _ in rows}), evidence=tuple(_evidence(s, r) for s, r in rows))


@register_proposal_rule("recurring-check-failure")
def recurring_check_failure(org: Organization, observed: Observed) -> list[Proposal]:
    proposals = []
    for (capability, tool), rows in sorted(_grouped(observed, FailureCategory.CHECK_FAILED, True).items(),
                                           key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        tasks = len({(s.project.id, r.task) for s, r in rows})
        proposals.append(_proposal(
            "recurring-check-failure", org, capability, str(tool), rows,
            f"Work for {capability} failed {tool} in {tasks} tasks across "
            f"{len({s.project.id for s, _ in rows})} projects.",
            f"Common failure mode: {tool} fails on submitted work (first seen: {rows[0][1].summary}). "
            f"Procedure: run {tool} on the files you produce before submitting."))
    return proposals


@register_proposal_rule("recurring-review-send-back")
def recurring_review_send_back(org: Organization, observed: Observed) -> list[Proposal]:
    proposals = []
    for (capability, _), rows in sorted(_grouped(observed, FailureCategory.REVIEW_SENT_BACK, False).items(),
                                        key=lambda kv: str(kv[0][0])):
        asked = list(dict.fromkeys(r.summary for _, r in rows))
        proposals.append(_proposal(
            "recurring-review-send-back", org, capability, "review", rows,
            f"Reviews sent work for {capability} back in {len(rows)} submissions.",
            "Validation criterion, from what reviewers asked for: " + " | ".join(asked)))
    return proposals


def proposal_status(states: Iterable[ProjectState], pid: str) -> str:
    return _status(list(states), pid)


def _status(states: list[ProjectState], pid: str) -> str:
    """The latest recorded decision on a proposal, across the projects read: adopted, rejected, or open."""
    status = "open"
    for state in states:
        for entry in state.audit:
            if entry.action != "decision.record":
                continue
            decision = state.decisions.get(entry.details.get("decision", ""))
            if decision is not None and decision.statement.startswith(f"{_PREFIX} {pid}: "):
                status = decision.statement.split(": ", 2)[1]
    return status


def learning_proposals(org: Organization, states: Iterable[ProjectState]) -> list[Proposal]:
    """Every proposal the registered rules make from these projects' failure records, by ID."""
    states = list(states)
    observed = [(state, record) for state in states for record in failure_records(state)]
    proposals = [p for rule in list(_RULES.values()) for p in rule(org, observed)]
    return sorted((Proposal(**{**p.to_dict(), "evidence": p.evidence, "targets": p.targets,
                               "status": _status(states, p.id)}) for p in proposals), key=lambda p: p.id)


def decide_proposal(engine: TaskEngine, proposal: Proposal, actor: Actor, adopt: bool, reason: str) -> Decision:
    """A person's decision on a proposal, recorded in a project it rests on. Changes no skill by itself."""
    if actor.kind is not ActorKind.HUMAN:
        raise ProposalError("only a human may decide a learning proposal: knowledge never changes on a "
                            "model's conclusion")
    if proposal.source == "evaluation":  # rests on recorded evaluation runs, not on any project's records (M42)
        return engine.record_decision(
            actor, DecisionKind.CROSS_TEAM_DECISION, Criticality.MEDIUM,
            statement=f"{_PREFIX} {proposal.id}: {'adopted' if adopt else 'rejected'}: {proposal.statement}",
            rationale=reason)
    project = engine.state.project.id
    mine = [e for e in proposal.evidence if e.get("project") == project]
    if not mine:
        rests_on = ", ".join(sorted({e["project"] for e in proposal.evidence}))
        raise ProposalError(f"{proposal.id} rests on records in {rests_on}; record the decision in one of them")
    return engine.record_decision(
        actor, DecisionKind.CROSS_TEAM_DECISION, Criticality.MEDIUM,
        statement=f"{_PREFIX} {proposal.id}: {'adopted' if adopt else 'rejected'}: {proposal.statement}",
        rationale=reason, evidence=tuple(ev for e in mine for ev in e["evidence"]), task_id=mine[0]["task"])
