"""M78: nobody approves, at a signoff gate, the evidence their own team or department produced.

Council record ``council/records/2026-11-14-g13-grouping-units.md``, decision 2c: the approver of a
``gate.verification`` task is never the head of the department whose unit produced the evidence. The rule is data
(``INDEPENDENT_GATES`` in ``src/nirmaan/company/governance.py``) read by the router. The approver is the first
holder of the gate's capability further up the producer's chain: the division's VP. The gate specs do not change.

The plan-equivalence test plans every representative request with the rule and without it and allows only the
changes in ``INTENDED``.
"""

from __future__ import annotations

from functools import cache

import pytest

from test_verification_departments import ALL_REQUESTS, _plan

from nirmaan.company import builder
from nirmaan.company.governance import INDEPENDENT_GATES
from nirmaan.models import Level, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.org.organization import OrganizationError

#: Every task-level change the rule makes, as (task, field, before, after) over all the requests.
INDEPENDENT_FROM = {
    # The coverage evidence comes from the Simulation department (its assertion coverage practice).
    "coverage.gate": ("verification.dynamic.director", "verification.vp", "verification.dynamic", "verification"),
}
INTENDED = {
    change
    for task, (before, after, unit_before, unit_after) in INDEPENDENT_FROM.items()
    for change in ((task, "owner", before, after), (task, "approver", before, after),
                   (task, "unit", unit_before, unit_after))
}


@cache
def _org(independent: tuple[str, ...] = INDEPENDENT_GATES):
    b = builder()
    b.definition.independent_gates = list(independent)
    return b.build()


def self_approvals(org, state) -> list[tuple[str, str, str]]:
    """(gate task, approver, producer) for every independent gate approved by a producer or one of its heads."""
    found = []
    for task in state.tasks.values():
        if task.gate not in org.independent_gates or not task.approver:
            continue
        for dep in task.depends_on:
            producer = state.tasks[dep].owner
            if producer and task.approver in org.own_heads(producer):
                found.append((task.id.rsplit(":", 1)[1], task.approver, producer))
    return found


def _state(org, text, clock):
    return Orchestrator(org, clock=clock).plan(text).state


# --- The rule -------------------------------------------------------------------------------------------------


def test_the_gates_themselves_are_unchanged(nirmaan_org):
    gate = nirmaan_org.gates["gate.verification"]
    assert (gate.approver_capability, gate.min_level, gate.human_required) == (
        "signoff.verification", Level.DIRECTOR, True)
    gate = nirmaan_org.gates["gate.implementation"]
    assert (gate.approver_capability, gate.min_level, gate.human_required) == (
        "signoff.implementation", Level.DIRECTOR, False)
    assert nirmaan_org.independent_gates == {"gate.verification"}


def test_own_heads_are_the_team_and_department_heads_not_the_vp(nirmaan_org):
    heads = nirmaan_org.own_heads("verification.dynamic.coverage.assertion.senior")
    assert heads == {"verification.dynamic.coverage.assertion.senior", "verification.dynamic.coverage.manager",
                     "verification.dynamic.director"}
    assert nirmaan_org.own_heads("verification.vp") == {"verification.vp"}


@pytest.mark.parametrize("request_text", ALL_REQUESTS)
def test_no_independent_gate_is_approved_by_its_producers_heads(request_text, nirmaan_org, fixed_clock):
    state = _state(nirmaan_org, request_text, fixed_clock)
    assert self_approvals(nirmaan_org, state) == []
    for task in state.tasks.values():
        if task.gate in nirmaan_org.independent_gates:
            assert task.approver and task.status is TaskStatus.PLANNED, task.id


def test_must_fail_the_producing_departments_head_approving_its_own_evidence(fixed_clock):
    # Without the rule (main before M78) the Simulation director approves the coverage its department produced:
    # the check catches it.
    off = _org(())
    caught = set()
    for text in ALL_REQUESTS:
        state = _state(off, text, fixed_clock)
        caught |= {(task, approver) for task, approver, _ in self_approvals(_org(INDEPENDENT_GATES), state)}
    assert caught == {(task, before) for task, (before, *_rest) in INDEPENDENT_FROM.items()}


def test_must_fail_a_gate_with_only_dependent_approvers_is_blocked_not_self_approved(fixed_clock):
    # Only the RTL department's own director holds signoff.rtl at the authority its gates need, so under the rule
    # the RTL gate has no approver: it is planned blocked, never routed back to the director.
    org = _org((*INDEPENDENT_GATES, "gate.rtl"))
    gates = [t for text in ALL_REQUESTS for t in _state(org, text, fixed_clock).tasks.values() if t.gate == "gate.rtl"]
    assert gates
    for task in gates:
        assert task.approver is None and task.status is TaskStatus.BLOCKED, task.id
        assert "no eligible gate approver" in task.blocked_reason


def test_an_unknown_independent_gate_is_reported():
    b = builder()
    b.definition.independent_gates = ["gate.nope"]
    with pytest.raises(OrganizationError, match="independent gate gate.nope: unknown gate"):
        b.build()


# --- Nothing else moves -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("request_text", ALL_REQUESTS)
def test_every_request_plans_as_before_but_for_the_gate_approvers(request_text, nirmaan_org, fixed_clock):
    before = _plan(_org(()), request_text, fixed_clock, remap=False)
    after = _plan(nirmaan_org, request_text, fixed_clock, remap=False)
    assert set(before) == set(after)
    for key, old in before.items():
        new = after[key]
        changed = {(key, f, old[f], new[f]) for f in ("owner", "reviewer", "approver", "unit") if old[f] != new[f]}
        assert changed <= INTENDED, changed
        skip = {"owner", "approver", "unit", "escalation_path", "owner_routing"} if changed else set()
        assert {k: v for k, v in new.items() if k not in skip} == {k: v for k, v in old.items() if k not in skip}, key


def test_each_intended_change_happens_somewhere(nirmaan_org, fixed_clock):
    seen = set()
    for text in ALL_REQUESTS:
        before = _plan(_org(()), text, fixed_clock, remap=False)
        after = _plan(nirmaan_org, text, fixed_clock, remap=False)
        seen |= {(k, f, before[k][f], after[k][f]) for k in before
                 for f in ("owner", "approver", "unit") if before[k][f] != after[k][f]}
    assert seen == INTENDED
