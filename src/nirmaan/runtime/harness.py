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

The tool definitions a seat is shown are company data, not code: each gate
tool's parameters and their descriptions reach the prompt as its input
contract. The fingerprint carries a digest of every tool definition in the
catalog (M74), so a changed description is a changed harness.

``harness_sha256`` is the sha256 of ``fingerprint()``: these settings, the
code digests, the tool digests and the run's own options (an ``--attempts``
override, whether knowledge documents were given, M67, the version of the
command-line program the runtime calls the model through: Claude Code's
``claude --version`` on the claude-code runtime, None on any other, and the
named variant the run chose, M74, ``VARIANTS``). The ``tools-in-loop`` variant
(M75) adds a ``loop`` section: its own settings (``LOOP_SETTINGS``), the
digests of the brokered server's code (``LOOP_CODE``) and the versions of the
tools it runs (``tool_pins``). Every eval trial records it
(``EvalResult.harness`` and each ``RecordedAnswer.harness``), and the levels
generator groups trials by skill, model, skill digest and harness: a group
whose harness is not the current one is stale, and a trial with no harness
recorded never counts (``docs/HARNESS.md``).

This module imports only the ``Limits`` model at load time (the tool catalog is
read when a fingerprint is computed), so the lower layers that read a setting
at call time (``nirmaan.models.limits``, ``nirmaan.org.knowledge``) do so
without an import cycle.
"""

from __future__ import annotations

import functools
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from nirmaan.models.limits import Limits, OnFailure

FORMAT = "nirmaan.harness"
VERSION = 2  # M74: the tool digests and the variant joined the fingerprint

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
#: The flags besides ``-p``, ``--model`` and ``--system-prompt``: JSON out, no tools, no session, no MCP servers,
#: and (M74) ``--safe-mode``, meant to start Claude Code with its customizations off, so no user-level instruction
#: file (``~/.claude/CLAUDE.md``), hook, skill or plugin reaches the seat. No committed record shows that yet: the
#: effect is unverified until the canary, scripts/claude_code_canary.py, has run and its output is committed.
#: ``--bare`` also drops them but never reads the plan login.
CLAUDE_CODE_FLAGS = ("--output-format", "json", "--tools", "", "--no-session-persistence", "--strict-mcp-config",
                     "--safe-mode")
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

# --- Named variants (M74) ---------------------------------------------------------------------

#: The harnesses an eval run may name (``nirmaan eval run --harness <name>``): each is the default harness with
#: the run options it sets, and its name is a run option of the fingerprint. A trial on any variant but
#: ``default`` is labelled with its name and listed apart: it never counts toward a level. Council record
#: 2026-11-14 (pilot retrospective), decision 4: ``attempts-3`` gives the seat three attempts, so a refused one is
#: answered again with the repair text (``REPAIR_AFTER_REFUSAL``) and the failed run's log excerpt.
VARIANTS: dict[str, dict[str, Any]] = {
    "default": {},
    "attempts-3": {"attempts": 3},
    "tools-in-loop": {"tools": True},  # M75: the seat calls brokered checks during its attempt (``LOOP_SETTINGS``)
}


def variant_options(name: str) -> dict[str, Any]:
    """The run options the named variant sets; ValueError for a name not in ``VARIANTS``."""
    if name not in VARIANTS:
        raise ValueError(f"unknown harness variant {name!r}; known: {', '.join(VARIANTS)}")
    return dict(VARIANTS[name])


def run_attempts(attempts: int | None, variant: str = "default") -> int | None:
    """The attempts override a run makes: the one given, else the variant's, else None (the default limits)."""
    return attempts if attempts is not None else variant_options(variant).get("attempts")


def run_tools(variant: str = "default") -> bool:
    """Whether the named variant gives the seat brokered tools during its attempt (M75, tools in the loop)."""
    return bool(variant_options(variant).get("tools"))


# --- Tools in the loop (M75) ---------------------------------------------------------------------
#
# Council record 2026-11-14 (pilot retrospective), decision 4, the first variant: during its attempt the seat
# calls the platform's own checks through the tool broker, under its role, and then submits. These settings are
# in the fingerprint of the ``tools-in-loop`` variant only (``fingerprint()["loop"]``), with the digests of
# ``LOOP_CODE`` and the versions of the tools it can run (``tool_pins``), so editing one changes that variant's
# harness and never the default's (docs/TOOLS_IN_THE_LOOP.md).

# The tools the seat may call are company data (``nirmaan.company.tools.IN_LOOP``, read by ``loop_tools``): the
# runtime names no tool. They are in the variant's fingerprint with these settings.
#: Calls per attempt, refused ones included; a call over the cap is refused and recorded.
LOOP_MAX_CALLS = 8
#: Seconds per attempt, the model's time and every brokered run together: past it the seat is stopped and the
#: attempt fails. The same as ``CLAUDE_CODE_TIMEOUT``, so the variant gives the seat no more time than the default.
LOOP_SECONDS = 1800
#: The most seconds one brokered run may take (the tool's ``timeout``), and never more than the attempt has left.
LOOP_CALL_SECONDS = 300
#: The most files, and characters over all of them, one call may pass.
LOOP_MAX_FILES = 16
LOOP_MAX_CHARS = 200_000
#: The only file suffixes a call may pass: HDL and SymbiYosys job files. No script, no testbench in another
#: language, no memory image: nothing a tool would run or read as anything but HDL or a proof setup.
LOOP_SUFFIXES = (".v", ".sv", ".vh", ".svh", ".sby")
#: The name Claude Code knows the brokered server by; its tools are ``mcp__<name>__<tool>``.
LOOP_SERVER = "nirmaan-broker"
#: Claude Code flags beside the seat's own (``CLAUDE_CODE_FLAGS``, ``--tools ""`` among them, so no built-in
#: tool): only the allowed brokered tools run, and anything else that would ask for permission is refused.
LOOP_FLAGS = ("--permission-mode", "dontAsk")
#: Seat flags (``CLAUDE_CODE_FLAGS``) the variant drops: on Claude Code 2.1.325 ``--safe-mode`` turns every MCP
#: server off, the one ``--mcp-config`` names included, so a seat under it never reaches the broker (H3 hand-run
#: call, 2026-11-16: 0 brokered calls with it, 1 without). The default and ``attempts-3`` keep it.
LOOP_DROPPED_FLAGS = ("--safe-mode",)
#: What keeps the user-level files out of the variant's call in its place. ``--restricted`` loads only managed
#: settings and ``--settings``: no user, project or local settings file, so no hook, plugin, skill or permission
#: rule of the person's own. ``CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`` loads no CLAUDE.md memory file (user, project
#: or auto memory). ``--mcp-config`` still loads, with ``--strict-mcp-config`` the only server
#: (scripts/claude_code_canary.py checks both live). Never ``--bare``: it never reads the plan login.
LOOP_ISOLATION_FLAGS = ("--restricted",)
LOOP_ENV = (("CLAUDE_CODE_DISABLE_CLAUDE_MDS", "1"),)
#: Appended to the work system prompt in the variant: ``FILE_FORMAT`` says the seat cannot run checks itself.
LOOP_SYSTEM = """\
In this run you may call the tools you are given before you answer. Each runs one of the checks the
platform runs over your files for this task, on the files you pass it, through the platform's tool broker.
Every call is recorded, and a run it makes is named [run:<id>]. The runs are advisory: only the checks the
platform runs on the files of your final answer judge your work, and a run made in the loop cannot be
listed in "tool_runs". At most {calls} calls and {seconds} seconds per attempt; past the time the attempt
fails. You have no other tool: no shell, no file access, no network. Then answer as described above."""

#: Every loop setting, by name: in the variant's fingerprint only.
LOOP_SETTINGS = ("LOOP_MAX_CALLS", "LOOP_SECONDS", "LOOP_CALL_SECONDS", "LOOP_MAX_FILES",
                 "LOOP_MAX_CHARS", "LOOP_SUFFIXES", "LOOP_SERVER", "LOOP_FLAGS", "LOOP_DROPPED_FLAGS",
                 "LOOP_ISOLATION_FLAGS", "LOOP_ENV", "LOOP_SYSTEM")
#: The brokered server's code, relative to ``SOURCE_ROOT``: the session, its screen and its socket (broker
#: side), and the stdio relay Claude Code starts. In the variant's fingerprint only.
LOOP_CODE = (
    "nirmaan/runtime/seat_tools.py",
    "nirmaan/runtime/seat_tools_relay.py",
)


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


def code_digests(files: tuple[str, ...] | None = None) -> dict[str, str]:
    """``CODE`` file (or each of ``files``) -> sha256 of its bytes; a file that cannot be read is named missing."""
    out: dict[str, str] = {}
    for rel in CODE if files is None else files:
        try:
            out[rel] = "sha256:" + hashlib.sha256((SOURCE_ROOT / rel).read_bytes()).hexdigest()
        except OSError:
            out[rel] = "missing"
    return out


def tool_digests() -> dict[str, str]:
    """Tool ID -> sha256 of its definition (name, status, description, every parameter and its description).

    A seat reads its gate tools' parameter descriptions as their input contract (M73's gate contracts), so the
    catalog's definitions are harness: an edited description changes the fingerprint (M74).
    """
    from nirmaan.company.tools import TOOLS

    return {spec.id: "sha256:" + hashlib.sha256(json.dumps(spec.model_dump(mode="json"), sort_keys=True,
                                                           ensure_ascii=True).encode("utf-8")).hexdigest()
            for spec in sorted(TOOLS, key=lambda spec: spec.id)}


def fingerprint(*, attempts: int | None = None, knowledge: bool = True, cli: str | None = None,
                variant: str = "default") -> dict[str, Any]:
    """The harness a trial runs in: every setting, the code and tool digests, and the run's own options.

    ``cli`` is the version of the command-line program the runtime calls the model through (the claude-code
    runtime's ``claude --version``), None for a runtime that calls none: a changed CLI is a changed harness.
    ``variant`` is a name in ``VARIANTS``; the attempts it sets apply when ``attempts`` is None.
    """
    module = globals()
    out = {"format": FORMAT, "version": VERSION,
           "settings": {name: _value(module[name]) for name in SETTINGS},
           "code": code_digests(),
           "tools": tool_digests(),
           "run": {"attempts": run_attempts(attempts, variant), "knowledge": knowledge, "cli": cli,
                   "variant": variant}}
    if run_tools(variant):  # M75: the brokered server's settings, its code, and the versions of its tools
        out["loop"] = {"settings": {name: _value(module[name]) for name in LOOP_SETTINGS},
                       "tools": list(loop_tools()), "code": code_digests(LOOP_CODE), "pins": tool_pins()}
    return out


def loop_tools() -> tuple[str, ...]:
    """The tools a seat may call in the loop (M75): company data, ``nirmaan.company.tools.IN_LOOP``."""
    from nirmaan.company.tools import IN_LOOP

    return tuple(IN_LOOP)


def tool_pins() -> dict[str, dict[str, str]]:
    """Each loop tool -> each executable its backends run -> the first line of its version (M75), or why none.

    The seat reads these tools' output during its attempt, so a changed tool is a changed harness for the
    variant. Asked once per process, with no credential in the environment, as a brokered run is.
    """
    return {tool: dict(found) for tool, found in _read_pins().items()}


def _read_pins() -> dict[str, dict[str, str]]:
    return _pins(loop_tools())


@functools.lru_cache(maxsize=4)
def _pins(tools: tuple[str, ...]) -> dict[str, dict[str, str]]:
    from nirmaan.integrations.eda import backends_for, run_environment

    flag = {"iverilog": "-V", "vvp": "-V", "yosys": "-V"}  # the others take --version
    pins: dict[str, dict[str, str]] = {}
    for tool in loop_tools():
        found: dict[str, str] = {}
        for exe in sorted({e for backend in backends_for(tool) for e in backend.executables}):
            path = shutil.which(exe)
            if path is None:
                found[exe] = "not on PATH"
                continue
            try:
                proc = subprocess.run([path, flag.get(exe, "--version")], capture_output=True, text=True,
                                      timeout=30, stdin=subprocess.DEVNULL, env=run_environment(Path.cwd()))
                first = next((ln.strip() for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()), "")
            except (OSError, subprocess.TimeoutExpired):
                first = ""
            found[exe] = first[:200] or "unknown"
        pins[tool] = found
    return pins


def harness_sha256(*, attempts: int | None = None, knowledge: bool = True, cli: str | None = None,
                   variant: str = "default") -> str:
    """sha256 over ``fingerprint()``, as ``sha256:<hex>``. With no options: the current default harness."""
    text = json.dumps(fingerprint(attempts=attempts, knowledge=knowledge, cli=cli, variant=variant),
                      sort_keys=True, ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
