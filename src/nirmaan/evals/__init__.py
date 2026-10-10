"""Seat evaluation (M27): a seat on a real or replayed model, judged by real tool runs.

Run records (M45): trials recorded as evidence, with rates, intervals, and re-judging.
"""

from nirmaan.evals.cases import EvalError, case_digest, load_case, load_cases, validate_case
from nirmaan.evals.records import (
    LIVE_TRIALS,
    EvalRecord,
    Rejudged,
    load_record,
    load_records,
    rate_text,
    record_run,
    record_trial,
    rejudge,
    select_cases,
    summarize,
    wilson,
)
from nirmaan.evals.runner import ReplayLLM, evaluate, replay_llm, run_case, write_result
from nirmaan.evals.scorers import (
    ScoreContext,
    available_scorers,
    register_scorer,
    unregister_scorer,
)

__all__ = [name for name in dir() if not name.startswith("_")]
