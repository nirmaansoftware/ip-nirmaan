"""Milestone 27: repair after review, and retry limits per stage.

When an independent reviewer requests changes, the submission is superseded
(its files leave ``state.artifacts`` for an ``Attempt`` that names the
reviews), and the owner may be run again with the review's findings as
citable records and the sent-back files in its prompt. Its new files go
through every before-review check and to review again. ``max_attempts`` and
``max_review_rounds`` are data on a capability or a workflow stage, with the
CLI over the stage over the capability over 1; the counts live in state, so a
limit covers every run, and an exhausted budget escalates. No test calls a
model API; real-tool tests skip when an executable is absent (or fail when CI
names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid

from nirmaan.models import (
    Assurance,
    EscalationKind,
    EvidenceKind,
    MemoryScope,
    ReviewState,
    TaskStatus,
    Verdict,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import route_escalation
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, assemble, limits, review_task, run_task
from nirmaan.work import AuthorityError, PolicyViolationError, ProjectStore

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
COUNTER_BLOCK = "Create a 4-bit wrapping counter."
BRIDGE = "Create a 4-port AXI-to-NoC bridge."

GOOD = (RTL / "counter.v").read_text()
REVISED = "// Wraps from 15 to 0, as the interface spec requires.\n" + GOOD


def needs(*executables: str):
    """Skip without the executables, except those CI names in NIRMAAN_REQUIRE_EDA (then it fails)."""
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")


def token(kind: str, record_id: str) -> str:
    return f"[{kind}:" + re.sub(r"[^A-Za-z0-9._\-]", ".", record_id) + "]"


def file(path: str, kind: str, content: str, cite: str, entry: str | None = None) -> dict:
    return {"path": path, "kind": kind, "title": path, "summary": f"{path}, from {cite}.",
            "content": content, **({"entry": entry} if entry else {})}


def answer(*files: dict) -> str:
    """A scripted model answer: the JSON object, then one delimited block per file."""
    meta = [{k: v for k, v in f.items() if k != "content"} for f in files]
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                       "escalation": None}, indent=1)
    return f"{head}\n" + "".join(f"=== FILE: {f['path']} ===\n{f['content']}=== END FILE ===\n" for f in files)


def verdict(word: str, comments: str) -> str:
    return json.dumps({"verdict": word, "comments": comments, "uncertainty": 0.2})


def workspace(engine, task_id: str, path: Path) -> None:
    engine.remember(MemoryScope.TASK, task_id, "input.workspace", str(path), human(engine.task(task_id).owner))


def superseded(engine, task_id: str) -> list:
    return sorted((a for a in engine.state.attempts.values() if a.task == task_id and a.reviews),
                  key=lambda a: a.number)


def run_of(engine, runs, tool: str) -> str:
    return next(r for r in runs if engine.state.tool_runs[r].tool == tool)


# --- A units-sheet seat, from data alone (the crown jewel's organization) -----------------------


@pytest.fixture()
def units(fixed_clock, tmp_path):
    """A units-sheet stage whose capability allows 2 attempts and 3 review rounds, and whose stage says 2 rounds.

    Its checker is bound here. Nothing in the runtime, prompt renderer, engine,
    policy, or broker knows about it.
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

    logs = tmp_path / "logs"
    logs.mkdir()

    @register_binding("units.lint")
    def check(params, engine):
        problems = [f"error: {row['name']} has no unit" for source in params.get("sources", "").split(",")
                    for row in json.loads(Path(source).read_text())["quantities"] if not row.get("unit")]
        log = logs / f"units-{len(list(logs.iterdir())) + 1}.log"
        log.write_text("checking quantities\n" + "".join(f"{p}\n" for p in problems) + "done\n")
        return ToolOutcome(not problems, f"{len(problems)} quantities without a unit", references=(str(log),))

    @register_extension("test-units-sheets")
    def units_sheets(b):
        reviewed = EvidenceRequirement(description="Independent review recorded",
                                       accepts=(EvidenceKind.REVIEW_RECORD,))
        b.add(
            ToolSpec(id="units.lint", name="Units lint", category="eda", risk=ToolRisk.EXECUTE,
                     status=ToolStatus.AVAILABLE),
            Capability(id="arch.units_sheet", name="Units sheet", kind=CapabilityKind.EXECUTION,
                       description="Tabulate a block's physical quantities.", produces=("units_sheet",),
                       approved_inputs=True, max_attempts=2, max_review_rounds=3),
            Skill(id="units_sheets", name="Units sheets", domain="architecture",
                  provides=("arch.units_sheet", "arch.review"), tools=("units.lint",),
                  validation_criteria=("Every quantity names its unit.",)),
            OrgUnit(id="architecture.units_sheets", name="Units sheets", kind=UnitKind.TEAM,
                    function=Function.ENGINEERING, parent="architecture", noun="Units Architect",
                    skills=("units_sheets",)),
            IntentRule(intent="units_sheet", patterns=(r"\bunits sheet\b",), priority=5),
            WorkflowTemplate(
                id="units-sheet", name="Units sheet", description="Tabulate quantities.", intents=("units_sheet",),
                stages=(
                    StageTemplate(id="brief", title="Brief", phase="Requirements", capability="req.analyze",
                                  criticality=Criticality.MEDIUM, review=ReviewRequirement(capability="req.review"),
                                  outputs=("requirements_spec",), evidence=(reviewed,)),
                    StageTemplate(id="units-sheet", title="Units sheet", phase="Architecture",
                                  capability="arch.units_sheet", depends_on=("brief",),
                                  criticality=Criticality.MEDIUM, max_review_rounds=2,
                                  review=ReviewRequirement(capability="arch.review", min_level=Level.SENIOR),
                                  outputs=("units_sheet",),
                                  evidence=(reviewed, EvidenceRequirement(
                                      description="Every quantity has a unit", accepts=(EvidenceKind.TOOL_RUN,),
                                      tools=("units.lint",),
                                      files=(FileInput(param="sources", kinds=("units_sheet",)),),
                                      before_review=True))),
                ),
            ),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a units sheet for a timer.")
        seat = tid(engine, "units-sheet")
        drive(engine, until=seat)
        workspace(engine, seat, tmp_path / "work")
        cite = token("artifact", engine.task(tid(engine, "brief")).artifacts[0])
        yield engine, seat, cite
    finally:
        unregister_extension("test-units-sheets")
        unregister_binding("units.lint")


def sheet(cite: str, *rows: tuple[str, str]) -> str:
    table = json.dumps({"quantities": [{"name": n, "unit": u} for n, u in rows]}) + "\n"
    return answer(file("units.json", "units_sheet", table, cite))


def send_back(engine, seat: str, comments: str) -> str:
    """The planned reviewer's seat requests changes, citing the latest passing check."""
    lint = [r for r in engine.state.tool_runs.values() if r.task == seat and r.succeeded][-1]
    reviewer = MockLLM(script=[verdict("request_changes", f"{comments} See {token('run', lint.id)}.")])
    report = review_task(engine, seat, ModelRuntime(reviewer))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    assert engine.task(seat).status is TaskStatus.CHANGES_REQUESTED
    return report.review


# --- Crown jewel: a new stage gets review repair with no core changes ----------------------------


def test_a_new_stage_gets_review_repair_with_no_core_changes(units):
    engine, seat, cite = units
    owner = MockLLM(script=[sheet(cite, ("period", "ns"), ("load", "ns")),
                            sheet(cite, ("period", "ns"), ("load", "cycles"))])
    assert run_task(engine, seat, ModelRuntime(owner)).status is ResultStatus.SUBMITTED
    first = engine.task(seat).artifacts
    review = send_back(engine, seat, "A load is counted in cycles, not ns.")

    report = run_task(engine, seat, ModelRuntime(owner))  # no override: the stage allows 2 rounds
    assert report.status is ResultStatus.SUBMITTED, report.detail
    prompt = owner.calls[1].render()
    assert "Repair after review: submission" in prompt
    assert token("review", review) in {c.token for c in owner.calls[1].citations}
    assert f"Review {token('review', review)} by {engine.task(seat).reviewer}" in prompt
    assert "A load is counted in cycles, not ns." in prompt
    assert "Content of sent-back file units.json" in prompt and '"unit": "ns"}]' in prompt
    assert "Repair" not in owner.calls[0].render()

    task = engine.task(seat)
    assert task.status is TaskStatus.IN_REVIEW and not set(first) & set(task.artifacts)
    (old,) = superseded(engine, seat)
    assert [a.id for a in old.artifacts] == list(first) and old.reviews == (review,)
    assert not set(first) & set(engine.state.artifacts)
    reviewer = MockLLM()
    assert review_task(engine, seat, ModelRuntime(reviewer)).status is ResultStatus.SUBMITTED
    assert engine.task(seat).review_state is ReviewState.PASSED
    assert "A load is counted in cycles" in reviewer.calls[0].render()  # earlier findings, as context
    assert '"unit": "ns"}]' not in reviewer.calls[0].render()  # never the superseded file
    engine.approve(seat, human(task.approver), "repaired")
    arts = [a for a in engine.state.artifacts.values() if a.task == seat]
    assert [a.id for a in arts] == list(task.artifacts)
    assert json.loads(Path(arts[0].location).read_text())["quantities"][1]["unit"] == "cycles"
    assert all(a.assurance is Assurance.APPROVED for a in arts)


# --- Limits: CLI over stage over capability over 1 -----------------------------------------------


def test_the_stage_overrides_the_capability_and_the_cli_overrides_the_stage(units):
    engine, seat, _ = units
    assert limits(engine, seat) == (2, 2)  # attempts from the capability; rounds from the stage (not 3)
    assert limits(engine, seat, attempts=4, review_rounds=1) == (4, 1)
    assert limits(engine, tid(engine, "brief")) == (1, 1)  # neither sets anything
    with pytest.raises(Exception, match="at least 1"):
        limits(engine, seat, review_rounds=0)


def test_a_cli_limit_below_the_stage_escalates_where_the_stage_would_repair(units):
    engine, seat, cite = units
    owner = MockLLM(script=[sheet(cite, ("period", "ns"))])
    run_task(engine, seat, ModelRuntime(owner))
    send_back(engine, seat, "Name the load too.")

    report = run_task(engine, seat, ModelRuntime(owner), review_rounds=1)
    assert report.status is ResultStatus.NEEDS_ESCALATION and len(owner.calls) == 1
    assert engine.task(seat).status is TaskStatus.ESCALATED


def test_exhausted_review_rounds_escalate_through_the_owners_route(units):
    engine, seat, cite = units
    owner = MockLLM(script=[sheet(cite, ("period", "ns")), sheet(cite, ("period", "ns"), ("load", "ns"))])
    run_task(engine, seat, ModelRuntime(owner))
    send_back(engine, seat, "Name the load too.")
    assert run_task(engine, seat, ModelRuntime(owner)).status is ResultStatus.SUBMITTED
    send_back(engine, seat, "A load is counted in cycles.")

    report = run_task(engine, seat, ModelRuntime(owner))
    assert report.status is ResultStatus.NEEDS_ESCALATION and len(owner.calls) == 2  # no third model call
    task = engine.task(seat)
    esc = engine.state.escalations[report.escalation]
    assert task.status is TaskStatus.ESCALATED and esc.task == seat and esc.kind is EscalationKind.TECHNICAL
    assert esc.target_role == route_escalation(engine.org, task.owner, EscalationKind.TECHNICAL)
    assert "2 of 2 review rounds" in esc.reason
    assert [a.id for a in superseded(engine, seat)] == [a.split(": ")[0] for a in esc.attempted_actions]
    assert engine.state.audit[-1].action == "escalation.raise"

    # Resolving restores the task, not the budget: the limit covers the total.
    engine.resolve_escalation(esc.id, human(esc.target_role), "one more round")
    assert engine.task(seat).status is TaskStatus.CHANGES_REQUESTED
    assert run_task(engine, seat, ModelRuntime(owner)).status is ResultStatus.NEEDS_ESCALATION
    assert len(owner.calls) == 2


# --- The budget persists across runs ---------------------------------------------------------------


@pytest.fixture()
def rtl_ready(nirmaan_org, fixed_clock, tmp_path):
    """The counter block with requirements, interface spec, and microarchitecture approved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    workspace(engine, rtl, tmp_path / "work")
    cite = token("artifact", engine.task(tid(engine, "microarchitecture")).artifacts[0])
    return engine, rtl, cite


def test_the_attempt_budget_persists_across_nirmaan_runs(rtl_ready, tmp_path, monkeypatch):
    """The default mock answer carries no files, so every attempt is refused; the SDK is never imported."""
    from nirmaan.cli import app

    engine, rtl, _ = rtl_ready
    monkeypatch.setitem(sys.modules, "anthropic", None)  # any import of the SDK now fails
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id

    def run(*extra: str):
        result = CliRunner().invoke(app, ["run", project, "rtl-implementation", "--runtime", "mock-llm",
                                          "--root", str(root), *extra])
        assert result.exit_code == 0, result.output
        return result.output, ProjectStore(root).load(project)

    output, state = run("--attempts", "2")
    assert "attempt 2: refused" in output and len(state.attempts) == 2
    output, state = run("--attempts", "2")  # the same limit, a new run: nothing left
    assert "escalation:" in output and len(state.attempts) == 2
    assert state.tasks[rtl].status is TaskStatus.ESCALATED
    esc = next(e for e in state.escalations.values() if e.task == rtl)
    assert "2 of 2 attempts" in esc.reason

    from nirmaan.work import TaskEngine
    from nirmaan.company import build_organization

    loaded = TaskEngine(build_organization(), state)
    loaded.resolve_escalation(esc.id, human(esc.target_role), "allow one more")
    ProjectStore(root).save(loaded.state)
    output, state = run("--attempts", "3")  # the limit covers the total: one more attempt
    assert sorted(a.number for a in state.attempts.values()) == [1, 2, 3]
    assert "refused" in output and "attempt 1" not in output


# --- RTL: a reviewer sends real, checked work back ---------------------------------------------


@needs("verilator", "yosys")
def test_a_reviewer_sends_rtl_back_and_the_repaired_rtl_is_approved(rtl_ready, tmp_path):
    from nirmaan import engineering
    from nirmaan.export import export_project

    engine, rtl, cite = rtl_ready

    def counter(content: str) -> str:
        return answer(file("counter.v", "rtl_source", content, cite, entry="counter"),
                      file("counter_tb.v", "testbench", (RTL / "counter_tb.v").read_text(), cite, entry="counter_tb"))

    owner = MockLLM(script=[counter(GOOD), counter(REVISED)])
    first = run_task(engine, rtl, ModelRuntime(owner))
    assert first.status is ResultStatus.SUBMITTED, first.detail
    sent = engine.task(rtl).artifacts
    lint = run_of(engine, first.tool_runs, "lint.run")
    reviewer = MockLLM(script=[verdict("request_changes",
                                       f"Lint {token('run', lint)} is clean, but the wrap is undocumented.")])
    review = review_task(engine, rtl, ModelRuntime(reviewer)).review
    assert engine.task(rtl).status is TaskStatus.CHANGES_REQUESTED
    assert not set(sent) & set(engine.state.artifacts)

    second = run_task(engine, rtl, ModelRuntime(owner), review_rounds=2)
    assert second.status is ResultStatus.SUBMITTED, second.detail
    prompt = owner.calls[1].render()
    assert token("review", review) in prompt and "the wrap is undocumented" in prompt
    assert "Content of sent-back file counter.v" in prompt
    task = engine.task(rtl)
    submitted = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in task.artifacts}
    assert Path(submitted["rtl_source"].location).read_text() == REVISED
    runs = {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in second.tool_runs}
    assert all(r.succeeded for r in runs.values())  # every before-review check, again, on the new files
    assert runs["lint.run"].params["sources"] == (submitted["rtl_source"].location,)

    assert review_task(engine, rtl, ModelRuntime(MockLLM())).status is ResultStatus.SUBMITTED
    engine.approve(rtl, human(task.approver), "repaired after review")
    assert engine.task(rtl).status is TaskStatus.COMPLETED
    assert {a.id for a in engine.state.artifacts.values() if a.task == rtl} == set(task.artifacts)
    (old,) = superseded(engine, rtl)
    assert {a.id for a in old.artifacts} == set(sent)
    assert all(a.assurance is not Assurance.APPROVED for a in old.artifacts)

    # Superseded files reach neither the engineering links nor the export.
    linked = {link.artifact for link in engineering.artifact_links(engine.state).links}
    assert linked and linked <= set(task.artifacts)
    out = tmp_path / "export"
    export_project(engine.org, engine.state, out)
    exported = {json.loads(p.read_text())["artifact"] for p in out.rglob("*.provenance.json")}
    assert not exported & set(sent) and set(task.artifacts) <= exported
    copies = [p for p in out.rglob("*counter.v")]
    assert copies and all(p.read_text() == REVISED for p in copies)


# --- The engine: supersession, verdicts, and P6 --------------------------------------------------


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def test_a_change_request_supersedes_the_submission_and_is_audited(bridge):
    t = tid(bridge, "requirements")
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v1"}])
    bridge.review(t, agent(task.reviewer), Verdict.REQUEST_CHANGES, "latency unspecified")
    (old,) = superseded(bridge, t)
    entry = bridge.state.audit[-1]
    assert entry.action == "task.review" and entry.details["superseded"] == old.id
    assert entry.details["artifacts"] == [f"{t}#a1"] and bridge.task(t).artifacts == ()
    assert old.refusal.startswith(f"changes requested by {task.reviewer}")

    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v2"}])
    assert bridge.task(t).artifacts == (f"{t}#a2",)  # never reuses a superseded ID


def test_a_superseded_submissions_reviews_do_not_conflict_with_the_next(bridge):
    t = tid(bridge, "requirements")
    task = bridge.task(t)
    other = "product.management.requirements.senior"
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v1"}])
    bridge.review(t, agent(other), Verdict.REQUEST_CHANGES, "latency unspecified")
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v2"}])
    bridge.review(t, agent(task.reviewer), Verdict.APPROVE, "latency now specified")
    assert bridge.task(t).review_state is ReviewState.PASSED


def test_p6_holds_through_a_repair(units):
    engine, seat, cite = units
    owner = MockLLM(script=[sheet(cite, ("period", "ns")), sheet(cite, ("period", "ns"), ("load", "cycles"))])
    run_task(engine, seat, ModelRuntime(owner))
    send_back(engine, seat, "Name the load too.")
    run_task(engine, seat, ModelRuntime(owner))
    task = engine.task(seat)
    with pytest.raises(PolicyViolationError, match="may not review"):
        review_task(engine, seat, ModelRuntime(MockLLM()), role=task.owner)
    with pytest.raises((PolicyViolationError, AuthorityError)):
        engine.review(seat, agent(task.owner), Verdict.APPROVE)
    assert {r.reviewer for r in engine.state.reviews.values() if r.task == seat} == {task.reviewer}
    assert task.owner != task.reviewer
    # The owner's packet is its own seat; the reviewer's packet is the reviewer's.
    assert assemble(engine, seat).role.role == task.owner
    assert assemble(engine, seat, role=task.reviewer).role.role == task.reviewer


# --- The laws ----------------------------------------------------------------------------------------


def test_the_runtime_names_no_seat_stage_or_tool_and_keeps_the_import_laws():
    src = Path(__file__).parent.parent / "src" / "nirmaan"
    runtime = "".join(p.read_text() for p in (src / "runtime").glob("*.py"))
    assert not re.search(r"lint\.run|simulator\.run|fw\.|dft\.|firmware|driver|rtl_source|rtl-implementation", runtime)
    for path in (*(src / "runtime").glob("*.py"), src / "work" / "engine.py", src / "work" / "policy.py"):
        tree = ast.parse(path.read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.split(".")[0] in ("veritriage", "anthropic") for m in imported), path


def test_no_shipped_capability_or_stage_sets_a_limit(nirmaan_org):
    assert {c.max_attempts for c in nirmaan_org.capabilities.values()} == {1}
    assert {c.max_review_rounds for c in nirmaan_org.capabilities.values()} == {1}
    stages = [s for w in nirmaan_org.workflows.values() for s in w.stages]
    assert {s.max_attempts for s in stages} == {None} and {s.max_review_rounds for s in stages} == {None}
