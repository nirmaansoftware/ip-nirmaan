"""M88: what a tool run prints, writes and reads back is bounded, and its temporary directory is removed.

docs/GATE_INTEGRITY.md, section 7. A seat-written testbench that printed without stopping filled 1.4 GB of
log and 1.8 GB of result JSON in one run on the owner's machine; these tests hold each bound.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import pytest
from laws import needs

from nirmaan.evals import load_cases, load_record, record_run
from nirmaan.integrations import eda
from nirmaan.integrations.eda import Backend, EdaResult, execute, read_output, temporary_runs
from nirmaan.integrations.eda_parsers import Diagnostic

REPO = Path(__file__).resolve().parents[1]
MB = 2**20


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _backend(code: str, parse=None, name: str = "capcheck", **extra) -> Backend:
    """A backend whose one step runs ``code`` and whose parser claims a pass unless told otherwise."""
    return Backend(name, "cap.check", (Path(sys.executable).name,), lambda job: [_python(code)],
                   parse or (lambda run: EdaResult(True, "claimed a pass")), required=(), **extra)


@pytest.fixture()
def small_caps(monkeypatch):
    monkeypatch.setattr(eda, "OUTPUT_CAP", 1 * MB)
    monkeypatch.setattr(eda, "DISK_CAP", 4 * MB)
    monkeypatch.setattr(eda, "DISK_CHECK_SECONDS", 0.05)
    monkeypatch.delenv(eda.KEEP_ENV, raising=False)


def _size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


# --- What a run prints -------------------------------------------------------------------------


def test_a_step_that_prints_without_stopping_is_stopped_and_fails(small_caps, tmp_path):
    started = time.monotonic()
    out = execute(_backend("while True: print('x' * 99)"), {"workdir": str(tmp_path / "run"), "timeout": "60"})
    assert time.monotonic() - started < 20  # stopped at the cap, long before the timeout
    assert not out.succeeded  # the parser claimed a pass; the cap overrules it
    assert "output over 1 MB" in out.summary and "the run fails" in out.summary
    log = Path(out.references[0])
    assert log.stat().st_size <= 1 * MB + 4096
    assert "[nirmaan: output over 1 MB" in log.read_text(encoding="utf-8")
    assert out.data["output_bytes"] > 1 * MB
    assert Path(out.references[1]).stat().st_size < 64 * 1024


def test_the_cap_covers_every_step_together(small_caps, tmp_path):
    half = "import sys; sys.stdout.write('y' * (600 * 1024))"
    backend = Backend("twosteps", "cap.check", (Path(sys.executable).name,), lambda job: [_python(half), _python(half)],
                      lambda run: EdaResult(True, "claimed a pass"), required=())
    out = execute(backend, {"workdir": str(tmp_path / "run")})
    assert not out.succeeded and "output over 1 MB" in out.summary
    assert out.data["exit_statuses"] == [0]  # the second step was stopped


def test_a_run_under_the_cap_is_unchanged(small_caps, tmp_path):
    out = execute(_backend("print('hello')"), {"workdir": str(tmp_path / "run")})
    assert out.succeeded and out.summary == "capcheck: claimed a pass"
    assert "hello" in Path(out.references[0]).read_text(encoding="utf-8")
    assert out.data["output_bytes"] == len("hello\n")


# --- What a run writes ---------------------------------------------------------------------------


def test_a_step_that_writes_one_file_without_stopping_is_stopped(small_caps, tmp_path):
    code = "f = open('big.bin', 'wb')\nwhile True: f.write(b'z' * 65536)"
    out = execute(_backend(code), {"workdir": str(tmp_path / "run"), "timeout": "60"})
    assert not out.succeeded and "wrote 4 MB or" in out.summary
    assert _size(tmp_path / "run") <= 4 * MB + 64 * 1024  # the file limit stops it at the cap


@pytest.mark.skipif(shutil.which("dd") is None, reason="needs dd")
def test_a_compiled_step_is_killed_at_the_file_limit(small_caps, tmp_path):
    backend = Backend("capcheck", "cap.check", ("dd",), lambda job: [["dd", "if=/dev/zero", "of=big.bin", "bs=65536"]],
                      lambda run: EdaResult(True, "claimed a pass"), required=())
    out = execute(backend, {"workdir": str(tmp_path / "run"), "timeout": "60"})
    assert not out.succeeded and "wrote 4 MB or 100000 files or more in dd" in out.summary
    assert (tmp_path / "run" / "big.bin").stat().st_size <= 4 * MB


def _missing(argv0: str, tmp_path: Path):
    backend = Backend("capcheck", "cap.check", (), lambda job: [[argv0]],
                      lambda run: EdaResult(run.returncode == 0, "parsed"), required=())
    return execute(backend, {"workdir": str(tmp_path / "run")})


def test_a_missing_executable_is_a_failed_step(small_caps, tmp_path):
    out = _missing(str(tmp_path / "no-such-tool-m88"), tmp_path)  # a path: no PATH search, so always not found
    assert not out.succeeded and out.data["exit_statuses"] == [127]
    assert "FileNotFoundError" in Path(out.references[0]).read_text(encoding="utf-8")


def test_a_missing_executable_found_through_path_is_a_failed_step_on_any_account(small_caps, tmp_path, monkeypatch):
    """A bare name is looked up along PATH. When a PATH folder cannot be searched by the account (the review
    loop's ``loopcheck`` cannot enter the runner's home), the lookup reports PermissionError, not
    FileNotFoundError, as ``execvp`` and ``Popen`` both do; the step fails either way."""
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o000)
    try:
        for path in (os.environ.get("PATH", ""), f"{locked}{os.pathsep}{os.environ.get('PATH', '')}"):
            monkeypatch.setenv("PATH", path)
            out = _missing("no-such-tool-m88", tmp_path)
            log = Path(out.references[0]).read_text(encoding="utf-8")
            assert not out.succeeded and out.data["exit_statuses"] == [127]
            assert re.search(r"^(FileNotFoundError|PermissionError): .*'no-such-tool-m88'$", log, re.MULTILINE), log
    finally:
        locked.chmod(0o700)


def test_a_step_that_writes_many_files_is_stopped(small_caps, tmp_path):
    code = ("import itertools, time\n"
            "for n in itertools.count():\n"
            "    open(f'part{n}.bin', 'wb').write(b'z' * 262144)\n"
            "    time.sleep(0.005)")
    started = time.monotonic()
    out = execute(_backend(code), {"workdir": str(tmp_path / "run"), "timeout": "60"})
    assert time.monotonic() - started < 20
    assert not out.succeeded and "wrote 4 MB or" in out.summary
    assert _size(tmp_path / "run") < 16 * MB


def test_a_step_that_makes_files_without_end_is_stopped(small_caps, monkeypatch, tmp_path):
    monkeypatch.setattr(eda, "FILES_CAP", 500)
    code = "import itertools\nfor n in itertools.count(): open(f'f{n}', 'w').close()"
    started = time.monotonic()
    out = execute(_backend(code), {"workdir": str(tmp_path / "run"), "timeout": "60"})
    assert time.monotonic() - started < 20
    assert not out.succeeded and "500 files or more" in out.summary


def test_a_file_read_back_past_the_cap_fails_the_run(small_caps, tmp_path):
    def parse(run):
        read_output(run.workdir / "report.txt")
        return EdaResult(True, "claimed a pass")

    out = execute(_backend("open('report.txt', 'w').write('r' * (2 * 1024 * 1024))", parse),
                  {"workdir": str(tmp_path / "run")})
    assert not out.succeeded
    assert "report.txt is over 1 MB" in out.summary and "not read, the run fails" in out.summary


def test_read_output_reads_a_small_file_and_names_a_missing_one(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    assert read_output(tmp_path / "a.json") == "{}"
    assert read_output(tmp_path / "missing.json") is None


# --- What a record keeps -------------------------------------------------------------------------


def test_a_record_keeps_a_head_and_a_tail_of_the_diagnostics(small_caps, tmp_path):
    diags = tuple(Diagnostic("error", f"line {n} " + "m" * 5000) for n in range(10_000))
    out = execute(_backend("print('ok')", lambda run: EdaResult(False, "s" * 50_000, diags)),
                  {"workdir": str(tmp_path / "run")})
    kept = out.data["result"]["diagnostics"]
    assert len(kept) == 2 * eda.DIAGNOSTICS_KEPT
    assert kept[0]["message"].startswith("line 0 ") and kept[-1]["message"].startswith("line 9999 ")
    assert all(len(d["message"]) <= eda.TEXT_CAP for d in kept)
    assert out.data["diagnostics_not_kept"] == 10_000 - 2 * eda.DIAGNOSTICS_KEPT
    assert len(out.data["result"]["summary"]) <= eda.TEXT_CAP
    assert Path(out.references[1]).stat().st_size < 1 * MB


def test_metrics_past_their_cap_are_not_kept_and_fail_the_run(small_caps, monkeypatch, tmp_path):
    monkeypatch.setattr(eda, "METRICS_CAP", 1000)
    out = execute(_backend("print('ok')", lambda run: EdaResult(True, "claimed a pass", (), {"big": "b" * 5000})),
                  {"workdir": str(tmp_path / "run")})
    assert not out.succeeded and "metrics are over" in out.summary and out.metrics == {}


# --- Temporary directories -----------------------------------------------------------------------


def _runs(prefix: str = "nirmaan-capcheck-") -> set[Path]:
    import tempfile

    return set(Path(tempfile.gettempdir()).glob(prefix + "*"))


def test_a_temporary_run_directory_is_removed_when_its_scope_ends(small_caps):
    before = _runs()
    with temporary_runs():
        out = execute(_backend("print('ok')"), {})
        made = Path(out.references[0]).parent
        assert made.is_dir() and made in _runs() - before  # its log is readable while the scope lasts
    assert not made.exists()
    assert _runs() == before


def test_a_timed_out_or_capped_run_is_removed_too(small_caps):
    with temporary_runs():
        slow = execute(_backend("import time; time.sleep(30)"), {"timeout": "1"})
        loud = execute(_backend("while True: print('x' * 99)"), {"timeout": "60"})
        assert "timed out after 1s" in slow.summary and "output over" in loud.summary
        made = [Path(o.references[0]).parent for o in (slow, loud)]
    assert not any(p.exists() for p in made)


def test_a_run_that_raises_or_is_refused_removes_its_directory_at_once(small_caps):
    def boom(job):
        raise RuntimeError("the steps could not be built")

    before = _runs()
    with pytest.raises(RuntimeError):
        execute(Backend("capcheck", "cap.check", (), boom, lambda run: EdaResult(True, ""), required=()), {})
    refused = execute(_backend("print('ok')", check=lambda job: "refused for the test"), {})
    assert not refused.succeeded and "refused for the test" in refused.summary
    assert _runs() == before  # nothing waits for the scope


def test_a_scope_removes_what_it_made_when_an_older_directory_goes_first(small_caps):
    older = eda.temporary_directory("nirmaan-capcheck-")
    with temporary_runs():
        eda.remove_temporary(older)
        newer = eda.temporary_directory("nirmaan-capcheck-")
    assert not older.exists() and not newer.exists()


def test_a_given_workdir_is_never_removed(small_caps, tmp_path):
    with temporary_runs():
        out = execute(_backend("print('ok')"), {"workdir": str(tmp_path / "mine")})
    assert Path(out.references[0]).is_file()


def test_the_debug_setting_keeps_temporary_directories(small_caps, monkeypatch):
    monkeypatch.setenv(eda.KEEP_ENV, "1")
    with temporary_runs():
        out = execute(_backend("print('ok')"), {})
    kept = Path(out.references[0]).parent
    try:
        assert kept.is_dir()
    finally:
        shutil.rmtree(kept, ignore_errors=True)


def test_an_eval_trial_removes_its_sandbox_when_it_ends(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    monkeypatch.delenv(eda.KEEP_ENV, raising=False)
    case = next(c for c in load_cases(REPO / "evals") if c.id == "spec/axi4-lite-interface")
    path = record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock)
    (trial,) = load_record(path).trials
    assert trial.result.sandbox and not Path(trial.result.sandbox).exists()
    monkeypatch.setenv(eda.KEEP_ENV, "1")
    path = record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock)
    (kept,) = load_record(path).trials
    assert Path(kept.result.sandbox).is_dir()
    assert kept.result.passed == trial.result.passed  # removing the sandbox changes no verdict


# --- The incident: a seat testbench that prints without stopping -------------------------------

LOOPING_TB = """\
module tb;
  integer n;
  initial begin
    n = 0;
    forever begin
      $display("ERROR: check %0d failed, printing again and again to fill the disk", n);
      n = n + 1;
    end
  end
endmodule
"""


@needs("iverilog", "vvp")
def test_a_testbench_that_prints_in_a_loop_fails_quickly_with_bounded_disk(small_caps, tmp_path):
    tb = tmp_path / "tb.v"
    tb.write_text(LOOPING_TB, encoding="utf-8")
    run = tmp_path / "run"
    started = time.monotonic()
    icarus = next(b for b in eda.backends_for("simulator.run") if b.name == "icarus")
    out = execute(icarus, {"sources": str(tb), "top": "tb", "workdir": str(run), "timeout": "120"})
    assert time.monotonic() - started < 30
    assert not out.succeeded and "output over 1 MB in vvp" in out.summary
    assert _size(run) < 2 * MB  # the log at the cap, sim.vvp, and a small record
    record = json.loads(Path(out.references[1]).read_text(encoding="utf-8"))
    assert len(record["result"]["diagnostics"]) == 2 * eda.DIAGNOSTICS_KEPT
    assert record["diagnostics_not_kept"] > 0
    assert Path(out.references[1]).stat().st_size < 64 * 1024
