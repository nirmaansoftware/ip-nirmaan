"""The VeriTriage bridge: the ONLY module in Nirmaan that imports VeriTriage.

VeriTriage is IP Nirmaan's verification-intelligence subsystem. The
organization reaches it here and nowhere else (a test enforces the law), and
only through its stable public surfaces: ``WorkspaceServices``, the
Knowledge Pack registry, and the M18 automation registries (organizational
events, M22). VeriTriage itself never imports Nirmaan.

What crosses the bridge is real: ``veritriage.investigate`` runs the full
deterministic pipeline and returns a session ID that a VERITRIAGE_SESSION
evidence record cites, which is how an organizational claim ("the regression
failure was triaged") becomes traceable into an Evidence Graph.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from nirmaan.events import TOPICS, OrgEvent
from nirmaan.runtime.tools import ToolOutcome, register_binding
from nirmaan.work.engine import TaskEngine

#: ``Event.source`` for everything IP Nirmaan publishes on the M18 bus.
SOURCE = "nirmaan"


def _services(params: dict[str, str]):
    from veritriage.workspace import WorkspaceServices

    root = params.get("workspace")
    return WorkspaceServices(session_root=Path(root) / "sessions" if root else None)


@register_binding("veritriage.investigate")
def investigate(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    paths = [Path(p) for p in params.get("paths", "").split(",") if p.strip()]
    if not paths:
        return ToolOutcome(False, "no artifact paths given")
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        return ToolOutcome(False, f"artifacts not found: {', '.join(missing)}")
    services = _services(params)
    session = services.investigate(paths, record_history=False, automate=False, learn=False)
    services.save(session)
    summary = services.summary(session)
    top = f"; top hypothesis: {summary.top_hypothesis}" if summary.top_hypothesis else ""
    return ToolOutcome(
        True,
        f"VeriTriage classified {', '.join(p.name for p in paths)} as {summary.classification} "
        f"({summary.confidence}% confidence, {summary.evidence_nodes} evidence nodes){top}",
        references=(session.session_id,),
        data=summary.model_dump(mode="json"),
    )


@register_binding("veritriage.explain_log")
def explain_log(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    path = Path(params.get("path", ""))
    if not path.is_file():
        return ToolOutcome(False, f"no such log: {path}")
    annotations = _services(params).explain_log(path)
    return ToolOutcome(True, f"{len(annotations)} annotated regions in {path.name}",
                       data={"annotations": [a.model_dump(mode="json") for a in annotations]})


@register_binding("knowledge.search")
def search(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    hits = _services(params).search_knowledge(params.get("query", ""))
    return ToolOutcome(True, f"{len(hits)} knowledge hits",
                       references=tuple(f"{h.pack}:{h.id}" for h in hits[:20]),
                       data={"hits": [h.model_dump(mode="json") for h in hits[:20]]})


def engine_version() -> str:
    """The installed VeriTriage engine's version."""
    import veritriage

    return veritriage.__version__


@lru_cache(maxsize=1)
def pack_catalog() -> dict[str, dict[str, str]]:
    """Registered VeriTriage Knowledge Packs: id -> name, domain, summary."""
    from veritriage.knowledge.registry import load_packs

    return {p.id: {"name": p.name, "domain": p.domain, "summary": p.summary} for p in load_packs()}


def _register_event_vocabulary() -> None:
    """Organizational triggers and the shipped rule, on VeriTriage's M18 registries.

    Organizational events travel as ``EventKind.EXTERNAL`` with
    ``source="nirmaan"``; these triggers are Nirmaan's vocabulary for them, so
    they live on this side of the bridge (see docs/NIRMAAN_MCP.md).
    """
    from veritriage.automation import Trigger, available_triggers, register_rule, register_trigger
    from veritriage.models import ActionKind, AutomationRule, EventKind

    for topic in TOPICS.values():
        trigger_id = "nirmaan." + topic.replace(".", "_")
        if trigger_id in available_triggers():
            continue

        def matches(self, event, _topic=topic):
            if event.source == SOURCE and event.payload.get("topic") == _topic:
                return True, f"IP Nirmaan: {_topic} ({event.subject})"
            return False, f"not an IP Nirmaan {_topic} event"

        register_trigger(type(
            f"OrgTrigger_{trigger_id}", (Trigger,),
            {"trigger_id": trigger_id, "kind": EventKind.EXTERNAL,
             "description": f"IP Nirmaan published {topic}.", "matches": matches},
        ))
    register_rule(AutomationRule(
        rule_id="nirmaan-escalation-raised",
        description="An IP Nirmaan escalation was raised. Surface it to whoever it is routed to.",
        when="nirmaan.escalation_raised",
        then=(ActionKind.NOTIFY,),
        priority=35,
    ))


class AutomationBridge:
    """Publishes organizational events onto a VeriTriage workspace's M18 bus.

    Each event is evaluated by the registered automation rules and whatever
    they request is dispatched by the workspace, which executes only its own
    closed action vocabulary. Returns the reactions as plain data.
    """

    def __init__(self, services=None) -> None:
        self._services = services

    @property
    def services(self):
        if self._services is None:
            from veritriage.workspace import WorkspaceServices

            self._services = WorkspaceServices()
        return self._services

    def publish(self, events: list[OrgEvent]) -> list[dict]:
        from veritriage.automation import RuleEngine
        from veritriage.models import EventKind

        reactions = []
        for org_event in events:
            event = self.services.events.publish(
                EventKind.EXTERNAL, org_event.payload(), subject=org_event.subject, source=SOURCE
            )
            outcomes = [o for o in RuleEngine().evaluate(event) if o.matched]
            requests = [r for o in outcomes for r in o.requests]
            results = self.services.dispatch_actions(requests) if requests else []
            reactions.append({
                "event_id": event.event_id,
                "sequence": event.sequence,
                "topic": org_event.topic,
                "subject": org_event.subject,
                "rules_fired": [o.rule_id for o in outcomes],
                "actions": [r.model_dump(mode="json") for r in results],
            })
        return reactions

    def recent(self, limit: int = 50) -> list[dict]:
        """Organizational events recorded on the bus, oldest first."""
        from veritriage.models import EventKind

        return [
            e.model_dump(mode="json")
            for e in self.services.events.events(kind=EventKind.EXTERNAL)
            if e.source == SOURCE
        ][-limit:]


_register_event_vocabulary()


def missing_packs(org) -> list[str]:
    """Skill knowledge sources that cite a pack VeriTriage does not ship."""
    catalog = pack_catalog()
    return sorted(
        f"{skill.id} -> {src.ref}"
        for skill in org.skills.values()
        for src in skill.knowledge_sources
        if src.kind.value == "veritriage_pack" and src.ref not in catalog
    )
