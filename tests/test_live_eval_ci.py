"""W2-L1-CI: the live evaluation in GitHub Actions runs one trial at a time and stops as the rules say.

`scripts/live_eval_ci.py` is what `.github/workflows/live-eval.yml` runs. No test calls a model: the trials
either come from a fake runner or from the real `nirmaan eval run` with a fake `claude` on the spec case.
"""

from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from laws import needs

from nirmaan.evals import load_record
from nirmaan.runtime.harness import harness_sha256

REPO = Path(__file__).resolve().parents[1]
SPEC_CASE = "spec/axi4-lite-interface"
AXI = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
LIMIT = "You've hit your 5-hour limit"


def _script():
    spec = importlib.util.spec_from_file_location("live_eval_ci", REPO / "scripts" / "live_eval_ci.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = _script()


def _opts(**over) -> dict:
    env = {"CASE": SPEC_CASE, "TRIALS": "3", "KNOWLEDGE": "on", "PURPOSE": "evidence", "HARNESS": "default",
           "EXPECTED": ""}
    env.update(over)
    return ci.options(env)


def test_the_cli_pin_is_2_1_325_with_integrity_hashes():
    assert ci.pinned_cli() == "2.1.325"
    lock = json.loads((REPO / ".github" / "live-eval" / "package-lock.json").read_text())["packages"]
    assert lock["node_modules/@anthropic-ai/claude-code"]["version"] == "2.1.325"


@pytest.mark.parametrize("over", [{"CASE": "dv/no-such-case"}, {"CASE": ""}, {"TRIALS": "0"}, {"TRIALS": "21"},
                                  {"TRIALS": "two"}, {"KNOWLEDGE": "maybe"}, {"PURPOSE": "practice"},
                                  {"HARNESS": "attempts-9"}])
def test_bad_input_is_refused_before_anything_runs(over):
    with pytest.raises(ci.Stop) as stop:
        _opts(**over)
    assert stop.value.code == ci.BAD_INPUT


def test_the_ci_only_cases_are_known():
    assert _opts(CASE="dv/cocotb-crc")["case"] == "dv/cocotb-crc"


def test_the_fingerprint_is_printed_and_checked(capsys):
    want = harness_sha256(cli="2.1.325", knowledge=False, variant="attempts-3")
    opts = _opts(KNOWLEDGE="off", HARNESS="attempts-3")
    assert ci.check(opts, require_expected=False, cli="2.1.325") == want
    assert f"harness: {want}" in capsys.readouterr().out
    assert ci.check({**opts, "expected": want}, require_expected=True, cli="2.1.325") == want
    for expected, cli, code in [(want, "2.1.283", ci.MISMATCH), (want, None, ci.MISMATCH),
                                (harness_sha256(cli="2.1.325"), "2.1.325", ci.MISMATCH), ("", "2.1.325", ci.BAD_INPUT)]:
        with pytest.raises(ci.Stop) as stop:
            ci.check({**opts, "expected": expected}, require_expected=True, cli=cli)
        assert stop.value.code == code


def test_the_command_is_one_trial_with_the_flags_asked_for(tmp_path):
    base = ["nirmaan", "eval", "run", SPEC_CASE, "--runtime", "claude-code", "--trials", "1", "--purpose", "evidence",
            "--out", str(tmp_path)]
    assert ci.command(_opts(), tmp_path) == base
    assert ci.command(_opts(KNOWLEDGE="off", HARNESS="tools-in-loop", PURPOSE="calibration"), tmp_path) == [
        *base[:9], "calibration", *base[10:], "--without-knowledge", "--harness", "tools-in-loop"]


DIGEST = harness_sha256(cli="2.1.325")


def _runner(codes, *, outputs=None, trial=None):
    """A fake `eval run`: each call writes one record and returns the next exit code and output."""
    calls = []

    def run(argv):
        out = Path(argv[argv.index("--out") + 1])
        calls.append(list(argv))
        record = out / f"record-{len(calls)}"
        body = {"purpose": "evidence", "knowledge": "on", "harness_variant": "default",
                "result": {"harness": DIGEST, "cli": "2.1.325"}, "answers": [{"harness": DIGEST}]}
        body.update(trial or {})
        path = record / SPEC_CASE.replace("/", "_") / "trial-01.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(body))
        return codes[len(calls) - 1], (outputs or [""] * len(codes))[len(calls) - 1]

    return run, calls


def _trial_dir_matches_records_module():
    from nirmaan.evals.records import trial_path

    return trial_path(Path("r"), SPEC_CASE, 1) == Path("r") / SPEC_CASE.replace("/", "_") / "trial-01.json"


def test_every_trial_runs_once_and_a_failed_trial_does_not_stop_the_batch(tmp_path, capsys):
    assert _trial_dir_matches_records_module()
    run, calls = _runner([0, 1, 0])
    assert ci.run_trials(_opts(), tmp_path, DIGEST, "2.1.325", run) == 0
    assert len(calls) == 3 and all(c.count("--trials") == 1 and c[c.index("--trials") + 1] == "1" for c in calls)
    assert "done: 3 of 3 trials ran, 2 passed" in capsys.readouterr().out


@pytest.mark.parametrize("codes,outputs,stop_code", [([0, 3, 0], None, ci.STOPPED_LIMIT),
                                                      ([0, 1, 0], ["", LIMIT, ""], ci.STOPPED_LIMIT),
                                                      ([0, -9, 0], None, ci.STOPPED_OTHER),
                                                      ([0, 2, 0], None, ci.STOPPED_OTHER)])
def test_a_limit_or_an_odd_exit_stops_the_batch_and_nothing_is_run_again(tmp_path, codes, outputs, stop_code):
    run, calls = _runner(codes, outputs=outputs)
    with pytest.raises(ci.Stop) as stop:
        ci.run_trials(_opts(), tmp_path, DIGEST, "2.1.325", run)
    assert stop.value.code == stop_code and len(calls) == 2  # trial 3 never started; trial 2 never re-ran
    assert "trial 2" in str(stop.value) and "never run again" in str(stop.value)
    assert "Trial 3 did not start" in str(stop.value)


def test_the_script_runs_without_its_docstring():
    # `python -OO` strips docstrings to None; the help text must not depend on one.
    proc = subprocess.run([sys.executable, "-OO", str(REPO / "scripts" / "live_eval_ci.py"), "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "one at a time" in proc.stdout and "check" in proc.stdout and "trials" in proc.stdout


@pytest.mark.parametrize("trial", [{"purpose": "calibration"}, {"knowledge": "off"}, {"harness_variant": "attempts-3"},
                                   {"result": None}, {"answers": [None]},
                                   {"result": {"harness": "sha256:other", "cli": "2.1.325"}},
                                   {"result": {"harness": DIGEST, "cli": "2.1.283"}},
                                   {"answers": [{"harness": "sha256:other"}]}])
def test_a_record_that_is_not_the_trial_asked_for_stops_the_batch(tmp_path, trial):
    run, calls = _runner([0, 0, 0], trial=trial)
    with pytest.raises(ci.Stop) as stop:
        ci.run_trials(_opts(), tmp_path, DIGEST, "2.1.325", run)
    assert stop.value.code == ci.MISMATCH and len(calls) == 1


def test_a_record_with_no_answers_is_read_by_its_result(tmp_path):
    # A trial whose seat made no model call has no answers (null or empty); its result still names the harness.
    for answers in (None, []):
        run, calls = _runner([0], trial={"answers": answers})
        assert ci.run_trials(_opts(TRIALS="1"), tmp_path / str(answers), DIGEST, "2.1.325", run) == 0


def _claude(bindir: Path, limit_from: int) -> Path:
    """A fake `claude` that answers the spec case with its reference spec, and from call `limit_from` on with a
    plan limit (as tests/test_nirmaan_eval_run_stop.py)."""
    calls = bindir / "calls"
    spec = (AXI / "interface_spec.md").read_text()
    script = bindir / "claude"
    script.write_text(f"""#!{sys.executable}
import json, re, sys
from pathlib import Path
if "--version" in sys.argv:
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
    return calls


def test_the_real_eval_run_stops_at_the_limit_with_one_record_per_trial(tmp_path, monkeypatch, capsys):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = _claude(bindir, limit_from=3)
    monkeypatch.setenv("NIRMAAN_CLAUDE_CODE", str(bindir / "claude"))
    monkeypatch.delenv("NIRMAAN_CLAUDE_CODE_MODEL", raising=False)
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(ci, "NIRMAAN", (sys.executable, "-c", "import sys; from nirmaan.cli import app; app()"))
    for key, value in {"CASE": SPEC_CASE, "TRIALS": "5", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                       "HARNESS": "default", "EXPECTED": DIGEST}.items():
        monkeypatch.setenv(key, value)
    out = tmp_path / "results"
    assert ci.main(["trials", "--out", str(out)]) == ci.STOPPED_LIMIT
    assert int(calls.read_text()) == 3  # trials 4 and 5 never started
    records = sorted(out.iterdir())
    assert len(records) == 3  # one record per trial, the limit trial kept as failed
    trials = [load_record(r).trials for r in records]
    assert all(len(t) == 1 for t in trials)
    assert sorted(t[0].result.passed for t in trials) == [False, True, True]
    assert all(t[0].result.harness == DIGEST and t[0].result.cli == "2.1.325" for t in trials)
    err = capsys.readouterr().err
    assert "STOP: trial 3 hit a plan or usage limit" in err and "Trials 4 to 5 did not start" in err


# --- Gate WF17: the checkout's tree hash and seat C ------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / ".gitignore").write_text("__pycache__/\nbuild/\n")
    (root / "src" / "pkg" / "judge.py").write_text("PASS = False\n")
    (root / "docs" / "a.md").write_text("a\n")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
        subprocess.run(["git", "-C", str(root), *args], check=True)
    return root


def test_the_tree_hash_sees_every_change_to_the_checkout(tmp_path):
    root = _repo(tmp_path)
    base = ci.tree_digest(ci.tree_manifest(root))
    assert ci.tree_digest(ci.tree_manifest(root)) == base
    (root / "build").mkdir()
    (root / "build" / "out.txt").write_text("ignored outside src, scripts and evals\n")
    assert ci.tree_digest(ci.tree_manifest(root)) == base
    changes = [
        lambda: (root / "src" / "pkg" / "judge.py").write_text("PASS = True\n"),  # a tracked file edited
        lambda: (root / "docs" / "new.md").write_text("x"),  # an untracked file
        lambda: ((root / "src" / "pkg" / "__pycache__").mkdir(), (root / "src" / "pkg" / "__pycache__" /
                                                                 "judge.cpython-312.pyc").write_bytes(b"x")),
        lambda: (root / "docs" / "a.md").chmod(0o755),  # a mode
        lambda: (root / "docs" / "a.md").unlink(),  # a deletion
        lambda: (root / "src" / "link").symlink_to("/etc"),  # a link under src
    ]
    for change in changes:
        root = _repo(tmp_path / str(len(list(tmp_path.iterdir()))))
        before = ci.tree_digest(ci.tree_manifest(root))
        change()
        assert ci.tree_digest(ci.tree_manifest(root)) != before


def test_the_tree_mode_needs_no_case_and_writes_its_manifest(tmp_path, monkeypatch, capsys):
    for key in ("CASE", "TRIALS", "EXPECTED"):
        monkeypatch.delenv(key, raising=False)
    manifest = tmp_path / "tree.txt"
    assert ci.main(["tree", "--write", str(manifest)]) == 0
    lines = manifest.read_text().splitlines()
    assert lines[0].startswith("commit ") and capsys.readouterr().out.strip() == ci.tree_digest(lines)
    assert any(line.startswith("file ") and line.split()[2] == "scripts/live_eval_ci.py" for line in lines)


def test_a_live_trial_of_a_case_that_runs_seat_c_is_refused_but_the_lifted_single_seat_case():
    """Gate SC7 (council record 2026-11-19, seat C and the live refusal): the lift covers firmware/axi4-lite-driver
    only, a single-seat case; every other case that runs seat C is still refused live (exit 6)."""
    assert ci.SEAT_C_LIVE == ("firmware/axi4-lite-driver",)
    assert ci.seat_c_problem("dv/cocotb-crc") is None and ci.seat_c_problem(SPEC_CASE) is None
    cases = {c.id: c for c in ci._cases()}
    assert all(cases[case].flow == "seat" and ci.seat_c_use(case) for case in ci.SEAT_C_LIVE)
    assert ci.seat_c_problem("firmware/axi4-lite-driver") is None
    others = [case for case in cases if ci.seat_c_use(case) and case not in ci.SEAT_C_LIVE]
    assert REGS_FLOW in others
    for case in others:
        problem = ci.seat_c_problem(case)
        assert problem and "fw.test" in problem and "WF17" in problem and "No trial ran" in problem, case


def test_main_runs_the_lifted_case_only_on_this_jobs_record_and_a_replay_check_runs(monkeypatch, capsys):
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    digest = harness_sha256(cli="2.1.325")
    for key, value in {"CASE": "firmware/axi4-lite-driver", "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                       "HARNESS": "default", "EXPECTED": digest}.items():
        monkeypatch.setenv(key, value)
    for key in [*JOB_ENV, ci.FW_REACH_ENV]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: pytest.fail("a trial started"))
    # check runs before the job's credential test, so it leaves the record to trials, which refuses without it.
    assert ci.main(["check", "--require-expected"]) == 0
    assert ci.main(["trials", "--out", "/nonexistent"]) == ci.UNCONFINED
    assert "gate WF17" in capsys.readouterr().err
    assert ci.main(["check"]) == 0


# --- M90, gate WF17: a job runs a case's seat C only on its own credential test record ----------------------------

JOB_ENV = {"GITHUB_RUN_ID": "77", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "live-eval"}


def _fw_record(tmp_path, **over):
    record = {"format": "nirmaan.fw-reach/1", "tool": "fw.test", "head": "c0ffee",
              "run": {"id": "77", "attempt": "1", "job": "live-eval", "ref": "refs/heads/main"},
              "require_denied": True, "every_probe_denied": True, "done": True, "control_ok": True, "missing": [],
              "seat_exec": "/opt/nirmaan-seat/bin/nirmaan-seat-exec", **over}
    path = tmp_path / f"fw-reach-{len(list(tmp_path.glob('fw-reach-*.json')))}.json"  # one file per record
    path.write_text(json.dumps(record))
    return {**JOB_ENV, ci.FW_REACH_ENV: str(path)}


def test_a_credential_test_record_counts_only_for_its_own_job_commit_and_gate_run(tmp_path, monkeypatch):
    assert ci.fw_reach_problem(_fw_record(tmp_path), "c0ffee") is None
    bad = [({}, "not set"), ({ci.FW_REACH_ENV: str(tmp_path / "none.json"), **JOB_ENV}, "cannot be read")]
    for over, why in [({"run": {"id": "76", "attempt": "1", "job": "live-eval"}}, "not this job's"),
                      ({"run": {"id": "77", "attempt": "2", "job": "live-eval"}}, "not this job's"),
                      ({"run": {"id": "77", "attempt": "1", "job": "replay"}}, "not this job's"),
                      ({"head": "beef"}, "not this checkout's"), ({"format": "x"}, "not one of"),
                      ({"require_denied": False}, "without --require-denied"),
                      ({"require_denied": None}, "without --require-denied"),
                      ({"every_probe_denied": False}, "every probe denied"), ({"done": False}, "every probe denied"),
                      ({"control_ok": False}, "every probe denied"), ({"missing": ["fw_reach_no_sudo"]}, "every probe"),
                      ({"seat_exec": None}, "seat wrapper")]:
        bad.append((_fw_record(tmp_path, **over), why))
    for env, why in bad:
        problem = ci.fw_reach_problem(env, "c0ffee")
        assert problem and why in problem, (env, problem)
    record = _fw_record(tmp_path)
    for name in JOB_ENV:  # outside a job nothing names the job, so no record is this job's
        assert "not this job's" in ci.fw_reach_problem({k: v for k, v in record.items() if k != name}, "c0ffee")
    assert "not this checkout's" in ci.fw_reach_problem(record, None)


def test_a_job_runs_a_cases_seat_c_only_on_its_own_credential_test_record(tmp_path, monkeypatch, capsys):
    """Gate WF17 covers every job that runs seat code: the replay and the re-judge run seat C only on their own job's
    credential test record, and fail closed without it."""
    monkeypatch.setattr(ci, "_head", lambda: "c0ffee")
    for case in ("firmware/axi4-lite-driver", REGS_FLOW_CASE):
        assert ci.seat_c_use(case)
        assert ci.confined_problem(case, _fw_record(tmp_path)) is None
        for env in ({}, _fw_record(tmp_path, every_probe_denied=False), _fw_record(tmp_path, require_denied=False),
                    {**_fw_record(tmp_path), "GITHUB_JOB": "replay"}):
            problem = ci.confined_problem(case, env)
            assert problem and "WF17" in problem and "Nothing ran" in problem, (case, env)
    for case in ("dv/cocotb-crc", TIMER_FLOW):  # no seat C: the cocotb reach test is enough
        assert ci.seat_c_use(case) is None and ci.confined_problem(case, {}) is None
    for key in [*JOB_ENV, ci.FW_REACH_ENV, "CASE"]:
        monkeypatch.delenv(key, raising=False)
    assert ci.main(["confined"]) == ci.BAD_INPUT
    monkeypatch.setenv("CASE", "no/such-case")
    assert ci.main(["confined"]) == ci.BAD_INPUT
    monkeypatch.setenv("CASE", "firmware/axi4-lite-driver")
    assert ci.main(["confined"]) == ci.UNCONFINED and "Nothing ran" in capsys.readouterr().err
    for key, value in _fw_record(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert ci.main(["confined"]) == 0 and "executes as the seat account" in capsys.readouterr().out
    monkeypatch.setenv("CASE", TIMER_FLOW)
    assert ci.main(["confined"]) == 0 and "runs no seat C" in capsys.readouterr().out


def test_a_passing_credential_test_lifts_the_live_refusal_for_the_single_seat_case_only(tmp_path, monkeypatch):
    """A record that counts does not lift exit 6 by itself: gate SC7 lifts it for firmware/axi4-lite-driver only
    (council record 2026-11-19, seat C and the live refusal). The register block flow stays refused with it."""
    monkeypatch.setattr(ci, "_head", lambda: "c0ffee")
    for key, value in _fw_record(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert ci.seat_c_problem("firmware/axi4-lite-driver") is None
    problem = ci.seat_c_problem(REGS_FLOW_CASE)
    assert problem and "WF17" in problem and "WF15 to WF19" in problem and "No trial ran" in problem


# --- G3 step 5: whole-flow cases on the same path (council record 2026-11-17, decision 4) ----------------------

TIMER_FLOW, REGS_FLOW = "flow/axil-timer", "flow/axi4-lite-regs-driver"
REGS_FLOW_CASE = REGS_FLOW


def test_a_whole_flow_case_is_known_when_named_one_trial_per_dispatch_on_the_default_harness():
    opts = _opts(CASE=TIMER_FLOW, TRIALS="1")
    assert opts["flow"] == "whole" and _opts()["flow"] == "seat"
    for over in ({"TRIALS": "2"}, {"TRIALS": "1", "HARNESS": "attempts-3"}, {"TRIALS": "1", "HARNESS": "tools-in-loop"}):
        with pytest.raises(ci.Stop) as stop:
            _opts(CASE=TIMER_FLOW, **over)
        assert stop.value.code == ci.BAD_INPUT and "one trial per dispatch" in str(stop.value)


def test_a_whole_flow_case_runs_in_the_whole_flow_fingerprint_and_the_single_seat_one_is_unchanged(capsys):
    for knowledge in ("on", "off"):
        opts = _opts(CASE=TIMER_FLOW, TRIALS="1", KNOWLEDGE=knowledge)
        want = harness_sha256(cli="2.1.325", knowledge=knowledge == "on", flow="whole")
        assert want != harness_sha256(cli="2.1.325", knowledge=knowledge == "on")
        assert ci.check({**opts, "expected": want}, require_expected=True, cli="2.1.325") == want
        assert "flow whole" in capsys.readouterr().out
    assert ci.check(_opts(), require_expected=False, cli="2.1.325") == DIGEST


def test_the_register_block_flow_is_refused_live_and_the_timer_flow_is_not():
    assert ci.seat_c_problem(TIMER_FLOW) is None
    problem = ci.seat_c_problem(REGS_FLOW)
    assert problem and "the firmware stage" in problem and "fw.test" in problem and "WF17" in problem


def test_main_refuses_the_register_block_flow_before_any_trial_and_checks_the_timer_flow(monkeypatch, capsys):
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: pytest.fail("a trial started"))
    for case, code in ((REGS_FLOW, ci.UNCONFINED), (TIMER_FLOW, 0)):
        for key, value in {"CASE": case, "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                           "HARNESS": "default", "EXPECTED": harness_sha256(cli="2.1.325", flow="whole")}.items():
            monkeypatch.setenv(key, value)
        assert ci.main(["check", "--require-expected"]) == code
    assert "gate WF17" in capsys.readouterr().err


def test_a_whole_flow_record_must_carry_the_label_and_the_whole_flow_fingerprint(tmp_path):
    opts = _opts(CASE=TIMER_FLOW, TRIALS="1")
    whole = harness_sha256(cli="2.1.325", flow="whole")
    good = {"purpose": "evidence", "knowledge": "on", "harness_variant": "default", "flow": "whole",
            "result": {"harness": whole, "cli": "2.1.325"}, "answers": [{"harness": whole}]}
    from nirmaan.evals.records import trial_path

    for n, (trial, ok) in enumerate([(good, True), ({**good, "flow": None}, False),
                                     ({k: v for k, v in good.items() if k != "flow"}, False)]):
        path = trial_path(tmp_path / str(n), TIMER_FLOW, 1)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(trial))
        problem = ci.record_problem(tmp_path / str(n), opts, whole, "2.1.325")
        assert (problem is None) == ok, problem
        assert ok or "flow" in problem


# --- The credential test for seat C (scripts/live_eval_fw_reach.py) --------------------------------------------


def _fw_reach():
    spec = importlib.util.spec_from_file_location("live_eval_fw_reach", REPO / "scripts" / "live_eval_fw_reach.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fw = _fw_reach()
CONFIG = {"canaries": ["0a1b", "2c3d"], "create_in": ["/tmp/a", "/tmp/b c"], "runner_uid": 1001,
          "runner": "runner", "harness_pid": 4242, "secret_file": "/tmp/s/credential", "nonce": "beef",
          "append_to": ["/usr/bin/cc", "/opt/nirmaan-seat/bin/nirmaan-seat-exec"], "seat_gid": 998}


def test_the_probe_names_every_target_and_refuses_a_name_it_cannot_write_as_a_literal():
    text = fw.probe_source(CONFIG)
    assert "__" not in text.split("#include \"nirmaan_hal.h\"", 1)[1].split("#define COUNT", 1)[0]
    for value in ('"0a1b", "2c3d"', '"/tmp/a", "/tmp/b c"', "1001L", "4242L", '"/tmp/s/credential"', '"beef"',
                  '{"/usr/bin/cc", "/opt/nirmaan-seat/bin/nirmaan-seat-exec", NULL}', "SEAT_GID = 998L"):
        assert value in text, value
    bare = fw.probe_source({k: v for k, v in CONFIG.items() if k not in ("append_to", "seat_gid")})
    assert "APPEND_TO[] = {NULL}" in bare and "SEAT_GID = -1L" in bare  # no seat account: groups never read denied
    for name in fw.PROBES:
        assert f'nirmaan_test_result("{name}", ' in text, name
    assert fw.c_string('a"b\\c') == '"a\\"b\\\\c"'
    with pytest.raises(SystemExit):
        fw.c_string("a\nb")


@needs("cc")
def test_the_probe_compiles_as_fw_test_compiles_a_driver_test(tmp_path):
    """Compiled only, never run here: it runs sudo and reads other processes, so it runs in CI's live-eval jobs."""
    from nirmaan.integrations import firmware

    reads = {"read_files": ["/repo/evals/firmware/axi4_lite/held_out_test.c", "/repo/.nirmaan-read-canary-n"],
             "list_dirs": ["/repo", "/home/runner"], "network": [list(n) for n in fw._reach().NETWORK]}
    for n, config in enumerate((CONFIG, {**CONFIG, "append_to": []}, {**CONFIG, **reads})):
        source = tmp_path / f"fw_reach_probe_{n}.c"
        source.write_text(fw.probe_source(config))
        proc = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", f"-I{firmware.HARNESS}",
                               "-c", str(source), "-o", str(tmp_path / f"probe_{n}.o")], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
    text = fw.probe_source({**CONFIG, **reads})  # gate SC6: every read target and every network target is tried
    assert all(f'"{path}", ' in text for path in reads["read_files"] + reads["list_dirs"])
    assert text.count("all &= one_target(") == len(reads["network"]) == 5
    assert 'one_target(1, "2606:4700:4700::1111", 443)' in text and 'one_target(2, "127.0.0.53", 53)' in text
    assert 'one_target(1, "::1", 9)' in text and 'one_target(0, "127.0.0.1", 9)' in text


def _log(denied=(), missing=(), done=True, control="ok"):
    lines = []
    for name in fw.PROBES:
        if name in missing:
            continue
        lines.append(f"FW-REACH {'denied' if name in denied else 'NOT DENIED'}: {name}: what: detail")
    if control:
        lines.append(f"FW-REACH control {control}: fw_reach_own_directory: wrote /tmp/x")
    return "\n".join(["noise", *lines, *(["FW-REACH done"] if done else [])])


def test_a_probe_is_denied_only_when_every_line_of_it_is_and_a_missing_probe_never_is():
    every = fw.parse(_log(denied=fw.PROBES))
    assert every["every_probe_denied"] and not every["missing"] and every["done"]
    assert every["control"] == ["ok: wrote /tmp/x"] and every["control_ok"]
    assert not fw.parse(_log(control="FAILED"))["control_ok"] and not fw.parse(_log(control=None))["control_ok"]
    mixed = fw.parse(_log(denied=fw.PROBES) + "\nFW-REACH NOT DENIED: fw_reach_no_write: /repo: created")
    assert not mixed["every_probe_denied"] and not mixed["probes"]["fw_reach_no_write"]["denied"]
    assert mixed["probes"]["fw_reach_identity"]["denied"]
    gone = fw.parse(_log(denied=fw.PROBES, missing=("fw_reach_no_signal",), done=False))
    assert gone["missing"] == ["fw_reach_no_signal"] and not gone["every_probe_denied"] and not gone["done"]
    assert not gone["probes"]["fw_reach_no_signal"]["denied"]


@pytest.mark.parametrize("found,require,code", [(dict(denied=fw.PROBES), True, 0), (dict(), False, 0),
                                                (dict(), True, 1), (dict(missing=("fw_reach_no_sudo",)), False, 1),
                                                (dict(denied=fw.PROBES, done=False), False, 1),
                                                (dict(denied=fw.PROBES, control="FAILED"), True, 1),
                                                (dict(denied=fw.PROBES, control=None), True, 1),
                                                (dict(control="FAILED"), False, 1),
                                                (dict(denied=fw.PROBES, seat_exec=None), True, 1),
                                                (dict(denied=fw.PROBES, seat_exec=None), False, 0)])
def test_the_record_mode_records_and_the_gate_mode_needs_every_probe_denied(tmp_path, monkeypatch, capsys, found,
                                                                          require, code):
    out = tmp_path / "fw-reach.json"
    found = dict(found)
    wrapper = found.pop("seat_exec", "/opt/nirmaan-seat/bin/nirmaan-seat-exec")

    def fake(argv, env):
        assert env[fw.CANARY_SECRET] and env[fw.CANARY_PLAIN] and env[fw.INNER] == "1"  # in the harness's real env
        out.write_text(json.dumps({"format": fw.FORMAT, "account": {"user": "runner", "uid": 1001},
                                   "seat_exec": wrapper, "summary": "s", **fw.parse(_log(**found))}))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(fw.subprocess, "run", fake)
    monkeypatch.setattr(fw, "git_head", lambda: "abc")
    assert fw.run(tmp_path, out, require, {"GITHUB_RUN_ID": "7", "GITHUB_JOB": "replay"}) == code
    record = json.loads(out.read_text())
    assert record["head"] == "abc" and record["run"]["id"] == "7" and record["run"]["job"] == "replay"
    assert record["require_denied"] is require  # what live_eval_ci.py's lift reads
    printed = capsys.readouterr().out
    control_ok = found.get("control", "ok") == "ok"
    assert ("NOT confined" in printed) == (not found.get("denied") and not found.get("missing") and control_ok)
    assert ("found no nirmaan-seat wrapper" in printed) == (require and wrapper is None)
    assert CONFIG["canaries"][0] not in printed


def test_a_target_it_cannot_name_or_find_fails_the_test_and_a_crash_never_reads_as_denied(tmp_path, monkeypatch,
                                                                                        capsys):
    create, append = fw.targets(tmp_path)
    assert str(tmp_path) in create and append == []
    for over in ({"package_file": ""}, {"purelib": ""}):
        with pytest.raises(fw.Unresolved):
            fw.targets(tmp_path, **over)
    with pytest.raises(SystemExit, match="do not exist"):
        fw.targets(tmp_path / "missing")
    # The probe process crashed (or never wrote): exit 1, whatever an older file said.
    out = tmp_path / "fw-reach.json"
    out.write_text(json.dumps({"every_probe_denied": True}))
    monkeypatch.setattr(fw.subprocess, "run", lambda argv, env: subprocess.CompletedProcess(argv, 1))
    for require in (False, True):
        assert fw.run(tmp_path, out, require, {}) == 1
        assert not out.exists() and "nothing is recorded as denied" in capsys.readouterr().out


def test_in_actions_the_credential_test_tries_every_target_of_the_reach_test(tmp_path, monkeypatch):
    """M90: seat C is tried against the same folders and files as cocotb's seat code, and the same failures stop it."""
    assert callable(fw._reach().targets)  # the real reach test's list
    seen = []

    class Reach:
        @staticmethod
        def targets(records, env):
            seen.append((records, env["GITHUB_ACTIONS"]))
            return [str(tmp_path), "/usr/local/bin"], ["/usr/bin/cc", "/opt/nirmaan-seat/bin/nirmaan-seat-exec"]

    monkeypatch.setattr(fw, "_reach", lambda: Reach)
    create, append = fw.targets(tmp_path, env={"GITHUB_ACTIONS": "true"})
    assert seen == [(tmp_path, "true")] and create.count(str(tmp_path)) == 1 and "/usr/local/bin" in create
    assert append == ["/usr/bin/cc", "/opt/nirmaan-seat/bin/nirmaan-seat-exec"]
    assert fw.targets(tmp_path, env={})[1] == [] and len(seen) == 1

    class Fails:
        @staticmethod
        def targets(records, env):
            raise SystemExit("reach test: cannot determine vvp on PATH")

    monkeypatch.setattr(fw, "_reach", lambda: Fails)
    with pytest.raises(SystemExit, match="cannot determine"):
        fw.targets(tmp_path, env={"GITHUB_ACTIONS": "true"})


CREDENTIAL_RECORD = REPO / "evals" / "flow" / "credential_test_record.json"


def test_the_recorded_credential_test_is_whole_and_the_register_block_flow_waits_while_it_shows_reach():
    """Decision 4: the credential test's result is recorded before the first register block trial. While the record
    shows any probe not denied, a live trial of the register block flow is refused (exit 6)."""
    record = json.loads(CREDENTIAL_RECORD.read_text())
    assert record["format"] == fw.FORMAT and record["tool"] == "fw.test" and record["done"] and record["control_ok"]
    assert not record["missing"] and set(record["probes"]) == set(fw.PROBES)
    assert record["run"]["id"] and record["run"]["job_id"] and record["head"]
    assert record["every_probe_denied"] == all(p["denied"] for p in record["probes"].values())
    if not record["every_probe_denied"]:
        assert ci.seat_c_problem(REGS_FLOW)
    else:  # M90: denied because fw.test ran the program as the seat account, through its wrapper, in a gate run
        assert record["seat_exec"] == "/opt/nirmaan-seat/bin/nirmaan-seat-exec" and record["seat_account"]["uid"] != \
            record["account"]["uid"]
        assert record["run_step"][0][0] == record["seat_exec"] and record["append_targets"]
        assert ci.seat_c_problem(REGS_FLOW)  # still refused live: lifting that is a change of its own


def test_the_committed_credential_record_is_from_main_in_gate_mode_for_the_replay_and_the_rejudge_job(tmp_path):
    """Gate SC3 (council record 2026-11-19, seat C and the live refusal, decision 1, item 3): the committed record is
    from a replay dispatched on main, holds the replay job's and the rejudge job's results, each in gate mode with every
    probe denied, through the seat wrapper, of one run and one commit."""
    record = json.loads(CREDENTIAL_RECORD.read_text())
    jobs = {"replay": record, "rejudge": record["rejudge"]}
    for job, part in jobs.items():
        assert part["format"] == fw.FORMAT and part["tool"] == "fw.test", job
        assert part["run"]["job"] == job and part["run"]["ref"] == "refs/heads/main" and part["run"]["job_id"], job
        assert part["require_denied"] is True and part["every_probe_denied"] is True and part["done"] is True, job
        assert part["control_ok"] is True and part["missing"] == [] and set(part["probes"]) == set(fw.PROBES), job
        assert all(p["denied"] and p["lines"] for p in part["probes"].values()), job
        assert part["seat_exec"] == "/opt/nirmaan-seat/bin/nirmaan-seat-exec" and part["run_step"][0][0] == \
            part["seat_exec"], job
        assert part["seat_account"]["uid"] != part["account"]["uid"], job
        own = tmp_path / f"{job}.json"  # each part passes the check its own job ran before running seat C
        own.write_text(json.dumps(part))
        env = {"GITHUB_RUN_ID": part["run"]["id"], "GITHUB_RUN_ATTEMPT": part["run"]["attempt"], "GITHUB_JOB": job,
               ci.FW_REACH_ENV: str(own)}
        assert ci.fw_reach_problem(env, part["head"]) is None, job
    assert record["run"]["id"] == record["rejudge"]["run"]["id"] and record["head"] == record["rejudge"]["head"]
    # At or after ip#371's merge: the program ran through the wrapper ip#371 added (checked above), on main; CI's
    # shallow checkout has no history to walk, so the commit itself is named in the record's ``about``.
    assert record["head"] in record["about"] or record["head"][:7] in record["about"]
    assert ci.seat_c_problem(REGS_FLOW)  # a record that counts lifts nothing for the flow case
    assert ci.seat_c_problem("firmware/axi4-lite-driver") is None  # gate SC7, on this job's own record only


# --- G3 third addendum (2026-11-19), gate WF21: no attempts option, and no whole-flow dispatch without its fingerprint

def test_the_whole_flow_ci_command_carries_no_attempts_option(tmp_path):
    for env in ({}, {"ATTEMPTS": "1"}, {"ATTEMPTS": "3"}):
        opts = _opts(CASE=TIMER_FLOW, TRIALS="1", **env)
        assert "attempts" not in opts
        argv = ci.command(opts, tmp_path)
        assert not any("attempt" in part for part in argv) and "--harness" not in argv
    with pytest.raises(SystemExit):  # the script's own command line takes none either
        ci.main(["check", "--attempts", "1"])
    root = Path(ci.__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    assert "attempts:" not in workflow and "ATTEMPTS" not in workflow and "--attempts" not in workflow


def test_a_whole_flow_dispatch_with_no_expected_fingerprint_is_refused_before_any_trial(monkeypatch, tmp_path,
                                                                                         capsys):
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: pytest.fail("a trial started"))
    monkeypatch.setattr(ci, "stream", lambda *a, **k: pytest.fail("a trial started"))
    for key, value in {"CASE": TIMER_FLOW, "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                       "HARNESS": "default"}.items():
        monkeypatch.setenv(key, value)
    for expected in (None, "", "  "):
        if expected is None:
            monkeypatch.delenv("EXPECTED", raising=False)
        else:
            monkeypatch.setenv("EXPECTED", expected)
        for argv in (["check", "--require-expected"], ["trials", "--out", str(tmp_path / "out")]):
            assert ci.main(argv) == ci.BAD_INPUT, argv
        assert "name the expected harness fingerprint" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    # With the whole-flow fingerprint named, the same check passes; the single-seat one is not accepted for it.
    whole = harness_sha256(cli="2.1.325", flow="whole")
    monkeypatch.setenv("EXPECTED", whole)
    assert ci.main(["check", "--require-expected"]) == 0
    monkeypatch.setenv("EXPECTED", harness_sha256(cli="2.1.325"))
    assert ci.main(["check", "--require-expected"]) == ci.MISMATCH


def test_every_case_that_runs_seat_c_gets_the_credential_test_in_every_job():
    """The workflow runs the credential test for flow/ and firmware/ cases; a case that runs seat C under
    any other name would be stopped by ``confined`` in every job (fail closed), so none may exist."""
    workflow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    condition = "if: startsWith(inputs.case, 'flow/') || startsWith(inputs.case, 'firmware/')"
    runs = condition + "\n        run: python scripts/live_eval_fw_reach.py"
    assert workflow.count(runs) == 3  # replay, trials, rejudge
    seat_c = [c.id for c in ci._cases() if ci.seat_c_use(c.id)]
    assert seat_c and all(case.startswith(("flow/", "firmware/")) for case in seat_c), seat_c


# --- Gates SC2 and SC4 (council record 2026-11-19, seat C and the live refusal, decision 1) ------------------------


def test_the_trials_step_refuses_on_a_missing_foreign_non_gate_or_not_denied_record(tmp_path, monkeypatch, capsys):
    """SC4: exit 6 from the trials step, with the record's own reason, for each record that does not count. SC7: with
    a record that counts, the trials of firmware/axi4-lite-driver start, and only then."""
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    monkeypatch.setattr(ci, "_head", lambda: "c0ffee")
    ran = []
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: ran.append(a) or 0)
    digest = harness_sha256(cli="2.1.325")
    base = {"CASE": "firmware/axi4-lite-driver", "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
            "HARNESS": "default", "EXPECTED": digest}
    cases = {"missing": {k: v for k, v in _fw_record(tmp_path).items() if k != ci.FW_REACH_ENV},
             "foreign run": _fw_record(tmp_path, run={"id": "76", "attempt": "1", "job": "live-eval"}),
             "foreign job": {**_fw_record(tmp_path), "GITHUB_JOB": "replay"},
             "not gate": _fw_record(tmp_path, require_denied=False),
             "not denied": _fw_record(tmp_path, every_probe_denied=False)}
    reasons = {"missing": "not set", "foreign run": "not this job's", "foreign job": "not this job's",
               "not gate": "without --require-denied", "not denied": "every probe denied"}
    for name, env in cases.items():
        for key in [*JOB_ENV, ci.FW_REACH_ENV]:
            monkeypatch.delenv(key, raising=False)
        for key, value in {**base, **env}.items():
            monkeypatch.setenv(key, value)
        assert ci.main(["trials", "--out", str(tmp_path / "out")]) == ci.UNCONFINED, name
        err = capsys.readouterr().err
        assert reasons[name] in err and "Nothing ran" in err, (name, err)
        assert not ran, name
    for key, value in {**base, **_fw_record(tmp_path)}.items():
        monkeypatch.setenv(key, value)
    assert ci.main(["trials", "--out", str(tmp_path / "out")]) == 0 and len(ran) == 1  # gate SC7: this case only


def test_every_other_case_that_runs_seat_c_still_exits_6_with_a_record_that_counts(tmp_path, monkeypatch, capsys):
    """Gate SC7 lifts firmware/axi4-lite-driver only: with this job's record showing every probe denied, a live trial
    of every other case that runs seat C (the register block flow today) still exits 6 from check and trials."""
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    monkeypatch.setattr(ci, "_head", lambda: "c0ffee")
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: pytest.fail("a trial started"))
    others = [c for c in ci._cases() if ci.seat_c_use(c.id) and c.id not in ci.SEAT_C_LIVE]
    assert REGS_FLOW in [c.id for c in others]
    for case in others:
        for key, value in {"CASE": case.id, "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                           "HARNESS": "default", "EXPECTED": harness_sha256(cli="2.1.325", flow=case.flow),
                           **_fw_record(tmp_path)}.items():
            monkeypatch.setenv(key, value)
        for argv in (["check", "--require-expected"], ["trials", "--out", str(tmp_path / "out")]):
            assert ci.main(argv) == ci.UNCONFINED, (case.id, argv)
            assert "live trials of it stay refused" in capsys.readouterr().err, (case.id, argv)


def test_every_job_names_the_seat_wrapper_and_the_trials_step_its_record():
    """SC2: each job that can run seat C sets NIRMAAN_SEAT_EXEC to the installed wrapper, so fw.test refuses rather
    than run as the runner; the trials step gets the job's credential test record (SC4)."""
    from nirmaan.integrations import firmware

    spec = importlib.util.spec_from_file_location("live_eval_seat", REPO / "scripts" / "live_eval_seat.py")
    seat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seat)
    workflow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    assert workflow.count(f"      {firmware.SEAT_EXEC_ENV}: {seat.EXEC}\n") == 3  # replay, live-eval, rejudge
    trials = workflow.split("- name: Run the trials one at a time")[1].split("- name:")[0]
    assert "FW_REACH: ${{ runner.temp }}/fw-reach/fw-reach.json" in trials


def test_the_broken_driver_control_needs_the_reference_to_pass_each_fixture_to_fail_and_the_wrapper():
    """Gate SC5: the record proves something only when the reference passes every check, each broken fixture is
    failed by a run that ran, and (in the replay job) every fw.test run went through the seat account's wrapper."""
    spec = importlib.util.spec_from_file_location("live_eval_fw_broken", REPO / "scripts" / "live_eval_fw_broken.py")
    broken = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(broken)

    def run(tool="fw.test", ran=True, ok=False, wrapped=True):
        return {"check": "c", "tool": tool, "ran": ran, "succeeded": ok, "summary": "", "through_wrapper": wrapped}

    good = {"reference": [run("fw.build", ok=True), run(ok=True)],
            **{n: [run("fw.build", ok=True), run()] for n in broken.BROKEN}}
    assert broken.problems(good, require_seat=True) == []
    assert set(broken.BROKEN) == {"wrong-map", "swallowed-error", "all-strobes", "sticky-response"}
    assert all((broken.FW / f).is_file() for swap in broken.BROKEN.values() for f in swap.values())
    bad = {**good, "reference": [run(ok=False)]}
    assert "reference driver does not pass" in broken.problems(bad, require_seat=False)[0]
    bad = {**good, "all-strobes": [run(ran=False)]}  # a refusal is not a failure of the judge
    assert broken.problems(bad, require_seat=False) == ["all-strobes: no held-out check failed it by a run that ran"]
    bad = {**good, "wrong-map": [run(wrapped=False)]}
    assert broken.problems(bad, require_seat=True) == ["an fw.test run did not go through the seat account's wrapper"]
    assert broken.problems(bad, require_seat=False) == []
    workflow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    assert "python scripts/live_eval_fw_broken.py --out \"$RUNNER_TEMP/fw-reach/fw-broken.json\" --require-seat" in workflow
