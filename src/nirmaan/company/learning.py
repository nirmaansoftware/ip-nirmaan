"""When recorded evaluation results propose a change (M42), as data.

Two failures in the latest five runs of a case on one runtime are a pattern;
one is not. A pass rate over the latest four runs a quarter below the four
before them is a regression. Change these here, in a reviewed pull request.
"""

from __future__ import annotations

from nirmaan.models import EvalProposalThresholds

EVAL_PROPOSAL_THRESHOLDS = EvalProposalThresholds(min_failures=2, within_runs=5, window=4, min_drop=0.25)
