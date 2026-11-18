"""Gate WF17: seat code in the live evaluation runs as an account of its own, and the reach test proves it.

The account itself (useradd, setpriv, setfacl) exists only on the CI runner, where `.github/workflows/live-eval.yml`
runs the reach test before any trial; these tests pin what the scripts decide without it.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

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


def test_every_write_target_exists_or_the_reach_test_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "WRAPPER", tmp_path / "opt" / "bin" / "vvp")
    with pytest.raises(SystemExit, match="do not exist"):
        reach.targets(tmp_path / "records", {})
    (tmp_path / "opt" / "bin").mkdir(parents=True)
    (tmp_path / "opt" / "bin" / "vvp").write_text("")
    (tmp_path / "opt" / "seat.py").write_text("")
    (tmp_path / "records").mkdir()
    env = {"GITHUB_OUTPUT": str(tmp_path / "out"), "RUNNER_TEMP": str(tmp_path)}
    create, append = reach.targets(tmp_path / "records", env)
    assert str(REPO) in create and str(REPO / "src" / "nirmaan") in create and str(tmp_path / "records") in create
    assert str(tmp_path) in create and str(tmp_path / "out") in append
    assert str(REPO / ".github" / "workflows" / "live-eval.yml") in append


def test_harden_takes_write_from_other_accounts_and_leaves_sticky_folders(tmp_path):
    tree = tmp_path / "toolcache" / "Python" / "bin"
    tree.mkdir(parents=True)
    exe = tree / "python3.12"
    exe.write_text("")
    exe.chmod(0o777)
    tree.chmod(0o777)
    folder = tmp_path / "pathdir"
    folder.mkdir()
    folder.chmod(0o777)
    (folder / "tool").write_text("")
    (folder / "tool").chmod(0o757)
    (folder / "deep").mkdir()
    (folder / "deep" / "x").write_text("")
    (folder / "deep" / "x").chmod(0o666)
    sticky = tmp_path / "sticky"
    sticky.mkdir()
    sticky.chmod(0o1777)
    changed = seat.harden([str(tmp_path / "toolcache")], [str(folder), str(sticky), str(tmp_path / "absent")])
    assert sorted(changed) == sorted(map(str, [tree, exe, folder, folder / "tool"]))
    assert oct(exe.stat().st_mode & 0o777) == "0o775" and oct((folder / "tool").stat().st_mode & 0o777) == "0o755"
    assert (folder / "deep" / "x").stat().st_mode & 0o002  # a PATH folder is hardened one level deep
    assert sticky.stat().st_mode & 0o1777 == 0o1777
    assert seat.harden([str(tmp_path / "toolcache")], [str(folder)]) == []
