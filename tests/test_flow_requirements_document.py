"""A customer document reaches its task's seat as text (G3, council record 2026-11-17, decision 2; fact 10).

A whole-flow case gives the requirements stage a fixed requirements document. A case's ``inputs`` are task memory
that parameterizes tools and is never rendered (tests/test_whole_flow_cases.py shows it), and the requirements task
builds on no stage. So the platform gives such a document as task memory ``document.<name>`` with its digest, and
the packet carries it as an approved upstream file: whole, citable, and withheld once its bytes change. Only that
task sees it. No single-seat case gives one, so every shipped case's prompt is byte for byte as before.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import load_cases
from nirmaan.integrations.veritriage import render_parts
from nirmaan.models import Actor, ActorKind, MemoryScope, TaskKind
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import context
from nirmaan.runtime.context import assemble
from nirmaan.runtime.files import digest
from nirmaan.runtime.prompt import render_work_prompt

ROOT = Path(__file__).resolve().parents[1]
TIMER = "Create an AXI4-Lite timer peripheral with an interrupt."
DOCUMENT = ROOT / "evals" / "flow" / "axil_timer" / "requirements.md"


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _prompt(engine, task_id: str, mode: str = "work") -> str:
    system, user = render_parts(render_work_prompt(assemble(engine, task_id), mode))
    return system + user


def _give(engine, task, path: Path, key: str = "document.customer_requirements") -> None:
    actor = Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name="eval-flow")
    engine.remember(MemoryScope.TASK, task.id, key, f"{digest(path.read_bytes())} {path}", actor)


def _stages(engine) -> dict:
    return {t.stage: t for t in engine.state.tasks.values() if t.kind is TaskKind.WORK and t.stage}


def test_the_document_reaches_the_requirements_seat_whole_and_citable(org, tmp_path):
    engine = Orchestrator(org).plan(TIMER)
    stages = _stages(engine)
    path = tmp_path / "requirements.md"
    shutil.copyfile(DOCUMENT, path)
    _give(engine, stages["requirements"], path)
    packet = assemble(engine, stages["requirements"].id)
    [view] = [a for a in packet.task.upstream_artifacts if a.kind == context.DOCUMENT_KIND]
    assert view.trusted and view.content == DOCUMENT.read_text(encoding="utf-8")
    prompt = render_work_prompt(packet)
    # Citable as a document, never as an artifact: no draft may derive from a record the engine does not hold.
    assert [c.kind for c in prompt.citations if c.target == view.id] == ["document"]
    text = "".join(render_parts(prompt))
    assert DOCUMENT.read_text(encoding="utf-8") in text and "customer_document, customer input" in text
    # Input from outside, never called approved by the organization.
    assert view.assurance == context.DOCUMENT_ASSURANCE and "customer_document, approved" not in text
    for stage, task in stages.items():  # only the task it was given to
        if stage != "requirements":
            assert "[req:TMR-MODULE]" not in _prompt(engine, task.id), stage


def test_a_changed_document_is_withheld_not_read(org, tmp_path):
    engine = Orchestrator(org).plan(TIMER)
    task = _stages(engine)["requirements"]
    path = tmp_path / "requirements.md"
    shutil.copyfile(DOCUMENT, path)
    _give(engine, task, path)
    path.write_text("changed after it was given\n", encoding="utf-8")
    prompt = _prompt(engine, task.id)
    assert "changed after it was given" not in prompt and "digest mismatch" in prompt


def test_only_a_task_scoped_document_key_counts(org, tmp_path):
    engine = Orchestrator(org).plan(TIMER)
    task = _stages(engine)["requirements"]
    actor = Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name="eval-flow")
    value = f"{digest(DOCUMENT.read_bytes())} {DOCUMENT}"
    engine.remember(MemoryScope.TASK, task.id, "input.customer_requirements", value, actor)  # an input: never shown
    engine.remember(MemoryScope.PROJECT, engine.state.project.id, "document.customer_requirements", value, actor)
    assert "[req:TMR-MODULE]" not in _prompt(engine, task.id)


@pytest.mark.parametrize("value", ["no-space-at-all", f"{DOCUMENT}", "sha256:abc "])
def test_a_malformed_document_value_shows_nothing(org, value):
    engine = Orchestrator(org).plan(TIMER)
    task = _stages(engine)["requirements"]
    actor = Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name="eval-flow")
    engine.remember(MemoryScope.TASK, task.id, "document.customer_requirements", str(value), actor)
    packet = assemble(engine, task.id)
    assert not [a for a in packet.task.upstream_artifacts if a.kind == context.DOCUMENT_KIND]


@pytest.mark.parametrize("case", load_cases(ROOT / "evals"), ids=lambda c: c.id)
def test_every_single_seat_cases_prompt_is_unchanged(org, monkeypatch, case):
    """With no document given, the packet and both prompts are byte for byte what they were without the route."""
    engine = Orchestrator(org).plan(case.request)
    seat = next(t for t in engine.state.tasks.values() if t.stage == case.seat and t.kind is not TaskKind.GATE)
    actor = Actor(role=str(seat.owner), kind=ActorKind.SYSTEM, name="eval-fixture")
    for key, paths in case.inputs.get(case.seat, {}).items():  # as the runner gives a seat its inputs (M71)
        engine.remember(MemoryScope.TASK, seat.id, f"input.{key}", ",".join(str(ROOT / p) for p in paths), actor)
    now = {mode: _prompt(engine, seat.id, mode) for mode in ("work", "review")}
    monkeypatch.setattr(context, "_documents_given", lambda state, task_id: [])
    assert {mode: _prompt(engine, seat.id, mode) for mode in ("work", "review")} == now


def test_a_seat_that_cites_the_document_is_not_refused_for_its_provenance(org, tmp_path):
    """The provenance check refuses a draft derived from an artifact the engine does not hold; a document is cited
    as a document, so a requirements seat grounding its work in the customer's document reaches review."""
    import json

    from nirmaan.runtime import Completion, ModelRuntime, run_task

    engine = Orchestrator(org).plan(TIMER)
    task = _stages(engine)["requirements"]
    path = tmp_path / "requirements.md"
    shutil.copyfile(DOCUMENT, path)
    _give(engine, task, path)

    class Seat:
        name = "test"

        def complete(self, prompt, tools=None):
            [token] = [c.token for c in prompt.citations if c.kind == "document"]
            head = json.dumps({"uncertainty": 0.0, "artifacts": [], "tool_runs": [], "claims": [], "escalation": None,
                               "notes": "", "files": [{"path": "requirements_spec.md", "kind": "requirements_spec",
                                                       "title": "requirements_spec.md",
                                                       "summary": f"The customer's requirements {token}."}]})
            return Completion(f"{head}\n=== FILE: requirements_spec.md ===\n{path.read_text()}=== END FILE ===\n",
                              "test")

    engine.remember(MemoryScope.TASK, task.id, "input.workspace", str(tmp_path / "seat"),
                    Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name="eval-flow"))
    run_task(engine, task.id, ModelRuntime(Seat(), runtime_id="test"))
    assert engine.task(task.id).status.value == "in_review"
    [art] = [engine.state.artifacts[a] for a in engine.task(task.id).artifacts]
    assert art.kind == "requirements_spec" and not art.derived_from
