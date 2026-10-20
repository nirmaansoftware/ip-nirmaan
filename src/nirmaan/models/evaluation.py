"""Evaluation vocabulary (M27): does a seat's work actually work?

A case fixes everything except the seat under evaluation: the request, the
reference documents that stand in for its approved upstream, and held-out
checks the seat never sees. A result records what ran and what each check
concluded. A score is backed by a recorded tool run or it is not a pass.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CaseFile(BaseModel):
    """A file a case supplies: a reference document or a reference answer's file."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description="Relative to the repository root, or absolute.")
    kind: str = Field(description="The artifact kind it is recorded as.")
    entry: str | None = Field(default=None, description="The entry point it declares, e.g. its top module.")


class HeldOutCheck(BaseModel):
    """A check the seat never sees, run by a registered scorer after the seat's work is submitted."""

    model_config = ConfigDict(frozen=True)

    name: str
    scorer: str = Field(default="held-out-run", description="A registered scorer ID.")
    tool: str | None = Field(default=None, description="The tool the scorer runs, when it runs one.")
    params: dict[str, str] = Field(default_factory=dict, description="Fixed tool parameters.")
    seat_files: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="Tool parameter -> artifact kinds taken from the seat's submitted files.")
    case_files: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="Tool parameter -> files the case supplies (held out from the seat).")
    seat_entries: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="Tool parameter -> artifact kinds whose declared entry fills it (M58), "
                                          "as the seat's own recorded runs of that file gave it.")
    mutants: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="Case file -> files that each stand in for it in a run that must "
                                          "fail (M58, the must-fail scorer).")
    cover_tool: str | None = Field(
        default=None, description="A tool that must also pass over the clean inputs (M58): every cover reached.")


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    request: str = Field(description="The requirement, as a person would type it.")
    seat: str = Field(description="The workflow stage whose seat is evaluated.")
    #: M58: the skills this case judges, from the skill catalog. Only these get credit from its results.
    skills: tuple[str, ...] = ()
    expected_behavior: str = ""
    constraints: tuple[str, ...] = ()
    known_failure_modes: tuple[str, ...] = ()
    upstream: dict[str, tuple[CaseFile, ...]] = Field(
        default_factory=dict, description="Stage -> reference documents that fix its approved output.")
    reference: tuple[CaseFile, ...] = Field(default=(), description="The reference answer, for replay.")
    held_out: tuple[HeldOutCheck, ...] = ()
    attempts: int = Field(default=1, ge=1)


class ScoreStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    #: The check could not run (tool refused, or nothing to check). Never a pass.
    NOT_RUN = "not_run"


class Score(BaseModel):
    model_config = ConfigDict(frozen=True)

    scorer: str
    name: str
    status: ScoreStatus
    summary: str = ""
    runs: tuple[str, ...] = Field(default=(), description="Tool runs recorded in the sandbox that back it.")
    failed_runs: tuple[str, ...] = Field(
        default=(), description="Runs a negative control required to fail, recorded failed in the sandbox (M58).")


class GateRun(BaseModel):
    """A tool run the seat's own before-review checks made."""

    model_config = ConfigDict(frozen=True)

    tool: str
    run: str
    succeeded: bool
    summary: str = ""


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: str
    case_digest: str = Field(description="sha256 over the case file and every file it references.")
    runtime: str
    replay: bool = Field(description="True when the seat replayed the case's own reference answer.")
    version: str
    started_at: datetime
    duration_s: float
    seat: str
    seat_status: str
    submitted: bool = Field(description="The work reached review: its own before-review checks passed.")
    attempts: int
    gate_runs: tuple[GateRun, ...] = ()
    scores: tuple[Score, ...] = ()
    passed: bool
    detail: str = ""
    audit_ok: bool
    #: M58: human attestations recorded on the seat's task. A trial carrying any is never evidence.
    attestations: tuple[str, ...] = ()
    sandbox: str
    #: The seat run's model calls (M31): how many, tokens as reported, and cost (None when any is unknown).
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


class RecordedAnswer(BaseModel):
    """One raw model answer in a trial (M45), with what it answered and what it cost, as reported."""

    model_config = ConfigDict(frozen=True)

    mode: str = Field(description="'work' or 'review'.")
    provider: str | None = None
    model: str | None = None
    prompt_sha256: str = Field(description="sha256 over the prompt as sent: system part, a NUL, the user part.")
    packet_sha256: str = Field(description="sha256 over the work packet the prompt carries, before rendering.")
    text: str = ""
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


class JudgeRun(BaseModel):
    """A tool run behind a judge verdict, as the sandbox recorded it (M45)."""

    model_config = ConfigDict(frozen=True)

    check: str
    run: str
    tool: str
    succeeded: bool
    summary: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class EvalTrial(BaseModel):
    """One case run once, as a run record keeps it (M45): the result, the raw answers, and the judge runs."""

    model_config = ConfigDict(frozen=True)

    format: Literal["nirmaan.eval-trial"] = "nirmaan.eval-trial"
    version: int = 1
    record: str = Field(description="The run record's ID (its directory name).")
    trial: int = Field(ge=1)
    stage: str = Field(description="The workflow stage whose seat was evaluated.")
    model: str | None = Field(default=None, description="The model the answers report.")
    #: M58: skill ID -> skill digest (card plus knowledge document) at run time, for the case's skills.
    skills: dict[str, str] = Field(default_factory=dict)
    result: EvalResult
    answers: tuple[RecordedAnswer, ...] = ()
    judge_runs: tuple[JudgeRun, ...] = ()


class EvalRunManifest(BaseModel):
    """What one ``nirmaan eval run`` was (M45): runtime, model, version, trials, cases, and the command."""

    model_config = ConfigDict(frozen=True)

    format: Literal["nirmaan.eval-run"] = "nirmaan.eval-run"
    version: int = 1
    id: str
    runtime: str
    model: str | None = None
    replay: bool
    nirmaan_version: str
    started_at: datetime
    finished_at: datetime
    trials: int = Field(ge=1)
    cases: tuple[str, ...]
    seats: tuple[str, ...]
    command: str = ""
    #: M58: the commit the run was made on, when it was made in a repository.
    head_sha: str | None = None


class EvalProposalThresholds(BaseModel):
    """When recorded evaluation runs propose a change (M42). Company data: ``company/learning.py``."""

    model_config = ConfigDict(frozen=True)

    #: A recurring failure: at least ``min_failures`` failed among the latest ``within_runs`` runs of a case.
    min_failures: int = Field(default=2, ge=1)
    within_runs: int = Field(default=5, ge=1)
    #: A regression: the pass rate over the latest ``window`` runs is at least ``min_drop`` below
    #: the rate over the ``window`` runs before them.
    window: int = Field(default=4, ge=1)
    min_drop: float = Field(default=0.25, gt=0.0, le=1.0)
