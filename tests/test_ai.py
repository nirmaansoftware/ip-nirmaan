"""Milestone 17: generative AI providers.

Covers the milestone's guarantees, not just its features: providers render and
never reason; they receive structured artifacts and no platform handles;
grounding is enforced against a deliberately hostile provider; a failing
provider costs prose and nothing else; prompts are pure and inspectable; no
vendor SDK ships; the M12 seam is reused rather than duplicated; and, above
all, a brand-new vendor needs only a registration (the crown-jewel
architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.ai.service as service_module
from veritriage.ai import (
    AIService,
    BaseProvider,
    LlmReasoningProvider,
    PromptContext,
    available_llm_providers,
    available_renderers,
    get_llm_provider,
    grounding,
    register_llm_provider,
    render_answer,
    render_report,
    unregister_llm_provider,
)
from veritriage.ai.providers import MockProvider
from veritriage.ai.renderers import RENDERERS
from veritriage.mcp.tools import call_tool
from veritriage.models import (
    GenerationRequest,
    GenerationResponse,
    ProviderCapabilities,
)
from veritriage.pipeline import analyze
from veritriage.project import build_project_model
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/ai/service.py -> parents[2] is the src/ root.
SRC = Path(service_module.__file__).parents[2]

BUILT_IN = {"null", "deterministic-echo", "mock", "reference"}


@pytest.fixture(autouse=True)
def _clean_mock():
    MockProvider.reset()
    yield
    MockProvider.reset()


@pytest.fixture()
def outcome(fixture_log):
    model = build_project_model(fixture_log("project/sample.vproj.json").parent)
    return analyze(
        [fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")], project=model
    )


# --- The registry -----------------------------------------------------------


def test_four_built_in_providers_register():
    assert BUILT_IN <= set(available_llm_providers())


def test_no_provider_calls_an_external_api():
    """M17 validates the architecture; it ships no vendor integration."""
    for name in BUILT_IN:
        capabilities = get_llm_provider(name).capabilities()
        assert capabilities.local, f"{name} claims to leave the machine"


def test_the_default_provider_generates_nothing():
    """Generation is off by default: the platform is complete without prose."""
    assert get_llm_provider().name == "null"
    assert get_llm_provider().capabilities().generates is False


def test_duplicate_provider_name_is_rejected():
    class _Clash(BaseProvider):
        name = "null"

    with pytest.raises(ValueError, match="already registered"):
        register_llm_provider(_Clash)


def test_unknown_provider_raises_with_the_registered_list():
    with pytest.raises(KeyError, match="Unknown LLM provider"):
        get_llm_provider("no-such-vendor")


# --- The central law: render, never reason ----------------------------------


def test_generation_never_changes_conclusions(outcome):
    before = outcome.report.model_dump(mode="json")
    for provider in ("null", "deterministic-echo", "reference"):
        for renderer in available_renderers():
            if renderer == "conversation-answer":
                continue
            render_report(AIService(provider), outcome.report, renderer)
    assert outcome.report.model_dump(mode="json") == before


def test_providers_receive_no_platform_handles(outcome):
    """A provider's entire input is a frozen prompt. Nothing else crosses."""
    captured: list = []

    class _Recorder(BaseProvider):
        name = "recorder"

        def capabilities(self):
            return ProviderCapabilities(name=self.name)

        def _generate(self, request: GenerationRequest) -> GenerationResponse:
            captured.append(request)
            return GenerationResponse(provider=self.name, text="ok")

    register_llm_provider(_Recorder)
    try:
        render_report(AIService("recorder"), outcome.report)
        assert len(captured) == 1
        request = captured[0]
        assert set(type(request).model_fields) == {"prompt", "max_output_chars"}
        # The prompt is frozen, so a provider cannot mutate even what it was given.
        with pytest.raises(Exception):
            request.prompt.system = "rewritten"
    finally:
        unregister_llm_provider("recorder")


def test_ai_never_reads_raw_artifacts():
    """Structured artifacts only: no file I/O anywhere in the package."""
    banned_calls = (".read_text", ".read_bytes", "open(", "Path(")
    banned_modules = {"pathlib", "os", "io", "subprocess"}
    for path in (SRC / "veritriage" / "ai").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned_calls:
            assert term not in text, f"{path.name} performs file I/O ({term})"
        leaked = banned_modules & imports(path)
        assert not leaked, f"{path.name} imports {leaked}"


def test_no_vendor_sdk_in_ai():
    """No vendor SDK ships in M17; the architecture is validated without one.

    Checked as imports rather than substrings: the docstrings legitimately name
    vendors as future integrations, and a guard that cannot tell a docstring
    from an import is a guard that gets deleted the first time it cries wolf.
    """
    banned = {
        "anthropic",
        "openai",
        "google.generativeai",
        "cohere",
        "litellm",
        "ollama",
        "transformers",
        "httpx",
        "requests",
        "urllib",
        "urllib.request",
        "socket",
    }
    for path in (SRC / "veritriage" / "ai").rglob("*.py"):
        leaked = banned & imports(path)
        assert not leaked, f"{path.name} imports {leaked}"


# --- Grounding --------------------------------------------------------------


def test_invented_citations_are_stripped(outcome):
    """The guarantee, tested against a deliberately hostile provider."""
    MockProvider.invent_citations = True
    view = render_report(AIService("mock"), outcome.report)

    assert view.grounded is False
    assert "[evidence:ev-invented]" in view.stripped_citations
    assert "[design:dn-fabricated]" in view.stripped_citations
    assert "ev-invented" not in view.prose
    assert "dn-fabricated" not in view.prose
    assert any("invented" in limit for limit in view.limitations)


def test_authorized_citations_survive(outcome):
    view = render_report(AIService("reference"), outcome.report)
    assert view.grounded is True
    assert view.citations
    for citation in view.citations:
        assert citation.token in view.prose


def test_enforcement_is_a_pure_function(outcome):
    prompt = AIService.build_prompt("engineer-summary", PromptContext(report=outcome.report))
    allowed = next(iter(prompt.allowed_tokens))
    text = f"Grounded in {allowed} and in [evidence:ev-nope]."
    first = grounding.enforce(text, prompt)
    second = grounding.enforce(text, prompt)
    assert first == second
    assert first[2] == ["[evidence:ev-nope]"]


def test_grounded_ratio_is_reported(outcome):
    prompt = AIService.build_prompt("engineer-summary", PromptContext(report=outcome.report))
    allowed = next(iter(prompt.allowed_tokens))
    assert grounding.grounded_ratio(f"see {allowed}", prompt) == 1.0
    assert grounding.grounded_ratio("see [evidence:ev-nope]", prompt) == 0.0
    assert grounding.grounded_ratio("no citations at all", prompt) == 1.0


def test_ordinary_brackets_are_not_mistaken_for_citations(outcome):
    prompt = AIService.build_prompt("engineer-summary", PromptContext(report=outcome.report))
    text = "The value [1] was observed at [t=500]."
    cleaned, used, stripped = grounding.enforce(text, prompt)
    assert cleaned == text
    assert not used and not stripped


# --- Prompts ----------------------------------------------------------------


def test_prompt_building_is_deterministic(outcome):
    context = PromptContext(report=outcome.report)
    first = AIService.build_prompt("engineer-summary", context)
    second = AIService.build_prompt("engineer-summary", context)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.render() == second.render()


def test_prompts_are_inspectable_before_generation(outcome):
    prompt = AIService.build_prompt("executive-summary", PromptContext(report=outcome.report))
    rendered = prompt.render()
    assert prompt.template_id == "executive-summary"
    assert prompt.citations
    assert "CITE ONLY THESE ARTIFACTS" in rendered
    assert prompt.size == len(rendered)
    # Every declared citation is offered to the provider verbatim.
    for citation in prompt.citations:
        assert citation.token in rendered


def test_prompt_carries_only_structured_artifacts(outcome):
    prompt = AIService.build_prompt("engineer-summary", PromptContext(report=outcome.report))
    headings = {s.heading for s in prompt.sections}
    assert "Verdict" in headings
    assert "Ranked hypotheses" in headings
    # No raw artifact text: the source path never appears as file content.
    assert "\n\nERROR" not in prompt.render()


def test_prompt_citations_resolve_to_real_artifacts(outcome):
    prompt = AIService.build_prompt("engineer-summary", PromptContext(report=outcome.report))
    report, graph = outcome.report, outcome.graph
    known_hypotheses = {h.id for h in report.reasoning.hypotheses}
    for citation in prompt.citations:
        if citation.kind == "evidence":
            assert citation.ref_id in graph.nodes, citation
        elif citation.kind == "hypothesis":
            assert citation.ref_id in known_hypotheses, citation


def test_every_named_renderer_builds_a_prompt(outcome):
    for name, template in RENDERERS.items():
        prompt = AIService.build_prompt(template, PromptContext(report=outcome.report))
        assert prompt.task, name
        assert prompt.system, name


def test_unknown_renderer_is_rejected(outcome):
    with pytest.raises(KeyError, match="Unknown renderer"):
        render_report(AIService("null"), outcome.report, "no-such-view")


# --- Degradation ------------------------------------------------------------


def test_a_failing_provider_costs_only_prose(outcome):
    MockProvider.should_fail = True
    view = render_report(AIService("mock"), outcome.report)

    assert view.is_empty
    assert any("unaffected" in limit for limit in view.limitations)
    # And every deterministic conclusion is exactly where it was.
    assert outcome.report.classification.confidence == 80
    assert outcome.report.reasoning.hypotheses
    assert outcome.report.plan is not None


def test_a_provider_that_raises_is_contained(outcome):
    class _Exploding(BaseProvider):
        name = "exploding"

        def capabilities(self):
            return ProviderCapabilities(name=self.name)

        def _generate(self, request):
            raise RuntimeError("vendor is down")

    register_llm_provider(_Exploding)
    try:
        view = render_report(AIService("exploding"), outcome.report)
        assert view.is_empty
        assert view.limitations
    finally:
        unregister_llm_provider("exploding")


def test_the_null_provider_says_why_it_generated_nothing(outcome):
    view = render_report(AIService("null"), outcome.report)
    assert view.is_empty
    assert any("does not generate" in limit for limit in view.limitations)


def test_an_oversized_prompt_is_refused_not_truncated(outcome):
    class _Tiny(BaseProvider):
        name = "tiny"

        def capabilities(self):
            return ProviderCapabilities(name=self.name, max_prompt_chars=10)

        def _generate(self, request):  # pragma: no cover - never reached
            raise AssertionError("should not have been called")

    register_llm_provider(_Tiny)
    try:
        view = render_report(AIService("tiny"), outcome.report)
        assert view.is_empty
        assert any("budget" in limit for limit in view.limitations)
    finally:
        unregister_llm_provider("tiny")


# --- The M12 bridge ---------------------------------------------------------


def test_reasoning_provider_bridges_to_one_registry(outcome):
    """The M12 seam is reused, not duplicated: one vendor registry serves both."""
    from veritriage.agents.providers import ReasoningProvider, build_request

    bridge = LlmReasoningProvider(AIService("reference"))
    assert isinstance(bridge, ReasoningProvider)

    result = next(r for r in outcome.report.agents.results if r.hypotheses)
    response = bridge.elaborate(build_request(result))
    assert response is not None and response.narrative


def test_the_bridge_returns_nothing_when_generation_is_off(outcome):
    from veritriage.agents.providers import build_request

    bridge = LlmReasoningProvider(AIService("null"))
    result = next(r for r in outcome.report.agents.results if r.hypotheses)
    assert bridge.elaborate(build_request(result)) is None


def test_the_m12_contract_is_untouched():
    """agents/providers.py must not have been edited to accommodate M17."""
    text = (SRC / "veritriage" / "agents" / "providers.py").read_text(encoding="utf-8")
    assert "veritriage.ai" not in text
    assert "class NullProvider" in text and "class DeterministicProvider" in text


def test_the_bridge_cannot_alter_an_agent_result(outcome):
    """Narration through the bridge obeys the M12 law: prose only."""
    from veritriage.agents import AgentCoordinator, build_agent_context

    context = build_agent_context(
        graph=outcome.graph,
        classification=outcome.report.classification,
        reasoning=outcome.report.reasoning,
        knowledge=outcome.report.knowledge,
    )
    plain = AgentCoordinator().coordinate(context)
    narrated = AgentCoordinator(
        provider=LlmReasoningProvider(AIService("reference"))
    ).coordinate(context)

    def conclusions(assessment):
        return [(f.category, f.confidence, tuple(f.supporting_agents)) for f in assessment.findings]

    assert conclusions(narrated) == conclusions(plain)
    assert any(r.narrative for r in narrated.results)


# --- Architecture guards ----------------------------------------------------


def test_core_unchanged_by_ai():
    for package in (
        "graph",
        "parsers",
        "rules",
        "reasoning",
        "knowledge",
        "waveform",
        "engineering",
        "project",
        "design",
        "agents",
        "learning",
        "planning",
        "conversation",
        "history",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.ai" not in imports(path), path


def test_conversation_stays_ai_free():
    """M16's guard must still hold: conversation produces answers, ai renders them."""
    for path in (SRC / "veritriage" / "conversation").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "veritriage.ai" not in text, path


def test_ai_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "ai.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


def test_no_report_schema_change_for_ai(outcome):
    """Generated prose is a view, never a report field."""
    assert outcome.report.schema_version == "13"
    assert not hasattr(outcome.report, "generated")


# --- Rendering the conversation layer ---------------------------------------


def test_conversation_answers_render_with_citations_preserved(outcome):
    from veritriage.conversation import start_conversation

    conversation = start_conversation(outcome.report, outcome.graph)
    answer = conversation.ask("why")
    view = render_answer(AIService("reference"), answer)

    assert view.grounded
    # The structured answer is untouched by rendering.
    assert answer.references
    assert answer.summary


def test_rendering_an_answer_needs_no_report(outcome):
    """A conversation answer is self-sufficient: it already carries its citations."""
    from veritriage.conversation import start_conversation

    answer = start_conversation(outcome.report, outcome.graph).ask("why")
    prompt = AIService.build_prompt("conversation-answer", PromptContext(answer=answer))
    assert prompt.citations
    assert any(s.heading == "Question asked" for s in prompt.sections)


# --- Clients ----------------------------------------------------------------


def test_services_expose_provider_management(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])

    statuses = {s.name: s for s in services.ai_provider_status("reference")}
    assert BUILT_IN <= set(statuses)
    assert statuses["reference"].active is True
    assert statuses["null"].capabilities.generates is False

    assert services.ai_renderers() == available_renderers()
    prompt = services.preview_prompt(session, "executive-summary")
    assert prompt.size > 0
    view = services.render_investigation(session, "engineer-summary", "reference")
    assert view.prose and view.grounded


def test_ai_over_mcp(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])
    services.save(session)
    args = {"session_id": session.session_id}

    status = call_tool(services, "ai_provider_status", {})
    assert {p["name"] for p in status["providers"]} >= BUILT_IN
    assert status["renderers"]

    preview = call_tool(services, "preview_prompt", {**args, "renderer": "engineer-summary"})
    assert preview["size"] > 0 and preview["allowed_citations"]

    # Every rendering tool returns the generated text AND the structured object.
    for tool in (
        "summarize_investigation",
        "explain_investigation_plan",
        "explain_design_context",
    ):
        result = call_tool(services, tool, {**args, "provider": "reference"})
        assert "generated" in result and "structured" in result, tool

    rendered = call_tool(
        services,
        "render_conversation_answer",
        {**args, "question": "why", "provider": "reference"},
    )
    assert rendered["answer"]["resolved"] is True
    assert "generated" in rendered


def test_generation_off_by_default_over_mcp(tmp_path, fixture_log):
    """Without naming a provider, MCP generates nothing and says so."""
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])
    services.save(session)

    result = call_tool(
        services, "summarize_investigation", {"session_id": session.session_id}
    )
    assert result["generated"]["prose"] == ""
    assert result["structured"]["classification"] == "testbench_failure"


# --- The crown jewel: a new vendor is a registration and nothing else


class _AcmeProvider(BaseProvider):
    """A throwaway vendor integration, defined entirely in this test.

    It proves the milestone's success criterion: supporting a new generative
    vendor requires writing ONLY a provider. It touches no core module, and its
    output is grounded by the same enforcement as every built-in.
    """

    name = "acme"
    model = "acme-large"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name, version="9.9.9", deterministic=True, local=False
        )

    def _generate(self, request: GenerationRequest) -> GenerationResponse:
        cited = " ".join(c.token for c in request.prompt.citations[:2])
        return GenerationResponse(
            provider=self.name,
            model=self.model,
            text=f"ACME rendering. Grounded in {cited}. Also [evidence:ev-hallucinated].",
        )


def test_new_provider_needs_only_registration(outcome, tmp_path, fixture_log):
    register_llm_provider(_AcmeProvider)
    try:
        assert "acme" in available_llm_providers()

        # It renders, with zero changes to the core...
        view = render_report(AIService("acme"), outcome.report)
        assert view.provider == "acme"
        assert view.prose

        # ...its hallucination is stripped by the same enforcement as any built-in...
        assert view.grounded is False
        assert "[evidence:ev-hallucinated]" in view.stripped_citations
        assert "ev-hallucinated" not in view.prose

        # ...its legitimate citations survived...
        assert view.citations

        # ...it appears in discovery, honestly declaring it is not local...
        statuses = {s.name: s for s in AIService("acme").status()}
        assert statuses["acme"].capabilities.local is False
        assert statuses["acme"].active is True

        # ...and it serves the M12 agent seam through the same registry.
        from veritriage.agents.providers import build_request

        result = next(r for r in outcome.report.agents.results if r.hypotheses)
        bridged = LlmReasoningProvider(AIService("acme")).elaborate(build_request(result))
        assert bridged is not None and bridged.narrative
    finally:
        unregister_llm_provider("acme")
