"""Wave 2: the five-department cut of Verification (capability build-out council record, section 4).

Verification had eight teams directly under its VP. It now has five departments: Methodology and Signoff,
Simulation, Formal and Static, Debug and Regression, and Processor and Accelerator. Every unit that existed is
moved, not rebuilt: each keeps its skills, tools, noun and ladder, so every role keeps what it holds. Two practices
become teams (equivalence, triage) and the regression practice joins Debug and Regression as a team. The new areas
enter as placeholders with a mission. The span and depth rules hold with zero exceptions.

The cut changes role IDs, so the proof that nothing else moved plans every representative request on the chart
before the cut (``PRE_CUT``, frozen below) and on the shipped chart, maps the old IDs to the new ones, and checks
that the plans are equal except for the changes listed in ``INTENDED``. Each of those follows from the new
structure: a department director now sits between a team manager and the VP, and a promoted team has its own
tech lead and manager.
"""

from __future__ import annotations

import json
import re
from functools import cache

import pytest

from test_block_verification import EVERYTHING, NOT_BLOCK_VERIFICATION, PLAIN, RANDOM, SV, UNBOUNDED
from test_nirmaan_applicability_golden import REQUESTS
from test_org_span import ACTIVE_AT_M60

from nirmaan.company import builder, org_chart
from nirmaan.company.org_chart import ARCH_LADDER, Function, Level, dept, div, prac, team
from nirmaan.models import UnitKind, UnitStatus
from nirmaan.orchestrator import Orchestrator

#: Verification as it was before the cut (main at 5ed483b), kept here as data so the plans can be compared.
PRE_CUT = div(
    "verification", "Verification",
    team("architecture", "Verification Architecture", noun="Verification Architect",
         skills=("verification_architecture",), ladder=ARCH_LADDER),
    team("planning", "Verification Planning", noun="Verification Planning Engineer",
         skills=("verification_planning",)),
    team("simulation", "Simulation",
         prac("systemverilog", "SystemVerilog", "SystemVerilog Verification Engineer", "directed_testing"),
         prac("uvm", "UVM", "UVM Verification Engineer", "uvm", "constrained_random"),
         prac("testbench", "Testbench", "Testbench Engineer", "uvm", "constrained_random", "directed_testing"),
         prac("vip", "VIP", "VIP Engineer", "vip_integration", "axi", "chi", "pcie"),
         prac("regression", "Regression", "Regression Engineer", "regression_management"),
         skills=("uvm", "sva")),
    team("formal", "Formal Verification",
         prac("property", "Property Verification", "Formal Verification Engineer", "formal_verification"),
         prac("model_checking", "Model Checking", "Model Checking Engineer", "model_checking"),
         prac("equivalence", "Equivalence", "Equivalence Engineer", "equivalence_checking"),
         prac("coverage", "Formal Coverage", "Formal Coverage Engineer", "formal_coverage")),
    team("coverage", "Coverage",
         prac("code", "Code Coverage", "Code Coverage Engineer", "code_coverage"),
         prac("functional", "Functional Coverage", "Functional Coverage Engineer", "functional_coverage"),
         prac("assertion", "Assertion Coverage", "Assertion Coverage Engineer", "assertion_coverage", "sva")),
    team("debug", "Debug",
         prac("logs", "Log Analysis", "Log Analysis Engineer", "log_analysis"),
         prac("waveforms", "Waveform Analysis", "Waveform Debug Engineer", "waveform_debug"),
         prac("triage", "Failure Triage", "Failure Triage Engineer", "failure_triage"),
         prac("root_cause", "Root Cause", "Root Cause Engineer", "root_cause_analysis"),
         prac("intelligence", "Regression Intelligence", "Regression Intelligence Engineer", "regression_intelligence"),
         skills=("debugging", "root_cause_analysis"), tools=("veritriage.investigate", "veritriage.explain_log")),
    team("cdc", "CDC / RDC Verification", noun="CDC Verification Engineer", skills=("cdc_verification",)),
    team("signoff", "Verification Signoff", noun="Verification Signoff Engineer",
         skills=("verification_signoff", "functional_coverage"), ladder=(Level.STAFF, Level.SENIOR)),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=("git", "linux", "debugging", "systemverilog", "verification_signoff"),
    tools=("git.read", "code.search", "veritriage.investigate"),
    mission="Prove, with evidence, that the design does what the requirements say.",
)

#: Where each unit went. Role IDs follow: a role is its unit's ID plus its level.
MOVES = {
    "verification": "verification",
    "verification.architecture": "verification.methodology.architecture",
    "verification.planning": "verification.methodology.planning",
    "verification.signoff": "verification.methodology.signoff",
    "verification.simulation": "verification.dynamic.testbench",
    "verification.simulation.systemverilog": "verification.dynamic.testbench.systemverilog",
    "verification.simulation.uvm": "verification.dynamic.testbench.uvm",
    "verification.simulation.testbench": "verification.dynamic.testbench.testing",
    "verification.simulation.vip": "verification.dynamic.testbench.vip",
    "verification.simulation.regression": "verification.debug.regression",
    "verification.coverage": "verification.dynamic.coverage",
    "verification.coverage.code": "verification.dynamic.coverage.code",
    "verification.coverage.functional": "verification.dynamic.coverage.functional",
    "verification.coverage.assertion": "verification.dynamic.coverage.assertion",
    "verification.formal": "verification.formal.proof",
    "verification.formal.property": "verification.formal.proof.property",
    "verification.formal.model_checking": "verification.formal.proof.model_checking",
    "verification.formal.coverage": "verification.formal.proof.coverage",
    "verification.formal.equivalence": "verification.formal.equivalence",
    "verification.cdc": "verification.formal.cdc",
    "verification.debug": "verification.debug.analysis",
    "verification.debug.logs": "verification.debug.analysis.logs",
    "verification.debug.waveforms": "verification.debug.analysis.waveforms",
    "verification.debug.root_cause": "verification.debug.analysis.root_cause",
    "verification.debug.intelligence": "verification.debug.analysis.intelligence",
    "verification.debug.triage": "verification.debug.triage",
}

#: Practices that became teams, each with its own tech lead and manager now, and the team they left.
PROMOTED = {
    "verification.formal.equivalence": "verification.formal.proof",
    "verification.debug.triage": "verification.debug.analysis",
    "verification.debug.regression": "verification.dynamic.testbench",
}

#: Units whose name changed with the move (the title of a team's manager and tech lead follows its name).
RENAMED = {
    "verification.dynamic.testbench": ("Simulation", "Testbench"),
    "verification.dynamic.testbench.testing": ("Testbench", "Directed and Random Testing"),
    "verification.formal.proof": ("Formal Verification", "Formal Proof"),
    "verification.formal.equivalence": ("Equivalence", "Equivalence Checking"),
    "verification.debug.analysis": ("Debug", "Debug Analysis"),
}

#: The regression practice left the Simulation team, whose own skills it no longer inherits.
LEFT_SIMULATION = {"verification.debug.regression": {"uvm", "sva"}}

DEPARTMENTS = {
    "verification.methodology": ["architecture", "planning", "signoff"],
    "verification.dynamic": ["testbench", "coverage", "gate_level_power", "emulation"],
    "verification.formal": ["proof", "equivalence", "cdc"],
    "verification.debug": ["analysis", "triage", "regression"],
    "verification.processor": ["isa", "models", "accelerator"],
}

PLACEHOLDERS = (
    "verification.dynamic.gate_level_power", "verification.dynamic.emulation", "verification.processor",
    "verification.processor.isa", "verification.processor.models", "verification.processor.accelerator",
)

#: Every task-level change the cut makes to a plan, as (task, field, before, after) over all the requests below.
INTENDED = {
    # The regression team has its own tech lead, who reviews and approves its work.
    *{(task, field, "verification.dynamic.testbench.tech_lead", "verification.debug.regression.tech_lead")
      for task in ("regression", "verify-fix") for field in ("reviewer", "approver")},
    # A work stream is led by the head of the narrowest unit holding all its tasks: regression work is now the
    # Regression team's, and work spanning regression and other verification teams is the VP's.
    ("ws.verification", "owner", "verification.dynamic.testbench.manager", "verification.debug.regression.manager"),
    ("ws.verification", "unit", "verification.dynamic.testbench", "verification.debug.regression"),
    ("ws.verification", "owner", "verification.dynamic.testbench.manager", "verification.vp"),
    ("ws.verification", "unit", "verification.dynamic.testbench", "verification"),
    # Proof and equivalence work now spans two Formal and Static teams, so their director leads it.
    ("ws.formal", "owner", "verification.formal.proof.manager", "verification.formal.director"),
    ("ws.formal", "unit", "verification.formal.proof", "verification.formal"),
    ("equivalence", "approver", "verification.formal.proof.tech_lead", "verification.formal.equivalence.tech_lead"),
    # The coverage gate goes to the first approver in the coverage owner's chain: now the Simulation director.
    *{("coverage.gate", field, "verification.vp", "verification.dynamic.director") for field in ("owner", "approver")},
    ("coverage.gate", "unit", "verification", "verification.dynamic"),
}

BLOCK_VERIFICATION = (PLAIN, SV, RANDOM, UNBOUNDED, EVERYTHING)
ALL_REQUESTS = tuple(dict.fromkeys((*REQUESTS, *NOT_BLOCK_VERIFICATION, *BLOCK_VERIFICATION)))

_ID = re.compile(r"verification(?:\.[a-z_]+)+")


def _moved(match: re.Match) -> str:
    token = match.group(0)
    if token in MOVES:
        return MOVES[token]
    unit, _, level = token.rpartition(".")
    return f"{MOVES[unit]}.{level}" if unit in MOVES else token


def _new_id(old: str) -> str:
    return _ID.sub(_moved, old)


@cache
def _pre_cut_org():
    b = builder()
    d = b.definition
    at = next(i for i, u in enumerate(d.units) if u.id == "verification")
    rest = [u for u in d.units if u.id != "verification" and not u.id.startswith("verification.")]
    old = org_chart._flatten(dict(PRE_CUT, children=[dict(c) for c in PRE_CUT["children"]]), org_chart.ROOT)
    d.units = rest[:at] + old + rest[at:]
    return b.build()


def _plan(org, text, clock, remap: bool):
    """Every task, keyed by its ID within the project, with old role and unit IDs mapped when asked."""
    state = Orchestrator(org, clock=clock).plan(text).state
    pid = state.project.id
    tasks = {}
    for t in state.tasks.values():
        dump = t.model_dump_json().replace(pid, "<project>")
        tasks[t.id.removeprefix(pid + ":")] = json.loads(_ID.sub(_moved, dump) if remap else dump)
    return tasks


# --- The shape --------------------------------------------------------------------------------------------


def test_verification_has_five_departments(nirmaan_org):
    assert {u.id: [c.id.rsplit(".", 1)[1] for c in nirmaan_org.children(u.id)]
            for u in nirmaan_org.children("verification")} == DEPARTMENTS
    for unit in DEPARTMENTS:
        assert nirmaan_org.units[unit].kind is UnitKind.DEPARTMENT
        director = nirmaan_org.head_of(unit)
        assert (director.id, director.level, director.reports_to) == (f"{unit}.director", Level.DIRECTOR,
                                                                        "verification.vp")
    assert nirmaan_org.roles["verification.dynamic.director"].title == "Director, Simulation"


def test_the_vp_spans_five_and_each_department_three_or_four(nirmaan_org):
    spans = {u: len(nirmaan_org.children(u)) for u in ("verification", *DEPARTMENTS)}
    assert spans == {"verification": 5, "verification.methodology": 3, "verification.dynamic": 4,
                     "verification.formal": 3, "verification.debug": 3, "verification.processor": 3}


def test_the_deepest_verification_role_is_six_layers_below_the_board(nirmaan_org):
    # Board, CEO, CTO, VP, director, manager, ICs: the department adds no layer past the rule's six.
    depth = max(len(nirmaan_org.line_chain(r.id)) for r in nirmaan_org.roles_in("verification"))
    assert depth == 6
    chain = [r.id for r in nirmaan_org.line_chain("verification.formal.proof.property.engineer")]
    assert chain == ["verification.formal.proof.manager", "verification.formal.director", "verification.vp",
                     "exec.cto", "exec.ceo", "exec.board"]


@pytest.mark.parametrize("unit", PLACEHOLDERS)
def test_new_verification_areas_enter_as_placeholders(nirmaan_org, unit):
    u = nirmaan_org.units[unit]
    assert u.status is UnitStatus.PLACEHOLDER and u.mission and not u.skills
    assert not any(nirmaan_org.is_active(r.id) for r in nirmaan_org.roles_in(unit))


def test_every_moved_unit_keeps_its_skills_tools_and_ladder(nirmaan_org):
    old = _pre_cut_org()
    names = {new: (old.units[o].name, nirmaan_org.units[new].name) for o, new in MOVES.items()}
    assert {u: n for u, n in names.items() if n[0] != n[1]} == RENAMED
    for old_unit, new_unit in MOVES.items():
        before = {_new_id(r.id): r for r in old.roles_in(old_unit, recursive=False)}
        after = {r.id: r for r in nirmaan_org.roles_in(new_unit, recursive=False)}
        if new_unit in PROMOTED:
            # A promoted team gains its manager and tech lead; nothing it had is lost.
            assert set(after) - set(before) == {f"{new_unit}.manager", f"{new_unit}.tech_lead"}, new_unit
            after = {k: v for k, v in after.items() if k in before}
        elif old_unit == "verification":
            after = {k: v for k, v in after.items() if k in before}
        assert set(after) == set(before), new_unit
        dropped = LEFT_SIMULATION.get(new_unit, set())
        for rid, role in before.items():
            mine = after[rid]
            assert mine.level == role.level, rid
            if role.level not in (Level.MANAGER, Level.TECH_LEAD):
                assert mine.title == role.title, rid
            assert set(nirmaan_org.effective_skills(rid)) == set(old.effective_skills(role.id)) - dropped, rid
            assert set(mine.tools) == set(role.tools), rid


def test_the_frozen_active_list_moved_with_the_units(nirmaan_org):
    old = _pre_cut_org()
    was_active = {u.id for u in old.subtree("verification") if u.status is UnitStatus.ACTIVE}
    listed = {u for u in ACTIVE_AT_M60 if u == "verification" or u.startswith("verification.")}
    active_departments = {u for u in DEPARTMENTS if nirmaan_org.units[u].status is UnitStatus.ACTIVE}
    assert active_departments == set(DEPARTMENTS) - {"verification.processor"}
    assert listed == {MOVES[u] for u in was_active} | active_departments


# --- Nothing else moves -------------------------------------------------------------------------------------


@pytest.mark.parametrize("request_text", ALL_REQUESTS)
def test_every_request_plans_as_before_but_for_the_cut(request_text, nirmaan_org, fixed_clock):
    before = _plan(_pre_cut_org(), request_text, fixed_clock, remap=True)
    after = _plan(nirmaan_org, request_text, fixed_clock, remap=False)
    assert set(before) == set(after)
    for key, old in before.items():
        new = after[key]
        changed = {(key, f, old[f], new[f]) for f in ("owner", "reviewer", "approver", "unit") if old[f] != new[f]}
        assert changed <= INTENDED, changed
        if old["owner"] == new["owner"]:
            # A department director joins the escalation path between a team manager and the VP, and a promoted
            # team's own lead and manager take the place of those of the team it left.
            path = [r for r in new["escalation_path"] if not (r.startswith("verification.") and r.endswith(".director"))]
            assert len(new["escalation_path"]) - len(path) <= 1, key
            unit = next((p for p in PROMOTED if new["owner"].startswith(p + ".")), None)
            if unit:
                heads = {f"{unit}.{level}": f"{PROMOTED[unit]}.{level}" for level in ("tech_lead", "manager")}
                path = [heads.get(r, r) for r in path]
            assert path == old["escalation_path"], key
        skip = {"owner", "reviewer", "approver", "unit", "escalation_path", "owner_routing", "reviewer_routing"}
        assert {k: v for k, v in new.items() if k not in skip} == {k: v for k, v in old.items() if k not in skip}, key
        for routing in ("owner_routing", "reviewer_routing"):
            if old.get(routing) is not None:
                assert old[routing]["chosen"] == old[routing.split("_")[0]], key
                assert new[routing]["chosen"] == new[routing.split("_")[0]], key


def test_each_intended_change_happens_somewhere(nirmaan_org, fixed_clock):
    seen = set()
    for text in ALL_REQUESTS:
        before = _plan(_pre_cut_org(), text, fixed_clock, remap=True)
        after = _plan(nirmaan_org, text, fixed_clock, remap=False)
        seen |= {(k, f, before[k][f], after[k][f]) for k in before
                 for f in ("owner", "reviewer", "approver", "unit") if before[k][f] != after[k][f]}
    assert seen == INTENDED
