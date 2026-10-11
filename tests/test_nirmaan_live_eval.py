"""Milestone 45: live evaluation as recorded, repeatable evidence.

``nirmaan eval run`` writes a run record (manifest, one trial file per case per
trial with the raw answers, hashes, judge runs, and accounting, and a summary
with Wilson intervals). ``nirmaan eval rejudge`` replays a record's answers
through the real gates and judges and compares verdicts. New spec and
firmware cases have real judges. M42 reads records, labelled by source.

No test calls a model: they use ``ReplayLLM``, ``MockLLM``, and a fake
``claude`` executable that answers with a case's reference file.
"""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from laws import needs

import nirmaan
from nirmaan.cli import app
from nirmaan.eval_proposals import eval_proposals, load_results
from nirmaan.evals import (
    ReplayLLM,
    load_case,
    load_cases,
    load_record,
    load_records,
    record_run,
    register_scorer,
    rejudge,
    run_case,
    select_cases,
    summarize,
    unregister_scorer,
    wilson,
)
from nirmaan.models import EvalTrial, Score, ScoreStatus
from nirmaan.runtime import ModelRuntime, register_runtime, unregister_runtime

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
SYNTHETIC = REPO / "tests" / "fixtures" / "eval_results_synthetic"
AXI = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
FW = REPO / "tests" / "fixtures" / "fw" / "axi4_lite"
SPEC_CASE = "spec/axi4-lite-interface"
FW_CASE = "firmware/axi4-lite-driver"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _case(case_id: str):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


def _fake_claude(tmp_path: Path, files: list[tuple[str, str, str]]) -> Path:
    """A ``claude`` that answers with ``files`` (name, kind, content), citing the first artifact token it is shown."""
    script = tmp_path / "claude"
    script.write_text(f"""#!{sys.executable}
import json, re, sys
prompt = sys.stdin.read()
cite = re.search(r"\\[artifact:[^\\]]+\\]", prompt)
files = {files!r}
meta = [{{"path": n, "kind": k, "title": n, "summary": n + " from " + (cite.group(0) if cite else "nothing")}}
        for n, k, _ in files]
head = json.dumps({{"uncertainty": 0.1, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                   "escalation": None, "notes": "fake claude"}})
text = head + "\\n" + "".join("=== FILE: " + n + " ===\\n" + c + "=== END FILE ===\\n" for n, _, c in files)
json.dump({{"type": "result", "subtype": "success", "is_error": False, "result": text,
           "usage": {{"input_tokens": 12, "output_tokens": 345, "cache_read_input_tokens": 6000,
                     "cache_creation_input_tokens": 800}}, "modelUsage": {{"claude-opus-5-5": {{}}}}}}, sys.stdout)
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture()
def spec_claude(tmp_path, monkeypatch):
    """The claude-code runtime, answered by a fake ``claude`` with the spec case's reference spec."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = _fake_claude(bindir, [("interface_spec.md", "interface_spec", (AXI / "interface_spec.md").read_text())])
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(script))
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    return script


# --- The run record ------------------------------------------------------------------------


def test_a_run_record_has_every_field(nirmaan_org, fixed_clock, tmp_path, spec_claude):
    path = record_run(nirmaan_org, [_case(SPEC_CASE)], "claude-code", trials=2, repo=REPO, out=tmp_path / "results",
                      command="nirmaan eval run --runtime claude-code --trials 2", clock=fixed_clock)
    assert path.parent == tmp_path / "results" and path.name == "2026-09-28-claude-code-claude-opus-5-5"
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["format"] == "nirmaan.eval-run" and manifest["id"] == path.name
    assert (manifest["runtime"], manifest["model"], manifest["replay"]) == ("claude-code", "claude-opus-5-5", False)
    assert manifest["trials"] == 2 and manifest["cases"] == [SPEC_CASE] and manifest["seats"] == ["interface-spec"]
    assert manifest["nirmaan_version"] == nirmaan.__version__ and "--trials 2" in manifest["command"]
    files = sorted((path / "spec_axi4-lite-interface").glob("*.json"))
    assert [f.name for f in files] == ["trial-01.json", "trial-02.json"]
    for number, file in enumerate(files, 1):
        trial = EvalTrial.model_validate_json(file.read_text())
        assert trial.format == "nirmaan.eval-trial" and trial.record == path.name and trial.trial == number
        assert trial.model == "claude-opus-5-5" and trial.result.runtime == "claude-code" and trial.result.passed
        [answer] = trial.answers
        assert answer.mode == "work" and answer.provider == "claude-code" and answer.model == "claude-opus-5-5"
        assert HEX64.match(answer.prompt_sha256) and HEX64.match(answer.packet_sha256)
        assert "=== FILE: interface_spec.md ===" in answer.text and "[req:AXIL-SLVERR]" in answer.text
        assert (answer.input_tokens, answer.output_tokens, answer.cache_read_tokens) == (12, 345, 6000)
        assert (trial.result.model_calls, trial.result.output_tokens, trial.result.cost_usd) == (1, 345, None)
        [judge] = trial.judge_runs
        assert judge.tool == "spec.check" and judge.succeeded and judge.run in trial.result.scores[0].runs
        assert judge.check == trial.result.scores[0].name and "checks" in judge.params
    summary = json.loads((path / "summary.json").read_text())
    assert summary["format"] == "nirmaan.eval-summary"
    case = summary["cases"][SPEC_CASE]
    assert (case["n"], case["passed"], case["rate"]) == (2, 2, 1.0)
    assert case["low"] == pytest.approx(wilson(2, 2)[0]) and case["high"] == 1.0
    assert summary["seats"]["interface-spec"]["n"] == 2
    assert summary["totals"] == {"trials": 2, "model_calls": 2, "input_tokens": 24, "output_tokens": 690,
                                 "cost_usd": None, "duration_s": pytest.approx(summary["totals"]["duration_s"])}
    # The same prompt twice: the same hashes. A second record never overwrites the first.
    a, b = (EvalTrial.model_validate_json(f.read_text()).answers[0] for f in files)
    assert (a.prompt_sha256, a.packet_sha256) == (b.prompt_sha256, b.packet_sha256)
    again = record_run(nirmaan_org, [_case(SPEC_CASE)], "claude-code", trials=1, repo=REPO,
                       out=tmp_path / "results", clock=fixed_clock)
    assert again.name == path.name + "-2" and (path / "spec_axi4-lite-interface" / "trial-02.json").exists()


def test_a_replay_is_recorded_as_a_replay(nirmaan_org, fixed_clock, tmp_path):
    path = record_run(nirmaan_org, [_case(SPEC_CASE)], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock)
    record = load_record(path)
    assert record.manifest.replay and record.manifest.runtime == "replay" and path.name.endswith("-replay-replay")
    [trial] = record.trials
    assert trial.result.replay and trial.answers[0].provider == "replay"


# --- Re-judging ----------------------------------------------------------------------------


def test_rejudging_a_record_reproduces_its_verdicts(nirmaan_org, fixed_clock, tmp_path, spec_claude):
    path = record_run(nirmaan_org, [_case(SPEC_CASE)], "claude-code", trials=2, repo=REPO, out=tmp_path / "r",
                      clock=fixed_clock)
    cases = {c.id: c for c in load_cases(EVALS)}
    outcomes = rejudge(nirmaan_org, load_record(path), cases, repo=REPO, sandbox=tmp_path / "sb")
    assert len(outcomes) == 2 and all(o.same for o in outcomes), [o.differences for o in outcomes]
    assert all(o.result.passed and o.result.scores[0].runs for o in outcomes)  # the judge ran again, for real

    # An answer edited after the fact: the judges, run again, rule differently, and it shows.
    trial_file = path / "spec_axi4-lite-interface" / "trial-01.json"
    data = json.loads(trial_file.read_text())
    data["answers"][0]["text"] = data["answers"][0]["text"].replace("[req:AXIL-SLVERR]", "")
    trial_file.write_text(json.dumps(data))
    [changed, same] = rejudge(nirmaan_org, load_record(path), cases, repo=REPO, sandbox=tmp_path / "sb2")
    assert not changed.same and same.same
    assert any("passed" in d for d in changed.differences), changed.differences

    # A case whose files changed is not comparable: reported, not silently re-judged.
    moved = {SPEC_CASE: cases[SPEC_CASE].model_copy(update={"constraints": ("something new",)})}
    outcomes = rejudge(nirmaan_org, load_record(path), moved, repo=REPO, sandbox=tmp_path / "sb3")
    assert all(not o.same and "case digest" in o.differences[0] for o in outcomes)


def test_the_cli_rejudges_and_fails_on_a_difference(nirmaan_org, fixed_clock, tmp_path, spec_claude):
    path = record_run(nirmaan_org, [_case(SPEC_CASE)], "claude-code", trials=1, repo=REPO, out=tmp_path,
                      clock=fixed_clock)
    ok = CliRunner().invoke(app, ["eval", "rejudge", str(path), "--cases", str(EVALS), "--repo", str(REPO)])
    assert ok.exit_code == 0, ok.output
    assert "same" in ok.output and "1 of 1 trials reproduced" in ok.output
    trial_file = next(path.rglob("trial-01.json"))
    data = json.loads(trial_file.read_text())
    data["answers"][0]["text"] = data["answers"][0]["text"].replace("s_axil_awaddr", "awaddr")
    trial_file.write_text(json.dumps(data))
    bad = CliRunner().invoke(app, ["eval", "rejudge", str(path), "--cases", str(EVALS), "--repo", str(REPO)])
    assert bad.exit_code == 1 and "DIFFERS" in bad.output


# --- Trials and intervals ------------------------------------------------------------------


def test_wilson_intervals_are_right():
    assert wilson(0, 0) is None
    low, high = wilson(5, 5)
    assert low == pytest.approx(0.5655, abs=1e-4) and high == 1.0
    low, high = wilson(0, 5)
    assert low == 0.0 and high == pytest.approx(0.4345, abs=1e-4)
    low, high = wilson(3, 10)
    assert low == pytest.approx(0.1078, abs=1e-4) and high == pytest.approx(0.6032, abs=1e-4)
    low, high = wilson(1, 1)
    assert low == pytest.approx(0.2065, abs=1e-4) and high == 1.0  # n=1 says little, and the interval shows it


def test_rates_are_per_case_and_per_seat(nirmaan_org, fixed_clock, tmp_path):
    base = run_case(nirmaan_org, _case(SPEC_CASE), repo=REPO, sandbox=tmp_path, clock=fixed_clock)

    def trial(case: str, stage: str, passed: bool, number: int) -> EvalTrial:
        result = base.model_copy(update={"case": case, "passed": passed, "model_calls": 1, "input_tokens": 10,
                                         "output_tokens": 100, "cost_usd": 0.5})
        return EvalTrial(record="r", trial=number, stage=stage, model="m", result=result)

    trials = ([trial("a/one", "stage-a", p, i) for i, p in enumerate([True, True, False], 1)]
              + [trial("a/two", "stage-a", p, i) for i, p in enumerate([True, False], 1)]
              + [trial("b/one", "stage-b", True, 1)])
    summary = summarize(trials)
    assert (summary["cases"]["a/one"]["n"], summary["cases"]["a/one"]["passed"]) == (3, 2)
    assert summary["cases"]["a/one"]["rate"] == pytest.approx(2 / 3)
    seat = summary["seats"]["stage-a"]
    assert (seat["n"], seat["passed"]) == (5, 3)
    assert (seat["low"], seat["high"]) == pytest.approx(wilson(3, 5))
    assert summary["seats"]["stage-b"] == {"n": 1, "passed": 1, "rate": 1.0, "low": pytest.approx(wilson(1, 1)[0]),
                                           "high": 1.0}
    assert summary["totals"]["cost_usd"] == pytest.approx(3.0) and summary["totals"]["output_tokens"] == 600


def test_the_cli_runs_trials_selects_seats_and_reports_honestly(fixed_clock, tmp_path, spec_claude):
    out = tmp_path / "results"
    ran = CliRunner().invoke(app, ["eval", "run", "--runtime", "claude-code", "--trials", "3", "--seats", "spec",
                                   "--cases", str(EVALS), "--repo", str(REPO), "--out", str(out)])
    assert ran.exit_code == 0, ran.output
    assert ran.output.count(f"PASS {SPEC_CASE}") == 3 and "rtl/" not in ran.output.replace(str(out), "")
    assert "3/3 passed (100%, 95% CI 44% to 100%)" in ran.output
    assert "fewer than 5 trials" in ran.output  # n is small, and the report says so
    [record] = list(out.iterdir())
    assert len(list(record.rglob("trial-*.json"))) == 3


def test_seats_select_by_group_or_stage():
    cases = load_cases(EVALS)
    assert [c.id for c in select_cases(cases, ["spec"])] == [SPEC_CASE]
    assert [c.id for c in select_cases(cases, ["firmware"])] == [FW_CASE]  # its group and its stage
    assert {c.seat for c in select_cases(cases, ["rtl"])} == {"rtl-implementation"}
    assert [c.id for c in select_cases(cases, ["interface-spec"])] == [SPEC_CASE]
    assert len(select_cases(cases, ["rtl", "spec", "firmware"])) == len(cases)
    assert select_cases(cases, []) == cases


# --- The new cases: real judges, and they fail bad answers ----------------------------------


def _bad_spec(**swap: str) -> str:
    text = (AXI / "interface_spec.md").read_text()
    for old, new in swap.items():
        assert old in text
        text = text.replace(old, new)
    return text


@pytest.mark.parametrize("why,swap", [
    ("a requirement's tag dropped", {"[req:AXIL-SLVERR]": ""}),
    ("ports named without their prefix", {"s_axil_": ""}),
    ("the error policy changed", {"SLVERR": "DECERR"}),
])
def test_the_spec_case_fails_a_bad_spec(nirmaan_org, fixed_clock, tmp_path, why, swap):
    case = _case(SPEC_CASE)
    llm = ReplayLLM([("interface_spec.md", "interface_spec", _bad_spec(**swap), None)])
    result = run_case(nirmaan_org, case, ModelRuntime(llm, runtime_id="bad-spec"), repo=REPO, sandbox=tmp_path,
                      clock=fixed_clock)
    assert result.submitted, result.detail  # it reached review: nothing before review catches it
    [score] = result.scores
    assert score.status is ScoreStatus.FAILED and score.runs, why
    assert not result.passed


def test_the_spec_case_passes_its_reference(nirmaan_org, fixed_clock, tmp_path):
    result = run_case(nirmaan_org, _case(SPEC_CASE), repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    assert result.passed, result.detail
    [score] = result.scores
    assert "8 of 8" in score.summary and "25 of 25" in score.summary


COSIM = ("cc", "make", "verilator", "iverilog", "vvp", "yosys")

#: A driver test that only reads reset values: it passes on a driver with the wrong map.
WEAK_FW_TEST = """\
#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    uint32_t value = 1u;
    axil_regs_init(&dev, hal);
    nirmaan_test_result("reads_reset", axil_regs_read(&dev, 0u, &value) == AXIL_REGS_OK && value == 0u, "reg0");
}
"""


@needs(*COSIM)
def test_the_firmware_case_passes_its_reference(nirmaan_org, fixed_clock, tmp_path):
    result = run_case(nirmaan_org, _case(FW_CASE), repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    assert result.passed, (result.detail, [s.summary for s in result.scores])
    assert {g.tool for g in result.gate_runs if g.succeeded} >= {"fw.build", "fw.test"}
    assert [s.status for s in result.scores] == [ScoreStatus.PASSED, ScoreStatus.PASSED]


@needs(*COSIM)
def test_the_firmware_case_catches_a_wrong_map_its_own_tests_miss(nirmaan_org, fixed_clock, tmp_path):
    files = [("axi4_lite_regs_map.h", "driver", (FW / "axi4_lite_regs_map_wrong.h").read_text(), None),
             ("axi4_lite_regs_drv.h", "driver", (FW / "axi4_lite_regs_drv.h").read_text(), None),
             ("axi4_lite_regs_drv.c", "driver", (FW / "axi4_lite_regs_drv.c").read_text(), None),
             ("weak_test.c", "driver_test", WEAK_FW_TEST, None)]
    result = run_case(nirmaan_org, _case(FW_CASE), ModelRuntime(ReplayLLM(files), runtime_id="weak-driver"),
                      repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    assert result.submitted, result.detail  # its own build and its own (weak) tests passed
    assert {g.tool for g in result.gate_runs if g.succeeded} >= {"fw.build", "fw.test"}
    build, test = result.scores
    assert build.status is ScoreStatus.PASSED
    assert test.status is ScoreStatus.FAILED and "index_reaches_the_specified_offset" in test.summary
    assert not result.passed


@needs(*COSIM)
def test_the_rtl_upstream_of_the_firmware_seat_passed_its_real_gates(nirmaan_org, fixed_clock, tmp_path):
    """A gated upstream stage is fixed through its own checks, never by a submission alone."""
    from nirmaan.models import TaskStatus
    from nirmaan.work import ProjectStore

    result = run_case(nirmaan_org, _case(FW_CASE), repo=REPO, sandbox=tmp_path, clock=fixed_clock)
    [state] = ProjectStore(tmp_path / ".nirmaan").list()
    rtl = next(t for t in state.tasks.values() if t.stage == "rtl-implementation")
    assert rtl.status is TaskStatus.COMPLETED
    tools = {state.tool_runs[r].tool for r in state.tool_runs if state.tool_runs[r].task == rtl.id
             and state.tool_runs[r].succeeded}
    assert tools >= {"lint.run", "simulator.run", "synth.run"}
    assert result.passed


# --- M42 reads real records ----------------------------------------------------------------


def test_m42_reads_records_alongside_the_synthetic_fixtures_labelled_by_source(nirmaan_org, fixed_clock, tmp_path,
                                                                               monkeypatch):
    bad = _bad_spec(**{"[req:AXIL-SLVERR]": ""})
    register_runtime("bad-spec-seat")(
        lambda: ModelRuntime(ReplayLLM([("interface_spec.md", "interface_spec", bad, None)]),
                             runtime_id="bad-spec-seat"))
    try:
        path = record_run(nirmaan_org, [_case(SPEC_CASE)], "bad-spec-seat", trials=3, repo=REPO,
                          out=tmp_path / "results", clock=fixed_clock)
    finally:
        unregister_runtime("bad-spec-seat")
    runs = load_results(tmp_path / "results") + load_results(SYNTHETIC)
    recorded = [r for r in runs if r.result.case == SPEC_CASE]
    assert len(recorded) == 3 and {r.source for r in recorded} == {f"record:{path.name}"}
    assert {r.source for r in runs if r.result.runtime.startswith("fixture-model-")} == {"file"}
    proposals = eval_proposals(nirmaan_org, runs, load_cases(EVALS))
    [real] = [p for p in proposals if p.subject == f"{SPEC_CASE}@bad-spec-seat"]
    assert real.count == 3 and {e["source"] for e in real.evidence} == {f"record:{path.name}"}
    assert any(p.subject.endswith("@fixture-model-a") and p.evidence[0]["source"] == "file" for p in proposals)
    # The CLI reads both directories and prints where each run came from.
    out = CliRunner().invoke(app, ["learn", "--evals", str(tmp_path / "results"), "--evals", str(SYNTHETIC),
                                   "--cases", str(EVALS)])
    assert out.exit_code == 0, out.output
    assert f"record:{path.name}" in out.output and "source file" in out.output


# --- The scheduled workflow ----------------------------------------------------------------

WORKFLOW = REPO / ".github" / "workflows" / "live-eval.yml"
GATE = REPO / "scripts" / "live_eval_gate.py"


def test_the_scheduled_workflow_never_runs_on_pull_requests():
    text = WORKFLOW.read_text()
    triggers = text.split("\non:", 1)[1].split("\njobs:", 1)[0]
    assert "schedule:" in triggers and "cron:" in triggers and "workflow_dispatch:" in triggers
    assert "pull_request" not in triggers and "push" not in triggers
    steps = text.split("steps:", 1)[1].split("\n      - ")[1:]
    gate = next(i for i, s in enumerate(steps) if "id: gate" in s)
    assert "live_eval_gate.py" in steps[gate] and "secrets.CLAUDE_CODE_OAUTH_TOKEN" in steps[gate]
    for step in steps[gate + 1:]:
        assert "if: steps.gate.outputs.enabled == 'true'" in step, step.splitlines()[0]


@pytest.mark.parametrize("secret,enabled", [(None, "false"), ("", "false"), ("sk-ant-oat-fake", "true")])
def test_the_gate_skips_cleanly_without_the_secret(tmp_path, secret, enabled):
    output = tmp_path / "github_output"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
    env["GITHUB_OUTPUT"] = str(output)
    if secret is not None:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = secret
    proc = subprocess.run([sys.executable, str(GATE)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert output.read_text().strip() == f"enabled={enabled}"
    if enabled == "false":
        assert "skipped" in proc.stdout and "CLAUDE_CODE_OAUTH_TOKEN" in proc.stdout
    assert secret is None or not secret or secret not in proc.stdout  # never echoes the secret


# --- spec.check on its own -------------------------------------------------------------------


def test_spec_check_judges_tags_terms_and_names(tmp_path):
    from nirmaan.integrations.spec_check import check_spec

    checks = EVALS / "spec" / "axi4_lite" / "interface_checks.json"
    passed, summary = check_spec([str(AXI / "interface_spec.md")], str(checks))
    assert passed and "8 of 8" in summary, summary
    twice = tmp_path / "twice.md"
    twice.write_text((AXI / "interface_spec.md").read_text() + "\n* Again. [req:AXIL-B2B]\n")
    passed, summary = check_spec([str(twice)], str(checks))
    assert not passed and "AXIL-B2B is tagged 2 times" in summary
    no_term = tmp_path / "no_term.md"
    no_term.write_text(_bad_spec(**{"unmapped addresses: SLVERR**": "unmapped addresses: an error**"}))
    passed, summary = check_spec([str(no_term)], str(checks))
    assert not passed and "AXIL-SLVERR does not say 'SLVERR'" in summary, summary
    with pytest.raises(ValueError, match="nirmaan.spec-checks"):
        bad = tmp_path / "bad.json"
        bad.write_text('{"requirements": []}')
        check_spec([str(AXI / "interface_spec.md")], str(bad))


# --- Crown jewel and laws --------------------------------------------------------------------


def test_a_new_seat_group_is_recorded_and_rejudged_with_no_core_changes(tmp_path):
    """A scorer, a case in a new group, and a runtime, all written here, go through run, history, and rejudge."""
    spec = (AXI / "interface_spec.md").read_text()

    @register_scorer("counts-tags")
    def _counts_tags(ctx) -> Score:
        runs = [ctx.tools.invoke("artifact.read", artifact=a)[0] for a in ctx.task.artifacts]
        return Score(scorer="counts-tags", name=ctx.check.name, status=ScoreStatus.PASSED,
                     summary=f"read back {len(runs)} artifacts", runs=tuple(runs))

    register_runtime("tmp-seat")(lambda: ModelRuntime(
        ReplayLLM([("interface_spec.md", "interface_spec", spec, None)]), runtime_id="tmp-seat"))
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "new.json").write_text(json.dumps({
        "id": "newgroup/interface", "request": "Create an AXI4-Lite register block.", "seat": "interface-spec",
        "expected_behavior": "A spec.", "reference": [{"path": str(AXI / "interface_spec.md"),
                                                      "kind": "interface_spec"}],
        "held_out": [{"name": "every artifact reads back", "scorer": "counts-tags"}]}))
    out = tmp_path / "results"
    try:
        ran = CliRunner().invoke(app, ["eval", "run", "--runtime", "tmp-seat", "--trials", "2", "--seats",
                                       "newgroup", "--cases", str(cases), "--repo", str(REPO), "--out", str(out)])
        assert ran.exit_code == 0, ran.output
        [record] = list(out.iterdir())
        history = CliRunner().invoke(app, ["eval", "history", "--results", str(out)])
        assert history.exit_code == 0, history.output
        assert record.name in history.output and "interface-spec: 2/2 passed" in history.output
        assert "newgroup/interface: 2/2 passed" in history.output
        as_json = json.loads(CliRunner().invoke(app, ["eval", "history", "--results", str(out), "--json"]).output)
        assert as_json[0]["id"] == record.name and as_json[0]["summary"]["seats"]["interface-spec"]["n"] == 2
        again = CliRunner().invoke(app, ["eval", "rejudge", str(record), "--cases", str(cases), "--repo", str(REPO)])
        assert again.exit_code == 0, again.output
        assert "2 of 2 trials reproduced" in again.output
    finally:
        unregister_scorer("counts-tags")
        unregister_runtime("tmp-seat")
    assert [r.manifest.id for r in load_records(out)] == [record.name]


def test_records_and_spec_check_keep_the_laws(nirmaan_org):
    """The record code names no stage, tool, kind, or role, and imports no VeriTriage."""
    org = nirmaan_org
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles) | set(org.tools)
                  | {s.id for w in org.workflows.values() for s in w.stages}
                  | {k for w in org.workflows.values() for s in w.stages for k in s.outputs})
    package = Path(nirmaan.__file__).parent
    for path in (package / "evals" / "records.py", package / "integrations" / "spec_check.py",
                 package / "eval_proposals.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(n.startswith("veritriage") for n in names), path
        if path.parent.name == "evals":
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert node.value not in vocabulary, f"{path.name} hard-codes {node.value!r}"


def test_the_case_loader_skips_data_files():
    """Checks files and run records under evals/ carry a format and are never read as cases."""
    ids = [c.id for c in load_cases(EVALS)]
    assert SPEC_CASE in ids and FW_CASE in ids and len(ids) == 6
    assert load_case(EVALS / "spec" / "axi4_lite_interface.json").seat == "interface-spec"
