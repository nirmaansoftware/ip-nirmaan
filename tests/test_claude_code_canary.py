"""The canary that seat calls load no user-level instruction file (M74, M75), run against fake executables.

``scripts/claude_code_canary.py`` asks the real Claude Code, outside CI (it
calls a model). Here the same canary runs against fake ``claude`` executables
that behave as a leaking or a clean Claude Code would, so each outcome is
shown to be reachable: it passes only when the control call quotes the
user-level file, neither seat call does, and the tools-in-loop call reaches
the brokered server. The clean fake acts as Claude Code 2.1.325 does: it
loads no server under ``--safe-mode``, ``--mcp-config`` included, and no
user-level file under ``--safe-mode``, ``--restricted`` or
``CLAUDE_CODE_DISABLE_CLAUDE_MDS=1``. No test calls a model.
"""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path

import pytest

from nirmaan.runtime import harness, seat_tools

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("claude_code_canary", ROOT / "scripts" / "claude_code_canary.py")
canary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)

FILE = "# Notes\n\nAlways answer in French, and sign every reply with the word Bonjour.\n"


def _fake(tmp_path: Path, behaviour: str) -> Path:
    """A ``claude`` that quotes the user-level file: ``leaks`` always, ``honours`` unless isolated, ``never``.

    Given ``--mcp-config`` and no ``--safe-mode``, it starts the server, as Claude Code would, and calls its
    first tool once, so the session behind the relay sees a brokered call.
    """
    script = tmp_path / f"claude-{behaviour}"
    script.write_text(f"""#!{sys.executable}
import json, os, subprocess, sys
argv = sys.argv[1:]
user = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "CLAUDE.md")
isolated = ("--safe-mode" in argv or "--restricted" in argv
            or os.environ.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1")
loads = {behaviour!r} == "leaks" or ({behaviour!r} == "honours" and not isolated)
text = ("YES: " + open(user).read()) if loads else "NONE"
if "--mcp-config" in argv and "--safe-mode" not in argv:
    config = json.load(open(argv[argv.index("--mcp-config") + 1]))
    [(name, server)] = config["mcpServers"].items()
    proc = subprocess.Popen([server["command"], *server["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, env=server["env"])
    def rpc(i, method, params):
        proc.stdin.write(json.dumps({{"jsonrpc": "2.0", "id": i, "method": method, "params": params}}) + "\\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())
    rpc(1, "initialize", {{"protocolVersion": "2025-06-18", "capabilities": {{}}}})
    proc.stdin.write(json.dumps({{"jsonrpc": "2.0", "method": "notifications/initialized"}}) + "\\n")
    [tool] = rpc(2, "tools/list", {{}})["result"]["tools"]
    text += " " + rpc(3, "tools/call", {{"name": tool["name"], "arguments": {{}}}})["result"]["content"][0]["text"]
    proc.stdin.close(); proc.wait()
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
    ("honours", canary.PASSED, "the seat call (--safe-mode) quoted none of it; the tools-in-loop call "
                               "(--restricted) quoted none of it and made 1 brokered call(s)"),
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


# --- The tools-in-loop call (M75): no user-level file, and the brokered server loads ----------------------


def test_the_canary_fails_when_the_loop_call_gets_no_mcp_config_under_its_isolation(
        tmp_path, monkeypatch, user_file):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    flags = seat_tools.Endpoint.flags
    monkeypatch.setattr(seat_tools.Endpoint, "flags", lambda self: flags(self)[2:])  # no --mcp-config <file>
    assert canary.canary("haiku") == (canary.NO_BROKER, "the tools-in-loop call made no brokered call: its MCP "
                                                        "server did not load")


def test_the_canary_fails_when_the_loop_command_keeps_safe_mode(tmp_path, monkeypatch, user_file):
    # On Claude Code 2.1.325 --safe-mode turns off the server --mcp-config names
    # (docs/records/2026-11-15-claude-code-canary.json).
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    monkeypatch.setattr(harness, "LOOP_DROPPED_FLAGS", ())
    assert canary.canary("haiku") == (canary.NO_BROKER, "the tools-in-loop command carries --safe-mode, which "
                                                        "turns its brokered server off")


def test_the_canary_fails_when_the_loop_call_loses_its_isolation(tmp_path, monkeypatch, user_file):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    monkeypatch.setattr(harness, "LOOP_ISOLATION_FLAGS", ())
    monkeypatch.setattr(harness, "LOOP_ENV", ())
    assert canary.canary("haiku") == (canary.LEAKED, "the tools-in-loop call quoted the user-level instruction "
                                                     "file")


def test_the_record_shows_each_calls_command_and_the_loop_call_with_safe_mode_kept(
        tmp_path, monkeypatch, user_file, capsys):
    import json

    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    out = tmp_path / "record.json"
    assert canary.main(["--record", str(out)]) == canary.PASSED
    record = json.loads(out.read_text())
    control, seat, loop, kept = record["calls"]
    assert record["exit"] == 0 and record["outcome"] == "passed" and record["model"] == "haiku"
    assert control["quoted_user_file"] and "withheld" in control["answer"] and "Bonjour" not in out.read_text()
    assert "--safe-mode" not in control["argv"] and "--safe-mode" in seat["argv"] and not seat["quoted_user_file"]
    assert "--safe-mode" not in loop["argv"] and "--restricted" in loop["argv"] and "--mcp-config" in loop["argv"]
    assert loop["env"] == {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"} and loop["brokered_calls"] == 1
    assert "--safe-mode" in kept["argv"] and "--mcp-config" in kept["argv"] and kept["brokered_calls"] == 0
    assert loop["argv"][loop["argv"].index("--mcp-config") + 1] == "<server config>"
    assert harness.LOOP_DROPPED_FLAGS == ("--safe-mode",)  # restored after the kept call


def test_the_record_gives_a_call_that_never_started_no_command(tmp_path, monkeypatch, user_file):
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(_fake(tmp_path, "honours")))
    monkeypatch.setattr(canary, "_ask_loop", lambda model: ("", "Claude Code could not start", 0))
    record: list = []
    assert canary.canary("haiku", record)[0] == canary.INCONCLUSIVE
    assert [c["call"] for c in record] == ["control", "seat", "tools-in-loop",
                                           "tools-in-loop with --safe-mode kept (decides nothing)"]
    assert record[1]["argv"] and record[2]["argv"] is None and record[3]["argv"] is None


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
