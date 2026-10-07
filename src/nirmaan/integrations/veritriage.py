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

Since M20 the bridge is also how an agent seat reaches a language model: the
one M17 provider registry (``veritriage.ai``), its frozen prompt, and its
grounding enforcement. The Anthropic provider is registered into that
registry here, because VeriTriage's own ``ai`` package ships no vendor SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from veritriage.ai import BaseProvider, register_llm_provider
from veritriage.models import GenerationRequest, GenerationResponse, ProviderCapabilities

from nirmaan.events import TOPICS, OrgEvent
from nirmaan.models import list_values
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
    paths = [Path(p) for p in list_values(params.get("paths", ""))]
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


def parse_design(name: str, data: bytes) -> dict:
    """The Design Graph of exactly these bytes, as plain data (M24).

    The bytes are written to a private temporary file (so what is parsed is what
    the caller checked, not whatever the original path holds by now), read by
    VeriTriage's project providers, and turned into a Design Graph. A node's
    ``source_file`` is reported as ``name`` when it is this file.
    """
    import tempfile

    from veritriage.design import build_design_graph
    from veritriage.project import build_project_model

    with tempfile.TemporaryDirectory(prefix="nirmaan-design-") as tmp:
        path = Path(tmp) / Path(name).name
        path.write_bytes(data)
        graph = build_design_graph(build_project_model(path))
        here = str(path)
    return {
        "nodes": [{"id": n.id, "kind": n.kind.value, "name": n.name,
                   "source_file": name if n.source_file == here else n.source_file,
                   "attributes": dict(n.attributes)}
                  for n in sorted(graph.nodes.values(), key=lambda n: n.id)],
        "edges": [{"from": e.source_id, "to": e.target_id, "relation": e.relation.value,
                   "rationale": e.rationale, "inferred": e.inferred} for e in graph.edges],
        "fingerprint": graph.fingerprint(),
    }


def missing_packs(org) -> list[str]:
    """Skill knowledge sources that cite a pack VeriTriage does not ship."""
    catalog = pack_catalog()
    return sorted(
        f"{skill.id} -> {src.ref}"
        for skill in org.skills.values()
        for src in skill.knowledge_sources
        if src.kind.value == "veritriage_pack" and src.ref not in catalog
    )


# --- Language models (M20): the one M17 provider registry, reached from here -------------
#
# A Nirmaan work prompt (``nirmaan.runtime.prompt.WorkPrompt``) is read by duck
# type: ``system``, ``task``, ``sections`` as (heading, lines) pairs, and
# ``citations`` with ``kind``, ``ref``, and ``label``. It becomes a frozen M17
# ``Prompt``, so rendering, generation, and grounding are VeriTriage's own code.


@dataclass(frozen=True)
class Generation:
    text: str
    provider: str
    model: str | None = None
    error: str | None = None


def _llm_prompt(prompt, system: str | None = None):
    from veritriage.models import Citation, Prompt, PromptSection

    return Prompt(
        template_id="nirmaan-work", system=prompt.system if system is None else system, task=prompt.task,
        sections=tuple(PromptSection(heading=h, lines=tuple(lines)) for h, lines in prompt.sections),
        citations=tuple(Citation(kind=c.kind, ref_id=c.ref, label=c.label) for c in prompt.citations),
    )


def render_prompt(prompt) -> str:
    """Exactly the text a provider is handed."""
    return _llm_prompt(prompt).render()


def generate(provider: str, prompt, max_output_chars: int = 64_000) -> Generation:
    """Ask a registered M17 provider. Never raises: a failure is returned."""
    from veritriage.ai import get_llm_provider
    from veritriage.models import GenerationRequest

    try:
        llm = get_llm_provider(provider)
    except KeyError as exc:
        return Generation("", provider, error=str(exc))
    response = llm.generate(GenerationRequest(prompt=_llm_prompt(prompt), max_output_chars=max_output_chars))
    return Generation(response.text, response.provider or provider, response.model,
                      (response.error or "the provider failed") if response.failed else None)


def ground(text: str, prompt) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """M17 grounding: keep citations the prompt declared, strip the rest.

    Returns the cleaned text, the tokens it legitimately used, and the tokens removed.
    """
    from veritriage.ai import grounding

    cleaned, used, stripped = grounding.enforce(text, _llm_prompt(prompt))
    return cleaned, tuple(c.token for c in used), tuple(stripped)


@register_llm_provider
class AnthropicProvider(BaseProvider):
    """Claude, behind the M17 registry. Only used when a person names it.

    The SDK is the optional ``ai`` extra and is imported only when a request is
    made. A refusal or a truncated response is a failed generation, never work.
    """

    name = "anthropic"
    model = "claude-opus-5-5"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(name=self.name, version=self.model, generates=True, deterministic=False,
                                    local=False, max_prompt_chars=400_000, supports_citations=True,
                                    notes="Anthropic Messages API; needs the ai extra and credentials.")

    def _generate(self, request: GenerationRequest) -> GenerationResponse:
        import anthropic

        prompt = request.prompt
        response = anthropic.Anthropic().beta.messages.create(
            model=self.model,
            max_tokens=16_000,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.model_copy(update={"system": ""}).render()}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return GenerationResponse(provider=self.name, model=self.model, failed=True,
                                      error=f"the model stopped with {response.stop_reason}")
        text = "".join(block.text for block in response.content if block.type == "text")
        return GenerationResponse(provider=self.name, model=getattr(response, "model", self.model),
                                  text=text[: request.max_output_chars])
