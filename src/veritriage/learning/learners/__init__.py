"""The built-in learner library.

Importing this package registers every built-in learner. Each module is
self-contained and reaches the engine through ``@register_learner`` alone, so
adding an eighth family means adding a module here (or anywhere else) and
nothing more, which ``test_new_learner_needs_only_registration`` proves.
"""

from veritriage.learning.learners.agents import AgentReliabilityLearner
from veritriage.learning.learners.gaps import RuleGapLearner
from veritriage.learning.learners.outcomes import (
    HypothesisHistoryLearner,
    RecommendationOutcomeLearner,
)
from veritriage.learning.learners.patterns import (
    EvidencePatternLearner,
    InvestigationPatternLearner,
)
from veritriage.learning.learners.project import ProjectProfileLearner
from veritriage.learning.learners.protocols import ProtocolStatisticsLearner

__all__ = [
    "AgentReliabilityLearner",
    "EvidencePatternLearner",
    "HypothesisHistoryLearner",
    "InvestigationPatternLearner",
    "ProjectProfileLearner",
    "ProtocolStatisticsLearner",
    "RecommendationOutcomeLearner",
    "RuleGapLearner",
]
