"""Knowledge documents enter the work packet, within a budget (M61).

A skill that cites a knowledge document gets the document's whole text in the
Domain section of every packet that carries the skill. Over the 40,000
character domain cap, or with a cited document missing, the seat declines
with the reason and nothing is asked; a prompt over the seat's model context
declines with no model call. Every workflow seat's packet holds a full domain
scope within the default model's context today.
"""

from __future__ import annotations

import pytest

from test_nirmaan_applicability_golden import REQUESTS

from nirmaan.company import builder
from nirmaan.company.model_profiles import DEFAULT_MODEL
from nirmaan.models import KnowledgeSource, KnowledgeSourceKind
from nirmaan.org import OrganizationError
from nirmaan.org import knowledge
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import Completion, ModelRuntime, RegistryLLM, ResultStatus, assemble, render_work_prompt, run_task
from nirmaan.runtime.model import context_limit
from nirmaan.runtime.selection import SelectingLLM, model_profiles

SKILL = "requirements_engineering"
REF = f"product/{SKILL}"
REQUEST = "Create a parameterizable synchronous FIFO."
MARKER = "M61 fixture: a requirement names its verification method."


def _org_citing(ref: str = REF, skill: str = SKILL):
    b = builder()
    b.definition.skills = [
        s.model_copy(update={"knowledge_sources": (*s.knowledge_sources,
                                                   KnowledgeSource(kind=KnowledgeSourceKind.KNOWLEDGE_DOCUMENT,
                                                                   ref=ref, title=ref))})
        if s.id == skill else s
        for s in b.definition.skills
    ]
    return b.build()


@pytest.fixture()
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "KNOWLEDGE_ROOT", tmp_path)
    return tmp_path


def _write(root, ref: str, text: str) -> None:
    path = root / f"{ref}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _task(engine, stage: str) -> str:
    return next(t.id for t in engine.state.tasks.values() if t.id.endswith(":" + stage))


class Spy:
    """A runtime that records whether it was asked anything."""

    runtime_id = "spy"

    def __init__(self) -> None:
        self.asked = 0

    def accepts(self, packet) -> bool:
        self.asked += 1
        return True

    def execute(self, packet, tools):  # pragma: no cover - never reached when the seat declines
        raise AssertionError("a declining seat was asked to work")


def test_every_workflow_seat_holds_a_full_domain_scope_within_its_model_context(nirmaan_org, fixed_clock):
    limit = context_limit(RegistryLLM("anthropic"))
    assert limit == min(p.context_chars for p in model_profiles() if not p.for_testing)
    seats = 0
    for text in REQUESTS:
        engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(text)
        for task in engine.state.tasks.values():
            for seat, mode in ((task.owner, "work"), (task.reviewer, "review")):
                if seat is None:
                    continue
                packet = assemble(engine, task.id, role=seat)
                assert packet.domain.declines is None, (task.id, seat)
                rendered = len(render_work_prompt(packet, mode).render())
                # With the domain scope at its cap, the prompt still fits the default seat model.
                assert rendered + knowledge.DOMAIN_CAP <= limit, (task.id, seat, rendered)
                seats += 1
    assert seats > 100


def test_a_cited_document_is_in_the_prompt_of_the_seats_whose_skill_cites_it(root, fixed_clock):
    _write(root, REF, f"# Requirements engineering\n\n{MARKER}\n")
    engine = Orchestrator(_org_citing(), clock=fixed_clock).plan(REQUEST)
    requirements = _task(engine, "requirements")
    for seat, mode in ((engine.task(requirements).owner, "work"), (engine.task(requirements).reviewer, "review")):
        packet = assemble(engine, requirements, role=seat)
        assert [d.ref for d in packet.domain.documents] == [REF]
        assert packet.domain.documents[0].digest.startswith("sha256:")
        prompt = render_work_prompt(packet, mode).render()
        assert MARKER in prompt and f"Knowledge document {REF}" in prompt
    # A task whose skills do not include the citing skill never carries it.
    program = assemble(engine, _task(engine, "program"))
    assert program.domain.documents == () and MARKER not in render_work_prompt(program).render()


def test_a_document_no_skill_cites_never_reaches_a_prompt(root, nirmaan_org, fixed_clock):
    _write(root, REF, MARKER)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REQUEST)
    packet = assemble(engine, _task(engine, "requirements"))
    assert packet.domain.documents == ()
    assert MARKER not in render_work_prompt(packet).render()


def test_over_the_domain_cap_the_seat_declines_and_nothing_is_cut(root, fixed_clock):
    _write(root, REF, MARKER + "x" * knowledge.DOMAIN_CAP)
    engine = Orchestrator(_org_citing(), clock=fixed_clock).plan(REQUEST)
    task = _task(engine, "requirements")
    packet = assemble(engine, task)
    assert packet.domain.documents == ()
    assert "over the domain cap of 40000" in packet.domain.declines
    assert MARKER not in render_work_prompt(packet).render()

    spy = Spy()
    report = run_task(engine, task, spy)
    assert report.status is ResultStatus.DECLINED and "over the domain cap" in report.detail
    assert spy.asked == 0 and engine.task(task).status.value == "ready"


def test_at_the_domain_cap_the_document_is_carried_whole(root, fixed_clock):
    text = MARKER + "y" * (knowledge.DOMAIN_CAP - len(MARKER))
    _write(root, REF, text)
    engine = Orchestrator(_org_citing(), clock=fixed_clock).plan(REQUEST)
    packet = assemble(engine, _task(engine, "requirements"))
    assert packet.domain.declines is None and packet.domain.documents[0].text == text


def test_a_cited_document_that_is_missing_makes_the_seat_decline(root, fixed_clock):
    engine = Orchestrator(_org_citing(), clock=fixed_clock).plan(REQUEST)
    task = _task(engine, "requirements")
    packet = assemble(engine, task)
    assert packet.domain.documents == () and "cited but missing" in packet.domain.declines
    report = run_task(engine, task, Spy())
    assert report.status is ResultStatus.DECLINED and SKILL in report.detail


class TinyLLM:
    """A model that accepts very little, and counts the calls it gets."""

    name = "tiny"
    context_chars = 1_000

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt):  # pragma: no cover - never called over the limit
        self.calls += 1
        return Completion("{}")


def test_a_prompt_over_the_seat_models_context_declines_with_no_call(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REQUEST)
    task = _task(engine, "requirements")
    llm = TinyLLM()
    report = run_task(engine, task, ModelRuntime(llm, runtime_id="tiny"))
    assert report.status is ResultStatus.DECLINED
    assert "over the seat's model context of 1000" in report.detail
    assert llm.calls == 0 and not engine.state.model_calls


def test_the_context_limit_comes_from_the_model_profiles():
    assert context_limit(RegistryLLM("anthropic")) == 400_000
    assert context_limit(type("Named", (), {"name": "x", "model": DEFAULT_MODEL})()) == 400_000
    assert context_limit(SelectingLLM()) is None  # the auto runtime checks each profile itself (M31)
    assert context_limit(type("Unknown", (), {"name": "nobody"})()) is None


@pytest.mark.parametrize("ref", ["product/other_skill", "requirements_engineering", "../product/requirements_engineering",
                                 "product/Requirements_Engineering"])
def test_a_document_ref_must_be_division_slash_the_citing_skill(ref):
    with pytest.raises(OrganizationError, match="knowledge document ref"):
        _org_citing(ref=ref)

