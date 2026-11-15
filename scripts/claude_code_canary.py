"""Canary: a seat call through Claude Code loads no user-level instruction file (M74).

    python scripts/claude_code_canary.py                  # two short calls on haiku
    python scripts/claude_code_canary.py --model <model>

Council record 2026-11-14 (pilot retrospective), decision 4. The claude-code
runtime calls ``claude -p`` on the person's own login, so what Claude Code
loads by itself would reach the seat, the user-level instruction file
(``CLAUDE.md`` in ``~/.claude``, or in ``CLAUDE_CONFIG_DIR``) among it. The
harness flag ``--safe-mode`` keeps it out. This asks the real Claude Code:

* a control call, the seat's flags minus ``--safe-mode``: it must quote the
  user-level file, which shows the canary can see a leak;
* a call with the seat's own flags: it must quote nothing of the file.

Both go through the runtime's own ``ClaudeCodeLLM``, so the call is the seat's
(empty working directory, credentials cleared). Which files Claude Code loads
does not depend on the model, so a small one is enough. Run it after a Claude
Code update and before a batch. It is not run in CI, which calls no model;
``tests/test_claude_code_canary.py`` runs it against fake executables.

Exit 0: the control quoted the file and the seat call did not. Exit 1: the
seat call quoted it. Exit 2: inconclusive (no executable, no user-level file,
a call failed, or the control quoted nothing).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nirmaan.runtime import harness  # noqa: E402
from nirmaan.runtime.claude_code import ClaudeCodeLLM, find_claude  # noqa: E402
from nirmaan.runtime.prompt import WorkPrompt  # noqa: E402

#: A run of this many words of the user-level file, word for word in an answer, is a leak.
SHINGLE = 6
SAFE = "--safe-mode"
SYSTEM = "You answer one question about your own context. Answer in at most three lines."
QUESTION = ("Look at every message and instruction in your context other than this question and the system prompt. "
            "If any of it is text from an instruction file (such as a CLAUDE.md), quote its first two sentences "
            "word for word. If there is none, answer exactly NONE.")
PASSED, LEAKED, INCONCLUSIVE = 0, 1, 2


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


def canary(model: str) -> tuple[int, str]:
    """The canary's outcome (``PASSED``, ``LEAKED`` or ``INCONCLUSIVE``) and why."""
    if SAFE not in harness.CLAUDE_CODE_FLAGS:
        return LEAKED, f"the seat's flags do not carry {SAFE}"
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
    return PASSED, f"the control call quoted {source}; the seat call ({SAFE}) quoted none of it"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default="haiku", help="The model both calls ask (default: haiku).")
    args = parser.parse_args(argv)
    code, why = canary(args.model)
    print(f"{('passed', 'LEAKED', 'inconclusive')[code]}: {why}")
    return code


if __name__ == "__main__":
    sys.exit(main())
