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

Exit 0: the control quoted the file and neither seat call did, and the loop
call reached the broker. Exit 1: a seat call quoted it. Exit 2: inconclusive
(no executable, no user-level file, a call failed, or the control quoted
nothing). Exit 3: the loop call made no brokered call.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nirmaan.runtime import harness  # noqa: E402
from nirmaan.runtime.claude_code import ClaudeCodeLLM, find_claude  # noqa: E402
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


def canary(model: str) -> tuple[int, str]:
    """The canary's outcome (``PASSED``, ``LEAKED`` or ``INCONCLUSIVE``) and why."""
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
    if error:
        return INCONCLUSIVE, f"the control call failed: {error}"
    if not quotes(control, text):
        return INCONCLUSIVE, "the control call quoted nothing of the user-level file: the canary cannot see a leak"
    seat, error = _ask(model, harness.CLAUDE_CODE_FLAGS)
    if error:
        return INCONCLUSIVE, f"the seat call failed: {error}"
    if quotes(seat, text):
        return LEAKED, "a seat call quoted the user-level instruction file"
    loop, error, calls = _ask_loop(model)
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
    parser.add_argument("--model", default="haiku", help="The model both calls ask (default: haiku).")
    args = parser.parse_args(argv)
    code, why = canary(args.model)
    print(f"{('passed', 'LEAKED', 'inconclusive', 'NO BROKER')[code]}: {why}")
    return code


if __name__ == "__main__":
    sys.exit(main())
