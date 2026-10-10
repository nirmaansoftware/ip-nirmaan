"""Work packets become prompts (M20): four scopes, a declared citation set, nothing else.

A :class:`WorkPrompt` is rendered from exactly the packet's four knowledge
scopes, as four sections in fixed order: Company, Domain, Project, Task.
Packet memory is never rendered (it may hold a task's tool inputs, which the
runtime uses and the model does not need).

Every evidence record and tool run the seat may rely on is declared as a
citation. Nirmaan IDs contain ``:`` and ``#``, which the M17 token grammar does
not allow, so an evidence token uses the ID with both replaced by ``.``; the
prompt keeps the mapping back to the real ID. Approved upstream artifacts are
citable too (M23), and a recorded file's content is rendered only while its
digest still matches; a task that works only from approved inputs never sees
an unapproved one. Rendering goes through the bridge, so the text shown by
``nirmaan run --dry-run`` is exactly the text a provider receives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from nirmaan.runtime.context import ArtifactView, AttemptView, ReviewView, WorkPacket

SCOPES = ("Company", "Domain", "Project", "Task")

_OUTPUT_WORK = (
    '{"uncertainty": number, "outcome": string or null, '
    '"artifacts": [{"kind": string, "title": string, "summary": string}], '
    '"files": [{"path": string, "kind": string, "title": string, "summary": string, "entry": string or null}], '
    '"tool_runs": [string], "claims": [string], '
    '"escalation": null or {"reason": string, "question": string, "options": [string]}, "notes": string}'
)
_FILE_FORMAT = """\
When an output is a file (a specification, RTL, a testbench), describe it in "files" and put its
exact content after the JSON object, once per file:
=== FILE: <path> ===
<content>
=== END FILE ===
Paths are relative (letters, digits, '_', '.', '-', '/'). A file's summary must cite like an
artifact's. "entry" names what a tool starts from, such as the top module. The platform writes
the files and runs the checks your task's evidence requirements name over them; you cannot run
or report those checks yourself."""
_OUTPUT_REVIEW = '{"verdict": "approve" or "request_changes", "comments": string, "uncertainty": number}'

WORK_SYSTEM = f"""\
You fill one seat in an engineering organization whose work is checked, not trusted.
Rules:
- Use only the four sections you are given. Do not assume facts they do not contain.
- Every artifact summary must cite at least one token from the citation list, written exactly.
  An artifact that cites nothing is discarded, and a token that is not on the list is removed.
- List in "tool_runs" only run IDs from the citation list. Naming a run that never happened
  rejects your whole result.
- Never claim that a tool ran, or that anything was verified or approved. Put statements you
  cannot cite in "claims"; they are recorded and prove nothing.
- Declare your uncertainty, from 0 (certain) to 1. If the evidence does not support a
  conclusion, escalate instead of guessing.
Answer with one JSON object and nothing else, except the file blocks described below:
{_OUTPUT_WORK}
{_FILE_FORMAT}"""

REVIEW_SYSTEM = f"""\
You are an independent reviewer in an engineering organization whose work is checked, not trusted.
You did not produce the work under review. Judge it only against the evidence you are given.
Rules:
- Your comments must cite at least one token from the citation list, written exactly.
  A review that cites nothing is not recorded, and a token that is not on the list is removed.
- Approve only if the conclusion follows from substantiated evidence. Otherwise request
  changes and say what is missing.
- Declare your uncertainty, from 0 (certain) to 1.
Answer with one JSON object and nothing else:
{_OUTPUT_REVIEW}"""

_UNSAFE = re.compile(r"[^A-Za-z0-9._\-]")


@dataclass(frozen=True)
class Citable:
    """One record the seat may cite: its token, and the real ID it stands for."""

    kind: str
    ref: str
    target: str
    label: str = ""

    @property
    def token(self) -> str:
        return f"[{self.kind}:{self.ref}]"


@dataclass(frozen=True)
class ToolNote:
    """A pre-flight tool call: the run it made, or why it was not run (``run`` is None)."""

    tool: str
    run: str | None
    succeeded: bool
    summary: str


@dataclass(frozen=True)
class WorkPrompt:
    mode: str
    system: str
    task: str
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    citations: tuple[Citable, ...]
    outcomes: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    #: What a model must offer to serve this prompt (M31), derived from the seat's work.
    needs: tuple[str, ...] = ()

    def render(self) -> str:
        from nirmaan.integrations.veritriage import render_prompt

        return render_prompt(self)

    def resolve(self, token: str) -> str | None:
        return next((c.target for c in self.citations if c.token == token), None)


def _company(packet: WorkPacket) -> tuple[str, ...]:
    lines = [f"Company: {packet.company.name}"]
    lines += [f"{p.id} {p.title}: {p.statement}" for p in packet.company.constitution]
    return tuple(lines)


def _domain(packet: WorkPacket) -> tuple[str, ...]:
    lines: list[str] = []
    for s in packet.domain.skills:
        lines.append(f"Skill {s.name} ({s.id})")
        for items, label in ((s.procedures, "procedure"), (s.constraints, "constraint"),
                             (s.common_failure_modes, "failure mode"), (s.validation_criteria, "validation"),
                             (s.knowledge_sources, "knowledge")):
            lines += [f"{s.name} {label}: {item}" for item in items]
    return tuple(lines) or ("No skills are recorded for this task.",)


def _project(packet: WorkPacket) -> tuple[str, ...]:
    p = packet.project
    lines = [f"Requirement: {p.requirement}", f"Intent: {p.intent or 'unrecognized'}"]
    if p.features:
        lines.append(f"Features: {', '.join(p.features)}")
    lines += [f"Parameter {k} = {v}" for k, v in sorted(p.parameters.items())]
    lines += [f"Assumption {a.id}: {a.note} (open question: {a.question})" for a in p.assumptions]
    lines += [f"Decision {d.id}: {d.statement} (rationale: {d.rationale})" for d in p.decisions]
    return tuple(lines)


def _citations(packet: WorkPacket, tools: tuple[ToolNote, ...]) -> list[Citable]:
    found: dict[str, Citable] = {}
    for ev in packet.task.evidence:
        found.setdefault(ev.id, Citable("evidence", _UNSAFE.sub(".", ev.id), ev.id, f"{ev.kind}: {ev.description}"))
        if ev.tool_run:
            found.setdefault(ev.tool_run, Citable("run", ev.tool_run, ev.tool_run, ev.description))
    for note in tools:
        if note.run:
            found.setdefault(note.run, Citable("run", note.run, note.run, f"{note.tool}: {note.summary}"))
    for review in packet.task.reviews:  # a recorded review is citable; it is not evidence (M27)
        found.setdefault(review.id, Citable("review", _UNSAFE.sub(".", review.id), review.id,
                                            f"{review.verdict} by {review.reviewer}"))
    for art in packet.task.upstream_artifacts:  # only what the organization approved is citable
        if art.trusted:
            found.setdefault(art.id, Citable("artifact", _UNSAFE.sub(".", art.id), art.id,
                                             f"{art.kind}: {art.title} (approved)"))
    return list(found.values())


def _content(art: ArtifactView, label: str) -> list[str]:
    """A recorded file's verified content, in the same block format a seat writes files in."""
    if art.content is not None:
        text = art.content if art.content.endswith("\n") else art.content + "\n"
        name = (art.location or "").rsplit("/", 1)[-1]
        return [f"Content of {label} ({art.digest}):\n=== FILE: {name} ===\n{text}=== END FILE ==="]
    if art.content_problem:
        return [f"Content of {label} is withheld: {art.content_problem}"]
    return []


def _task(packet: WorkPacket, mode: str, cites: list[Citable], tools: tuple[ToolNote, ...]) -> tuple[str, ...]:
    t = packet.task
    token = {c.target: c.token for c in cites}
    lines = [f"Task {t.id}: {t.title} ({t.kind}, {t.status})",
             f"Your seat: {packet.role.name} ({packet.role.role})"]
    if mode == "review":
        lines.append(f"The work under review was produced by {t.owner}; you are a different seat.")
    if t.expected_outputs:
        lines.append(f"Expected outputs: {', '.join(t.expected_outputs)}")
    if t.outcomes:
        lines.append(f"Outcomes (conclude exactly one): {', '.join(t.outcomes)}")
    for req in t.evidence_requirements:
        tools_named = f"; tools: {', '.join(req.tools)}" if req.tools else ""
        kinds = dict.fromkeys(k for b in req.files if not b.upstream for k in b.kinds)
        upstream = dict.fromkeys(k for b in req.files if b.upstream for k in b.kinds)
        if kinds:
            tools_named += f"; run by the platform over your {', '.join(kinds)} files"
        if upstream:
            tools_named += (f", with the approved {', '.join(upstream)}" if kinds
                            else f"; run by the platform over the approved {', '.join(upstream)}")
        if req.before_review:
            tools_named += "; must be met before review"
        if req.when_produced:
            tools_named += f"; applies only if you produce a {' or '.join(req.when_produced)} file"
        if req.when_upstream:
            tools_named += f"; applies only to work built on a {' or '.join(req.when_upstream)}"
        accepts = ", ".join(k.value for k in req.accepts)
        lines.append(f"Evidence requirement: {req.description} (accepts: {accepts}{tools_named})")
    lines.append(f"Permitted tools: {', '.join(packet.tools) or 'none'}")
    for art in t.upstream_artifacts:
        if t.approved_inputs and not art.trusted:
            lines.append(f"Upstream artifact {art.id} withheld: it is {art.assurance}, not approved")
            continue
        body = f": {art.summary}" if art.summary else ""
        cite = f" {token[art.id]}" if art.id in token else ""
        lines.append(f"Upstream artifact{cite} {art.title} ({art.kind}, {art.assurance}){body}")
        lines += _content(art, token.get(art.id, art.title))
    if mode == "review":
        for art in t.artifacts:
            lines.append(f"Artifact under review: {art.title} ({art.kind}): {art.summary or '(no content)'}")
            lines += _content(art, art.title)
    for ev in t.evidence:
        state = "substantiated" if ev.substantiated else "NOT substantiated"
        run = f", tool run {token[ev.tool_run]}" if ev.tool_run else ""
        lines.append(f"Evidence {token[ev.id]} on {ev.task}: {ev.kind}, {state}{run}: {ev.description}")
    for note in tools:
        if note.run:
            outcome = "succeeded" if note.succeeded else "failed"
            lines.append(f"Tool run {token[note.run]} {note.tool} {outcome} for this task: {note.summary}")
        else:
            lines.append(f"Tool {note.tool} was not run: {note.summary}")
    if mode == "work" and t.attempts:
        lines += _repair(t.attempts, t.reviews, token)
    elif mode == "review":
        lines += _sent_back(t.attempts, t.reviews, token)
    if t.escalation_path:
        lines.append(f"Escalation path: {' -> '.join(t.escalation_path)}")
    return tuple(lines)


def _sent_back(attempts: tuple[AttemptView, ...], reviews: tuple[ReviewView, ...],
               token: dict[str, str]) -> list[str]:
    """Every change request on a superseded submission (M27), with its citation token."""
    by_id = {r.id: r for r in reviews}
    return [f"Review {token.get(r.id, r.id)} by {r.reviewer} on submission {a.number} requested "
            f"changes: {r.comments or '(no comments)'}"
            for a in attempts for r in (by_id[i] for i in a.reviews if i in by_id)
            if r.verdict == "request_changes"]


def _repair(attempts: tuple[AttemptView, ...], reviews: tuple[ReviewView, ...], token: dict[str, str]) -> list[str]:
    """Repair context: submissions a review sent back (M27), then this round's refused attempts (M26)."""
    lines: list[str] = []
    sent = [a for a in attempts if a.reviews]
    if sent:
        lines.append(f"Repair after review: submission {sent[-1].number} was sent back by an independent "
                     "review and nothing from it counts. Address every finding and answer again in full; your "
                     "new files go through every check and to review again.")
        lines += _sent_back(tuple(sent), reviews, token)
        for art in sent[-1].artifacts:
            lines += _content(art, f"sent-back file {art.title}")
    refused = [a for a in attempts if not a.reviews and (not sent or a.number > sent[-1].number)]
    if not refused:
        return lines
    latest = refused[-1]
    lines.append(f"Repair: your previous attempt {latest.number} was refused and nothing from it counts. "
                 "Fix what failed and answer again in full; files from a refused attempt are never reviewed.")
    lines += [f"Attempt {a.number} was refused: {a.refusal}" for a in refused]
    for failed in latest.failed_runs:
        run = token.get(failed.run, failed.run)
        ev = f", evidence {token[failed.evidence]}" if failed.evidence in token else ""
        lines.append(f"Failed run {run} {failed.tool}{ev}: {failed.summary}")
        if failed.excerpt:
            body = "\n".join(f"| {line}" for line in failed.excerpt)
            lines.append(f"Log excerpt of {run} ({failed.excerpt_note}):\n{body}")
        else:
            lines.append(f"No log excerpt of {run}: {failed.excerpt_note}")
    for art in latest.artifacts:
        lines += _content(art, f"refused file {art.title}")
    return lines


def render_work_prompt(packet: WorkPacket, mode: str = "work", tools: tuple[ToolNote, ...] = ()) -> WorkPrompt:
    """Render a packet for a seat. ``mode`` is ``work`` (the owner) or ``review``."""
    if mode not in ("work", "review"):
        raise ValueError(f"unknown prompt mode {mode!r}")
    t = packet.task
    cites = _citations(packet, tools)
    if mode == "review":
        system, ask = REVIEW_SYSTEM, f"Review the submitted work of task {t.id} independently."
    else:
        system = WORK_SYSTEM
        ask = f"Produce {', '.join(t.expected_outputs) or 'the task output'} for task {t.id}"
        ask += f" and conclude exactly one outcome: {', '.join(t.outcomes)}." if t.outcomes else "."
    sections = tuple(zip(SCOPES, (_company(packet), _domain(packet), _project(packet),
                                  _task(packet, mode, cites, tools))))
    from nirmaan.runtime.selection import seat_needs

    return WorkPrompt(mode=mode, system=system, task=ask, sections=sections, citations=tuple(cites),
                      outcomes=t.outcomes, outputs=t.expected_outputs, needs=seat_needs(packet))
