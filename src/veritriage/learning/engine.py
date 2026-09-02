"""The Learning Engine: observe recorded history, recall it for the next run.

Two phases, deliberately mirroring the ``HistoryEngine.record`` / ``augment``
split proven in M4:

* :meth:`observe` runs every registered learner over the whole corpus and
  replaces the stored artifacts. Pure: same history in, byte-identical
  artifacts out, regardless of when it runs or what order runs arrived in.
* :meth:`recall` projects the stored artifacts into a :class:`LearningContext`
  for one upcoming investigation, and :meth:`augment` attaches the
  signature-specific part once the run has produced one.

The engine remembers. It does not decide. Everything it emits is a hint or a
bounded calibration multiplier, both of which carry the regression IDs they
were learned from, and neither of which can create a hypothesis, change a
classification, or touch the Evidence Graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from veritriage.feedback.reweight import recommendation_weights
from veritriage.learning.calibration import calibration_map
from veritriage.learning.corpus import Corpus
from veritriage.learning.persistence import LearningStore
from veritriage.learning.registry import Learner, available_learners, default_learners
from veritriage.models import (
    AgentReliability,
    AnalysisReport,
    InvestigationPattern,
    LearningContext,
    LearningHint,
    LearningStatistics,
    ProjectProfile,
    RecommendationOutcome,
    RuleGap,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from veritriage.feedback import FeedbackRecord
    from veritriage.history.record import RegressionRecord

#: Hints below this support strength are not worth an engineer's attention.
MIN_HINT_STRENGTH = 0.2

#: Bounds on what one recall surfaces, so a large corpus stays readable.
MAX_HINTS = 8
MAX_COMMON_RECOMMENDATIONS = 5


class LearningEngine:
    """Derives learning artifacts from history and recalls them for a run."""

    def __init__(self, store: LearningStore, learners: list[Learner] | None = None) -> None:
        self._store = store
        self._learners = learners  # None -> registry defaults, resolved per call

    # --- Phase one: observe -------------------------------------------------

    def observe(
        self,
        records: Sequence["RegressionRecord"],
        feedback: Sequence["FeedbackRecord"] = (),
    ) -> LearningStatistics:
        """Recompute every artifact from the corpus and replace what is stored.

        Wholesale recomputation is the normal path, not an expensive fallback:
        it is what makes the milestone's purity law hold and what lets a
        corrected `FeedbackRecord` immediately fix every artifact it touches.
        """
        corpus = Corpus(records, feedback)
        learners = self._learners if self._learners is not None else default_learners()
        artifacts = []
        for learner in sorted(learners, key=lambda item: item.learner_id):
            artifacts.extend(learner.observe(corpus))
        artifacts.sort(key=lambda a: a.artifact_id)
        self._store.replace_all(
            artifacts,
            corpus_size=len(corpus),
            feedback_count=len(corpus.feedback),
            generated_at=corpus.as_of,
        )
        return self.statistics()

    # --- Phase two: recall --------------------------------------------------

    def recall(self, project_key: str | None = None) -> LearningContext:
        """What history suggests for an upcoming investigation.

        Called before an analysis, so it carries everything that does not
        depend on this run's outcome: agent reliability and its calibration,
        the project profile, and the recommendations that have historically
        helped. The signature-specific part arrives later, via :meth:`augment`.
        """
        reliability = [
            a for a in self._store.by_kind("agent_reliability") if isinstance(a, AgentReliability)
        ]
        profile = self._project_profile(project_key)
        common = [
            a
            for a in self._store.by_kind("recommendation_outcome")
            if isinstance(a, RecommendationOutcome)
            and a.usefulness is not None
            and a.usefulness >= 0.5
        ]
        common.sort(key=lambda a: (-a.useful_votes, a.action))
        # Every rated outcome, not only the helpful ones: reordering advice
        # needs to know what wasted time as much as what helped.
        rated = [
            a
            for a in self._store.by_kind("recommendation_outcome")
            if isinstance(a, RecommendationOutcome)
        ]
        gaps = [a for a in self._store.by_kind("rule_gap") if isinstance(a, RuleGap)]
        gaps.sort(key=lambda a: (-a.times_incorrect, a.signature))

        hints: list[LearningHint] = []
        if profile is not None and profile.observations > 0:
            hints.append(
                LearningHint(
                    kind=profile.kind,
                    statement=profile.summary,
                    strength=profile.confidence,
                    artifact_id=profile.artifact_id,
                    supporting_regressions=list(profile.supporting_regressions),
                )
            )
        # Recurring failure modes and evidence combinations are recalled in
        # full, before the run has a signature of its own, so agents receive
        # them as memory rather than only seeing them in the finished report.
        # `augment` later promotes the one that matches this run's signature.
        for kind in ("investigation_pattern", "evidence_pattern"):
            for artifact in self._store.by_kind(kind):
                hints.append(
                    LearningHint(
                        kind=artifact.kind,
                        statement=artifact.summary,
                        strength=artifact.confidence,
                        artifact_id=artifact.artifact_id,
                        supporting_regressions=list(artifact.supporting_regressions),
                    )
                )
        for artifact in sorted(reliability, key=lambda a: a.agent_id):
            if artifact.accuracy is None:
                continue
            hints.append(
                LearningHint(
                    kind=artifact.kind,
                    statement=artifact.summary,
                    strength=artifact.confidence,
                    artifact_id=artifact.artifact_id,
                    supporting_regressions=list(artifact.supporting_regressions),
                )
            )

        return LearningContext(
            generated_at=self._store.meta("generated_at"),
            corpus_size=int(self._store.meta("corpus_size", "0") or 0),
            hints=_rank_hints(hints),
            agent_reliability=sorted(reliability, key=lambda a: a.agent_id),
            project_profile=profile,
            common_recommendations=common[:MAX_COMMON_RECOMMENDATIONS],
            recommendation_weights=recommendation_weights(rated),
            rule_gaps=gaps,
            calibration=calibration_map(reliability),
        )

    def augment(self, report: AnalysisReport, signature_digest: str) -> None:
        """Attach the signature-specific memory once the run has a signature.

        Additive, and strictly to ``report.learning``: nothing in the
        classification, the reasoning result, or the agent assessment is
        touched. Mirrors ``HistoryEngine.augment``.
        """
        context = report.learning
        if context is None:
            return
        pattern = self._store.by_key("investigation_pattern", signature_digest)
        if pattern is None or not isinstance(pattern, InvestigationPattern):
            return
        context.recurring_pattern = pattern
        hint = LearningHint(
            kind=pattern.kind,
            statement=pattern.summary,
            strength=pattern.confidence,
            artifact_id=pattern.artifact_id,
            supporting_regressions=list(pattern.supporting_regressions),
        )
        context.hints = _rank_hints([hint, *context.hints])

    # --- Introspection ------------------------------------------------------

    def statistics(self) -> LearningStatistics:
        return self._store.statistics(learners=sorted(available_learners()))

    def artifacts(self, kind: str | None = None):
        return self._store.by_kind(kind) if kind else self._store.all_artifacts()

    def _project_profile(self, project_key: str | None) -> ProjectProfile | None:
        for key in (project_key, "unscoped"):
            if key is None:
                continue
            found = self._store.by_key("project_profile", key)
            if isinstance(found, ProjectProfile):
                return found
        return None


def _rank_hints(hints: list[LearningHint]) -> list[LearningHint]:
    """Strongest first, deduplicated by artifact, bounded, deterministic."""
    seen: set[str] = set()
    kept: list[LearningHint] = []
    for hint in sorted(hints, key=lambda h: (-h.strength, h.artifact_id)):
        if hint.strength < MIN_HINT_STRENGTH or hint.artifact_id in seen:
            continue
        seen.add(hint.artifact_id)
        kept.append(hint)
    return kept[:MAX_HINTS]
