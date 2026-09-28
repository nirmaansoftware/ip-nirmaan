"""``nirmaan`` command-line interface: inspect the company, plan and run projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

import nirmaan
from nirmaan.company import COMPANY_NAME, build_organization
from nirmaan.demos import DEMOS, demo as get_demo
from nirmaan.models import Actor, ActorKind, EscalationKind, EvidenceKind, TaskKind, Verdict
from nirmaan.orchestrator import Orchestrator, UnrecognizedRequirement
from nirmaan.org import Organization, OrganizationError
from nirmaan.views import org_tree, plan_tree
from nirmaan.work import (
    ProjectStore,
    TaskEngine,
    WorkError,
    PolicyViolationError,
    status_report,
    trace_graph,
    verify_chain,
    why_blocked,
)

app = typer.Typer(
    name="nirmaan",
    help=f"{COMPANY_NAME} - the organizational operating system for semiconductor engineering.",
    no_args_is_help=True,
    add_completion=False,
)
org_app = typer.Typer(help="Inspect the organization: units, roles, skills, tools.", no_args_is_help=True)
task_app = typer.Typer(help="Move a task through its lifecycle, as a role.", no_args_is_help=True)
app.add_typer(org_app, name="org")
app.add_typer(task_app, name="task")

console = Console()
_err = Console(stderr=True)

ROOT_OPTION = typer.Option(Path(".nirmaan"), "--root", help="Where projects are stored.")

_ORG: Organization | None = None


def _org() -> Organization:
    global _ORG
    if _ORG is None:
        try:
            _ORG = build_organization()
        except OrganizationError as exc:
            _err.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(2)
    return _ORG


def _fail(message: str) -> None:
    _err.print(f"[red]{escape(message)}[/red]")
    raise typer.Exit(1)


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        console.print(escape(line), highlight=False, soft_wrap=True)


# --- Organization ------------------------------------------------------------------------


@org_app.command("tree")
def org_tree_cmd(
    unit: Optional[str] = typer.Option(None, "--unit", help="Start at this unit ID."),
    depth: int = typer.Option(1, "--depth", "-d", help="How many levels to expand."),
    roles: bool = typer.Option(False, "--roles", help="List each unit's roles."),
) -> None:
    """The org chart."""
    org = _org()
    if unit and unit not in org.units:
        _fail(f"Unknown unit {unit!r}")
    _print_lines(org_tree(org, unit, depth, roles))


@org_app.command("stats")
def org_stats() -> None:
    """How big the company is."""
    org = _org()
    table = Table(title=f"{org.name}  ({org.fingerprint})")
    table.add_column("Concept")
    table.add_column("Count", justify="right")
    for key, value in org.stats().items():
        table.add_row(key.replace("_", " "), str(value))
    console.print(table)


@org_app.command("unit")
def org_unit(unit_id: str) -> None:
    """One unit: mission, head, baseline skills and tools, children."""
    org = _org()
    if unit_id not in org.units:
        _fail(f"Unknown unit {unit_id!r}")
    unit = org.units[unit_id]
    head = org.head_of(unit_id)
    console.print(f"[bold]{escape(unit.name)}[/bold] [{unit.kind.value}, {unit.function.value}, {unit.status.value}]")
    console.print(f"Mission: {escape(unit.mission or '-')}")
    console.print(f"Head: {escape(head.title) if head else '-'}")
    console.print(f"Baseline skills: {', '.join(unit.skills) or '-'}")
    console.print(f"Baseline tools: {', '.join(unit.tools) or '-'}")
    for kid in org.children(unit_id):
        console.print(f"  child: {kid.id}  ({escape(kid.name)})")
    for role in org.roles_in(unit_id, recursive=False):
        console.print(f"  role: {role.id}  {escape(role.title)} [{role.level.display_name}]")


@org_app.command("role")
def org_role(role_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """A role's full agent card: skills, capabilities, authority, tools, escalation."""
    org = _org()
    if role_id not in org.roles:
        _fail(f"Unknown role {role_id!r}")
    card = org.agent_card(role_id)
    if as_json:
        console.print_json(json.dumps(card))
        return
    role = org.roles[role_id]
    console.print(f"[bold]{escape(role.title)}[/bold]  ({role_id})  {role.level.display_name}")
    console.print(f"Unit: {role.unit}   Division: {card['division']}   Manager: {card['manager']}")
    for r in card["responsibilities"]:
        console.print(f"  - {escape(r)}")
    console.print("Skills: " + ", ".join(f"{k} ({v})" for k, v in card["skills"].items()))
    console.print("Capabilities: " + ", ".join(card["capabilities"]))
    console.print("Tools: " + ", ".join(card["tools"]))
    console.print("Quality gates: " + (", ".join(card["quality_gates"]) or "-"))
    console.print("Escalates to: " + " -> ".join(card["escalation_targets"]))


@org_app.command("skills")
def org_skills(domain: Optional[str] = typer.Option(None, "--domain")) -> None:
    """The skill catalog."""
    org = _org()
    table = Table(title="Skills")
    for col in ("ID", "Domain", "Provides", "Knowledge"):
        table.add_column(col)
    for skill in org.skills.values():
        if domain and skill.domain != domain:
            continue
        table.add_row(skill.id, f"{skill.domain}/{skill.subdomain}", ", ".join(skill.provides),
                      ", ".join(k.ref for k in skill.knowledge_sources))
    console.print(table)


@org_app.command("skill")
def org_skill(skill_id: str) -> None:
    """One skill, and who holds it."""
    org = _org()
    if skill_id not in org.skills:
        _fail(f"Unknown skill {skill_id!r}")
    console.print_json(org.skills[skill_id].model_dump_json())
    holders = [r.id for r in org.roles.values() if skill_id in org.effective_skills(r.id)]
    console.print(f"Held by {len(holders)} roles")


@org_app.command("tools")
def org_tools() -> None:
    """The tool catalog: which tools really execute here, and which are contracts."""
    from nirmaan.runtime import available_bindings

    bound = set(available_bindings())
    table = Table(title="Tools")
    for col in ("ID", "Category", "Risk", "Status", "Binding"):
        table.add_column(col)
    for tool in _org().tools.values():
        table.add_row(tool.id, tool.category, tool.risk.value, tool.status.value, "yes" if tool.id in bound else "-")
    console.print(table)


@org_app.command("validate")
def org_validate() -> None:
    """Validate the organization (every reference, chain, and workflow)."""
    from nirmaan.integrations.veritriage import missing_packs

    org = _org()
    missing = missing_packs(org)
    if missing:
        _fail("Skills cite unknown VeriTriage packs: " + ", ".join(missing))
    console.print(f"[green]{org.name} is valid[/green]: {org.stats()['roles']} roles, "
                  f"{len(org.workflows)} workflows, fingerprint {org.fingerprint}")


@org_app.command("export")
def org_export(output: Optional[Path] = typer.Option(None, "--output", "-o")) -> None:
    """The machine-readable company, derived roles included."""
    data = json.dumps(_org().export(), indent=2, sort_keys=True)
    if output:
        output.write_text(data + "\n", encoding="utf-8")
        console.print(f"Wrote {output}")
    else:
        console.print(data, highlight=False)


@app.command()
def workflows(workflow_id: Optional[str] = typer.Argument(None)) -> None:
    """The workflow registry."""
    org = _org()
    if workflow_id:
        wf = org.workflows.get(workflow_id)
        if wf is None:
            _fail(f"Unknown workflow {workflow_id!r}")
        console.print(f"[bold]{escape(wf.name)}[/bold]: {escape(wf.description)}")
        for stage in wf.stages:
            cond = "" if stage.when.is_unconditional else f"  when {stage.when.model_dump(exclude_defaults=True)}"
            gate = f"  gate={stage.gate}" if stage.gate else ""
            console.print(f"  {stage.id:24} {stage.capability:24} after {list(stage.depends_on)}{cond}{gate}")
        return
    for wf in org.workflows.values():
        console.print(f"{wf.id:26} {len(wf.stages):3} stages  intents={','.join(wf.intents)}  {escape(wf.name)}")


@app.command()
def policies() -> None:
    """The company constitution and the checks that enforce it."""
    for p in _org().principles.values():
        console.print(f"[bold]{p.id}[/bold] {escape(p.title)} [{p.enforcement.value}]: {escape(p.statement)}")
        console.print(f"     checks: {', '.join(p.checks)}")


# --- Planning ----------------------------------------------------------------------------


@app.command()
def analyze(requirement: str) -> None:
    """How the organization reads a requirement (no plan is made)."""
    analysis = Orchestrator(_org()).analyze(requirement)
    console.print_json(analysis.model_dump_json())


@app.command()
def plan(
    requirement: str,
    detail: bool = typer.Option(False, "--detail", help="Show reviewers, evidence, escalation, and routing."),
    save: bool = typer.Option(True, "--save/--no-save"),
    as_json: bool = typer.Option(False, "--json"),
    human_gate: List[str] = typer.Option([], "--human-gate", help="Require a human at this gate ID."),
    auto_gate: List[str] = typer.Option([], "--auto-gate", help="Allow a non-human at this gate ID."),
    root: Path = ROOT_OPTION,
) -> None:
    """Turn a requirement into an organization-driven execution plan."""
    org = _org()
    overrides = {g: True for g in human_gate} | {g: False for g in auto_gate}
    try:
        engine = Orchestrator(org).plan(requirement, gate_overrides=overrides)
    except UnrecognizedRequirement as exc:
        _fail(str(exc))
    if save:
        path = ProjectStore(root).save(engine.state)
        _err.print(f"saved {engine.state.project.id} -> {path}")
    if as_json:
        console.print(json.dumps(engine.state.model_dump(mode="json"), indent=2), highlight=False)
    else:
        _print_lines(plan_tree(org, engine.state, detail))


@app.command()
def demo(
    key: str = typer.Argument("all", help="Demo number, or 'all'."),
    detail: bool = typer.Option(False, "--detail"),
    save: bool = typer.Option(False, "--save/--no-save"),
    root: Path = ROOT_OPTION,
) -> None:
    """Plan the built-in demonstration requirements."""
    org = _org()
    chosen = DEMOS if key == "all" else (get_demo(key),)
    for d in chosen:
        console.rule(f"Demo {d.key}: {d.title}")
        engine = Orchestrator(org).plan(d.requirement)
        if save:
            ProjectStore(root).save(engine.state)
        _print_lines(plan_tree(org, engine.state, detail))


# --- Projects ----------------------------------------------------------------------------


def _load(project: str, root: Path) -> TaskEngine:
    try:
        state = ProjectStore(root).load(project)
    except (KeyError, ValueError) as exc:
        _fail(str(exc))
    org = _org()
    if state.project.organization_fingerprint != org.fingerprint:
        _err.print("[yellow]note: the organization changed since this project was planned[/yellow]")
    return TaskEngine(org, state)


def _task_id(engine: TaskEngine, task: str) -> str:
    return task if ":" in task else f"{engine.state.project.id}:{task}"


@app.command()
def projects(root: Path = ROOT_OPTION) -> None:
    """Saved projects."""
    table = Table(title="Projects")
    for col in ("ID", "Name", "Intent", "Tasks", "Progress"):
        table.add_column(col)
    for state in ProjectStore(root).list():
        report = status_report(_org(), state)
        table.add_row(state.project.id, state.project.name, report.intent or "-", str(report.tasks),
                      f"{report.progress:.0%}")
    console.print(table)


@app.command()
def show(project: str, detail: bool = typer.Option(False, "--detail"), root: Path = ROOT_OPTION) -> None:
    """A saved project's plan tree with current statuses."""
    engine = _load(project, root)
    _print_lines(plan_tree(engine.org, engine.state, detail))


@app.command()
def status(project: str, as_json: bool = typer.Option(False, "--json"), root: Path = ROOT_OPTION) -> None:
    """The manager's view: progress, blockers, escalations, reviews, gates, risks."""
    engine = _load(project, root)
    report = status_report(engine.org, engine.state)
    if as_json:
        console.print_json(json.dumps(report.to_dict()))
        return
    console.print(f"[bold]{escape(report.name)}[/bold]  {report.progress:.0%} complete  ({report.tasks} tasks)")
    console.print("By status: " + ", ".join(f"{k}={v}" for k, v in report.by_status.items()))
    console.print("Assurance: " + ", ".join(f"{k}={v}" for k, v in report.assurance.items()))
    for section in ("blocked", "escalations", "pending_reviews", "gates", "risks", "assumptions"):
        items = getattr(report, section)
        console.print(f"\n[bold]{section.replace('_', ' ').title()}[/bold] ({len(items)})")
        for item in items:
            console.print("  " + escape(json.dumps(item)))


@app.command()
def why(project: str, task: str, root: Path = ROOT_OPTION) -> None:
    """Why is this task blocked? The dependency and evidence chain."""
    engine = _load(project, root)
    tid = _task_id(engine, task)
    if tid not in engine.state.tasks:
        _fail(f"Unknown task {task!r}")
    blocker = why_blocked(engine.state, tid)
    if not blocker.is_blocked:
        console.print(f"{escape(blocker.title)} [{blocker.status}] is not blocked.")
        return
    _print_lines(blocker.lines())


@app.command()
def trace(project: str, output: Optional[Path] = typer.Option(None, "-o", "--output"), root: Path = ROOT_OPTION) -> None:
    """The requirement-to-evidence trace graph."""
    graph = trace_graph(_load(project, root).state)
    data = json.dumps(graph, indent=2)
    if output:
        output.write_text(data + "\n", encoding="utf-8")
        console.print(f"Wrote {output}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    else:
        console.print(data, highlight=False)


@app.command()
def audit(project: str, tail: int = typer.Option(20, "--tail"), root: Path = ROOT_OPTION) -> None:
    """The hash-chained audit trail, verified."""
    state = _load(project, root).state
    problems = verify_chain(state.audit)
    verdict = "[green]intact[/green]" if not problems else f"[red]BROKEN: {escape(problems[0])}[/red]"
    console.print(f"{len(state.audit)} entries, chain {verdict}")
    for entry in state.audit[-tail:]:
        console.print(escape(f"#{entry.sequence:04d} {entry.actor} {entry.action} {entry.subject} {entry.reason}"))


@app.command()
def dashboard(project: str, output: Path = typer.Option(Path("nirmaan-dashboard.html"), "-o", "--output"),
              root: Path = ROOT_OPTION) -> None:
    """A self-contained HTML organization dashboard for one project."""
    from nirmaan.dashboard import render_dashboard

    engine = _load(project, root)
    output.write_text(render_dashboard(engine.org, engine.state), encoding="utf-8")
    console.print(f"Wrote {output}")


# --- Task lifecycle ----------------------------------------------------------------------


def _actor(role: str, agent: bool) -> Actor:
    return Actor(role=role, kind=ActorKind.AI_AGENT if agent else ActorKind.HUMAN, name="cli")


def _mutate(project: str, root: Path, action) -> None:
    engine = _load(project, root)
    try:
        result = action(engine)
    except (WorkError, PolicyViolationError, PermissionError) as exc:
        _fail(str(exc))
    ProjectStore(root).save(engine.state)
    if result is not None:
        console.print(escape(str(result)))


AS_OPTION = typer.Option(..., "--as", help="Role ID acting.")
AGENT_OPTION = typer.Option(False, "--agent", help="Act as an AI agent rather than a human.")


@task_app.command("start")
def task_start(project: str, task: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION, root: Path = ROOT_OPTION):
    _mutate(project, root, lambda e: e.start(_task_id(e, task), _actor(role, agent)).status.value)


@task_app.command("submit")
def task_submit(
    project: str, task: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
    artifact: List[str] = typer.Option(..., "--artifact", help="kind:title[:location]"),
    outcome: Optional[str] = typer.Option(None, "--outcome"), notes: str = typer.Option("", "--notes"),
    root: Path = ROOT_OPTION,
):
    drafts = []
    for spec in artifact:
        parts = spec.split(":", 2)
        if len(parts) < 2:
            _fail(f"--artifact must be kind:title[:location], got {spec!r}")
        drafts.append({"kind": parts[0], "title": parts[1], "location": parts[2] if len(parts) > 2 else None})
    _mutate(project, root, lambda e: e.submit(_task_id(e, task), _actor(role, agent), drafts, notes, outcome).status.value)


@task_app.command("review")
def task_review(project: str, task: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
                changes: bool = typer.Option(False, "--request-changes"), comments: str = typer.Option("", "--comments"),
                root: Path = ROOT_OPTION):
    verdict = Verdict.REQUEST_CHANGES if changes else Verdict.APPROVE
    _mutate(project, root, lambda e: e.review(_task_id(e, task), _actor(role, agent), verdict, comments).review_state.value)


@task_app.command("approve")
def task_approve(project: str, task: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
                 note: str = typer.Option("", "--note"), root: Path = ROOT_OPTION):
    """Approve work, or a gate (gates may require a human)."""
    _mutate(project, root, lambda e: e.approve(_task_id(e, task), _actor(role, agent), note).status.value)


@task_app.command("attest")
def task_attest(project: str, task: str, description: str, role: str = AS_OPTION, root: Path = ROOT_OPTION):
    """Record a named human's attestation (e.g. a lint run made in another environment)."""
    _mutate(project, root, lambda e: e.record_evidence(
        _task_id(e, task), _actor(role, False), EvidenceKind.HUMAN_ATTESTATION, description).id)


@task_app.command("evidence")
def task_evidence(project: str, task: str, description: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
                  kind: EvidenceKind = typer.Option(EvidenceKind.DOCUMENT, "--kind"),
                  reference: Optional[str] = typer.Option(None, "--ref", help="Artifact, review, or session ID."),
                  root: Path = ROOT_OPTION):
    """Attach evidence. Only substantiated evidence satisfies a requirement; a claim never does."""
    def act(e: TaskEngine):
        ref = reference
        if ref and ":" not in ref and _task_id(e, ref) in {**e.state.artifacts, **e.state.reviews}:
            ref = _task_id(e, ref)
        ev = e.record_evidence(_task_id(e, task), _actor(role, agent), kind, description, reference=ref)
        return f"{ev.id} ({ev.kind.value}, substantiated={ev.substantiated})"

    _mutate(project, root, act)


@task_app.command("complete")
def task_complete(project: str, task: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
                  root: Path = ROOT_OPTION):
    _mutate(project, root, lambda e: e.complete(_task_id(e, task), _actor(role, agent)).status.value)


@task_app.command("tool")
def task_tool(project: str, task: str, tool: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
              param: List[str] = typer.Option([], "--param", help="key=value"), root: Path = ROOT_OPTION):
    """Invoke a tool through the broker and attach the run as evidence."""
    from nirmaan.runtime import ToolBroker

    params = dict(p.split("=", 1) for p in param)

    def act(e: TaskEngine):
        actor = _actor(role, agent)
        tid = _task_id(e, task)
        run, outcome = ToolBroker(e).invoke(actor, tool, params, tid)
        kind = EvidenceKind.VERITRIAGE_SESSION if tool == "veritriage.investigate" else EvidenceKind.TOOL_RUN
        ev = e.record_evidence(tid, actor, kind, run.summary,
                               reference=run.references[0] if run.references else None, tool_run=run.id)
        return f"{run.id}: {run.summary} -> evidence {ev.id} (substantiated={ev.substantiated})"

    _mutate(project, root, act)


@task_app.command("escalate")
def task_escalate(project: str, task: str, reason: str, role: str = AS_OPTION, agent: bool = AGENT_OPTION,
                  kind: EscalationKind = typer.Option(EscalationKind.TECHNICAL, "--kind"),
                  question: str = typer.Option("", "--question"),
                  option: List[str] = typer.Option([], "--option"), root: Path = ROOT_OPTION):
    _mutate(project, root, lambda e: e.escalate(_task_id(e, task), _actor(role, agent), kind, reason,
                                                blocking_question=question, recommended_options=tuple(option)))


@task_app.command("resolve")
def task_resolve(project: str, escalation: str, resolution: str, role: str = AS_OPTION,
                 agent: bool = AGENT_OPTION, root: Path = ROOT_OPTION):
    _mutate(project, root, lambda e: e.resolve_escalation(escalation, _actor(role, agent), resolution).state.value)


# --- Agents (M20) ------------------------------------------------------------------------


@app.command("run")
def run_cmd(
    project: str, task: str,
    runtime: str = typer.Option("unbound", "--runtime", help="Registered runtime ID (e.g. mock-llm, anthropic)."),
    review: bool = typer.Option(False, "--review", help="Seat the runtime as the task's reviewer instead."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the exact prompt; run nothing, change nothing."),
    inputs: List[str] = typer.Option([], "--input", help="key=value for the task's tools, e.g. paths=fail.log"),
    root: Path = ROOT_OPTION,
) -> None:
    """Hand one task to an agent runtime. The default runtime (unbound) declines."""
    from nirmaan.models import MemoryScope
    from nirmaan.runtime import assemble, get_runtime, render_work_prompt, review_task, run_task

    engine = _load(project, root)
    tid = _task_id(engine, task)
    if tid not in engine.state.tasks:
        _fail(f"Unknown task {task!r}")
    try:
        agent = get_runtime(runtime)
    except KeyError as exc:
        _fail(str(exc.args[0]))
    target = engine.task(tid)
    if dry_run:
        seat = target.reviewer if review else None
        _print_lines(render_work_prompt(assemble(engine, tid, role=seat), "review" if review else "work")
                     .render().splitlines())
        _err.print("dry run: no model was called, no tool was run, nothing was saved")
        return
    try:
        for spec in inputs:
            key, sep, value = spec.partition("=")
            if not sep:
                _fail(f"--input must be key=value, got {spec!r}")
            engine.remember(MemoryScope.TASK, tid, f"input.{key}", value, _actor(target.owner, False))
        report = review_task(engine, tid, agent) if review else run_task(engine, tid, agent)
    except (WorkError, PolicyViolationError, PermissionError) as exc:
        _fail(str(exc))
    ProjectStore(root).save(engine.state)
    console.print(f"{report.task}: {report.status.value}", highlight=False)
    if report.detail:
        console.print(escape(report.detail), highlight=False, soft_wrap=True)
    for label, ids in (("tool runs", report.tool_runs), ("evidence", report.evidence)):
        if ids:
            console.print(f"{label}: {', '.join(ids)}", highlight=False)
    for label, ref in (("escalation", report.escalation), ("review", report.review)):
        if ref:
            console.print(f"{label}: {ref}", highlight=False)


@app.command()
def version() -> None:
    """Print the platform version and its verification engine."""
    from nirmaan.integrations.veritriage import engine_version

    console.print(f"{COMPANY_NAME} {nirmaan.__version__} (verification engine: VeriTriage {engine_version()})")


if __name__ == "__main__":  # pragma: no cover
    app()
