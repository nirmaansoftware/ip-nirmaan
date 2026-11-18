"""The two whole-flow cases, their fixed documents and fixtures (G3, council record 2026-11-17, decision 2).

The cases load only when asked for (``flow="whole"``), name no skill, fix no stage, and list what each seated stage
exercises as the planner gives it. Their digests cover every fixed input. Every held-out check and every mutant
cites a statement in the fixed documents (WF3), and the copies leave the single-seat cases' files as they are.
The record's open finding on the requirements seat is settled here: a document given through the case's ``inputs``
never reaches that seat as text.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

import flow_mutants
from laws import needs
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
            "tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_tb_strict2.v",
            "tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_awready_low_in_reset.v")


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


# --- Each fixed requirements document has a current check record by another session ------------------------------
#
# By convention a whole-flow requirements document is checked by a session other than its writer, and the check is
# kept next to it as ``requirements_check.json`` (format ``nirmaan.flow-document-check``): the document's sha256, the
# writer and the checker, when, the sources read, per-tag evidence (``path:line``, a test id, or ``unjudged``) and the
# result. Any edit to the document makes the record stale. A document whose first record has not landed yet is listed,
# with the reason, in ``evals/flow/requirements_check_pending.json``; a listed document that has a record fails, so the
# entry must go once its record lands. An author never writes the record for its own document.

CHECK_PENDING = FLOW / "requirements_check_pending.json"
CHECK_FIELDS = {"format", "case", "document", "document_sha256", "writer", "checker", "checked_at", "sources_read",
                "evidence", "result"}
_LINE = re.compile(r"^(?P<path>[^:\s]+):(?P<first>\d+)(?:-(?P<last>\d+))?$")
_TEST_ID = re.compile(r"^(?P<path>tests/[^:\s]+\.py)::(?P<name>\w+)(?:\[.*\])?$")


def _flow_requirements_documents() -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in FLOW.glob("*/requirements.md"))


def _evidence_problem(item: str, root: Path) -> str | None:
    if item == "unjudged":
        return None
    if m := _TEST_ID.match(item):
        path = root / m["path"]
        if not path.is_file() or not re.search(rf"^def {m['name']}\(", path.read_text(encoding="utf-8"), re.M):
            return f"no such test: {item}"
        return None
    if m := _LINE.match(item):
        path = root / m["path"]
        if not path.is_file():
            return f"no such file: {item}"
        lines = len(path.read_text(encoding="utf-8").splitlines())
        first, last = int(m["first"]), int(m["last"] or m["first"])
        if not 1 <= first <= last <= lines:
            return f"line out of range: {item}"
        return None
    return f"evidence is not path:line, a test id or unjudged: {item!r}"


def _check_record_problems(doc: str, record: dict, citations: dict, root: Path = ROOT) -> list[str]:
    """What is wrong with a document's check record, as a list (empty when it holds)."""
    problems = []
    missing = CHECK_FIELDS - set(record)
    if missing:
        return [f"missing fields: {sorted(missing)}"]
    if record["format"] != "nirmaan.flow-document-check":
        problems.append(f"format is {record['format']!r}")
    if record["case"] != citations["case"]:
        problems.append(f"case {record['case']!r} is not {citations['case']!r}")
    if record["document"] != doc:
        problems.append(f"document {record['document']!r} is not {doc!r}")
    if record["document_sha256"] != hashlib.sha256((root / doc).read_bytes()).hexdigest():
        problems.append("stale: the document changed after it was checked (document_sha256 differs)")
    writer, checker = record["writer"], record["checker"]
    if not (isinstance(writer, str) and writer and isinstance(checker, str) and checker):
        problems.append("writer and checker must be named")
    elif writer == checker:
        problems.append("the checker must be a session other than the writer")
    try:
        datetime.fromisoformat(str(record["checked_at"]))
    except ValueError:
        problems.append(f"checked_at is not an ISO date: {record['checked_at']!r}")
    sources = record["sources_read"]
    if not (isinstance(sources, list) and doc in sources and all((root / s).is_file() for s in sources)):
        problems.append("sources_read must list the document and only files that exist")
    tags = re.findall(r"\[req:([A-Z0-9-]+)\]", (root / doc).read_text(encoding="utf-8"))
    entries = record["evidence"] if isinstance(record["evidence"], list) else []
    seen = [e.get("tag") for e in entries if isinstance(e, dict)]
    if sorted(seen) != sorted(tags):
        extra = sorted({t for t in seen if t not in tags or seen.count(t) > 1}, key=str)
        problems.append(f"evidence must name each tag of the document once: missing {sorted(set(tags) - set(seen))}, "
                        f"extra or repeated {extra}")
    unjudged = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        items = entry.get("evidence")
        items = [items] if isinstance(items, str) else items
        if not items or not all(isinstance(i, str) for i in items):
            problems.append(f"{entry.get('tag')}: no evidence")
            continue
        if "unjudged" in items:
            if items != ["unjudged"]:
                problems.append(f"{entry.get('tag')}: unjudged and judged at once")
            unjudged.add(entry.get("tag"))
        problems.extend(f"{entry.get('tag')}: {p}" for i in items if (p := _evidence_problem(i, root)))
    if unjudged != set(citations["not_judged"]):
        problems.append(f"tags marked unjudged {sorted(unjudged)} differ from citations.json not_judged "
                        f"{sorted(citations['not_judged'])}")
    if record["result"] != "holds":
        problems.append(f"result is {record['result']!r}: a document that does not hold is fixed, not used")
    return problems


def _pending() -> dict[str, str]:
    data = json.loads(CHECK_PENDING.read_text(encoding="utf-8"))
    assert data["format"] == "nirmaan.flow-document-check-pending"
    return data["pending"]


def test_the_pending_list_names_only_flow_requirements_documents_each_with_a_reason():
    pending, documents = _pending(), set(_flow_requirements_documents())
    assert set(pending) <= documents, sorted(set(pending) - documents)
    assert all(isinstance(why, str) and why.strip() for why in pending.values())


@pytest.mark.parametrize("doc", _flow_requirements_documents())
def test_every_flow_requirements_document_has_a_current_check_record_by_another_session(doc):
    path = ROOT / doc
    record = path.with_name("requirements_check.json")
    pending = _pending()
    if doc in pending:  # its first record has not landed: it must not have one yet, or the entry is stale
        assert not record.is_file(), f"{doc}: its record has landed, so remove it from {CHECK_PENDING.name}"
        return
    assert record.is_file(), f"{doc} has no check record ({record.relative_to(ROOT).as_posix()}) and is not pending"
    citations = json.loads(path.with_name("citations.json").read_text(encoding="utf-8"))
    problems = _check_record_problems(doc, json.loads(record.read_text(encoding="utf-8")), citations)
    assert problems == [], problems


def test_the_check_record_rule_refuses_a_stale_or_self_checked_record():
    """The rule works before any record lands: a record built here (never written to disk) holds, and editing the
    document, naming the writer as the checker, dropping a tag, disagreeing with citations.json either way (a not judged
    tag given evidence, a cited tag marked unjudged), unreadable evidence or a result that does not hold each fail it."""
    doc = "evals/flow/axil_timer/requirements.md"
    citations = json.loads((FLOW / "axil_timer" / "citations.json").read_text(encoding="utf-8"))
    tags = re.findall(r"\[req:([A-Z0-9-]+)\]", (ROOT / doc).read_text(encoding="utf-8"))
    good = {"format": "nirmaan.flow-document-check", "case": "flow/axil-timer", "document": doc,
            "document_sha256": hashlib.sha256((ROOT / doc).read_bytes()).hexdigest(),
            "writer": "writer-session", "checker": "checker-session", "checked_at": "2026-11-18T06:00:00+00:00",
            "sources_read": [doc, "tests/fixtures/rtl/axil_timer/axil_timer_tb.v"],
            "evidence": [{"tag": t, "evidence": "unjudged" if t in citations["not_judged"]
                          else "tests/fixtures/rtl/axil_timer/axil_timer_tb.v:281"} for t in tags],
            "result": "holds"}
    assert _check_record_problems(doc, good, citations) == []
    bad = [
        dict(good, document_sha256=hashlib.sha256((ROOT / doc).read_bytes() + b"\n").hexdigest()),
        dict(good, checker="writer-session"),
        dict(good, evidence=good["evidence"][1:]),
        dict(good, evidence=[dict(e, evidence="tests/fixtures/rtl/axil_timer/axil_timer_tb.v:281")
                             for e in good["evidence"]]),
        dict(good, evidence=[dict(e, evidence="unjudged" if e["tag"] == "TMR-ORDER" else e["evidence"])
                             for e in good["evidence"]]),  # a tag a check cites, marked unjudged
        dict(good, evidence=[dict(good["evidence"][0], evidence="axil_timer_tb.v line 281"), *good["evidence"][1:]]),
        dict(good, result="does not hold"),
    ]
    for record in bad:
        assert _check_record_problems(doc, record, citations), record
    assert "stale" in _check_record_problems(doc, bad[0], citations)[0]


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


#: Each whole-flow case's own copy of the single-seat reference testbench, which its check 1 runs (G3 follow-up).
TB_COPIES = {"flow/axil-timer": ("tests/fixtures/rtl/axil_timer/axil_timer_tb.v",
                                 "evals/flow/axil_timer/axil_timer_tb.v"),
             "flow/axi4-lite-regs-driver": ("tests/fixtures/rtl/axi4_lite/axi4_lite_regs_tb.v",
                                            "evals/flow/axi4_lite/axi4_lite_regs_tb.v")}


#: Checks of an original a flow copy drops on purpose, by copy: the original's check line, word for word, and why.
#: Each must be in the original and absent from the copy; any other dropped or altered check fails the test.
TB_COPY_EXEMPT = {
    "evals/flow/axi4_lite/axi4_lite_regs_tb.v": {
        """check("AWREADY in reset", {31'd0, awready}, 32'd1);""":
            "No flow document states READY during reset (evals/flow/axi4_lite/requirements.md, section 2), and the "
            "single-seat interface specification (tests/fixtures/rtl/axi4_lite/interface_spec.md, sections 4 and 7) "
            "does not require it; only the single-seat microarchitecture.md (line 74) does, and in a whole flow the "
            "RTL stage writes its own microarchitecture, a design choice given to that seat, so a conforming flow "
            "block may hold AWREADY low in reset. AXIL-TEST-RANGE (requirements.md section 4) says a "
            "testbench checks only what the document states, and the judge assumes only behaviour the fixed "
            "document states (council/records/2026-11-17-g3-whole-flow-cases.md, lines 206 to 208), so a "
            "conforming block must not fail it. The single-seat original keeps it. A block that holds AWREADY low in "
            "reset (tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_awready_low_in_reset.v) passes this copy and "
            "fails the original: tests/test_whole_flow_cases.py::"
            "test_a_block_holding_awready_low_in_reset_passes_the_flow_copy_and_fails_the_original.",
    },
}


def _check_calls(path: str) -> list[str]:
    return [line.strip() for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
            if re.match(r"\s*(check|expect_reg)\(", line)]


def _copy_problems(kept: list[str], added: list[str], exempt: dict[str, str]) -> list[str]:
    """What is wrong with a copy's check lines against the original's (empty when it keeps every one but the named
    exemptions, in order, word for word, and adds some)."""
    problems = [f"exemption not in the original: {line}" for line in exempt if line not in kept]
    problems += [f"exempted check still in the copy: {line}" for line in exempt if line in added]
    problems += [f"exemption without a reason: {line}" for line, why in exempt.items() if not why.strip()]
    at = 0  # kept lines must appear in the copy in order: each is looked for after the one before it
    for line in kept:
        if line in exempt:
            continue
        if line in added[at:]:
            at = added.index(line, at) + 1
        else:
            problems.append(f"check dropped, altered or out of order: {line}")
    if len(added) <= len(kept) - len(exempt):
        problems.append("the copy adds no check")
    return problems


def test_the_copy_rule_refuses_any_other_dropped_or_altered_check():
    kept = ['check("a", x, 1);', 'check("b", y, 0);', 'expect_reg("c", 8\'h0, 0);']
    exempt = {'check("b", y, 0);': "a named reason"}
    good = ['check("a", x, 1);', 'check("new", z, 1);', 'expect_reg("c", 8\'h0, 0);']
    assert _copy_problems(kept, good, exempt) == []
    assert _copy_problems(kept, good, {})  # the same drop without its exemption fails
    assert _copy_problems(kept, ['check("new", z, 1);', 'expect_reg("c", 8\'h0, 0);'], exempt)  # another drop
    assert _copy_problems(kept, ['check("a", x, 2);', 'check("new", z, 1);', 'expect_reg("c", 8\'h0, 0);'], exempt)
    assert _copy_problems(kept, ['expect_reg("c", 8\'h0, 0);', 'check("a", x, 1);', 'check("n", z, 1);'], exempt)
    assert _copy_problems(kept, [*good, 'check("b", y, 0);'], exempt)  # an exempted check left in the copy
    assert _copy_problems(kept, good, {**exempt, 'check("gone", q, 0);': "why"})  # a stale exemption
    assert _copy_problems(kept, good, {'check("b", y, 0);': " "})  # no reason


@pytest.mark.parametrize("case_id", sorted(TB_COPIES))
def test_the_reference_testbench_copy_keeps_every_check_and_only_the_flow_case_runs_it(cases, case_id):
    """The copy adds checks and keeps every one of the original's, in order, word for word, except the named
    exemptions in ``TB_COPY_EXEMPT``; the single-seat case keeps running the original, so its digest and its
    recorded trials stay as they are."""
    original, copy = TB_COPIES[case_id]
    assert set(TB_COPY_EXEMPT) <= {c for _, c in TB_COPIES.values()}
    assert _copy_problems(_check_calls(original), _check_calls(copy), TB_COPY_EXEMPT.get(copy, {})) == []
    assert cases[case_id].held_out[0].case_files["sources"] == (copy,)
    single = {c.id: c for c in load_cases(EVALS)}
    assert any(original in c.case_files.get("sources", ()) for s in single.values() for c in s.held_out)
    assert not any(copy in files for s in single.values() for c in s.held_out for files in c.case_files.values())


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


# --- The author's mutant sweep, kept as a check record ----------------------------------------------------------------
#
# ``evals/flow/<block>/mutant_sweep.json`` records the sweep the author ran on each case's testbench copy (ip#339):
# every mutant ``tests/flow_mutants.py`` builds from the reference RTL, the tag it violates, its sha256 and its result,
# and the conforming RTLs, which must pass. The record is held to the builders (each mutant's text is rebuilt and its
# sha256 compared), to the testbench copy and reference RTL it ran on (by sha256: an edit to either makes it stale), and
# to the case: every tag the testbench check cites has a mutant that fails. One mutant per tag runs here with the
# simulator; the whole sweep reruns with the scratch script that wrote the record.

SWEEPS = {"flow/axil-timer": (FLOW / "axil_timer" / "mutant_sweep.json", flow_mutants.timer_mutants,
                              flow_mutants.TIMER_TAGS),
          "flow/axi4-lite-regs-driver": (FLOW / "axi4_lite" / "mutant_sweep.json", flow_mutants.regs_mutants,
                                         flow_mutants.REGS_TAGS)}
AWREADY_LOW = ROOT / "tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_awready_low_in_reset.v"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("case_id", sorted(SWEEPS))
def test_each_sweep_record_matches_its_builders_and_fails_every_tag_the_testbench_check_cites(cases, case_id):
    path, build, tags = SWEEPS[case_id]
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["format"] == "nirmaan.flow-mutant-sweep" and record["case"] == case_id
    case = cases[case_id]
    check = case.held_out[0]  # check 1 runs the testbench copy
    assert record["testbench"]["path"] == check.case_files["sources"][0] == TB_COPIES[case_id][1]
    assert record["testbench"]["sha256"] == _sha(ROOT / record["testbench"]["path"]), "stale: rerun the sweep"
    assert record["builder"] == f"tests/flow_mutants.py::{build.__name__}"
    reference = ROOT / record["reference"]["path"]
    assert record["reference"]["sha256"] == _sha(reference) and record["reference"]["result"] == "passes"
    built = build(reference.read_text(encoding="utf-8"))
    rows = record["mutants"]
    assert [r["mutant"] for r in rows] and sorted(r["mutant"] for r in rows) == sorted(built)
    for row in rows:
        assert set(row) == {"tag", "mutant", "sha256", "result", "errors", "first_failure"}, row
        assert row["tag"] == flow_mutants.tag_of(row["mutant"], tags)
        assert row["sha256"] == hashlib.sha256(built[row["mutant"]].encode("utf-8")).hexdigest(), row["mutant"]
        assert row["result"] == "fails" and row["first_failure"], row["mutant"]
    for entry in record["conforming"]:
        assert entry["result"] == "passes" and entry["sha256"] == _sha(ROOT / entry["path"]), entry
    citations = json.loads(CASES[case_id].read_text(encoding="utf-8"))
    judged = {t for t in citations["checks"][check.name] if t in set(tags.values())}
    assert judged == set(tags.values())  # the builders name exactly the tags the testbench check cites
    assert judged <= {r["tag"] for r in rows if r["result"] == "fails"}
    if case_id == "flow/axi4-lite-regs-driver":
        assert AWREADY_LOW.relative_to(ROOT).as_posix() in {e["path"] for e in record["conforming"]}


@needs("iverilog", "vvp")
@pytest.mark.parametrize("case_id", sorted(SWEEPS))
def test_one_mutant_per_tag_fails_the_testbench_copy_and_the_conforming_rtl_passes(case_id, tmp_path):
    path, build, _ = SWEEPS[case_id]
    record = json.loads(path.read_text(encoding="utf-8"))
    tb, top = ROOT / record["testbench"]["path"], record["testbench"]["top"]
    built = build((ROOT / record["reference"]["path"]).read_text(encoding="utf-8"))
    first = {}
    for row in record["mutants"]:
        first.setdefault(row["tag"], row["mutant"])
    for tag, name in sorted(first.items()):
        source = tmp_path / f"{name}.v"
        source.write_text(built[name], encoding="utf-8")
        passed, failed, why = flow_mutants.simulate(tb, top, source, tmp_path)
        assert failed is None or failed > 0, (tag, name, passed)
    for rel in [record["reference"]["path"], *(e["path"] for e in record["conforming"])]:
        passed, failed, why = flow_mutants.simulate(tb, top, ROOT / rel, tmp_path)
        assert failed == 0 and passed, (rel, why)


@needs("iverilog", "vvp")
def test_a_block_holding_awready_low_in_reset_passes_the_flow_copy_and_fails_the_original(tmp_path):
    """The one exemption of the register block copy (``TB_COPY_EXEMPT``), shown by a run: the conforming block that
    holds AWREADY low in reset passes the flow case's copy and fails the single-seat original on that check."""
    original, copy = TB_COPIES["flow/axi4-lite-regs-driver"]
    passed, failed, why = flow_mutants.simulate(ROOT / copy, "axi4_lite_regs_tb", AWREADY_LOW, tmp_path)
    assert failed == 0 and passed, why
    passed, failed, why = flow_mutants.simulate(ROOT / original, "axi4_lite_regs_tb", AWREADY_LOW, tmp_path)
    assert failed and why.startswith("AWREADY in reset"), (failed, why)
