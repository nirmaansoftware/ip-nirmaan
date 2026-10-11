"""Engineering Context Engine (Milestone 7).

Turns engineering change (commits, CI runs, ownership, issues) into normalized
evidence in the Evidence Graph, gathered by pluggable providers, so VeriTriage
answers "what changed?" before "what broke?". The Verification Intelligence
Core never learns which tool the context came from; providers isolate every
engineering system, and everything downstream is tool-agnostic.

Public surface:

* ``EngineeringContext`` and friends: the normalized model providers produce.
* ``ContextProvider`` + registry: the one-class-per-system extension point.
* ``collect_context``: merge context from every available provider for a root.
* ``EngineeringContextParser``: the artifact entry path (``*.engctx.json``).
* ``emit_engineering_evidence`` / ``engineering_reasoning_rules`` /
  ``build_engineering_view`` / ``augment_with_ownership``: additive graph,
  reasoning, and report integration.
* ``impacted_tests_in_run`` / ``impacted_tests_from_history``: deterministic
  test impact analysis.
* ``diff_against_last_green``: what landed between a failing run and the
  last recorded green one, joined from the regression database and a
  provider range query.

Importing this package registers the built-in providers and the manifest
parser, so ``pipeline.analyze()`` handles a context manifest with no other
setup.
"""

from veritriage.engineering.context import (
    augment_with_ownership,
    build_engineering_view,
    emit_engineering_evidence,
)
from veritriage.engineering.impact import (
    impacted_tests_from_history,
    impacted_tests_in_run,
)
from veritriage.engineering.regression_diff import (
    diff_against_last_green,
    last_green_before,
)
from veritriage.engineering.inference import engineering_reasoning_rules
from veritriage.engineering.investigation import build_investigation
from veritriage.engineering.model import (
    RegressionDiff,
    ChangeCategory,
    ChangedFile,
    CIRun,
    Commit,
    ContextCapability,
    EngineeringContext,
    HistoricalRegression,
    IssueRef,
    Ownership,
)
from veritriage.engineering.parser import EngineeringContextParser, stored_context
from veritriage.engineering.providers import (
    ContextProvider,
    ContextProviderError,
    available_providers,
    collect_context,
    register_provider,
    unregister_provider,
)
from veritriage.engineering.timeline import build_timeline

__all__ = [
    "CIRun",
    "ChangeCategory",
    "ChangedFile",
    "Commit",
    "ContextCapability",
    "ContextProvider",
    "ContextProviderError",
    "EngineeringContext",
    "EngineeringContextParser",
    "HistoricalRegression",
    "IssueRef",
    "Ownership",
    "augment_with_ownership",
    "available_providers",
    "build_engineering_view",
    "build_investigation",
    "build_timeline",
    "collect_context",
    "emit_engineering_evidence",
    "engineering_reasoning_rules",
    "impacted_tests_from_history",
    "RegressionDiff",
    "diff_against_last_green",
    "impacted_tests_in_run",
    "last_green_before",
    "register_provider",
    "stored_context",
    "unregister_provider",
]
