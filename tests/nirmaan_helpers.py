"""Test helpers for IP Nirmaan: drive a project forward the honest way.

``drive`` moves tasks through the engine exactly as people would: owners start
and submit, independent reviewers review, authorized approvers approve, gate
owners (as humans when a gate requires it) sign off. Evidence is attached only
in forms the engine can substantiate: human attestations, the task's own
document artifact, or a real VeriTriage run. Nothing is faked, so a project
that completes under ``drive`` completed under the real rules.

A task with before-review checks (M23, M26, M27) is worked in the gated order:
real files are written, every check runs for real over them through the
broker, and only then is the work submitted. Driving such a task needs the
EDA tools on PATH.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from nirmaan.models import (
    Actor,
    ActorKind,
    EvidenceKind,
    ReviewState,
    TaskKind,
    TaskStatus,
    Verdict,
)
from nirmaan.runtime import ToolBroker
from nirmaan.work import TaskEngine
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"

#: The executables ``drive`` needs to take a gated RTL task through its checks for real (M27).
GATE_TOOLS = ("verilator", "iverilog", "vvp", "yosys")

#: What a gated task produces under ``drive``, per artifact kind: a real file and the entry it declares.
GATED_FILES = {"rtl_source": ("counter.v", "counter"), "testbench": ("counter_tb.v", "counter_tb")}


def needs(*executables: str):
    """Skip without the executables, except those CI names in NIRMAAN_REQUIRE_EDA (then it fails)."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


def human(role: str) -> Actor:
    return Actor(role=role, kind=ActorKind.HUMAN, name="test")


def agent(role: str) -> Actor:
    return Actor(role=role, kind=ActorKind.AI_AGENT, name="test")


def tid(engine: TaskEngine, stage: str) -> str:
    return f"{engine.state.project.id}:{stage}"


def attach_evidence(engine: TaskEngine, task_id: str, workspace: Path | None = None) -> None:
    task = engine.task(task_id)
    owner = human(task.owner)
    for req in task.evidence_requirements:
        kinds = {k.value for k in req.accepts}
        if "review_record" in kinds and len(kinds) == 1:
            continue  # recorded by the review itself
        if "human_attestation" in kinds:
            engine.record_evidence(task_id, owner, EvidenceKind.HUMAN_ATTESTATION, f"attested: {req.description}")
        elif "document" in kinds and task.artifacts:
            engine.record_evidence(task_id, owner, EvidenceKind.DOCUMENT, req.description, reference=task.artifacts[0])
        elif "veritriage_session" in kinds:
            run, _ = ToolBroker(engine).invoke(
                owner, "veritriage.investigate",
                {"paths": str(FIXTURES / "axi_timeout.log"), "workspace": str(workspace or "/tmp/nirmaan-vt")},
                task_id,
            )
            engine.record_evidence(task_id, owner, EvidenceKind.VERITRIAGE_SESSION, run.summary,
                                   reference=run.references[0] if run.references else None, tool_run=run.id)


def work(engine: TaskEngine, task_id: str, outcome: str | None = None, workspace: Path | None = None) -> None:
    """Take one READY work/decision task all the way to COMPLETED."""
    task = engine.task(task_id)
    owner = agent(task.owner)
    engine.start(task_id, owner)
    if task.kind is TaskKind.DECISION:
        outcome = outcome or task.outcomes[0]
    if any(r.before_review for r in task.evidence_requirements):
        gated_submit(engine, task_id, outcome, workspace)
    else:
        produced = [{"kind": k, "title": f"{task.title} ({k})"} for k in (task.expected_outputs or ("note",))]
        engine.submit(task_id, owner, produced, outcome=outcome)
    task = engine.task(task_id)
    if task.status is TaskStatus.COMPLETED:
        return
    attach_evidence(engine, task_id, workspace)
    task = engine.task(task_id)
    if task.status is TaskStatus.COMPLETED:
        return
    if task.review_state is not ReviewState.NOT_REQUIRED:
        engine.review(task_id, agent(task.reviewer), Verdict.APPROVE, "looks right")
        engine.approve(task_id, agent(task.approver))
    else:
        missing = unsatisfied_requirements(engine.state, engine.task(task_id))
        raise AssertionError(f"{task_id} cannot complete: {missing}")


def gated_submit(engine: TaskEngine, task_id: str, outcome: str | None = None,
                 workspace: Path | None = None) -> None:
    """Write real files, run every before-review check over them for real, then submit (M27).

    Parameters are filled from each requirement's own data (its file bindings
    and fixed parameters), the way the model runtime fills them, so a check the
    files fail keeps the task from review here too.
    """
    task = engine.task(task_id)
    owner = agent(task.owner)
    root = Path(workspace or tempfile.mkdtemp(prefix="nirmaan-drive-")) / task_id.replace(":", "_")
    root.mkdir(parents=True, exist_ok=True)
    produced = []
    for kind in task.expected_outputs:
        if kind not in GATED_FILES:
            raise AssertionError(f"{task_id} is gated, and drive has no {kind} file to produce for it")
        name, entry = GATED_FILES[kind]
        shutil.copyfile(FIXTURES / "rtl" / name, root / name)
        produced.append((kind, str(root / name), entry))
    kinds = {kind for kind, _, _ in produced}
    broker = ToolBroker(engine)
    for req in (r for r in task.evidence_requirements if r.before_review and r.applies(kinds)):
        params = dict(req.params)
        for binding in req.files:
            matched = [(path, entry) for k in binding.kinds for kind, path, entry in produced if kind == k]
            params[binding.param] = matched[0][1] if binding.entry else ",".join(p for p, _ in matched)
        for tool in req.tools:
            run, _ = broker.invoke(owner, tool, {**params, "workdir": str(root / tool)}, task_id)
            engine.record_evidence(task_id, owner, EvidenceKind.TOOL_RUN, run.summary,
                                   reference=run.references[0] if run.references else None, tool_run=run.id)
    drafts = [{"kind": kind, "title": Path(path).name, "location": path} for kind, path, _ in produced]
    engine.submit(task_id, owner, drafts, outcome=outcome)


def approve_gate(engine: TaskEngine, task_id: str) -> None:
    task = engine.task(task_id)
    engine.approve_gate(task_id, human(task.owner) if task.human_required else agent(task.owner))


def drive(engine: TaskEngine, until: str | None = None, outcomes: dict[str, str] | None = None,
          workspace: Path | None = None, limit: int = 500) -> None:
    """Complete READY tasks in plan order until ``until`` is READY (or everything is done)."""
    outcomes = outcomes or {}
    for _ in range(limit):
        if until and engine.task(until).status is TaskStatus.READY:
            return
        ready = [t for t in engine.state.tasks.values()
                 if t.status is TaskStatus.READY and t.kind in (TaskKind.WORK, TaskKind.DECISION, TaskKind.GATE)]
        if not ready:
            return
        task = ready[0]
        if task.kind is TaskKind.GATE:
            approve_gate(engine, task.id)
        else:
            work(engine, task.id, outcomes.get(task.stage or ""), workspace)
