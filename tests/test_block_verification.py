"""Block verification: verify an existing block's RTL, with DV gates before review (M68).

A request that starts with "Verify" (or "Write a testbench for ...") plans
``block-verification``: the block's specification and RTL are handed over and
approved, then a verification plan checked against the spec, a self-checking
testbench that must pass on the approved RTL, and a proof over the approved RTL
that must be proven and reach every cover, each before review. Features refine
the testbench and proof tasks, so the skills a verification eval case judges
reach that seat's packet. Every request that is not a block verification plans
exactly as before. Real-tool tests skip when an executable is absent (or fail
when CI names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import json
import shutil
from functools import cache
from pathlib import Path

import pytest

from laws import needs
from nirmaan_helpers import GATE_TOOLS
from test_nirmaan_applicability_golden import REQUESTS
from test_nirmaan_gates_everywhere import FORMAL_TOOLS

from nirmaan.company import builder
from nirmaan.evals import load_case, run_case, validate_case
from nirmaan.models import FileInput, ScoreStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import assemble

REPO = Path(__file__).resolve().parents[1]
COUNTER = "tests/fixtures/rtl/counter.v"
COUNTER_TB = "tests/fixtures/rtl/counter_tb.v"
SPEC = "tests/fixtures/vplan/requirements_spec.md"

M68_FEATURES = ("systemverilog", "random_stimulus", "unbounded_proof", "coverage", "equivalence")

PLAIN = "Verify the existing interrupt controller RTL."
SV = "Verify the existing interrupt controller RTL with a SystemVerilog testbench."
RANDOM = "Verify the existing CRC block RTL with constrained-random stimulus."
UNBOUNDED = "Formally verify the existing deep counter RTL with an unbounded proof."
EVERYTHING = ("Formally verify the existing CRC block RTL with an unbounded proof, a constrained-random "
              "SystemVerilog testbench, coverage and an equivalence check.")

SV_SENIOR = "verification.dynamic.testbench.systemverilog.senior"
TB_SENIOR = "verification.dynamic.testbench.testing.senior"
SIM_LEAD = "verification.dynamic.testbench.tech_lead"
PROPERTY = "verification.formal.proof.property.senior"
MODEL_CHECKING = "verification.formal.proof.model_checking.senior"
FORMAL_SKILLS = ("formal_verification", "sva", "assertion_coverage")

#: Each request's DV seats: the task's skills, its owner and its reviewer.
SEATS = {
    (PLAIN, "dv-plan"): (("verification_planning",), "verification.methodology.planning.engineer",
                         "verification.methodology.planning.senior"),
    (PLAIN, "testbench"): (("directed_testing",), SV_SENIOR, SIM_LEAD),
    (SV, "testbench"): (("directed_testing", "systemverilog"), SV_SENIOR, SIM_LEAD),
    (RANDOM, "testbench"): (("directed_testing", "constrained_random"), TB_SENIOR, SIM_LEAD),
    (PLAIN, "assertions-formal"): (FORMAL_SKILLS, PROPERTY, MODEL_CHECKING),
    (UNBOUNDED, "assertions-formal"): ((*FORMAL_SKILLS, "model_checking"), MODEL_CHECKING, PROPERTY),
    (EVERYTHING, "coverage"): (("code_coverage",), "verification.dynamic.coverage.code.engineer",
                               "verification.dynamic.coverage.code.senior"),
    (EVERYTHING, "equivalence"): (("equivalence_checking",), "verification.formal.equivalence.engineer",
                                  MODEL_CHECKING),
}

#: Requests that verify something but are not a block verification, or name an M68 feature in another
#: workflow: they plan as before.
NOT_BLOCK_VERIFICATION = (
    "Create a FIFO and verify it with a SystemVerilog testbench and coverage.",
    "Verify the RTL fix to the arbiter.",
    "Change the data width of the bridge from 64 to 128 bits, with an equivalence check and coverage.",
    "Add a random backoff to the existing NoC router.",
    "Investigate why the regression tests started failing, with an unbounded proof.",
)


def _task(engine, stage):
    tasks = [t for t in engine.state.tasks.values() if t.stage == stage]
    assert len(tasks) == 1, [t.id for t in tasks]
    return tasks[0]


# --- Planning --------------------------------------------------------------------------------------------


def test_a_verify_request_plans_block_verification_with_its_gates(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(PLAIN)
    assert engine.state.project.analysis.intent == "block_verification"
    assert engine.state.project.workflows == ("block-verification",)
    stages = {t.stage for t in engine.state.tasks.values() if t.stage}
    assert stages == {"interface-spec", "design-under-test", "dv-plan", "testbench", "assertions-formal"}
    gated = {stage: {tool for r in _task(engine, stage).evidence_requirements if r.before_review for tool in r.tools}
             for stage in stages}
    assert gated == {"interface-spec": set(), "design-under-test": set(), "dv-plan": {"vplan.check"},
                     "testbench": {"simulator.run"}, "assertions-formal": {"formal.run", "formal.cover"}}
    # Every DV gate runs over the approved RTL, never a file of the seat's own.
    for stage in ("testbench", "assertions-formal"):
        for req in (r for r in _task(engine, stage).evidence_requirements if r.before_review):
            assert FileInput(param="sources", kinds=("rtl_source",), upstream=True,
                             beside=stage == "assertions-formal") in req.files
            assert not any("rtl_source" in b.kinds for b in req.files if not b.upstream)
    proof = next(r for r in _task(engine, "assertions-formal").evidence_requirements if "formal.run" in r.tools)
    assert [(b.metric, b.op, b.value) for b in proof.bounds] == [("proven", "min", 1)]


def test_coverage_and_equivalence_are_planned_when_asked_for(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(EVERYTHING)
    stages = {t.stage for t in engine.state.tasks.values() if t.stage}
    assert {"coverage", "equivalence"} <= stages
    assert set(M68_FEATURES) <= set(engine.state.project.analysis.features)
    # M69: equivalence.run runs, so the seat's eqy setup is gated over the approved RTL versions, placed beside it.
    gate, = (r for r in _task(engine, "equivalence").evidence_requirements if r.before_review)
    assert gate.tools == ("equivalence.run",) and gate.files == (
        FileInput(param="eqy", kinds=("equivalence_setup",)),
        FileInput(param="sources", kinds=("rtl_source",), upstream=True, beside=True))


def test_beside_is_for_upstream_inputs_only():
    with pytest.raises(ValueError, match="only an upstream input"):
        FileInput(param="sources", kinds=("rtl_source",), beside=True)


# --- Packets ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("request_text,stage", sorted(SEATS))
def test_each_dv_seat_carries_its_skills(request_text, stage, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    task = _task(engine, stage)
    skills, owner, reviewer = SEATS[(request_text, stage)]
    assert (task.workflow, task.skills, task.owner, task.reviewer) == ("block-verification", skills, owner, reviewer)
    for seat in (None, owner, reviewer):
        packet = assemble(engine, task.id) if seat is None else assemble(engine, task.id, role=seat)
        assert set(skills) <= {s.id for s in packet.domain.skills}, seat
        assert packet.domain.declines is None


def test_a_request_with_every_feature_stays_within_the_domain_cap(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(EVERYTHING)
    assert _task(engine, "testbench").skills == ("directed_testing", "systemverilog", "constrained_random")
    assert _task(engine, "assertions-formal").skills == (*FORMAL_SKILLS, "model_checking")
    for task in (t for t in engine.state.tasks.values() if t.stage):
        for seat in (task.owner, task.reviewer):
            assert assemble(engine, task.id, role=seat).domain.declines is None, (task.stage, seat)


def test_the_proof_seat_is_told_the_approved_rtl_sits_beside_its_files(nirmaan_org, fixed_clock):
    from nirmaan.runtime import render_work_prompt

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(PLAIN)
    proof = render_work_prompt(assemble(engine, _task(engine, "assertions-formal").id), "work").render()
    testbench = render_work_prompt(assemble(engine, _task(engine, "testbench").id), "work").render()
    told = "the approved rtl_source files are placed beside your files under their own names"
    assert told in proof and told not in testbench


# --- Nothing else moves ----------------------------------------------------------------------------------


@cache
def _pre_m68_org():
    """The organization with M68's data taken out: no new intent, features or workflow."""
    b = builder()
    d = b.definition
    d.features = [f for f in d.features if f.feature not in M68_FEATURES]
    d.intents = [i for i in d.intents if i.intent != "block_verification"]
    d.workflows = [wf for wf in d.workflows if wf.id != "block-verification"]
    return b.build()


def _plan(org, text, clock):
    """Every task, keyed by its ID within the project (the project ID follows the organization's fingerprint)."""
    state = Orchestrator(org, clock=clock).plan(text).state
    pid = state.project.id
    return {t.id.removeprefix(pid + ":"): json.loads(t.model_dump_json().replace(pid, "<project>"))
            for t in state.tasks.values()}


@pytest.mark.parametrize("request_text", [*(r for r in REQUESTS if "verify" not in r.lower()),
                                          *NOT_BLOCK_VERIFICATION])
def test_every_other_request_plans_exactly_as_before(request_text, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert "block-verification" not in engine.state.project.workflows
    assert _plan(_pre_m68_org(), request_text, fixed_clock) == _plan(nirmaan_org, request_text, fixed_clock)


# --- The gates, for real, through the eval harness ---------------------------------------------------------

#: The counter with its wrap broken: after a wrap the count restarts at 1, not 0.
MUTANT = (REPO / COUNTER).read_text(encoding="utf-8").replace(
    "        else if (wrap)\n            count <= 4'd0;", "        else if (wrap)\n            count <= 4'd1;")

#: A property file of the seat's own: after a wrap the count is back at 0, and a wrap is reached.
CHECKER = """\
`timescale 1ns / 1ps
module counter_check (input wire clk, input wire rst, input wire en);
    wire [3:0] count;
    wire wrap;
    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));
    reg seen_reset = 1'b0;
    reg wrapped = 1'b0;
    always @(posedge clk) begin
        if (rst)
            seen_reset <= 1'b1;
        wrapped <= wrap && !rst;
        if (seen_reset && wrapped)
            assert (count == 4'd0);
    end
    always @(posedge clk)
        if (seen_reset && !rst)
            cover (wrap);
endmodule
"""

#: The seat's proof setup: it names the RTL by its file name, as the approved file is placed beside it.
CHECKER_SBY = """\
[options]
mode prove
depth 20

[engines]
smtbmc

[script]
read -formal counter.v counter_check.sv
prep -top counter_check

[files]
counter.v
counter_check.sv
"""


def _case(tmp_path: Path, seat: str, reference: list[dict], held_out: list[dict]) -> Path:
    assert MUTANT != (REPO / COUNTER).read_text(encoding="utf-8")
    mutant = tmp_path / "mutants" / "counter.v"
    mutant.parent.mkdir(parents=True, exist_ok=True)
    mutant.write_text(MUTANT, encoding="utf-8")
    for check in held_out:
        check["mutants"] = {COUNTER: [str(mutant)]}
    data = {"id": f"tmp/block-verification-{seat}", "request": "Verify the existing 4-bit wrapping counter RTL.",
            "seat": seat, "expected_behavior": "The seat's own checks pass on the approved RTL and fail the mutant.",
            "upstream": {"interface-spec": [{"path": SPEC, "kind": "interface_spec"}],
                         "design-under-test": [{"path": COUNTER, "kind": "rtl_source", "entry": "counter"}]},
            "reference": reference, "held_out": held_out}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / "seat-reference" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


@needs(*GATE_TOOLS)
def test_a_testbench_seat_passes_its_gate_on_the_approved_rtl_and_fails_the_mutant(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    case = load_case(_case(tmp_path, "testbench",
                           [{"path": COUNTER_TB, "kind": "testbench", "entry": "counter_tb"}],
                           [{"name": "The seat's testbench fails the mutant", "scorer": "must-fail",
                             "tool": "simulator.run", "seat_files": {"sources": ["testbench"]},
                             "seat_entries": {"top": ["testbench"]}, "case_files": {"sources": [COUNTER]}}]))
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores


@needs(*FORMAL_TOOLS)
def test_a_proof_seat_passes_its_gates_over_the_approved_rtl_placed_beside_it(nirmaan_org, fixed_clock, tmp_path):
    reference = [{"path": _write(tmp_path, "counter_check.sv", CHECKER), "kind": "assertions"},
                 {"path": _write(tmp_path, "counter_check.sby", CHECKER_SBY), "kind": "formal_spec"}]
    case = load_case(_case(tmp_path, "assertions-formal", reference,
                           [{"name": "The seat's proof fails the mutant", "scorer": "must-fail", "tool": "formal.run",
                             "cover_tool": "formal.cover",
                             "seat_files": {"sby": ["formal_spec"], "sources": ["assertions"]},
                             "case_files": {"sources": [COUNTER]}}]))
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores


@needs(*FORMAL_TOOLS)
def test_a_seat_file_named_like_the_approved_rtl_is_not_replaced_and_the_proof_is_refused(nirmaan_org,
                                                                                          fixed_clock, tmp_path):
    """The seat ships its own counter.v (the mutant): the link is not made, and the proof did not read the RTL."""
    reference = [{"path": _write(tmp_path, "counter_check.sv", CHECKER), "kind": "assertions"},
                 {"path": _write(tmp_path, "counter.v", (REPO / COUNTER).read_text(encoding="utf-8")),
                  "kind": "assertions"},
                 {"path": _write(tmp_path, "counter_check.sby", CHECKER_SBY), "kind": "formal_spec"}]
    case = load_case(_case(tmp_path, "assertions-formal", reference, []))
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert not result.submitted, result
    assert "does not read counter.v" in result.detail, result.detail


# --- The equivalence gate, for real (M69) ------------------------------------------------------------------

REFACTOR = "tests/fixtures/eqy/counter_refactor.v"
#: The seat's setup: it names both approved versions by file name, as they are placed beside it.
EQUIVALENCE_EQY = """\
[gold]
read_verilog -sv counter.v
prep -top counter

[gate]
read_verilog -sv counter_refactor.v
prep -top counter

[strategy sby]
use sby
engine smtbmc
depth 10
"""


@needs(*FORMAL_TOOLS, "eqy", "make")
def test_an_equivalence_seat_passes_its_gate_on_the_approved_versions_and_fails_the_mutant(nirmaan_org,
                                                                                          fixed_clock, tmp_path):
    """The approved counter and its refactor are equivalent under the seat's setup; a refactor that wraps one
    count early (tests/fixtures/eqy/counter_wraps_early.v) must fail it."""
    mutant = tmp_path / "mutants" / "counter_refactor.v"
    mutant.parent.mkdir(parents=True)
    shutil.copy(REPO / "tests/fixtures/eqy/counter_wraps_early.v", mutant)
    data = {"id": "tmp/block-verification-equivalence",
            "request": "Verify the existing 4-bit counter RTL with an equivalence check of its refactor.",
            "seat": "equivalence", "expected_behavior": "The seat's setup proves the approved versions equivalent "
                                                       "and fails a refactor that changes behaviour.",
            "upstream": {"interface-spec": [{"path": SPEC, "kind": "interface_spec"}],
                         "design-under-test": [{"path": COUNTER, "kind": "rtl_source", "entry": "counter"},
                                               {"path": REFACTOR, "kind": "rtl_source", "entry": "counter"}]},
            "reference": [{"path": _write(tmp_path, "counter.eqy", EQUIVALENCE_EQY), "kind": "equivalence_setup"}],
            "held_out": [{"name": "The seat's setup fails the non-equivalent refactor", "scorer": "must-fail",
                          "tool": "equivalence.run", "seat_files": {"eqy": ["equivalence_setup"]},
                          "case_files": {"sources": [COUNTER, REFACTOR]}, "mutants": {REFACTOR: [str(mutant)]}}]}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    case = load_case(path)
    assert validate_case(nirmaan_org, case, REPO) == []
    result = run_case(nirmaan_org, case, repo=REPO, sandbox=tmp_path / "sandbox", clock=fixed_clock)
    assert result.submitted, result
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED], result.scores
