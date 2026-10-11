"""Knowledge inference: how structured knowledge reaches reasoning and reports.

Two integration surfaces, both additive:

1. **Reasoning signals.** ``knowledge_reasoning_rules()`` wraps every failure
   pattern in a standard :class:`ReasoningRule`, so matched knowledge
   contributes ranking weight through the exact same interface as the
   built-in rules. The reasoning engine does not know knowledge exists; it
   just receives more rules. Knowledge is evidence, not hidden prompt text.

2. **Report context.** ``KnowledgeEngine.analyze()`` produces the
   :class:`KnowledgeContext` embedded in the report: matched patterns with
   causes/ownership/signals/references, matched concepts, the state-machine
   projection, and the suggested playbooks.

Nothing here touches an LLM: the module imports no AI code, performs no I/O,
and is fully deterministic.
"""

from __future__ import annotations

import weakref

from veritriage.graph.graph import EvidenceGraph
from veritriage.knowledge.graph import KnowledgeGraph
from veritriage.knowledge.matcher import (
    PatternMatch,
    best_projection,
    match_concepts,
    match_patterns,
)
from veritriage.models import (
    HypothesisCategory,
    KnowledgeContext,
    KnowledgeReference,
    MatchedConcept,
    MatchedPattern,
    PlaybookStepView,
    PlaybookView,
    ReasoningSignal,
    WorkingSet,
)
from veritriage.references.resolve import resolve_references
from veritriage.reasoning.signals import ReasoningRule

#: Ownership -> the hypothesis category it corroborates (for display only;
#: ranking weights come from each pattern's explicit confidence_modifiers).
_OWNERSHIP_LABEL = {
    "design": "design (RTL)",
    "testbench": "testbench / verification environment",
    "infrastructure": "infrastructure / compute environment",
    "build": "build / compile flow",
}


class _SharedMatchPass:
    """One match pass shared by every pattern rule built together.

    There is one :class:`KnowledgePatternRule` per known failure pattern, and
    each needs the same ``match_patterns`` result for the same graph. Calling
    it per rule made the knowledge stage quadratic in pattern count: with 100
    patterns, one analysis ran 100 full passes over every pattern, clause and
    node to use one row of each. This memo makes it one pass.

    The graph is held by a **weak** reference and compared by **identity**, so
    a collected graph is never kept alive and a recycled address can never be
    mistaken for the graph that produced the cached matches: the weak
    reference dies with the object and the comparison then fails.

    Scope: one Evidence Graph, unmutated. ``pipeline.analyze()`` builds the
    rules per run and never mutates the graph after ``builder.build()``, which
    is the only path the platform itself uses. Because
    ``knowledge_reasoning_rules()`` is public, the shape of the graph is
    checked too, so rules held across analyses of a graph that grew do not
    silently reason from the previous pass. That check is a guard, not a
    guarantee: a mutation that leaves node and edge counts unchanged would
    not be caught, so do not reuse rules across mutations of one graph.
    """

    __slots__ = ("_ref", "_shape", "_matches")

    def __init__(self) -> None:
        self._ref: weakref.ref | None = None
        self._shape: tuple[int, int] = (-1, -1)
        self._matches: list[PatternMatch] = []

    def matches(self, knowledge: KnowledgeGraph, graph: EvidenceGraph) -> list[PatternMatch]:
        cached = self._ref() if self._ref is not None else None
        shape = (len(graph.nodes), len(graph.edges))
        if cached is not graph or shape != self._shape:
            self._matches = match_patterns(knowledge, graph)
            self._shape = shape
            try:
                self._ref = weakref.ref(graph)
            except TypeError:  # pragma: no cover - defensive
                self._ref = None
        return self._matches


class KnowledgePatternRule(ReasoningRule):
    """Adapter: one failure pattern exposed as a standard reasoning rule.

    When the pattern matches the working set's evidence, it emits one signal
    whose weights are the pattern's confidence modifiers and whose evidence
    IDs are the nodes that satisfied the clauses. Signals never conclude;
    like every other rule, knowledge only shifts hypothesis ranking.
    """

    def __init__(
        self,
        knowledge: KnowledgeGraph,
        pattern_id: str,
        shared: "_SharedMatchPass | None" = None,
    ) -> None:
        self._knowledge = knowledge
        self._pattern_id = pattern_id
        # Rules built together share one pass; a rule built alone gets its own,
        # so the constructor stays usable on its own exactly as before.
        self._shared = shared if shared is not None else _SharedMatchPass()
        self.name = f"knowledge:{pattern_id}"

    def evaluate(self, graph: EvidenceGraph, working_set: WorkingSet) -> ReasoningSignal | None:
        match = next(
            (
                m
                for m in self._shared.matches(self._knowledge, graph)
                if m.pattern.id == self._pattern_id
            ),
            None,
        )
        if match is None or not match.pattern.confidence_modifiers:
            return None
        weights = {
            HypothesisCategory(category): weight
            for category, weight in match.pattern.confidence_modifiers.items()
        }
        evidence_ids = sorted({i for ids in match.matched_evidence.values() for i in ids})
        return ReasoningSignal(
            name=self.name,
            description=(
                f"Known verification pattern '{match.pattern.name}' "
                f"({match.pack.name} pack): {match.pattern.summary}"
            ),
            evidence_ids=evidence_ids,
            weights=weights,
            confidence=match.score,
        )


def knowledge_reasoning_rules(knowledge: KnowledgeGraph | None = None) -> list[ReasoningRule]:
    """One reasoning rule per known failure pattern, in deterministic order."""
    knowledge = knowledge or KnowledgeGraph.build()
    shared = _SharedMatchPass()
    return [
        KnowledgePatternRule(knowledge, pattern.id, shared)
        for _, pattern in sorted(knowledge.patterns(), key=lambda pair: pair[1].id)
    ]


class KnowledgeEngine:
    """Builds the report-facing knowledge context for one Evidence Graph."""

    def __init__(self, knowledge: KnowledgeGraph | None = None) -> None:
        self.knowledge = knowledge or KnowledgeGraph.build()

    def analyze(self, graph: EvidenceGraph) -> KnowledgeContext:
        matches = match_patterns(self.knowledge, graph)
        concepts = match_concepts(self.knowledge, graph)
        projection = best_projection(self.knowledge, graph)
        return KnowledgeContext(
            pack_versions=self.knowledge.pack_versions(),
            concepts=[
                MatchedConcept(
                    concept_id=c.concept.id,
                    name=c.concept.name,
                    pack=c.pack.id,
                    summary=c.concept.summary,
                    evidence_ids=c.evidence_ids[:6],
                )
                for c in concepts
            ],
            patterns=[self._pattern_view(m) for m in matches],
            state_projection=projection,
        )

    def _pattern_view(self, match: PatternMatch) -> MatchedPattern:
        playbook = None
        resolved = self.knowledge.playbook_for(match.pattern.id)
        if resolved is not None:
            pack, pb = resolved
            playbook = PlaybookView(
                playbook_id=pb.id,
                name=pb.name,
                pack=pack.id,
                steps=[
                    PlaybookStepView(
                        order=i, action=step.action, detail=step.detail, signals=step.signals
                    )
                    for i, step in enumerate(pb.steps, start=1)
                ],
            )
        return MatchedPattern(
            pattern_id=match.pattern.id,
            name=match.pattern.name,
            pack=match.pack.id,
            pack_version=match.pack.version,
            score=match.score,
            summary=match.pattern.summary,
            matched_evidence=match.matched_evidence,
            typical_causes=match.pattern.typical_causes,
            ownership=_OWNERSHIP_LABEL.get(match.pattern.ownership, match.pattern.ownership),
            suggested_signals=match.pattern.suggested_signals,
            references=[
                KnowledgeReference(
                    source=r.source, section=r.section, note=r.note, uri=r.uri
                )
                # Citations become links here, at the report boundary, so the
                # packs themselves stay plain data and the resolver seam is
                # the only thing that knows about URIs.
                for r in resolve_references(list(match.pattern.references))
            ],
            playbook=playbook,
        )
