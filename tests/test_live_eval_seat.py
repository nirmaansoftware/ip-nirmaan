"""Gate WF17: seat code in the live evaluation runs as an account of its own, and the reach test proves it.

The account itself (useradd, setpriv, setfacl) exists only on the CI runner, where `.github/workflows/live-eval.yml`
runs the reach test before any trial; these tests pin what the scripts decide without it.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seat = _load("live_eval_seat")
reach = _load("live_eval_reach")

COCOTB_ENV = {"GPI_USERS": "/py/libpython3.12.so;cocotb._init:_initialise_testbench", "PYGPI_PYTHON_BIN": "/py/python",
              "PYTHONPATH": "/tmp/nirmaan-cocotb-x/cocotb_tests", "TOPLEVEL_LANG": "verilog", "COCOTB_TOPLEVEL": "crc",
              "COCOTB_TEST_MODULES": "test_crc", "COCOTB_RESULTS_FILE": "/tmp/nirmaan-cocotb-x/results.xml"}


def test_the_seat_gets_cocotb_settings_and_nothing_else():
    env = {**COCOTB_ENV, "CLAUDE_CODE_OAUTH_TOKEN": "canary", "NIRMAAN_REACH_CANARY": "canary", "HOME": "/home/runner",
           "PATH": "/usr/bin", "GITHUB_ENV": "/home/runner/work/_temp/env", "LD_PRELOAD": "/x.so",
           "COCOTB_AUTH_TOKEN": "canary", "PYTHONHOME": "/x"}
    kept = seat.kept_env(env)
    assert sorted(kept) == sorted(f"{k}={v}" for k, v in COCOTB_ENV.items())
    assert not any("canary" in pair for pair in kept)


def test_the_wrapper_runs_sudo_without_a_shell_and_without_the_environment():
    argv = seat.wrap_argv("/usr/bin/vvp", ["-m", "/py/cocotb/libs/libcocotbvpi_icarus.vpl", "sim.vvp", "-none"],
                          "/tmp/nirmaan-cocotb-x", {**COCOTB_ENV, "CLAUDE_CODE_OAUTH_TOKEN": "canary"})
    assert argv[:6] == ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", "/opt/nirmaan-seat/seat.py", "run"]
    assert argv[argv.index("--cwd") + 1] == "/tmp/nirmaan-cocotb-x" and argv[argv.index("--exe") + 1] == "/usr/bin/vvp"
    assert argv[argv.index("--") + 1:] == ["-m", "/py/cocotb/libs/libcocotbvpi_icarus.vpl", "sim.vvp", "-none"]
    assert "canary" not in " ".join(argv)
    text = seat.wrapper_text("/usr/bin/vvp")
    assert text.startswith("#!/bin/sh\n") and 'exec /usr/bin/python3 -I /opt/nirmaan-seat/seat.py wrap /usr/bin/vvp -- "$@"' in text


def test_the_arguments_reach_run_as_given(monkeypatch):
    calls = []
    monkeypatch.setattr(seat, "run", lambda cwd, exe, env, rest: calls.append((cwd, exe, env, rest)) or 0)
    monkeypatch.setattr(seat.os, "geteuid", lambda: 0)
    argv = seat.wrap_argv("/usr/bin/vvp", ["--help", "-none"], "/tmp/nirmaan-x", COCOTB_ENV)
    assert seat.main(argv[5:]) == 0
    assert calls == [("/tmp/nirmaan-x", "/usr/bin/vvp", seat.kept_env(COCOTB_ENV), ["--help", "-none"])]
    execs = []
    monkeypatch.setattr(seat.os, "execv", lambda path, argv: execs.append(argv) or (_ for _ in ()).throw(SystemExit(0)))
    with pytest.raises(SystemExit):
        seat.main(["wrap", "/usr/bin/vvp", "--", "-m", "x.vpl", "sim.vvp"])
    assert execs[0][-3:] == ["-m", "x.vpl", "sim.vvp"] and execs[0][0] == "/usr/bin/sudo"


def test_only_root_runs_the_account_modes(monkeypatch, capsys):
    monkeypatch.setattr(seat.os, "geteuid", lambda: 1001)
    for mode in (["install"], ["cleanup"], ["run", "--cwd", "/tmp/nirmaan-x", "--exe", "/usr/bin/vvp", "--", "a"]):
        assert seat.main(mode) == 126
    assert "runs as root" in capsys.readouterr().err


def test_run_refuses_a_setting_that_is_not_cocotbs(monkeypatch):
    monkeypatch.setenv("SUDO_UID", "1001")
    monkeypatch.setenv("SUDO_GID", "1001")
    monkeypatch.setattr(seat, "_seat", lambda: type("P", (), {"pw_uid": 999, "pw_gid": 999})())
    for pair in ("LD_PRELOAD=/x.so", "COCOTB_SECRET_KEY=x", "HOME=/home/runner"):
        with pytest.raises(seat.Refused, match="refusing to pass"):
            seat.run("/tmp/nirmaan-x", "/usr/bin/vvp", [pair], [])
    monkeypatch.setattr(seat, "installed_exes", lambda: ["/usr/bin/vvp"])
    with pytest.raises(seat.Refused, match="not a program this account runs"):
        seat.run("/tmp/nirmaan-x", "/bin/sh", [], [])
    monkeypatch.setenv("SUDO_UID", "0")
    with pytest.raises(seat.Refused, match="must be the runner"):
        seat.run("/tmp/nirmaan-x", "/usr/bin/vvp", [], [])


def test_a_run_directory_is_one_the_harness_made_in_the_temporary_folder(tmp_path):
    me = os.getuid()
    root = tmp_path / "tmp"
    run = root / "nirmaan-eval-abc" / "judge" / "check-1"
    run.mkdir(parents=True)
    assert seat.run_dir_problem(run, me, root) is None
    assert seat.grants_for(run, root) == [(str(root / "nirmaan-eval-abc"), "--x"),
                                          (str(root / "nirmaan-eval-abc" / "judge"), "--x"), (str(run), "rwx")]
    single = root / "nirmaan-cocotb-xyz"
    single.mkdir()
    assert seat.grants_for(single, root) == [(str(single), "rwx")]
    other = root / "elsewhere"
    other.mkdir()
    (root / "nirmaan-link").symlink_to(tmp_path)
    for where, why in [(tmp_path, "is not inside"), (root, "is not inside a"), (other, "is not inside a"),
                       (root / "nirmaan-link", "is not a directory")]:
        problem = seat.run_dir_problem(where, me, root)
        assert problem and why in problem, (where, problem)
    assert "does not belong to the runner" in seat.run_dir_problem(run, me + 1, root)


# --- M90: the program fw.test builds runs as the seat account ---------------------------------------------------


def test_the_exec_wrapper_runs_sudo_with_no_environment_and_no_shell(monkeypatch, capsys):
    argv = seat.exec_argv("/tmp/nirmaan-verilator-cosim-x/seat", "/tmp/nirmaan-verilator-cosim-x/cosim/Vdut",
                          ["+nirmaan_nonce=ab"])
    assert argv == ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", "/opt/nirmaan-seat/seat.py", "run-built",
                    "--cwd", "/tmp/nirmaan-verilator-cosim-x/seat", "--exe",
                    "/tmp/nirmaan-verilator-cosim-x/cosim/Vdut", "--", "+nirmaan_nonce=ab"]
    text = seat.exec_wrapper_text()
    assert text.startswith("#!/bin/sh\n") and text.endswith('exec /usr/bin/python3 -I /opt/nirmaan-seat/seat.py exec -- "$@"\n')
    assert seat.EXEC == Path("/opt/nirmaan-seat/bin/nirmaan-seat-exec") and seat.EXEC_NAME == "nirmaan-seat-exec"
    from nirmaan.integrations import firmware

    assert firmware.SEAT_EXEC == seat.EXEC_NAME  # fw.test looks for the wrapper this script installs
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "canary")
    execs = []
    monkeypatch.setattr(seat.os, "execv", lambda path, argv: execs.append(argv) or (_ for _ in ()).throw(SystemExit(0)))
    with pytest.raises(SystemExit):
        seat.main(["exec", "--", "/tmp/nirmaan-x/seat", "/tmp/nirmaan-x/cosim/Vdut", "+nirmaan_nonce=ab"])
    assert execs == [seat.exec_argv("/tmp/nirmaan-x/seat", "/tmp/nirmaan-x/cosim/Vdut", ["+nirmaan_nonce=ab"])]
    assert "canary" not in " ".join(execs[0]) and "--env" not in execs[0]
    assert seat.main(["exec", "--", "/tmp/nirmaan-x/seat"]) == 126
    assert "nothing ran" in capsys.readouterr().err


def test_run_built_runs_with_no_environment_and_passes_a_signal_on(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(seat, "run", lambda cwd, exe, env, rest, built=False: calls.append((cwd, exe, env, rest, built))
                        or 7)
    monkeypatch.setattr(seat.os, "geteuid", lambda: 0)
    assert seat.main(seat.exec_argv("/tmp/nirmaan-x/seat", "/tmp/nirmaan-x/cosim/Vdut", ["a"])[5:]) == 7
    assert calls == [("/tmp/nirmaan-x/seat", "/tmp/nirmaan-x/cosim/Vdut", [], ["a"], True)]
    monkeypatch.setattr(seat.os, "geteuid", lambda: 1001)
    assert seat.main(["run-built", "--cwd", "/tmp/nirmaan-x/seat", "--exe", "/tmp/nirmaan-x/cosim/Vdut"]) == 126
    assert "runs as root" in capsys.readouterr().err


def test_run_built_refuses_any_setting(monkeypatch):
    monkeypatch.setenv("SUDO_UID", "1001")
    monkeypatch.setenv("SUDO_GID", "1001")
    monkeypatch.setattr(seat, "_seat", lambda: type("P", (), {"pw_uid": 999, "pw_gid": 999})())
    for pair in ("COCOTB_TOPLEVEL=x", "PATH=/usr/bin"):
        with pytest.raises(seat.Refused, match="refusing to pass"):
            seat.run("/tmp/nirmaan-x/seat", "/tmp/nirmaan-x/cosim/Vdut", [pair], [], built=True)


def test_a_signal_that_ends_the_seat_run_ends_the_wrapper_by_the_same_signal(tmp_path):
    """So fw.test sees a crash under the account as it does without it (a negative exit status), not ``128 + N``."""
    import signal
    import subprocess
    import sys

    script = (f"import importlib.util, sys\nspec = importlib.util.spec_from_file_location('s', {str(REPO / 'scripts' / 'live_eval_seat.py')!r})\n"
              "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\nsys.exit(m.passed_on(int(sys.argv[1])))\n")
    for code, want in ((0, 0), (3, 3), (-signal.SIGSEGV, -signal.SIGSEGV), (-signal.SIGTERM, -signal.SIGTERM),
                       (-signal.SIGKILL, -signal.SIGKILL)):
        assert subprocess.run([sys.executable, "-I", "-c", script, str(code)], cwd=tmp_path).returncode == want, code


def test_a_built_program_is_one_the_runner_made_in_the_same_run_directory(tmp_path):
    me = os.getuid()
    root = tmp_path / "tmp"
    run = root / "nirmaan-verilator-cosim-abc"
    here = run / "seat"
    (run / "cosim").mkdir(parents=True)
    here.mkdir()
    exe = run / "cosim" / "Vdut"
    exe.write_text("x")
    exe.chmod(0o755)
    assert seat.built_problem(exe, here, me, root) is None
    nested = root / "nirmaan-eval-x" / "judge" / "fw-1"
    (nested / "cosim").mkdir(parents=True)
    (nested / "seat").mkdir()
    (nested / "cosim" / "Vdut").write_text("x")
    (nested / "cosim" / "Vdut").chmod(0o755)
    assert seat.built_problem(nested / "cosim" / "Vdut", nested / "seat", me, root) is None
    other = root / "nirmaan-other"
    other.mkdir()
    (other / "Vdut").write_text("x")
    (other / "Vdut").chmod(0o755)
    (run / "cosim" / "link").symlink_to(exe)
    (run / "folder").mkdir()
    (run / "fifo-dir").mkdir()
    os.mkfifo(run / "fifo-dir" / "fifo")
    for target, why in [(other / "Vdut", "is not inside the run directory"), (Path("/bin/sh"), "is not inside"),
                        (run, "is the run directory"), (run / "cosim" / "link", "is a link"),
                        (run / "folder", "is not a regular file"), (run / "fifo-dir" / "fifo", "is not a regular file")]:
        problem = seat.built_problem(target, here, me, root)
        assert problem and why in problem, (target, problem)
    assert "does not belong to the runner" in seat.built_problem(exe, here, me + 1, root)
    for mode, why in ((0o757, "writable by other accounts"), (0o4755, "set-id"), (0o750, "cannot be run by other")):
        exe.chmod(mode)
        problem = seat.built_problem(exe, here, me, root)
        assert problem and why in problem, (oct(mode), problem)


def test_the_checkout_is_never_a_run_directory():
    assert seat.run_dir_problem(REPO, os.getuid()) is not None


def test_reclaim_returns_files_and_removes_links(tmp_path, monkeypatch):
    chowned = []
    monkeypatch.setattr(seat.os, "lchown", lambda path, uid, gid: chowned.append(str(path)))
    run = tmp_path / "run"
    (run / "sub").mkdir(parents=True)
    (run / "results.xml").write_text("x")
    (run / "sub" / "f").write_text("y")
    (run / "link").symlink_to("/etc/passwd")
    os.mkfifo(run / "fifo")
    seat._reclaim(run, os.getuid(), (1, 1))
    assert not (run / "link").is_symlink() and not (run / "fifo").exists()
    assert sorted(Path(p).name for p in chowned) == ["f", "results.xml", "run", "sub"]
    assert (run / "results.xml").read_text() == "x"


def test_the_probe_module_tries_every_reach_and_one_control():
    config = {"seat": "nirmaan-seat", "runner": "runner", "runner_uid": 1001, "harness_pid": 42, "nonce": "n",
              "create_in": ["/repo"], "append_to": ["/repo/pyproject.toml"], "canaries": ["a", "b"],
              "secret_file": "/x/credential"}
    text = reach.probe_module(config)
    compile(text, "reach_probe_test.py", "exec")
    tests = [line.split("async def ")[1].split("(")[0] for line in text.splitlines() if line.startswith("async def ")]
    assert tuple(tests) == reach.PROBES
    assert text.count("@cocotb.test()") == len(reach.PROBES)
    assert json.loads(eval(text.split("CONFIG = json.loads(")[1].split(")\n")[0])) == config  # noqa: S307


def _junit(results: dict[str, str]) -> str:
    cases = "".join(f'<testcase classname="reach_probe_test" name="{n}">{"" if s == "pass" else f"<{s}/>"}</testcase>'
                    for n, s in results.items())
    return f'<testsuites><testsuite name="all">{cases}</testsuite></testsuites>'


def test_the_reach_test_passes_only_when_every_probe_is_in_the_results_and_passed():
    every = dict.fromkeys(reach.PROBES, "pass")
    assert reach.results_problem(_junit(every)) is None
    assert "not denied in reach_no_sudo" in reach.results_problem(_junit({**every, "reach_no_sudo": "failure"}))
    assert "not denied in reach_no_write" in reach.results_problem(_junit({**every, "reach_no_write": "error"}))
    assert "not denied in reach_no_signal" in reach.results_problem(_junit({**every, "reach_no_signal": "skipped"}))
    less = {k: v for k, v in every.items() if k != "reach_no_credential"}
    assert "missing reach_no_credential" in reach.results_problem(_junit(less))
    assert "unexpected tests extra" in reach.results_problem(_junit({**every, "extra": "pass"}))
    assert reach.results_problem(None) == "cocotb wrote no results"


def test_the_reach_test_needs_the_wrapper_first_on_path(monkeypatch):
    monkeypatch.setattr(reach.shutil, "which", lambda name: "/usr/bin/vvp")
    assert "not the seat account's /opt/nirmaan-seat/bin/vvp" in reach.precheck()
    monkeypatch.setattr(reach.shutil, "which", lambda name: None)
    assert "vvp on PATH is None" in reach.precheck()


def _opt(tmp_path: Path) -> Path:
    opt = tmp_path / "opt"
    (opt / "bin").mkdir(parents=True)
    (opt / "bin" / "vvp").write_text("")
    (opt / "bin" / "nirmaan-seat-exec").write_text("")
    (opt / "seat.py").write_text("")
    (opt / "exes.json").write_text(json.dumps([str(opt / "bin" / "vvp")]))
    (tmp_path / "records").mkdir()
    return opt


def test_every_write_target_exists_or_the_reach_test_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "WRAPPER", tmp_path / "opt" / "bin" / "vvp")
    monkeypatch.setattr(reach, "TOOLS", ("python3",))
    with pytest.raises(SystemExit, match="cannot determine|do not exist"):
        reach.targets(tmp_path / "records", {"PATH": os.environ["PATH"]})
    _opt(tmp_path)
    (tmp_path / "cocotb").mkdir()
    (tmp_path / "cocotb" / "__init__.py").write_text("")
    real = reach.importlib.util.find_spec
    monkeypatch.setattr(reach.importlib.util, "find_spec", lambda name: SimpleNamespace(
        origin=str(tmp_path / "cocotb" / "__init__.py")) if name == "cocotb" else real(name))
    env = {"GITHUB_OUTPUT": str(tmp_path / "out"), "RUNNER_TEMP": str(tmp_path), "PATH": os.environ["PATH"]}
    create, append = reach.targets(tmp_path / "records", env)
    assert str(REPO) in create and str(REPO / "src" / "nirmaan") in create and str(tmp_path / "records") in create
    assert str(tmp_path) in create and str(tmp_path / "out") in append
    assert str(REPO / ".github" / "workflows" / "live-eval.yml") in append
    assert str(tmp_path / "cocotb") in create and str(tmp_path / "opt" / "bin" / "vvp") in append
    assert str(tmp_path / "opt" / "bin" / "nirmaan-seat-exec") in append  # M90: fw.test's wrapper
    assert reach.EXEC_NAME == seat.EXEC_NAME


@pytest.mark.parametrize("what", ["package", "cocotb", "tool", "wrapped", "path", "actions"])
def test_a_target_the_reach_test_cannot_determine_fails_it_never_shrinks_it(tmp_path, monkeypatch, what):
    """A None or a missing target must never read as denied: the reach test fails and no trial runs."""
    import nirmaan

    monkeypatch.setattr(reach, "WRAPPER", tmp_path / "opt" / "bin" / "vvp")
    monkeypatch.setattr(reach, "TOOLS", ("python3",))
    opt = _opt(tmp_path)
    env = {"PATH": os.environ["PATH"]}
    if what == "package":
        monkeypatch.setattr(nirmaan, "__file__", None)
    elif what == "cocotb":
        real = reach.importlib.util.find_spec
        monkeypatch.setattr(reach.importlib.util, "find_spec", lambda name: None if name == "cocotb" else real(name))
    elif what == "tool":
        monkeypatch.setattr(reach, "TOOLS", ("python3", "no-such-gate-tool"))
    elif what == "wrapped":
        (opt / "exes.json").write_text("[]")
    elif what == "path":
        env = {}
    else:  # in Actions the step's command files and the runner's temporary folder are required
        env["GITHUB_ACTIONS"] = "true"
    with pytest.raises(reach.Unresolved, match="cannot determine"):
        reach.targets(tmp_path / "records", env)


def test_reach_fails_the_job_when_a_target_cannot_be_determined(tmp_path, monkeypatch):
    import nirmaan

    monkeypatch.setattr(reach, "precheck", lambda: None)
    monkeypatch.setattr(nirmaan, "__file__", None)
    with pytest.raises(SystemExit) as stop:
        reach.reach(tmp_path)
    assert stop.value.code not in (0, None)


def test_seat_c_as_the_seat_account_changes_no_fingerprint():
    """M90 (G3 fourth addendum, decision 2, item 5; gate WF25): the fw.test change touches no file a fingerprint
    digests and no tool definition, so the default and whole-flow fingerprints are what they were."""
    from nirmaan.company.tools import TOOLS
    from nirmaan.integrations import firmware
    from nirmaan.runtime import harness

    digested = {*harness.CODE, *harness.LOOP_CODE, *harness.FLOW_CODE}
    for rel in ("nirmaan/integrations/firmware.py", "nirmaan/integrations/eda.py"):
        assert rel not in digested, rel
    fw_specs = {spec.id: spec.model_dump(mode="json") for spec in TOOLS if spec.id in ("fw.build", "fw.test")}
    assert set(fw_specs) == {"fw.build", "fw.test"}
    assert not any(firmware.SEAT_EXEC in json.dumps(spec) for spec in fw_specs.values())  # no seat text reaches a seat
