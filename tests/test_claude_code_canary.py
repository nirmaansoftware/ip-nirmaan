"""The canary that seat calls load no user-level instruction file (M74), run against fake executables.

``scripts/claude_code_canary.py`` asks the real Claude Code, outside CI (it
calls a model). Here the same canary runs against fake ``claude`` executables
that behave as a leaking or a clean Claude Code would, so each outcome is
shown to be reachable: it passes only when the control call quotes the
user-level file and the seat call does not. No test calls a model.
"""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import pytest

from nirmaan.runtime import harness

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("claude_code_canary", ROOT / "scripts" / "claude_code_canary.py")
canary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)

FILE = "# Notes\n\nAlways answer in French, and sign every reply with the word Bonjour.\n"


def _fake(tmp_path: Path, behaviour: str) -> Path:
    """A ``claude`` that quotes the user-level file: ``leaks`` always, ``honours`` unless --safe-mode, ``never``."""
    script = tmp_path / f"claude-{behaviour}"
    script.write_text(f"""#!/usr/bin/env python3
import json, os, sys
user = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "CLAUDE.md")
loads = {behaviour!r} == "leaks" or ({behaviour!r} == "honours" and "--safe-mode" not in sys.argv)
text = ("YES: " + open(user).read()) if loads else "NONE"
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": text,
                   "usage": {{}}, "modelUsage": {{}}}}))
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture()
def user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "config"))
    path = tmp_path / "config" / "CLAUDE.md"
    path.parent.mkdir()
    path.write_text(FILE, encoding="utf-8")
    return path


@pytest.mark.parametrize("behaviour, outcome, why", [
    ("honours", canary.PASSED, "the seat call (--safe-mode) quoted none of it"),
    ("leaks", canary.LEAKED, "a seat call quoted the user-level instruction file"),
    ("never", canary.INCONCLUSIVE, "the canary cannot see a leak"),
])
def test_the_canary_passes_only_when_the_control_sees_the_file_and_the_seat_does_not(
        tmp_path, monkeypatch, user_file, behaviour, outcome, why):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, behaviour)))
    code, reason = canary.canary("haiku")
    assert code == outcome and why in reason, reason
    assert harness.CLAUDE_CODE_FLAGS[-1] == "--safe-mode"  # the seat's flags are restored after the control


def test_the_canary_fails_when_the_seat_flags_lose_safe_mode(tmp_path, monkeypatch, user_file):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    monkeypatch.setattr(harness, "CLAUDE_CODE_FLAGS", tuple(f for f in harness.CLAUDE_CODE_FLAGS
                                                            if f != "--safe-mode"))
    assert canary.canary("haiku") == (canary.LEAKED, "the seat's flags do not carry --safe-mode")


def test_with_no_user_level_file_or_no_executable_the_canary_is_inconclusive(tmp_path, monkeypatch, user_file):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    user_file.unlink()
    code, reason = canary.canary("haiku")
    assert code == canary.INCONCLUSIVE and "nothing could leak" in reason
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE")
    monkeypatch.setattr(canary, "find_claude", lambda: None)
    assert canary.canary("haiku")[0] == canary.INCONCLUSIVE


def test_the_main_prints_the_outcome_and_exits_with_it(tmp_path, monkeypatch, user_file, capsys):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    assert canary.main(["--model", "haiku"]) == 0 and capsys.readouterr().out.startswith("passed: ")


# --- The detector ---------------------------------------------------------------------------------


def test_a_quoted_run_of_words_is_a_leak():
    assert canary.quotes('YES: "Always answer in French, and sign every reply"', FILE)
    assert canary.quotes("always ANSWER in french and sign", FILE)  # case and punctuation ignored


def test_no_quote_or_a_short_overlap_is_no_leak():
    assert not canary.quotes("NONE", FILE)
    assert not canary.quotes("I always answer in French.", FILE)  # four words in a row, under the run length
    assert not canary.quotes("", FILE) and not canary.quotes("anything at all here today", "")


def test_the_user_level_file_is_read_from_the_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert canary.user_instruction_file() == tmp_path / "CLAUDE.md"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert canary.user_instruction_file() == Path.home() / ".claude" / "CLAUDE.md"
