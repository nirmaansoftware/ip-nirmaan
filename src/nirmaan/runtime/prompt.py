"""Work packets become prompts (M20): four scopes, a declared citation set, nothing else.

A :class:`WorkPrompt` is rendered from exactly the packet's four knowledge
scopes, as four sections in fixed order: Company, Domain, Project, Task.
Packet memory is never rendered (it may hold a task's tool inputs, which the
runtime uses and the model does not need).

Every evidence record and tool run the seat may rely on is declared as a
citation. Nirmaan IDs contain ``:`` and ``#``, which the M17 token grammar does
not allow, so an evidence token uses the ID with both replaced by ``.``; the
prompt keeps the mapping back to the real ID. Rendering goes through the
bridge, so the text shown by ``nirmaan run --dry-run`` is exactly the text a
provider receives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from nirmaan.runtime.context import WorkPacket

SCOPES = ("Company", "Domain", "Project", "Task")

_OUTPUT_WORK = (
    '{"uncertainty": number, "outcome": string or null, '
    '"artifacts": [{"kind": string, "title": string, "summary": string}], '
    '"tool_runs": [string], "claims": [string], '
    '"escalation": null or {"reason": string, "question": string, "options": [string]}, "notes": string}'
)
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
Answer with one JSON object and nothing else:
{_OUTPUT_WORK}"""

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

    def render(self) -> str:
        from nirmaan.integrations.veritriage import render_prompt

        return render_prompt(self)

    def resolve(self, token: str) -> str | None:
        return next((c.target for c in self.citations if c.token == token), None)


def _company(packet: WorkPacket) -> tuple[str, ...]:
    lines = [f"Company: {packet.company['name']}"]
    lines += [f"{p['id']} {p['title']}: {p['statement']}" for p in packet.company["constitution"]]
    return tuple(lines)


def _domain(packet: WorkPacket) -> tuple[str, ...]:
    lines: list[str] = []
    for s in packet.domain["skills"]:
        lines.append(f"Skill {s['name']} ({s['id']})")
        for field, label in (("procedures", "procedure"), ("constraints", "constraint"),
                             ("common_failure_modes", "failure mode"), ("validation_criteria", "validation"),
                             ("knowledge_sources", "knowledge")):
            lines += [f"{s['name']} {label}: {item}" for item in s[field]]
    return tuple(lines) or ("No skills are recorded for this task.",)


def _project(packet: WorkPacket) -> tuple[str, ...]:
    p = packet.project
    lines = [f"Requirement: {p['requirement']}", f"Intent: {p['intent'] or 'unrecognized'}"]
    if p["features"]:
        lines.append(f"Features: {', '.join(p['features'])}")
    lines += [f"Parameter {k} = {v}" for k, v in sorted(p["parameters"].items())]
    lines += [f"Assumption {a['id']}: {a['note']} (open question: {a['question']})" for a in p["assumptions"]]
    lines += [f"Decision {d['id']}: {d['statement']} (rationale: {d['rationale']})" for d in p["decisions"]]
    return tuple(lines)


def _citations(packet: WorkPacket, tools: tuple[ToolNote, ...]) -> list[Citable]:
    found: dict[str, Citable] = {}
    for ev in packet.task["evidence"]:
        found.setdefault(ev["id"], Citable("evidence", _UNSAFE.sub(".", ev["id"]), ev["id"],
                                           f"{ev['kind']}: {ev['description']}"))
        if ev["tool_run"]:
            found.setdefault(ev["tool_run"], Citable("run", ev["tool_run"], ev["tool_run"], ev["description"]))
    for note in tools:
        if note.run:
            found.setdefault(note.run, Citable("run", note.run, note.run, f"{note.tool}: {note.summary}"))
    return list(found.values())


def _task(packet: WorkPacket, mode: str, cites: list[Citable], tools: tuple[ToolNote, ...]) -> tuple[str, ...]:
    t: dict[str, Any] = packet.task
    token = {c.target: c.token for c in cites}
    lines = [f"Task {t['id']}: {t['title']} ({t['kind']}, {t['status']})",
             f"Your seat: {packet.role['name']} ({packet.role['role']})"]
    if mode == "review":
        lines.append(f"The work under review was produced by {t['owner']}; you are a different seat.")
    if t["expected_outputs"]:
        lines.append(f"Expected outputs: {', '.join(t['expected_outputs'])}")
    if t["outcomes"]:
        lines.append(f"Outcomes (conclude exactly one): {', '.join(t['outcomes'])}")
    for req in t["evidence_requirements"]:
        tools_named = f"; tools: {', '.join(req['tools'])}" if req["tools"] else ""
        lines.append(f"Evidence requirement: {req['description']} (accepts: {', '.join(req['accepts'])}{tools_named})")
    lines.append(f"Permitted tools: {', '.join(packet.tools) or 'none'}")
    for art in t["upstream_artifacts"]:
        body = f": {art['summary']}" if art["summary"] else ""
        lines.append(f"Upstream artifact {art['title']} ({art['kind']}, {art['assurance']}){body}")
    if mode == "review":
        for art in t["artifacts"]:
            lines.append(f"Artifact under review: {art['title']} ({art['kind']}): {art['summary'] or '(no content)'}")
    for ev in t["evidence"]:
        state = "substantiated" if ev["substantiated"] else "NOT substantiated"
        run = f", tool run {token[ev['tool_run']]}" if ev["tool_run"] else ""
        lines.append(f"Evidence {token[ev['id']]} on {ev['task']}: {ev['kind']}, {state}{run}: {ev['description']}")
    for note in tools:
        if note.run:
            outcome = "succeeded" if note.succeeded else "failed"
            lines.append(f"Tool run {token[note.run]} {note.tool} {outcome} for this task: {note.summary}")
        else:
            lines.append(f"Tool {note.tool} was not run: {note.summary}")
    if t["escalation_path"]:
        lines.append(f"Escalation path: {' -> '.join(t['escalation_path'])}")
    return tuple(lines)


def render_work_prompt(packet: WorkPacket, mode: str = "work", tools: tuple[ToolNote, ...] = ()) -> WorkPrompt:
    """Render a packet for a seat. ``mode`` is ``work`` (the owner) or ``review``."""
    if mode not in ("work", "review"):
        raise ValueError(f"unknown prompt mode {mode!r}")
    t = packet.task
    cites = _citations(packet, tools)
    if mode == "review":
        system, ask = REVIEW_SYSTEM, f"Review the submitted work of task {t['id']} independently."
    else:
        system = WORK_SYSTEM
        ask = f"Produce {', '.join(t['expected_outputs']) or 'the task output'} for task {t['id']}"
        ask += f" and conclude exactly one outcome: {', '.join(t['outcomes'])}." if t["outcomes"] else "."
    sections = tuple(zip(SCOPES, (_company(packet), _domain(packet), _project(packet),
                                  _task(packet, mode, cites, tools))))
    return WorkPrompt(mode=mode, system=system, task=ask, sections=sections, citations=tuple(cites),
                      outcomes=tuple(t["outcomes"]), outputs=tuple(t["expected_outputs"]))
