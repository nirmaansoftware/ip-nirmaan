"""The engineering trace graph: requirement to evidence, as typed edges.

A projection of project state, never a second store. It deliberately does not
extend the VeriTriage Evidence Graph: that graph is what happened in one
verification run, this one is what the organization did about a requirement.
They meet at VERITRIAGE_SESSION evidence, whose reference is a VeriTriage
session ID, so a claim here can be followed into the Evidence Graph there.
"""

from __future__ import annotations

from enum import Enum

from nirmaan.models import ProjectState, TaskKind


class TraceRelation(str, Enum):
    DECOMPOSES = "decomposes"  # requirement/program/workstream -> task
    DEPENDS_ON = "depends_on"
    OWNED_BY = "owned_by"
    REVIEWED_BY = "reviewed_by"
    PRODUCES = "produces"  # task -> artifact
    DERIVED_FROM = "derived_from"  # artifact -> upstream artifact
    SUPPORTED_BY = "supported_by"  # task -> evidence
    RECORDED_BY = "recorded_by"  # evidence -> tool run
    GATED_BY = "gated_by"
    DECIDED = "decided"  # task -> decision
    ESCALATED = "escalated"  # task -> escalation
    VERIFIED_IN = "verified_in"  # evidence -> external VeriTriage session


def trace_graph(state: ProjectState) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid: str, kind: str, label: str, **attrs) -> None:
        nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, **attrs})

    def edge(src: str, rel: TraceRelation, dst: str) -> None:
        edges.append({"from": src, "relation": rel.value, "to": dst})

    req = state.project.requirement
    node(req.id, "requirement", req.text)
    for task in state.tasks.values():
        node(task.id, f"task:{task.kind.value}", task.title, status=task.status.value)
        parent = task.parent or (req.id if task.kind is TaskKind.PROGRAM else None)
        if parent:
            edge(parent, TraceRelation.DECOMPOSES, task.id)
        for dep in task.depends_on:
            edge(task.id, TraceRelation.GATED_BY if state.tasks[dep].kind is TaskKind.GATE
                 else TraceRelation.DEPENDS_ON, dep)
        if task.owner:
            node(f"role:{task.owner}", "role", task.owner)
            edge(task.id, TraceRelation.OWNED_BY, f"role:{task.owner}")
        if task.reviewer:
            node(f"role:{task.reviewer}", "role", task.reviewer)
            edge(task.id, TraceRelation.REVIEWED_BY, f"role:{task.reviewer}")
        for ev in task.evidence:
            edge(task.id, TraceRelation.SUPPORTED_BY, ev)
    for art in state.artifacts.values():
        node(art.id, "artifact", art.title, assurance=art.assurance.value, produced_by=art.produced_by)
        edge(art.task, TraceRelation.PRODUCES, art.id)
        for up in art.derived_from:
            edge(art.id, TraceRelation.DERIVED_FROM, up)
    for ev in state.evidence.values():
        node(ev.id, "evidence", ev.description, evidence_kind=ev.kind.value, substantiated=ev.substantiated)
        if ev.tool_run:
            run = state.tool_runs.get(ev.tool_run)
            node(ev.tool_run, "tool_run", run.summary if run else ev.tool_run, tool=run.tool if run else None)
            edge(ev.id, TraceRelation.RECORDED_BY, ev.tool_run)
        if ev.kind.value == "veritriage_session" and ev.reference:
            node(f"veritriage:{ev.reference}", "veritriage_session", ev.reference)
            edge(ev.id, TraceRelation.VERIFIED_IN, f"veritriage:{ev.reference}")
    for dec in state.decisions.values():
        node(dec.id, "decision", dec.statement, decision_kind=dec.kind.value)
        if dec.task:
            edge(dec.task, TraceRelation.DECIDED, dec.id)
        for ev in dec.evidence:
            edge(dec.id, TraceRelation.SUPPORTED_BY, ev)
    for esc in state.escalations.values():
        node(esc.id, "escalation", esc.reason, state=esc.state.value, target=esc.target_role)
        if esc.task:
            edge(esc.task, TraceRelation.ESCALATED, esc.id)
    return {"nodes": list(nodes.values()), "edges": edges}


def untraced_requirements(state: ProjectState) -> list[str]:
    """Work tasks whose completion is not backed by substantiated evidence."""
    problems = []
    for task in state.tasks.values():
        if task.kind is TaskKind.WORK and task.status.value == "completed":
            if not any(state.evidence[e].substantiated for e in task.evidence if e in state.evidence):
                problems.append(task.id)
    return problems
