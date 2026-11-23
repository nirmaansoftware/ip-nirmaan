"""Gate ET5 as the seat account (scripts/live_eval_controls.py): what it runs and refuses, how a sweep row compares.

The runs themselves need the seat account, which only the live evaluation's `replay` job has; these tests check the
parts that need no account: the selection of the timer's controls, the fixture tests it names, the refusals before
anything runs, the comparison of a sweep row with the record, and that each sweep run is started in a run directory
of its own under ``/tmp/nirmaan-*`` with the step's environment naming it.
"""

from __future__ import annotations

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
