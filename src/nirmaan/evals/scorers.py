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
from nirmaan.models.workflow import Bound
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
    cases = {param: [resolve(ctx.repo, p) for p in paths] for param, paths in check.case_files.items()}
    entries: dict[str, str] = {}
    for param, kinds in check.seat_entries.items():  # G3: a whole flow's check takes the RTL stage's declared top
        entry = _declared_entry(ctx, param, kinds)
        if entry is None:
            return score(ScoreStatus.NOT_RUN, f"no run of the seat's own declares {param} for its "
                                              f"{' or '.join(kinds)} file")
        entries[param] = entry

    def judge(stage: Path | None) -> Score:
        given = _stage_cases(stage, cases) if stage is not None else {k: [str(p) for p in v] for k, v in cases.items()}
        for param, paths in given.items():
            values.setdefault(param, []).extend(paths)
        params = {**check.params, **entries, **values}  # lists: the broker holds them to the tool's contract (M28)
        try:
            run_id, outcome = ctx.tools.invoke(str(check.tool), **params)
        except ToolAccessDenied as exc:
            return score(ScoreStatus.NOT_RUN, f"{check.tool} not run: {exc}")
        status = ScoreStatus.PASSED if outcome.succeeded else ScoreStatus.FAILED
        return score(status, f"{check.tool} {run_id}: {outcome.summary}", (run_id,))

    from nirmaan.integrations.eda import HELD_OUT_STAGED  # the tools are the gate backends' to name, not the judge's

    if str(check.tool) not in HELD_OUT_STAGED or not cases:
        return judge(None)
    if ctx.work is not None:
        ctx.work.mkdir(parents=True, exist_ok=True)
        return judge(Path(tempfile.mkdtemp(prefix="held-out-", dir=ctx.work)))
    with tempfile.TemporaryDirectory(prefix="nirmaan-held-out-") as stage:
        return judge(Path(stage))


def _stage_cases(where: Path, cases: dict[str, list[Path]]) -> dict[str, list[str]]:
    """Copy each case file into ``where`` under its own name (in a numbered folder of its own when two share a name);
    a case path that is not a file is passed as it is."""
    names = [p.name for paths in cases.values() for p in paths if p.is_file()]
    apart = len(set(names)) != len(names)
    staged: dict[str, list[str]] = {}
    n = 0
    for param, paths in cases.items():
        for path in paths:
            if not path.is_file():
                staged.setdefault(param, []).append(str(path))
                continue
            n += 1
            target = (where / str(n) if apart else where) / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            staged.setdefault(param, []).append(str(target))
    return staged


# --- Negative controls (M58) -------------------------------------------------------------------


def _values(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]


def _declared_entry(ctx: ScoreContext, param: str, kinds: tuple[str, ...]) -> str | None:
    """The value the seat's own latest passing run over one of its files of these kinds gave ``param``.

    The seat's own: a run of the task that produced the file (G3: in a whole flow, the stage that wrote it, such as
    the RTL stage for ``rtl_source``; for a single seat, the seat's task, as before).
    """
    arts = ctx.seat_files(kinds)
    files = {str(a.location) for a in arts}
    owners = {a.task for a in arts} | {ctx.task.id}
    for run in reversed(list(ctx.engine.state.tool_runs.values())):
        if run.task in owners and run.succeeded and param in run.params and not files.isdisjoint(
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
    reached and the pass is not vacuous (with ``cover_bounds`` the cover run is checked against them as a
    requirement's bounds are, M48: a coverage run must meet them); and each mutant must make the tool fail
    on a run that executed and wrote its log. A refusal, which ran nothing, never counts as a mutant caught.
    Every run reads a staged copy of its inputs, each under its own file name, so a mutant takes the name of the file it
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
        # A fresh folder each time, so a second evaluation into the same sandbox never meets the first one's files.
        ctx.work.mkdir(parents=True, exist_ok=True)
        return _must_fail_runs(ctx, inputs, entries, Path(tempfile.mkdtemp(prefix="must-fail-", dir=ctx.work)), score)
    with tempfile.TemporaryDirectory(prefix="nirmaan-must-fail-") as stage:
        return _must_fail_runs(ctx, inputs, entries, Path(stage), score)


def _must_fail_runs(ctx: ScoreContext, inputs: dict[str, list[Path]], entries: dict[str, str], stage: Path,
                    score: Callable[..., Score]) -> Score:
    """The clean run, the cover run and one run per mutant, each on inputs staged under ``stage``."""
    check = ctx.check

    bounds = tuple(Bound.parse(text) for text in check.cover_bounds)

    def run(tool: str, label: str, swap: tuple[Path, Path] | None = None, bounds: tuple[Bound, ...] = ()):
        params = {**check.params, **entries, **_stage(stage / label, inputs, swap)}
        return ctx.tools.invoke(tool, bounds=bounds, **params)

    try:
        clean_id, clean = run(str(check.tool), "clean")
        passed = [clean_id]
        if not clean.succeeded:
            return score(ScoreStatus.FAILED, f"the clean inputs do not pass: {check.tool} {clean_id}: "
                                             f"{clean.summary}", tuple(passed))
        if check.cover_tool:
            cover_id, cover = run(check.cover_tool, "cover", bounds=bounds)
            passed.append(cover_id)
            if not cover.succeeded:
                return score(ScoreStatus.FAILED, f"covers not reached on the clean inputs: {check.cover_tool} "
                                                 f"{cover_id}: {cover.summary}", tuple(passed))
        caught: list[str] = []
        for n, (original, mutants) in enumerate(sorted(check.mutants.items()), start=1):
            for m, mutant in enumerate(mutants, start=1):
                run_id, outcome = run(str(check.tool), f"mutant-{n}-{m}",
                                      (resolve(ctx.repo, original), resolve(ctx.repo, mutant)))
                if outcome.succeeded:  # the surviving mutant's run is listed, so the record carries it (M6)
                    return score(ScoreStatus.FAILED, f"mutant {mutant} survived: {check.tool} {run_id} passed",
                                 (*passed, run_id), tuple(caught))
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


# --- One file at a time (M71) -----------------------------------------------------------------


def _own_entry(ctx: ScoreContext, param: str, location: str, others: set[str]) -> str | None:
    """The value the seat's own latest passing run over this one file, and none of its others, gave ``param``."""
    for run in reversed(list(ctx.engine.state.tool_runs.values())):
        used = {v for value in run.params.values() for v in _values(value)}
        if run.task == ctx.task.id and run.succeeded and param in run.params and location in used \
                and others.isdisjoint(used):
            return str(run.params[param])
    return None


def _matched(caught: dict[str, set[str]], files: list[str]) -> dict[str, str]:
    """A different file for every mutant, each one that fails it (a bipartite matching, by augmenting paths)."""
    owner: dict[str, str] = {}

    def assign(mutant: str, seen: set[str]) -> bool:
        for f in files:
            if f in caught[mutant] and f not in seen:
                seen.add(f)
                if f not in owner or assign(owner[f], seen):
                    owner[f] = mutant
                    return True
        return False

    for mutant in caught:
        assign(mutant, set())
    return {mutant: f for f, mutant in owner.items()}


@register_scorer("must-fail-each", requires_tool=True)
def must_fail_each(ctx: ScoreContext) -> Score:
    """A negative control over several seat files, each judged on its own (M71): one repro per failure bucket.

    The check's ``seat_files`` name one parameter and the kinds of the files judged one at a time (a triage
    seat's repro testbenches); each runs alone with the case's files, its entry from the seat's own passing run
    over that file alone. Every file must pass on the clean inputs, and every mutant (one seeded bug per
    bucket) must fail a different file: one repro that fails every bug, or two buckets the seat merged, leaves a
    mutant with no file of its own. A refusal never counts as a mutant caught.
    """
    check = ctx.check

    def score(status: ScoreStatus, summary: str, runs: tuple[str, ...] = (), failed: tuple[str, ...] = ()) -> Score:
        return Score(scorer=check.scorer, name=check.name, status=status, summary=summary, runs=runs,
                     failed_runs=failed)

    if not check.mutants:
        return score(ScoreStatus.NOT_RUN, "the check names no mutant, so nothing has to fail")
    if len(check.seat_files) != 1:
        return score(ScoreStatus.NOT_RUN, "a check judged one file at a time names exactly one seat parameter")
    [(param, kinds)] = check.seat_files.items()
    files = [str(a.location) for a in ctx.seat_files(kinds)]
    if not files:
        return score(ScoreStatus.NOT_RUN, f"the seat submitted no {' or '.join(kinds)} file")
    case_inputs = {p: [resolve(ctx.repo, f) for f in paths] for p, paths in check.case_files.items()}
    entries: dict[str, dict[str, str]] = {}
    for location in files:
        entries[location] = {}
        for entry_param, entry_kinds in check.seat_entries.items():
            if set(entry_kinds) != set(kinds):
                return score(ScoreStatus.NOT_RUN, f"{entry_param} must come from the files judged one at a time")
            entry = _own_entry(ctx, entry_param, location, set(files) - {location})
            if entry is None:
                return score(ScoreStatus.NOT_RUN, f"no run of the seat's own over {Path(location).name} alone "
                                                  f"declares {entry_param}")
            entries[location][entry_param] = entry
    if ctx.work is not None:
        ctx.work.mkdir(parents=True, exist_ok=True)
        return _each_runs(ctx, param, files, case_inputs, entries,
                          Path(tempfile.mkdtemp(prefix="must-fail-each-", dir=ctx.work)), score)
    with tempfile.TemporaryDirectory(prefix="nirmaan-must-fail-each-") as stage:
        return _each_runs(ctx, param, files, case_inputs, entries, Path(stage), score)


def _each_runs(ctx: ScoreContext, param: str, files: list[str], case_inputs: dict[str, list[Path]],
               entries: dict[str, dict[str, str]], stage: Path, score: Callable[..., Score]) -> Score:
    """Per seat file: the clean run, then one run per mutant; then the matching of mutants to files."""
    check = ctx.check
    mutants = [(resolve(ctx.repo, original), resolve(ctx.repo, m))
               for original, ms in sorted(check.mutants.items()) for m in ms]
    passed: list[str] = []
    survived: list[str] = []  # the runs a mutant passed: listed with the clean runs, so the record carries them (M6)
    failed_by: dict[str, dict[str, str]] = {str(m): {} for _, m in mutants}  # mutant -> file -> failed run
    try:
        for n, location in enumerate(files, start=1):
            inputs = {**case_inputs}
            inputs[param] = [*inputs.get(param, []), Path(location)]
            names = [p.name for paths in inputs.values() for p in paths]
            if len(set(names)) != len(names):
                return score(ScoreStatus.NOT_RUN, f"two inputs share a file name ({', '.join(sorted(names))}); "
                                                  "a staged run could not tell them apart")

            def run(label: str, swap: tuple[Path, Path] | None = None):
                return ctx.tools.invoke(str(check.tool), **{**check.params, **entries[location],
                                                            **_stage(stage / f"file-{n}" / label, inputs, swap)})

            clean_id, clean = run("clean")
            passed.append(clean_id)
            if not clean.succeeded:
                return score(ScoreStatus.FAILED, f"{Path(location).name} does not pass on the clean inputs: "
                                                 f"{check.tool} {clean_id}: {clean.summary}", (*passed, *survived))
            for m, (original, mutant) in enumerate(mutants, start=1):
                run_id, outcome = run(f"mutant-{m}", (original, mutant))
                if not outcome.succeeded and not outcome.references:
                    return score(ScoreStatus.NOT_RUN, f"mutant {mutant} was refused, not run: {outcome.summary}",
                                 (*passed, *survived))
                if outcome.succeeded:
                    survived.append(run_id)
                else:
                    failed_by[str(mutant)][location] = run_id
    except ToolAccessDenied as exc:
        return score(ScoreStatus.NOT_RUN, f"not run: {exc}")
    matching = _matched({m: set(by) for m, by in failed_by.items()}, files)
    alone = [m for m in failed_by if m not in matching]
    caught = tuple(failed_by[m][f] for m, f in sorted(matching.items()))
    if alone:
        return score(ScoreStatus.FAILED, f"no repro of its own fails {', '.join(Path(m).name for m in alone)}: "
                                         f"only {len(matching)} of {len(failed_by)} mutants have a file of their "
                                         "own that fails them", (*passed, *survived), caught)
    return score(ScoreStatus.PASSED, f"each of {len(files)} files passed {check.tool} on the clean inputs; each of "
                                     f"{len(failed_by)} mutants fails a file of its own", (*passed, *survived), caught)


# --- The object screen before a whole-flow check links seat C (G3, gate WF16) ------------------------------------

#: What the screen reads of a check's inputs: C files and headers, whatever parameter names them.
_C_SUFFIXES = (".c", ".h")


def _screen(ctx: ScoreContext, staged: bool) -> Score | None:
    """The object screen over the check's C (``nirmaan.evals.object_screen``): a failed check when it refuses.

    The C files are the check's inputs that are C files or headers, the seat's and the case's, as the tool will
    get them: in place for ``held-out-run``, copied into one folder under their own names for ``must-fail``, which
    runs every input from such a staged copy. Which checks are screened is the case's data (the scorer it names),
    never this code's. None when the screen finds nothing, or the seat gave the check no C.
    """
    from nirmaan.evals import object_screen

    check = ctx.check
    seat = [Path(str(a.location)) for kinds in check.seat_files.values() for a in ctx.seat_files(kinds)]
    seat = [p for p in dict.fromkeys(seat) if p.suffix in _C_SUFFIXES]
    case = [p for paths in check.case_files.values() for p in (resolve(ctx.repo, f) for f in paths)
            if p.suffix in _C_SUFFIXES]
    if not seat:
        return None  # the scorer itself says the seat submitted no such file, or there is no seat C to screen
    if staged and len({p.name for p in [*seat, *case]}) != len(seat) + len(case):
        return None  # must-fail refuses two inputs that share a file name, and runs nothing

    def judge(where: Path) -> Score | None:
        sources, mine = [*seat, *case], set(seat)
        if staged:
            (where / "src").mkdir(parents=True)
            copies = {p: where / "src" / p.name for p in sources}
            for p, copy in copies.items():
                shutil.copyfile(p, copy)
            sources, mine = list(copies.values()), {copies[p] for p in seat}
        hits = object_screen.screen(sources, mine, where / "screen")
        if not hits:
            return None
        return Score(scorer=check.scorer, name=check.name, status=ScoreStatus.FAILED,
                     summary=object_screen.summary(hits))

    if ctx.work is not None:
        ctx.work.mkdir(parents=True, exist_ok=True)
        return judge(Path(tempfile.mkdtemp(prefix="object-screen-", dir=ctx.work)))
    with tempfile.TemporaryDirectory(prefix="nirmaan-object-screen-") as where:
        return judge(Path(where))


def _screened(inner: Scorer, staged: bool) -> Scorer:
    def scorer(ctx: ScoreContext) -> Score:
        return _screen(ctx, staged) or inner(ctx)

    scorer.__doc__ = (f"``{inner.__name__}`` after the object screen (gate WF16): a refusal is the check's failed "
                      "verdict, with nothing linked or run; otherwise the inner scorer's score, unchanged.")
    return scorer


#: The whole-flow checks that build or link seat-written C name these (tests/test_object_screen.py holds every
#: whole-flow case to it, and every single-seat case away from it). The scorers above are unchanged.
SCREENED = {"screened-held-out-run": "held-out-run", "screened-must-fail": "must-fail"}
screened_held_out_run = register_scorer("screened-held-out-run", requires_tool=True)(_screened(held_out_run, False))
screened_must_fail = register_scorer("screened-must-fail", requires_tool=True)(_screened(must_fail, True))
