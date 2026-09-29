"""Milestone 23: architecture and RTL agents.

Seats for interface specification, microarchitecture, and RTL implementation,
all filled by the one M20 ``ModelRuntime``. A design seat works only from
approved upstream artifacts, returns files that become artifacts with
provenance, and RTL reaches review only after real lint and simulation passed
on exactly the files submitted. No test calls a model API; real-tool tests skip
when an executable is absent (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import agent, drive, human, tid

from nirmaan.models import (
    Assurance,
    DecisionKind,
    EscalationKind,
    EvidenceKind,
    ReviewState,
    TaskStatus,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import (
    MockLLM,
    ModelRuntime,
    ResultStatus,
    assemble,
    render_work_prompt,
    review_task,
    run_task,
)
from nirmaan.runtime.files import split_files
from nirmaan.work import PolicyViolationError
from nirmaan.work.engine import WorkError
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
AXI = RTL / "axi4_lite"
COUNTER_BLOCK = "Create a 4-bit wrapping counter."
AXI_BLOCK = "Create an AXI4-Lite register block."


def needs(*executables: str):
    """Skip without the executables, except those CI names in NIRMAAN_REQUIRE_EDA (then it fails)."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


def token(art_id: str) -> str:
    return "[artifact:" + re.sub(r"[^A-Za-z0-9._\-]", ".", art_id) + "]"


def file(path: str, kind: str, content: str, cite: str, entry: str | None = None) -> dict:
    return {"path": path, "kind": kind, "title": path, "summary": f"{path}, from {cite}.",
            "content": content, **({"entry": entry} if entry else {})}


def answer(*files: dict, **fields) -> str:
    """A scripted model answer: the JSON object, then one delimited block per file."""
    meta = [{k: v for k, v in f.items() if k != "content"} for f in files]
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                       "escalation": None, **fields}, indent=1)
    blocks = "".join(f"=== FILE: {f['path']} ===\n{f['content']}=== END FILE ===\n" for f in files)
    return f"{head}\n{blocks}"


def upstream(engine, stage: str) -> str:
    return engine.task(tid(engine, stage)).artifacts[0]


def with_workspace(engine, task_id: str, path: Path) -> None:
    owner = human(engine.task(task_id).owner)
    from nirmaan.models import MemoryScope

    engine.remember(MemoryScope.TASK, task_id, "input.workspace", str(path), owner)


def counter_files(cite: str, rtl: str | None = None) -> tuple[dict, dict]:
    return (file("counter.v", "rtl_source", rtl or (RTL / "counter.v").read_text(), cite, entry="counter"),
            file("counter_tb.v", "testbench", (RTL / "counter_tb.v").read_text(), cite, entry="counter_tb"))


@pytest.fixture()
def block(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)


@pytest.fixture()
def rtl_ready(block, tmp_path):
    """The counter block with requirements, interface spec, and microarchitecture approved."""
    rtl = tid(block, "rtl-implementation")
    drive(block, until=rtl)
    assert block.task(rtl).status is TaskStatus.READY
    with_workspace(block, rtl, tmp_path / "work")
    return block, rtl


def _no_tools(monkeypatch, tmp_path) -> None:
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


# --- Planning: small blocks get a small workflow ------------------------------------------


def test_small_blocks_plan_the_block_workflow(nirmaan_org, fixed_clock):
    orchestrator = Orchestrator(nirmaan_org, clock=fixed_clock)
    engine = orchestrator.plan(AXI_BLOCK)
    assert engine.state.project.analysis.intent == "block_design"
    assert engine.state.project.workflows == ("block-design",)
    stages = [t.stage for t in engine.state.tasks.values() if t.stage]
    assert stages == ["requirements", "interface-spec", "microarchitecture", "rtl-implementation"]
    rtl = engine.task(tid(engine, "rtl-implementation"))
    assert set(rtl.expected_outputs) == {"rtl_source", "testbench"}
    gated = [r for r in rtl.evidence_requirements if r.before_review]
    assert {t for r in gated for t in r.tools} == {"lint.run", "simulator.run", "synth.run", "formal.run"}
    assert orchestrator.analyze("Create a 4-port AXI-to-NoC bridge.").intent == "new_ip"


# --- Only approved upstream artifacts ---------------------------------------------------


def test_unapproved_upstream_artifacts_are_refused(block, tmp_path):
    """A microarchitecture withdrawn before review: the RTL seat must not build on it."""
    micro, rtl = tid(block, "microarchitecture"), tid(block, "rtl-implementation")
    drive(block, until=micro)
    owner = agent(block.task(micro).owner)
    block.start(micro, owner)
    block.submit(micro, owner, [{"kind": "microarchitecture_spec", "title": "Draft microarchitecture",
                                 "summary": "An unreviewed draft."}])
    block.escalate(micro, owner, EscalationKind.TECHNICAL, reason="withdrawn before review")
    task = block.task(micro)
    authority = AuthorityService(block.org)
    manager = next(r for r in task.escalation_path
                   if authority.check(r, DecisionKind.CANCEL_TASK, task.criticality, task.unit).allowed)
    block.cancel(micro, human(manager), "withdrawn")
    assert block.task(rtl).status is TaskStatus.READY  # a cancelled dependency counts as settled
    draft = block.state.artifacts[upstream(block, "microarchitecture")]
    assert draft.assurance is Assurance.EXECUTED

    text = render_work_prompt(assemble(block, rtl)).render()
    assert "An unreviewed draft." not in text and "withheld" in text
    assert token(draft.id) not in text

    llm = MockLLM()
    with pytest.raises(PolicyViolationError, match=r"P8.*executed, not approved"):
        run_task(block, rtl, ModelRuntime(llm))
    assert llm.calls == []  # refused before any prompt reached a model
    assert block.task(rtl).status is TaskStatus.READY and block.state.tool_runs == {}


# --- Files: approved content reaches the next seat, with provenance -----------------------


def test_a_spec_seat_writes_a_file_the_next_seat_reads(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    spec = tid(engine, "interface-spec")
    drive(engine, until=spec)
    with_workspace(engine, spec, tmp_path)
    requirements = upstream(engine, "requirements")
    body = "# Counter interface\n\nPorts: clk, rst, en, count[3:0], wrap.\n"
    report = run_task(engine, spec, ModelRuntime(MockLLM(script=[
        answer(file("interface_spec.md", "interface_spec", body, token(requirements)))])))

    assert report.status is ResultStatus.SUBMITTED
    task = engine.task(spec)
    assert task.status is TaskStatus.IN_REVIEW
    art = engine.state.artifacts[task.artifacts[0]]
    path = Path(art.location)
    assert path.read_text() == body and path.is_relative_to(tmp_path)
    assert art.digest == "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    assert art.derived_from == (requirements,) and art.produced_by.startswith("mock-llm@")
    assert token(requirements) in art.summary

    review_task(engine, spec, ModelRuntime(MockLLM()))
    engine.approve(spec, human(task.approver), "spec agreed")
    assert engine.state.artifacts[art.id].assurance is Assurance.APPROVED

    micro = tid(engine, "microarchitecture")
    text = render_work_prompt(assemble(engine, micro)).render()
    assert token(art.id) in text and "count[3:0], wrap." in text  # approved content, byte for byte

    path.write_text(body + "Tampered after approval.\n")
    text = render_work_prompt(assemble(engine, micro)).render()
    assert "digest mismatch" in text and "Tampered" not in text


def test_a_seat_cannot_review_its_own_spec(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    spec = tid(engine, "interface-spec")
    drive(engine, until=spec)
    with_workspace(engine, spec, tmp_path)
    run_task(engine, spec, ModelRuntime(MockLLM(script=[
        answer(file("interface_spec.md", "interface_spec", "# Spec\n", token(upstream(engine, "requirements"))))])))

    llm = MockLLM()
    with pytest.raises(PolicyViolationError, match="P6"):
        review_task(engine, spec, ModelRuntime(llm), role=engine.task(spec).owner)
    assert llm.calls == [] and engine.task(spec).review_state is ReviewState.PENDING


# --- RTL reaches review only through real lint and simulation -----------------------------


@needs("verilator", "yosys")
def test_rtl_whose_real_lint_fails_cannot_reach_review(rtl_ready):
    engine, rtl = rtl_ready
    cite = token(upstream(engine, "microarchitecture"))
    broken = (RTL / "counter.v").read_text().replace("count <= count + 4'd1;", "count <= count + 5'd1;")
    assert broken != (RTL / "counter.v").read_text()
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite, broken))])))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()
    lint = next(engine.state.tool_runs[r] for r in report.tool_runs if engine.state.tool_runs[r].tool == "lint.run")
    assert not lint.succeeded and "WIDTH" in Path(lint.references[1]).read_text()
    ev = next(engine.state.evidence[e] for e in report.evidence if engine.state.evidence[e].tool_run == lint.id)
    assert ev.kind is EvidenceKind.TOOL_RUN and not ev.substantiated  # the failure is on the record
    with pytest.raises(WorkError, match="not in review"):
        review_task(engine, rtl, ModelRuntime(MockLLM()))


@needs("verilator", "yosys")
def test_rtl_that_passes_real_lint_and_simulation_goes_to_review(rtl_ready):
    engine, rtl = rtl_ready
    micro = upstream(engine, "microarchitecture")
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(token(micro)))])))

    assert report.status is ResultStatus.SUBMITTED, report.detail
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_REVIEW
    arts = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in task.artifacts}
    assert set(arts) == {"rtl_source", "testbench"}
    for art in arts.values():
        data = Path(art.location).read_bytes()
        assert art.digest == "sha256:" + hashlib.sha256(data).hexdigest() and art.derived_from == (micro,)
    runs = {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in report.tool_runs}
    assert set(runs) == {"lint.run", "simulator.run", "synth.run"} and all(r.succeeded for r in runs.values())
    assert runs["lint.run"].params["sources"] == arts["rtl_source"].location
    assert runs["simulator.run"].params["sources"] == f"{arts['rtl_source'].location},{arts['testbench'].location}"
    assert runs["simulator.run"].params["top"] == "counter_tb"
    assert unsatisfied_requirements(engine.state, task) == ["Independent review recorded"]

    llm = MockLLM()
    review = review_task(engine, rtl, ModelRuntime(llm))
    assert review.status is ResultStatus.SUBMITTED and engine.task(rtl).review_state is ReviewState.PASSED
    assert "module counter" in llm.calls[0].render()  # the reviewer reads the RTL itself
    engine.approve(rtl, human(task.approver), "lint-clean and simulated")
    assert engine.task(rtl).status is TaskStatus.COMPLETED
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)


def test_a_model_claiming_a_run_that_never_happened_is_refused(rtl_ready, monkeypatch, tmp_path):
    """No simulator is even installed; the model says lint and simulation passed anyway."""
    engine, rtl = rtl_ready
    _no_tools(monkeypatch, tmp_path)
    cite = token(upstream(engine, "microarchitecture"))
    lie = answer(*counter_files(cite), tool_runs=["run-0042"], claims=["lint and simulation passed"])
    with pytest.raises(PolicyViolationError, match="P5"):
        run_task(engine, rtl, ModelRuntime(MockLLM(script=[lie])))
    assert "run-0042" not in engine.state.tool_runs
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()


def test_without_the_tools_the_task_is_blocked_and_nothing_is_simulated(rtl_ready, monkeypatch, tmp_path):
    engine, rtl = rtl_ready
    _no_tools(monkeypatch, tmp_path)
    cite = token(upstream(engine, "microarchitecture"))
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[answer(*counter_files(cite))])))

    assert report.status is ResultStatus.BLOCKED
    task = engine.task(rtl)
    assert task.status is TaskStatus.BLOCKED and "not found" in task.blocked_reason
    assert "never simulated" in task.blocked_reason
    assert engine.state.tool_runs == {} and task.artifacts == ()


def test_an_answer_without_the_rtl_file_is_refused(rtl_ready):
    """Prose about RTL is not RTL: nothing to lint, so nothing goes to review."""
    engine, rtl = rtl_ready
    cite = token(upstream(engine, "microarchitecture"))
    prose = answer(artifacts=[{"kind": "rtl_source", "title": "Counter", "summary": f"Written per {cite}."}])
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[prose])))
    assert report.status is ResultStatus.REFUSED and "no rtl_source file" in report.detail
    assert engine.task(rtl).status is TaskStatus.IN_PROGRESS and engine.state.tool_runs == {}


# --- The file-block format ------------------------------------------------------------------


def test_file_blocks_are_split_from_the_answer_verbatim():
    text = ('{"files": [{"path": "a.v"}]}\n=== FILE: a.v ===\nassign x = {a, b};\n'
            "  $display(\"\\n\");\n=== END FILE ===\n")
    rest, files, problems = split_files(text)
    assert json.loads(rest) == {"files": [{"path": "a.v"}]}  # braces in Verilog do not confuse the parser
    assert files == {"a.v": 'assign x = {a, b};\n  $display("\\n");\n'} and problems == []


@pytest.mark.parametrize("path", ["/etc/passwd", "../escape.v", "a/../../b.v", "sp ace.v", ""])
def test_unsafe_paths_are_rejected(path):
    _, files, problems = split_files(f"{{}}\n=== FILE: {path} ===\nx\n=== END FILE ===\n")
    assert files == {} and problems


def test_unterminated_and_duplicate_blocks_are_rejected():
    _, files, problems = split_files("{}\n=== FILE: a.v ===\none\n=== END FILE ===\n"
                                     "=== FILE: a.v ===\ntwo\n=== END FILE ===\n=== FILE: b.v ===\nopen\n")
    assert files == {"a.v": "one\n"} and len(problems) == 2


def test_orphan_files_and_uncited_files_are_dropped_and_reported(rtl_ready):
    engine, rtl = rtl_ready
    cite = token(upstream(engine, "microarchitecture"))
    good, tb = counter_files(cite)
    uncited = {**tb, "summary": "Trust me."}
    text = answer(good, uncited) + "=== FILE: extra.v ===\nmodule extra; endmodule\n=== END FILE ===\n"
    runtime = ModelRuntime(MockLLM(script=[text]))
    report = run_task(engine, rtl, runtime)
    assert "dropped uncited files: counter_tb.v" in report.detail
    assert "extra.v" in report.detail  # a block no entry declared


# --- Crown jewel: a new design seat needs no core changes ------------------------------------


def test_a_new_design_seat_needs_no_core_changes(fixed_clock, tmp_path):
    """A register-map seat joins: capability, skill, unit, intent, workflow, and its own checker.

    Nothing in the runtime, prompt renderer, engine, policy, or broker changes.
    The seat writes a JSON file; ``regmap.check`` runs over it before review.
    """
    from nirmaan.company import builder
    from nirmaan.models import (
        Capability,
        CapabilityKind,
        Criticality,
        EvidenceRequirement,
        FileInput,
        Function,
        IntentRule,
        Level,
        OrgUnit,
        ReviewRequirement,
        Skill,
        StageTemplate,
        ToolRisk,
        ToolSpec,
        ToolStatus,
        UnitKind,
        WorkflowTemplate,
    )
    from nirmaan.org import register_extension, unregister_extension
    from nirmaan.runtime import ToolOutcome, register_binding, unregister_binding

    @register_binding("regmap.check")
    def check(params, engine):
        problems = []
        for source in params.get("sources", "").split(","):
            regs = json.loads(Path(source).read_text())["registers"]
            offsets = [r["offset"] for r in regs]
            problems += [f"overlapping offset {o}" for o in set(offsets) if offsets.count(o) > 1]
        return ToolOutcome(not problems, "; ".join(problems) or f"{len(offsets)} registers, no overlap")

    @register_extension("test-register-maps")
    def register_maps(b):
        review = ReviewRequirement(capability="arch.review", min_level=Level.SENIOR)
        b.add(
            ToolSpec(id="regmap.check", name="Register map checker", category="eda", risk=ToolRisk.EXECUTE,
                     status=ToolStatus.AVAILABLE),
            Capability(id="arch.register_map", name="Register map design", kind=CapabilityKind.EXECUTION,
                       description="Specify a block's software-visible registers.", produces=("register_map",),
                       approved_inputs=True),
            Skill(id="register_map_design", name="Register map design", domain="architecture",
                  provides=("arch.register_map", "arch.review"), tools=("regmap.check",),
                  validation_criteria=("No two registers share an offset.",)),
            OrgUnit(id="architecture.regmaps", name="Register Maps", kind=UnitKind.TEAM,
                    function=Function.ENGINEERING, parent="architecture", noun="Register Map Architect",
                    skills=("register_map_design",)),
            IntentRule(intent="register_map", patterns=(r"\bregister map\b",), priority=5),
            WorkflowTemplate(
                id="register-map", name="Register map", description="Specify a register map.",
                intents=("register_map",),
                stages=(
                    StageTemplate(id="brief", title="Register brief", phase="Requirements",
                                  capability="req.analyze", criticality=Criticality.MEDIUM,
                                  review=ReviewRequirement(capability="req.review"), outputs=("requirements_spec",),
                                  evidence=(EvidenceRequirement(description="Independent review recorded",
                                                                accepts=(EvidenceKind.REVIEW_RECORD,)),)),
                    StageTemplate(id="register-map", title="Register map", phase="Architecture",
                                  capability="arch.register_map", depends_on=("brief",),
                                  criticality=Criticality.MEDIUM, review=review, outputs=("register_map",),
                                  evidence=(EvidenceRequirement(description="Independent review recorded",
                                                                accepts=(EvidenceKind.REVIEW_RECORD,)),
                                            EvidenceRequirement(
                                                description="Register map is overlap-free",
                                                accepts=(EvidenceKind.TOOL_RUN,), tools=("regmap.check",),
                                                files=(FileInput(param="sources", kinds=("register_map",)),),
                                                before_review=True))),
                ),
            ),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a register map for a timer.")
        seat = tid(engine, "register-map")
        drive(engine, until=seat)
        task = engine.task(seat)
        assert task.owner.startswith("architecture.regmaps.")
        with_workspace(engine, seat, tmp_path)
        cite = token(upstream(engine, "brief"))
        overlapping = json.dumps({"registers": [{"name": "CTRL", "offset": 0}, {"name": "LOAD", "offset": 0}]})
        report = run_task(engine, seat, ModelRuntime(MockLLM(script=[
            answer(file("regs.json", "register_map", overlapping + "\n", cite))])))
        assert report.status is ResultStatus.REFUSED and engine.task(seat).status is TaskStatus.IN_PROGRESS

        clean = json.dumps({"registers": [{"name": "CTRL", "offset": 0}, {"name": "LOAD", "offset": 4}]})
        report = run_task(engine, seat, ModelRuntime(MockLLM(script=[
            answer(file("regs.json", "register_map", clean + "\n", cite))])))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        assert engine.task(seat).status is TaskStatus.IN_REVIEW
        review_task(engine, seat, ModelRuntime(MockLLM()))
        engine.approve(seat, human(task.approver))
        art = engine.state.artifacts[engine.task(seat).artifacts[0]]
        assert art.assurance is Assurance.APPROVED and json.loads(Path(art.location).read_text()) == json.loads(clean)
    finally:
        unregister_extension("test-register-maps")
        unregister_binding("regmap.check")


# --- The AXI4-Lite register block: the Stage 4 demo -------------------------------------


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
def test_the_axi4_lite_register_block_is_designed_by_agents(nirmaan_org, fixed_clock, tmp_path):
    """Spec, microarchitecture, and RTL seats; real lint, simulation, synthesis, and formal; reviewed and approved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    stages = (("interface-spec", "requirements", [("interface_spec.md", "interface_spec", None)]),
              ("microarchitecture", "interface-spec", [("microarchitecture.md", "microarchitecture_spec", None)]),
              ("rtl-implementation", "microarchitecture", [("axi4_lite_regs.v", "rtl_source", "axi4_lite_regs"),
                                                           ("axi4_lite_regs_tb.v", "testbench", "axi4_lite_regs_tb"),
                                                           ("axi4_lite_regs.sby", "formal_spec", None)]))
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, outputs in stages:
        seat = tid(engine, stage)
        assert engine.task(seat).status is TaskStatus.READY, seat
        with_workspace(engine, seat, tmp_path / stage)
        cite = token(upstream(engine, source))
        llm = MockLLM(script=[answer(*(file(name, kind, (AXI / name).read_text(), cite, entry)
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
    for art in arts:  # every file is the one the tools ran on, derived from the approved microarchitecture
        assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
        assert art.derived_from == (upstream(engine, "microarchitecture"),)
    runs = {engine.state.tool_runs[engine.state.evidence[e].tool_run].tool
            for e in rtl.evidence if engine.state.evidence[e].tool_run}
    assert runs == {"lint.run", "simulator.run", "synth.run", "formal.run"}
    # Every claim is backed by a recorded run or a recorded review; nothing is a bare claim.
    for task in engine.state.tasks.values():
        for ev in (engine.state.evidence[e] for e in task.evidence):
            assert ev.kind is not EvidenceKind.CLAIM
            if ev.kind is EvidenceKind.TOOL_RUN:
                assert ev.substantiated and engine.state.tool_runs[ev.tool_run].succeeded
