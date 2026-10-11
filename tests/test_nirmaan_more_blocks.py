"""Milestone 26: three more blocks designed by agents, end to end.

The M23 flow proved on the AXI4-Lite register block now runs on a synchronous
FIFO, a round-robin arbiter, and an APB register block. For each, a plain
request plans the ``block-design`` workflow; the interface-spec,
microarchitecture, and RTL seats are filled by ``ModelRuntime`` over a scripted
``MockLLM`` answering with the block's fixture files; the RTL reaches review
only after real lint and simulation ran on exactly those files; and a human
approves every stage. No test calls a model API.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from nirmaan_helpers import drive, human, tid
from test_nirmaan_design_agents import answer, file, token, upstream, with_workspace
from laws import needs

from nirmaan.models import Assurance, EvidenceKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, review_task, run_task

RTL = Path(__file__).parent / "fixtures" / "rtl"

#: (request, fixture folder, RTL module). The request is what a person would type.
BLOCKS = [
    ("Create a parameterizable synchronous FIFO.", "sync_fifo", "sync_fifo"),
    ("Create a round-robin arbiter for four requesters.", "rr_arbiter", "rr_arbiter"),
    ("Create an APB register block with four 32-bit registers.", "apb_regs", "apb_regs"),
]


@pytest.mark.parametrize("request_text", [b[0] for b in BLOCKS] + [
    "Design a synchronous FIFO with configurable depth and width.",
    "Build an N-way round-robin arbiter.",
    "Implement a register block with an APB interface.",
])
def test_natural_requests_plan_the_block_workflow(nirmaan_org, fixed_clock, request_text):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert engine.state.project.analysis.intent == "block_design"
    assert engine.state.project.workflows == ("block-design",)
    stages = [t.stage for t in engine.state.tasks.values() if t.stage]
    assert stages == ["requirements", "interface-spec", "microarchitecture", "rtl-implementation"]


@pytest.mark.parametrize("request_text", [
    "Implement an APB4 subordinate with four registers.",
    "Create an APB3 register block.",
])
def test_apb_revisions_are_recognized(nirmaan_org, fixed_clock, request_text):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert engine.state.project.analysis.intent == "block_design"
    assert "apb" in engine.state.project.analysis.features


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
@pytest.mark.parametrize("request_text,folder,top", BLOCKS, ids=[b[1] for b in BLOCKS])
def test_the_block_is_designed_by_agents(nirmaan_org, fixed_clock, tmp_path, request_text, folder, top):
    """Spec, microarchitecture, and RTL seats; real lint, simulation, synthesis, and formal; approved."""
    fixtures = RTL / folder
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    stages = (("interface-spec", "requirements", [("interface_spec.md", "interface_spec", None)]),
              ("microarchitecture", "interface-spec", [("microarchitecture.md", "microarchitecture_spec", None)]),
              ("rtl-implementation", "microarchitecture", [(f"{top}.v", "rtl_source", top),
                                                           (f"{top}_tb.v", "testbench", f"{top}_tb"),
                                                           (f"{top}.sby", "formal_spec", None)]))
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, outputs in stages:
        seat = tid(engine, stage)
        assert engine.task(seat).status is TaskStatus.READY, seat
        with_workspace(engine, seat, tmp_path / stage)
        cite = token(upstream(engine, source))
        llm = MockLLM(script=[answer(*(file(name, kind, (fixtures / name).read_text(), cite, entry)
                                       for name, kind, entry in outputs))])
        report = run_task(engine, seat, ModelRuntime(llm))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        if source != "requirements":  # the approved upstream document reached the seat verbatim
            upstream_art = engine.state.artifacts[upstream(engine, source)]
            assert Path(upstream_art.location).read_text() in llm.calls[0].render()
        review = review_task(engine, seat, ModelRuntime(MockLLM()))
        assert review.status is ResultStatus.SUBMITTED, review.detail
        engine.approve(seat, human(engine.task(seat).approver), "agreed")
        assert engine.task(seat).status is TaskStatus.COMPLETED

    rtl = engine.task(tid(engine, "rtl-implementation"))
    arts = [engine.state.artifacts[a] for a in rtl.artifacts]
    assert {a.kind for a in arts} == {"rtl_source", "testbench", "formal_spec"}
    assert all(a.assurance is Assurance.APPROVED for a in arts)
    for art in arts:  # every file is the fixture, byte for byte, derived from the approved microarchitecture
        assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
        assert Path(art.location).read_bytes() == (fixtures / Path(art.location).name).read_bytes()
        assert art.derived_from == (upstream(engine, "microarchitecture"),)
    runs = [engine.state.tool_runs[engine.state.evidence[e].tool_run]
            for e in rtl.evidence if engine.state.evidence[e].tool_run]
    gated = {t for r in rtl.evidence_requirements if r.before_review for t in r.tools}
    assert {"lint.run", "simulator.run", "synth.run", "formal.run"} <= {r.tool for r in runs} == gated
    sim = next(r for r in runs if r.tool == "simulator.run")
    assert sim.succeeded and f"{top}_tb: PASS" in Path(sim.references[0]).read_text()
    # Every claim is backed by a recorded run or a recorded review; nothing is a bare claim.
    for task in engine.state.tasks.values():
        for ev in (engine.state.evidence[e] for e in task.evidence):
            assert ev.kind is not EvidenceKind.CLAIM
            if ev.kind is EvidenceKind.TOOL_RUN:
                assert ev.substantiated and engine.state.tool_runs[ev.tool_run].succeeded
