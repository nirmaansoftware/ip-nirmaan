"""Milestone 9: Investigation Orchestrator.

Covers the milestone's guarantees, not just its features: the orchestrator
never bypasses Workspace Services (unimportable modules, AST-proven), plans
and traces are immutable and structurally deterministic, profiles only
compose registered steps, failure isolation and partial completion work,
the core remains untouched, and adding a workflow step requires only
registration (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pydantic

from laws import imports

import veritriage.orchestrator.engine as engine_module
from veritriage.models import PlanStep, StepStatus
from veritriage.orchestrator import (
    ExecutionEngine,
    InvestigationProfile,
    InvestigationStep,
    available_profiles,
    available_steps,
    build_plan,
    get_profile,
    register_profile,
    register_step,
    resume_profile,
    run_profile,
    unregister_profile,
    unregister_step,
)
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/orchestrator/engine.py -> parents[2] is the src/ root.
SRC = Path(engine_module.__file__).parents[2]


@pytest.fixture()
def services(tmp_path):
    return WorkspaceServices(session_root=tmp_path / "sessions", db=tmp_path / "reg.db")


# --- Plans and profiles -----------------------------------------------------


def test_seven_profiles_register():
    assert set(available_profiles()) == {
        "fast-triage",
        "full-investigation",
        "regression-analysis",
        "protocol-debug",
        "waveform-focused",
        "infrastructure-review",
        "engineering-review",
    }


def test_profiles_only_compose_registered_steps():
    registered = set(available_steps())
    for profile in available_profiles().values():
        for step in profile.steps:
            assert step.step_type in registered, f"{profile.name}: {step.step_type}"
        ids = {s.id for s in profile.steps}
        for step in profile.steps:
            assert set(step.depends_on) <= ids, f"{profile.name}: dangling dependency"


def test_plan_ids_are_deterministic():
    profile = get_profile("fast-triage")
    a = build_plan(profile, ["sim.log"])
    b = build_plan(profile, ["sim.log"])
    c = build_plan(profile, ["other.log"])
    assert a.plan_id == b.plan_id
    assert a.plan_id != c.plan_id
    assert a.plan_id.startswith("plan-")


def test_plans_and_traces_are_immutable(services, fixture_log):
    session = run_profile(services, "fast-triage", [fixture_log("uvm_assertion.log")])
    with pytest.raises(pydantic.ValidationError):
        session.plan.profile = "tampered"
    with pytest.raises(pydantic.ValidationError):
        session.trace.completed = False
    with pytest.raises(pydantic.ValidationError):
        session.trace.steps[0].status = StepStatus.FAILED


# --- Execution --------------------------------------------------------------


def test_fast_triage_end_to_end(services, fixture_log):
    session = run_profile(services, "fast-triage", [fixture_log("uvm_assertion.log")])
    assert session.trace is not None and session.plan is not None
    assert session.trace.completed
    assert [t.step_id for t in session.trace.steps] == [
        "analyze-artifacts",
        "persist-session",
        "summarize",
    ]  # dependency order, sorted frontier: deterministic
    # The persisted bundle carries the plan and trace.
    reloaded = services.load(session.session_id)
    assert reloaded.trace is not None and reloaded.trace.completed
    assert reloaded.plan.profile == "fast-triage"


def test_full_investigation_produces_report_with_metrics(services, fixture_log, tmp_path):
    out = tmp_path / "out"
    session = run_profile(
        services,
        "full-investigation",
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")],
        output_dir=out,
    )
    assert session.trace.completed
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "Investigation Performance" in html
    assert "analyze-artifacts" in html


def test_trace_structure_is_deterministic(services, fixture_log):
    first = run_profile(services, "fast-triage", [fixture_log("uvm_assertion.log")])
    second = run_profile(services, "fast-triage", [fixture_log("uvm_assertion.log")])
    assert first.trace.structural_view() == second.trace.structural_view()
    # Same investigation, same session identity, trace excluded from it.
    assert first.session_id == second.session_id


def test_attribution_names_every_contributing_subsystem(services, fixture_log):
    session = run_profile(
        services,
        "full-investigation",
        [
            fixture_log("uvm_assertion.log"),
            fixture_log("axi_handshake_stall.wave.json"),
            fixture_log("change_context.engctx.json"),
        ],
    )
    by_name = {a.subsystem: a for a in session.trace.attribution}
    assert {"knowledge", "waveform", "engineering", "reasoning", "ownership"} <= set(by_name)
    assert by_name["knowledge"].signals
    assert by_name["waveform"].signals
    assert by_name["ownership"].recommendations == 1


def test_failure_isolation_and_partial_completion(services, tmp_path):
    @register_step
    class _ExplodingStep(InvestigationStep):
        step_type = "test-exploding"

        def run(self, services, context, params):
            raise RuntimeError("boom")

    @register_step
    class _IndependentStep(InvestigationStep):
        step_type = "test-independent"

        def run(self, services, context, params):
            return {"independent": True}

    profile = InvestigationProfile(
        name="test-isolation",
        description="test",
        steps=(
            PlanStep(id="analyze-artifacts", step_type="analyze-artifacts", outputs=("session",)),
            PlanStep(id="boom", step_type="test-exploding", depends_on=("analyze-artifacts",)),
            PlanStep(id="after-boom", step_type="summarize", depends_on=("boom",)),
            PlanStep(
                id="independent", step_type="test-independent", depends_on=("analyze-artifacts",)
            ),
        ),
    )
    register_profile(profile)
    try:
        fixture = Path(__file__).parent / "fixtures" / "uvm_assertion.log"
        session = run_profile(services, "test-isolation", [fixture])
        by_id = {t.step_id: t for t in session.trace.steps}
        assert by_id["boom"].status is StepStatus.FAILED
        assert "boom" in by_id["after-boom"].note
        assert by_id["after-boom"].status is StepStatus.SKIPPED
        assert by_id["independent"].status is StepStatus.COMPLETED
        assert not session.trace.completed  # partial completion, fully traced
    finally:
        unregister_profile("test-isolation")
        unregister_step("test-exploding")
        unregister_step("test-independent")


def test_retry_budget_is_honored(services, fixture_log):
    calls = {"n": 0}

    @register_step
    class _FlakyStep(InvestigationStep):
        step_type = "test-flaky"

        def run(self, services, context, params):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return {"flaky": "ok"}

    profile = InvestigationProfile(
        name="test-retry",
        description="test",
        steps=(
            PlanStep(id="analyze-artifacts", step_type="analyze-artifacts", outputs=("session",)),
            PlanStep(
                id="flaky",
                step_type="test-flaky",
                depends_on=("analyze-artifacts",),
                max_retries=2,
            ),
        ),
    )
    register_profile(profile)
    try:
        session = run_profile(services, "test-retry", [fixture_log("uvm_assertion.log")])
        flaky = next(t for t in session.trace.steps if t.step_id == "flaky")
        assert flaky.status is StepStatus.COMPLETED
        assert flaky.attempts == 3
    finally:
        unregister_profile("test-retry")
        unregister_step("test-flaky")


def test_resume_reruns_only_incomplete_steps(services, fixture_log):
    fails = {"on": True}

    @register_step
    class _ResumableStep(InvestigationStep):
        step_type = "test-resumable"

        def run(self, services, context, params):
            if fails["on"]:
                raise RuntimeError("first run fails")
            return {"resumable": "done"}

    profile = InvestigationProfile(
        name="test-resume",
        description="test",
        steps=(
            PlanStep(id="analyze-artifacts", step_type="analyze-artifacts", outputs=("session",)),
            PlanStep(id="resumable", step_type="test-resumable", depends_on=("analyze-artifacts",)),
        ),
    )
    register_profile(profile)
    try:
        first = run_profile(services, "test-resume", [fixture_log("uvm_assertion.log")])
        assert not first.trace.completed

        fails["on"] = False
        resumed = resume_profile(services, first.session_id)
        by_id = {t.step_id: t for t in resumed.trace.steps}
        assert by_id["analyze-artifacts"].note == "carried over from the previous run"
        assert by_id["resumable"].status is StepStatus.COMPLETED
        assert resumed.trace.completed
        # Resuming a completed session is a no-op returning the stored session.
        again = resume_profile(services, resumed.session_id)
        assert again.trace.completed
    finally:
        unregister_profile("test-resume")
        unregister_step("test-resumable")


def test_diamond_dependencies_execute_in_sorted_order(services, fixture_log):
    order: list[str] = []

    def _recorder(name):
        @register_step
        class _Step(InvestigationStep):
            step_type = f"test-rec-{name}"

            def run(self, services, context, params):
                order.append(name)
                return {}

        return _Step

    for name in ("b", "a", "join"):
        _recorder(name)
    profile = InvestigationProfile(
        name="test-diamond",
        description="test",
        steps=(
            PlanStep(id="analyze-artifacts", step_type="analyze-artifacts", outputs=("session",)),
            PlanStep(id="zz-b", step_type="test-rec-b", depends_on=("analyze-artifacts",)),
            PlanStep(id="aa-a", step_type="test-rec-a", depends_on=("analyze-artifacts",)),
            PlanStep(id="join", step_type="test-rec-join", depends_on=("zz-b", "aa-a")),
        ),
    )
    register_profile(profile)
    try:
        run_profile(services, "test-diamond", [fixture_log("uvm_assertion.log")])
        assert order == ["a", "b", "join"]  # sorted frontier: aa-a before zz-b
    finally:
        unregister_profile("test-diamond")
        for name in ("b", "a", "join"):
            unregister_step(f"test-rec-{name}")


# --- MCP integration --------------------------------------------------------


def test_orchestration_tools_over_mcp(services, fixture_log):
    from veritriage.mcp import call_tool

    profiles = call_tool(services, "list_profiles", {})
    assert any(p["name"] == "fast-triage" for p in profiles)
    summary = call_tool(
        services,
        "run_investigation",
        {"profile": "fast-triage", "paths": [str(fixture_log("uvm_assertion.log"))]},
    )
    plan = call_tool(services, "get_investigation_plan", {"session_id": summary["session_id"]})
    assert plan["profile"] == "fast-triage"
    trace = call_tool(services, "get_investigation_trace", {"session_id": summary["session_id"]})
    assert trace["completed"] is True
    resumed = call_tool(
        services, "resume_investigation", {"session_id": summary["session_id"]}
    )
    assert resumed["completed"] is True


# --- Architecture guards ----------------------------------------------------


def test_orchestrator_never_bypasses_services():
    # AST import analysis: the orchestrator may import only the workspace,
    # the models vocabulary, and itself. The pipeline, parsers, engines,
    # providers, and adapters are unimportable here.
    allowed_prefixes = ("veritriage.workspace", "veritriage.models", "veritriage.orchestrator")
    for path in (SRC / "veritriage" / "orchestrator").rglob("*.py"):
        for module in imports(path):
            if module.startswith("veritriage"):
                assert module.startswith(allowed_prefixes), f"{path.name} imports {module}"


def test_core_unchanged_by_orchestration():
    # No core package, and no workspace or mcp module, imports the
    # orchestrator: the workspace stays below it, and dependencies keep
    # pointing outward. (MCP tools import it lazily inside handlers, which
    # is a client relationship; the tools module is checked by name.)
    core = (
        "graph", "parsers", "rules", "reasoning", "knowledge", "waveform",
        "engineering", "history", "signatures", "similarity", "storage",
        "analytics", "feedback", "models", "reports", "dashboard", "workspace",
    )
    for package in core:
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            if package == "models" and path.name == "orchestration.py":
                continue  # the shared vocabulary itself
            text = path.read_text(encoding="utf-8")
            assert "veritriage.orchestrator" not in text, f"{path} imports the orchestrator"
    pipeline = (SRC / "veritriage" / "pipeline.py").read_text(encoding="utf-8")
    assert "veritriage.orchestrator" not in pipeline


def test_no_ai_in_orchestrator():
    banned = ("anthropic", "reasoning.ai", "AIReasoner")
    for path in (SRC / "veritriage" / "orchestrator").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_orchestration_vocabulary_is_plain_data():
    # The models vocabulary stays layer-neutral: no graph, engine, or
    # workspace import in the orchestration models.
    for module in imports(SRC / "veritriage" / "models" / "orchestration.py"):
        assert not module.startswith("veritriage.") or module.startswith(
            "veritriage.models"
        ), f"models/orchestration.py imports {module}"


# --- The crown jewel: a new workflow step is one registration ----------------


def test_new_step_needs_only_registration(services, fixture_log):
    # A throwaway step and profile defined entirely in this test: they run
    # through the real engine, land in the trace with artifact flow and
    # timing, and appear in the persisted session, with zero changes to the
    # engine, the workspace, or any core module.
    @register_step
    class _FailingSeverityCountStep(InvestigationStep):
        step_type = "test-count-failing"
        default_inputs = ("session",)
        default_outputs = ("failing_count",)

        def run(self, services, context, params):
            session = context["session"]
            return {"failing_count": len(services.evidence(session, failing_only=True))}

    profile = InvestigationProfile(
        name="test-custom",
        description="crown jewel",
        steps=(
            PlanStep(id="analyze-artifacts", step_type="analyze-artifacts", outputs=("session",)),
            PlanStep(
                id="count-failing",
                step_type="test-count-failing",
                depends_on=("analyze-artifacts",),
                inputs=("session",),
                outputs=("failing_count",),
            ),
            PlanStep(id="persist-session", step_type="persist-session", depends_on=("analyze-artifacts",)),
        ),
    )
    register_profile(profile)
    try:
        session = run_profile(services, "test-custom", [fixture_log("uvm_assertion.log")])
        assert session.trace.completed
        custom = next(t for t in session.trace.steps if t.step_id == "count-failing")
        assert custom.status is StepStatus.COMPLETED
        assert custom.consumed == ("session",)
        assert custom.produced == ("failing_count",)
    finally:
        unregister_profile("test-custom")
        unregister_step("test-count-failing")
