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
from nirmaan.models import (Actor, ActorKind, Criticality, DecisionKind, EscalationKind, EvidenceKind, TaskKind,
                            Verdict)
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
eval_app = typer.Typer(help="Evaluate a seat: a real or replayed model, judged by real tool runs.",
                       no_args_is_help=True)
app.add_typer(org_app, name="org")
app.add_typer(task_app, name="task")
app.add_typer(eval_app, name="eval")
regmap_app = typer.Typer(help="Register maps as data: check one, or lower it to a header or a table.",
                         no_args_is_help=True)
app.add_typer(regmap_app, name="regmap")
vplan_app = typer.Typer(help="Load and save verification plans: requirements and the items that prove them.",
                        no_args_is_help=True)
app.add_typer(vplan_app, name="vplan")

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
    from nirmaan.runtime import available_bindings, unavailable_reason

    bound = set(available_bindings())
    table = Table(title="Tools")
    for col in ("ID", "Category", "Risk", "Status", "Binding", "Here"):
        table.add_column(col)
    for tool in _org().tools.values():
        why = unavailable_reason(tool.id) if tool.id in bound else None
        here = "-" if tool.id not in bound else f"no: {why}" if why else "yes"
        table.add_row(tool.id, tool.category, tool.risk.value, tool.status.value,
                      "yes" if tool.id in bound else "-", here)
    console.print(table)


@org_app.command("tool")
def org_tool(tool_id: str) -> None:
    """One tool's contract: what it takes, and whether this machine can run it."""
    from nirmaan.runtime import available_bindings, unavailable_reason

    tool = _org().tools.get(tool_id)
    if tool is None:
        _fail(f"Unknown tool {tool_id!r}")
    bound = tool_id in available_bindings()
    why = unavailable_reason(tool_id) if bound else None
    here = "no binding" if not bound else f"no: {why}" if why else "yes"
    _print_lines([f"{tool.id}: {tool.name} ({tool.category}, {tool.risk.value}, {tool.status.value})",
                  tool.description, f"Runs here: {here}"])
    if tool.params is None:
        console.print("Parameters: no contract declared; parameters are taken as given.")
        return
    table = Table(title="Parameters")
    for col in ("Name", "Kind", "Required", "Description"):
        table.add_column(col)
    for param in tool.params:
        table.add_row(escape(param.label), param.kind.value, "required" if param.required else "",
                      escape(param.description))
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


@app.command("export")
def export_cmd(project: str, out: Path = typer.Option(..., "--out", help="A new or empty directory."),
               root: Path = ROOT_OPTION) -> None:
    """Write the numbered deliverable tree. A read: project state is not changed."""
    from nirmaan.export import ExportError, export_project

    try:
        state = ProjectStore(root).load(project, verify=False)  # the export reports a broken chain itself
        report = export_project(_org(), state, out)
    except (KeyError, ValueError, ExportError) as exc:
        _fail(str(exc))
    if report.chain_problems:
        console.print(f"[bold red]AUDIT CHAIN FAILED VERIFICATION: {escape(report.chain_problems[0])}[/bold red]")
    console.print(f"Wrote {len(report.files)} files to {escape(str(out))}: {report.artifacts} artifacts, "
                  f"{len(report.missing)} missing, {report.signed_off} of {report.gates} gates signed off")


@app.command()
def gaps(project: str, as_json: bool = typer.Option(False, "--json"), root: Path = ROOT_OPTION) -> None:
    """Which requirements are not yet backed by passing verification evidence? Exits 1 when any."""
    from nirmaan.engineering import requirement_coverage

    coverage = requirement_coverage(_load(project, root).state)
    unbacked = [r for r in coverage if not r.backed]
    if as_json:
        typer.echo(json.dumps([r.to_dict() for r in coverage], indent=2))
    else:
        console.print(f"{len(coverage) - len(unbacked)} of {len(coverage)} recorded requirements are backed "
                      "by passing, cited tool runs.")
        for req in unbacked:
            console.print(f"\n[bold]{escape(req.requirement)}[/bold] {escape(req.text)}")
            for reason in req.reasons:
                console.print(f"  - {escape(reason)}")
    if unbacked:
        raise typer.Exit(1)


@app.command()
def decisions(project: str, as_json: bool = typer.Option(False, "--json"), root: Path = ROOT_OPTION) -> None:
    """Why each choice was made: decision tasks and recorded decisions, read from the record."""
    from nirmaan.records import decision_records

    records = decision_records(_load(project, root).state)
    if as_json:
        typer.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return
    for r in records:
        console.print(escape(f"{r.id} [{r.status}] {r.question}"), highlight=False, soft_wrap=True)
        console.print(escape(f"  chosen: {r.chosen or 'not yet decided'}; alternatives: "
                             f"{', '.join(r.alternatives) or 'none recorded'}"), highlight=False, soft_wrap=True)
        if r.decided_by:
            console.print(escape(f"  decided by {r.decided_by} at {r.decided_at}"), highlight=False)
        if r.kind:
            links = [f"supersedes {r.supersedes}"] if r.supersedes else []
            links += [f"superseded by {r.superseded_by}"] if r.superseded_by else []
            console.print(escape(f"  {r.criticality} {r.kind}" + "".join(f"; {x}" for x in links)), highlight=False)
        for c in r.consequences:
            console.print(escape(f"  cancelled {c['task']}: {c['title']}"), highlight=False, soft_wrap=True)


@app.command()
def decide(
    project: str,
    statement: str = typer.Argument(..., help="The decision, as one sentence."),
    role: str = typer.Option(..., "--as", help="Role ID deciding."),
    kind: DecisionKind = typer.Option(..., "--kind", help="Sets, with --criticality, the authority required."),
    criticality: Criticality = typer.Option(..., "--criticality"),
    subject: str = typer.Option("", "--subject", help="The question decided."),
    task: Optional[str] = typer.Option(None, "--task", help="The task the decision is about."),
    option: List[str] = typer.Option([], "--option", help="An alternative considered (repeatable)."),
    evidence: List[str] = typer.Option([], "--evidence", help="An evidence ID it rests on (repeatable)."),
    rationale: str = typer.Option("", "--rationale"),
    supersedes: Optional[str] = typer.Option(None, "--supersedes", help="A decision ID this one replaces."),
    agent: bool = typer.Option(False, "--agent", help="Act as an AI agent rather than a human."),
    root: Path = ROOT_OPTION,
) -> None:
    """Record an explicit engineering decision. The authority matrix and the constitution decide."""
    _mutate(project, root, lambda e: e.record_decision(
        _actor(role, agent), kind, criticality, statement, rationale, evidence=tuple(evidence),
        task_id=_task_id(e, task) if task else None, subject=subject, options=tuple(option),
        supersedes=supersedes).id)


@app.command()
def failures(projects: List[str], as_json: bool = typer.Option(False, "--json"), root: Path = ROOT_OPTION) -> None:
    """What went wrong and whether it was resolved; with several projects, counts across them."""
    from nirmaan.records import failure_records, failure_summary

    states = [_load(p, root).state for p in projects]
    records = [r for s in states for r in failure_records(s)]
    summary = failure_summary(states)
    if as_json:
        typer.echo(json.dumps({"failures": [r.to_dict() for r in records],
                               "summary": [c.to_dict() for c in summary]}, indent=2))
        return
    for r in records:
        status = f"resolved: {r.resolution}" if r.resolved else "open"
        console.print(escape(f"{r.category.value}{' ' + r.subject if r.subject else ''} on {r.task}: "
                             f"{r.summary} ({status})"), highlight=False, soft_wrap=True)
    if len(states) > 1:
        console.print("\nAcross projects:")
        for c in summary:
            console.print(escape(f"  {c.category.value} {c.subject or '-'}: {c.count} in {c.projects} "
                                 f"projects, {c.resolved} resolved"), highlight=False)


@app.command()
def costs(project: str, as_json: bool = typer.Option(False, "--json"), root: Path = ROOT_OPTION) -> None:
    """What the project's model calls cost, as recorded: by model, purpose, and task."""
    from nirmaan.costs import cost_report

    report = cost_report(_load(project, root).state)
    if as_json:
        typer.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return
    unknown = f"; {report.unknown_cost_calls} of unknown cost" if report.unknown_cost_calls else ""
    console.print(escape(f"{report.calls} model calls, {report.input_tokens} input and {report.output_tokens} "
                         f"output tokens, ${report.cost_usd:.4f}{unknown}"), highlight=False)
    for model, line in sorted(report.by_model.items()):
        console.print(escape(f"  {model}: {line.calls} calls, ${line.cost_usd:.4f}"), highlight=False)


@app.command()
def learn(
    projects: List[str] = typer.Argument(None, help="Projects whose failure records to read."),
    evals: Optional[Path] = typer.Option(None, "--evals", help="Recorded evaluation results to read too (M42)."),
    cases: Path = typer.Option(Path("evals"), "--cases", help="Evaluation case files, for each seat's capability."),
    decide: Optional[str] = typer.Option(None, "--decide", help="A proposal ID to decide."),
    in_project: Optional[str] = typer.Option(None, "--in", help="The project to record the decision in."),
    role: Optional[str] = typer.Option(None, "--as", help="Role ID deciding, as a human."),
    adopt: Optional[bool] = typer.Option(None, "--adopt/--reject", help="Adopt or reject the proposal."),
    reason: str = typer.Option("", "--reason", help="Why: recorded as the decision's rationale."),
    as_json: bool = typer.Option(False, "--json"),
    root: Path = ROOT_OPTION,
) -> None:
    """Skill changes proposed by failures that recur across projects or evaluation runs; decide one as a person."""
    from nirmaan.proposals import ProposalError, decide_proposal, learning_proposals

    if not projects and evals is None:
        _fail("name projects, --evals DIR, or both")
    engines = {p: _load(p, root) for p in projects or []}
    proposals = learning_proposals(_org(), [e.state for e in engines.values()]) if engines else []
    if evals is not None:
        from nirmaan.eval_proposals import eval_proposals, load_results

        try:
            runs = load_results(evals)
        except (ValueError, OSError) as exc:
            _fail(f"cannot read evaluation results under {evals}: {exc}")
        proposals += eval_proposals(_org(), runs, _cases(cases), states=[e.state for e in engines.values()])
    if decide:
        chosen = next((p for p in proposals if p.id == decide), None)
        if chosen is None or adopt is None or not role or not in_project:
            _fail("--decide needs a listed proposal ID, --in PROJECT, --as ROLE, and --adopt or --reject")
        engine = next((e for pid, e in engines.items() if pid == in_project
                       or e.state.project.id == in_project), None)
        if engine is None:
            _fail(f"--in {in_project} is not one of the projects read")
        try:
            decision = decide_proposal(engine, chosen, _actor(role, False), adopt, reason)
        except (ProposalError, WorkError, PolicyViolationError, PermissionError) as exc:
            _fail(str(exc))
        ProjectStore(root).save(engine.state)
        console.print(escape(f"{decision.id}: {decision.statement}"), highlight=False, soft_wrap=True)
        return
    if as_json:
        typer.echo(json.dumps([p.to_dict() for p in proposals], indent=2))
        return
    if not proposals:
        console.print("No failure recurs often enough to propose a change.")
    for p in proposals:
        console.print(escape(f"{p.id} [{p.status}] [{p.source}] {p.statement}"), highlight=False, soft_wrap=True)
        console.print(escape(f"  for {', '.join(p.targets) or 'no providing skill'}: {p.suggestion}"),
                      highlight=False, soft_wrap=True)
        for e in p.evidence if p.source == "evaluation" else ():
            verdicts = "; ".join(f"{v['check']} {v['status']}: {v['summary']}" for v in e["verdicts"])
            console.print(escape(f"  run {e['run']} {e['case']} on {e['runtime']} {e['version']} "
                                 f"{e['started_at']}: {'passed' if e['passed'] else 'failed'} ({verdicts}) "
                                 f"<- {e['file']}"), highlight=False, soft_wrap=True)


@app.command()
def links(project: str, root: Path = ROOT_OPTION) -> None:
    """Design Graph nodes each artifact links to, parsed from its digest-checked file."""
    from nirmaan.engineering import artifact_links

    report = artifact_links(_load(project, root).state)
    for link in report.links:
        console.print(f"{escape(link.artifact)} {link.kind} {link.node_kind} {escape(link.node_name)}")
    for refused in report.refused:
        console.print(f"[red]refused[/red] {escape(refused.artifact)}: {escape(refused.reason)}")


@vplan_app.command("import")
def vplan_import(project: str, file: Path, role: str = typer.Option(..., "--as", help="Role ID acting."),
                 agent: bool = typer.Option(False, "--agent", help="Act as an AI agent rather than a human."),
                 amend: bool = typer.Option(False, "--amend", help="The file is the next version of the plan: "
                                            "add, modify, and retire (M38)."),
                 root: Path = ROOT_OPTION) -> None:
    """Record a plan's requirements and items through the engine. All or nothing; it backs nothing."""
    from nirmaan.vplan import PlanError, amend_plan, import_plan

    engine = _load(project, root)
    try:
        if amend:
            changed = amend_plan(engine, _actor(role, agent), file.read_text(encoding="utf-8"))
        else:
            report = import_plan(engine, _actor(role, agent), file.read_text(encoding="utf-8"))
    except PlanError as exc:
        for problem in exc.problems:
            _err.print(f"[red]{escape(str(file))}: {escape(problem)}[/red]")
        _fail(f"refused {file}: nothing was recorded")
    except OSError as exc:
        _fail(str(exc))
    ProjectStore(root).save(engine.state)
    if amend:
        console.print(f"Amended the plan: added {len(changed.added)}, modified {len(changed.modified)}, "
                      f"retired {len(changed.retired)}, kept {len(changed.kept)}. Superseded versions stay on the "
                      "audit trail. None is backed until a passing, cited tool run backs it.")
        return
    console.print(f"Recorded {report.requirements} requirements and {report.items} verification items. "
                  "None is backed until a passing, cited tool run backs it.")


@vplan_app.command("export")
def vplan_export(project: str, out: Optional[Path] = typer.Option(None, "--out", help="Write here, not stdout."),
                 root: Path = ROOT_OPTION) -> None:
    """The project's requirements and verification items, in the plan format."""
    from nirmaan.vplan import export_plan

    text = export_plan(_load(project, root).state)
    if out is None:
        typer.echo(text, nl=False)
    else:
        out.write_text(text, encoding="utf-8")
        console.print(f"Wrote {escape(str(out))}")


@app.command()
def mcp(root: Path = ROOT_OPTION) -> None:
    """Serve IP Nirmaan over MCP (stdio): plan, status, why, and task actions."""
    from nirmaan.mcp import serve

    serve(str(root))


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
              param: List[str] = typer.Option([], "--param", help="key=value; repeat a key for a list"),
              root: Path = ROOT_OPTION):
    """Invoke a tool through the broker and attach the run as evidence. Values are typed by its contract."""
    from nirmaan.runtime import ToolBroker

    given: dict[str, list[str]] = {}
    for p in param:
        key, _, value = p.partition("=")
        given.setdefault(key, []).append(value)
    params = {k: v[0] if len(v) == 1 else v for k, v in given.items()}

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
    attempts: Optional[int] = typer.Option(None, "--attempts", min=1,
                                           help="Attempts when a submission is refused (default: the stage's, "
                                                "else the capability's)."),
    review_rounds: Optional[int] = typer.Option(None, "--review-rounds", min=1,
                                                help="Submissions that may go to review (default: the stage's, "
                                                     "else the capability's)."),
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
        report = review_task(engine, tid, agent) if review else run_task(engine, tid, agent, attempts=attempts,
                                                                    review_rounds=review_rounds)
    except (WorkError, PolicyViolationError, PermissionError) as exc:
        _fail(str(exc))
    ProjectStore(root).save(engine.state)
    console.print(f"{report.task}: {report.status.value}", highlight=False)
    if report.detail:
        console.print(escape(report.detail), highlight=False, soft_wrap=True)
    for label, ids in (("tool runs", report.tool_runs), ("evidence", report.evidence)):
        if ids:
            console.print(f"{label}: {', '.join(ids)}", highlight=False)
    if len(report.attempts) > 1:
        for step in report.attempts:
            recorded = f" ({step['attempt']})" if step["attempt"] else ""
            console.print(f"attempt {step['number']}: {step['status']}{recorded}", highlight=False)
    for label, ref in (("escalation", report.escalation), ("review", report.review)):
        if ref:
            console.print(f"{label}: {ref}", highlight=False)


@app.command("drive")
def drive_cmd(
    project: str, task: Optional[str] = typer.Argument(None, help="One task; omit to drive every ready task."),
    runtime: str = typer.Option("unbound", "--runtime", help="Registered runtime ID for the owner seat."),
    reviewer_runtime: Optional[str] = typer.Option(None, "--reviewer-runtime",
                                                   help="Runtime ID for the reviewer seat (default: --runtime)."),
    max_calls: int = typer.Option(20, "--max-calls", min=0, help="Runtime calls this invocation may make."),
    attempts: Optional[int] = typer.Option(None, "--attempts", min=1, help="As for nirmaan run."),
    review_rounds: Optional[int] = typer.Option(None, "--review-rounds", min=1, help="As for nirmaan run."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan of calls; run nothing, change nothing."),
    inputs: List[str] = typer.Option([], "--input", help="key=value for the task's tools (needs TASK)."),
    jobs: int = typer.Option(1, "--jobs", min=1, help="Model calls in flight at once across independent tasks."),
    root: Path = ROOT_OPTION,
) -> None:
    """Run the owner and reviewer seats in turn until a person must act. Never approves (docs/AUTO_LOOP.md)."""
    from nirmaan.models import MemoryScope
    from nirmaan.runtime import Stop, get_runtime, loop, plan_loop

    def say(text: str) -> None:
        console.print(escape(text), highlight=False, soft_wrap=True)

    engine = _load(project, root)
    tid = _task_id(engine, task) if task else None
    if tid is not None and tid not in engine.state.tasks:
        _fail(f"Unknown task {task!r}")
    if inputs and tid is None:
        _fail("--input needs a TASK")
    reviewer_id = reviewer_runtime or runtime
    try:
        owner, reviewer = get_runtime(runtime), get_runtime(reviewer_id)
    except KeyError as exc:
        _fail(str(exc.args[0]))
    if runtime == reviewer_id:
        _err.print(f"note: both seats run on {runtime}; independence is by seat and prompt (docs/AUTO_LOOP.md 5)",
                   soft_wrap=True)
    try:
        if dry_run:
            plan = plan_loop(engine, runtime, reviewer_id, tid, max_calls, attempts, review_rounds, jobs)
            current = None
            for number, step in enumerate(plan.steps, 1):
                if step.task != current:
                    current = step.task
                    say(f"plan for {step.task}")
                if step.calls == 0:
                    later = number > 1 and plan.steps[number - 2].task == step.task
                    what = "escalates if changes are requested again" if later else "escalates, its limits are spent"
                    say(f"  {number}. owner {step.role}: {what} (no call)")
                elif step.seat == "owner":
                    calls = f"up to {step.calls} call{'s' if step.calls > 1 else ''}"
                    say(f"  {number}. owner {step.role} on {step.runtime}: round {step.round} of "
                        f"{step.rounds}, {calls}")
                else:
                    say(f"  {number}. reviewer {step.role} on {step.runtime}: 1 call")
            for stopped, why in plan.stops.items():
                say(f"{stopped}: then stop, {why.value}")
            if len(plan.concurrent) > 1:
                say(f"concurrently: {', '.join(plan.concurrent)} (up to {jobs} call{'s' if jobs > 1 else ''} "
                    "in flight)")
            say(f"worst case: {plan.calls} calls, budget {max_calls}")
            limits = plan.project_budget
            if limits is not None and limits.calls is not None and plan.spent is not None:
                left = max(limits.calls - plan.spent.calls, 0)
                fits = ("the worst case fits" if plan.calls <= left
                        else "the worst case does not fit, so the loop stops when it is spent")
                say(f"project budget: {plan.spent.calls} of {limits.calls} calls spent, {left} left; {fits}")
            if limits is not None and limits.cost_usd is not None and plan.spent is not None:
                say(f"project cost budget: {plan.spent.cost_usd} of {limits.cost_usd} USD spent"
                    + (f", {plan.spent.unknown_cost} call(s) of unknown cost" if plan.spent.unknown_cost else ""))
            _err.print("dry run: no model was called, no tool was run, nothing was saved")
            return
        if tid is not None:
            target = engine.task(tid)
            for spec in inputs:
                key, sep, value = spec.partition("=")
                if not sep:
                    _fail(f"--input must be key=value, got {spec!r}")
                engine.remember(MemoryScope.TASK, tid, f"input.{key}", value, _actor(target.owner, False))
        store = ProjectStore(root)
        report = loop(engine, owner, reviewer, tid, max_calls, attempts, review_rounds,
                      on_step=lambda e: store.save(e.state), jobs=jobs)
    except (WorkError, PolicyViolationError, PermissionError) as exc:
        _fail(str(exc))
    store.save(engine.state)
    for step in report.steps:
        say(f"step {step.number}: {step.task} {step.seat} {step.role} on {step.runtime}: {step.status} "
            f"({step.calls} call{'' if step.calls == 1 else 's'})")
        if step.detail:
            say("  " + step.detail)
        for label, ref in (("review", step.review), ("escalation", step.escalation)):
            if ref:
                say(f"  {label}: {ref}")
    for stopped, why in report.stops.items():
        say(f"{stopped}: stopped, {why.value}")
    say(f"calls: {report.calls} of {max_calls}")
    if Stop.PROJECT_BUDGET in report.stops.values():
        say("the project budget is spent; a person may raise it with nirmaan budget (docs/LOOP_CONCURRENCY.md)")


@app.command("budget")
def budget_cmd(
    project: str,
    calls: Optional[int] = typer.Option(None, "--calls", min=0, help="Model calls the project may make in all."),
    cost_usd: Optional[float] = typer.Option(None, "--cost-usd", min=0, help="Known cost the project may reach."),
    clear: bool = typer.Option(False, "--clear", help="Lift every limit."),
    role: Optional[str] = typer.Option(None, "--as", help="Role ID of the person deciding."),
    reason: str = typer.Option("", "--reason", help="Why: recorded with the decision."),
    root: Path = ROOT_OPTION,
) -> None:
    """Show, or as a person set, the project's model-call budget (docs/LOOP_CONCURRENCY.md)."""
    from nirmaan.work.budget import budget, spend

    engine = _load(project, root)
    if calls is None and cost_usd is None and not clear:
        limits, spent = budget(engine.state), spend(engine.state)
        if limits is None:
            console.print("no budget is set", highlight=False)
        else:
            console.print(escape(f"set by {limits.set_by}: {limits.reason}"), highlight=False)
        console.print(f"calls: {spent.calls}" + (f" of {limits.calls} spent" if limits and limits.calls is not None
                                                 else " made"), highlight=False)
        cost = f"cost: {spent.cost_usd} USD" + (f" of {limits.cost_usd}" if limits and limits.cost_usd is not None
                                               else "")
        console.print(cost + (f", {spent.unknown_cost} call(s) of unknown cost" if spent.unknown_cost else ""),
                      highlight=False)
        return
    if role is None or not reason.strip():
        _fail("setting a budget is a person's decision: give --as ROLE and a --reason")
    previous = budget(engine.state)
    if not clear:
        calls = calls if calls is not None else (previous.calls if previous else None)
        cost_usd = cost_usd if cost_usd is not None else (previous.cost_usd if previous else None)
    else:
        calls = cost_usd = None
    _mutate(project, root, lambda e: e.set_budget(_actor(role, False), calls, cost_usd, reason) or
            f"budget: calls {calls if calls is not None else 'unlimited'}, "
            f"cost {cost_usd if cost_usd is not None else 'unlimited'} USD")


# --- Seat evaluation (M27) ---------------------------------------------------------------

CASES_OPTION = typer.Option(Path("evals"), "--cases", help="Directory of evaluation case files.")


def _cases(cases: Path):
    from nirmaan.evals import EvalError, load_cases

    try:
        return load_cases(cases)
    except (EvalError, ValueError) as exc:
        _fail(str(exc))


@eval_app.command("list")
def eval_list(cases: Path = CASES_OPTION) -> None:
    """The evaluation cases: ID, seat, and request."""
    for case in _cases(cases):
        console.print(escape(f"{case.id}  [{case.seat}]  {case.request}"), highlight=False, soft_wrap=True)


@eval_app.command("run")
def eval_run(
    case_ids: List[str] = typer.Argument(None, help="Case IDs to run (default: every case)."),
    runtime: Optional[str] = typer.Option(None, "--runtime", help="Registered runtime ID to put in the seat."),
    replay: bool = typer.Option(False, "--replay", help="Replay each case's reference answer instead."),
    attempts: Optional[int] = typer.Option(None, "--attempts", min=1, help="Attempts when a submission is refused."),
    cases: Path = CASES_OPTION,
    repo: Path = typer.Option(Path("."), "--repo", help="Root that case file paths are relative to."),
    out: Path = typer.Option(Path(".nirmaan") / "evals", "--out", help="Where result records are written."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run evaluation cases. Exits 1 when any case fails."""
    from nirmaan.evals import EvalError, run_case, write_result
    from nirmaan.runtime import get_runtime

    if replay == (runtime is not None):
        _fail("choose one: --runtime ID (a model in the seat) or --replay (the reference answer)")
    known = {case.id: case for case in _cases(cases)}
    unknown = [c for c in case_ids or [] if c not in known]
    if unknown:
        _fail(f"unknown case {', '.join(unknown)}; known: {', '.join(known) or 'none'}")
    try:
        agent = get_runtime(runtime) if runtime else None
    except KeyError as exc:
        _fail(str(exc.args[0]))
    results = []
    for case_id in case_ids or list(known):
        try:
            result = run_case(_org(), known[case_id], agent, repo=repo, attempts=attempts)
        except EvalError as exc:
            _fail(str(exc))
        path = write_result(result, out)
        results.append(result)
        if not as_json:
            passed = sum(s.status.value == "passed" for s in result.scores)
            console.print(escape(f"{'PASS' if result.passed else 'FAIL'} {result.case} [{result.runtime}]: "
                                 f"{result.seat_status}, {passed}/{len(result.scores)} held-out checks passed "
                                 f"({result.duration_s}s) -> {path}"), highlight=False, soft_wrap=True)
            for score in result.scores:
                console.print(f"  {score.status.value}: {escape(score.name)}: {escape(score.summary)}",
                              highlight=False, soft_wrap=True)
            if not result.submitted and result.detail:
                console.print(f"  {escape(result.detail)}", highlight=False, soft_wrap=True)
    if as_json:
        typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
    if not all(r.passed for r in results):
        raise typer.Exit(1)


# --- Register maps (M30) ------------------------------------------------------------------


def _regmap(path: Path):
    from nirmaan.regmap import load_map

    try:
        return load_map(path)
    except (OSError, ValueError) as exc:
        _fail(f"cannot read the register map {path}: {str(exc).splitlines()[0]}")


@regmap_app.command("check")
def regmap_check(path: Path) -> None:
    """Validate a register map. Exits 1 when it has problems."""
    from nirmaan.regmap import map_summary, validate

    regmap = _regmap(path)
    problems = validate(regmap)
    for problem in problems:
        _err.print(escape(problem), highlight=False)
    if problems:
        raise typer.Exit(1)
    console.print(escape(f"valid: {map_summary(regmap)}"), highlight=False)


@regmap_app.command("lower")
def regmap_lower(path: Path, to: str = typer.Option(..., "--to", help="A registered lowering, e.g. c-header.")) -> None:
    """Print the map lowered to a header, a table, or any registered lowering."""
    from nirmaan.regmap import lower

    try:
        typer.echo(lower(_regmap(path), to), nl=False)
    except (KeyError, ValueError) as exc:
        _fail(str(exc.args[0]))


@app.command()
def version() -> None:
    """Print the platform version and its verification engine."""
    from nirmaan.integrations.veritriage import engine_version

    console.print(f"{COMPANY_NAME} {nirmaan.__version__} (verification engine: VeriTriage {engine_version()})")


if __name__ == "__main__":  # pragma: no cover
    app()
