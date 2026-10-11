"""Milestone 39: typed values end to end, and the typed work packet.

A tool's parameters are parsed once, by the contract, at the broker: an
integer is an ``int``, a number a ``float``, a list of paths a tuple. The
binding receives them typed, the ``ToolRun`` stores them typed, and a project
saved before M39 (text values) still loads, verifies, and reads typed. The work
packet a model runtime renders is a typed model, and the prompts it renders are
byte-identical to the dict packet's (golden files rendered before the change).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import drive, human, tid
from laws import needs

from nirmaan.models import (
    Actor,
    ActorKind,
    MemoryScope,
    ParamKind,
    ParamSpec,
    ToolRun,
    list_values,
    param_matches,
    text_value,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    MockLLM,
    ModelRuntime,
    ToolBroker,
    ToolContractError,
    assemble,
    render_work_prompt,
    review_task,
    run_task,
)
from nirmaan.work import ProjectStore
from nirmaan.work.audit import verify_chain

FIXTURES = Path(__file__).parent / "fixtures"
OLD_PROJECT = FIXTURES / "projects" / "m28-tool-runs.json"
GOLDEN = FIXTURES / "prompts"
REGRESSION = "Investigate a regression failure introduced by a recent RTL commit."
COUNTER_BLOCK = "Create a 4-bit wrapping counter."
RTL = FIXTURES / "rtl"

#: What the extension tool's binding received, call by call.
RECEIVED: list[dict] = []


# --- An extension tool with every kind of value ----------------------------------------------


@pytest.fixture()
def gauge(fixed_clock):
    """An extension declares ``gauge.read`` (text, path, paths, integer, number); no core change."""
    from nirmaan.company import builder
    from nirmaan.models import Function, OrgUnit, Skill, ToolRisk, ToolSpec, ToolStatus, UnitKind
    from nirmaan.org import register_extension, unregister_extension
    from nirmaan.runtime import ToolOutcome, register_binding, unregister_binding

    @register_binding("gauge.read")
    def read(params, engine):
        RECEIVED.append(dict(params))
        # Arithmetic on the values: text would concatenate or raise, typed values compute.
        total = params.get("count", 0) * 2 + params.get("scale", 0.0)
        return ToolOutcome(True, f"{len(params.get('files', ()))} files, total {total}")

    @register_extension("test-gauge")
    def extension(b):
        b.add(
            ToolSpec(id="gauge.read", name="Gauge", category="platform", risk=ToolRisk.READ,
                     status=ToolStatus.AVAILABLE,
                     params=(ParamSpec(name="label"), ParamSpec(name="file", kind=ParamKind.PATH),
                             ParamSpec(name="files", kind=ParamKind.PATHS),
                             ParamSpec(name="count", kind=ParamKind.INTEGER),
                             ParamSpec(name="scale", kind=ParamKind.NUMBER))),
            Skill(id="gauges", name="Gauges", domain="architecture", tools=("gauge.read",),
                  validation_criteria=("Every reading names its scale.",)),
            OrgUnit(id="architecture.gauges", name="Gauges", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                    parent="architecture", noun="Gauge Architect", skills=("gauges",)),
        )

    RECEIVED.clear()
    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
        role = next(r for r in org.roles.values() if r.unit == "architecture.gauges" and r.level.rank <= 40)
        yield engine, Actor(role=role.id, kind=ActorKind.HUMAN, name="test")
    finally:
        unregister_extension("test-gauge")
        unregister_binding("gauge.read")


TYPED = {"label": "x", "file": "a.v", "files": ("a.v", "b.v"), "count": 3, "scale": 0.5}


def test_the_cli_text_reaches_the_binding_typed(gauge):
    engine, actor = gauge
    run, outcome = ToolBroker(engine).invoke(actor, "gauge.read", {
        "label": "x", "file": "a.v", "files": "a.v,b.v", "count": "3", "scale": "0.5"})
    assert RECEIVED == [TYPED]
    assert outcome.summary == "2 files, total 6.5"
    assert dict(run.params) == TYPED
    assert type(run.params["count"]) is int and type(run.params["scale"]) is float


def test_a_callers_values_reach_the_binding_typed(gauge):
    engine, actor = gauge
    run, _ = ToolBroker(engine).invoke(actor, "gauge.read", {
        "label": ["x"], "file": ["a.v"], "files": ["a.v", "b.v"], "count": 3, "scale": 0.5})
    assert RECEIVED == [TYPED] and dict(run.params) == TYPED
    run, _ = ToolBroker(engine).invoke(actor, "gauge.read", {"scale": 2})  # an int is a number
    assert run.params["scale"] == 2.0 and type(run.params["scale"]) is float


def test_typed_values_survive_a_save_and_a_reload(gauge, tmp_path):
    engine, actor = gauge
    run, _ = ToolBroker(engine).invoke(actor, "gauge.read", {"files": "a.v,b.v", "count": "3", "scale": "0.5"})
    store = ProjectStore(tmp_path)
    path = store.save(engine.state)
    saved = json.loads(path.read_text())["tool_runs"][run.id]["params"]
    assert saved == {"files": ["a.v", "b.v"], "count": 3, "scale": 0.5}
    loaded = store.load(engine.state.project.id).tool_runs[run.id]
    assert dict(loaded.params) == {"files": ("a.v", "b.v"), "count": 3, "scale": 0.5}
    assert type(loaded.params["scale"]) is float and loaded.values("files") == ["a.v", "b.v"]
    assert store.save(store.load(engine.state.project.id)).read_text() == path.read_text()


def test_the_cli_takes_a_repeated_param_as_a_list(gauge, tmp_path, monkeypatch):
    import nirmaan.cli as cli

    engine, actor = gauge
    monkeypatch.setattr(cli, "_ORG", None)  # the CLI builds the organization with the extension
    ProjectStore(tmp_path).save(engine.state)
    task = next(iter(engine.state.tasks))
    result = CliRunner().invoke(cli.app, [
        "task", "tool", engine.state.project.id, task, "gauge.read", "--as", actor.role,
        "--param", "files=a.v", "--param", "files=b.v", "--param", "count=3", "--param", "scale=0.5",
        "--param", "label=x", "--param", "file=a.v", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert RECEIVED == [TYPED]
    run = next(iter(ProjectStore(tmp_path).load(engine.state.project.id).tool_runs.values()))
    assert dict(run.params) == TYPED


@pytest.mark.parametrize("params,why", [
    ({"count": "soon"}, "count must be a whole number"),
    ({"count": "1.5"}, "count must be a whole number"),
    ({"count": 1.5}, "count must be a whole number"),
    ({"count": True}, "count must be a whole number"),
    ({"scale": "wide"}, "scale must be a number"),
    ({"scale": False}, "scale must be a number"),
    ({"count": ["1", "2"]}, "count takes one value"),
    ({"files": ["ok.v", "odd,name.v"]}, "comma"),
    ({"file": ["a.v", "b.v"]}, "file takes one path"),
])
def test_bad_types_are_refused_before_any_run(gauge, params, why):
    engine, actor = gauge
    with pytest.raises(ToolContractError, match=why):
        ToolBroker(engine).invoke(actor, "gauge.read", params)
    assert RECEIVED == [] and engine.state.tool_runs == {}


def test_a_new_typed_tool_needs_no_core_changes(gauge):
    """Crown jewel: the extension above declared a typed contract and a binding, and nothing else.

    The broker parses by its contract, the binding computes on the typed values, the run stores them,
    and a requirement's fixed text parameters match them by value.
    """
    engine, actor = gauge
    run, outcome = ToolBroker(engine).invoke(actor, "gauge.read", {"count": "4", "scale": "1e-1"})
    assert outcome.succeeded and outcome.summary == "0 files, total 8.1"
    assert dict(run.params) == {"count": 4, "scale": 0.1}
    assert param_matches(run.params["count"], "4") and param_matches(run.params["scale"], "0.1")
    assert not param_matches(run.params["count"], "5")


# --- The one parser, and its readers ---------------------------------------------------------


def test_every_typed_value_has_one_text_form_that_parses_back():
    cases = [(ParamKind.TEXT, "a b"), (ParamKind.PATH, "/x/a.v"), (ParamKind.PATHS, ("a.v", "b.v")),
             (ParamKind.PATHS, ()), (ParamKind.INTEGER, -3), (ParamKind.NUMBER, 40.0), (ParamKind.NUMBER, 0.1)]
    for kind, value in cases:
        spec = ParamSpec(name="p", kind=kind)
        assert spec.parse(value) == value
        assert spec.parse(text_value(value)) == value, (kind, value)
    assert text_value(40.0) == "40" and text_value(2.5) == "2.5" and text_value(("a", "b")) == "a,b"


def test_the_readers_take_typed_values_and_saved_text():
    assert list_values(("a.v", "b.v")) == list_values("a.v, b.v,,") == ["a.v", "b.v"]
    assert list_values(3) == ["3"] and list_values("") == [] and list_values(()) == []
    assert param_matches("60", "60") and param_matches(60, "60") and param_matches(60.0, "60")
    assert param_matches(("a.v", "b.v"), "a.v,b.v") and not param_matches(("a.v",), "a.v,b.v")
    assert not param_matches(60, "sixty") and not param_matches(None, "60")


# --- Projects saved before M39 ---------------------------------------------------------------


def _old_store(tmp_path) -> tuple[ProjectStore, str]:
    project = json.loads(OLD_PROJECT.read_text())["project"]["id"]
    (tmp_path / "projects").mkdir()
    shutil.copy(OLD_PROJECT, tmp_path / "projects" / f"{project}.json")
    return ProjectStore(tmp_path), project


def test_a_project_saved_before_typed_values_loads_and_verifies(tmp_path, nirmaan_org):
    store, project = _old_store(tmp_path)
    state = store.load(project)  # verifies the audit chain
    assert verify_chain(state.audit) == []
    runs = {r.tool: r for r in state.tool_runs.values()}
    assert runs["lint.run"].params["timeout"] == "30"  # stored text is read as stored
    assert runs["lint.run"].values("sources") == ["/nonexistent/m39/a.v", "/nonexistent/m39/b.v"]
    assert len(runs["veritriage.investigate"].values("paths")) == 2
    # Saving it again migrates nothing in place: the runs' stored values and the audit chain are written back
    # exactly as they were. Fields added to other records since the fixture was saved (M37's `when_upstream`
    # on a requirement, say) appear at their defaults, and a second round trip writes the same bytes.
    path = store.save(state)
    saved, old = json.loads(path.read_text()), json.loads(OLD_PROJECT.read_text())
    assert saved["tool_runs"] == old["tool_runs"]
    assert saved["audit"] == old["audit"]
    assert store.save(store.load(project)).read_text() == path.read_text()


def test_a_saved_run_reads_typed_by_its_contract(tmp_path, nirmaan_org):
    store, project = _old_store(tmp_path)
    runs = {r.tool: r for r in store.load(project).tool_runs.values()}
    lint = runs["lint.run"].typed(nirmaan_org.tools["lint.run"])
    assert lint == {"sources": ("/nonexistent/m39/a.v", "/nonexistent/m39/b.v"), "top": "a", "timeout": 30,
                    "max_warnings": 0.0}
    atpg = runs["dft.atpg"].typed(nirmaan_org.tools["dft.atpg"])
    assert atpg["seed"] == 7 and atpg["min_test_coverage"] == 90.5 and len(atpg["sources"]) == 2
    # A value that no longer parses stays as it was stored, rather than vanishing.
    odd = ToolRun(id="run-9", tool="lint.run", actor="x", task=None, params={"timeout": "soon"},
                  succeeded=False, summary="saved long ago")
    assert odd.typed(nirmaan_org.tools["lint.run"]) == {"timeout": "soon"}


def test_a_requirement_matches_saved_and_typed_runs_alike():
    from nirmaan.models import Evidence, EvidenceKind, EvidenceRequirement, ProjectState
    from nirmaan.work.policy import satisfies

    req = EvidenceRequirement(description="lint", accepts=(EvidenceKind.TOOL_RUN,), tools=("lint.run",),
                              params=(("timeout", "30"),))
    ev = Evidence(id="ev", kind=EvidenceKind.TOOL_RUN, description="", task=None, recorded_by="x",
                  tool_run="run-1", substantiated=True)
    for stored in ("30", 30):
        run = ToolRun(id="run-1", tool="lint.run", actor="x", task=None, params={"timeout": stored},
                      succeeded=True, summary="")
        state = ProjectState.model_construct(tool_runs={"run-1": run})
        assert satisfies(state, ev, req), stored
    run = ToolRun(id="run-1", tool="lint.run", actor="x", task=None, params={"timeout": 31}, succeeded=True,
                  summary="")
    assert not satisfies(ProjectState.model_construct(tool_runs={"run-1": run}), ev, req)


# --- The typed work packet -------------------------------------------------------------------


@pytest.fixture()
def regression(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)


def test_the_packet_is_typed_all_the_way_down(regression, fixture_log, tmp_path):
    from pydantic import BaseModel

    from nirmaan.runtime.context import TaskScope, WorkPacket

    triage = tid(regression, "triage")
    owner = human(regression.task(triage).owner)
    regression.remember(MemoryScope.TASK, triage, "input.paths", str(fixture_log("axi_timeout.log")), owner)
    run_task(regression, triage, ModelRuntime(MockLLM()))
    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    packet = assemble(regression, root)
    assert isinstance(packet, WorkPacket) and isinstance(packet.task, TaskScope)

    def no_untyped(value, where):
        if isinstance(value, BaseModel):
            assert value.model_config.get("frozen"), where
            for name in type(value).model_fields:
                no_untyped(getattr(value, name), f"{where}.{name}")
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                no_untyped(item, f"{where}[{i}]")
        elif isinstance(value, dict):  # only maps whose keys are data: parameters, proficiencies
            assert where in ("packet.project.parameters", "packet.role.skills", "packet.role.capabilities"), where
            assert all(isinstance(v, (str, int)) for v in value.values()), where

    no_untyped(packet, "packet")
    with pytest.raises(Exception):
        packet.task.title = "changed"  # frozen
    assert packet.task.evidence and all(e.task for e in packet.task.evidence)
    assert packet.role.role == regression.task(root).owner


# --- Golden prompts: rendered by the dict packet before M39 ----------------------------------


def _normalize(text: str, *roots: Path, mask_logs: bool = False) -> str:
    for root in roots:
        text = text.replace(str(root), "<" + ("fixtures" if root == FIXTURES else "tmp") + ">")
    text = re.sub(r"prj-[0-9a-f]{10}", "prj-<id>", text)  # the ID follows the organization's fingerprint
    if mask_logs:
        text = re.sub(r"(?m)^\| .*$", "| <log>", text)  # the installed Verilator's own words
        text = re.sub(r"(?m)first: .*$", "first: <diagnostic>", text)
    return text


def _golden(name: str, text: str) -> None:
    path = GOLDEN / f"{name}.txt"
    if os.environ.get("NIRMAAN_WRITE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert text == path.read_text(encoding="utf-8"), f"{name} changed; see {path}"


def test_golden_prompts_of_the_regression_seats(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    owner = human(regression.task(triage).owner)
    regression.remember(MemoryScope.TASK, triage, "input.paths", str(fixture_log("axi_timeout.log")), owner)
    regression.remember(MemoryScope.TASK, triage, "input.workspace", str(tmp_path), owner)
    llm = MockLLM()
    run_task(regression, triage, ModelRuntime(llm))
    _golden("triage-work", _normalize(llm.calls[0].render(), tmp_path, FIXTURES))

    root = tid(regression, "root-cause")
    drive(regression, until=root, workspace=tmp_path)
    llm = MockLLM()
    run_task(regression, root, ModelRuntime(llm))
    _golden("root-cause-work", _normalize(llm.calls[0].render(), tmp_path, FIXTURES))
    llm = MockLLM()
    review_task(regression, root, ModelRuntime(llm))
    _golden("root-cause-review", _normalize(llm.calls[0].render(), tmp_path, FIXTURES))


@pytest.fixture()
def counter(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    engine.remember(MemoryScope.TASK, rtl, "input.workspace", str(tmp_path / "work"), human(engine.task(rtl).owner))
    return engine, rtl


def test_golden_prompt_with_approved_upstream_files(counter, tmp_path):
    engine, rtl = counter
    text = render_work_prompt(assemble(engine, rtl)).render()
    _golden("rtl-work", _normalize(text, tmp_path, FIXTURES))


@needs("verilator", "yosys")
def test_golden_prompt_of_a_repair(counter, tmp_path):
    from test_nirmaan_repair import LINT_BROKEN
    from test_nirmaan_repair import counter as answer
    from test_nirmaan_repair import token

    engine, rtl = counter
    cite = token("artifact", engine.task(tid(engine, "microarchitecture")).artifacts[0])
    llm = MockLLM(script=[answer(cite, LINT_BROKEN), answer(cite)])
    run_task(engine, rtl, ModelRuntime(llm), attempts=2)
    assert len(llm.calls) == 2
    _golden("rtl-repair", _normalize(llm.calls[1].render(), tmp_path, FIXTURES, mask_logs=True))
