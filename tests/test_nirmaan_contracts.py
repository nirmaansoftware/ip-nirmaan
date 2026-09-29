"""Milestone 28: tool contracts. A tool says what it takes, and the broker holds callers to it.

Every tool with a binding declares its parameters (name, kind, required).
The broker refuses an undeclared or ill-typed parameter before anything runs,
takes a list of paths and refuses a path it could not tell from two, and the
runtime hands each tool only the task inputs it declares. Missing required
inputs stay recorded failed runs (the M21/M25 rule); that is not changed here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import human
from test_nirmaan_design_agents import (  # noqa: F401  (block and rtl_ready are fixtures)
    RTL,
    answer,
    block,
    counter_files,
    needs,
    rtl_ready,
    token,
    upstream,
)

import nirmaan
from nirmaan.cli import app
from nirmaan.models import MemoryScope, ParamKind, ParamSpec, ToolRun, list_values
from nirmaan.runtime import (
    MockLLM,
    ModelRuntime,
    ResultStatus,
    ToolBroker,
    ToolContractError,
    available_bindings,
    run_task,
)

INTEGRATIONS = Path(nirmaan.__file__).parent / "integrations"
#: A parameter read by name: params.get("x"), params["x"], p.get('x'), _token(p, 'x'), _design(job, 'x'), ...
_READ = re.compile(r"""(?:\b(?:p|params|job\.params)(?:\.get\(|\[|,\s*)|_design\(job,\s*)['"]([a-z_]+)['"]""")


def _owner(engine, task_id):
    return human(engine.task(task_id).owner)


# --- Every executable tool declares what it takes ------------------------------------------


def test_every_bound_tool_declares_a_contract(nirmaan_org):
    for tool_id in available_bindings():
        spec = nirmaan_org.tools[tool_id]
        assert spec.params is not None, f"{tool_id} has a binding but no parameter contract"
        names = [p.name for p in spec.params]
        assert len(names) == len(set(names)), tool_id


def test_every_parameter_an_integration_reads_is_declared(nirmaan_org):
    """A static scan, so settings no machine here can run (OpenROAD's) are still covered."""
    declared = {p.name for t in nirmaan_org.tools.values() for p in (t.params or ())}
    for path in sorted(INTEGRATIONS.glob("*.py")):
        for name in set(_READ.findall(path.read_text(encoding="utf-8"))):
            assert name in declared, f"{path.name} reads {name!r}, which no tool declares"


def test_list_values_is_the_one_reader_of_stored_lists():
    assert list_values("a.v, b.v,,") == ["a.v", "b.v"]
    assert list_values("") == []
    legacy = ToolRun(id="run-0001", tool="lint.run", actor="x", task=None, params={"sources": "a.v,b.v"},
                     succeeded=True, summary="saved before M28")
    assert legacy.values("sources") == ["a.v", "b.v"] and legacy.values("top") == []


# --- The broker holds callers to the contract ----------------------------------------------


@pytest.mark.parametrize("tool,params,why", [
    ("lint.run", {"source": "counter.v"}, "does not take 'source'"),
    ("lint.run", {"sources": "counter.v", "timeout": "soon"}, "timeout"),
    ("synth.run", {"sources": "counter.v", "top": "counter", "max_latches": "none"}, "max_latches"),
    ("lint.run", {"sources": ["ok.v", "odd,name.v"]}, "comma"),
    ("formal.run", {"sby": ["a.sby", "b.sby"]}, "one path"),
])
def test_a_call_outside_the_contract_is_refused_and_nothing_runs(rtl_ready, tool, params, why):
    engine, rtl = rtl_ready
    before = dict(engine.state.tool_runs)
    with pytest.raises(ToolContractError, match=why):
        ToolBroker(engine).invoke(_owner(engine, rtl), tool, params, rtl)
    assert engine.state.tool_runs == before


@needs("verilator")
def test_a_list_of_paths_runs_and_is_stored_as_before(rtl_ready):
    engine, rtl = rtl_ready
    source = str(RTL / "counter.v")
    run, outcome = ToolBroker(engine).invoke(_owner(engine, rtl), "lint.run", {"sources": [source]}, rtl)
    assert outcome.succeeded, outcome.summary
    assert run.params["sources"] == source and run.values("sources") == [source]


def test_a_tool_without_a_contract_takes_parameters_as_given(nirmaan_org):
    """Extensions that declare no contract keep working: params None means 'as given' (lists still joined)."""
    from nirmaan.runtime.tools import check_params

    spec = nirmaan_org.tools["project.read"].model_copy(update={"params": None})
    assert check_params(spec, {"anything": "goes", "x": ["a", "b"]}) == {"anything": "goes", "x": "a,b"}


# --- The runtime hands a tool only what it declares ----------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys")
def test_the_runtime_passes_a_tool_only_its_declared_inputs(rtl_ready):
    engine, rtl = rtl_ready
    engine.remember(MemoryScope.TASK, rtl, "input.bogus", "1", _owner(engine, rtl))
    cite = token(upstream(engine, "microarchitecture"))
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite))])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    runs = [engine.state.tool_runs[r] for r in report.tool_runs]
    assert {r.tool for r in runs} >= {"lint.run", "simulator.run", "synth.run"}
    for run in runs:
        declared = {p.name for p in engine.org.tools[run.tool].params}
        assert "workspace" not in run.params and "bogus" not in run.params, run
        assert set(run.params) <= declared or all(k.startswith("max_") for k in set(run.params) - declared), run


# --- Crown jewel and discovery -------------------------------------------------------------


def test_a_new_tool_contract_needs_no_core_changes(fixed_clock):
    """An extension declares a tool with a contract, a skill and team holding it, and a binding.

    The broker enforces the contract with no core change.
    """
    from nirmaan.company import builder
    from nirmaan.models import Actor, ActorKind, Function, OrgUnit, Skill, ToolRisk, ToolSpec, ToolStatus, UnitKind
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.org import register_extension, unregister_extension
    from nirmaan.runtime import ToolOutcome, register_binding, unregister_binding

    @register_binding("ruler.measure")
    def measure(params, engine):
        return ToolOutcome(True, f"{len(list_values(params['items']))} items at scale {params.get('scale', '1')}")

    @register_extension("test-ruler")
    def ruler(b):
        b.add(
            ToolSpec(id="ruler.measure", name="Ruler", category="platform", risk=ToolRisk.READ,
                     status=ToolStatus.AVAILABLE,
                     params=(ParamSpec(name="items", kind=ParamKind.PATHS, required=True),
                             ParamSpec(name="scale", kind=ParamKind.NUMBER))),
            Skill(id="rulers", name="Rulers", domain="architecture", tools=("ruler.measure",)),
            OrgUnit(id="architecture.rulers", name="Rulers", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                    parent="architecture", noun="Ruler Architect", skills=("rulers",)),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
        role = next(r for r in org.roles.values() if r.unit == "architecture.rulers" and r.level.rank <= 40)
        actor = Actor(role=role.id, kind=ActorKind.HUMAN, name="test")
        broker = ToolBroker(engine)
        run, outcome = broker.invoke(actor, "ruler.measure", {"items": ["a", "b"], "scale": "2.5"})
        assert outcome.succeeded and outcome.summary == "2 items at scale 2.5" and run.params["items"] == "a,b"
        with pytest.raises(ToolContractError, match="scale"):
            broker.invoke(actor, "ruler.measure", {"items": "a", "scale": "big"})
        with pytest.raises(ToolContractError, match="does not take 'size'"):
            broker.invoke(actor, "ruler.measure", {"items": "a", "size": "3"})
    finally:
        unregister_extension("test-ruler")
        unregister_binding("ruler.measure")


def test_the_cli_shows_a_tool_contract():
    result = CliRunner().invoke(app, ["org", "tool", "pnr.run"])
    assert result.exit_code == 0, result.output
    for text in ("netlist", "required", "stop_after", "max_<metric>", "paths"):
        assert text in result.output, text
    unknown = CliRunner().invoke(app, ["org", "tool", "no.such.tool"])
    assert unknown.exit_code != 0
