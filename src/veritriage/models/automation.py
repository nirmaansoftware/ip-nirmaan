"""Automation vocabulary (Milestone 18).

Events, triggers, rules, and action requests. Like every model in this package
these are plain data importing nothing from the graph or engine layers.

The shape encodes the milestone's law. An :class:`ActionRequest` is a *request*
naming a capability the workspace already has, never a callable and never code.
There is no field anywhere here that could carry a script, which is what makes
"actions never execute arbitrary code" structurally true rather than a policy.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventKind(str, Enum):
    """The platform moments worth reacting to.

    Every one of these is already computed deterministically somewhere in the
    platform; M18 publishes them rather than discovering them.
    """

    ANALYSIS_COMPLETED = "analysis_completed"
    REGRESSION_DETECTED = "regression_detected"
    LEARNING_UPDATED = "learning_updated"
    DESIGN_CHANGED = "design_changed"
    PROJECT_UPDATED = "project_updated"
    PROJECT_INDEXED = "project_indexed"
    PLAN_GENERATED = "plan_generated"
    CONVERSATION_STARTED = "conversation_started"
    PROVIDER_FAILURE = "provider_failure"
    WORKSPACE_OPENED = "workspace_opened"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    EVIDENCE_IMPORTED = "evidence_imported"
    #: Supplied by a caller (a CI job, a cron entry someone else owns). The
    #: platform never sleeps, spawns, or polls for this.
    SCHEDULE_TICK = "schedule_tick"
    #: Published by a system beside VeriTriage, through that system's own
    #: integration. ``Event.source`` names the publisher and ``payload["topic"]``
    #: names what happened in the publisher's vocabulary. VeriTriage never
    #: interprets either: only triggers someone registers do.
    EXTERNAL = "external"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class ActionKind(str, Enum):
    """A closed vocabulary of capabilities the workspace already has.

    Closed on purpose. There is no "run this" member and no way to add one
    without editing this enum, so an automation rule cannot reach code the
    platform does not already own.
    """

    RUN_ANALYSIS = "run_analysis"
    GENERATE_REPORT = "generate_report"
    GENERATE_PLAN = "generate_plan"
    REFRESH_LEARNING = "refresh_learning"
    SUMMARIZE_CHANGES = "summarize_changes"
    REBUILD_DESIGN_GRAPH = "rebuild_design_graph"
    EXPORT_BUNDLE = "export_bundle"
    NOTIFY = "notify"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class Event(BaseModel):
    """One thing that happened. Immutable, ordered, content-addressed.

    Immutability is what makes replay, ordering, and audit meaningful: a log
    that can be edited is not a log, a sequence that can be reassigned is not an
    order, and a record of what happened does not change because what happened
    does not change.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    event_id: str = Field(description="Content digest of kind, payload, and sequence.")
    kind: EventKind
    sequence: int = Field(ge=0, description="Monotonic, assigned by the bus.")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="workspace", description="Which layer published it.")
    subject: str | None = Field(
        default=None, description="What it is about: a session, project, or provider ID."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Plain, already-computed facts. Never a raw artifact or a callable.",
    )

    def summary(self) -> str:
        """A printable one-liner, assembled from the payload."""
        detail = ", ".join(f"{k}={v}" for k, v in sorted(self.payload.items()) if v is not None)
        subject = f" [{self.subject}]" if self.subject else ""
        return f"#{self.sequence} {self.kind.display_name}{subject}" + (
            f": {detail}" if detail else ""
        )


def make_event_id(kind: EventKind, payload: dict[str, Any], sequence: int) -> str:
    """Deterministic event ID: same kind, payload, and position yields the same ID."""
    canonical = json.dumps(
        {"kind": kind.value, "payload": payload, "sequence": sequence},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "ev-auto-" + hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


class ActionRequest(BaseModel):
    """A request that something should happen. Never a call, never code."""

    model_config = ConfigDict(frozen=True)

    action: ActionKind
    reason: str = Field(description="Which rule asked for this, and why.")
    subject: str | None = Field(default=None, description="Session, project, or provider.")
    params: dict[str, str] = Field(
        default_factory=dict, description="Plain string parameters only."
    )


class ActionResult(BaseModel):
    """What the workspace did with a request, including declining it."""

    action: ActionKind
    requested_by: str = Field(description="Rule ID that asked.")
    executed: bool = False
    skipped_reason: str | None = None
    detail: str | None = None
    error: str | None = None


class AutomationRule(BaseModel):
    """IF a registered trigger matches, THEN request these actions.

    Structured throughout: ``when`` names a registered trigger and ``then`` is a
    list of enum members. No expression language, no embedded code, nothing to
    evaluate but a lookup.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    description: str
    when: str = Field(description="Registered trigger ID.")
    then: tuple[ActionKind, ...] = Field(description="Actions to request when it matches.")
    enabled: bool = True
    priority: int = Field(default=50, ge=0, description="Lower fires earlier.")


class RuleOutcome(BaseModel):
    """One rule's verdict on one event. Recorded whether or not it fired."""

    rule_id: str
    event_id: str
    event_kind: EventKind
    matched: bool
    reason: str = Field(description="Why it matched, or why it did not.")
    requests: list[ActionRequest] = Field(default_factory=list)
    results: list[ActionResult] = Field(default_factory=list)


class AutomationContext(BaseModel):
    """What automation observed and decided around one analysis.

    Attached to the report as ``AnalysisReport.automation`` by the workspace
    after ``analyze()`` returns, exactly as historical context is. The pipeline
    never touches it, and nothing here can change a conclusion.
    """

    events: list[Event] = Field(default_factory=list)
    outcomes: list[RuleOutcome] = Field(default_factory=list)
    rules_evaluated: int = 0
    rules_fired: list[str] = Field(default_factory=list)
    actions_requested: list[ActionRequest] = Field(default_factory=list)
    actions_executed: list[ActionResult] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.events or self.outcomes)


class AutomationStatus(BaseModel):
    """The state of the automation layer, for discovery and diagnostics."""

    enabled: bool = True
    registered_rules: list[str] = Field(default_factory=list)
    enabled_rules: list[str] = Field(default_factory=list)
    registered_triggers: list[str] = Field(default_factory=list)
    action_vocabulary: list[str] = Field(default_factory=list)
    events_recorded: int = 0
    events_dropped: int = Field(
        default=0, description="Oldest events discarded once the log cap was reached."
    )
    subscribers: int = 0
