"""The two whole-flow cases, their fixed documents and fixtures (G3, council record 2026-11-17, decision 2).

The cases load only when asked for (``flow="whole"``), name no skill, fix no stage, and list what each seated stage
exercises as the planner gives it. Their digests cover every fixed input. Every held-out check and every mutant
cites a statement in the fixed documents (WF3), and the copies leave the single-seat cases' files as they are.
The record's open finding on the requirements seat is settled here: a document given through the case's ``inputs``
never reaches that seat as text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import load_cases, validate_case
from nirmaan.evals.cases import referenced_files
from nirmaan.integrations.veritriage import render_parts
from nirmaan.models import Actor, ActorKind, MemoryScope, TaskKind
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime.context import assemble
from nirmaan.runtime.prompt import render_work_prompt

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
FLOW = EVALS / "flow"
CASES = {"flow/axil-timer": FLOW / "axil_timer" / "citations.json",
         "flow/axi4-lite-regs-driver": FLOW / "axi4_lite" / "citations.json"}
FIXTURES = ("tests/fixtures/fw/axi4_lite/axi4_lite_regs_drv_swallowed_error.c",
            "tests/fixtures/fw/axi4_lite/axi4_lite_regs_drv_all_strobes.c",
            "tests/fixtures/fw/axi4_lite/axi4_lite_regs_drv_sticky_response.c",
            "tests/fixtures/rtl/axil_timer/axil_timer_tb_weak.v",
            "tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v",
            "tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_tb_strict2.v")


@pytest.fixture(scope="module")
def org():
    return build_organization()


@pytest.fixture(scope="module")
def cases():
    return {c.id: c for c in load_cases(EVALS, flow="whole")}


def test_the_two_cases_load_only_when_asked_for(cases):
    assert sorted(cases) == sorted(CASES)
    assert not {c.id for c in load_cases(EVALS)} & set(CASES)


def test_each_case_is_valid_credits_nothing_and_fixes_no_stage(org, cases):
    for case in cases.values():
        assert validate_case(org, case, ROOT) == [], case.id
        assert case.flow == "whole" and case.skills == () and case.upstream == {}
        # The reference answers every stage, for a replay only; no seat is given it.
        assert {f.kind for f in case.reference} >= {"requirements_spec", "interface_spec", "rtl_source"}
        assert case.expected_behavior and case.known_failure_modes and case.held_out


def test_exercised_is_what_the_planner_gives_each_seated_stage(org, cases):
    for case in cases.values():
        engine = Orchestrator(org).plan(case.request)
        planned = {}
        for task in engine.state.tasks.values():
            if task.kind is TaskKind.WORK and task.stage:
                planned[task.stage] = sorted(s.id for s in assemble(engine, task.id).domain.skills)
        assert {stage: sorted(skills) for stage, skills in case.exercised.items()} == planned, case.id
        assert case.seat == list(planned)[-1]  # the final stage is the one judged


def test_the_digest_covers_every_fixed_input(cases):
    for case in cases.values():
        named = referenced_files(case)
        given = [p for stage in case.inputs.values() for files in stage.values() for p in files]
        assert given and set(given) <= set(named), case.id
        assert all((ROOT / p).is_file() for p in named), case.id


def test_the_held_out_checks_are_as_ruled(cases):
    timer, regs = cases["flow/axil-timer"], cases["flow/axi4-lite-regs-driver"]
    assert len(timer.held_out) == 2 and len(regs.held_out) == 7
    assert [c.tool for c in regs.held_out] == ["simulator.run", "regmap.verify", "simulator.run", "fw.build", "fw.test",
                                               "fw.test", "fw.test"]
    # Check 5 runs on the flow's own RTL, its top from the RTL stage's declared entry; 6 and 7 on the reference.
    own, ref, driver_test = regs.held_out[4], regs.held_out[5], regs.held_out[6]
    assert own.seat_files["rtl"] == ("rtl_source",) and own.seat_entries == {"top": ("rtl_source",)}
    assert "top" not in own.params and "rtl" not in own.case_files
    assert ref.case_files["rtl"] == ("tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v",)
    assert driver_test.scorer == "must-fail" and driver_test.seat_files["sources"] == ("driver", "driver_test")
    assert all("evals/flow/axi4_lite/held_out_test.c" in c.case_files.get("sources", ()) for c in (own, ref))


# --- Every check and mutant cites the fixed documents (WF3) ------------------------------------------------------


def _tags(path: Path) -> set[str]:
    return set(re.findall(r"\[req:([A-Z0-9-]+)\]", path.read_text(encoding="utf-8")))


def _headings(path: Path) -> set[str]:
    return {line[3:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## ")}


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_check_and_mutant_cites_a_statement_in_the_fixed_documents(cases, case_id):
    case = cases[case_id]
    data = json.loads(CASES[case_id].read_text(encoding="utf-8"))
    assert data["format"] == "nirmaan.flow-citations" and data["case"] == case_id
    documents = [ROOT / d for d in data["documents"]]
    given = {p for stage in case.inputs.values() for files in stage.values() for p in files}
    assert set(data["documents"]) <= given  # the documents cited are the case's fixed inputs
    tags = set().union(*(_tags(d) for d in documents))
    headings = {f"{d.relative_to(ROOT).as_posix()}: {h}" for d in documents for h in _headings(d)}
    assert set(data["checks"]) == {c.name for c in case.held_out}
    assert set(data["mutants"]) == {m for c in case.held_out for files in c.mutants.values() for m in files}
    for cited in [*data["checks"].values(), *data["mutants"].values()]:
        assert cited
        for ref in cited:
            assert ref in tags or ref in headings, (case_id, ref)
    # And the other way: every tag is cited by a check or a mutant, or listed as judged by none, with the reason.
    cited_tags = {ref for refs in [*data["checks"].values(), *data["mutants"].values()] for ref in refs} & tags
    not_judged = data["not_judged"]
    assert all(isinstance(why, str) and why for why in not_judged.values())
    assert set(not_judged) <= tags and not set(not_judged) & cited_tags
    assert cited_tags | set(not_judged) == tags, sorted(tags - cited_tags - set(not_judged))


def test_each_tag_is_stated_once_and_both_documents_state_the_whole_range_rule():
    for path, rule in ((FLOW / "axil_timer" / "requirements.md", "TMR-TEST-RANGE"),
                       (FLOW / "axi4_lite" / "requirements.md", "AXIL-TEST-RANGE")):
        found = re.findall(r"\[req:([A-Z0-9-]+)\]", path.read_text(encoding="utf-8"))
        assert len(found) == len(set(found)), path
        assert rule in found
        assert "Tests accept the whole allowed range" in path.read_text(encoding="utf-8")


# --- The copies leave the single-seat cases as they are ------------------------------------------------------------


def test_the_register_block_copy_keeps_every_requirement_of_the_spec_cases_document():
    original = EVALS / "spec" / "axi4_lite" / "requirements.md"
    assert _tags(original) <= _tags(FLOW / "axi4_lite" / "requirements.md")


def test_the_driver_interface_copy_names_the_requirements_and_never_the_specification_or_the_rtl_as_the_source():
    copy = (FLOW / "axi4_lite" / "driver_api.md").read_text(encoding="utf-8")
    flat = " ".join(copy.split())
    assert "from the interface specification" not in flat and "derived from the RTL" not in flat
    assert "the requirements document fixes" in flat and "must agree with the block's approved RTL" in flat
    original = (EVALS / "firmware" / "axi4_lite" / "driver_api.md").read_text(encoding="utf-8")
    # Below the reworded opening, the programming interface is the single-seat case's, word for word.
    assert copy.split("## `axi4_lite_regs_map.h`", 1)[1] == original.split("## `axi4_lite_regs_map.h`", 1)[1]


def test_the_held_out_test_copy_adds_only_the_unmapped_write_check():
    original = (EVALS / "firmware" / "axi4_lite" / "held_out_test.c").read_text(encoding="utf-8")
    copy = (FLOW / "axi4_lite" / "held_out_test.c").read_text(encoding="utf-8")
    checks = re.compile(r'check\("(\w+)"')
    assert checks.findall(copy) == [*checks.findall(original)[:4], "unmapped_write_is_a_bus_error",
                                    *checks.findall(original)[4:]]


def test_the_fixtures_exist():
    for rel in FIXTURES:
        assert (ROOT / rel).is_file(), rel


# --- Open finding: the requirements seat and a document given through inputs --------------------------------------


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_document_given_through_inputs_never_reaches_the_requirements_seat_as_text(org, cases, case_id):
    """Fact 10 of the record, settled: task inputs are task memory, which parameterizes a task's tools and is never
    rendered (``runtime/prompt.py``), and the requirements task builds on no stage, so no approved upstream file
    carries it either. The whole-flow runner must give the document another way, or label its trials
    "seated from interface-spec" (decision 2)."""
    case = cases[case_id]
    engine = Orchestrator(org).plan(case.request)
    [task] = [t for t in engine.state.tasks.values() if t.stage == "requirements"]
    assert task.depends_on == () or not any(engine.state.tasks[d].artifacts for d in task.depends_on)
    actor = Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name="test")
    for key, paths in case.inputs["requirements"].items():  # as the runner gives a stage its inputs (M71)
        engine.remember(MemoryScope.TASK, task.id, f"input.{key}", ",".join(str(ROOT / p) for p in paths), actor)
    packet = assemble(engine, task.id)
    assert any(m.key == "input.customer_requirements" for m in packet.memory)  # given ...
    system, user = render_parts(render_work_prompt(packet))
    prompt = system + user
    for paths in case.inputs["requirements"].values():
        for rel in paths:
            text = (ROOT / rel).read_text(encoding="utf-8")
            line = max(text.splitlines(), key=len)  # the document's longest line stands for its text
            assert line.strip() not in prompt and rel not in prompt  # ... but neither its text nor its path is seen
    assert case.request in prompt  # the request itself is rendered
