"""The rule-gap learner: where the platform is reliably wrong.

Milestone 4 designed ``FeedbackRecord.diagnosis`` so that a signature whose
regressions are repeatedly marked ``incorrect`` could be flagged as a
candidate for a new rule. M13 built the readers for the recommendation votes
but left the diagnosis verdicts unaggregated. This is that reader.

It is deliberately the least clever learner in the library. It counts
engineer overrules per failure signature and says so. It proposes no rule,
edits no pack, and adjusts no confidence: a gap is an argument for human
attention, and turning one into a pattern is design work, not arithmetic.
"""

from __future__ import annotations

from veritriage.learning.corpus import Corpus
from veritriage.learning.registry import Learner, register_learner
from veritriage.models import LearningArtifact, RuleGap

#: A signature needs this many engineer judgments before a gap is claimed.
#: One overrule is an anecdote; it must be judged more than once to count.
MIN_JUDGED = 2

#: And at least this many of those judgments must have been "incorrect".
MIN_INCORRECT = 2


def compute_rule_gaps(corpus: Corpus) -> list[RuleGap]:
    """Every signature engineers have overruled often enough to flag.

    A free function as well as a learner because two callers need it: the
    Learning Engine, which persists the artifacts, and the analytics
    dashboard, which shows the same list without opening the learning store.
    Both get identical output from identical history.
    """
    by_signature: dict[str, list] = {}
    for record in corpus.failures():
        by_signature.setdefault(record.signature.digest, []).append(record)

    artifacts: list[RuleGap] = []
    for digest in sorted(by_signature):
        group = by_signature[digest]
        judged = [
            r for r in group if corpus.diagnosis(r.regression_id) is not None
        ]
        incorrect = [
            r for r in judged if corpus.diagnosis(r.regression_id) == "incorrect"
        ]
        if len(judged) < MIN_JUDGED or len(incorrect) < MIN_INCORRECT:
            continue

        rate = round(len(incorrect) / len(judged), 4)
        classification = group[0].classification
        causes = sorted(
            {
                cause
                for r in incorrect
                if (cause := corpus.confirmed_cause(r.regression_id)) is not None
            }
        )
        modules = sorted({m for r in group for m in r.signature.modules})
        readable = classification.replace("_", " ")
        summary = (
            f"Engineers overruled this signature in {len(incorrect)} of "
            f"{len(judged)} judged run(s); the platform called it "
            f"{readable} each time."
        )
        if causes:
            summary += f" Reported cause: {causes[0]}"
        summary += " No rule or pack pattern explains it yet."

        artifacts.append(
            RuleGap(
                artifact_id=f"lp-rule_gap-{digest}",
                key=digest,
                summary=summary,
                observations=len(group),
                confidence=Learner._support(len(incorrect), saturation=4),
                supporting_regressions=corpus.cite(incorrect),
                updated_at=corpus.as_of,
                signature=digest,
                classification=classification,
                times_judged=len(judged),
                times_incorrect=len(incorrect),
                incorrect_rate=rate,
                reported_root_causes=causes,
                typical_modules=modules[:6],
                details={
                    "runs_with_this_signature": len(group),
                    "judged_by_an_engineer": len(judged),
                },
            )
        )
    return artifacts


@register_learner
class RuleGapLearner(Learner):
    """Failure signatures engineers keep overruling."""

    learner_id = "rule-gaps"
    artifact_kind = "rule_gap"

    def observe(self, corpus: Corpus) -> list[LearningArtifact]:
        return list(compute_rule_gaps(corpus))
