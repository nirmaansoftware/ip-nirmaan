"""Evaluation vocabulary (M27): does a seat's work actually work?

A case fixes everything except the seat under evaluation: the request, the
reference documents that stand in for its approved upstream, and held-out
checks the seat never sees. A result records what ran and what each check
concluded. A score is backed by a recorded tool run or it is not a pass.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

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


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    request: str = Field(description="The requirement, as a person would type it.")
    seat: str = Field(description="The workflow stage whose seat is evaluated.")
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
    sandbox: str
    #: The seat run's model calls (M31): how many, tokens as reported, and cost (None when any is unknown).
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
