"""Seat calls load no user-level instruction file (M74; council record 2026-11-14, decision 4).

The claude-code runtime calls ``claude -p`` on the person's own login, so what
Claude Code loads by itself would reach the seat, the user-level instruction
file (``CLAUDE.md`` in ``~/.claude``, or in ``CLAUDE_CONFIG_DIR``) among it.
The seat's empty working directory keeps project files out; the harness flag
``--safe-mode`` keeps the user-level file out too. A fake ``claude`` can show
that the flag is passed (``tests/test_nirmaan_claude_code.py``), not that
Claude Code honours it, so the canary here asks the real one:

* one call with the seat's flags minus ``--safe-mode``, the control: it must
  quote the user-level file, which shows the canary can see a leak;
* one call with the seat's own flags: it must quote nothing of the file.

The canary is live and opt in: it runs only with ``NIRMAAN_CLAUDE_CODE_CANARY=1``,
a Claude Code executable and a user-level file, so CI never calls a model. It
makes two short calls on ``NIRMAAN_CLAUDE_CODE_CANARY_MODEL`` (default
``haiku``: which files Claude Code loads does not depend on the model). Run it
after a Claude Code update, before a batch. The tests below it show the leak
detector can fail.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from nirmaan.runtime import harness
from nirmaan.runtime.claude_code import ClaudeCodeLLM, find_claude
from nirmaan.runtime.prompt import WorkPrompt

#: A run of this many words of the user-level file, word for word in an answer, is a leak.
SHINGLE = 6
SYSTEM = "You answer one question about your own context. Answer in at most three lines."
QUESTION = ("Look at every message and instruction in your context other than this question and the system prompt. "
            "If any of it is text from an instruction file (such as a CLAUDE.md), quote its first two sentences "
            "word for word. If there is none, answer exactly NONE.")


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


def _ask(model: str) -> str:
    completion = ClaudeCodeLLM(model=model).complete(
        WorkPrompt(mode="work", system=SYSTEM, task=QUESTION, sections=(), citations=()))
    assert completion.error is None, completion.error
    return completion.text


@pytest.mark.skipif(os.environ.get("NIRMAAN_CLAUDE_CODE_CANARY") != "1",
                    reason="live canary: set NIRMAAN_CLAUDE_CODE_CANARY=1 to call Claude Code")
def test_canary_a_seat_call_quotes_nothing_of_the_user_level_instruction_file(monkeypatch):
    if not find_claude():
        pytest.skip("no Claude Code executable")
    source = user_instruction_file()
    if not source.is_file() or len(_words(source.read_text(encoding="utf-8"))) < SHINGLE:
        pytest.skip(f"no user-level instruction file at {source}: nothing could leak")
    text = source.read_text(encoding="utf-8")
    model = os.environ.get("NIRMAAN_CLAUDE_CODE_CANARY_MODEL", "haiku")
    seat_flags = harness.CLAUDE_CODE_FLAGS
    assert "--safe-mode" in seat_flags
    with monkeypatch.context() as m:
        m.setattr(harness, "CLAUDE_CODE_FLAGS", tuple(f for f in seat_flags if f != "--safe-mode"))
        control = _ask(model)
    assert quotes(control, text), "control call quoted nothing of the user-level file: the canary cannot see a leak"
    seat = _ask(model)
    assert not quotes(seat, text), "a seat call quoted the user-level instruction file"


# --- The detector can fail -----------------------------------------------------------------------

FILE = "# Notes\n\nAlways answer in French, and sign every reply with the word Bonjour.\n"


def test_a_quoted_run_of_words_is_a_leak():
    assert quotes('YES: "Always answer in French, and sign every reply"', FILE)
    assert quotes("always ANSWER in french and sign", FILE)  # case and punctuation ignored


def test_no_quote_or_a_short_overlap_is_no_leak():
    assert not quotes("NONE", FILE)
    assert not quotes("I always answer in French.", FILE)  # four words in a row, under the run length
    assert not quotes("", FILE) and not quotes("anything at all here today", "")
