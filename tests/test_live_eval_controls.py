"""Gate ET5 as the seat account (scripts/live_eval_controls.py): what it runs and refuses, how a sweep row compares.

The runs themselves need the seat account, which only the live evaluation's `replay` job has; these tests check the
parts that need no account: the selection of the timer's controls, the fixture tests it names, the refusals before
anything runs, the comparison of a sweep row with the record, and that each sweep run is started in a run directory
of its own under ``/tmp/nirmaan-*`` with the step's environment naming it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("live_eval_controls", REPO / "scripts" / "live_eval_controls.py")
controls = importlib.util.module_from_spec(spec)
sys.modules["live_eval_controls"] = controls
spec.loader.exec_module(controls)

from nirmaan.integrations import eda  # noqa: E402


def test_the_selection_is_exactly_the_timer_controls():
    """Every control of flow/axil-timer, and nothing else, has a parameter id the selection names."""
    data = json.loads((REPO / "evals" / "flow" / "controls.json").read_text(encoding="utf-8"))
    word = controls.CONTROLS_SELECT.rsplit(" and ", 1)[1]
    timer = {c["id"] for c in data["controls"] if c["case"] == controls.CASE}
    assert len(timer) == 7 and {c["id"] for c in data["controls"] if word in c["id"]} == timer
    assert controls.CONTROLS_SELECT.startswith("test_the_control_gets_the_verdict_it_expects and ")
    assert "def test_the_control_gets_the_verdict_it_expects(" in (REPO / controls.CONTROLS_TEST).read_text()


def test_every_fixture_test_exists_and_every_failing_testbench_is_run():
    """Each named file and test exists, and every committed ``*_fail.v`` testbench is named by one of them."""
    texts = []
    for test in controls.FIXTURE_TESTS:
        path, _, name = test.partition("::")
        text = (REPO / path).read_text(encoding="utf-8")
        assert not name or re.search(rf"^def {name}\(", text, re.MULTILINE), test
        texts.append(text if not name else text.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0])
    failing = sorted(p.name for p in (REPO / "tests" / "fixtures").rglob("*_fail.v"))
    assert len(failing) == 6
    for name in failing:
        assert any(name in text for text in texts), name
    assert {"tests/test_gate_inputs.py", "tests/test_gate_reads.py"} <= set(controls.FIXTURE_TESTS)  # gate ET1


def test_another_case_is_refused_before_anything_runs(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CASE", "flow/axi4-lite-regs-driver")
    monkeypatch.setattr(controls, "pytest_part", lambda *a: pytest.fail("ran"))
    assert controls.main(["--out", str(tmp_path / "out")]) == 2
    assert "nothing ran" in capsys.readouterr().out and not (tmp_path / "out").exists()


def test_a_job_without_the_seat_accounts_wrappers_is_refused(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CASE", controls.CASE)
    monkeypatch.delenv(eda.SEAT_TOOLS_ENV, raising=False)
    monkeypatch.setattr(controls, "pytest_part", lambda *a: pytest.fail("ran"))
    assert controls.main(["--out", str(tmp_path / "out")]) == 2
    assert f"{eda.SEAT_TOOLS_ENV} is not set" in capsys.readouterr().out


def test_wrappers_not_roots_or_not_first_on_path_are_refused(monkeypatch, tmp_path):
    folder = tmp_path / "bin"
    folder.mkdir()
    for name in ("iverilog", "vvp", "yosys", "sby", "eqy", "verilator"):
        (folder / name).write_text("#!/bin/sh\n")
        (folder / name).chmod(0o755)
    monkeypatch.setenv(eda.SEAT_TOOLS_ENV, str(folder))
    assert "not a regular file only root may write" in controls.wrappers_problem(dict(os.environ))
    # Wrappers that pass, but another iverilog first on PATH: the sweep starts it by name, so it is refused.
    monkeypatch.setattr(eda, "seat_tools_problem", lambda steps: None)
    other = tmp_path / "other"
    other.mkdir()
    (other / "iverilog").write_text("#!/bin/sh\n")
    (other / "iverilog").chmod(0o755)
    env = {**os.environ, "PATH": f"{other}:{folder}"}
    assert "not the seat account's wrapper" in controls.wrappers_problem(env)
    assert controls.wrappers_problem({**os.environ, "PATH": str(folder)}) is None


def test_flow_control_lines_are_read_from_the_output():
    out = 'x\nFLOW-CONTROL {"id": "timer-tb-weak", "verdicts": ["failed"]}\n.\nFLOW-CONTROL {"id": "a"}\n'
    assert controls.flow_controls(out) == [{"id": "timer-tb-weak", "verdicts": ["failed"]}, {"id": "a"}]


def test_a_sweep_row_compares_result_count_and_first_failure():
    mutant = {"result": "fails", "errors": 6, "first_failure": "COUNT after a stop"}
    assert controls.compare_row(mutant, (44953, 6, "COUNT after a stop")) == {
        "result": "fails", "checks_passed": 44953, "errors": 6, "first_failure": "COUNT after a stop",
        "expected_result": "fails", "same_result": True, "same_errors": True, "same_first_failure": True}
    row = controls.compare_row(mutant, (44957, 2, "another check"))
    assert row["same_result"] and not row["same_errors"] and not row["same_first_failure"]
    row = controls.compare_row(mutant, (44959, 0, ""))  # a mutant that survives differs in its result
    assert row["result"] == "passes" and not row["same_result"]
    assert not controls.compare_row(mutant, (None, None, "syntax error"))["same_errors"]  # did not build: fails
    assert controls.compare_row(mutant, (None, None, "syntax error"))["same_result"]
    reference = {"result": "passes", "checks": 44959}
    assert controls.compare_row(reference, (44959, 0, ""))["same_errors"] is True
    assert controls.compare_row(reference, (44958, 0, ""))["same_errors"] is False
    assert controls.compare_row(reference, (44958, 1, "x"))["same_result"] is False


def test_each_sweep_run_is_in_a_run_directory_of_its_own_named_to_the_wrappers(monkeypatch, tmp_path):
    """The whole record, every row rebuilt and run in a fresh ``/tmp/nirmaan-sweep-*`` folder that is the current
    directory and ``eda.SEAT_RUN_DIR_ENV``, with no inputs outside it; the rows are compared and the folders removed."""
    sys.path.insert(0, str(REPO / "tests"))
    import flow_mutants

    record = json.loads(controls.SWEEP.read_text(encoding="utf-8"))
    seen = []

    def simulate(tb, top, source, workdir):
        here = Path(os.getcwd())
        assert here == workdir == tb.parent == source.parent
        assert here.parent == Path("/tmp").resolve() and here.name.startswith("nirmaan-sweep-")
        assert os.environ[eda.SEAT_RUN_DIR_ENV] == str(here) and os.environ[eda.SEAT_INPUTS_ENV] == "[]"
        assert tb.read_text(encoding="utf-8") == (REPO / record["testbench"]["path"]).read_text(encoding="utf-8")
        assert top == record["testbench"]["top"]
        seen.append(here)
        if source.name == Path(record["reference"]["path"]).name:
            return record["reference"]["checks"], 0, ""
        row = next(r for r in record["mutants"] if f"{r['mutant']}.v" == source.name)
        return 1, row["errors"], row["first_failure"]

    monkeypatch.setattr(flow_mutants, "simulate", simulate)
    monkeypatch.setattr(controls, "simulator_version", lambda: "Icarus Verilog version 12.0 (stable)")
    monkeypatch.delenv(eda.SEAT_RUN_DIR_ENV, raising=False)
    assert controls.sweep(tmp_path) is True
    out = json.loads((tmp_path / "sweep.json").read_text(encoding="utf-8"))
    assert out["ok"] and len(out["rows"]) == len(record["mutants"]) + 1 == len(seen) == len(set(seen))
    assert all(r["same_result"] and r["same_errors"] and r["same_first_failure"] and r["same_sha256"]
               for r in out["rows"])
    assert out["rows"][0]["mutant"] == "reference" and out["simulator"].startswith("Icarus Verilog")
    assert not any(p.exists() for p in seen) and eda.SEAT_RUN_DIR_ENV not in os.environ


def test_each_bypass_control_records_what_its_tool_gave_and_changes_nothing(monkeypatch, tmp_path):
    """For security to state why a bypass control differs as the seat account (ET5 replay run 45119522138): each tool
    run of a bypass control is written with its command, exit status, the line naming what it could not open, its last
    lines and the run's summary; the run's arguments and outcome pass through unchanged, and other tests are not
    recorded."""
    from types import SimpleNamespace

    from nirmaan.runtime.tools import ToolOutcome

    printed = "Reading m.v\nERROR: Can't open include file `/tmp/nirmaan-x/CANARY_ET1.vh'!\nEnd of script.\n"
    outcome = ToolOutcome(False, "yosys: synthesis failed: 1 error", metrics={"exit_status": 1})
    calls = []

    def run_step(argv, *rest):
        calls.append(("step", argv, rest))
        return eda._Step(printed, 1, None, len(printed))

    def execute(backend, params, sources, workdir):
        calls.append(("run", backend, params, sources, workdir))
        eda._run_step(["/opt/nirmaan-seat/bin/yosys", "-s", "synth.ys"], "cwd", {}, 0.0, 10, workdir)
        return outcome

    monkeypatch.setattr(eda, "_run_step", run_step)
    monkeypatch.setattr(eda, "_execute", execute)
    path = tmp_path / "bypass.jsonl"
    plugin = controls.BypassOutcomes(path)
    plugin.pytest_configure(None)
    gate = SimpleNamespace(name="yosys", tool="synth.run")
    for nodeid, result in (("tests/test_gate_inputs.py::test_control_without_the_check_a_tool_acts_on_the_form[x]",
                            "failed"), ("tests/test_gate_inputs.py::test_a_plain_top_still_synthesizes", "passed")):
        plugin.pytest_runtest_logstart(nodeid, None)
        assert eda._execute(gate, {"top": "m"}, ("m.v",), tmp_path) is outcome  # passed through unchanged
        plugin.pytest_runtest_logreport(SimpleNamespace(when="call", outcome=result))
        plugin.pytest_runtest_logfinish(nodeid, None)
    assert [c[0] for c in calls] == ["run", "step"] * 2 and calls[0][2:] == ({"top": "m"}, ("m.v",), tmp_path)
    [line] = controls.bypass_lines(path)  # the other test is not recorded
    assert line["test"].endswith("test_control_without_the_check_a_tool_acts_on_the_form[x]")
    assert line["result"] == "failed"
    [run] = line["runs"]
    assert run["backend"] == "yosys" and run["succeeded"] is False and run["summary"] == outcome.summary
    assert run["metrics"] == {"exit_status": 1}
    [step] = run["steps"]
    assert step["command"] == ["/opt/nirmaan-seat/bin/yosys", "-s", "synth.ys"] and step["exit"] == 1
    assert step["error_lines"] == ["ERROR: Can't open include file `/tmp/nirmaan-x/CANARY_ET1.vh'!"]
    assert step["last_lines"][-1] == "End of script."


def test_the_fixtures_run_loads_the_recorder_and_writes_a_bypass_controls_runs(tmp_path):
    """End to end, with no tool: ``pytest_part`` starts pytest with the recorder, and a bypass control's run that is
    refused before any step is written with its summary and no step."""
    tests = tmp_path / "suite"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "from nirmaan.integrations.eda import backends_for, execute\n\n\n"
        "def test_control_without_the_check_probe(tmp_path):\n"
        "    gate = next(b for b in backends_for('synth.run') if b.name == 'yosys')\n"
        "    (tmp_path / 'm.v').write_text('module m; endmodule\\n')\n"
        "    assert not execute(gate, {'sources': str(tmp_path / 'm.v'), 'top': 'm;x'}).succeeded\n\n\n"
        "def test_another():\n"
        "    pass\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    part = controls.pytest_part("probe", ["test_probe.py"], tests, out, env, bypass=out / "bypass.jsonl")
    assert part["exit"] == 0, part["output"]
    [line] = controls.bypass_lines(out / "bypass.jsonl")
    assert line["test"] == "test_probe.py::test_control_without_the_check_probe" and line["result"] == "passed"
    [run] = line["runs"]
    assert run["backend"] == "yosys" and run["succeeded"] is False and run["steps"] == []
    assert "top must be a plain module name" in run["summary"]


# --- The committed record of the dispatched run (gate ET5) --------------------------------------------------------

RECORD = REPO / "evals" / "flow" / "et5_controls_record.json"
LINKED = "test_a_setup_over_an_approved_file_linked_beside_it_still_proves"


def test_the_committed_et5_controls_record_is_from_main_and_shows_each_part_against_its_expectation():
    """Replay run 45119522138 of flow/axil-timer on main at c0ba283c (the merge of ip#464), with controls set: the seven
    timer controls gave the verdicts of controls_record.json, all 100 sweep rows gave the record's result, error count
    and first failure, and of the 402 fixture tests 390 passed and 12 failed (11 bypass controls and the linked setup),
    none skipped; every must-refuse fixture passed. The record says what each difference is and claims no verdict."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["format"] == "nirmaan.et5-seat-controls-record/1"
    run = record["run"]
    assert run["id"] == "45119522138" and run["commit"].startswith("c0ba283c") and re.fullmatch(r"[0-9a-f]{40}",
                                                                                                run["commit"])
    assert (run["branch"], run["event"]) == ("main", "workflow_dispatch")
    assert run["inputs"] == {"case": controls.CASE, "replay": True, "controls": True}
    assert run["artifact"] == f"live-eval-controls-{run['id']}" and run["url"].endswith(f"/actions/runs/{run['id']}")
    assert set(run["jobs"]) == {"replay", "rejudge"}
    assert all(run["id"] in j["url"] and j["url"].endswith(f"/job/{j['id']}") for j in run["jobs"].values())
    assert (run["jobs"]["replay"]["conclusion"], run["jobs"]["rejudge"]["conclusion"]) == ("failure", "success")
    assert record["summary"]["commit"] == run["commit"] and record["summary"]["seat_tools"] == "/opt/nirmaan-seat/bin"
    assert record["summary"]["required"] == controls.REQUIRED.split() and record["summary"]["ok"] is False
    assert run["id"] in record["about"] and run["commit"][:8] in record["about"]
    assert "Whether ET5 is met is verification-lead's statement, not this record's." in record["about"]

    # The reference answer's replay, its re-judge and the reach test, in the same run.
    replay = record["replay"]
    assert (replay["passed"], replay["n"]) == (1, 1)
    assert replay["rejudge"] == [{"case": controls.CASE, "trial": 1, "same": True, "differences": []}]
    assert replay["tool_reach_every_denied"] == {"replay": True, "rejudge": True}
    assert set(replay["tool_reach_commit"].values()) == {run["commit"]}

    # Controls: each timer control, in the manifest's order, as the manifest expects and as the CI run recorded.
    manifest = [c for c in json.loads((REPO / "evals" / "flow" / "controls.json").read_text())["controls"]
                if c["case"] == controls.CASE]
    recorded = {c["id"]: c for c in json.loads((REPO / "evals" / "flow" / "controls_record.json").read_text())[
        "controls"]}
    part = record["controls"]
    assert part["exit"] == 0 and part["junit"] == {"tests": 7, "passed": 7, "failed": 0, "error": 0, "skipped": 0}
    assert [c["id"] for c in part["controls"]] == [c["id"] for c in manifest]
    for got, want in zip(part["controls"], manifest):
        expected = [s["expect"] for s in want["checks"]]
        assert got["expected"] == expected == got["verdicts"] == got["recorded"] == recorded[want["id"]]["verdicts"]
        assert got["submitted"] is want.get("reaches_review", True)

    # Sweep: the reference and every mutant, each as the sweep record has it.
    sweep = json.loads(controls.SWEEP.read_text(encoding="utf-8"))
    rows = record["sweep"]["rows"]
    assert record["sweep"]["ok"] is True and record["sweep"]["record_simulator"] == sweep["simulator"]
    assert [r["mutant"] for r in rows] == ["reference", *(m["mutant"] for m in sweep["mutants"])]
    assert rows[0]["sha256"] == sweep["reference"]["sha256"] and rows[0]["result"] == "passes"
    assert (rows[0]["checks_passed"], rows[0]["errors"]) == (sweep["reference"]["checks"], 0)
    for row, want in zip(rows[1:], sweep["mutants"]):
        assert (row["tag"], row["sha256"], row["result"]) == (want["tag"], want["sha256"], want["result"]), row
        assert (row["errors"], row["first_failure"]) == (want["errors"], want["first_failure"]), row
    assert all(r["same_result"] and r["same_errors"] and r["same_first_failure"] and r["same_sha256"] for r in rows)

    # Fixtures: every test ran, none skipped; the failures are exactly the differences the record names.
    part = record["fixtures"]
    assert part["files"] == list(controls.FIXTURE_TESTS) and part["exit"] == 1
    assert part["junit"] == {"tests": 402, "passed": 390, "failed": 12, "error": 0, "skipped": 0}
    assert len(part["tests"]) == 402 and len({t["test"] for t in part["tests"]}) == 402
    failed = [t["test"] for t in part["tests"] if t["outcome"] != "passed"]
    assert failed == [d["test"] for d in part["differences"]]
    names = [t.split("::")[-1] for t in failed]
    assert [n for n in names if not n.startswith("test_control_without_the_check")] == [LINKED]
    assert sum(n.startswith("test_control_without_the_check") for n in names) == 11
    for diff in part["differences"]:
        assert diff["what"].startswith("must-pass" if diff["test"].endswith(LINKED) else "bypass control"), diff
    refusing = [t for t in part["tests"] if "_refused" in t["test"].split("::")[-1]]
    assert refusing and all(t["outcome"] == "passed" for t in refusing)  # every must-refuse fixture still refused


# --- Uploads committed as uploaded (third addendum to the ET record, decision E4) ---------------------------------

#: Where controls uploads are committed, each run in ``run-<id>/`` with its ``index.json`` and the artifact's files at
#: ``<artifact name>/<file name>``. Not under ``evals/``: ``bypass.json`` and ``controls.json`` are JSON arrays as
#: uploaded, and ``nirmaan.evals.cases.load_cases`` reads every ``*.json`` there that is not a ``format`` object as a
#: case.
EVIDENCE = REPO / "docs" / "evidence" / "et5"
#: Every program a seat-account step starts is a wrapper here (``.github/actions/live-eval-seat``).
WRAPPERS = "/opt/nirmaan-seat/bin/"
#: What gate ET1's targets hold: the canary (``tests/test_gate_inputs.py``) and the host file's marker
#: (``tests/test_gate_reads.py``). Neither may be in a control's record as the account.
TARGET_CONTENT = ("canary_et1_7f3a", "NIRMAAN_MARKER_4b1d")


def committed_files(folder: Path, files: dict) -> None:
    """``folder`` holds exactly ``files`` (each ``name: {sha256, bytes}``, by its path in the folder), besides an
    ``index.json``, each with the sha256 and size named (decision R1, item 3)."""
    found = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != "index.json")
    assert found == sorted(files), found
    for name, want in files.items():
        data = (folder / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (want["sha256"], want["bytes"]), name


def committed_upload(run: str) -> tuple[dict, Path]:
    """A run's committed upload and its ``index.json``, after ``committed_files``."""
    folder = EVIDENCE / f"run-{run}"
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    committed_files(folder, index["files"])
    return index, folder


def junit_outcomes(path: Path) -> dict[str, str]:
    """Each test of a JUnit file, as ``path::name``, with its outcome: passed, failed, error or skipped."""
    import xml.etree.ElementTree as ET

    out = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        name = case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", "")
        kinds = [k for k in ("failure", "error", "skipped") if case.find(k) is not None]
        out[name] = {"failure": "failed", "error": "error", "skipped": "skipped"}[kinds[0]] if kinds else "passed"
    return out


def test_run_45135605510s_controls_upload_is_committed_as_uploaded_and_as_records_only():
    """Decision E4, item 6: the upload the addendum's facts T3 to T7 were read from, as uploaded, cited as what showed
    the finding of decision E3 and never as showing gate ET5 met. It holds what fact T3 says: controls 7, the sweep as
    recorded, 402 fixture tests with 391 passed and 11 failed, none skipped, the linked setup passing, and the 11
    failures the bypass controls of fact T5; and what fact T7 found: the ``[files]`` control passed through the seat
    account's ``sby`` with the host file's marker in its summary."""
    index, folder = committed_upload("45135605510")
    assert index["format"] == "nirmaan.et5-controls-upload-index/1"
    assert index["about"].startswith("Records only.") and "never as showing gate ET5 met" in index["about"]
    run = index["run"]
    assert (run["id"], run["commit"], run["branch"], run["attempt"]) == (
        "45135605510", "a15b8c1dfe531f3634120f40335901c8965d8611", "main", 1)
    assert run["inputs"] == {"case": controls.CASE, "replay": True, "controls": True}
    assert run["artifact"] == "live-eval-controls-45135605510"
    assert {k: v["conclusion"] for k, v in run["jobs"].items()} == {"replay": "failure", "rejudge": "success"}
    upload = folder / run["artifact"]
    assert sorted(p.name for p in upload.iterdir()) == sorted(
        ["bypass.json", "controls.json", "controls.log", "controls.xml", "fixtures.log", "fixtures.xml",
         "summary.json", "sweep.json"])

    summary = json.loads((upload / "summary.json").read_text(encoding="utf-8"))
    assert (summary["format"], summary["case"], summary["commit"]) == (
        "nirmaan.et5-seat-controls", controls.CASE, run["commit"])
    assert (summary["controls"]["exit"], summary["controls"]["count"], summary["sweep"]["ok"]) == (0, 7, True)
    assert (summary["fixtures"]["exit"], summary["ok"]) == (1, False)
    assert json.loads((upload / "sweep.json").read_text(encoding="utf-8"))["ok"] is True

    outcomes = junit_outcomes(upload / "fixtures.xml")
    assert len(outcomes) == 402 and "skipped" not in outcomes.values() and "error" not in outcomes.values()
    failed = sorted(t for t, o in outcomes.items() if o == "failed")
    assert len(failed) == 11 and failed == sorted(summary["bypass"]["failed"])
    assert all(t.split("::")[1].startswith(controls.BYPASS) for t in failed)
    assert outcomes[f"tests/test_gate_reads.py::{LINKED}"] == "passed"

    bypass = {c["test"]: c for c in json.loads((upload / "bypass.json").read_text(encoding="utf-8"))}
    assert len(bypass) == summary["bypass"]["count"] == 48
    finding = bypass["tests/test_gate_reads.py::test_control_without_the_check_the_host_file_reaches_the_summary"
                     "[files-absolute]"]
    assert finding["result"] == "passed"
    [found] = finding["runs"]
    assert [s["command"][0] for s in found["steps"]] == [f"{WRAPPERS}sby"]
    assert "NIRMAAN_MARKER_4b1d" in found["summary"]


# --- Gate ET18: the record gate ET5 is stated on (third addendum to the ET record, decision E4) -------------------

#: Replay run 45159697183 of flow/axil-timer, on main at f8dcc97e (the merge of ip#475), with controls set and no model.
ET18_RUN = "45159697183"
ET18_RECORD = REPO / "evals" / "flow" / f"et5_controls_record_{ET18_RUN}.json"
#: Decision E2, item 1: for each failed bypass control, the program whose own line says it could not open, resolve or
#: write the target, and that line, by the end of the control's name. One cause each; a failed control none of them
#: names, or whose run lacks the line, is a difference (item 2).
CAUSES = (
    ("::test_control_without_the_check_a_top_reaches_the_shell", "yosys",
     r"touch: cannot touch '[^']*/MARKER': Permission denied"),
    ("::test_control_without_the_check_a_setup_reaches_the_shell", "sby",
     r"touch: cannot touch '[^']*/MARKER': Permission denied"),
    ("-yosys]", "yosys", r"ERROR: Can not open file `[^`]*/outside/CANARY_ET1\.hex` for \\\$readmemh"),
    ("-verilator-lint]", "verilator", r"Can't resolve module reference: '[^']*CANARY_ET1\.vh'"),
    ("[glued_macro_call-icarus]", "vvp", r"\$writememh: Unable to open \S*/outside/MARKER for writing"),
    ("[include-glued]", "sby", r"Can't open include file `leak\.vh'"),
    ("[files-absolute]", "sby",
     r"(?:FileNotFoundError|PermissionError): \[Errno \d+\] [^:]*: '[^']*/host/leak\.vh'"),
)


def cause_of(test: str) -> tuple[str, re.Pattern]:
    [(program, line)] = [(p, l) for end, p, l in CAUSES if test.endswith(end)]
    return program, re.compile(line)


def test_the_et18_record_is_from_main_and_reads_every_bypass_control_by_decision_e2():
    """Gate ET18 (decision E4, item 3): replay run 45159697183 on main at f8dcc97e, which holds gate ET17 (the merge of ip#475), with
    its controls upload and both jobs' tool reach records committed as uploaded. Controls 7 of 7 and the sweep 100 of
    100 against the committed files; every fixture test ran, none skipped; the linked setup's test and every
    must-refuse fixture passed; every probe denied in both jobs on the run's commit; the failed tests are exactly the
    bypass controls the record names, and each gives the reading of decision E2, item 1: for every tool run, the seat
    account's wrapper as the command and the tool's own line naming the target it could not open, resolve or write,
    with none of a target's content in its record. The controls whose tool runs as the caller (decision 6) are listed
    and claimed for nothing."""
    record = json.loads(ET18_RECORD.read_text(encoding="utf-8"))
    assert record["format"] == "nirmaan.et5-seat-controls-record/2"
    run = record["run"]
    assert (run["id"], run["branch"], run["event"]) == (ET18_RUN, "main", "workflow_dispatch")
    assert run["commit"].startswith("f8dcc97e") and re.fullmatch(r"[0-9a-f]{40}", run["commit"])
    assert run["inputs"] == {"case": controls.CASE, "replay": True, "controls": True}
    assert {k: v["conclusion"] for k, v in run["jobs"].items()} == {"replay": "failure", "rejudge": "success", "live-eval": "skipped"}
    assert all(run["id"] in j["url"] and j["url"].endswith(f"/job/{j['id']}") for j in run["jobs"].values())
    # The rejudge job alone was run again (attempt 2) after attempt 1's stopped in its tool install; the replay job
    # ran once. Each job's own steps, as GitHub reported them.
    assert {k: v["attempt"] for k, v in run["jobs"].items()} == {"replay": 1, "rejudge": 2, "live-eval": 1}
    assert run["steps"]["replay"]["Replay the reference answer"] == "success"
    assert run["steps"]["rejudge"]["Re-judge the records"] == "success"
    assert {s: c for job in run["steps"].values() for s, c in job.items() if c != "success"} == {
        "Run the controls, the mutant sweep and the gate fixtures as the seat account": "failure"}
    assert "Whether ET5 is met is verification-lead's statement, not this record's." in record["about"]
    folder = REPO / record["folder"]
    assert folder == EVIDENCE / f"run-{ET18_RUN}"
    committed_files(folder, record["files"])
    upload = folder / f"live-eval-controls-{ET18_RUN}"

    # The run's own summary, on the same commit, and the reach test in both jobs.
    summary = json.loads((upload / "summary.json").read_text(encoding="utf-8"))
    assert (summary["format"], summary["case"], summary["commit"]) == (
        "nirmaan.et5-seat-controls", controls.CASE, run["commit"])
    assert summary["seat_tools"] == WRAPPERS.rstrip("/") and summary["required"] == controls.REQUIRED.split()
    for job in ("replay", "rejudge"):
        reach = json.loads((folder / f"live-eval-tool-reach-{job}-{ET18_RUN}" / "tool-reach.json").read_text(
            encoding="utf-8"))
        assert (reach["format"], reach["commit"], reach["run_id"], reach["job"]) == (
            "nirmaan.tool-reach", run["commit"], ET18_RUN, job)
        assert reach["every_denied"] is True and reach["probes"] and all(p["denied"] for p in reach["probes"])

    # Controls: each timer control, in the manifest's order, as the manifest expects and as the CI run recorded.
    manifest = [c for c in json.loads((REPO / "evals" / "flow" / "controls.json").read_text())["controls"]
                if c["case"] == controls.CASE]
    recorded = {c["id"]: c for c in json.loads((REPO / "evals" / "flow" / "controls_record.json").read_text())[
        "controls"]}
    assert (summary["controls"]["exit"], summary["controls"]["count"]) == (0, 7)
    assert junit_outcomes(upload / "controls.xml") and set(junit_outcomes(upload / "controls.xml").values()) == {
        "passed"}
    lines = json.loads((upload / "controls.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in lines] == [c["id"] for c in manifest]
    for got, want in zip(lines, manifest):
        assert got["verdicts"] == [s["expect"] for s in want["checks"]] == recorded[want["id"]]["verdicts"], got["id"]

    # Sweep: the reference and every mutant, each as the sweep record has it.
    sweep_record = json.loads(controls.SWEEP.read_text(encoding="utf-8"))
    sweep = json.loads((upload / "sweep.json").read_text(encoding="utf-8"))
    rows = sweep["rows"]
    assert sweep["ok"] is True and summary["sweep"]["ok"] is True
    assert [r["mutant"] for r in rows] == ["reference", *(m["mutant"] for m in sweep_record["mutants"])]
    assert len(rows) == 100
    assert all(r["same_result"] and r["same_errors"] and r["same_first_failure"] and r["same_sha256"] for r in rows)
    for row, want in zip(rows[1:], sweep_record["mutants"]):
        assert (row["sha256"], row["result"], row["errors"], row["first_failure"]) == (
            want["sha256"], want["result"], want["errors"], want["first_failure"]), row

    # Fixtures: every test ran, none skipped; the linked setup and every must-refuse fixture passed.
    outcomes = junit_outcomes(upload / "fixtures.xml")
    assert len(outcomes) == 408 and set(outcomes.values()) <= {"passed", "failed"}
    assert outcomes[f"tests/test_gate_reads.py::{LINKED}"] == "passed"
    refusing = [t for t in outcomes if "_refused" in t.split("::")[1]]
    assert refusing and all(outcomes[t] == "passed" for t in refusing)

    # The bypass controls, read by decision E2.
    bypass = json.loads((upload / "bypass.json").read_text(encoding="utf-8"))
    assert len(bypass) == summary["bypass"]["count"] == sum(controls.BYPASS in t for t in outcomes)
    named = record["bypass_controls"]
    caller = []
    for control in bypass:
        test = control["test"]
        assert control["result"] == outcomes[test], test
        steps = [s for r in control["runs"] for s in r["steps"]]
        assert steps, test
        if not all(s["command"][0].startswith(WRAPPERS) for s in steps):  # item 3: the caller's by decision 6
            # A Verilator simulator build (no wrapper by eda.seat_tool), and the model it built, run by path.
            assert {r["backend"] for r in control["runs"]} == {"verilator-sim"}, test
            for r in control["runs"]:
                build, *model = [s["command"] for s in r["steps"]]
                assert build[0] == "verilator" and eda.seat_tool(build) is None, test
                assert all(not argv[0].startswith(WRAPPERS) and "/obj/" in argv[0] for argv in model), test
            caller.append(test)
            continue
        assert not any(word in json.dumps(control) for word in TARGET_CONTENT), test  # items 2 and 4
        if control["result"] == "passed":
            continue
        program, line = cause_of(test)  # item 1, for every tool run it made
        assert len(named["failed_as_the_account"][test]) == len(control["runs"]), test
        for run_record, said in zip(control["runs"], named["failed_as_the_account"][test]):
            printed = [ln for s in run_record["steps"] if s["command"][0] == WRAPPERS + program
                       for ln in s["error_lines"] + s["last_lines"]]
            assert any(line.search(ln) for ln in printed), (test, printed)
            assert said["line"] in printed and line.search(said["line"]), (test, said)
    assert caller == named["as_the_caller"]
    failed = sorted(t for t, o in outcomes.items() if o == "failed")
    assert failed == sorted(named["failed_as_the_account"]) == sorted(summary["bypass"]["failed"])
