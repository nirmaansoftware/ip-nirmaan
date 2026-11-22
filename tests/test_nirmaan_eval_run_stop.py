"""RR5: a live ``nirmaan eval run`` stops at the first trial with no model answer.

Council records 2026-11-15-pilot-topup-reruns (decision 4) and the pilot exit
addendum (gate RR5): on 2026-11-15 the plan's usage limit was reached and the
runner went on, so nine trials failed in two seconds each with no model answer.
The rule: the runner stops at the first trial that returns no model answer,
judged by the trial's structure and not by the wording of a message; that
trial stays recorded as failed (D11); no later trial starts; the run exits 3.

No test calls a model: a fake ``claude`` answers with the spec case's
reference spec, and from a chosen call on with the message the 2026-11-15 run
met.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan.cli import STOPPED_EXIT, app
from nirmaan.evals import ReplayLLM, load_record, load_records, no_model_answer
from nirmaan.runtime import ModelRuntime, register_runtime, unregister_runtime

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
RESULTS = EVALS / "results"
AXI = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
SPEC_CASE = "spec/axi4-lite-interface"
#: What Claude Code printed once the plan's limit was reached on 2026-11-15 (record ``-limit-12``, trial 1).
LIMIT = "You've hit your 5-hour limit · resets 3:50pm (Asia/Calcutta)"


def _claude(bindir: Path, limit_from: int) -> tuple[Path, Path]:
    """A ``claude`` that answers with the reference spec, and from call ``limit_from`` on reports the plan limit."""
    calls = bindir / "calls"
    spec = (AXI / "interface_spec.md").read_text()
    script = bindir / "claude"
    script.write_text(f"""#!{sys.executable}
import json, re, sys
from pathlib import Path
if "--version" in sys.argv:  # asked once per seat runtime for the harness; not a model call
    print("2.1.325 (Claude Code)")
    sys.exit(0)
prompt = sys.stdin.read()
calls = Path({str(calls)!r})
n = int(calls.read_text()) + 1 if calls.exists() else 1
calls.write_text(str(n))
if n >= {limit_from}:
    json.dump({{"type": "result", "subtype": "success", "is_error": True, "result": {LIMIT!r},
               "usage": {{"input_tokens": 0, "output_tokens": 0}}}}, sys.stdout)
    sys.exit(0)
cite = re.search(r"\\[artifact:[^\\]]+\\]", prompt)
meta = [{{"path": "interface_spec.md", "kind": "interface_spec", "title": "interface_spec.md",
          "summary": "spec from " + (cite.group(0) if cite else "nothing")}}]
head = json.dumps({{"uncertainty": 0.1, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                   "escalation": None, "notes": "fake claude"}})
text = head + "\\n=== FILE: interface_spec.md ===\\n" + {spec!r} + "=== END FILE ===\\n"
json.dump({{"type": "result", "subtype": "success", "is_error": False, "result": text,
           "usage": {{"input_tokens": 12, "output_tokens": 345}}, "modelUsage": {{"claude-opus-5-5": {{}}}}}},
          sys.stdout)
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script, calls


def _run(out: Path, runtime: str, trials: int):
    return CliRunner().invoke(app, ["eval", "run", "--runtime", runtime, "--trials", str(trials), "--seats", "spec",
                                    "--cases", str(EVALS), "--repo", str(REPO), "--out", str(out)])


@pytest.mark.parametrize("k", [1, 3, 4])
def test_a_run_stops_at_the_first_trial_with_no_model_answer(fixed_clock, tmp_path, monkeypatch, k):
    n = 4
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script, calls = _claude(bindir, limit_from=k)  # the spec case makes one model call per trial
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(script))
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    out = tmp_path / "results"
    ran = _run(out, "claude-code", n)
    assert ran.exit_code == STOPPED_EXIT == 3, ran.output
    assert int(calls.read_text()) == k  # no trial after k started
    [path] = list(out.iterdir())
    record = load_record(path)
    # k trials recorded, the k-th failed with the limit and kept (D11), nothing after it.
    assert [t.trial for t in record.trials] == list(range(1, k + 1))
    assert [t.result.passed for t in record.trials] == [True] * (k - 1) + [False]
    last = record.trials[-1]
    assert no_model_answer(last) and LIMIT in last.result.detail
    assert [a.error for a in last.answers] == [f"Claude Code reported success: {LIMIT}"]
    # The record is finished: its summary counts the k trials, the stopped one as a failure.
    summary = json.loads((path / "summary.json").read_text())
    assert summary["cases"][SPEC_CASE]["n"] == k and summary["cases"][SPEC_CASE]["passed"] == k - 1
    assert record.manifest.trials == n  # the planned count stays what was planned
    # The message names the stop and the limit.
    assert ran.output.count("PASS ") == k - 1 and ran.output.count(f"FAIL {SPEC_CASE}") == 1
    assert f"run stopped: {SPEC_CASE} trial {k} got no model answer" in ran.output
    assert "hit your 5-hour limit" in ran.output and "No further trial started" in ran.output


def test_a_model_that_answers_wrongly_does_not_stop_the_run(fixed_clock, tmp_path):
    bad = (AXI / "interface_spec.md").read_text().replace("[req:AXIL-SLVERR]", "")
    register_runtime("wrong-spec-seat")(
        lambda: ModelRuntime(ReplayLLM([("interface_spec.md", "interface_spec", bad, None)]),
                             runtime_id="wrong-spec-seat"))
    try:
        ran = _run(tmp_path / "results", "wrong-spec-seat", 3)
    finally:
        unregister_runtime("wrong-spec-seat")
    assert ran.exit_code == 1, ran.output  # every trial failed, and the run went on to the planned count
    assert ran.output.count(f"FAIL {SPEC_CASE}") == 3 and "run stopped" not in ran.output
    [path] = list((tmp_path / "results").iterdir())
    assert len(load_record(path).trials) == 3


def test_the_rule_reads_structure_and_matches_the_committed_limit_failures():
    trials = {(r.path.name, t.result.case, t.trial): t for r in load_records(RESULTS) if not r.manifest.replay
              for t in r.trials}
    stopped = {key for key, t in trials.items() if no_model_answer(t)}
    limited = {key for key, t in trials.items() if "hit your" in t.result.detail}
    assert stopped and stopped == limited  # the 2026-11-15 limit failures, and nothing a model answered
    first = trials[min(stopped)]
    # The same structure under any wording stops; one answer with text among failed calls does not.
    reworded = first.model_copy(update={"answers": tuple(a.model_copy(update={"error": "quota"}) for a in first.answers)})
    assert no_model_answer(reworded)
    answered = first.model_copy(update={"answers": (*first.answers, first.answers[0].model_copy(
        update={"error": None, "text": "{}"}))})
    assert not no_model_answer(answered)
    assert not no_model_answer(first.model_copy(update={"answers": ()}))  # no call made: nothing to stop on


@pytest.mark.parametrize("k", [1, 2])
def test_a_no_answer_on_attempt_one_stops_an_attempts_3_run_before_attempts_two_and_three(fixed_clock, tmp_path,
                                                                                          monkeypatch, k):
    """RR5 with ``--harness attempts-3`` (M74): the stop is judged on the trial, so a trial whose first attempt
    gets no model answer ends the run there; the other two attempts of that trial are not used, and no later
    trial starts."""
    n = 3
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script, calls = _claude(bindir, limit_from=k)
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(script))
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    out = tmp_path / "results"
    ran = CliRunner().invoke(app, ["eval", "run", "--runtime", "claude-code", "--trials", str(n), "--seats", "spec",
                                   "--harness", "attempts-3", "--cases", str(EVALS), "--repo", str(REPO),
                                   "--out", str(out)])
    assert ran.exit_code == STOPPED_EXIT == 3, ran.output
    assert int(calls.read_text()) == k  # one call per trial, none for attempts 2 and 3 of the stopped trial
    [path] = list(out.iterdir())
    record = load_record(path)
    assert record.manifest.harness_variant == "attempts-3"
    assert [t.trial for t in record.trials] == list(range(1, k + 1))
    last = record.trials[-1]
    assert no_model_answer(last) and not last.result.passed and len(last.answers) == 1 and last.result.attempts == 1
    assert f"run stopped: {SPEC_CASE} trial {k} got no model answer" in ran.output


def test_a_limit_on_attempt_two_after_an_answered_attempt_one_stops_the_run(fixed_clock, tmp_path, monkeypatch):
    """RR5 under attempts-3: attempt 1 answers (wrongly, so the seat tries again) and attempt 2 meets the plan's
    limit. The last answer decides, so the run stops there with exit 3 and no later trial starts."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # Attempt 1: the reference spec with no citation, which the seat's rules refuse, so it tries again.
    spec = (AXI / "interface_spec.md").read_text()
    calls = bindir / "calls"
    script = bindir / "claude"
    script.write_text(f"""#!{sys.executable}
import json, sys
from pathlib import Path
if "--version" in sys.argv:
    print("2.1.325 (Claude Code)")
    sys.exit(0)
sys.stdin.read()
calls = Path({str(calls)!r})
n = int(calls.read_text()) + 1 if calls.exists() else 1
calls.write_text(str(n))
if n >= 2:
    json.dump({{"type": "result", "subtype": "success", "is_error": True, "result": {LIMIT!r},
               "usage": {{"input_tokens": 0, "output_tokens": 0}}}}, sys.stdout)
    sys.exit(0)
meta = [{{"path": "interface_spec.md", "kind": "interface_spec", "title": "interface_spec.md", "summary": "spec"}}]
head = json.dumps({{"uncertainty": 0.1, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                   "escalation": None, "notes": "fake claude"}})
text = head + "\\n=== FILE: interface_spec.md ===\\n" + {spec!r} + "=== END FILE ===\\n"
json.dump({{"type": "result", "subtype": "success", "is_error": False, "result": text,
           "usage": {{"input_tokens": 12, "output_tokens": 345}}, "modelUsage": {{"claude-opus-5-5": {{}}}}}},
          sys.stdout)
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(script))
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    out = tmp_path / "results"
    ran = CliRunner().invoke(app, ["eval", "run", "--runtime", "claude-code", "--trials", "3", "--seats", "spec",
                                   "--harness", "attempts-3", "--cases", str(EVALS), "--repo", str(REPO),
                                   "--out", str(out)])
    assert ran.exit_code == STOPPED_EXIT == 3, ran.output
    assert int(calls.read_text()) == 2  # attempt 1 answered, attempt 2 met the limit, nothing after
    [path] = list(out.iterdir())
    record = load_record(path)
    assert [t.trial for t in record.trials] == [1]
    last = record.trials[0]
    assert len(last.answers) == 2 and last.answers[0].text and not last.answers[0].error
    assert not last.answers[1].text and last.answers[1].error
    assert no_model_answer(last) and not last.result.passed
    assert f"run stopped: {SPEC_CASE} trial 1 got no model answer" in ran.output
