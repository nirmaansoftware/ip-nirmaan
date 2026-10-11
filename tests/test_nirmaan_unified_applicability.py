"""M48: one condition type, bounds as a structured field, and one limits model.

docs/UNIFIED_APPLICABILITY.md. Five ways to say "this applies only when"
became one predicate (``Condition``, over a registered condition kind with a
declared phase) and one evaluator; metric bounds left the tool-parameter
namespace for ``EvidenceRequirement.bounds``; retries, attempts and review
rounds are one ``Limits`` object with one resolver. Old-form data and old
projects still load. The characterization is
tests/test_nirmaan_applicability_golden.py.
"""

from __future__ import annotations

import json
import shutil
import types
from pathlib import Path

import pytest

from laws import imports
from nirmaan.models import (
    Bound,
    Capability,
    CapabilityKind,
    Condition,
    ConditionPhase,
    Criticality,
    Evidence,
    EvidenceKind,
    EvidenceRequirement,
    FileInput,
    Limits,
    OnFailure,
    ProjectState,
    StageTemplate,
    ToolRun,
)
from nirmaan_helpers import agent, human, tid

SRC = Path(__file__).resolve().parent.parent / "src" / "nirmaan"
FIXTURES = Path(__file__).parent / "fixtures"
OLD_PROJECT = FIXTURES / "projects" / "m28-tool-runs.json"
REGRESSION = "Investigate a regression failure introduced by a recent RTL commit."


# --- 1. Old-form data builds the new form ----------------------------------------------------


def test_an_old_form_requirement_builds_the_new_form():
    req = EvidenceRequirement(
        description="old", accepts=(EvidenceKind.TOOL_RUN,), tools=("synth.run",),
        when=Condition(any_of=("at_speed",)), when_produced=("formal_spec",), when_upstream=("rtl_source", "layout"),
        params=(("max_latches", "0"), ("stop_after", "route"), ("min_fill_shapes", "1")))
    assert req.when == (Condition(any_of=("at_speed",)), Condition(on="produced", any_of=("formal_spec",)),
                        Condition(on="upstream", any_of=("rtl_source", "layout")))
    assert req.params == (("stop_after", "route"),)
    assert req.bounds == (Bound(metric="latches", op="max", value=0), Bound(metric="fill_shapes", op="min", value=1))
    dumped = req.model_dump(mode="json")
    assert not {"when_produced", "when_upstream"} & set(dumped)
    assert EvidenceRequirement.model_validate(dumped) == req


def test_an_unconditional_old_when_is_no_clause():
    saved = {"description": "x", "accepts": ["review_record"], "when": {"all_of": [], "any_of": [], "none_of": []},
             "when_produced": []}
    assert EvidenceRequirement.model_validate(saved).when == ()


def test_old_form_limits_build_the_new_form():
    stage = StageTemplate(id="s", title="S", phase="P", capability="c", max_retries=2, on_failure=OnFailure.FAIL,
                          max_attempts=3, max_review_rounds=2)
    assert stage.limits == Limits(retries=2, on_failure=OnFailure.FAIL, attempts=3, review_rounds=2)
    cap = Capability(id="c", name="C", kind=CapabilityKind.EXECUTION, description="", max_attempts=2,
                     max_review_rounds=3)
    assert cap.limits == Limits(attempts=2, review_rounds=3)
    assert StageTemplate(id="s", title="S", phase="P", capability="c").limits == Limits()


def _old_store(tmp_path):
    from nirmaan.work import ProjectStore

    project = json.loads(OLD_PROJECT.read_text())["project"]["id"]
    (tmp_path / "projects").mkdir()
    shutil.copy(OLD_PROJECT, tmp_path / "projects" / f"{project}.json")
    return ProjectStore(tmp_path), project


def test_an_old_project_loads_verifies_and_resaves_stably(tmp_path, nirmaan_org):
    from nirmaan.work.audit import verify_chain

    store, project = _old_store(tmp_path)
    state = store.load(project)
    assert verify_chain(state.audit) == []
    reqs = [r for t in state.tasks.values() for r in t.evidence_requirements]
    assert reqs and all(isinstance(r.when, tuple) for r in reqs)
    path = store.save(state)
    text = path.read_text()
    assert "when_produced" not in text and "max_retries" not in text
    saved, old = json.loads(text), json.loads(OLD_PROJECT.read_text())
    assert saved["tool_runs"] == old["tool_runs"] and saved["audit"] == old["audit"]
    assert store.save(store.load(project)).read_text() == text


# --- 2. One evaluator ------------------------------------------------------------------------


def test_the_evaluator_decides_each_clause_in_its_phase():
    from nirmaan.applicability import Facts, applies

    when = (Condition(any_of=("dft",)), Condition(on="produced", any_of=("formal_spec",)))
    assert applies(when, Facts(ConditionPhase.PLAN, features={"dft"}))  # the run clause waits for the run
    assert not applies(when, Facts(ConditionPhase.PLAN, features=set()))
    assert applies(when, Facts(ConditionPhase.RUN, produced={"formal_spec"}))  # the plan clause was decided
    assert not applies(when, Facts(ConditionPhase.RUN, produced={"rtl_source"}))
    assert applies(when, Facts(ConditionPhase.RUN, upstream={"x"}))  # produced not known yet: not excluded
    assert applies((), Facts(ConditionPhase.RUN))
    with pytest.raises(ValueError, match="no-such-kind"):
        applies((Condition(on="no-such-kind", any_of=("a",)),), Facts(ConditionPhase.RUN))


def test_facts_are_computed_only_when_a_clause_asks():
    from nirmaan.applicability import Facts, applies

    asked = []
    facts = Facts(ConditionPhase.RUN, produced={"rtl_source"}, upstream=lambda: asked.append(1) or {"layout"})
    assert applies((Condition(on="produced", any_of=("rtl_source",)),), facts) and not asked
    assert applies((Condition(on="upstream", any_of=("layout",)),), facts) and asked == [1]


def test_an_optional_binding_is_decided_by_the_evaluator_over_the_available_inputs():
    from nirmaan.applicability import Facts, binding_wanted

    optional = FileInput(param="map", kinds=("register_map",), upstream=True, optional=True)
    required = FileInput(param="rtl", kinds=("rtl_source",), upstream=True)
    assert binding_wanted(optional, Facts(ConditionPhase.RUN, inputs={"register_map"}))
    assert not binding_wanted(optional, Facts(ConditionPhase.RUN, inputs=set()))
    assert binding_wanted(required, Facts(ConditionPhase.RUN, inputs=set()))


def test_the_workflows_carry_no_old_form_and_validate_their_conditions(nirmaan_org):
    from nirmaan.org.validate import validate_organization

    for wf in nirmaan_org.workflows.values():
        for stage in wf.stages:
            for req in stage.evidence:
                assert not any(k[:4] in ("max_", "min_") for k, _ in req.params), (wf.id, stage.id, req.params)
    bad = nirmaan_org.workflows["rtl-change"]
    stage = bad.stages[0].model_copy(update={"when": Condition(on="produced", any_of=("rtl_source",))})
    req = EvidenceRequirement(description="x", accepts=(EvidenceKind.REVIEW_RECORD,),
                              when=(Condition(on="nope", any_of=("a",)),))
    stage = stage.model_copy(update={"evidence": (*stage.evidence, req)})
    org = types.SimpleNamespace(**{k: getattr(nirmaan_org, k) for k in dir(nirmaan_org) if not k.startswith("__")})
    org.workflows = {**nirmaan_org.workflows, bad.id: bad.model_copy(update={"stages": (stage, *bad.stages[1:])})}
    issues = validate_organization(org)
    assert any("run-phase" in i and "produced" in i for i in issues), issues
    assert any("unknown condition kind nope" in i for i in issues), issues


# --- 3. Bounds ---------------------------------------------------------------------------------


def _ev(run_id: str) -> Evidence:
    return Evidence(id="ev", kind=EvidenceKind.TOOL_RUN, description="", task=None, recorded_by="x",
                    tool_run=run_id, substantiated=True)


def test_a_requirement_counts_only_runs_checked_against_its_bounds():
    from nirmaan.work.policy import satisfies

    req = EvidenceRequirement(description="synth", accepts=(EvidenceKind.TOOL_RUN,), tools=("synth.run",),
                              bounds=(Bound(metric="latches", op="max", value=0),))

    def run(**kw):
        return ToolRun(id="run-1", tool="synth.run", actor="x", task=None, succeeded=True, summary="", **kw)

    def ok(r):
        return satisfies(ProjectState.model_construct(tool_runs={"run-1": r}), _ev("run-1"), req)

    assert ok(run(bounds=(Bound(metric="latches", op="max", value=0),)))
    assert ok(run(bounds=(Bound(metric="latches", op="max", value=0), Bound(metric="cells", op="max", value=9))))
    assert not ok(run(bounds=()))
    assert not ok(run(bounds=(Bound(metric="latches", op="max", value=1),)))
    # A run saved before M48 was checked against every max_/min_ parameter it carried.
    legacy = run(params={"max_latches": "0"})
    assert legacy.bounds is None and ok(legacy)
    assert not ok(run(params={"max_latches": "1"}))
    # After M48 a parameter is only a parameter, whatever its name.
    assert not ok(run(params={"max_latches": "0"}, bounds=()))


def test_a_saved_run_round_trips_with_or_without_bounds():
    legacy = ToolRun(id="r", tool="t", actor="a", task=None, succeeded=True, summary="")
    assert "bounds" not in legacy.model_dump(mode="json")
    new = legacy.model_copy(update={"bounds": (Bound(metric="m", op="min", value=1.5),)})
    assert ToolRun.model_validate(new.model_dump(mode="json")) == new


def test_bounds_have_one_text_form():
    for text, bound in (("latches<=0", Bound(metric="latches", op="max", value=0)),
                        ("test_coverage>=90.5", Bound(metric="test_coverage", op="min", value=90.5))):
        assert Bound.parse(text) == bound and Bound.parse(str(bound)) == bound
    with pytest.raises(ValueError):
        Bound.parse("latches=0")


@pytest.fixture()
def gauge(fixed_clock):
    """An organization with an EDA tool whose backend reports a metric, and a real input named ``max_depth``."""
    from nirmaan.company import builder
    from nirmaan.integrations.eda import Backend, EdaResult, register_backend
    from nirmaan.models import (
        Function,
        OrgUnit,
        ParamKind,
        ParamSpec,
        Skill,
        ToolRisk,
        ToolSpec,
        ToolStatus,
        UnitKind,
    )
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.org import register_extension
    from nirmaan.registry import Registries

    with Registries.scoped():
        @register_extension("test-gauge")
        def extension(b):
            b.add(ToolSpec(id="gauge.run", name="Gauge", category="eda", risk=ToolRisk.EXECUTE,
                           status=ToolStatus.AVAILABLE,
                           params=(ParamSpec(name="max_depth", kind=ParamKind.INTEGER, description="A real input."),
                                   ParamSpec(name="workdir", kind=ParamKind.PATH))),
                  Skill(id="gauging", name="Gauging", domain="architecture", tools=("gauge.run",),
                        validation_criteria=("Gauged.",)),
                  OrgUnit(id="architecture.gauges", name="Gauges", kind=UnitKind.TEAM,
                          function=Function.ENGINEERING, parent="architecture", noun="Gauge Architect",
                          skills=("gauging",)))

        register_backend(Backend("gauge", "gauge.run", ("true",), lambda job: [["true"]],
                                 lambda run: EdaResult(True, "gauged", (), {"widgets": 3}), required=()))
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
        role = next(r for r in org.roles.values() if r.unit == "architecture.gauges")
        yield engine, human(role.id)


@pytest.mark.skipif(shutil.which("true") is None, reason="needs true(1)")
def test_bounds_are_enforced_from_the_field(gauge, tmp_path):
    from nirmaan.runtime import ToolBroker

    engine, actor = gauge
    broker = ToolBroker(engine)
    over = (Bound(metric="widgets", op="max", value=2),)
    run, _ = broker.invoke(actor, "gauge.run", {"workdir": str(tmp_path / "a")}, bounds=over)
    assert not run.succeeded and "widgets 3 exceeds max_widgets 2" in run.summary and run.bounds == over
    within = (Bound(metric="widgets", op="max", value=3), Bound(metric="widgets", op="min", value=3))
    run, _ = broker.invoke(actor, "gauge.run", {"workdir": str(tmp_path / "b")}, bounds=within)
    assert run.succeeded and run.bounds == within
    unknown = (Bound(metric="gadgets", op="min", value=1),)
    run, _ = broker.invoke(actor, "gauge.run", {"workdir": str(tmp_path / "c")}, bounds=unknown)
    assert not run.succeeded and "gadgets was not reported" in run.summary


@pytest.mark.skipif(shutil.which("true") is None, reason="needs true(1)")
def test_a_max_input_is_not_read_as_a_bound(gauge, tmp_path):
    from nirmaan.runtime import ToolBroker

    engine, actor = gauge
    run, _ = ToolBroker(engine).invoke(actor, "gauge.run", {"max_depth": 2, "workdir": str(tmp_path)})
    assert run.succeeded, run.summary  # no `depth` metric, and none is asked for
    assert run.params["max_depth"] == 2 and run.bounds == ()


def test_a_bound_passed_as_a_parameter_is_refused(nirmaan_org, fixed_clock):
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.runtime import ToolBroker, ToolContractError

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter.")
    rtl = tid(engine, "rtl-implementation")
    with pytest.raises(ToolContractError, match="max_latches"):
        ToolBroker(engine).invoke(human(engine.task(rtl).owner), "synth.run",
                                  {"sources": "counter.v", "top": "counter", "max_latches": "0"}, rtl)
    for spec in nirmaan_org.tools.values():
        assert not any(p.prefix and p.name in ("max_", "min_") for p in spec.params or ()), spec.id


# --- 4. Limits ---------------------------------------------------------------------------------


def test_one_resolver_takes_each_limit_from_the_first_layer_that_sets_it():
    from nirmaan.models import resolve_limits

    assert resolve_limits() == Limits(attempts=1, review_rounds=1, retries=1,
                                      on_failure=OnFailure.RETRY_THEN_ESCALATE)
    cli, stage, cap = Limits(attempts=4), Limits(attempts=2, retries=3), Limits(review_rounds=5, retries=9,
                                                                                on_failure=OnFailure.FAIL)
    assert resolve_limits(cli, stage, cap) == Limits(attempts=4, review_rounds=5, retries=3,
                                                     on_failure=OnFailure.FAIL)


def test_the_engine_and_the_runner_resolve_limits_alike(nirmaan_org, fixed_clock):
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.runtime import limits
    from nirmaan.work.limits import limits_for

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    verify = tid(engine, "verify-fix")
    assert limits(engine, verify).retries == 2 and limits_for(nirmaan_org, engine.task(verify)).retries == 2
    assert limits(engine, tid(engine, "triage")).retries == 1
    assert limits(engine, verify, attempts=3).attempts == 3


@pytest.fixture()
def probe_org(fixed_clock):
    """A capability that allows two retries, and a stage whose requirement applies only on sky130 (M48)."""
    import re

    from nirmaan.applicability import ConditionKind, register_condition_kind
    from nirmaan.company import builder
    from nirmaan.models import Function, IntentRule, OrgUnit, Skill, UnitKind, WorkflowTemplate
    from nirmaan.org import register_extension
    from nirmaan.registry import Registries

    with Registries.scoped():  # registered for this test only
        register_condition_kind(ConditionKind(
            name="pdk", phase=ConditionPhase.PLAN,
            facts=lambda f: re.findall(r"\b(sky130|gf180)", f.source("requirement").text.lower()),
            describe=lambda c: f"applies only on {' or '.join(c.any_of)}"))
        sky130 = Condition(on="pdk", any_of=("sky130",))

        @register_extension("test-pdk-probe")
        def extension(b):
            b.add(Capability(id="pdk.probe", name="PDK probe", kind=CapabilityKind.EXECUTION,
                             description="Probe a process kit.", limits=Limits(retries=2)),
                  Skill(id="pdk_probing", name="PDK probing", domain="architecture", provides=("pdk.probe",),
                        validation_criteria=("The kit is probed.",)),
                  OrgUnit(id="architecture.probes", name="Probes", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                          parent="architecture", noun="Probe Architect", skills=("pdk_probing",)),
                  IntentRule(intent="pdk_probe", patterns=(r"\bprobe the pdk\b",), priority=1),
                  WorkflowTemplate(
                      id="pdk-probe", name="PDK probe", description="Probe a process kit.", intents=("pdk_probe",),
                      stages=(
                          StageTemplate(
                              id="probe", title="Probe", phase="PD", capability="pdk.probe",
                              criticality=Criticality.MEDIUM,
                              evidence=(EvidenceRequirement(description="Probed on sky130",
                                                            accepts=(EvidenceKind.REVIEW_RECORD,), when=(sky130,)),
                                        EvidenceRequirement(description="Run on the kit",
                                                            accepts=(EvidenceKind.TOOL_RUN,), tools=("pnr.run",),
                                                            when=(Condition(on="pdk", any_of=("gf180",)),)))),
                          StageTemplate(id="sky130-only", title="sky130 only", phase="PD", capability="pdk.probe",
                                        depends_on=("probe",), when=sky130),
                      )))

        yield builder().build()


def test_a_new_condition_kind_needs_no_core_changes(probe_org, fixed_clock):
    from nirmaan.orchestrator import Orchestrator

    sky = Orchestrator(probe_org, clock=fixed_clock).plan("Probe the PDK for the sky130 flow.")
    probe = sky.task(tid(sky, "probe"))
    assert [r.description for r in probe.evidence_requirements] == ["Probed on sky130"]
    assert any(t.stage == "sky130-only" for t in sky.state.tasks.values())
    gf = Orchestrator(probe_org, clock=fixed_clock).plan("Probe the PDK for the gf180 flow.")
    assert [r.description for r in gf.task(tid(gf, "probe")).evidence_requirements] == ["Run on the kit"]
    assert not any(t.stage == "sky130-only" for t in gf.state.tasks.values())


def test_a_capability_sets_the_retries_the_engine_allows(probe_org, fixed_clock):
    from nirmaan.models import TaskStatus
    from nirmaan.orchestrator import Orchestrator

    engine = Orchestrator(probe_org, clock=fixed_clock).plan("Probe the PDK for the gf180 flow.")
    probe = tid(engine, "probe")
    owner = agent(engine.task(probe).owner)
    for attempt in (1, 2):
        engine.start(probe, owner)
        engine.fail(probe, owner, f"attempt {attempt}")
        assert engine.task(probe).status is TaskStatus.READY
    engine.start(probe, owner)
    engine.fail(probe, owner, "attempt 3")
    assert engine.task(probe).status is TaskStatus.ESCALATED


# --- 5. Laws -----------------------------------------------------------------------------------


def test_one_evaluator_reads_applicability():
    """No reader tests a requirement's clauses itself: every one goes through ``applicability.applies``."""
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "when_produced" not in text or path.name == "workflow.py", path
        assert "when_upstream" not in text or path.name == "workflow.py", path
    for path in (SRC / "work" / "policy.py", SRC / "runtime" / "model.py", SRC / "orchestrator" / "planner.py"):
        assert "nirmaan.applicability" in imports(path), path
    assert "_within_limits" not in (SRC / "integrations" / "eda.py").read_text()


def test_the_import_laws_hold():
    found = imports(SRC / "applicability.py")
    assert not any(m == "veritriage" or m.startswith("veritriage.") for m in found)
    assert not any(m.startswith(("nirmaan.work", "nirmaan.runtime", "nirmaan.orchestrator", "nirmaan.company"))
                   for m in found), found
    names = ("sky130", "rtl_source", "formal_spec", "register_map")
    assert not any(n in (SRC / "applicability.py").read_text() for n in names)
