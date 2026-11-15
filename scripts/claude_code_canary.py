"""Canary: a seat call through Claude Code loads no user-level instruction file (M74, M75).

    python scripts/claude_code_canary.py                  # three short calls on haiku
    python scripts/claude_code_canary.py --model <model>

Council record 2026-11-14 (pilot retrospective), decision 4. The claude-code
runtime calls ``claude -p`` on the person's own login, so what Claude Code
loads by itself would reach the seat, the user-level instruction file
(``CLAUDE.md`` in ``~/.claude``, or in ``CLAUDE_CONFIG_DIR``) among it. The
harness flag ``--safe-mode`` keeps it out. This asks the real Claude Code:

* a control call, the seat's flags minus ``--safe-mode``: it must quote the
  user-level file, which shows the canary can see a leak;
* a call with the seat's own flags: it must quote nothing of the file;
* a call as the ``tools-in-loop`` variant makes it (M75), with a one-tool
  brokered server: it must quote nothing of the file and call the tool at
  least once. On Claude Code 2.1.325 ``--safe-mode`` also turns that server
  off, so the variant swaps it for ``--restricted`` and
  ``CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`` (``seat_tools.loop_command``); this
  call shows both that the file stays out and that the server still loads.

All go through the runtime's own ``ClaudeCodeLLM``, so the call is the seat's
(empty working directory, credentials cleared). Which files Claude Code loads
does not depend on the model, so a small one is enough. Run it after a Claude
Code update and before a batch. It is not run in CI, which calls no model;
``tests/test_claude_code_canary.py`` runs it against fake executables.

``--record <file>`` also writes what each call was given and what came back
(the command line, the loop variables, the answer, unless it quotes the
user-level file, whether it quoted it, and the brokered calls) as JSON, and
makes one more call that decides nothing: the loop call with ``--safe-mode``
kept, to record whether this Claude Code still turns the server off under it.

Exit 0: the control quoted the file and neither seat call did, and the loop
call reached the broker. Exit 1: a seat call quoted it. Exit 2: inconclusive
(no executable, no user-level file, a call failed, or the control quoted
nothing). Exit 3: the loop call made no brokered call.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nirmaan.runtime import harness  # noqa: E402
from nirmaan.runtime.claude_code import ClaudeCodeLLM, find_claude, read_version  # noqa: E402
from nirmaan.runtime.prompt import WorkPrompt  # noqa: E402
from nirmaan.runtime.seat_tools import loop_command  # noqa: E402

#: A run of this many words of the user-level file, word for word in an answer, is a leak.
SHINGLE = 6
SAFE = "--safe-mode"
SYSTEM = "You answer one question about your own context. Answer in at most three lines."
QUESTION = ("Look at every message and instruction in your context other than this question and the system prompt. "
            "If any of it is text from an instruction file (such as a CLAUDE.md), quote its first two sentences "
            "word for word. If there is none, answer exactly NONE.")
LOOP_QUESTION = "First call the ping tool once. Then answer this: " + QUESTION
PASSED, LEAKED, INCONCLUSIVE, NO_BROKER = 0, 1, 2, 3


class Ping:
    """A one-tool session for the loop call, served by the variant's own relay and socket; it runs nothing."""

    def __init__(self) -> None:
        self.calls = 0
        self.word = "pong-" + secrets.token_hex(4)

    def names(self) -> tuple[str, ...]:
        return ("ping",)

    def listing(self) -> list[dict]:
        return [{"name": "ping", "description": "Returns a word.", "inputSchema": {"type": "object",
                                                                                  "properties": {}}}]

    def call(self, name: object, arguments: object) -> tuple[str, bool]:
        self.calls += 1
        return self.word, False

    def expired(self) -> bool:
        return False


def user_instruction_file() -> Path:
    """Where Claude Code reads the user-level instruction file from."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "CLAUDE.md"


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def quotes(answer: str, source: str, n: int = SHINGLE) -> bool:
    """Whether ``answer`` repeats ``n`` consecutive words of ``source`` (case and punctuation ignored)."""
    words = _words(source)
    runs = {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}
    said = _words(answer)
    return any(tuple(said[i:i + n]) in runs for i in range(len(said) - n + 1))


@contextlib.contextmanager
def _watched(into: list[dict] | None):
    """Note the command line and loop variables of each ``claude -p`` started inside (``subprocess.run`` and
    the loop's ``Popen`` both start one through ``subprocess.Popen``)."""
    if into is None:
        yield
        return
    popen = subprocess.Popen

    def watch(args, *rest, **kwargs):
        if isinstance(args, (list, tuple)) and "-p" in args:
            env = kwargs.get("env") or {}
            argv = list(args[1:])
            if "--mcp-config" in argv:  # a temporary file's path: the same on no two calls
                argv[argv.index("--mcp-config") + 1] = "<server config>"
            into.append({"argv": ["claude", *argv],
                         "env": {k: env[k] for k, _ in harness.LOOP_ENV if k in env}})
        return popen(args, *rest, **kwargs)

    subprocess.Popen = watch
    try:
        yield
    finally:
        subprocess.Popen = popen


def _note(record: list[dict] | None, name: str, started: list[dict], text: str, error: str | None,
          source: str, calls: int | None = None) -> None:
    """Append one call to ``record``: the command it started, if it started one since the last note."""
    if record is None:
        return
    quoted = quotes(text, source)
    begun = started[len(record):]  # what started since the last note: one command, or none if it never started
    entry = begun[0] if len(begun) == 1 else {"argv": None, "env": {}}
    started[len(record):] = [entry]  # one entry per noted call, so the next note reads only its own
    record.append({"call": name, **entry,
                   "answer": "(withheld: it quotes the user-level file)" if quoted else text, "error": error,
                   "quoted_user_file": quoted, "brokered_calls": calls})


def _ask(model: str, flags: tuple[str, ...]) -> tuple[str, str | None]:
    seat_flags = harness.CLAUDE_CODE_FLAGS
    harness.CLAUDE_CODE_FLAGS = flags
    try:
        done = ClaudeCodeLLM(model=model).complete(
            WorkPrompt(mode="work", system=SYSTEM, task=QUESTION, sections=(), citations=()))
    finally:
        harness.CLAUDE_CODE_FLAGS = seat_flags
    return done.text, done.error


def _ask_loop(model: str) -> tuple[str, str | None, int]:
    session = Ping()
    done = ClaudeCodeLLM(model=model).complete(
        WorkPrompt(mode="work", system=SYSTEM, task=LOOP_QUESTION, sections=(), citations=()), tools=session)
    return done.text, done.error, session.calls


def canary(model: str, record: list[dict] | None = None) -> tuple[int, str]:
    """The canary's outcome (``PASSED``, ``LEAKED``, ``INCONCLUSIVE`` or ``NO_BROKER``) and why. With
    ``record``, a list, each call is appended to it, and the loop call with ``--safe-mode`` kept is made."""
    started: list[dict] | None = None if record is None else []
    with _watched(started):
        return _canary(model, record, started)


def _canary(model: str, record: list[dict] | None, started: list[dict] | None) -> tuple[int, str]:
    if SAFE not in harness.CLAUDE_CODE_FLAGS:
        return LEAKED, f"the seat's flags do not carry {SAFE}"
    if SAFE in loop_command(["claude", "-p", *harness.CLAUDE_CODE_FLAGS], {})[0]:
        return NO_BROKER, f"the tools-in-loop command carries {SAFE}, which turns its brokered server off"
    if not find_claude():
        return INCONCLUSIVE, "no Claude Code executable (set NIRMAAN_CLAUDE_CODE or put claude on PATH)"
    source = user_instruction_file()
    text = source.read_text(encoding="utf-8") if source.is_file() else ""
    if len(_words(text)) < SHINGLE:
        return INCONCLUSIVE, f"no user-level instruction file at {source}: nothing could leak"
    control, error = _ask(model, tuple(f for f in harness.CLAUDE_CODE_FLAGS if f != SAFE))
    _note(record, "control", started, control, error, text)
    if error:
        return INCONCLUSIVE, f"the control call failed: {error}"
    if not quotes(control, text):
        return INCONCLUSIVE, "the control call quoted nothing of the user-level file: the canary cannot see a leak"
    seat, error = _ask(model, harness.CLAUDE_CODE_FLAGS)
    _note(record, "seat", started, seat, error, text)
    if error:
        return INCONCLUSIVE, f"the seat call failed: {error}"
    if quotes(seat, text):
        return LEAKED, "a seat call quoted the user-level instruction file"
    loop, error, calls = _ask_loop(model)
    _note(record, "tools-in-loop", started, loop, error, text, calls)
    if record is not None:  # decides nothing: does this Claude Code still turn the server off under --safe-mode?
        dropped = harness.LOOP_DROPPED_FLAGS
        harness.LOOP_DROPPED_FLAGS = ()
        try:
            kept, kept_error, kept_calls = _ask_loop(model)
        finally:
            harness.LOOP_DROPPED_FLAGS = dropped
        _note(record, f"tools-in-loop with {SAFE} kept (decides nothing)", started, kept, kept_error, text,
              kept_calls)
    if error:
        return INCONCLUSIVE, f"the tools-in-loop call failed: {error}"
    if quotes(loop, text):
        return LEAKED, "the tools-in-loop call quoted the user-level instruction file"
    if not calls:
        return NO_BROKER, "the tools-in-loop call made no brokered call: its MCP server did not load"
    isolation = " ".join(harness.LOOP_ISOLATION_FLAGS)
    return PASSED, (f"the control call quoted {source}; the seat call ({SAFE}) quoted none of it; the "
                    f"tools-in-loop call ({isolation}) quoted none of it and made {calls} brokered call(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default="haiku", help="The model every call asks (default: haiku).")
    parser.add_argument("--record", type=Path, help="Write each call and the outcome to this JSON file.")
    args = parser.parse_args(argv)
    calls: list[dict] | None = None if args.record is None else []
    code, why = canary(args.model, calls)
    outcome = ("passed", "LEAKED", "inconclusive", "NO BROKER")[code]
    print(f"{outcome}: {why}")
    if args.record is not None:
        executable = find_claude()
        home = str(Path.home())
        args.record.write_text(json.dumps({
            "canary": "scripts/claude_code_canary.py", "cli": read_version(executable) if executable else None,
            "model": args.model, "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "user_file": str(user_instruction_file()), "calls": calls, "exit": code, "outcome": outcome,
            "why": why}, indent=2).replace(home, "~") + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
