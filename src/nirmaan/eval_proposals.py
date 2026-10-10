"""Learning proposals from evaluation results (M42): a seat that keeps failing a case proposes a change.

``load_results`` reads recorded ``EvalResult`` files (M27); ``eval_proposals``
runs a registry of rules over them, per case and runtime, and returns M33
``Proposal``s with ``source="evaluation"``, each citing every run it rests on
(run ID, file, case, runtime, version, and every judge verdict). Thresholds are
company data (``company/learning.py``). Nothing here runs a case, calls a
model, stores anything, or edits a skill: a person decides, through
``nirmaan.proposals.decide_proposal``, and changes data in a pull request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from nirmaan.models import EvalCase, EvalProposalThresholds, EvalResult, ProjectState
from nirmaan.org import Organization
from nirmaan.proposals import Proposal, proposal_id, proposal_status, providers

SOURCE = "evaluation"


@dataclass(frozen=True)
class EvalRun:
    """One recorded evaluation run, with the file it was read from."""

    id: str
    path: str
    result: EvalResult

    def evidence(self) -> dict[str, Any]:
        r = self.result
        return {"run": self.id, "file": self.path, "case": r.case, "runtime": r.runtime, "version": r.version,
                "started_at": r.started_at.isoformat(), "case_digest": r.case_digest, "passed": r.passed,
                "submitted": r.submitted, "seat_status": r.seat_status,
                "failed_gates": [{"tool": g.tool, "run": g.run, "summary": g.summary}
                                 for g in r.gate_runs if not g.succeeded],
                "verdicts": [{"check": s.name, "scorer": s.scorer, "status": s.status.value, "summary": s.summary,
                              "runs": list(s.runs)} for s in r.scores],
                "detail": r.detail}


def run_id(result: EvalResult) -> str:
    """A stable ID for one run: its case, runtime, start time, and case digest."""
    key = f"{result.case}|{result.runtime}|{result.started_at.isoformat()}|{result.case_digest}"
    return "ev-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def load_results(root: Path | str) -> list[EvalRun]:
    """Every recorded result under ``root``: one per file, or a list per file. The same run read twice is one."""
    runs: dict[str, EvalRun] = {}
    for path in sorted(Path(root).rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data if isinstance(data, list) else [data]:
            result = EvalResult.model_validate(item)
            runs.setdefault(run_id(result), EvalRun(run_id(result), str(path), result))
    return sorted(runs.values(), key=lambda r: (r.result.started_at, r.id))


@dataclass(frozen=True)
class EvalHistory:
    """What a rule reads: the trustworthy runs, the thresholds, and each case's capability."""

    runs: tuple[EvalRun, ...]
    thresholds: EvalProposalThresholds
    org: Organization
    cases: dict[str, EvalCase]

    def groups(self) -> dict[tuple[str, str], list[EvalRun]]:
        """Runs by (case, runtime), oldest first."""
        out: dict[tuple[str, str], list[EvalRun]] = {}
        for run in self.runs:
            out.setdefault((run.result.case, run.result.runtime), []).append(run)
        return {key: sorted(rows, key=lambda r: (r.result.started_at, r.id)) for key, rows in sorted(out.items())}

    def capability(self, case_id: str) -> str | None:
        """The capability the case's seat stage needs, from the workflows; None when unknown or ambiguous."""
        case = self.cases.get(case_id)
        found = {s.capability for w in self.org.workflows.values() for s in w.stages if case and s.id == case.seat}
        return found.pop() if len(found) == 1 else None


EvalRule = Callable[[Organization, EvalHistory], list[Proposal]]
_RULES: dict[str, EvalRule] = {}


def register_eval_rule(rule_id: str) -> Callable[[EvalRule], EvalRule]:
    def _register(fn: EvalRule) -> EvalRule:
        if rule_id in _RULES and _RULES[rule_id] is not fn:
            raise ValueError(f"Evaluation rule {rule_id!r} is already registered")
        _RULES[rule_id] = fn
        return fn

    return _register


def unregister_eval_rule(rule_id: str) -> None:
    _RULES.pop(rule_id, None)


def _proposal(rule: str, org: Organization, history: EvalHistory, case: str, runtime: str, rows: list[EvalRun],
              count: int, statement: str, suggestion: str) -> Proposal:
    capability, subject = history.capability(case), f"{case}@{runtime}"
    return Proposal(id=proposal_id(rule, capability, subject), rule=rule, capability=capability, subject=subject,
                    targets=providers(org, capability), statement=statement, suggestion=suggestion, count=count,
                    projects=0, evidence=tuple(r.evidence() for r in rows), source=SOURCE)


def _suggestion(history: EvalHistory, case: str, runtime: str, failed: list[EvalRun]) -> str:
    """A different model, a procedure change, or a new check: whichever the evidence points to."""
    passing = sorted(other for (c, other), rows in history.groups().items()
                     if c == case and other != runtime and rows[-1].result.passed)
    if passing:
        return (f"Model: {', '.join(passing)} passed {case} in its latest run. Seat "
                f"{history.capability(case) or 'this seat'} with that model through model selection (a model "
                f"profile, or the auto runtime's choice), then rerun the case.")
    if not any(r.result.submitted for r in failed):
        gates = list(dict.fromkeys(g.tool for r in failed for g in r.result.gate_runs if not g.succeeded))
        why = [g.summary for r in failed for g in r.result.gate_runs if not g.succeeded] or [failed[0].result.detail]
        tools = ", ".join(gates) or "the seat's own before-review checks"
        return (f"Procedure: run {tools} on the files you produce before submitting; the work never reached "
                f"review in {len(failed)} runs (first: {why[0]}).")
    judges = list(dict.fromkeys(s.name for r in failed for s in r.result.scores if s.status.value != "passed"))
    said = list(dict.fromkeys(s.summary for r in failed for s in r.result.scores if s.status.value != "passed"))
    return (f"Check: the seat's own checks passed but held-out {', '.join(judges)} failed it; add a before-review "
            f"check covering that judge. Validation criterion, from the judges: {' | '.join(said)}")


@register_eval_rule("recurring-eval-failure")
def recurring_eval_failure(org: Organization, history: EvalHistory) -> list[Proposal]:
    t, proposals = history.thresholds, []
    for (case, runtime), rows in history.groups().items():
        failed = [r for r in rows[-t.within_runs:] if not r.result.passed]
        if len(failed) < t.min_failures:
            continue
        proposals.append(_proposal(
            "recurring-eval-failure", org, history, case, runtime, failed, len(failed),
            f"{case} failed in {len(failed)} of the latest {min(len(rows), t.within_runs)} runs on {runtime}.",
            _suggestion(history, case, runtime, failed)))
    return proposals


@register_eval_rule("eval-pass-rate-regression")
def pass_rate_regression(org: Organization, history: EvalHistory) -> list[Proposal]:
    t, proposals = history.thresholds, []
    for (case, runtime), rows in history.groups().items():
        if len(rows) < 2 * t.window:
            continue
        earlier, latest = rows[-2 * t.window:-t.window], rows[-t.window:]
        before, now = (sum(r.result.passed for r in w) / t.window for w in (earlier, latest))
        if before - now < t.min_drop:
            continue

        def versions(window: list[EvalRun]) -> str:
            return ", ".join(dict.fromkeys(r.result.version for r in window))

        proposals.append(_proposal(
            "eval-pass-rate-regression", org, history, case, runtime, [*earlier, *latest],
            sum(not r.result.passed for r in latest),
            f"{case} on {runtime} passed {before:.0%} of {t.window} runs, then {now:.0%} of the latest {t.window}.",
            f"Compare what changed between version {versions(earlier)} and version {versions(latest)} (skill "
            f"text, model, or case digest) before deciding; the failing runs' judges say: "
            + " | ".join(dict.fromkeys(s.summary for r in latest if not r.result.passed for s in r.result.scores))))
    return proposals


def eval_proposals(org: Organization, runs: Iterable[EvalRun], cases: Iterable[EvalCase],
                   thresholds: EvalProposalThresholds | None = None,
                   states: Iterable[ProjectState] = ()) -> list[Proposal]:
    """Every proposal the registered rules make from recorded runs, with its status from ``states``, by ID.

    Replays (the case's own reference answer) and results whose audit chain did not verify are not read.
    """
    from nirmaan.company.learning import EVAL_PROPOSAL_THRESHOLDS

    trusted = tuple(r for r in runs if not r.result.replay and r.result.audit_ok)
    history = EvalHistory(trusted, thresholds or EVAL_PROPOSAL_THRESHOLDS, org, {c.id: c for c in cases})
    states = list(states)
    proposals = [p for rule in list(_RULES.values()) for p in rule(org, history)]
    return sorted((Proposal(**{**p.to_dict(), "evidence": p.evidence, "targets": p.targets,
                               "status": proposal_status(states, p.id)}) for p in proposals), key=lambda p: p.id)
