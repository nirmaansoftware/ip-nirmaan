"""Organizational events, derived from the audit trail (M22).

An event is a projection of an audit entry, never a separate claim: the task
engine gets no hook and no listener, and an event exists only because the
engine committed the change that caused it. Each event carries the audit
entry's sequence and hash, so the hash-chained record substantiates it.

Pure: this module imports no VeriTriage. The bridge publishes these onto the
M18 bus (``integrations/veritriage.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nirmaan.models import ProjectState

#: Audit action -> organizational topic. Adding a topic is one row here plus a
#: trigger in the bridge.
TOPICS: dict[str, str] = {
    "task.complete": "task.completed",
    "gate.approve": "gate.approved",
    "escalation.raise": "escalation.raised",
}


@dataclass(frozen=True)
class OrgEvent:
    topic: str
    project: str
    subject: str
    actor: str
    actor_kind: str
    audit_sequence: int
    audit_hash: str
    details: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        """Plain, already-computed facts, as the M18 ``Event.payload`` expects."""
        return {
            "topic": self.topic,
            "project": self.project,
            "actor": self.actor,
            "actor_kind": self.actor_kind,
            "audit_sequence": self.audit_sequence,
            "audit_hash": self.audit_hash,
            **{k: v for k, v in self.details.items() if k != "policy_warnings"},
        }


def org_events(state: ProjectState, since: int = 0) -> list[OrgEvent]:
    """Events for every audit entry at or after ``since``, in audit order."""
    return [
        OrgEvent(
            topic=TOPICS[entry.action],
            project=state.project.id,
            subject=entry.subject,
            actor=entry.actor,
            actor_kind=entry.actor_kind.value,
            audit_sequence=entry.sequence,
            audit_hash=entry.hash,
            details=dict(entry.details),
        )
        for entry in state.audit[since:]
        if entry.action in TOPICS
    ]
