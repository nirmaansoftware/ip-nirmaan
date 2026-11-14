"""The harness (M73): every setting around the model in a seat's run, in one place, and its fingerprint.

A skill level is earned by a model and a harness together. The harness is
everything around the model in ``run_task``: the knowledge and content budgets,
the attempt and review limits, the system prompts and the order of the
prompt's sections, the text a seat gets when it is asked again, the bounded
log excerpt on a retry, the Claude Code flags and timeout, and the Anthropic
API settings. The code reads each of these from this module (``harness.NAME``),
so there is one copy of each.

Some of a seat's run is code, not a value: how a packet is assembled, how each
prompt line is worded (M68's "beside" line is one), how an answer is parsed
and grounded, how the eval runner fixes the upstream stages. ``CODE`` names
those files, and the fingerprint carries the sha256 of each file's bytes.

``harness_sha256`` is the sha256 of ``fingerprint()``: these settings, the
code digests and the run's own options (an ``--attempts`` override, whether
knowledge documents were given, M67, and the version of the command-line
program the runtime calls the model through: Claude Code's ``claude
--version`` on the claude-code runtime, None on any other). Every eval trial records it
(``EvalResult.harness`` and each ``RecordedAnswer.harness``), and the levels
generator groups trials by skill, model, skill digest and harness: a group
whose harness is not the current one is stale, and a trial with no harness
recorded never counts (``docs/HARNESS.md``).

This module imports only the ``Limits`` model, so the lower layers that read a
setting at call time (``nirmaan.models.limits``, ``nirmaan.org.knowledge``) do
so without an import cycle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nirmaan.models.limits import Limits, OnFailure

FORMAT = "nirmaan.harness"
VERSION = 1

# --- Budgets ---------------------------------------------------------------------------------

#: M61: the most characters of knowledge documents one packet's domain scope carries; over it the seat declines.
DOMAIN_CAP = 40_000
#: The most of one recorded file's content a packet carries; a larger file is withheld with the reason.
MAX_CONTENT = 60_000

# --- Limits ----------------------------------------------------------------------------------

#: M48: the limits a task gets when no override, stage or capability sets a field.
DEFAULT_LIMITS = Limits(attempts=1, review_rounds=1, retries=1, on_failure=OnFailure.RETRY_THEN_ESCALATE)

# --- The prompt ------------------------------------------------------------------------------

#: M20: the prompt's sections, in this order.
SCOPES = ("Company", "Domain", "Project", "Task")

OUTPUT_WORK = (
    '{"uncertainty": number, "outcome": string or null, '
    '"artifacts": [{"kind": string, "title": string, "summary": string}], '
    '"files": [{"path": string, "kind": string, "title": string, "summary": string, "entry": string or null}], '
    '"tool_runs": [string], "claims": [string], '
    '"escalation": null or {"reason": string, "question": string, "options": [string]}, "notes": string}'
)
FILE_FORMAT = """\
When an output is a file (a specification, RTL, a testbench), describe it in "files" and put its
exact content after the JSON object, once per file:
=== FILE: <path> ===
<content>
=== END FILE ===
Paths are relative (letters, digits, '_', '.', '-', '/'). A file's summary must cite like an
artifact's. "entry" names what a tool starts from, such as the top module. The platform writes
the files and runs the checks your task's evidence requirements name over them; you cannot run
or report those checks yourself."""
OUTPUT_REVIEW = '{"verdict": "approve" or "request_changes", "comments": string, "uncertainty": number}'

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
{OUTPUT_WORK}
{FILE_FORMAT}"""

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
{OUTPUT_REVIEW}"""

#: M27: the first line of the repair context after a review sent the submission back.
REPAIR_AFTER_REVIEW = ("Repair after review: submission {number} was sent back by an independent review and "
                       "nothing from it counts. Address every finding and answer again in full; your new files go "
                       "through every check and to review again.")
#: M26: the first line of the repair context after the engine refused an attempt.
REPAIR_AFTER_REFUSAL = ("Repair: your previous attempt {number} was refused and nothing from it counts. Fix what "
                        "failed and answer again in full; files from a refused attempt are never reviewed.")

# --- The log excerpt on a retry (M26) ----------------------------------------------------------

#: The most log lines a repairing seat is shown per failed run, and the most characters of each.
EXCERPT_LINES = 20
EXCERPT_WIDTH = 240
#: A log line worth showing first (case-insensitive); with none, the last lines are shown.
EXCERPT_NOTABLE = r"error|warning|fail|fatal|assert|mismatch"

# --- The claude-code runtime (M33) ---------------------------------------------------------------

#: Seconds Claude Code may take to answer one prompt.
CLAUDE_CODE_TIMEOUT = 1800
#: The flags besides ``-p``, ``--model`` and ``--system-prompt``: JSON out, no tools, no session, no MCP servers.
CLAUDE_CODE_FLAGS = ("--output-format", "json", "--tools", "", "--no-session-persistence", "--strict-mcp-config")
#: Removed from Claude Code's environment, so it answers on the plan login rather than billing a key.
CLAUDE_CODE_CLEARED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

# --- The anthropic runtime (M20) ---------------------------------------------------------------

ANTHROPIC_MAX_TOKENS = 16_000
ANTHROPIC_THINKING = "adaptive"
ANTHROPIC_EFFORT = "high"
#: The most characters of an answer a registry provider's text is kept to.
MAX_OUTPUT_CHARS = 64_000

#: Every setting above, by name: the fingerprint reads them from this module when it is computed.
SETTINGS = ("DOMAIN_CAP", "MAX_CONTENT", "DEFAULT_LIMITS", "SCOPES", "WORK_SYSTEM", "REVIEW_SYSTEM",
            "REPAIR_AFTER_REVIEW", "REPAIR_AFTER_REFUSAL", "EXCERPT_LINES", "EXCERPT_WIDTH", "EXCERPT_NOTABLE",
            "CLAUDE_CODE_TIMEOUT", "CLAUDE_CODE_FLAGS", "CLAUDE_CODE_CLEARED_ENV", "ANTHROPIC_MAX_TOKENS",
            "ANTHROPIC_THINKING", "ANTHROPIC_EFFORT", "MAX_OUTPUT_CHARS")

# --- The code ----------------------------------------------------------------------------------

#: Where the packages live: ``src/`` in the repository.
SOURCE_ROOT = Path(__file__).resolve().parents[2]
#: The files whose code shapes a seat's run, relative to ``SOURCE_ROOT``. Any edit to one, even a
#: comment, changes the fingerprint, on purpose: a harness change is never missed.
CODE = (
    "nirmaan/runtime/base.py",  # run_task: attempts, refusals, what a result becomes
    "nirmaan/runtime/context.py",  # the work packet
    "nirmaan/runtime/prompt.py",  # each line of the prompt
    "nirmaan/runtime/model.py",  # pre-flight tools, parsing, grounding, files, the post-answer checks
    "nirmaan/runtime/files.py",  # file blocks and the log excerpt
    "nirmaan/runtime/selection.py",  # what a seat needs, and the auto runtime's model choice
    "nirmaan/runtime/claude_code.py",  # the claude-code runtime
    "nirmaan/org/knowledge.py",  # reading knowledge documents, and the decline
    "nirmaan/integrations/veritriage.py",  # the bridge: rendering, grounding, the anthropic provider
    "nirmaan/evals/runner.py",  # the eval harness: the sandbox, the fixed upstream stages, the seat
    "veritriage/models/ai.py",  # how a prompt renders to text
    "veritriage/ai/grounding.py",  # which citations survive
)


def _value(value: Any) -> Any:
    if isinstance(value, Limits):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return list(value)
    return value


def code_digests() -> dict[str, str]:
    """``CODE`` file -> sha256 of its bytes; a file that cannot be read is named as missing."""
    out: dict[str, str] = {}
    for rel in CODE:
        try:
            out[rel] = "sha256:" + hashlib.sha256((SOURCE_ROOT / rel).read_bytes()).hexdigest()
        except OSError:
            out[rel] = "missing"
    return out


def fingerprint(*, attempts: int | None = None, knowledge: bool = True, cli: str | None = None) -> dict[str, Any]:
    """The harness a trial runs in: every setting, the code digests, and the run's own options.

    ``cli`` is the version of the command-line program the runtime calls the model through (the claude-code
    runtime's ``claude --version``), None for a runtime that calls none: a changed CLI is a changed harness.
    """
    module = globals()
    return {"format": FORMAT, "version": VERSION,
            "settings": {name: _value(module[name]) for name in SETTINGS},
            "code": code_digests(),
            "run": {"attempts": attempts, "knowledge": knowledge, "cli": cli}}


def harness_sha256(*, attempts: int | None = None, knowledge: bool = True, cli: str | None = None) -> str:
    """sha256 over ``fingerprint()``, as ``sha256:<hex>``. With no options: the current default harness."""
    text = json.dumps(fingerprint(attempts=attempts, knowledge=knowledge, cli=cli), sort_keys=True,
                      ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
