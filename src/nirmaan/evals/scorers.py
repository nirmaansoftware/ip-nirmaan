"""Scorers: how a held-out check is judged. A registry, like every other extension point.

A scorer gets the seat's task after its run and a tool handle bound to the
evaluation actor, and returns a :class:`Score`. The runner accepts a pass only
when it cites a successful run recorded in the sandbox, so a scorer cannot
judge by reading text alone.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nirmaan.evals.cases import resolve
from nirmaan.models import Artifact, HeldOutCheck, Score, ScoreStatus, Task
from nirmaan.registry import Registry
from nirmaan.runtime import ToolAccessDenied, ToolHandle
from nirmaan.work import TaskEngine


@dataclass(frozen=True)
class ScoreContext:
    engine: TaskEngine
    task: Task
    check: HeldOutCheck
    repo: Path
    tools: ToolHandle

    def seat_files(self, kinds: tuple[str, ...]) -> list[Artifact]:
        """The seat's submitted files of these kinds, in this order."""
        arts = [self.engine.state.artifacts[a] for a in self.task.artifacts]
        return [a for kind in kinds for a in arts if a.kind == kind and a.location]


Scorer = Callable[[ScoreContext], Score]


@dataclass(frozen=True)
class ScorerSpec:
    fn: Scorer
    requires_tool: bool = False


_SCORERS: MutableMapping[str, ScorerSpec] = Registry("evals.scorers")


def register_scorer(scorer_id: str, requires_tool: bool = False) -> Callable[[Scorer], Scorer]:
    def _register(fn: Scorer) -> Scorer:
        if scorer_id in _SCORERS and _SCORERS[scorer_id].fn is not fn:
            raise ValueError(f"Scorer {scorer_id!r} is already registered")
        _SCORERS[scorer_id] = ScorerSpec(fn, requires_tool)
        return fn

    return _register


def unregister_scorer(scorer_id: str) -> None:
    _SCORERS.pop(scorer_id, None)


def available_scorers() -> list[str]:
    return sorted(_SCORERS)


def scorer_spec(scorer_id: str) -> ScorerSpec | None:
    return _SCORERS.get(scorer_id)


@register_scorer("held-out-run", requires_tool=True)
def held_out_run(ctx: ScoreContext) -> Score:
    """Run the check's tool over the seat's files and the case's held-out files; its result is the score."""
    check = ctx.check

    def score(status: ScoreStatus, summary: str, runs: tuple[str, ...] = ()) -> Score:
        return Score(scorer=check.scorer, name=check.name, status=status, summary=summary, runs=runs)

    values: dict[str, list[str]] = {}
    for param, kinds in check.seat_files.items():
        files = ctx.seat_files(kinds)
        if not files:
            return score(ScoreStatus.NOT_RUN, f"the seat submitted no {' or '.join(kinds)} file")
        values.setdefault(param, []).extend(str(a.location) for a in files)
    for param, paths in check.case_files.items():
        values.setdefault(param, []).extend(str(resolve(ctx.repo, p)) for p in paths)
    params = {**check.params, **values}  # lists: the broker holds them to the tool's contract (M28)
    try:
        run_id, outcome = ctx.tools.invoke(str(check.tool), **params)
    except ToolAccessDenied as exc:
        return score(ScoreStatus.NOT_RUN, f"{check.tool} not run: {exc}")
    status = ScoreStatus.PASSED if outcome.succeeded else ScoreStatus.FAILED
    return score(status, f"{check.tool} {run_id}: {outcome.summary}", (run_id,))
