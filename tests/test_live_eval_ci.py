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


def test_a_live_trial_of_a_case_that_runs_seat_c_is_refused():
    assert ci.seat_c_problem("dv/cocotb-crc") is None and ci.seat_c_problem(SPEC_CASE) is None
    problem = ci.seat_c_problem("firmware/axi4-lite-driver")
    assert problem and "fw.test" in problem and "WF17" in problem


def test_main_refuses_seat_c_before_any_trial_but_a_replay_check_does_not(monkeypatch, capsys):
    monkeypatch.setattr(ci, "installed_cli", lambda: "2.1.325")
    digest = harness_sha256(cli="2.1.325")
    for key, value in {"CASE": "firmware/axi4-lite-driver", "TRIALS": "1", "KNOWLEDGE": "on", "PURPOSE": "evidence",
                       "HARNESS": "default", "EXPECTED": digest}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(ci, "run_trials", lambda *a, **k: pytest.fail("a trial started"))
    assert ci.main(["check", "--require-expected"]) == ci.UNCONFINED
    assert ci.main(["trials", "--out", "/nonexistent"]) == ci.UNCONFINED
    assert "gate WF17" in capsys.readouterr().err
    assert ci.main(["check"]) == 0
