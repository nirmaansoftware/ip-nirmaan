"""The claude-code runtime: a seat filled through ``claude -p``, on the person's own Claude plan.

Every test runs a fake ``claude`` script the test writes, which records how it
was called and answers with Claude Code's JSON. No test calls a model.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from nirmaan_helpers import drive, tid

from nirmaan.demos import demo
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, ResultStatus, get_runtime, run_task
from nirmaan.runtime.claude_code import ClaudeCodeLLM


def _fake_claude(tmp_path: Path, answer: dict | str, exit_code: int = 0) -> tuple[Path, Path]:
    """A ``claude`` that records its argv, stdin, cwd, and credential variables, then prints ``answer``."""
    record = tmp_path / "call.json"
    body = answer if isinstance(answer, str) else json.dumps(answer)
    script = tmp_path / "claude"
    script.write_text(f"""#!/usr/bin/env python3
import json, os, sys
json.dump({{"argv": sys.argv[1:], "stdin": sys.stdin.read(), "cwd": os.getcwd(),
           "key": os.environ.get("ANTHROPIC_API_KEY"), "token": os.environ.get("ANTHROPIC_AUTH_TOKEN")}},
          open({str(record)!r}, "w"))
sys.stdout.write({body!r})
sys.exit({exit_code})
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script, record


def _result(text: str, **extra) -> dict:
    return {"type": "result", "subtype": "success", "is_error": False, "result": text, "total_cost_usd": 0.42,
            "usage": {"input_tokens": 12, "output_tokens": 345, "cache_read_input_tokens": 6000,
                      "cache_creation_input_tokens": 800}, "modelUsage": {"claude-opus-5-5": {}}, **extra}


@pytest.fixture()
def triage(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(demo("4").requirement)
    task = tid(engine, "triage")
    drive(engine, until=task)
    return engine, task


def test_the_call_is_clean_and_uses_the_plan_not_a_key(triage, tmp_path, monkeypatch):
    engine, task = triage
    script, record = _fake_claude(tmp_path, _result("not json, but a reply"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-should-not-leak")
    run_task(engine, task, ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code"))
    call = json.loads(record.read_text())
    argv = call["argv"]
    assert argv[:3] == ["-p", "--output-format", "json"] and argv[argv.index("--model") + 1] == "claude-opus-5-5"
    assert argv[argv.index("--tools") + 1] == "" and "--no-session-persistence" in argv
    assert "--strict-mcp-config" in argv and argv[argv.index("--system-prompt") + 1]
    assert "## Company" in call["stdin"] and argv[argv.index("--system-prompt") + 1] not in call["stdin"]
    assert call["key"] is None and call["token"] is None  # the plan login, never a key
    assert Path(call["cwd"]).name.startswith("nirmaan-claude-code-") and not Path(call["cwd"]).exists()


def test_a_reply_is_a_recorded_call_with_tokens_and_no_invented_cost(triage, tmp_path):
    engine, task = triage
    script, _ = _fake_claude(tmp_path, _result("I think it is an RTL bug."))
    report = run_task(engine, task, ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code"))
    assert report.status is ResultStatus.DECLINED  # not JSON: declined, as for any seat
    [call] = engine.state.model_calls.values()
    assert call.provider == "claude-code" and call.model == "claude-opus-5-5" and call.succeeded
    assert (call.input_tokens, call.output_tokens, call.cache_read_tokens, call.cache_write_tokens) == (12, 345, 6000, 800)
    assert call.cost_usd is None  # a subscription has no per-call price; total_cost_usd is an estimate


#: Claude Code's side call on a small model, listed first in ``modelUsage`` on a real ``-p`` run.
SIDE_CALL = {"claude-haiku-5-5": {"inputTokens": 300, "outputTokens": 20}}


def test_the_model_asked_for_is_recorded_when_a_side_call_is_listed_first(triage, tmp_path):
    engine, task = triage
    usage = {**SIDE_CALL, "claude-opus-5-5": {"inputTokens": 12, "outputTokens": 345}}
    assert next(iter(usage)) == "claude-haiku-5-5"
    script, _ = _fake_claude(tmp_path, _result("reply", modelUsage=usage))
    run_task(engine, task, ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code"))
    [call] = engine.state.model_calls.values()
    assert call.model == "claude-opus-5-5" and call.output_tokens == 345


def test_a_failed_call_records_the_model_asked_for_too(triage, tmp_path):
    engine, task = triage
    usage = {**SIDE_CALL, "claude-opus-5-5": {"outputTokens": 1}}
    script, _ = _fake_claude(tmp_path, {"type": "result", "subtype": "error_max_turns", "is_error": True,
                                        "result": "stopped", "modelUsage": usage}, exit_code=1)
    run_task(engine, task, ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code"))
    [call] = engine.state.model_calls.values()
    assert not call.succeeded and call.model == "claude-opus-5-5"


@pytest.mark.parametrize("usage, recorded", [
    # The model asked for is absent: the one that wrote most, never the first key.
    ({**SIDE_CALL, "claude-sonnet-5-5": {"outputTokens": 900}}, "claude-sonnet-5-5"),
    # A tie for most is every tied model, never one picked.
    ({"claude-b": {"outputTokens": 7}, "claude-a": {"outputTokens": 7}, "claude-c": {"outputTokens": 1}},
     "claude-a+claude-b"),
    ({"claude-a": {}, "claude-b": "not a mapping"}, "claude-a+claude-b"),
    # Nothing reported: the model asked for.
    ({}, "claude-opus-5-5"),
    (None, "claude-opus-5-5"),
])
def test_without_the_model_asked_for_the_one_that_wrote_most_is_recorded(usage, recorded):
    from nirmaan.runtime.claude_code import answered_by

    assert answered_by("claude-opus-5-5", usage) == recorded


@pytest.mark.parametrize("answer,code,why", [
    ({"type": "result", "subtype": "error_max_turns", "is_error": True, "result": "stopped"}, 1, "error_max_turns"),
    ("Invalid API key or not logged in", 1, "without a JSON result"),
])
def test_a_failed_call_is_recorded_as_failed(triage, tmp_path, answer, code, why):
    engine, task = triage
    script, _ = _fake_claude(tmp_path, answer, exit_code=code)
    report = run_task(engine, task, ModelRuntime(ClaudeCodeLLM(executable=str(script)), runtime_id="claude-code"))
    assert report.status is ResultStatus.DECLINED and why in report.detail
    [call] = engine.state.model_calls.values()
    assert not call.succeeded and why in call.error and call.cost_usd is None


def test_no_executable_declines_without_a_call(triage, monkeypatch):
    engine, task = triage
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")
    report = run_task(engine, task, get_runtime("claude-code"))
    assert report.status is ResultStatus.DECLINED and "no Claude Code executable" in report.detail
    assert not engine.state.model_calls


def test_an_evaluation_runs_on_the_claude_code_runtime(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    from test_nirmaan_evals import _spec_case

    from nirmaan.evals import load_case, run_case

    script, _ = _fake_claude(tmp_path, _result("unusable"))
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(script))
    case = load_case(_spec_case(tmp_path, []))
    result = run_case(nirmaan_org, case, get_runtime("claude-code"), repo=tmp_path, sandbox=tmp_path / "sb",
                      clock=fixed_clock)
    assert result.runtime == "claude-code" and result.model_calls == 1 and result.output_tokens == 345
    assert result.cost_usd is None and not result.passed
