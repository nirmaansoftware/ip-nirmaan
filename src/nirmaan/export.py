"""The project deliverable export: a numbered tree, as a view over project state.

The layout is the declared folder table (``nirmaan.company.deliverables``, plus
any ``register_folder`` overlays); this module names no folder. It is a read:
it never raises an assurance level, never fills a missing deliverable, writes
nothing back into project state, and records no audit entry. A broken audit
chain is exported and reported loudly. The same state always gives the same
bytes: everything is sorted by ID and the only timestamps are recorded ones.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from nirmaan.company import deliverables
from nirmaan.models import (
    ApprovalState,
    Artifact,
    Assurance,
    DeliverableFolder,
    ExportSection,
    ProjectState,
    Task,
    TaskKind,
    TaskStatus,
)
from nirmaan.org import Organization
from nirmaan.work.audit import verify_chain
from nirmaan.work.trace import untraced_requirements


class ExportError(Exception):
    """The export cannot run as asked (a bad folder table, or a non-empty output directory)."""


# --- The folder table, as a registry ----------------------------------------------------------

_OVERLAY: dict[str, DeliverableFolder] = {}


def register_folder(folder: DeliverableFolder) -> None:
    """Add a folder, or replace the folder with the same ID (a remap)."""
    _OVERLAY[folder.id] = folder


def unregister_folder(folder_id: str) -> None:
    """Remove an overlay; a replaced built-in folder comes back."""
    _OVERLAY.pop(folder_id, None)


def folders() -> list[DeliverableFolder]:
    """The effective table: the declared folders with overlays applied, by ID."""
    table = {f.id: f for f in deliverables.DELIVERABLE_FOLDERS}
    table.update(_OVERLAY)
    return sorted(table.values(), key=lambda f: f.id)


def validate_folders(table: list[DeliverableFolder]) -> None:
    """Each folder, kind, capability, and section is claimed at most once."""
    seen: dict[tuple[str, str], str] = {}
    for folder in table:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", folder.id) or folder.id in (".", ".."):
            raise ExportError(f"folder ID {folder.id!r} is not a plain directory name")
        claims = (("folder", (folder.id,)), ("artifact kind", folder.artifact_kinds),
                  ("capability", folder.capabilities), ("section", tuple(s.value for s in folder.sections)),
                  ("tool", folder.tool_runs))
        if folder.tool_runs and ExportSection.TOOL_RUNS in folder.sections:
            raise ExportError(f"{folder.id} lists every tool run already; it cannot also list some by tool")
        for what, values in claims:
            for value in values:
                if (what, value) in seen:
                    raise ExportError(f"{what} {value!r} is claimed by both {seen[what, value]} and {folder.id}")
                seen[what, value] = folder.id


#: Writers for sections that live outside this module: (org, state, writer, folder) -> files written.
_SECTION_WRITERS: dict[ExportSection, Callable[..., list[str]]] = {}


def register_section_writer(section: ExportSection, writer: Callable[..., list[str]]) -> None:
    """Give a section its writer. The folder table decides where (and whether) it is written."""
    _SECTION_WRITERS[section] = writer


# --- Report ----------------------------------------------------------------------------------

_MEANING = {
    Assurance.PLANNED: "planned only: not produced",
    Assurance.EXECUTED: "executed only: submitted by its owner, not verified by recorded evidence",
    Assurance.VERIFIED: "verified: every evidence requirement of its task is met; not approved",
    Assurance.APPROVED: "approved: verified, independently reviewed, and approved by an authorized role",
}


@dataclass(frozen=True)
class MissingDeliverable:
    folder: str | None
    kind: str
    task: str
    title: str
    status: str


@dataclass
class ExportReport:
    out: Path
    files: list[str] = field(default_factory=list)
    artifacts: int = 0
    missing: list[MissingDeliverable] = field(default_factory=list)
    not_required: list[MissingDeliverable] = field(default_factory=list)
    unfiled: list[str] = field(default_factory=list)
    chain_problems: list[str] = field(default_factory=list)
    gates: int = 0
    signed_off: int = 0


# --- Writing ---------------------------------------------------------------------------------


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


class _Writer:
    def __init__(self, out: Path, report: ExportReport) -> None:
        self._out = out
        self._report = report

    def bytes(self, rel: str, data: bytes) -> str:
        path = self._out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._report.files.append(rel)
        return _sha(data)

    def text(self, rel: str, lines: list[str]) -> str:
        return self.bytes(rel, ("\n".join(lines).rstrip("\n") + "\n").encode("utf-8"))

    def json(self, rel: str, data: Any) -> str:
        return self.bytes(rel, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    def copy(self, rel: str, source: str) -> tuple[str | None, str]:
        """Copy a referenced file. Returns (sha256, note); sha is None when nothing was copied."""
        try:
            path = Path(source)
            if not path.is_file():
                return None, "not a readable file at export time (for example a session ID); recorded as given"
            return self.bytes(rel, path.read_bytes()), "copied as found at export time"
        except (OSError, ValueError) as exc:
            return None, f"not a readable file at export time ({type(exc).__name__}); recorded as given"


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _local(state: ProjectState, item_id: str) -> str:
    prefix = f"{state.project.id}:"
    return _safe(item_id[len(prefix):] if item_id.startswith(prefix) else item_id)


def _label(art: Artifact) -> str:
    return art.assurance.value.upper()


def _route(table: list[DeliverableFolder], kind: str, capability: str | None) -> DeliverableFolder | None:
    for folder in table:
        if kind in folder.artifact_kinds:
            return folder
    for folder in table:
        if capability and capability in folder.capabilities:
            return folder
    return None


def _evidence(state: ProjectState, ids: tuple[str, ...]) -> list[dict]:
    rows = []
    for ev_id in ids:
        ev = state.evidence.get(ev_id)
        if ev is None:
            rows.append({"id": ev_id, "recorded": False})
            continue
        rows.append({"id": ev.id, "kind": ev.kind.value, "description": ev.description,
                     "substantiated": ev.substantiated, "recorded_by": ev.recorded_by,
                     "reference": ev.reference, "tool_run": ev.tool_run})
    return rows


def _task_summary(task: Task | None, task_id: str) -> dict:
    if task is None:
        return {"id": task_id, "recorded": False}
    return {"id": task.id, "title": task.title, "capability": task.capability, "owner": task.owner,
            "reviewer": task.reviewer, "approver": task.approver, "status": task.status.value}


def _write_artifact(state: ProjectState, w: _Writer, folder: DeliverableFolder, art: Artifact) -> str:
    task = state.tasks.get(art.task)
    stem = f"{folder.id}/{_local(state, art.id)}.{_label(art)}"
    content_rel = f"{stem}.md"
    content = [
        f"# {art.title}",
        "",
        f"- Artifact: `{art.id}`",
        f"- Kind: {art.kind}",
        f"- Assurance: **{_label(art)}** ({_MEANING[art.assurance]})",
        f"- Produced by: {art.produced_by}",
        f"- Task: `{art.task}`" + (f" {task.title}" if task else " (not in project state)"),
        f"- Recorded location: {art.location or 'none'}",
        "",
        "## Recorded content",
        "",
        art.summary or "_No content was recorded with this artifact._",
    ]
    content_sha = w.text(content_rel, content)
    location_rel, location_sha, location_note = None, None, "no location was recorded"
    if art.location:
        candidate = f"{stem}.{_safe(Path(art.location).name) or 'location'}"
        location_sha, location_note = w.copy(candidate, art.location)
        location_rel = candidate if location_sha else None
        if location_sha and not art.digest:
            location_note += "; no digest was recorded with the artifact, so it cannot be checked"
        elif location_sha and art.digest == f"sha256:{location_sha}":
            location_note += "; matches the digest recorded with the artifact"
        elif location_sha:
            location_note += "; DOES NOT MATCH the digest recorded with the artifact: the file changed since"
    audit = [
        {"sequence": e.sequence, "action": e.action, "actor": e.actor, "at": e.at.isoformat(), "hash": e.hash}
        for e in state.audit
        if e.subject == art.task or art.id in e.details.get("artifacts", ())
    ]
    req = state.project.requirement
    w.json(f"{stem}.provenance.json", {
        "artifact": art.id,
        "kind": art.kind,
        "title": art.title,
        "assurance": art.assurance.value,
        "assurance_meaning": _MEANING[art.assurance],
        "produced_by": art.produced_by,
        "task": _task_summary(task, art.task),
        "requirement": {"id": task.requirement if task else req.id, "text": req.text},
        "inputs": {"artifact_kinds": list(task.inputs) if task else [], "derived_from": list(art.derived_from)},
        "evidence": _evidence(state, task.evidence if task else art.evidence),
        "verified_with": list(art.evidence),
        "reviews": sorted(r.id for r in state.reviews.values() if r.task == art.task),
        "audit": audit,
        "location": {"recorded": art.location, "note": location_note},
        "files": {"content": content_rel, "location_copy": location_rel},
        "hashes": {"record_sha256": _sha(_canonical(art.model_dump(mode="json"))),
                   "content_sha256": content_sha, "location_sha256": location_sha,
                   "recorded_digest": art.digest},
    })
    return content_rel


# --- Sections --------------------------------------------------------------------------------


def _trace(state: ProjectState, w: _Writer, folder: DeliverableFolder, exported: dict[str, str]) -> list[str]:
    tasks = []
    for task in sorted(state.tasks.values(), key=lambda t: t.id):
        if task.kind not in (TaskKind.WORK, TaskKind.DECISION) and not task.artifacts:
            continue
        arts = [state.artifacts[a] for a in task.artifacts if a in state.artifacts]
        tasks.append({
            "id": task.id, "title": task.title, "kind": task.kind.value, "capability": task.capability,
            "status": task.status.value, "owner": task.owner,
            "artifacts": [{"id": a.id, "kind": a.kind, "assurance": a.assurance.value,
                           "exported_as": exported.get(a.id)} for a in arts],
            "evidence": _evidence(state, task.evidence),
        })
    req = state.project.requirement
    untraced = sorted(untraced_requirements(state))
    w.json(f"{folder.id}/requirement_trace.json", {
        "requirement": {"id": req.id, "text": req.text, "submitted_by": req.submitted_by},
        "project": state.project.id,
        "tasks": tasks,
        "untraced": untraced,
    })
    lines = [f"# Requirement trace: {req.id}", "", req.text, ""]
    if untraced:
        lines += ["Completed work without substantiated evidence: " + ", ".join(f"`{t}`" for t in untraced), ""]
    for row in tasks:
        lines.append(f"## `{row['id']}` {row['title']} ({row['status']})")
        lines.append("")
        for a in row["artifacts"]:
            lines.append(f"- artifact `{a['id']}` ({a['kind']}): **{a['assurance'].upper()}**")
        for e in row["evidence"]:
            state_word = "substantiated" if e.get("substantiated") else "NOT substantiated"
            lines.append(f"- evidence `{e['id']}` ({e.get('kind', 'unrecorded')}): {state_word}")
        if not row["artifacts"] and not row["evidence"]:
            lines.append("- nothing produced or recorded yet")
        lines.append("")
    w.text(f"{folder.id}/requirement_trace.md", lines)
    return ["requirement_trace.json", "requirement_trace.md"]


def _tool_runs(state: ProjectState, w: _Writer, folder: DeliverableFolder,
               tools: tuple[str, ...] | None = None) -> list[str]:
    """Every recorded run (or, M44, every run of ``tools``), with its referenced files copied."""
    written = []
    for run in sorted(state.tool_runs.values(), key=lambda r: r.id):
        if tools is not None and run.tool not in tools:
            continue
        base = f"{folder.id}/tool_runs/{_safe(run.id)}"
        refs, used = [], set()
        for index, ref in enumerate(run.references):
            name = _safe(Path(ref).name) if ref else ""
            if not name or name in used or name == "run.json":
                name = f"{index + 1}_{name or 'reference'}"
            sha, note = w.copy(f"{base}/{name}", ref)
            if sha:
                used.add(name)
            refs.append({"reference": ref, "copied_as": f"{base}/{name}" if sha else None,
                         "sha256": sha, "note": note})
        w.json(f"{base}/run.json", {**run.model_dump(mode="json"), "references": refs})
        written.append(f"tool_runs/{_safe(run.id)}/")
    return written


def _reviews(state: ProjectState, w: _Writer, folder: DeliverableFolder) -> list[str]:
    w.json(f"{folder.id}/reviews.json",
           [r.model_dump(mode="json") for r in sorted(state.reviews.values(), key=lambda r: r.id)])
    return ["reviews.json"]


def _audit_chain(state: ProjectState, w: _Writer, folder: DeliverableFolder, problems: list[str]) -> list[str]:
    w.json(f"{folder.id}/audit_chain.json", {
        "project": state.project.id,
        "length": len(state.audit),
        "head_hash": state.audit[-1].hash if state.audit else None,
        "verify_chain": {"intact": not problems, "problems": problems},
        "entries": [e.model_dump(mode="json") for e in state.audit],
    })
    return ["audit_chain.json"]


def _gates(org: Organization, state: ProjectState) -> list[dict]:
    approvals = {e.subject: e for e in state.audit if e.action == "gate.approve"}
    rows = []
    for task in sorted((t for t in state.tasks.values() if t.kind is TaskKind.GATE), key=lambda t: t.id):
        entry = approvals.get(task.id)
        signed = (entry is not None and task.status is TaskStatus.COMPLETED
                  and task.approval_state is ApprovalState.GRANTED)
        spec = org.gates.get(task.gate) if task.gate else None
        rows.append({
            "task": task.id, "gate": task.gate, "name": spec.name if spec else task.title,
            "status": task.status.value, "approval_state": task.approval_state.value, "signed_off": signed,
            "audit": {"sequence": entry.sequence, "actor": entry.actor, "actor_kind": entry.actor_kind.value,
                      "human": bool(entry.details.get("human")), "at": entry.at.isoformat(), "hash": entry.hash}
            if signed and entry else None,
        })
    return rows


def _signoff(org: Organization, state: ProjectState, w: _Writer, folder: DeliverableFolder,
             problems: list[str]) -> list[str]:
    gates = _gates(org, state)
    signed = [g for g in gates if g["signed_off"]]
    w.json(f"{folder.id}/signoff.json", {
        "project": state.project.id, "gates": gates, "signed_off": len(signed),
        "audit_chain_intact": not problems,
    })
    lines = ["# Signoff", "", f"Signed off: {len(signed)} of {len(gates)} gates.", ""]
    if problems:
        lines += ["**WARNING: the audit chain failed verification. These records come from an "
                  "unverified trail and must not be relied on.**", ""]
    lines += ["Only gate approvals the engine recorded appear here. An artifact's own approval is "
              "shown in its sidecar, not as a signoff.", "", "## Signed off", ""]
    lines += [f"- `{g['task']}` {g['name']}: by {g['audit']['actor']} "
              f"({'human' if g['audit']['human'] else g['audit']['actor_kind']}) at {g['audit']['at']}, "
              f"audit #{g['audit']['sequence']} `{g['audit']['hash']}`" for g in signed] or ["None."]
    lines += ["", "## Not signed off", ""]
    lines += [f"- `{g['task']}` {g['name']}: {g['status']}" for g in gates if not g["signed_off"]] or ["None."]
    w.text(f"{folder.id}/signoff.md", lines)
    return ["signoff.json", "signoff.md"]


# --- The export ------------------------------------------------------------------------------


def export_project(org: Organization, state: ProjectState, out: Path,
                   table: list[DeliverableFolder] | None = None) -> ExportReport:
    """Write the deliverable tree for ``state`` into ``out`` (new or empty). Changes no state."""
    table = sorted(table, key=lambda f: f.id) if table is not None else folders()
    validate_folders(table)
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ExportError(f"{out} exists and is not empty; export into a new or empty directory")
    report = ExportReport(out=out, chain_problems=verify_chain(state.audit))
    w = _Writer(out, report)
    problems = report.chain_problems

    placed: dict[str, list[Artifact]] = {f.id: [] for f in table}
    exported: dict[str, str] = {}
    for art in sorted(state.artifacts.values(), key=lambda a: a.id):
        task = state.tasks.get(art.task)
        folder = _route(table, art.kind, task.capability if task else None)
        if folder is None:
            report.unfiled.append(art.id)
            continue
        exported[art.id] = _write_artifact(state, w, folder, art)
        placed[folder.id].append(art)
    report.artifacts = len(exported)

    for task in sorted(state.tasks.values(), key=lambda t: t.id):
        if task.kind not in (TaskKind.WORK, TaskKind.DECISION):
            continue
        produced = {state.artifacts[a].kind for a in task.artifacts if a in state.artifacts}
        for kind in task.expected_outputs:
            if kind in produced:
                continue
            folder = _route(table, kind, task.capability)
            item = MissingDeliverable(folder.id if folder else None, kind, task.id, task.title, task.status.value)
            (report.not_required if task.status is TaskStatus.CANCELLED else report.missing).append(item)

    section_files: dict[str, list[str]] = {f.id: [] for f in table}
    for folder in table:
        for section in folder.sections:
            if section is ExportSection.TRACE:
                section_files[folder.id] += _trace(state, w, folder, exported)
            elif section is ExportSection.TOOL_RUNS:
                section_files[folder.id] += _tool_runs(state, w, folder)
            elif section is ExportSection.REVIEWS:
                section_files[folder.id] += _reviews(state, w, folder)
            elif section is ExportSection.AUDIT_CHAIN:
                section_files[folder.id] += _audit_chain(state, w, folder, problems)
            elif section is ExportSection.SIGNOFF:
                section_files[folder.id] += _signoff(org, state, w, folder, problems)
            elif section in _SECTION_WRITERS:
                section_files[folder.id] += _SECTION_WRITERS[section](org, state, w, folder)
        if folder.tool_runs:  # M44: the runs of the folder's tools, e.g. the lint runs that gated the RTL
            section_files[folder.id] += _tool_runs(state, w, folder, folder.tool_runs)
    gates = _gates(org, state)
    report.gates, report.signed_off = len(gates), sum(1 for g in gates if g["signed_off"])

    for folder in table:
        w.text(f"{folder.id}/README.md", _folder_readme(folder, placed[folder.id], exported, report,
                                                        section_files[folder.id]))
    w.text("INDEX.md", _index(state, table, placed, exported, report, section_files))
    report.files.sort()
    return report


def _artifact_line(art: Artifact, rel: str) -> str:
    return f"- `{rel}`: {art.title} (`{art.id}`, {art.kind}), **{_label(art)}**: {_MEANING[art.assurance]}"


def _missing_line(m: MissingDeliverable) -> str:
    return f"- {m.kind} from `{m.task}` ({m.title}), task status: {m.status}"


def _folder_readme(folder: DeliverableFolder, arts: list[Artifact], exported: dict[str, str],
                   report: ExportReport, sections: list[str]) -> list[str]:
    missing = [m for m in report.missing if m.folder == folder.id]
    not_required = [m for m in report.not_required if m.folder == folder.id]
    lines = [f"# {folder.id}: {folder.title}", ""]
    if folder.description:
        lines += [folder.description, ""]
    lines += [f"Collects artifact kinds: {', '.join(folder.artifact_kinds) or 'none'}.",
              f"Also collects, by task capability: {', '.join(folder.capabilities) or 'none'}.",
              *([f"Lists the recorded runs of: {', '.join(folder.tool_runs)}, pass or fail."]
                if folder.tool_runs else []), "",
              f"## Present ({len(arts)})", ""]
    lines += [_artifact_line(a, exported[a.id].split("/", 1)[1]) for a in arts] or \
             ["Nothing has been produced for this folder."]
    if sections:
        lines += ["", "## Evidence and signoff files", ""] + [f"- `{s}`" for s in sections]
    lines += ["", f"## Missing ({len(missing)})", ""]
    lines += [_missing_line(m) for m in missing] or ["Nothing the plan expects here is missing."]
    if not_required:
        lines += ["", f"## Not required ({len(not_required)})", "",
                  "The tasks that would have produced these were cancelled.", ""]
        lines += [_missing_line(m) for m in not_required]
    return lines


def _index(state: ProjectState, table: list[DeliverableFolder], placed: dict[str, list[Artifact]],
           exported: dict[str, str], report: ExportReport, section_files: dict[str, list[str]]) -> list[str]:
    project, req = state.project, state.project.requirement
    problems = report.chain_problems
    lines = [f"# Deliverables: {project.name}", ""]
    if problems:
        lines += [f"**AUDIT CHAIN FAILED VERIFICATION: {len(problems)} problem(s). Nothing in this export "
                  "can be trusted as recorded until the trail is repaired. First: " + problems[0] + "**", ""]
    else:
        head = state.audit[-1].hash if state.audit else "none"
        lines += [f"Audit chain: intact, {len(state.audit)} entries, head `{head}`.", ""]
    lines += [
        f"- Project: `{project.id}`, planned {project.created_at.isoformat()}",
        f"- Requirement `{req.id}`: {req.text}",
        f"- Organization fingerprint: `{project.organization_fingerprint}`",
        "- This export is a read of recorded project state. Assurance levels are exactly as the engine "
        "recorded them; nothing here was verified, approved, or produced by the export.",
        "",
        "## Assurance levels",
        "",
    ]
    lines += [f"- **{level.value.upper()}**: {_MEANING[level]}" for level in Assurance]
    counts = {level: sum(1 for a in state.artifacts.values() if a.assurance is level) for level in Assurance}
    lines += [
        "",
        "## Summary",
        "",
        f"- Artifacts exported: {report.artifacts} ("
        + ", ".join(f"{level.value.upper()} {counts[level]}" for level in reversed(list(Assurance))) + ")",
        f"- Missing deliverables: {len(report.missing)}",
        f"- Not required (cancelled): {len(report.not_required)}",
        f"- Unfiled artifacts: {len(report.unfiled)}",
        f"- Signoff: {report.signed_off} of {report.gates} gates",
    ]
    for folder in table:
        lines += ["", f"## {folder.id}: {folder.title}", ""]
        lines += [_artifact_line(a, exported[a.id]) for a in placed[folder.id]]
        lines += [f"- `{folder.id}/{s}`" for s in section_files[folder.id]]
        lines += ["- MISSING: " + _missing_line(m)[2:] for m in report.missing if m.folder == folder.id]
        lines += ["- NOT REQUIRED: " + _missing_line(m)[2:] for m in report.not_required if m.folder == folder.id]
        if lines[-1] == "":
            lines.append("- Nothing produced, and nothing planned.")
    orphans = [m for m in report.missing if m.folder is None]
    if report.unfiled or orphans:
        lines += ["", "## Unfiled", "", "No folder in the table collects these, so they are listed, not exported.", ""]
        lines += [f"- artifact `{a}` ({state.artifacts[a].kind}), **{_label(state.artifacts[a])}**"
                  for a in report.unfiled]
        lines += ["- MISSING: " + _missing_line(m)[2:] for m in orphans]
    return lines


# The engineering-graph section (M24) brings its own writer.
from nirmaan import engineering as _engineering  # noqa: E402
from nirmaan import records as _records  # noqa: E402

register_section_writer(ExportSection.ENGINEERING_GRAPH, _engineering.export_section)
register_section_writer(ExportSection.DECISIONS, _records.decisions_section)
register_section_writer(ExportSection.FAILURES, _records.failures_section)
