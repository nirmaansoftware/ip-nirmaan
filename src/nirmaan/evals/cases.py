"""Evaluation cases: data on disk, loaded and checked before anything runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nirmaan.models import EvalCase, TaskKind
from nirmaan.org import Organization


class EvalError(RuntimeError):
    """An evaluation that cannot run honestly. Nothing was scored."""


def load_case(path: Path | str) -> EvalCase:
    return EvalCase.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_cases(root: Path | str) -> list[EvalCase]:
    """Every ``*.json`` case under ``root``, by ID. Two cases with one ID are an error."""
    cases: dict[str, EvalCase] = {}
    for path in sorted(Path(root).rglob("*.json")):
        case = load_case(path)
        if case.id in cases:
            raise EvalError(f"two cases are named {case.id!r}; the second is {path}")
        cases[case.id] = case
    return [cases[key] for key in sorted(cases)]


def resolve(repo: Path, path: str) -> Path:
    """A case path: absolute as given, else relative to the repository root."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(repo) / candidate


def referenced_files(case: EvalCase) -> list[str]:
    """Every file the case names: upstream documents, the reference answer, held-out inputs."""
    paths = [f.path for files in case.upstream.values() for f in files]
    paths += [f.path for f in case.reference]
    paths += [p for check in case.held_out for files in check.case_files.values() for p in files]
    return sorted(dict.fromkeys(paths))


def case_digest(case: EvalCase, repo: Path) -> str:
    """sha256 over the case and the bytes of every file it names, so a result is tied to exact inputs."""
    digest = hashlib.sha256(json.dumps(case.model_dump(mode="json"), sort_keys=True).encode("utf-8"))
    for path in referenced_files(case):
        target = resolve(repo, path)
        digest.update(path.encode("utf-8"))
        digest.update(target.read_bytes() if target.is_file() else b"\0missing")
    return "sha256:" + digest.hexdigest()


def validate_case(org: Organization, case: EvalCase, repo: Path) -> list[str]:
    """Every reason the case cannot run as written. Empty means it can."""
    from nirmaan.evals.scorers import scorer_spec
    from nirmaan.orchestrator import Orchestrator, UnrecognizedRequirement

    problems = [f"file not found: {p}" for p in referenced_files(case) if not resolve(repo, p).is_file()]
    for check in case.held_out:
        spec = scorer_spec(check.scorer)
        if spec is None:
            problems.append(f"check {check.name!r}: no scorer {check.scorer!r} is registered")
        elif spec.requires_tool and not check.tool:
            problems.append(f"check {check.name!r}: scorer {check.scorer!r} needs a tool")
        if check.tool and check.tool not in org.tools:
            problems.append(f"check {check.name!r}: unknown tool {check.tool!r}")
    try:
        engine = Orchestrator(org).plan(case.request)
    except UnrecognizedRequirement as exc:
        return [*problems, f"the request is not recognized: {exc}"]
    work = [t for t in engine.state.tasks.values() if t.kind is TaskKind.WORK and t.stage]
    seats = [t for t in work if t.stage == case.seat]
    if len(seats) != 1:
        problems.append(f"seat {case.seat!r} is {len(seats)} tasks in the planned workflow; it must be one")
    for stage, files in case.upstream.items():
        tasks = [t for t in work if t.stage == stage]
        if not tasks:
            problems.append(f"upstream stage {stage!r} is not in the planned workflow")
        for f in files:
            if tasks and f.kind not in tasks[0].expected_outputs:
                problems.append(f"upstream {f.path}: stage {stage!r} does not produce {f.kind!r}")
    return problems
