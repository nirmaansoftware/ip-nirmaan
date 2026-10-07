"""The cross-domain engineering graph (M24): artifacts to design, requirements to evidence.

Two joins the trace graph lacked, and the one question they answer:

* **Artifact to Design Graph node.** Derived, never recorded: an artifact's file
  is read, checked against its recorded digest (refused on any mismatch), and
  those exact bytes are parsed by VeriTriage through the bridge. The link kinds
  (``nirmaan.company.traceability``) walk the resulting graph.
* **Requirement to verification item.** Recorded through the task engine
  (``record_spec_requirement``, ``record_verification_item``), with provenance.
* **The question.** :func:`unbacked_requirements`: which requirements are not
  yet backed by passing verification evidence, and why each is not.

Everything here is a read: no state change, no audit entry, no model call.
See docs/ENGINEERING_GRAPH.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nirmaan.company import traceability
from nirmaan.company.traceability import ItemKind, LinkKind
from nirmaan.models import Artifact, EvidenceKind, ProjectState, ToolRun, VerificationItem
from nirmaan.work.trace import trace_graph

# --- The kind tables, as registries -------------------------------------------------------

_LINK_OVERLAY: dict[str, LinkKind] = {}
_ITEM_OVERLAY: dict[str, ItemKind] = {}


def register_link_kind(kind: LinkKind) -> None:
    """Add a link kind, or replace the one with the same ID."""
    _LINK_OVERLAY[kind.id] = kind


def unregister_link_kind(kind_id: str) -> None:
    _LINK_OVERLAY.pop(kind_id, None)


def register_item_kind(kind: ItemKind) -> None:
    """Add a verification-item kind, or replace the one with the same ID."""
    _ITEM_OVERLAY[kind.id] = kind


def unregister_item_kind(kind_id: str) -> None:
    _ITEM_OVERLAY.pop(kind_id, None)


def link_kinds() -> dict[str, LinkKind]:
    return {**{k.id: k for k in traceability.LINK_KINDS}, **_LINK_OVERLAY}


def item_kinds() -> dict[str, ItemKind]:
    return {**{k.id: k for k in traceability.ITEM_KINDS}, **_ITEM_OVERLAY}


# --- The file, checked ----------------------------------------------------------------------


def verified_bytes(art: Artifact) -> tuple[bytes | None, str]:
    """The artifact's file, only if it still matches its recorded digest; else None and why."""
    if not art.location:
        return None, f"{art.id} has no recorded file"
    if not art.digest:
        return None, f"{art.id} has no recorded digest to check {art.location} against"
    path = Path(art.location)
    if not path.is_file():
        return None, f"{art.location} no longer exists"
    data = path.read_bytes()
    actual = "sha256:" + hashlib.sha256(data).hexdigest()
    if actual != art.digest:
        return None, (f"{art.location} does not match its recorded digest {art.digest} "
                      f"(it is now {actual}): changed after it was recorded")
    return data, ""


# --- Links: artifact -> Design Graph node ---------------------------------------------------


@dataclass(frozen=True)
class DesignLink:
    artifact: str
    kind: str
    node: str
    node_kind: str
    node_name: str
    rationale: str
    digest: str


@dataclass(frozen=True)
class RefusedLink:
    artifact: str
    reason: str


@dataclass
class LinkReport:
    links: list[DesignLink] = field(default_factory=list)
    refused: list[RefusedLink] = field(default_factory=list)
    nodes: dict[str, dict] = field(default_factory=dict)  # every linked design node, as plain data


def _walk(graph: dict, name: str, kind: LinkKind) -> dict[str, str]:
    """Node ID -> rationale for the nodes ``kind`` reaches from the modules file ``name`` defines."""
    start = {n["id"]: f"{name} defines {n['kind']} {n['name']}"
             for n in graph["nodes"] if n["kind"] == "module" and n["source_file"] == name}
    if not kind.walk:
        return start
    reached: dict[str, str] = {}
    frontier = start
    for step in kind.walk:
        relation, backward = step.lstrip("<"), step.startswith("<")
        following: dict[str, str] = {}
        for edge in graph["edges"]:
            if edge["relation"] != relation:
                continue
            here, there = (edge["to"], edge["from"]) if backward else (edge["from"], edge["to"])
            if here in frontier and there not in following:
                following[there] = f"{frontier[here]}; {relation}: {edge['rationale']}"
        for node_id, why in following.items():
            reached.setdefault(node_id, why)
        frontier = following
    return reached


def artifact_links(state: ProjectState) -> LinkReport:
    """Every link the registered kinds derive from the project's files, and every refusal."""
    kinds = link_kinds()
    report = LinkReport()
    for art in sorted(state.artifacts.values(), key=lambda a: a.id):
        applicable = [k for k in sorted(kinds.values(), key=lambda k: k.id) if art.kind in k.artifact_kinds]
        if not applicable:
            continue
        data, why = verified_bytes(art)
        if data is None:
            report.refused.append(RefusedLink(art.id, why))
            continue
        from nirmaan.integrations.veritriage import parse_design

        name = Path(art.location).name
        graph = parse_design(name, data)
        nodes = {n["id"]: n for n in graph["nodes"]}
        for kind in applicable:
            for node_id, rationale in sorted(_walk(graph, name, kind).items()):
                node = nodes.get(node_id)
                if node is None or node["kind"] not in kind.node_kinds:
                    continue
                report.nodes.setdefault(node_id, node)
                report.links.append(DesignLink(art.id, kind.id, node_id, node["kind"], node["name"],
                                               rationale, art.digest))
    return report


# --- The question: which requirements are not backed? --------------------------------------


@dataclass(frozen=True)
class ItemStatus:
    item: str
    kind: str
    name: str
    artifact: str
    status: str  # passed, failed, not_run, not_cited, unverifiable
    reason: str
    run: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class RequirementStatus:
    requirement: str
    text: str
    source: str
    section: str
    backed: bool
    reasons: tuple[str, ...]
    items: tuple[ItemStatus, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _names(run: ToolRun, location: str) -> bool:
    target = Path(location).resolve()
    return any(p.strip() and (p.strip() == location or Path(p.strip()).resolve() == target)
               for value in run.params.values() for p in value.split(","))


def _unaccepted(state: ProjectState, task_id: str) -> str:
    """Why the claims and attestations on the producing task were not enough, when there are any."""
    kinds = [state.evidence[e].kind for e in (state.tasks[task_id].evidence if task_id in state.tasks else ())
             if e in state.evidence]
    claims = sum(k is EvidenceKind.CLAIM for k in kinds)
    attested = sum(k is EvidenceKind.HUMAN_ATTESTATION for k in kinds)
    if not claims and not attested:
        return ""
    return (f" ({claims} claim record(s) and {attested} human attestation record(s) on {task_id} "
            "do not count: only a passing, cited tool run does)")


def holding_artifact(state: ProjectState, item: VerificationItem) -> Artifact | None:
    """The artifact whose file holds the item: its recorded one, or, for an item planned before its
    file existed (M29), the latest recorded artifact of that file name. Derived on every call."""
    if item.artifact:
        return state.artifacts.get(item.artifact)
    named = [a for a in state.artifacts.values() if a.location and Path(a.location).name == item.file]
    return named[-1] if named else None


def _item_status(state: ProjectState, item: VerificationItem, kinds: dict[str, ItemKind]) -> ItemStatus:
    art = holding_artifact(state, item)

    def status(word: str, reason: str, run: str | None = None, evidence: str | None = None) -> ItemStatus:
        return ItemStatus(item.id, item.kind, item.name, art.id if art else item.artifact, word, reason, run,
                          evidence)

    kind = kinds.get(item.kind)
    if kind is None:
        return status("unverifiable", f"unknown verification-item kind {item.kind!r}")
    if art is None and item.file:
        return status("unverifiable", f"no recorded artifact holds {item.file} yet (planned in {item.plan})")
    if art is None:
        return status("unverifiable", f"its artifact {item.artifact} is not recorded")
    data, why = verified_bytes(art)
    if data is None:
        return status("unverifiable", why)
    if item.name not in data.decode("utf-8", errors="replace"):
        return status("unverifiable", f"{item.name!r} does not occur in {art.location}")
    note = _unaccepted(state, art.task)
    runs = [r for r in state.tool_runs.values() if r.tool in kind.tools and _names(r, art.location)]
    if not runs:
        return status("not_run", f"no recorded run of {' or '.join(kind.tools)} names {art.location}{note}")
    latest = runs[-1]
    if not latest.succeeded:
        return status("failed", f"the latest run {latest.id} ({latest.tool}) failed: {latest.summary}{note}",
                      latest.id)
    cited = sorted(e.id for e in state.evidence.values()
                   if e.tool_run == latest.id and e.kind is EvidenceKind.TOOL_RUN and e.substantiated)
    if not cited:
        return status("not_cited", f"the latest run {latest.id} ({latest.tool}) passed but is not cited by "
                                   f"substantiated tool-run evidence{note}", latest.id)
    return status("passed", f"{latest.id} ({latest.tool}) passed on {art.location}, cited by {cited[0]}",
                  latest.id, cited[0])


def requirement_coverage(state: ProjectState) -> list[RequirementStatus]:
    """Every recorded requirement, backed or not, with each proving item's status. Sorted by ID."""
    kinds = item_kinds()
    statuses = {i.id: _item_status(state, i, kinds) for i in state.verification_items.values()}
    result = []
    for req in sorted(state.spec_requirements.values(), key=lambda r: r.id):
        items = tuple(statuses[i.id] for i in sorted(state.verification_items.values(), key=lambda i: i.id)
                      if req.id in i.proves)
        if not items:
            reasons: tuple[str, ...] = ("no verification item is recorded as proving it",)
        else:
            reasons = tuple(f"{s.item} ({s.kind}): {s.reason}" for s in items if s.status != "passed")
        result.append(RequirementStatus(req.id, req.text, req.source, req.section,
                                        bool(items) and not reasons, reasons, items))
    return result


def unbacked_requirements(state: ProjectState) -> list[RequirementStatus]:
    """Which requirements are not yet backed by passing verification evidence? One call."""
    return [r for r in requirement_coverage(state) if not r.backed]


# --- The graph, joined ------------------------------------------------------------------------


def engineering_graph(state: ProjectState, links: LinkReport | None = None,
                      coverage: list[RequirementStatus] | None = None) -> dict:
    """The trace graph plus linked design nodes, spec requirements, and verification items."""
    links = links if links is not None else artifact_links(state)
    coverage = coverage if coverage is not None else requirement_coverage(state)
    graph = trace_graph(state)
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = list(graph["edges"])
    for node_id, node in sorted(links.nodes.items()):
        nodes.setdefault(node_id, {"id": node_id, "kind": f"design:{node['kind']}", "label": node["name"]})
    for link in links.links:
        edges.append({"from": link.artifact, "relation": link.kind, "to": link.node})
    status = {s.item: s for r in coverage for s in r.items}
    for req in coverage:
        rid = f"req:{req.requirement}"
        nodes[rid] = {"id": rid, "kind": "spec_requirement", "label": req.text, "backed": req.backed}
        edges.append({"from": rid, "relation": "quoted_from", "to": req.source})
    for item in sorted(state.verification_items.values(), key=lambda i: i.id):
        nodes[item.id] = {"id": item.id, "kind": f"verification_item:{item.kind}", "label": item.name,
                          "status": status[item.id].status if item.id in status else None}
        held = status[item.id].artifact if item.id in status else item.artifact
        if held:
            edges.append({"from": item.id, "relation": "held_in", "to": held})
        if item.plan:  # M29: declared by an approved plan before its file existed
            edges.append({"from": item.id, "relation": "planned_in", "to": item.plan})
        for rid in item.proves:
            edges.append({"from": item.id, "relation": "proves", "to": f"req:{rid}"})
        if item.id in status and status[item.id].run:
            edges.append({"from": item.id, "relation": "run_in", "to": status[item.id].run})
    # Sorted, so a state and its saved-and-reloaded copy give the same graph.
    return {"nodes": sorted(nodes.values(), key=lambda n: n["id"]),
            "edges": sorted(edges, key=lambda e: (e["from"], e["relation"], e["to"])),
            "refused": [asdict(r) for r in links.refused]}


# --- The export section ----------------------------------------------------------------------


def export_section(org, state: ProjectState, w, folder) -> list[str]:
    """``engineering_graph.json`` and ``requirement_gaps.md`` for the export's evidence folder."""
    links = artifact_links(state)
    coverage = requirement_coverage(state)
    unbacked = [r for r in coverage if not r.backed]
    w.json(f"{folder.id}/engineering_graph.json", {
        "project": state.project.id,
        "links": [asdict(l) for l in links.links],
        "refused": [asdict(r) for r in links.refused],
        "requirements": [r.to_dict() for r in coverage],
        "unbacked": [r.to_dict() for r in unbacked],
        "graph": engineering_graph(state, links, coverage),
    })
    lines = ["# Requirements not yet backed by passing verification evidence", "",
             f"{len(coverage) - len(unbacked)} of {len(coverage)} recorded requirements are backed. "
             "Backed means every verification item declared to prove it has a passing, cited, substantiated "
             "tool run over its digest-checked file. Claims and attestations never count.", ""]
    for req in unbacked:
        lines += [f"## `{req.requirement}` {req.text}", ""] + [f"- {r}" for r in req.reasons] + [""]
    if links.refused:
        lines += ["## Refused design links", ""] + [f"- `{r.artifact}`: {r.reason}" for r in links.refused] + [""]
    w.text(f"{folder.id}/requirement_gaps.md", lines)
    return ["engineering_graph.json", "requirement_gaps.md"]
