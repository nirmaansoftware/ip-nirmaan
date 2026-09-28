"""Plain-text views of the organization and of projects.

Deterministic strings, shared by the CLI, the docs, and the tests, so what an
engineer reads is exactly what the tests pin.
"""

from __future__ import annotations

from nirmaan.models import ProjectState, Task, TaskKind, UnitStatus
from nirmaan.org import Organization

_BRANCH, _LAST, _PIPE, _GAP = "├── ", "└── ", "│   ", "    "


def _title(org: Organization, role: str | None) -> str:
    if role is None:
        return "UNASSIGNED"
    r = org.roles.get(role)
    return f"{r.title} ({role})" if r else role


def plan_tree(org: Organization, state: ProjectState, detail: bool = False) -> list[str]:
    """The organization-driven execution plan, as a tree."""
    p = state.project
    a = p.analysis
    lines = [
        f"PROJECT: {p.name}  [{p.id}]",
        f"Requirement: {p.requirement.text}",
        f"Intent: {a.intent}   Workflow(s): {', '.join(p.workflows)}",
        f"Features: {', '.join(a.features) or '-'}",
    ]
    if a.parameters:
        lines.append("Parameters: " + ", ".join(f"{k}={v}" for k, v in a.parameters.items()))
    for assumption in a.assumptions:
        lines.append(f"Assumption [{assumption.id}]: {assumption.note}")
        lines.append(f"  Open question: {assumption.question}")
    lines.append("")
    program = next(t for t in state.tasks.values() if t.kind is TaskKind.PROGRAM)
    lines.append(f"PROGRAM MANAGER  {_title(org, program.owner)}  [{program.status.value}]")
    streams = [t for t in state.tasks.values() if t.parent == program.id]
    for i, ws in enumerate(streams):
        last = i == len(streams) - 1
        lines.append(f"{_LAST if last else _BRANCH}{ws.phase}  (lead: {_title(org, ws.owner)})")
        kids = [t for t in state.tasks.values() if t.parent == ws.id]
        for j, task in enumerate(kids):
            klast = j == len(kids) - 1
            prefix = (_GAP if last else _PIPE) + (_LAST if klast else _BRANCH)
            cont = (_GAP if last else _PIPE) + (_GAP if klast else _PIPE) + "  "
            lines.append(prefix + _task_line(org, task))
            if detail:
                lines += [cont + d for d in _task_details(org, state, task)]
    return lines


def _task_line(org: Organization, task: Task) -> str:
    tag = {TaskKind.GATE: "GATE ", TaskKind.DECISION: "DECISION "}.get(task.kind, "")
    human = " (human approval)" if task.human_required else ""
    return f"{tag}{task.title} [{task.status.value}]  owner: {_title(org, task.owner)}{human}"


def _task_details(org: Organization, state: ProjectState, task: Task) -> list[str]:
    out = []
    if task.reviewer or task.approver:
        out.append(f"reviewer: {_title(org, task.reviewer) if task.reviewer else '-'}   "
                   f"approver: {_title(org, task.approver) if task.approver else '-'}")
    if task.capability:
        out.append(f"capability: {task.capability}   criticality: {task.criticality.value}")
    if task.skills:
        out.append(f"skills: {', '.join(task.skills)}")
    if task.depends_on:
        out.append("depends on: " + ", ".join(state.tasks[d].title for d in task.depends_on))
    for req in task.evidence_requirements:
        out.append(f"evidence: {req.description} ({' | '.join(k.value for k in req.accepts)})")
    if task.outcomes:
        out.append(f"outcomes: {', '.join(task.outcomes)}")
    if task.branch:
        out.append(f"branch: runs if {state.tasks[task.branch[0]].title} = {task.branch[1]}")
    if task.escalation_path:
        out.append("escalation: " + " -> ".join(task.escalation_path[:5]))
    if task.risk:
        out.append(f"risk: {task.risk}")
    if task.owner_routing:
        out.append(f"why this owner: {task.owner_routing.rationale}")
    return out


def org_tree(org: Organization, unit_id: str | None = None, depth: int = 2, roles: bool = False) -> list[str]:
    start = org.units[unit_id or org.root.id]
    lines: list[str] = []

    def walk(unit, prefix: str, level: int, last: bool, is_root: bool) -> None:
        head = org.head_of(unit.id)
        status = " (placeholder)" if unit.status is UnitStatus.PLACEHOLDER else ""
        head_txt = f"  head: {head.title}" if head else ""
        count = len(org.roles_in(unit.id))
        label = f"{unit.name} [{unit.kind.value}, {count} roles]{status}{head_txt}"
        lines.append(label if is_root else prefix + (_LAST if last else _BRANCH) + label)
        child_prefix = "" if is_root else prefix + (_GAP if last else _PIPE)
        if roles:
            for r in org.roles_in(unit.id, recursive=False):
                lines.append(child_prefix + "  * " + f"{r.title} [{r.level.display_name}]")
        if level >= depth:
            return
        kids = org.children(unit.id)
        for i, kid in enumerate(kids):
            walk(kid, child_prefix, level + 1, i == len(kids) - 1, False)

    walk(start, "", 0, True, True)
    return lines
