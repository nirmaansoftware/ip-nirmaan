"""Milestone 26: the repair loop.

When a seat's files fail their before-review checks, the runtime may ask the
same seat again, handing it the failed runs as citable evidence with a bounded
excerpt of each log. The limit is data (a capability's ``max_attempts``,
default 1, or ``run_task(attempts=...)``); a refused attempt's files are kept
in an ``Attempt`` record and never count toward review. No test calls a model
API; real-tool tests skip when an executable is absent (or fail when CI names
it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid

from nirmaan.models import Assurance, EvidenceKind, MemoryScope, ReviewState, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, review_task, run_task
from nirmaan.work import PolicyViolationError, ProjectStore

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
AXI = RTL / "axi4_lite"
FW = FIXTURES / "fw" / "axi4_lite"
COUNTER_BLOCK = "Create a 4-bit wrapping counter."
WITH_DRIVER = "Create an AXI4-Lite register block and its driver."
COSIM = ("cc", "verilator", "make")

GOOD = (RTL / "counter.v").read_text()
LINT_BROKEN = GOOD.replace("count <= count + 4'd1;", "count <= count + 5'd1;")  # a width warning; simulates fine
SIM_BROKEN = GOOD.replace("count <= count + 4'd1;", "count <= count + 4'd2;")  # lint-clean; counts wrong


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


def workspace(engine, task_id: str, path: Path) -> None:
    engine.remember(MemoryScope.TASK, task_id, "input.workspace", str(path), human(engine.task(task_id).owner))


def counter(cite: str, rtl: str = GOOD) -> str:
    return answer(file("counter.v", "rtl_source", rtl, cite, entry="counter"),
                  file("counter_tb.v", "testbench", (RTL / "counter_tb.v").read_text(), cite, entry="counter_tb"))


def runs_of(engine, ids) -> dict:
    return {engine.state.tool_runs[r].tool: engine.state.tool_runs[r] for r in ids}


@pytest.fixture()
def rtl_ready(nirmaan_org, fixed_clock, tmp_path):
    """The counter block with requirements, interface spec, and microarchitecture approved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    assert engine.task(rtl).status is TaskStatus.READY
    workspace(engine, rtl, tmp_path / "work")
    cite = token("artifact", engine.task(tid(engine, "microarchitecture")).artifacts[0])
    return engine, rtl, cite


def attempts_of(engine, task_id: str) -> list:
    return sorted((a for a in engine.state.attempts.values() if a.task == task_id), key=lambda a: a.number)


# --- The limit is data, and 1 changes nothing ----------------------------------------------


def test_no_shipped_capability_turns_repair_on(nirmaan_org):
    assert {c.max_attempts for c in nirmaan_org.capabilities.values()} == {1}


@needs("verilator", "yosys")
def test_one_attempt_behaves_exactly_as_before(rtl_ready):
    engine, rtl, cite = rtl_ready
    llm = MockLLM(script=[counter(cite, LINT_BROKEN), counter(cite)])
    report = run_task(engine, rtl, ModelRuntime(llm))

    assert report.status is ResultStatus.REFUSED and "P9" in report.detail
    assert len(llm.calls) == 1 and "attempts were refused" not in report.detail
    assert [a["attempt"] for a in report.attempts] == [None]
    assert engine.state.attempts == {}
    assert "task.attempt" not in {e.action for e in engine.state.audit}
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()
    assert "Repair" not in llm.calls[0].render()


# --- RTL: failed lint, repaired ---------------------------------------------------------------


@needs("verilator", "yosys")
def test_rtl_that_fails_lint_then_passes_reaches_review(rtl_ready):
    engine, rtl, cite = rtl_ready
    llm = MockLLM(script=[counter(cite, LINT_BROKEN), counter(cite)])
    report = run_task(engine, rtl, ModelRuntime(llm), attempts=2)

    assert report.status is ResultStatus.SUBMITTED, report.detail
    assert len(llm.calls) == 2
    assert [a["status"] for a in report.attempts] == ["refused", "submitted"]
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_REVIEW

    (first,) = attempts_of(engine, rtl)
    assert first.number == 1 and "P9" in first.refusal and report.attempts[0]["attempt"] == first.id
    assert sorted(a.kind for a in first.artifacts) == ["rtl_source", "testbench"]
    for art in first.artifacts:  # recorded, digested, and never the task's
        assert art.assurance is Assurance.EXECUTED and art.id not in engine.state.artifacts
        assert art.digest == "sha256:" + hashlib.sha256(Path(art.location).read_bytes()).hexdigest()
        assert Path(art.location).parent.name == "1"
    old = {a.location for a in first.artifacts}
    submitted = [engine.state.artifacts[a] for a in task.artifacts]
    assert all(Path(a.location).parent.name == "2" for a in submitted) and not old & {a.location for a in submitted}

    failed = runs_of(engine, first.tool_runs)["lint.run"]
    assert not failed.succeeded and set(failed.values("sources")) <= old
    assert all(not engine.state.evidence[e].substantiated for e in first.evidence
               if engine.state.evidence[e].tool_run == failed.id)
    passing = runs_of(engine, report.attempts[1]["tool_runs"])
    assert all(r.succeeded for r in passing.values())
    assert passing["lint.run"].params["sources"] == (next(a.location for a in submitted if a.kind == "rtl_source"),)
    entries = [e for e in engine.state.audit if e.action == "task.attempt"]
    assert len(entries) == 1 and entries[0].details["attempt"] == first.id
    assert entries[0].details["tool_runs"] == list(first.tool_runs)

    reviewer = MockLLM()
    review_task(engine, rtl, ModelRuntime(reviewer))
    seen = reviewer.calls[0].render()
    # The reviewer sees attempt 1's failed run (it is the task's evidence), never its files.
    assert "count <= count + 5'd1;" not in seen and "count <= count + 4'd1;" in seen
    assert engine.task(rtl).review_state is ReviewState.PASSED
    engine.approve(rtl, human(task.approver), "repaired and simulated")
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in task.artifacts)


@needs("verilator", "yosys")
def test_the_repair_prompt_cites_the_failed_run_and_quotes_its_log(rtl_ready):
    engine, rtl, cite = rtl_ready
    llm = MockLLM(script=[counter(cite, LINT_BROKEN), counter(cite)])
    run_task(engine, rtl, ModelRuntime(llm), attempts=2)

    (first,) = attempts_of(engine, rtl)
    lint = runs_of(engine, first.tool_runs)["lint.run"]
    ev = next(e for e in first.evidence if engine.state.evidence[e].tool_run == lint.id)
    before, after = llm.calls[0].render(), llm.calls[1].render()
    assert "Repair" not in before
    assert "Repair: your previous attempt 1 was refused" in after
    assert token("evidence", ev) in after and token("run", lint.id) in after
    assert token("evidence", ev) in {c.token for c in llm.calls[1].citations}  # citable, not just shown
    assert f"Log excerpt of {token('run', lint.id)}" in after and "%Warning-WIDTH" in after
    excerpt = after.split(f"Log excerpt of {token('run', lint.id)}")[1].split("\n\n")[0]
    assert sum(1 for line in excerpt.splitlines() if line.startswith("| ")) <= 20  # bounded
    assert "count <= count + 5'd1;" in after  # the refused file itself, digest-checked


@needs("verilator", "yosys")
def test_exhausting_the_attempts_stays_refused_and_lists_every_attempt(rtl_ready):
    """Lint-clean but wrong, then simulating but lint-dirty: each requirement has *a* passing run, never both."""
    engine, rtl, cite = rtl_ready
    llm = MockLLM(script=[counter(cite, SIM_BROKEN), counter(cite, LINT_BROKEN)])
    report = run_task(engine, rtl, ModelRuntime(llm), attempts=2)

    assert report.status is ResultStatus.REFUSED and len(llm.calls) == 2
    first, second = attempts_of(engine, rtl)
    assert [a["attempt"] for a in report.attempts] == [first.id, second.id]
    assert [a["status"] for a in report.attempts] == ["refused", "refused"]
    assert first.id in report.detail and second.id in report.detail and "2 attempts" in report.detail
    assert [e.details["attempt"] for e in engine.state.audit if e.action == "task.attempt"] == [first.id, second.id]
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_PROGRESS and task.artifacts == ()
    one, two = runs_of(engine, first.tool_runs), runs_of(engine, second.tool_runs)
    assert one["lint.run"].succeeded and not one["simulator.run"].succeeded
    assert two["simulator.run"].succeeded and not two["lint.run"].succeeded

    # A passing lint of attempt 1 does not carry attempt 2's files to review, even by hand.
    drafts = [{k: getattr(a, k) for k in ("kind", "title", "summary", "location", "digest")} for a in second.artifacts]
    with pytest.raises(PolicyViolationError, match="no passing run .* covers"):
        engine.submit(rtl, agent(task.owner), drafts)
    assert engine.task(rtl).artifacts == ()


def test_a_tool_the_broker_refuses_is_blocked_with_no_retry(rtl_ready, monkeypatch, tmp_path):
    engine, rtl, cite = rtl_ready
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    llm = MockLLM(script=[counter(cite), counter(cite)])
    report = run_task(engine, rtl, ModelRuntime(llm), attempts=3)

    assert report.status is ResultStatus.BLOCKED and len(llm.calls) == 1
    assert engine.task(rtl).status is TaskStatus.BLOCKED
    assert engine.state.attempts == {} and engine.state.tool_runs == {}


def test_nirmaan_run_takes_an_attempts_override_and_never_reaches_a_model_api(rtl_ready, tmp_path, monkeypatch):
    """The default mock answer carries no files, so both attempts are refused; the SDK is never imported."""
    from nirmaan.cli import app

    engine, rtl, _ = rtl_ready
    monkeypatch.setitem(sys.modules, "anthropic", None)  # any import of the SDK now fails
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id
    bad = CliRunner().invoke(app, ["run", project, "rtl-implementation", "--runtime", "mock-llm",
                                   "--attempts", "0", "--root", str(root)])
    assert bad.exit_code != 0

    result = CliRunner().invoke(app, ["run", project, "rtl-implementation", "--runtime", "mock-llm",
                                      "--attempts", "2", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "refused" in result.output and "attempt 1: refused" in result.output
    assert "attempt 2: refused" in result.output
    state = ProjectStore(root).load(project)
    assert sorted(a.number for a in state.attempts.values()) == [1, 2]


# --- Firmware: the same loop, from data alone ------------------------------------------------


def design_the_block(engine, tmp_path: Path) -> None:
    """The M23 flow: interface spec, microarchitecture, RTL, each by a seat, reviewed and approved."""
    stages = (("interface-spec", "requirements", [("interface_spec.md", "interface_spec", None)]),
              ("microarchitecture", "interface-spec", [("microarchitecture.md", "microarchitecture_spec", None)]),
              ("rtl-implementation", "microarchitecture", [("axi4_lite_regs.v", "rtl_source", "axi4_lite_regs"),
                                                           ("axi4_lite_regs_tb.v", "testbench", "axi4_lite_regs_tb")]))
    drive(engine, until=tid(engine, "interface-spec"))
    for stage, source, outputs in stages:
        seat = tid(engine, stage)
        workspace(engine, seat, tmp_path / stage)
        cite = token("artifact", engine.task(tid(engine, source)).artifacts[0])
        llm = MockLLM(script=[answer(*(file(name, kind, (AXI / name).read_text(), cite, entry)
                                       for name, kind, entry in outputs))])
        report = run_task(engine, seat, ModelRuntime(llm))
        assert report.status is ResultStatus.SUBMITTED, report.detail
        review_task(engine, seat, ModelRuntime(MockLLM()))
        engine.approve(seat, human(engine.task(seat).approver), "agreed")


def firmware_answer(cite: str, map_header: Path) -> str:
    files = [file("axi4_lite_regs_map.h", "driver", map_header.read_text(), cite)]
    files += [file(n, "driver", (FW / n).read_text(), cite) for n in ("axi4_lite_regs_drv.h", "axi4_lite_regs_drv.c")]
    files.append(file("axi4_lite_regs_test.c", "driver_test", (FW / "axi4_lite_regs_test.c").read_text(), cite))
    return answer(*files)


@needs(*COSIM, "iverilog", "vvp", "yosys")
def test_a_firmware_seat_is_repaired_by_the_same_loop(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(WITH_DRIVER)
    design_the_block(engine, tmp_path)
    seat = tid(engine, "firmware")
    workspace(engine, seat, tmp_path / "firmware")
    cite = token("artifact", engine.task(tid(engine, "interface-spec")).artifacts[0])
    llm = MockLLM(script=[firmware_answer(cite, FW / "axi4_lite_regs_map_wrong.h"),
                          firmware_answer(cite, FW / "axi4_lite_regs_map.h")])
    report = run_task(engine, seat, ModelRuntime(llm), attempts=2)

    assert report.status is ResultStatus.SUBMITTED, report.detail
    (first,) = attempts_of(engine, seat)
    failed = runs_of(engine, first.tool_runs)
    assert failed["fw.build"].succeeded and not failed["fw.test"].succeeded
    ev = next(e for e in first.evidence if engine.state.evidence[e].tool_run == failed["fw.test"].id)
    prompt = llm.calls[1].render()
    assert token("evidence", ev) in prompt and f"Log excerpt of {token('run', failed['fw.test'].id)}" in prompt
    task = engine.task(seat)
    assert task.status is TaskStatus.IN_REVIEW
    passing = runs_of(engine, report.attempts[1]["tool_runs"])
    assert all(r.succeeded for r in passing.values())
    assert set(passing["fw.test"].values("sources")) == {engine.state.artifacts[a].location
                                                                   for a in task.artifacts}


# --- Crown jewel: a new check gets repair with no core changes ---------------------------------


def test_a_new_check_gets_repair_with_no_core_changes(fixed_clock, tmp_path):
    """A units-table seat with ``max_attempts=2`` and its own checker, bound here.

    Nothing in the runtime, prompt renderer, engine, policy, or broker changes:
    the capability's limit and the stage's before-review requirement are data.
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

    @register_binding("units.check")
    def check(params, engine):
        problems = [f"error: {row['name']} has no unit" for source in params.get("sources", "").split(",")
                    for row in json.loads(Path(source).read_text())["quantities"] if not row.get("unit")]
        log = logs / f"units-{len(list(logs.iterdir())) + 1}.log"
        log.write_text("checking quantities\n" + "".join(f"{p}\n" for p in problems) + "done\n")
        return ToolOutcome(not problems, f"{len(problems)} quantities without a unit", references=(str(log),))

    @register_extension("test-units-tables")
    def units_tables(b):
        reviewed = EvidenceRequirement(description="Independent review recorded",
                                       accepts=(EvidenceKind.REVIEW_RECORD,))
        b.add(
            ToolSpec(id="units.check", name="Units checker", category="eda", risk=ToolRisk.EXECUTE,
                     status=ToolStatus.AVAILABLE),
            Capability(id="arch.units_table", name="Units table", kind=CapabilityKind.EXECUTION,
                       description="Tabulate a block's physical quantities.", produces=("units_table",),
                       approved_inputs=True, max_attempts=2),
            Skill(id="units_tables", name="Units tables", domain="architecture",
                  provides=("arch.units_table", "arch.review"), tools=("units.check",),
                  validation_criteria=("Every quantity names its unit.",)),
            OrgUnit(id="architecture.units", name="Units", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                    parent="architecture", noun="Units Architect", skills=("units_tables",)),
            IntentRule(intent="units_table", patterns=(r"\bunits table\b",), priority=5),
            WorkflowTemplate(
                id="units-table", name="Units table", description="Tabulate quantities.", intents=("units_table",),
                stages=(
                    StageTemplate(id="brief", title="Brief", phase="Requirements", capability="req.analyze",
                                  criticality=Criticality.MEDIUM, review=ReviewRequirement(capability="req.review"),
                                  outputs=("requirements_spec",), evidence=(reviewed,)),
                    StageTemplate(id="units-table", title="Units table", phase="Architecture",
                                  capability="arch.units_table", depends_on=("brief",),
                                  criticality=Criticality.MEDIUM,
                                  review=ReviewRequirement(capability="arch.review", min_level=Level.SENIOR),
                                  outputs=("units_table",),
                                  evidence=(reviewed, EvidenceRequirement(
                                      description="Every quantity has a unit", accepts=(EvidenceKind.TOOL_RUN,),
                                      tools=("units.check",),
                                      files=(FileInput(param="sources", kinds=("units_table",)),),
                                      before_review=True))),
                ),
            ),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Write a units table for a timer.")
        seat = tid(engine, "units-table")
        drive(engine, until=seat)
        workspace(engine, seat, tmp_path / "work")
        cite = token("artifact", engine.task(tid(engine, "brief")).artifacts[0])
        unitless = json.dumps({"quantities": [{"name": "period", "unit": "ns"}, {"name": "load"}]}) + "\n"
        complete = json.dumps({"quantities": [{"name": "period", "unit": "ns"}, {"name": "load", "unit": "cycles"}]})
        llm = MockLLM(script=[answer(file("units.json", "units_table", unitless, cite)),
                              answer(file("units.json", "units_table", complete + "\n", cite))])
        report = run_task(engine, seat, ModelRuntime(llm))  # no override: the capability says 2

        assert report.status is ResultStatus.SUBMITTED, report.detail
        assert len(llm.calls) == 2 and "| error: load has no unit" in llm.calls[1].render()
        (first,) = attempts_of(engine, seat)
        assert json.loads(Path(first.artifacts[0].location).read_text()) == json.loads(unitless)
        art = engine.state.artifacts[engine.task(seat).artifacts[0]]
        assert json.loads(Path(art.location).read_text()) == json.loads(complete)
        assert engine.task(seat).status is TaskStatus.IN_REVIEW
    finally:
        unregister_extension("test-units-tables")
        unregister_binding("units.check")


# --- The laws ----------------------------------------------------------------------------------


def test_the_runtime_names_no_seat_or_tool_and_keeps_the_import_laws():
    src = Path(__file__).parent.parent / "src" / "nirmaan"
    runtime = "".join(p.read_text() for p in (src / "runtime").glob("*.py"))
    assert not re.search(r"lint\.run|simulator\.run|fw\.|dft\.|firmware|driver|rtl_source", runtime)
    for path in (*(src / "runtime").glob("*.py"), src / "work" / "engine.py"):
        tree = ast.parse(path.read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.split(".")[0] in ("veritriage", "anthropic") for m in imported), path
