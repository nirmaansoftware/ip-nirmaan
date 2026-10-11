"""Recommendation reweighting: advice ordered by what actually helped.

The second half of what Milestone 4 designed and left unbuilt. M13 turned
``useful_recommendations`` and ``false_recommendations`` votes into
``RecommendationOutcome`` artifacts and stopped there, on purpose: it said
whether a recommendation is surfaced is "a presentation decision made
later, from data an engineer can inspect". This module is that decision.

Three properties make it safe to apply to a deterministic platform:

* It is a **reorder only**. No action is added, removed, reworded or
  re-rationalized; the same recommendations come out, in a different order.
* It is **deterministic**. A stable sort on (learned usefulness, original
  priority) over a fixed weight table, so the same history and the same run
  always produce the same order.
* It is **inert without history**. An empty weight table returns the input
  list unchanged and identical, so a platform with no learning store behaves
  exactly as it did before this module existed.

Conclusions are untouched: the graph, the classification, the signals and
the ranked hypotheses are all produced upstream and never consulted here.
"""

from __future__ import annotations

from veritriage.models import EngineeringRecommendation, RecommendationOutcome

#: Votes needed before an action's usefulness is allowed to move it at all.
#: One vote is an opinion; the threshold keeps a single bad day from burying
#: advice that is usually right.
MIN_VOTES = 2

#: Neutral weight for an action history has nothing to say about. Unrated
#: advice sorts between the demoted and the promoted rather than last.
NEUTRAL = 0.5


def recommendation_weights(
    outcomes: list[RecommendationOutcome],
) -> dict[str, float]:
    """Action -> learned usefulness, for outcomes with enough votes.

    Actions below :data:`MIN_VOTES` are omitted entirely rather than given a
    provisional weight, so a caller can tell "history has no opinion" from
    "history is neutral".
    """
    weights: dict[str, float] = {}
    for outcome in outcomes:
        if outcome.usefulness is None:
            continue
        if outcome.useful_votes + outcome.false_votes < MIN_VOTES:
            continue
        weights[outcome.action] = outcome.usefulness
    return weights


def reweight_recommendations(
    recommendations: list[EngineeringRecommendation],
    weights: dict[str, float],
) -> list[EngineeringRecommendation]:
    """Reorder recommendations by learned usefulness, highest first.

    Ties, and every action history has no opinion about, keep their original
    relative order, so the deterministic ranking remains the backbone and
    feedback only perturbs it. Priorities are renumbered to stay contiguous.

    Returns the input list unchanged when ``weights`` is empty.
    """
    if not weights or not recommendations:
        return recommendations

    ordered = sorted(
        enumerate(recommendations),
        key=lambda pair: (-weights.get(pair[1].action, NEUTRAL), pair[0]),
    )
    return [
        item.model_copy(update={"priority": rank})
        for rank, (_, item) in enumerate(ordered, start=1)
    ]
