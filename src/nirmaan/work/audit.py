"""The audit trail: append-only, hash-chained, verifiable.

Every state change the task engine makes appends one entry whose hash covers
its content and the previous entry's hash. Editing, reordering, or dropping an
entry breaks the chain, and ``verify_chain`` says exactly where. This is what
makes constitution articles 10 and 11 (no hidden state changes; work remains
auditable) checkable facts rather than intentions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

from nirmaan.models import Actor, AuditEntry

GENESIS = "0" * 64


def _digest(sequence: int, at: datetime, actor: str, actor_kind: str, action: str, subject: str,
            reason: str, details: dict[str, Any], previous_hash: str) -> str:
    payload = json.dumps(
        {
            "sequence": sequence,
            "at": at.isoformat(),
            "actor": actor,
            "actor_kind": actor_kind,
            "action": action,
            "subject": subject,
            "reason": reason,
            "details": details,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append(
    trail: list[AuditEntry],
    at: datetime,
    actor: Actor,
    action: str,
    subject: str,
    reason: str = "",
    details: dict[str, Any] | None = None,
) -> list[AuditEntry]:
    """A new trail with one more entry. The input trail is never modified."""
    previous = trail[-1].hash if trail else GENESIS
    sequence = len(trail)
    details = dict(details or {})
    entry = AuditEntry(
        sequence=sequence,
        at=at,
        actor=actor.label,
        actor_kind=actor.kind,
        action=action,
        subject=subject,
        reason=reason,
        details=details,
        previous_hash=previous,
        hash=_digest(sequence, at, actor.label, actor.kind.value, action, subject, reason, details, previous),
    )
    return [*trail, entry]


def verify_chain(trail: Iterable[AuditEntry], start: int = 0, previous: str = GENESIS) -> list[str]:
    """Every break in the chain, as a human-readable problem. Empty means intact.

    ``start`` and ``previous`` verify only the entries from ``start`` on, after
    an already-verified prefix whose last hash is ``previous`` (M32): the engine
    verifies a trail once in full, then each operation's new entries.
    """
    problems: list[str] = []
    entries = list(trail)
    if start:
        if len(entries) < start or entries[start - 1].hash != previous:
            return [f"the verified prefix of {start} entries changed (entries removed or replaced)"]
    else:
        previous = GENESIS
    for index, entry in enumerate(entries[start:], start=start):
        if entry.sequence != index:
            problems.append(f"entry {index}: sequence {entry.sequence} out of order")
        if entry.previous_hash != previous:
            problems.append(f"entry {index}: previous-hash mismatch (entry removed or reordered)")
        expected = _digest(
            entry.sequence, entry.at, entry.actor, entry.actor_kind.value, entry.action, entry.subject,
            entry.reason, entry.details, entry.previous_hash,
        )
        if entry.hash != expected:
            problems.append(f"entry {index}: content does not match its hash (edited)")
        previous = entry.hash
    return problems
