"""Scorers: how a held-out check is judged. A registry, like every other extension point.

A scorer gets the seat's task after its run and a tool handle bound to the
evaluation actor, and returns a :class:`Score`. The runner accepts a pass only
when it cites a successful run recorded in the sandbox, so a scorer cannot
judge by reading text alone.
"""

from __future__ import annotations

import shutil
import tempfile
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
    #: A folder inside the evaluation's sandbox for this check's own files, kept with the record the runs are
    #: in. None when the caller gives no sandbox: a scorer then cleans up whatever it stages.
    work: Path | None = None

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


# --- Negative controls (M58) -------------------------------------------------------------------


def _values(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]


def _declared_entry(ctx: ScoreContext, param: str, kinds: tuple[str, ...]) -> str | None:
    """The value the seat's own latest passing run over one of its files of these kinds gave ``param``."""
    files = {str(a.location) for a in ctx.seat_files(kinds)}
    for run in reversed(list(ctx.engine.state.tool_runs.values())):
        if run.task == ctx.task.id and run.succeeded and param in run.params and not files.isdisjoint(
                v for value in run.params.values() for v in _values(value)):
            return str(run.params[param])
    return None


def _stage(where: Path, inputs: dict[str, list[Path]], swap: tuple[Path, Path] | None) -> dict[str, list[str]]:
    """Copy every input into ``where`` under its own name, with ``swap`` = (case file, mutant) applied.

    A setup that names its files relative to itself (a proof's job file) then reads the mutant in place.
    """
    where.mkdir(parents=True)
    staged: dict[str, list[str]] = {}
    for param, paths in inputs.items():
        for path in paths:
            source = swap[1] if swap and path == swap[0] else path
            target = where / path.name
            shutil.copyfile(source, target)
            staged.setdefault(param, []).append(str(target))
    return staged


@register_scorer("must-fail", requires_tool=True)
def must_fail(ctx: ScoreContext) -> Score:
    """A negative control: the inputs pass as given, and fail with each mutant standing in for its case file.

    The clean run (the seat's files of the kinds in ``seat_files`` with the case's files) must pass; the
    check's ``cover_tool``, when it names one, must pass over the same clean inputs, so every cover is
    reached and the pass is not vacuous; and each mutant must make the tool fail on a run that executed
    and wrote its log. A refusal, which ran nothing, never counts as a mutant caught. Every run reads a
    staged copy of its inputs, each under its own file name, so a mutant takes the name of the file it
    stands in for. The scorer is judging the seat's testbench or assertions, not the seat's RTL: a
    testbench that cannot tell a mutant from the clean design proves nothing about either.
    """
    check = ctx.check

    def score(status: ScoreStatus, summary: str, runs: tuple[str, ...] = (), failed: tuple[str, ...] = ()) -> Score:
        return Score(scorer=check.scorer, name=check.name, status=status, summary=summary, runs=runs,
                     failed_runs=failed)

    if not check.mutants:
        return score(ScoreStatus.NOT_RUN, "the check names no mutant, so nothing has to fail")
    inputs: dict[str, list[Path]] = {}
    for param, kinds in check.seat_files.items():
        files = ctx.seat_files(kinds)
        if not files:
            return score(ScoreStatus.NOT_RUN, f"the seat submitted no {' or '.join(kinds)} file")
        inputs.setdefault(param, []).extend(Path(str(a.location)) for a in files)
    for param, paths in check.case_files.items():
        inputs.setdefault(param, []).extend(resolve(ctx.repo, p) for p in paths)
    names = [p.name for paths in inputs.values() for p in paths]
    if len(set(names)) != len(names):
        return score(ScoreStatus.NOT_RUN, f"two inputs share a file name ({', '.join(sorted(names))}); "
                                          "a staged run could not tell them apart")
    entries: dict[str, str] = {}
    for param, kinds in check.seat_entries.items():
        entry = _declared_entry(ctx, param, kinds)
        if entry is None:
            return score(ScoreStatus.NOT_RUN, f"no run of the seat's own declares {param} for its "
                                              f"{' or '.join(kinds)} file")
        entries[param] = entry
    if ctx.work is not None:
        return _must_fail_runs(ctx, inputs, entries, ctx.work / "must-fail", score)
    with tempfile.TemporaryDirectory(prefix="nirmaan-must-fail-") as stage:
        return _must_fail_runs(ctx, inputs, entries, Path(stage), score)


def _must_fail_runs(ctx: ScoreContext, inputs: dict[str, list[Path]], entries: dict[str, str], stage: Path,
                    score: Callable[..., Score]) -> Score:
    """The clean run, the cover run and one run per mutant, each on inputs staged under ``stage``."""
    check = ctx.check

    def run(tool: str, label: str, swap: tuple[Path, Path] | None = None):
        params = {**check.params, **entries, **_stage(stage / label, inputs, swap)}
        return ctx.tools.invoke(tool, **params)

    try:
        clean_id, clean = run(str(check.tool), "clean")
        passed = [clean_id]
        if not clean.succeeded:
            return score(ScoreStatus.FAILED, f"the clean inputs do not pass: {check.tool} {clean_id}: "
                                             f"{clean.summary}", tuple(passed))
        if check.cover_tool:
            cover_id, cover = run(check.cover_tool, "cover")
            passed.append(cover_id)
            if not cover.succeeded:
                return score(ScoreStatus.FAILED, f"covers not reached on the clean inputs: {check.cover_tool} "
                                                 f"{cover_id}: {cover.summary}", tuple(passed))
        caught: list[str] = []
        for n, (original, mutants) in enumerate(sorted(check.mutants.items()), start=1):
            for m, mutant in enumerate(mutants, start=1):
                run_id, outcome = run(str(check.tool), f"mutant-{n}-{m}",
                                      (resolve(ctx.repo, original), resolve(ctx.repo, mutant)))
                if outcome.succeeded:
                    return score(ScoreStatus.FAILED, f"mutant {mutant} survived: {check.tool} {run_id} passed",
                                 tuple(passed), tuple(caught))
                if not outcome.references:
                    return score(ScoreStatus.NOT_RUN, f"mutant {mutant} was refused, not run: {outcome.summary}",
                                 tuple(passed), tuple(caught))
                caught.append(run_id)
    except ToolAccessDenied as exc:
        return score(ScoreStatus.NOT_RUN, f"not run: {exc}")
    return score(ScoreStatus.PASSED, f"{check.tool} {clean_id} passed on the clean inputs"
                                     f"{' with every cover reached' if check.cover_tool else ''}; "
                                     f"{len(caught)} of {sum(map(len, check.mutants.values()))} mutants "
                                     f"failed it", tuple(passed),
                 tuple(caught))
