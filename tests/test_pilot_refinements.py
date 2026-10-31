"""The RTL pilot's skills reach the block-design RTL seat's packet (M66).

M65 refines block-design's one RTL task with ``arbitration`` on an arbiter. M66
does the same for the pilot's other blocks and bus interfaces: ``apb``, ``axi``,
a FIFO (``buffering_flow_control``), a skid buffer or register slice
(``pipeline_design`` and ``buffering_flow_control``), a timer (``fsm_design``)
and GPIO (``control_logic_design``). Timer, GPIO and skid-buffer requests now
plan block-design. Every request that is not one of these blocks plans exactly
as before, and on these blocks only the RTL task changes.
"""

from __future__ import annotations

import json
from functools import cache

import pytest

from test_nirmaan_applicability_golden import REQUESTS

from nirmaan.company import builder
from nirmaan.evals import load_cases
from nirmaan.org import knowledge
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import assemble

RTL = "rtl-implementation"
M66_FEATURES = ("apb", "axi", "fifo", "register_slice", "timer", "gpio")
NEW_FEATURES = ("fifo", "timer", "gpio", "register_slice")

INTERCONNECT = "design.rtl.design.interconnect.senior"
INTERFACE = "design.rtl.interface.senior"
PIPELINE = "design.rtl.design.pipeline.senior"
DESIGN_LEAD = "design.rtl.design.tech_lead"
INTERFACE_LEAD = "design.rtl.interface.tech_lead"

#: Each existing RTL eval case's request: its RTL task's skills, owner and reviewer.
CASES = {
    "rtl/rr-arbiter": (("arbitration",), INTERCONNECT, DESIGN_LEAD),
    "rtl/sync-fifo": (("buffering_flow_control",), INTERCONNECT, DESIGN_LEAD),
    "rtl/apb-regs": (("apb",), INTERFACE, INTERFACE_LEAD),
    "rtl/axi4-lite-regs": (("axi",), INTERFACE, INTERFACE_LEAD),
}

#: Requests the pilot's new cases will make; before M66 the first three matched no intent.
BLOCKS = {
    "Create an AXI4-Lite timer peripheral with an interrupt.": (("axi", "fsm_design"), INTERFACE, INTERFACE_LEAD),
    "Create an APB GPIO peripheral with interrupts.": (("apb", "control_logic_design"), INTERFACE, INTERFACE_LEAD),
    "Create a skid buffer with valid/ready handshakes.":
        (("pipeline_design", "buffering_flow_control"), PIPELINE, DESIGN_LEAD),
    "Create a register slice for a valid/ready stream.":
        (("pipeline_design", "buffering_flow_control"), PIPELINE, DESIGN_LEAD),
}

#: Requests that name a new feature but are not one of the blocks: they must plan as before.
NOT_BLOCKS = (
    "Design a low-power PCIe controller with a watchdog timer and GPIO pins.",
    "Design a controller with a timer.",
    "Design a configurable 4-port AXI-to-NoC bridge with input FIFOs and a skid buffer.",
)

#: block_design's patterns before M66, for the baseline organization.
PRE_M66_BLOCK_PATTERNS = (
    r"\b(create|build|design|develop|implement|write)\b.*\b(register (block|file|bank)|fifo|arbiter|counter)\b",
    r"\b(create|build|design|develop|implement|write)\b.*\b(apb[34]?|axi4?[- ]?lite) (subordinate|slave|peripheral)\b",
)


def _rtl(engine):
    tasks = [t for t in engine.state.tasks.values() if t.stage == RTL]
    assert len(tasks) == 1, [t.id for t in tasks]
    return tasks[0]


@cache
def _pre_m66_org():
    """The organization with M66's data taken out: M65's refinement only, no new features or patterns."""
    b = builder()
    d = b.definition
    d.features = [f for f in d.features if f.feature not in NEW_FEATURES]
    d.intents = [i.model_copy(update={"patterns": PRE_M66_BLOCK_PATTERNS}) if i.intent == "block_design" else i
                 for i in d.intents]
    d.workflows = [
        wf.model_copy(update={"stages": tuple(
            s.model_copy(update={"refinements": _m65_only(s.refinements)}) if s.id == RTL else s
            for s in wf.stages)}) if wf.id == "block-design" else wf
        for wf in d.workflows
    ]
    return b.build()


def _m65_only(refinements):
    kept = refinements[:1]
    assert [r.skills for r in kept] == [("arbitration",)]
    return kept


def _check(engine, skills, owner, reviewer):
    rtl = _rtl(engine)
    assert rtl.workflow == "block-design" and rtl.id.endswith(":" + RTL)
    assert (rtl.skills, rtl.owner, rtl.reviewer) == (skills, owner, reviewer)
    for seat in (rtl.owner, rtl.reviewer):
        packet = assemble(engine, rtl.id, role=seat)
        held = [s.id for s in packet.domain.skills]
        assert set(skills) | {"rtl_design"} <= set(held), (seat, held)
        assert packet.domain.declines is None
    return rtl


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_each_rtl_eval_case_seat_carries_its_skills(case_id, nirmaan_org, fixed_clock):
    case = next(c for c in load_cases(knowledge.KNOWLEDGE_ROOT.parent / "evals") if c.id == case_id)
    assert case.seat == RTL
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    rtl = _check(engine, *CASES[case_id])
    # Every skill the case is judged on reaches the seat it judges.
    assert set(case.skills) <= {s.id for s in assemble(engine, rtl.id).domain.skills}


@pytest.mark.parametrize("request_text", sorted(BLOCKS))
def test_timer_gpio_and_skid_buffer_requests_plan_block_design(request_text, nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    assert engine.state.project.analysis.intent == "block_design"
    _check(engine, *BLOCKS[request_text])


def test_a_block_with_several_features_carries_every_skill_within_the_domain_cap(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(
        "Create an AXI4-Lite timer peripheral with a FIFO and an APB GPIO.")
    rtl = _rtl(engine)
    assert rtl.skills == ("apb", "axi", "buffering_flow_control", "fsm_design", "control_logic_design")
    for seat in (rtl.owner, rtl.reviewer):
        assert assemble(engine, rtl.id, role=seat).domain.declines is None


def _plan(org, text, clock):
    """Every task, keyed by its ID within the project (the project ID follows the organization's fingerprint)."""
    state = Orchestrator(org, clock=clock).plan(text).state
    pid = state.project.id
    return {t.id.removeprefix(pid + ":"): json.loads(t.model_dump_json().replace(pid, "<project>"))
            for t in state.tasks.values()}


@pytest.mark.parametrize("request_text", [*(r for r in REQUESTS if r not in BLOCKS), *NOT_BLOCKS])
def test_only_the_rtl_task_of_a_pilot_block_changes(request_text, nirmaan_org, fixed_clock):
    before = _plan(_pre_m66_org(), request_text, fixed_clock)
    after = _plan(nirmaan_org, request_text, fixed_clock)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(request_text)
    features = set(engine.state.project.analysis.features)
    block = "block-design" in engine.state.project.workflows and features & set(M66_FEATURES)
    changed = sorted(t for t in after if after[t] != before.get(t)) + sorted(set(before) - set(after))
    if not block:
        assert changed == [], (request_text, changed)
    else:
        # The RTL task gains its block's skills and may route to a seat holding them; then the RTL phase's
        # workstream follows its one task's unit (the FIFO's). Nothing else moves.
        assert set(changed) <= {RTL, "ws.rtl"}, (request_text, changed)
        assert "ws.rtl" not in changed or after[RTL]["unit"] != before[RTL]["unit"], request_text
