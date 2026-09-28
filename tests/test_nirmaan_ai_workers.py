"""Milestone 20: the first AI workers, seated in verification.

A model-backed runtime renders a work packet into a prompt, asks a language
model, and hands back a result the engine judges like any other. No test here
calls a model API: ``MockLLM`` is deterministic, and the Anthropic provider is
exercised against a fake SDK module.
"""

from __future__ import annotations

import json
import sys
import types

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import drive, human, tid

from nirmaan.models import EvidenceKind, MemoryScope, ReviewState, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    Completion,
    MockLLM,
    ModelRuntime,
    RegistryLLM,
    ResultStatus,
    assemble,
    available_runtimes,
    get_runtime,
    register_runtime,
    render_work_prompt,
    review_task,
    run_task,
    unregister_runtime,
)
from nirmaan.work import PolicyViolationError, ProjectStore

REGRESSION = "Investigate a regression failure introduced by a recent RTL commit."


@pytest.fixture()
def regression(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)


def _inputs(engine, task_id, fixture_log, tmp_path):
    """What a person hands the triage seat: the failing logs, and where VeriTriage may write."""
    owner = human(engine.task(task_id).owner)
    engine.remember(MemoryScope.TASK, task_id, "input.paths", str(fixture_log("axi_timeout.log")), owner)
    engine.remember(MemoryScope.TASK, task_id, "input.workspace", str(tmp_path), owner)


def _work(**fields) -> str:
    return json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], **fields})


def _triaged(engine, fixture_log, tmp_path):
    triage = tid(engine, "triage")
    _inputs(engine, triage, fixture_log, tmp_path)
    run_task(engine, triage, ModelRuntime(MockLLM()))
    return triage


# --- The seats -------------------------------------------------------------------------------


def test_a_model_triages_with_real_veritriage(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    _inputs(regression, triage, fixture_log, tmp_path)
    llm = MockLLM()
    report = run_task(regression, triage, ModelRuntime(llm))

    assert report.status is ResultStatus.SUBMITTED
    assert regression.task(triage).status is TaskStatus.COMPLETED
    run = regression.state.tool_runs[report.tool_runs[0]]
    assert run.tool == "veritriage.investigate" and run.succeeded
    ev = regression.state.evidence[report.evidence[0]]
    assert ev.kind is EvidenceKind.VERITRIAGE_SESSION and ev.substantiated and ev.tool_run == run.id
    # The model saw the run it can cite, and its report cites it.
    assert f"[run:{run.id}]" in llm.calls[0].render()
    art = regression.state.artifacts[regression.task(triage).artifacts[0]]
    assert f"[run:{run.id}]" in art.summary and art.produced_by.startswith("mock-llm@")


def test_root_cause_concludes_a_declared_outcome_from_triage_evidence(regression, fixture_log, tmp_path):
    triage = _triaged(regression, fixture_log, tmp_path)
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    packet = assemble(regression, root)
    assert any(e["task"] == triage and e["substantiated"] for e in packet.task["evidence"])

    report = run_task(regression, root, ModelRuntime(MockLLM()))
    task = regression.task(root)
    assert report.status is ResultStatus.SUBMITTED
    assert task.status is TaskStatus.IN_REVIEW and task.outcome in task.outcomes
    summary = regression.state.artifacts[task.artifacts[0]].summary
    assert "[evidence:" in summary or "[run:" in summary


def test_demo_4_runs_on_agents_and_ends_at_a_human_approval(regression, fixture_log, tmp_path):
    """Triage, root cause, and review by agents on fixture logs; a person approves."""
    _triaged(regression, fixture_log, tmp_path)
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)  # change correlation, done the ordinary way
    run_task(regression, root, ModelRuntime(MockLLM()))

    reviewer = ModelRuntime(MockLLM())
    review = review_task(regression, root, reviewer)
    task = regression.task(root)
    assert review.status is ResultStatus.SUBMITTED
    assert task.review_state is ReviewState.PASSED and task.status is TaskStatus.IN_REVIEW
    record = regression.state.reviews[review.review]
    assert record.reviewer == task.reviewer != task.owner

    # Agents cannot finish the job: the approval is a person's.
    regression.approve(root, human(task.approver), "agreed with the agents")
    task = regression.task(root)
    assert task.status is TaskStatus.COMPLETED
    assert all(regression.state.artifacts[a].assurance.value == "approved" for a in task.artifacts)
    # The agents' conclusion picked the fix branch; the other three were cancelled.
    taken = {t.stage for t in regression.state.tasks.values()
             if t.branch and t.status is not TaskStatus.CANCELLED}
    assert taken == {t.stage for t in regression.state.tasks.values() if t.branch == (root, task.outcome)}
    assert len(taken) == 1


# --- The constitution holds against a model -----------------------------------------------


def test_an_agent_citing_a_run_that_never_happened_is_refused(regression):
    triage = tid(regression, "triage")
    # The pre-flight VeriTriage call (given no logs) is a real, failed run-0001; run-0042 never happened.
    lie = _work(artifacts=[{"kind": "triage_report", "title": "RTL bug",
                            "summary": "Triage [run:run-0001] was inconclusive; the simulator proved it [run:run-0042]."}],
                tool_runs=["run-0042"])
    with pytest.raises(PolicyViolationError, match="P5"):
        run_task(regression, triage, ModelRuntime(MockLLM(script=[lie])))
    assert set(regression.state.tool_runs) == {"run-0001"}
    assert not regression.task(triage).artifacts


def test_an_agent_cannot_review_its_own_output(regression, fixture_log, tmp_path):
    _triaged(regression, fixture_log, tmp_path)
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    run_task(regression, root, ModelRuntime(MockLLM()))

    llm = MockLLM()
    with pytest.raises(PolicyViolationError, match="P6"):
        review_task(regression, root, ModelRuntime(llm), role=regression.task(root).owner)
    assert llm.calls == []  # refused before any model call
    assert regression.task(root).review_state is ReviewState.PENDING


def test_invented_citations_are_stripped_and_reported(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    _inputs(regression, triage, fixture_log, tmp_path)
    text = _work(artifacts=[{"kind": "triage_report", "title": "Timeout",
                             "summary": "AXI timeout [run:run-0001] per [evidence:ev-invented]."}])
    report = run_task(regression, triage, ModelRuntime(MockLLM(script=[text])))
    art = regression.state.artifacts[regression.task(triage).artifacts[0]]
    assert "[run:run-0001]" in art.summary and "ev-invented" not in art.summary
    assert "[evidence:ev-invented]" in report.detail


def test_an_uncited_artifact_is_dropped_and_completion_refused(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    _inputs(regression, triage, fixture_log, tmp_path)
    text = _work(artifacts=[{"kind": "triage_report", "title": "Trust me", "summary": "It is an RTL bug."}])
    with pytest.raises(PolicyViolationError, match="P4"):
        run_task(regression, triage, ModelRuntime(MockLLM(script=[text])))


def test_undeclared_uncertainty_is_refused(regression):
    text = json.dumps({"artifacts": [{"kind": "triage_report", "title": "x", "summary": "y"}]})
    with pytest.raises(PolicyViolationError, match="P3"):
        run_task(regression, tid(regression, "triage"), ModelRuntime(MockLLM(script=[text])))


@pytest.mark.parametrize("reply", [Completion(text="", error="APIConnectionError: offline"),
                                   Completion(text="I think it is an RTL bug.")])
def test_a_failed_or_unreadable_call_records_nothing(regression, reply):
    triage = tid(regression, "triage")
    report = run_task(regression, triage, ModelRuntime(MockLLM(script=[reply])))
    assert report.status is ResultStatus.DECLINED
    assert not regression.task(triage).artifacts and regression.task(triage).status is TaskStatus.IN_PROGRESS
    assert not any(regression.state.evidence[e].kind is EvidenceKind.CLAIM for e in report.evidence)


def test_a_model_can_ask_to_escalate(regression):
    text = _work(uncertainty=0.9, escalation={"reason": "the log is truncated",
                                              "question": "Can the test be re-run with full logging?"})
    report = run_task(regression, tid(regression, "triage"), ModelRuntime(MockLLM(script=[text])))
    assert report.status is ResultStatus.NEEDS_ESCALATION
    assert regression.state.escalations[report.escalation].blocking_question.startswith("Can the test")


def test_an_uncited_review_is_not_recorded(regression, fixture_log, tmp_path):
    _triaged(regression, fixture_log, tmp_path)
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    run_task(regression, root, ModelRuntime(MockLLM()))
    text = json.dumps({"verdict": "approve", "comments": "Looks fine to me.", "uncertainty": 0.1})
    review = review_task(regression, root, ModelRuntime(MockLLM(script=[text])))
    assert review.status is ResultStatus.DECLINED
    assert regression.task(root).review_state is ReviewState.PENDING


# --- Prompts ----------------------------------------------------------------------------------


def test_prompts_render_only_the_four_scopes(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    _inputs(regression, triage, fixture_log, tmp_path)
    prompt = render_work_prompt(assemble(regression, triage))
    assert [heading for heading, _ in prompt.sections] == ["Company", "Domain", "Project", "Task"]
    text = prompt.render()
    assert text == render_work_prompt(assemble(regression, triage)).render()  # deterministic
    assert "input.paths" not in text and "axi_timeout.log" not in text  # memory is never rendered
    assert "P5" in text and REGRESSION in text


def test_evidence_ids_become_citable_tokens(regression, fixture_log, tmp_path):
    _triaged(regression, fixture_log, tmp_path)
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    prompt = render_work_prompt(assemble(regression, root))
    ev_id = next(e for e in regression.state.evidence if e.startswith(tid(regression, "triage")))
    token = next(c.token for c in prompt.citations if c.target == ev_id)
    assert token.startswith("[evidence:") and ":" not in token[10:] and "#" not in token
    assert prompt.resolve(token) == ev_id and token in prompt.render()


# --- Registries: one vendor registry, runtimes by registration --------------------------------


def test_any_m17_provider_serves_a_seat_through_the_one_registry(regression, fixture_log, tmp_path):
    from veritriage.ai.providers import MockProvider

    triage = tid(regression, "triage")
    _inputs(regression, triage, fixture_log, tmp_path)
    MockProvider.script = [_work(artifacts=[{"kind": "triage_report", "title": "Timeout",
                                             "summary": "AXI timeout [run:run-0001]."}])]
    try:
        report = run_task(regression, triage, ModelRuntime(RegistryLLM("mock")))
    finally:
        MockProvider.reset()
    assert report.status is ResultStatus.SUBMITTED
    assert regression.task(triage).status is TaskStatus.COMPLETED


def test_a_new_runtime_registers_with_zero_core_changes(regression, fixture_log, tmp_path):
    """Crown jewel: a new model runtime is one registration and works from the CLI."""

    class AcmeLLM:
        name = "acme"

        def complete(self, prompt):
            run = next(c.token for c in prompt.citations if c.token.startswith("[run:"))
            return Completion(text=_work(artifacts=[{"kind": "triage_report", "title": "Acme triage",
                                                     "summary": f"Timeout on the AXI port {run}."}]))

    register_runtime("acme-test")(lambda: ModelRuntime(AcmeLLM(), runtime_id="acme-test"))
    try:
        assert "acme-test" in available_runtimes()
        root = tmp_path / "store"
        ProjectStore(root).save(regression.state)
        result = CliRunner().invoke(_app(), [
            "run", regression.state.project.id, "triage", "--runtime", "acme-test",
            "--input", f"paths={fixture_log('axi_timeout.log')}", "--input", f"workspace={tmp_path}",
            "--root", str(root)])
        assert result.exit_code == 0, result.output
        state = ProjectStore(root).load(regression.state.project.id)
        task = state.tasks[tid(regression, "triage")]
        assert task.status is TaskStatus.COMPLETED
        assert state.artifacts[task.artifacts[0]].produced_by.startswith("acme-test@")
    finally:
        unregister_runtime("acme-test")
    assert "acme-test" not in available_runtimes()


# --- Nothing changes without a model ----------------------------------------------------------


def _app():
    from nirmaan.cli import app

    return app


def test_nothing_changes_for_users_without_a_model(regression, tmp_path):
    assert {"unbound", "mock-llm", "anthropic"} <= set(available_runtimes())
    root = tmp_path / "store"
    ProjectStore(root).save(regression.state)
    before = len(regression.state.audit)
    result = CliRunner().invoke(_app(), ["run", regression.state.project.id, "triage", "--root", str(root)])
    assert result.exit_code == 0 and "declined" in result.output
    state = ProjectStore(root).load(regression.state.project.id)
    assert len(state.audit) == before and state.tool_runs == {}
    assert state.tasks[tid(regression, "triage")].status is TaskStatus.READY


def test_dry_run_shows_the_exact_prompt_and_changes_nothing(regression, tmp_path):
    root = tmp_path / "store"
    ProjectStore(root).save(regression.state)
    before = len(regression.state.audit)
    result = CliRunner().invoke(_app(), ["run", regression.state.project.id, "triage", "--runtime", "anthropic",
                                         "--dry-run", "--root", str(root)])
    assert result.exit_code == 0, result.output
    expected = render_work_prompt(assemble(regression, tid(regression, "triage"))).render()
    assert expected.splitlines()[0] in result.output and "## Task" in result.output
    assert len(ProjectStore(root).load(regression.state.project.id).audit) == before


# --- The Anthropic provider, against a fake SDK -----------------------------------------------


def _fake_anthropic(monkeypatch, stop_reason="end_turn", text="{}"):
    sent: dict = {}

    class _Messages:
        def create(self, **kwargs):
            sent.update(kwargs)
            block = types.SimpleNamespace(type="text", text=text)
            return types.SimpleNamespace(stop_reason=stop_reason, content=[block], model=kwargs["model"])

    class Anthropic:
        def __init__(self):
            self.beta = types.SimpleNamespace(messages=_Messages())

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Anthropic))
    return sent


def test_the_anthropic_seat_sends_one_grounded_prompt(regression, monkeypatch):
    sent = _fake_anthropic(monkeypatch, text="not json")
    runtime = get_runtime("anthropic")
    prompt = render_work_prompt(assemble(regression, tid(regression, "triage")))
    completion = runtime.llm.complete(prompt)
    assert completion.error is None and completion.text == "not json"
    assert sent["model"] == "claude-opus-5" and sent["thinking"] == {"type": "adaptive"}
    assert sent["system"] == prompt.system and "## Company" in sent["messages"][0]["content"]
    assert sent["fallbacks"] == "default" and sent["betas"] == ["server-side-fallback-2026-07-01"]


def test_an_anthropic_refusal_is_a_failed_call_not_work(regression, monkeypatch):
    _fake_anthropic(monkeypatch, stop_reason="refusal")
    report = run_task(regression, tid(regression, "triage"), get_runtime("anthropic"))
    assert report.status is ResultStatus.DECLINED and "refusal" in report.detail
