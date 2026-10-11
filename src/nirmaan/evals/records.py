"""Run records (M45): a live evaluation kept as evidence anyone can re-examine and re-judge.

``record_run`` runs cases ``trials`` times each and writes one directory:
``manifest.json`` (what ran), one ``<case>/trial-NN.json`` per trial (the
``EvalResult``, every raw model answer with its prompt and packet hashes and
tokens, and every tool run behind a judge verdict), and ``summary.json`` (pass
rates per case and per seat with Wilson intervals, and totals). ``rejudge``
replays a record's answers through the real gates and judges and reports any
verdict that differs. Like the runner, nothing here names a stage, tool,
artifact kind, or role: all of those come from cases and records.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import nirmaan
from nirmaan.evals.cases import case_digest
from nirmaan.evals.runner import REPLAY, evaluate, replay_llm
from nirmaan.models import EvalCase, EvalResult, EvalRunManifest, EvalTrial, JudgeRun, RecordedAnswer
from nirmaan.org import Organization
from nirmaan.runtime import AgentRuntime, Completion, ModelRuntime, WorkPrompt, get_runtime
from nirmaan.runtime.model import NO_CALL

MANIFEST = "manifest.json"
SUMMARY = "summary.json"
SUMMARY_FORMAT = "nirmaan.eval-summary"
#: The convention for a model: at least this many trials per case.
LIVE_TRIALS = 5
#: 95% two-sided normal quantile, for Wilson score intervals.
Z95 = 1.959963984540054
_UNSAFE = re.compile(r"[^A-Za-z0-9._\-]")


def _safe(text: str) -> str:
    return _UNSAFE.sub("_", text)


def trial_path(record: Path, case_id: str, trial: int) -> Path:
    return Path(record) / _safe(case_id) / f"trial-{trial:02d}.json"


# --- Hashes and the recording model ---------------------------------------------------------


def prompt_sha256(prompt: WorkPrompt) -> str:
    """sha256 over the prompt as a chat-shaped model is sent it: the system part, a NUL, the user part."""
    from nirmaan.integrations.veritriage import render_parts

    system, user = render_parts(prompt)
    return hashlib.sha256(f"{system}\0{user}".encode("utf-8")).hexdigest()


def packet_sha256(prompt: WorkPrompt) -> str:
    """sha256 over the work packet the prompt carries (task, sections, citations, outputs), before rendering."""
    packet = {k: v for k, v in dataclasses.asdict(prompt).items() if k != "system"}
    return hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class RecordingLLM:
    """Wraps a runtime's model for one trial and keeps every answer it gives, as given."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "llm")
        self.answers: list[RecordedAnswer] = []

    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def complete(self, prompt: WorkPrompt) -> Completion:
        c = self.inner.complete(prompt)
        self.answers.append(RecordedAnswer(
            mode=prompt.mode, provider=c.provider or self.name, model=c.model, prompt_sha256=prompt_sha256(prompt),
            packet_sha256=packet_sha256(prompt), text=c.text, error=c.error, input_tokens=c.input_tokens,
            output_tokens=c.output_tokens, cache_read_tokens=c.cache_read_tokens,
            cache_write_tokens=c.cache_write_tokens))
        return c


class RecordedAnswers:
    """Answers with a trial's recorded answers, in order; never invents one when they run out."""

    name = "rejudge"

    def __init__(self, answers: Sequence[RecordedAnswer]) -> None:
        self._left = list(answers)

    def complete(self, prompt: WorkPrompt) -> Completion:
        if not self._left:
            return Completion("", error=NO_CALL + "no recorded answer is left to replay")
        a = self._left.pop(0)
        return Completion(a.text, a.model, a.error, a.provider, a.input_tokens, a.output_tokens,
                          a.cache_read_tokens, a.cache_write_tokens)


def model_of(runtime: AgentRuntime) -> str:
    """The model a runtime is configured to seat, before it answers; its ID when nothing says."""
    llm = getattr(runtime, "llm", None)
    return str(getattr(llm, "model", None) or getattr(llm, "_model", None) or getattr(llm, "name", None)
               or runtime.runtime_id)


# --- Running and recording -------------------------------------------------------------------


def select_cases(cases: Sequence[EvalCase], seats: Sequence[str]) -> list[EvalCase]:
    """The cases whose seat stage, or whose group (the ID before the first ``/``), is in ``seats``."""
    if not seats:
        return list(cases)
    return [c for c in cases if c.seat in seats or c.id.split("/", 1)[0] in seats]


def record_trial(org: Organization, case: EvalCase, seat_runtime: AgentRuntime, *, replay: bool, record: str,
                 trial: int, repo: Path, attempts: int | None = None, sandbox: Path | None = None,
                 clock: Callable[[], datetime] | None = None) -> EvalTrial:
    """Run one case once with every model answer captured, and keep the tool runs behind each verdict."""
    llm = getattr(seat_runtime, "llm", None)
    recorder = RecordingLLM(llm) if llm is not None else None
    if recorder is not None:
        seat_runtime.llm = recorder  # type: ignore[attr-defined]
    try:
        result, engine = evaluate(org, case, seat_runtime, replay=replay, repo=repo, attempts=attempts,
                                  sandbox=sandbox, clock=clock)
    finally:
        if recorder is not None:
            seat_runtime.llm = llm  # type: ignore[attr-defined]
    judge_runs = tuple(
        JudgeRun(check=score.name, run=run.id, tool=run.tool, succeeded=run.succeeded, summary=run.summary,
                 params=run.model_dump(mode="json")["params"])
        for score in result.scores for run in (engine.state.tool_runs.get(r) for r in score.runs) if run)
    answers = tuple(recorder.answers) if recorder else ()
    model = next((a.model for a in answers if a.model), None) or model_of(seat_runtime)
    return EvalTrial(record=record, trial=trial, stage=case.seat, model=model, result=result, answers=answers,
                     judge_runs=judge_runs)


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _free(out: Path, name: str) -> Path:
    """``out/name``, or the first ``name-2``, ``name-3`` that does not exist: a record is never overwritten."""
    candidate, n = Path(out) / name, 1
    while candidate.exists():
        n += 1
        candidate = Path(out) / f"{name}-{n}"
    return candidate


def record_run(org: Organization, cases: Sequence[EvalCase], runtime: str | None, *, trials: int, repo: Path,
               out: Path, attempts: int | None = None, command: str = "",
               clock: Callable[[], datetime] | None = None,
               on_trial: Callable[[EvalTrial, Path], None] | None = None) -> Path:
    """Run every case ``trials`` times on a registered runtime (``None`` replays) and write a run record.

    Each trial gets a fresh runtime and its own sandbox. The manifest is written first and rewritten at the
    end, so a run cut short still leaves a readable record of the trials it finished.
    """
    if trials < 1:
        raise ValueError("trials must be at least 1")
    now = clock or (lambda: datetime.now(timezone.utc))
    started = now()
    probe = get_runtime(runtime) if runtime else None
    runtime_id, model = (probe.runtime_id, model_of(probe)) if probe else (REPLAY, REPLAY)
    path = _free(out, f"{started:%Y-%m-%d}-{_safe(runtime_id)}-{_safe(model)}")
    path.mkdir(parents=True)

    def manifest(finished: datetime) -> EvalRunManifest:
        return EvalRunManifest(id=path.name, runtime=runtime_id, model=model, replay=runtime is None,
                               nirmaan_version=nirmaan.__version__, started_at=started, finished_at=finished,
                               trials=trials, cases=tuple(c.id for c in cases),
                               seats=tuple(dict.fromkeys(c.seat for c in cases)), command=command)

    _write(path / MANIFEST, manifest(started).model_dump(mode="json"))
    done: list[EvalTrial] = []
    for case in cases:
        for number in range(1, trials + 1):
            seat = get_runtime(runtime) if runtime else ModelRuntime(replay_llm(case, repo), runtime_id=REPLAY)
            trial = record_trial(org, case, seat, replay=runtime is None, record=path.name, trial=number, repo=repo,
                                 attempts=attempts, clock=clock)
            target = trial_path(path, case.id, number)
            _write(target, trial.model_dump(mode="json"))
            done.append(trial)
            if on_trial:
                on_trial(trial, target)
    _write(path / MANIFEST, manifest(now()).model_dump(mode="json"))
    _write(path / SUMMARY, summarize(done))
    return path


# --- Reading ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalRecord:
    path: Path
    manifest: EvalRunManifest
    trials: tuple[EvalTrial, ...]

    def summary(self) -> dict[str, Any]:
        return summarize(self.trials)


def load_record(path: Path | str) -> EvalRecord:
    """A run record directory: its manifest and every trial file under it, by case and trial number."""
    path = Path(path)
    manifest = EvalRunManifest.model_validate_json((path / MANIFEST).read_text(encoding="utf-8"))
    trials = [EvalTrial.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(path.rglob("trial-*.json"))]
    return EvalRecord(path, manifest, tuple(sorted(trials, key=lambda t: (t.result.case, t.trial))))


def load_records(root: Path | str) -> list[EvalRecord]:
    """Every run record under ``root``, oldest first."""
    records = [load_record(m.parent) for m in sorted(Path(root).rglob(MANIFEST))]
    return sorted(records, key=lambda r: (r.manifest.started_at, r.manifest.id))


# --- Rates and intervals ---------------------------------------------------------------------


def wilson(passed: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """The Wilson score interval for ``passed`` of ``n``; None when n is 0. Honest at small n."""
    if n <= 0:
        return None
    p, z2 = passed / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    low = 0.0 if passed == 0 else max(0.0, centre - half)
    high = 1.0 if passed == n else min(1.0, centre + half)
    return low, high


def _rate(passed: int, n: int) -> dict[str, Any]:
    low, high = wilson(passed, n) or (None, None)
    return {"n": n, "passed": passed, "rate": passed / n if n else None, "low": low, "high": high}


def summarize(trials: Iterable[EvalTrial]) -> dict[str, Any]:
    """Pass rates per case and per seat stage, with 95% Wilson intervals, and totals across trials."""
    trials = list(trials)
    by_case: dict[str, list[bool]] = {}
    by_seat: dict[str, list[bool]] = {}
    for t in trials:
        by_case.setdefault(t.result.case, []).append(t.result.passed)
        by_seat.setdefault(t.stage, []).append(t.result.passed)
    costs = [t.result.cost_usd for t in trials]
    return {
        "format": SUMMARY_FORMAT,
        "cases": {k: _rate(sum(v), len(v)) for k, v in sorted(by_case.items())},
        "seats": {k: _rate(sum(v), len(v)) for k, v in sorted(by_seat.items())},
        "totals": {"trials": len(trials), "model_calls": sum(t.result.model_calls for t in trials),
                   "input_tokens": sum(t.result.input_tokens for t in trials),
                   "output_tokens": sum(t.result.output_tokens for t in trials),
                   "cost_usd": None if any(c is None for c in costs) else round(sum(costs), 6),  # type: ignore[arg-type]
                   "duration_s": round(sum(t.result.duration_s for t in trials), 3)},
    }


def rate_text(entry: Mapping[str, Any]) -> str:
    """``k/n passed (rate, 95% CI low to high)``: n is always shown."""
    if not entry["n"]:
        return "0 trials"
    return (f"{entry['passed']}/{entry['n']} passed ({entry['rate']:.0%}, 95% CI {entry['low']:.0%} to "
            f"{entry['high']:.0%})")


# --- Re-judging ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rejudged:
    trial: EvalTrial
    result: EvalResult | None
    differences: tuple[str, ...]

    @property
    def same(self) -> bool:
        return not self.differences


def _compare(before: EvalResult, after: EvalResult) -> tuple[str, ...]:
    out = [f"{field}: recorded {getattr(before, field)!r}, now {getattr(after, field)!r}"
           for field in ("submitted", "seat_status", "passed") if getattr(before, field) != getattr(after, field)]
    now = {s.name: s.status.value for s in after.scores}
    for score in before.scores:
        if now.get(score.name) != score.status.value:
            out.append(f"judge {score.name!r}: recorded {score.status.value}, now {now.get(score.name, 'absent')}")
    return tuple(out)


def rejudge(org: Organization, record: EvalRecord, cases: Mapping[str, EvalCase], *, repo: Path,
            sandbox: Path | None = None) -> list[Rejudged]:
    """Replay each trial's recorded answers through the real gates and judges, and compare the verdicts.

    A trial whose case changed since it was recorded (its digest differs) is not comparable and is
    reported as a difference without being re-run.
    """
    out: list[Rejudged] = []
    for trial in record.trials:
        recorded = trial.result
        case = cases.get(recorded.case)
        if case is None:
            out.append(Rejudged(trial, None, (f"case {recorded.case} is not among the cases given",)))
            continue
        digest = case_digest(case, repo)
        if digest != recorded.case_digest:
            out.append(Rejudged(trial, None, (f"case digest changed: recorded {recorded.case_digest}, now {digest}; "
                                              "the judges are not the ones that ruled",)))
            continue
        runtime = ModelRuntime(RecordedAnswers(trial.answers), runtime_id=recorded.runtime)
        where = Path(sandbox) / f"{_safe(recorded.case)}-{trial.trial:02d}" if sandbox else None
        result, _ = evaluate(org, case, runtime, replay=recorded.replay, repo=repo,
                             attempts=max(1, recorded.attempts), sandbox=where,
                             clock=lambda at=recorded.started_at: at)
        out.append(Rejudged(trial, result, _compare(recorded, result)))
    return out
