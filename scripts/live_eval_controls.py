"""Gate ET5 as the seat account: the timer's controls, its whole mutant sweep and the committed gate fixtures.

Gate ET5 of ``council/records/2026-11-22-eda-tools-seat-account.md`` asks that, with the tools that read seat Verilog
run as ``nirmaan-seat``, the timer's mutant sweep and controls and every committed fixture give the results they gave.
CI's test job runs them as the runner. This runs them in the ``replay`` job of ``.github/workflows/live-eval.yml``,
where ``NIRMAAN_SEAT_TOOLS`` names the account's wrappers (gate ET2), after the reach test and the reference answer's
replay, when a replay of ``flow/axil-timer`` is dispatched with ``controls`` set. It calls no model and takes no
secret. Three parts, each written to ``--out``:

- ``controls``: the timer's controls of ``evals/flow/controls.json``, through
  ``tests/test_whole_flow_controls.py::test_the_control_gets_the_verdict_it_expects``, from the checkout as CI's test
  job runs them. Each control's eval sandbox is in a ``/tmp/nirmaan-*`` folder, where the account's view of a run can
  hold its inputs (``scripts/live_eval_seat.py``). The test holds each control to the verdicts of
  ``evals/flow/controls_record.json``; its ``FLOW-CONTROL`` lines are kept (``controls.json``).
- ``sweep``: the reference RTL and every mutant of ``evals/flow/axil_timer/mutant_sweep.json``, rebuilt with
  ``tests/flow_mutants.py`` (each text's sha256 checked against the record) and run on the case's testbench copy by
  ``flow_mutants.simulate``, the function the sweep was written with, each in a run directory of its own under
  ``/tmp/nirmaan-*``, with ``iverilog`` and ``vvp`` the account's wrappers. Each row is compared with the record's
  result, error count and first failure (``sweep.json``).
- ``fixtures``: gate ET1's must-refuse fixtures and bypass controls (``tests/test_gate_inputs.py``,
  ``tests/test_gate_reads.py``) and the tests of the committed ``*_fail.v`` testbenches (``FIXTURE_TESTS``), from a
  copy of the checkout in a ``/tmp/nirmaan-*`` folder only the runner may read: the account reads only input files
  the runner made in such a folder, and these tests name committed files as inputs. Gate ET1's bypass controls
  (``test_control_without_the_check_*``: with the screen bypassed, the tool is expected to reach a canary or write a
  marker) are among them; for each, every tool run is written down as the tool gave it (``BypassOutcomes``,
  ``bypass.json``, and a ``BYPASS-CONTROL`` line each): its command, exit status, the lines it printed that name what
  it could not open or read, its last lines, and the run's own summary and metrics. That only records; no test's
  outcome changes.

Every pytest run requires the tools it uses (``NIRMAAN_REQUIRE_EDA``), so a missing tool fails, never skips. Each
writes its JUnit file and its output. ``summary.json`` names the commit, the wrappers and each part's outcome.

Exit codes: 0 every part ran, every test passed and every sweep row gave the record's result, error count and first
failure; 1 otherwise; 2 bad input (another case, or no seat account's wrappers: nothing ran).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = "flow/axil-timer"
SWEEP = ROOT / "evals" / "flow" / "axil_timer" / "mutant_sweep.json"
CONTROLS_TEST = "tests/test_whole_flow_controls.py"
#: The timer's controls, by their test's parameter ids (``evals/flow/controls.json``: every id starts ``timer-``).
CONTROLS_SELECT = "test_the_control_gets_the_verdict_it_expects and timer-"
#: Gate ET1's fixtures, and the tests that run the committed ``*_fail.v`` testbenches through the gates (the four
#: block fixtures' files whole, so each failing testbench beside its passing one).
FIXTURE_TESTS = (
    "tests/test_gate_inputs.py",
    "tests/test_gate_reads.py",
    "tests/test_apb_regs_fixture.py",
    "tests/test_axi4_lite_fixture.py",
    "tests/test_rr_arbiter_fixture.py",
    "tests/test_sync_fifo_fixture.py",
    "tests/test_nirmaan_eda.py::test_a_failing_simulation_log_feeds_veritriage",
    "tests/test_nirmaan_gate_integrity.py::test_a_testbench_that_reports_failure_in_words_fails",
    "tests/test_nirmaan_gates_everywhere.py::test_a_failing_self_check_blocks_review",
    "tests/test_nirmaan_gates_rest.py::test_a_failing_simulation_blocks_review",
)
#: The tools these tests run, required: a missing one fails its test instead of skipping it (``tests/laws.py``).
REQUIRED = "verilator iverilog vvp yosys cc make sby yices-smt2 eqy"
#: The seat account's programs this checks before anything runs (``nirmaan.integrations.eda.seat_tools_problem``).
WRAPPED = (["iverilog"], ["vvp"], ["yosys"], ["sby"], ["eqy"], ["verilator", "--lint-only"])
#: Where a run's directory and inputs must be for the account to see them (``scripts/live_eval_seat.py``).
RUN_ROOT, RUN_PREFIX = "/tmp", "nirmaan-"
FLOW_CONTROL = re.compile(r"^FLOW-CONTROL (\{.*\})$", re.MULTILINE)
BAD_INPUT = 2
#: Gate ET1's bypass controls, by the start of their test names (``tests/test_gate_inputs.py``,
#: ``tests/test_gate_reads.py``).
BYPASS = "test_control_without_the_check_"
#: A line a tool printed that says what it could not open, find or read (or another error), kept for a bypass control.
ERROR_LINE = re.compile(r"no such file|can't open|cannot open|could not open|can't find|cannot find|not found|"
                        r"permission denied|read-only file system|can't resolve|error", re.IGNORECASE)
#: How much of a step's output a bypass control's record keeps: lines of each kind, and characters of each line.
KEEP_LINES, KEEP_CHARS = 5, 400
#: How ``pytest_part`` starts pytest with ``BypassOutcomes``: as ``python -m pytest`` does (the current folder first
#: on ``sys.path``), with the plugin loaded from this file by its path, so nothing else is put on ``sys.path``.
BOOT = ("import importlib.util, os, sys\n"
        "sys.path[0] = os.getcwd()\n"
        "spec = importlib.util.spec_from_file_location('nirmaan_et5_controls', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "import pytest\n"
        "sys.exit(pytest.main(sys.argv[3:], plugins=[module.BypassOutcomes(sys.argv[2])]))\n")


def _kept(line: str) -> str:
    return line if len(line) <= KEEP_CHARS else line[:KEEP_CHARS] + "..."


def step_record(argv: Sequence[str], step) -> dict:
    """One tool step as it ran (``eda._run_step``): its command, exit status (None when stopped, and why), the lines it
    printed that name what it could not open or read, and its last lines."""
    lines = [line for line in step.output.splitlines() if line.strip()]
    return {"command": list(argv), "exit": step.code, "stopped": step.stopped,
            "error_lines": [_kept(line) for line in lines if ERROR_LINE.search(line)][:KEEP_LINES],
            "last_lines": [_kept(line) for line in lines[-KEEP_LINES:]]}


class BypassOutcomes:
    """A pytest plugin: for each bypass control (``BYPASS``), every gate run it made through
    ``nirmaan.integrations.eda`` (the backend, each step as ``step_record`` keeps it, the run's summary and metrics)
    and the test's result, one JSON line per control in ``path``. It wraps ``eda._execute`` and ``eda._run_step``,
    which ``eda.execute`` looks up when it runs, and passes every argument and result through unchanged."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.test: str | None = None
        self.result = "not run"
        self.runs: list[dict] = []

    def pytest_configure(self, config) -> None:
        from nirmaan.integrations import eda

        execute, run_step = eda._execute, eda._run_step

        def recorded_execute(backend, *args, **kwargs):
            if self.test is None:
                return execute(backend, *args, **kwargs)
            run = {"backend": backend.name, "tool": backend.tool, "steps": []}
            self.runs.append(run)
            outcome = execute(backend, *args, **kwargs)
            run.update(succeeded=outcome.succeeded, summary=outcome.summary, metrics=outcome.metrics)
            return outcome

        def recorded_step(argv, *args, **kwargs):
            step = run_step(argv, *args, **kwargs)
            if self.test is not None and self.runs:
                self.runs[-1]["steps"].append(step_record(argv, step))
            return step

        eda._execute, eda._run_step = recorded_execute, recorded_step

    def pytest_runtest_logstart(self, nodeid: str, location) -> None:
        self.test = nodeid if BYPASS in nodeid else None
        self.result, self.runs = "not run", []

    def pytest_runtest_logreport(self, report) -> None:
        if self.test is not None and (report.when == "call" or report.outcome != "passed"):
            self.result = report.outcome

    def pytest_runtest_logfinish(self, nodeid: str, location) -> None:
        if self.test is None:
            return
        line = {"test": self.test, "result": self.result, "runs": self.runs}
        with self.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(line, sort_keys=True, default=str) + "\n")
        self.test = None


def _eda():
    sys.path.insert(0, str(ROOT / "src"))
    from nirmaan.integrations import eda

    return eda


def wrappers_problem(env: dict[str, str]) -> str | None:
    """Why the seat account's wrappers are not what this job runs, or None: ``NIRMAAN_SEAT_TOOLS`` names them, each is
    root's and written by no other account, and ``iverilog`` and ``vvp`` on ``PATH`` are those wrappers (the sweep
    starts them by name)."""
    eda = _eda()
    folder = env.get(eda.SEAT_TOOLS_ENV, "").strip()
    if not folder:
        return f"{eda.SEAT_TOOLS_ENV} is not set: this runs only where the tools are the seat account's"
    problem = eda.seat_tools_problem([list(argv) for argv in WRAPPED])
    if problem:
        return problem
    for name in ("iverilog", "vvp"):
        found = shutil.which(name, path=env.get("PATH"))
        if found != str(Path(folder) / name):
            return f"{name} on PATH is {found}, not the seat account's wrapper {Path(folder) / name}"
    return None


def flow_controls(output: str) -> list[dict]:
    """The ``FLOW-CONTROL`` lines a controls run printed, each as the dict it holds."""
    return [json.loads(m) for m in FLOW_CONTROL.findall(output)]


def compare_row(expected: dict, got: tuple[int | None, int | None, str]) -> dict:
    """One sweep row as run here beside the record's: the result (``passes`` or ``fails``), the error count and the
    first failure, each the same or not."""
    passed, failed, why = got
    result = "passes" if failed == 0 and passed else "fails"
    row = {"result": result, "checks_passed": passed, "errors": failed, "first_failure": why,
           "expected_result": expected["result"]}
    row["same_result"] = result == expected["result"]
    if "errors" in expected:
        row["same_errors"] = failed == expected["errors"]
        row["same_first_failure"] = why == expected["first_failure"]
    else:  # the reference: it passes with the record's count of checks
        row["same_errors"] = failed == 0 and passed == expected["checks"]
        row["same_first_failure"] = why == ""
    return row


@contextlib.contextmanager
def run_directory() -> Iterator[Path]:
    """A run directory the account may be given (``/tmp/nirmaan-sweep-*``), the current directory inside the block, with
    the step's environment naming it as the gates do (``eda.SEAT_RUN_DIR_ENV``, no inputs outside it), removed after."""
    eda = _eda()
    where = Path(tempfile.mkdtemp(prefix=f"{RUN_PREFIX}sweep-", dir=RUN_ROOT)).resolve()
    before, saved = os.getcwd(), {k: os.environ.get(k) for k in (eda.SEAT_RUN_DIR_ENV, eda.SEAT_INPUTS_ENV)}
    os.environ[eda.SEAT_RUN_DIR_ENV], os.environ[eda.SEAT_INPUTS_ENV] = str(where), "[]"
    os.chdir(where)
    try:
        yield where
    finally:
        os.chdir(before)
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(where, ignore_errors=True)


def simulator_version() -> str:
    """The first line ``iverilog -V`` prints, as the sweep runs it, or "" when it does not start."""
    try:
        lines = subprocess.run(["iverilog", "-V"], capture_output=True, text=True).stdout.splitlines()
    except OSError:
        return ""
    return lines[0] if lines else ""


def sweep(out: Path) -> bool:
    """The whole timer sweep as the account (``sweep.json``); True when every row gave the record's result, error count
    and first failure, from the text whose sha256 the record holds."""
    sys.path.insert(0, str(ROOT / "tests"))
    import flow_mutants

    record = json.loads(SWEEP.read_text(encoding="utf-8"))
    assert record["case"] == CASE, record["case"]
    tb_text = (ROOT / record["testbench"]["path"]).read_text(encoding="utf-8")
    top = record["testbench"]["top"]
    reference = ROOT / record["reference"]["path"]
    built = flow_mutants.timer_mutants(reference.read_text(encoding="utf-8"))
    runs = [("reference", reference.name, reference.read_text(encoding="utf-8"), record["reference"])]
    runs += [(r["mutant"], f"{r['mutant']}.v", built.get(r["mutant"], ""), r) for r in record["mutants"]]
    with run_directory():
        version = simulator_version()
    rows = []
    for name, filename, text, expected in runs:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with run_directory() as where:
            tb = where / Path(record["testbench"]["path"]).name
            tb.write_text(tb_text, encoding="utf-8")
            source = where / filename
            source.write_text(text, encoding="utf-8")
            got = flow_mutants.simulate(tb, top, source, where)
        row = {"mutant": name, "tag": expected.get("tag"), "sha256": sha, "same_sha256": sha == expected["sha256"],
               **compare_row(expected, got)}
        rows.append(row)
        print(f"SWEEP {json.dumps(row, sort_keys=True)}", flush=True)
    ok = all(r["same_result"] and r["same_errors"] and r["same_first_failure"] and r["same_sha256"] for r in rows)
    (out / "sweep.json").write_text(json.dumps({
        "format": "nirmaan.et5-seat-sweep", "case": CASE, "sweep": SWEEP.relative_to(ROOT).as_posix(),
        "simulator": version, "rows": rows, "ok": ok}, indent=2) + "\n", encoding="utf-8")
    return ok


def pytest_part(name: str, tests: Sequence[str], cwd: Path, out: Path, env: dict[str, str],
                bypass: Path | None = None) -> dict:
    """One pytest run, its temporary folders in a ``/tmp/nirmaan-*`` folder of their own, its JUnit file and output
    kept; the tools it uses required. With ``bypass``, each bypass control's tool runs are written there
    (``BypassOutcomes``)."""
    base = Path(tempfile.mkdtemp(prefix=f"{RUN_PREFIX}et5-{name}-", dir=RUN_ROOT)).resolve()
    start = [sys.executable, "-c", BOOT, str(Path(__file__).resolve()), str(bypass)] if bypass else \
        [sys.executable, "-m", "pytest"]
    argv = [*start, "-q", "-rs", "-p", "no:cacheprovider", f"--basetemp={base / 'pytest'}",
            f"--junitxml={out / f'{name}.xml'}", *tests]
    proc = subprocess.run(argv, cwd=cwd, env={**env, "NIRMAAN_REQUIRE_EDA": REQUIRED}, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    (out / f"{name}.log").write_text(output, encoding="utf-8")
    print(output, flush=True)
    shutil.rmtree(base, ignore_errors=True)
    return {"tests": list(tests), "exit": proc.returncode, "junit": f"{name}.xml", "log": f"{name}.log",
            "output": output}


def bypass_lines(path: Path) -> list[dict]:
    """The bypass controls' records ``BypassOutcomes`` wrote, in the order they ran (none when it wrote none)."""
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def copy_checkout() -> Path:
    """A copy of the checkout in a ``/tmp/nirmaan-*`` folder only the runner may read (``mkdtemp`` makes it 0700), so
    the committed files a fixture test names are input files the account's view can hold."""
    base = Path(tempfile.mkdtemp(prefix=f"{RUN_PREFIX}et5-checkout-", dir=RUN_ROOT)).resolve()
    shutil.copytree(ROOT, base / "repo", symlinks=True,
                    ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache", "graphify-out"))
    return base / "repo"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", required=True, type=Path, help="the folder the records are written to")
    args = parser.parse_args(argv)
    case = os.environ.get("CASE", "")
    if case != CASE:
        print(f"::error::Gate ET5's controls run only with a replay of {CASE}, not {case!r}; nothing ran.")
        return BAD_INPUT
    problem = wrappers_problem(dict(os.environ))
    if problem:
        print(f"::error::{problem}; nothing ran.")
        return BAD_INPUT
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

    controls = pytest_part("controls", [CONTROLS_TEST, "-k", CONTROLS_SELECT], ROOT, out, env)
    lines = flow_controls(controls.pop("output"))
    (out / "controls.json").write_text(json.dumps(lines, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    swept = sweep(out)
    copy = copy_checkout()
    lines_file = out / "bypass.jsonl"
    lines_file.unlink(missing_ok=True)
    fixtures = pytest_part("fixtures", FIXTURE_TESTS, copy, out, {**env, "PYTHONPATH": str(copy / "src")},
                           bypass=lines_file)
    fixtures.pop("output")
    shutil.rmtree(copy.parent, ignore_errors=True)
    bypass = bypass_lines(lines_file)
    (out / "bypass.json").write_text(json.dumps(bypass, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines_file.unlink(missing_ok=True)
    for control in bypass:
        print(f"BYPASS-CONTROL {json.dumps(control, sort_keys=True)}", flush=True)

    ok = controls["exit"] == 0 and fixtures["exit"] == 0 and swept
    summary = {"format": "nirmaan.et5-seat-controls", "case": CASE, "commit": commit,
               "seat_tools": os.environ[_eda().SEAT_TOOLS_ENV], "required": REQUIRED.split(),
               "controls": {**controls, "lines": "controls.json", "count": len(lines)},
               "sweep": {"record": "sweep.json", "ok": swept}, "fixtures": fixtures,
               "bypass": {"record": "bypass.json", "count": len(bypass),
                          "failed": [c["test"] for c in bypass if c["result"] != "passed"]}, "ok": ok}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"ET5 as the seat account: controls exit {controls['exit']} ({len(lines)} controls), sweep "
          f"{'as recorded' if swept else 'DIFFERS'}, fixtures exit {fixtures['exit']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
