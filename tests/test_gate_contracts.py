"""A seat is told the input contract of every gate tool its stage runs over its files.

The platform runs a gate tool over the seat's own files, filling the tool's
parameters from the file kinds a requirement binds. A parameter that takes one
path refuses a list, so a seat that writes two proof setups is refused before
review ("sby takes one path, not a list"). The work prompt states each gate
tool's contract, generated from the tool's own definition (its parameters and
their kinds) and the requirement's file bindings, never written per case. No
test calls a model.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_nirmaan_applicability_golden import REQUESTS

from nirmaan.evals import load_cases
from nirmaan.models import EvidenceKind, EvidenceRequirement, FileInput, ParamKind, ParamSpec, ToolRisk, ToolSpec
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime.context import assemble
from nirmaan.runtime.prompt import render_work_prompt

EVALS = Path(__file__).resolve().parents[1] / "evals"


def _lines(prompt: str, start: str) -> list[str]:
    return [line.removeprefix("- ") for line in prompt.splitlines() if line.removeprefix("- ").startswith(start)]


@pytest.fixture()
def arbiter(nirmaan_org, fixed_clock):
    case = next(c for c in load_cases(EVALS) if c.id == "rtl/rr-arbiter")
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    return engine, next(t for t in engine.state.tasks.values() if t.stage == case.seat)


def test_the_arbiter_seat_is_told_that_each_proof_gate_takes_one_sby(arbiter):
    # The pilot's live batch: three of five rr-arbiter trials wrote two .sby files and were refused before review.
    engine, rtl = arbiter
    prompt = render_work_prompt(assemble(engine, rtl.id)).render()
    for tool in ("formal.run", "formal.cover"):
        [line] = _lines(prompt, f"Input contract of {tool},")
        assert "Parameter sby takes one path, required" in line
        assert "from your formal_spec files, so submit exactly one formal_spec file" in line
        assert f"{tool} refuses the run (sby takes one path, not a list)" in line
        assert "Parameter sources takes a list of paths" in line and "from your rtl_source files" in line
    # The other gates' contracts are there too; the reviewer, who submits nothing, is not given them.
    assert {line.split(",")[0] for line in _lines(prompt, "Input contract of ")} == {
        f"Input contract of {tool}" for tool in ("lint.run", "simulator.run", "synth.run", "formal.run",
                                                 "formal.cover")}
    assert not _lines(render_work_prompt(assemble(engine, rtl.id, role=rtl.reviewer), "review").render(),
                      "Input contract of ")


def test_every_gate_tool_of_every_stage_declares_the_parameters_its_files_fill(nirmaan_org):
    # The contract is the tool's own definition: a gate tool with no declared parameters, or a binding to a
    # parameter the tool does not declare, would leave the seat without one.
    gated = 0
    for workflow in nirmaan_org.workflows.values():
        for stage in workflow.stages:
            for req in stage.evidence:
                if not req.files:
                    continue
                for tool in req.tools:
                    spec = nirmaan_org.tools.get(tool)
                    where = f"{workflow.id}/{stage.id}: {tool}"
                    assert spec is not None and spec.params is not None, where
                    assert all(spec.param(b.param) for b in req.files), where
                    gated += 1
    assert gated > 20


def test_every_planned_seat_gets_a_contract_for_every_gate_tool(nirmaan_org, fixed_clock):
    # Over every workflow the representative requests reach: each task's work prompt carries one contract line
    # per gate tool its requirements run over files, and none says a parameter or contract is missing.
    seen: set[str] = set()
    for request in REQUESTS:
        engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request)
        for task in engine.state.tasks.values():
            gated = {tool for req in task.evidence_requirements if req.files for tool in req.tools}
            if not gated or task.owner is None:
                continue
            prompt = render_work_prompt(assemble(engine, task.id)).render()
            contracts = _lines(prompt, "Input contract of ")
            assert {line.split(",")[0].split(":")[0].removeprefix("Input contract of ") for line in contracts} \
                == gated, (request, task.stage)
            assert not any("declares no parameters" in line or "is not one" in line for line in contracts)
            seen |= gated
    assert {"lint.run", "simulator.run", "synth.run", "formal.run", "formal.cover"} <= seen


def test_a_new_gate_tool_gets_its_contract_with_no_core_change(arbiter):
    # A tool registered tomorrow, with a one-file parameter, a list and an upstream input, is described from its
    # definition alone.
    engine, rtl = arbiter
    packet = assemble(engine, rtl.id)
    tool = ToolSpec(id="newgate.run", name="A new gate", category="eda", risk=ToolRisk.EXECUTE, params=(
        ParamSpec(name="setup", kind=ParamKind.PATH, required=True, description="The one setup file."),
        ParamSpec(name="rtl", kind=ParamKind.PATHS, description="The RTL."),
        ParamSpec(name="spec", kind=ParamKind.PATH, description="The approved spec.")))
    req = EvidenceRequirement(description="The new gate passes", accepts=(EvidenceKind.TOOL_RUN,),
                              tools=("newgate.run", "unknown.run"), before_review=True,
                              params=(("mode", "strict"),),
                              files=(FileInput(param="setup", kinds=("newgate_setup",)),
                                     FileInput(param="rtl", kinds=("rtl_source",)),
                                     FileInput(param="spec", kinds=("requirements_spec",), upstream=True)))
    task = packet.task.model_copy(update={"evidence_requirements": (req,), "gates": (tool,)})
    prompt = render_work_prompt(packet.model_copy(update={"task": task})).render()
    [line] = _lines(prompt, "Input contract of newgate.run,")
    assert ("Parameter setup takes one path, required: The one setup file. The platform fills it from your "
            "newgate_setup files, so submit exactly one newgate_setup file: two or more make a list, and "
            "newgate.run refuses the run (setup takes one path, not a list).") in line
    assert "Parameter rtl takes a list of paths: The RTL. The platform fills it from your rtl_source files." in line
    assert ("from the approved upstream requirements_spec files, so exactly one requirements_spec file in all"
            in line)
    assert line.endswith("Set by the platform: mode=strict.")
    # A tool with no definition is said to have none, never given an invented contract.
    assert _lines(prompt, "Input contract of unknown.run:") == [
        "Input contract of unknown.run: it declares no parameters, so the platform passes the files as given"]
