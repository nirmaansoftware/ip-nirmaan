"""Milestone 16: the Conversation Engine.

Covers the milestone's guarantees, not just its features: conversation
navigates and never concludes; every citation resolves; an unknown target is an
honest miss rather than a guess; answers are deterministic; no language model
and no generated prose; the parser declares its vocabulary; nothing is
persisted; and, above all, a brand-new intent needs only a registration (the
crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.conversation.engine as engine_module
from veritriage.conversation import (
    ConversationContext,
    ConversationEngine,
    QuestionHandler,
    available_handlers,
    parse,
    register_handler,
    start_conversation,
    unregister_handler,
    vocabulary,
)
from veritriage.mcp.tools import call_tool
from veritriage.models import (
    Answer,
    ConversationSession,
    Intent,
    NavigationContext,
    Question,
)
from veritriage.pipeline import analyze
from veritriage.project import build_project_model
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/conversation/engine.py -> parents[2] is the src/ root.
SRC = Path(engine_module.__file__).parents[2]


@pytest.fixture()
def outcome(fixture_log):
    """A rich investigation: reasoning, agents, knowledge, plan, and design."""
    model = build_project_model(fixture_log("project/sample.vproj.json").parent)
    return analyze(
        [fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")], project=model
    )


@pytest.fixture()
def engine(outcome):
    return start_conversation(outcome.report, outcome.graph, session_id="ses-test")


# --- The registry -----------------------------------------------------------


def test_every_intent_has_a_handler():
    assert set(available_handlers()) == set(Intent)


def test_duplicate_handler_is_rejected():
    class _Clash(QuestionHandler):
        intent = Intent.WHY

        def answer(self, question, context, navigation):  # pragma: no cover
            raise AssertionError

    with pytest.raises(ValueError, match="already handled"):
        register_handler(_Clash)


# --- The central law: navigates, never concludes ----------------------------


def test_conversation_never_mutates_the_session(outcome, engine):
    before = outcome.report.model_dump(mode="json")
    graph_before = set(outcome.graph.nodes), len(outcome.graph.edges)

    for question in (
        "why is this a testbench issue?",
        "why not rtl_bug",
        "show evidence",
        "show only error",
        "summarize agents",
        "summarize plan",
        "trace the plan",
        "go to scb",
        "help",
    ):
        engine.ask(question)

    assert outcome.report.model_dump(mode="json") == before
    assert (set(outcome.graph.nodes), len(outcome.graph.edges)) == graph_before


def test_conversation_owns_no_intelligence(engine):
    """Every answer restates something; none computes a new conclusion."""
    answer = engine.ask("why is this a testbench issue?")
    assert answer.resolved
    assert answer.references, "an answer must cite what it restates"


def test_every_reference_resolves_to_a_real_artifact(outcome, engine):
    report = outcome.report
    known_hypotheses = {h.id for h in report.reasoning.hypotheses}
    known_agents = {r.agent_id for r in report.agents.results}
    known_plan = {s.step_id for s in report.plan.all_steps()}
    known_patterns = {p.pattern_id for p in (report.knowledge.patterns if report.knowledge else [])}

    for question in (
        "why",
        "why not",
        "show evidence",
        "summarize agents",
        "summarize knowledge",
        "summarize plan",
        "summarize design",
        "trace",
    ):
        answer = engine.ask(question)
        for reference in answer.references:
            kind = reference.kind.value
            if kind == "evidence":
                assert reference.ref_id in outcome.graph.nodes, reference
            elif kind == "hypothesis":
                assert reference.ref_id in known_hypotheses, reference
            elif kind == "agent":
                assert reference.ref_id in known_agents, reference
            elif kind == "plan":
                assert reference.ref_id in known_plan, reference
            elif kind == "knowledge":
                assert reference.ref_id in known_patterns, reference
            assert reference.label, reference


def test_unresolvable_citations_are_stripped_by_the_engine(outcome):
    """The citation law is enforced, not trusted."""

    class _Liar(QuestionHandler):
        intent = Intent.NAVIGATE

        def answer(self, question, context, navigation):
            from veritriage.models import Reference, ReferenceKind

            return (
                Answer(
                    intent=Intent.NAVIGATE,
                    question="q",
                    summary="invented",
                    references=[
                        Reference(
                            kind=ReferenceKind.EVIDENCE, ref_id="ev-phantom", label="nope"
                        )
                    ],
                ),
                navigation,
            )

    unregister_handler(Intent.NAVIGATE)
    register_handler(_Liar)
    try:
        conversation = start_conversation(outcome.report, outcome.graph)
        answer = conversation.ask(Question(intent=Intent.NAVIGATE))
        assert answer.references == [], "a phantom citation must not reach a client"
        assert any("did not resolve" in limit for limit in answer.limitations)
    finally:
        unregister_handler(Intent.NAVIGATE)
        from veritriage.conversation.handlers.navigate import NavigateHandler

        register_handler(NavigateHandler)


def test_answers_are_deterministic(outcome):
    first = start_conversation(outcome.report, outcome.graph).ask("why")
    second = start_conversation(outcome.report, outcome.graph).ask("why")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


# --- Honest misses ----------------------------------------------------------


def test_out_of_vocabulary_declares_what_it_understands(engine):
    answer = engine.ask("what colour is the sky?")
    assert answer.resolved is False
    assert answer.intent is Intent.HELP
    assert answer.sections[0].statements == vocabulary()
    assert any("never guessed" in limit for limit in answer.limitations)


def test_unknown_target_is_an_honest_miss(engine):
    answer = engine.ask("go to no_such_module")
    assert answer.resolved is False
    assert "no_such_module" in answer.summary
    assert answer.limitations


def test_parser_declares_what_it_cannot_answer():
    assert parse("hello there") is None
    assert parse("") is None
    assert vocabulary(), "the vocabulary must be enumerable"


def test_parser_maps_the_declared_vocabulary():
    cases = {
        "why is this rtl": Intent.WHY,
        "why not the testbench": Intent.WHY_NOT,
        "explain the scoreboard": Intent.EXPLAIN,
        "show evidence": Intent.SHOW_EVIDENCE,
        "show only error": Intent.FILTER,
        "compare with reg-1": Intent.COMPARE,
        "trace step-abc": Intent.TRACE,
        "go to l2_cache": Intent.NAVIGATE,
        "summarize design": Intent.SUMMARIZE,
        "help": Intent.HELP,
    }
    for text, intent in cases.items():
        parsed = parse(text)
        assert parsed is not None, text
        assert parsed.intent is intent, text


def test_parser_extracts_targets_and_filters():
    assert parse("summarize design").target == "design"
    assert parse("go to l2_cache").target == "l2_cache"
    assert parse("explain agent protocol").target == "protocol"
    assert parse("show only coverage").filter == "coverage"
    assert parse("show only coverage").target is None


def test_a_broken_handler_never_ends_a_conversation(outcome):
    class _Exploding(QuestionHandler):
        intent = Intent.COMPARE

        def answer(self, question, context, navigation):
            raise RuntimeError("handler is down")

    unregister_handler(Intent.COMPARE)
    register_handler(_Exploding)
    try:
        conversation = start_conversation(outcome.report, outcome.graph)
        answer = conversation.ask(Question(intent=Intent.COMPARE))
        assert answer.resolved is False
        assert "unaffected" in " ".join(answer.limitations)
        # And the conversation continues.
        assert conversation.ask("why").resolved
    finally:
        unregister_handler(Intent.COMPARE)
        from veritriage.conversation.handlers.trace import CompareHandler

        register_handler(CompareHandler)


# --- Navigation -------------------------------------------------------------


def test_navigation_context_carries_between_turns(engine):
    engine.ask("explain agent testbench")
    assert engine.session.context.agent_id == "testbench"
    engine.ask("show only error")
    assert engine.session.context.evidence_filter == "error"
    assert engine.session.context.agent_id == "testbench", "context accumulates"


def test_a_filter_narrows_the_next_answer(engine):
    unfiltered = engine.ask("show evidence")
    engine.ask("show only test_metadata")
    filtered = engine.ask("show evidence")
    assert len(filtered.references) <= len(unfiltered.references)


def test_clearing_the_filter_restores_the_view(engine):
    engine.ask("show only error")
    assert engine.session.context.evidence_filter == "error"
    cleared = engine.ask(Question(intent=Intent.FILTER, filter="all"))
    assert cleared.resolved
    assert engine.session.context.evidence_filter is None


def test_navigation_never_changes_conclusions(outcome, engine):
    top_before = outcome.report.reasoning.hypotheses[0].confidence
    engine.ask("go to scb")
    engine.ask("show only error")
    assert outcome.report.reasoning.hypotheses[0].confidence == top_before


def test_followups_make_navigation_possible_without_prose(engine):
    answer = engine.ask("why")
    assert answer.followups
    for followup in answer.followups:
        assert isinstance(followup, Question)
    # And a suggested follow-up is answerable as given.
    assert engine.ask(answer.followups[0]).intent is answer.followups[0].intent


def test_turns_accumulate_in_order(engine):
    engine.ask("help")
    engine.ask("why")
    assert engine.session.turn_count == 2
    assert [t.index for t in engine.session.turns] == [0, 1]
    assert engine.session.last_answer().intent is Intent.WHY


def test_a_conversation_can_be_resumed_from_its_serialized_form(outcome):
    first = start_conversation(outcome.report, outcome.graph)
    first.ask("explain agent testbench")
    carried = ConversationSession.model_validate_json(first.session.model_dump_json())

    resumed = ConversationEngine(
        ConversationContext(report=outcome.report, graph=outcome.graph), session=carried
    )
    assert resumed.session.context.agent_id == "testbench"
    resumed.ask("why")
    assert resumed.session.turn_count == 2


# --- Cross-layer navigation -------------------------------------------------


def test_why_reaches_reasoning_agents_and_signals(engine):
    answer = engine.ask("why")
    kinds = {r.kind.value for r in answer.references}
    assert "hypothesis" in kinds
    assert {"agent", "evidence"} & kinds


def test_trace_reaches_the_curated_pattern_behind_a_step(engine):
    answer = engine.ask("trace")
    assert answer.resolved
    headings = {s.heading for s in answer.sections}
    assert "Where it came from" in headings
    kinds = {r.kind.value for r in answer.references}
    assert "plan" in kinds


def test_summaries_cover_every_available_layer(engine, outcome):
    for layer in ("evidence", "reasoning", "agents", "knowledge", "plan", "design"):
        answer = engine.ask(f"summarize {layer}")
        assert answer.resolved, layer
        assert answer.sections, layer


def test_summary_of_an_absent_layer_is_honest(fixture_log):
    outcome = analyze(fixture_log("uvm_scoreboard.log"))
    conversation = start_conversation(outcome.report, outcome.graph)
    answer = conversation.ask("summarize design")
    assert answer.resolved is False
    assert answer.limitations


def test_why_not_explains_the_losing_alternatives(engine):
    answer = engine.ask("why not")
    assert answer.resolved
    assert any("Why not" in s.heading for s in answer.sections)


# --- Architecture guards ----------------------------------------------------


def test_no_ai_in_conversation():
    """No language model, no NLP library, no generated prose."""
    banned = (
        "anthropic",
        "openai",
        "torch",
        "spacy",
        "nltk",
        "transformers",
        "embed(",
        "reasoning.ai",
        "AIReasoner",
    )
    for path in (SRC / "veritriage" / "conversation").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_conversation_never_imports_the_workspace():
    """The workspace exposes conversation, not the reverse."""
    for path in (SRC / "veritriage" / "conversation").rglob("*.py"):
        imported = imports(path)
        for banned in (
            "veritriage.workspace",
            "veritriage.pipeline",
            "veritriage.mcp",
            "veritriage.reasoning",
            "veritriage.agents",
            "veritriage.learning",
            "veritriage.planning",
        ):
            assert banned not in imported, f"{path.name} imports {banned}"


def test_conversation_persists_nothing():
    """Navigation state is not intelligence; it does not belong in a store."""
    for path in (SRC / "veritriage" / "conversation").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in ("sqlite3", ".read_text", ".write_text", "open(", "Path("):
            assert term not in text, f"{path.name} performs storage or I/O ({term})"


def test_core_unchanged_by_conversation():
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
        "history",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.conversation" not in imports(path), path


def test_conversation_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "conversation.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


def test_no_report_schema_change_for_conversation(outcome):
    """Conversation is live interaction, not a new report field."""
    assert outcome.report.schema_version == "13"
    assert not hasattr(outcome.report, "conversation")


# --- Clients ----------------------------------------------------------------


def test_services_expose_conversation(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])

    answer, conversation = services.ask(session, "why")
    assert answer.resolved and conversation.turn_count == 1

    # Passing the conversation back continues it.
    answer2, conversation2 = services.ask(session, "show evidence", conversation)
    assert conversation2.turn_count == 2
    assert services.conversation_vocabulary()


def test_conversation_over_mcp(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])
    services.save(session)
    args = {"session_id": session.session_id}

    asked = call_tool(services, "ask", {**args, "question": "why"})
    assert asked["answer"]["resolved"] is True
    assert asked["conversation"]["turns"]

    # The returned conversation is accepted back, which is what makes MCP
    # conversational rather than merely repetitive.
    followup = call_tool(
        services,
        "ask",
        {**args, "question": "show evidence", "conversation": asked["conversation"]},
    )
    assert len(followup["conversation"]["turns"]) == 2

    structured = call_tool(services, "ask", {**args, "intent": "summarize", "target": "agents"})
    assert structured["answer"]["intent"] == "summarize"

    for tool in (
        "explain_finding",
        "explain_hypothesis",
        "explain_rejection",
        "show_supporting_evidence",
        "trace_recommendation",
    ):
        result = call_tool(services, tool, dict(args))
        assert "answer" in result, tool

    assert call_tool(services, "summarize_layer", {**args, "target": "agents"})["answer"]
    assert call_tool(services, "conversation_vocabulary", {})["phrasings"]


# --- The crown jewel: a new intent is a registration and nothing else


class _RiskHandler(QuestionHandler):
    """A throwaway handler for a fictional intent, defined in this test.

    It proves the milestone's success criterion: teaching the platform a new
    kind of question requires writing ONLY a handler. It touches no core
    module, owns no intelligence, and its answer is verified by the same
    citation law as every built-in.
    """

    intent = Intent.COMPARE  # reused slot; restored in the test's finally block

    def answer(self, question, context, navigation):
        from veritriage.models import AnswerSection

        plan = context.report.plan
        risks = list(plan.risks) if plan is not None else []
        return (
            Answer(
                intent=self.intent,
                question=question.text or "what could go wrong",
                summary=f"{len(risks)} risk(s) were recorded for this investigation.",
                sections=[AnswerSection(heading="Risks", statements=risks)],
                references=(
                    [context.plan_ref(s) for s in plan.steps] if plan is not None else []
                ),
            ),
            navigation,
        )


def test_new_intent_needs_only_registration(outcome):
    from veritriage.conversation.handlers.trace import CompareHandler

    unregister_handler(Intent.COMPARE)
    register_handler(_RiskHandler)
    try:
        conversation = start_conversation(outcome.report, outcome.graph)
        answer = conversation.ask(Question(intent=Intent.COMPARE))

        # It ran, with zero changes to the core...
        assert answer.resolved
        assert answer.sections[0].heading == "Risks"
        # ...its citations went through the same verification as any built-in...
        assert all(r.kind.value == "plan" for r in answer.references)
        # ...and the turn was recorded like any other.
        assert conversation.session.turn_count == 1
    finally:
        unregister_handler(Intent.COMPARE)
        register_handler(CompareHandler)
