"""Milestone 31 (working name): a seat states what it needs, a model is chosen, and every call is counted.

Needs are derived from the work (structured output always; files when the
task's checks run over files it produces; plus a capability's declared
``model_needs``). ``select_model`` keeps the profiles that offer every need and
hold the prompt, and picks the cheapest, or refuses with every reason. Every
model call, successful or not, becomes a ``ModelCall`` the engine records, with
tokens and cost as reported, and ``None`` where nothing was reported.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import types

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid

from nirmaan.cli import app
from nirmaan.demos import demo
from nirmaan.models import ModelProfile
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    Completion,
    MockLLM,
    ModelRuntime,
    ResultStatus,
    assemble,
    get_runtime,
    review_task,
    run_task,
)
from nirmaan.runtime.selection import (
    SelectingLLM,
    model_profiles,
    register_model_profile,
    seat_needs,
    select_model,
    unregister_model_profile,
)
from nirmaan.costs import cost_report
from nirmaan.work import ProjectStore

REGRESSION = demo("4").requirement


@pytest.fixture()
def regression(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)


def _triage_ready(engine):
    triage = tid(engine, "triage")
    drive(engine, until=triage)
    return triage


def _answer(**fields) -> str:
    return json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "escalation": None,
                       **fields})


class _Metered:
    """The deterministic MockLLM answer (it cites real prompt tokens), reported as an Opus call with usage."""

    name = "metered"

    def complete(self, prompt):
        return dataclasses.replace(MockLLM().complete(prompt), model="claude-opus-5-5", provider="anthropic",
                                   input_tokens=1000, output_tokens=200)


def _profile(pid: str, offers=("structured_output", "files"), price=1.0, context=1_000_000, testing=False,
             provider="mock-llm") -> ModelProfile:
    return ModelProfile(id=pid, provider=provider, model=pid, offers=offers, context_chars=context,
                        input_per_mtok=price, output_per_mtok=price * 5, for_testing=testing)


# --- Selection -----------------------------------------------------------------------------


def test_the_shipped_profiles():
    profiles = {p.id: p for p in model_profiles()}
    opus = profiles["claude-opus-5-5"]
    assert opus.provider == "anthropic" and opus.input_per_mtok == 4.0 and opus.output_per_mtok == 20.0
    assert opus.cache_read_per_mtok == 0.2 and not opus.for_testing
    assert profiles["mock-llm"].for_testing


def test_a_need_no_profile_offers_is_refused_with_every_reason():
    choice = select_model(("structured_output", "telepathy"), prompt_chars=100)
    assert choice.profile is None
    assert choice.rejected and all("telepathy" in why for why in choice.rejected.values()
                                   if "testing" not in why)


def test_a_prompt_larger_than_a_context_is_refused():
    register_model_profile(_profile("tiny", context=50))
    try:
        choice = select_model(("structured_output",), prompt_chars=100, profiles=[_profile("tiny", context=50)])
        assert choice.profile is None and "context" in choice.rejected["tiny"]
    finally:
        unregister_model_profile("tiny")


def test_the_cheapest_fitting_profile_wins_and_testing_profiles_only_when_asked():
    cheap, dear = _profile("cheap", price=0.5), _profile("dear", price=3.0)
    assert select_model(("structured_output",), 10, profiles=[dear, cheap]).profile.id == "cheap"
    test_only = _profile("free-test", price=0.0, testing=True)
    assert select_model(("structured_output",), 10, profiles=[dear, test_only]).profile.id == "dear"
    assert select_model(("structured_output",), 10, profiles=[dear, test_only],
                        include_testing=True).profile.id == "free-test"


def test_seat_needs_come_from_the_work(nirmaan_org, fixed_clock, regression):
    block = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    rtl = assemble(block, tid(block, "rtl-implementation"))
    assert set(seat_needs(rtl)) == {"structured_output", "files"}
    triage = assemble(regression, tid(regression, "triage"))
    assert seat_needs(triage) == ("structured_output",)
    declared = dataclasses.replace(triage, task={**triage.task, "model_needs": ["vision"]})
    assert set(seat_needs(declared)) == {"structured_output", "vision"}


# --- Accounting ----------------------------------------------------------------------------


def test_work_and_review_calls_are_recorded_with_tokens_and_cost(regression, fixture_log, tmp_path):
    triage = _triage_ready(regression)
    report = run_task(regression, triage, ModelRuntime(_Metered(), runtime_id="metered"))
    calls = list(regression.state.model_calls.values())
    assert len(calls) == 1, report.detail
    call = calls[0]
    assert call.task == triage and call.purpose == "work" and call.model == "claude-opus-5-5"
    assert call.input_tokens == 1000 and call.output_tokens == 200
    assert call.cost_usd == pytest.approx(1000 * 4 / 1e6 + 200 * 20 / 1e6)
    assert any(e.action == "model.call" for e in regression.state.audit)


def test_a_declined_answer_still_records_its_call_and_unknown_usage_stays_unknown(regression):
    triage = _triage_ready(regression)
    reply = Completion(text="I think it is an RTL bug.", model="claude-opus-5-5")
    report = run_task(regression, triage, ModelRuntime(MockLLM(script=[reply])))
    assert report.status is ResultStatus.DECLINED
    [call] = regression.state.model_calls.values()
    assert call.input_tokens is None and call.output_tokens is None and call.cost_usd is None
    failed = Completion(text="", error="APIConnectionError: offline")
    run_task(regression, triage, ModelRuntime(MockLLM(script=[failed])))
    calls = sorted(regression.state.model_calls.values(), key=lambda c: c.id)
    assert len(calls) == 2 and not calls[1].succeeded and "offline" in calls[1].error


def test_a_review_call_is_recorded(regression, fixture_log, tmp_path):
    from test_nirmaan_ai_workers import _triaged

    triage = _triaged(regression, fixture_log, tmp_path)
    before = len(regression.state.model_calls)
    review = Completion(text=json.dumps({"verdict": "approve", "uncertainty": 0.1, "comments": "fine"}),
                        model="claude-opus-5-5", input_tokens=500, output_tokens=50)
    review_task(regression, triage, ModelRuntime(MockLLM(script=[review])))
    new = [c for c in regression.state.model_calls.values()][before:]
    assert [c.purpose for c in new] == ["review"] and new[0].output_tokens == 50


def test_nirmaan_costs_adds_them_up(regression, tmp_path):
    triage = _triage_ready(regression)
    for tokens in (1000, 3000):
        reply = Completion(text="unusable", model="claude-opus-5-5", input_tokens=tokens, output_tokens=100)
        run_task(regression, triage, ModelRuntime(MockLLM(script=[reply])))
    run_task(regression, triage, ModelRuntime(MockLLM(script=[Completion(text="unusable")])))
    report = cost_report(regression.state)
    assert report.calls == 3 and report.input_tokens == 4000 and report.unknown_cost_calls == 1
    assert report.cost_usd == pytest.approx(4000 * 4 / 1e6 + 200 * 20 / 1e6)
    root = tmp_path / "store"
    ProjectStore(root).save(regression.state)
    out = CliRunner().invoke(app, ["costs", regression.state.project.id, "--root", str(root), "--json"])
    assert out.exit_code == 0, out.output
    data = json.loads(out.output)
    assert data["calls"] == 3 and data["by_model"]["claude-opus-5-5"]["calls"] == 2


def _fake_anthropic(monkeypatch, usage=True):
    class _Messages:
        def create(self, **kwargs):
            block = types.SimpleNamespace(type="text", text="{}")
            response = types.SimpleNamespace(stop_reason="end_turn", content=[block], model=kwargs["model"])
            if usage:
                response.usage = types.SimpleNamespace(input_tokens=1200, output_tokens=300,
                                                       cache_read_input_tokens=800,
                                                       cache_creation_input_tokens=0)
            return response

    class Anthropic:
        def __init__(self):
            self.beta = types.SimpleNamespace(messages=_Messages())

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Anthropic))


@pytest.mark.parametrize("usage", [True, False])
def test_the_anthropic_provider_reports_usage_when_the_sdk_does(regression, monkeypatch, usage):
    from nirmaan.runtime import render_work_prompt

    _fake_anthropic(monkeypatch, usage=usage)
    completion = get_runtime("anthropic").llm.complete(render_work_prompt(assemble(regression, tid(regression,
                                                                                                    "triage"))))
    assert completion.error is None and completion.provider == "anthropic"
    if usage:
        assert (completion.input_tokens, completion.output_tokens, completion.cache_read_tokens) == (1200, 300, 800)
    else:
        assert completion.input_tokens is None and completion.output_tokens is None


def test_an_evaluation_result_carries_its_calls(nirmaan_org, fixed_clock, tmp_path):
    from test_nirmaan_evals import _spec_case

    from nirmaan.evals import load_case, run_case

    case = load_case(_spec_case(tmp_path, []))
    reply = Completion(text="unusable", model="claude-opus-5-5", input_tokens=2000, output_tokens=100)
    result = run_case(nirmaan_org, case, ModelRuntime(MockLLM(script=[reply]), runtime_id="metered"), repo=tmp_path,
                      sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.model_calls == 1 and result.input_tokens == 2000 and result.output_tokens == 100
    assert result.cost_usd == pytest.approx(2000 * 4 / 1e6 + 100 * 20 / 1e6)


# --- The auto runtime and the crown jewel ---------------------------------------------------


def test_auto_with_nothing_fitting_declines_without_calling(regression):
    triage = _triage_ready(regression)
    llm = SelectingLLM(profiles=[_profile("text-only", offers=("files",))])
    report = run_task(regression, triage, ModelRuntime(llm, runtime_id="auto"))
    assert report.status is ResultStatus.DECLINED and "no model fits" in report.detail
    assert not regression.state.model_calls  # nothing was called, so nothing is counted


def test_a_new_model_profile_needs_no_core_changes(regression):
    """A profile registered here is cheaper than Opus and fits; ``auto`` chooses it and counts its call."""
    register_model_profile(ModelProfile(id="house-model", provider="mock-llm", model="house-model-1",
                                        offers=("structured_output", "files"), context_chars=2_000_000,
                                        input_per_mtok=0.5, output_per_mtok=2.0))
    try:
        assert "house-model" in {p.id for p in model_profiles()}
        triage = _triage_ready(regression)
        run_task(regression, triage, get_runtime("auto"))
        [call] = regression.state.model_calls.values()
        assert call.model == "house-model-1" and call.provider == "mock-llm"
    finally:
        unregister_model_profile("house-model")
    assert "house-model" not in {p.id for p in model_profiles()}
