"""A refinement adds skills to a stage's one task when a feature holds, with no fan-out (M65).

A variant makes a task of its own per feature (``rtl-implementation.arbitration``
on ``new-ip``). A block is one task: the arbiter's RTL stage on ``block-design``
stays ``rtl-implementation`` and carries ``arbitration``, so the skill routes
the task and enters its seat's work packet. A request without the feature plans
exactly as before.
"""

from __future__ import annotations

import pytest

from nirmaan.company import builder
from nirmaan.models import Refinement
from nirmaan.models.workflow import Condition
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import OrganizationError
from nirmaan.runtime import assemble

ARBITER = "Create a round-robin arbiter for four requesters."
FIFO = "Create a parameterizable synchronous FIFO."
COUNTER = "Create a 4-bit wrapping counter."


def _stage_task(engine, stage: str):
    tasks = [t for t in engine.state.tasks.values() if t.stage == stage]
    assert len(tasks) == 1, [t.id for t in tasks]
    return tasks[0]


def _org_refining(stage_id: str, refinement: Refinement, workflow: str = "block-design"):
    b = builder()
    b.definition.workflows = [
        wf.model_copy(update={"stages": tuple(
            s.model_copy(update={"refinements": (*s.refinements, refinement)}) if s.id == stage_id else s
            for s in wf.stages)}) if wf.id == workflow else wf
        for wf in b.definition.workflows
    ]
    return b.build()


def test_the_arbiter_rtl_task_carries_arbitration_with_no_fan_out(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(ARBITER)
    rtl = _stage_task(engine, "rtl-implementation")
    assert rtl.workflow == "block-design" and rtl.id.endswith(":rtl-implementation")
    assert rtl.skills == ("arbitration",)
    # The skill routes the task: its owner holds arbitration.
    assert "arbitration" in nirmaan_org.agent_card(rtl.owner)["skills"]
    # And enters the owner's work packet.
    packet = assemble(engine, rtl.id)
    assert "arbitration" in [s.id for s in packet.domain.skills]


def test_a_block_without_the_feature_plans_as_before(nirmaan_org, fixed_clock):
    # A counter: no refinement holds (M66 refines the FIFO's RTL task, tests/test_pilot_refinements.py).
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(COUNTER)
    rtl = _stage_task(engine, "rtl-implementation")
    assert rtl.skills == ()
    assert "arbitration" not in [s.id for s in assemble(engine, rtl.id).domain.skills]


def test_a_new_refinement_is_data_alone(fixed_clock):
    # Crown jewel: a refinement written into a workflow needs no core change to reach its task.
    org = _org_refining("microarchitecture", Refinement(when=Condition(any_of=("arbitration",)),
                                                        skills=("qos_architecture",)))
    arbiter = _stage_task(Orchestrator(org, clock=fixed_clock).plan(ARBITER), "microarchitecture")
    assert "qos_architecture" in arbiter.skills
    fifo = _stage_task(Orchestrator(org, clock=fixed_clock).plan(FIFO), "microarchitecture")
    assert "qos_architecture" not in fifo.skills


@pytest.mark.parametrize("refinement, expected", [
    (Refinement(when=Condition(any_of=("arbitration",)), skills=("no_such_skill",)), "unknown skill no_such_skill"),
    (Refinement(when=Condition(any_of=("no_such_feature",)), skills=("arbitration",)), "no_such_feature"),
    (Refinement(when=Condition(on="produced", any_of=("rtl_source",)), skills=("arbitration",)), "produced"),
])
def test_a_bad_refinement_fails_validation(refinement, expected):
    with pytest.raises(OrganizationError, match=expected):
        _org_refining("rtl-implementation", refinement)
