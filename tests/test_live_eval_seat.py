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
    monkeypatch.setattr(seat, "run", lambda cwd, exe, env, rest, run_dir=None, inputs=(): calls.append(
        (cwd, exe, env, rest, run_dir, inputs)) or 0)
    monkeypatch.setattr(seat.os, "geteuid", lambda: 0)
    argv = seat.wrap_argv("/usr/bin/vvp", ["--help", "-none"], "/tmp/nirmaan-x", COCOTB_ENV)
    assert seat.main(argv[5:]) == 0
    assert calls == [("/tmp/nirmaan-x", "/usr/bin/vvp", seat.kept_env(COCOTB_ENV), ["--help", "-none"], None, [])]
    # Gate ET2: the run's own directory and its input files, as the harness names them in the step's environment.
    named = {**COCOTB_ENV, seat.RUN_DIR_ENV: "/tmp/nirmaan-yosys-x",
             seat.INPUTS_ENV: json.dumps(["/tmp/nirmaan-flow-y/stages/rtl/a.v", "/tmp/nirmaan-flow-y/stages/rtl/b.v"])}
    argv = seat.wrap_argv("/usr/bin/yosys", ["-s", "synth.ys"], "/tmp/nirmaan-yosys-x", named)
    assert seat.main(argv[5:]) == 0
    assert calls[-1][3:] == (["-s", "synth.ys"], "/tmp/nirmaan-yosys-x",
                             ["/tmp/nirmaan-flow-y/stages/rtl/a.v", "/tmp/nirmaan-flow-y/stages/rtl/b.v"])
    assert not [pair for pair in seat.kept_env(named) if pair.startswith(("NIRMAAN_SEAT_",))]
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
    (opt / "bin" / "nirmaan-seat-model").write_text("")
    (opt / "seat.py").write_text("")
    (opt / "exes.json").write_text(json.dumps([str(opt / "bin" / "vvp")]))
    (tmp_path / "records").mkdir()
    return opt


def _usable_path() -> str:
    """The real PATH minus folders this account cannot reach.

    The cloud review loop runs its local check as another account, and the runner's own PATH still lists
    $RUNNER_TEMP/cad-bin, which that account cannot traverse; reach.targets stats every PATH folder and would
    raise PermissionError. These tests are about the targets, not about that account, so keep the readable folders.
    """
    return os.pathsep.join(d for d in os.environ["PATH"].split(os.pathsep) if d and os.access(d, os.X_OK))


def test_every_write_target_exists_or_the_reach_test_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "WRAPPER", tmp_path / "opt" / "bin" / "vvp")
    monkeypatch.setattr(reach, "TOOLS", ("python3",))
    with pytest.raises(SystemExit, match="cannot determine|do not exist"):
        reach.targets(tmp_path / "records", {"PATH": _usable_path()})
    _opt(tmp_path)
    (tmp_path / "cocotb").mkdir()
    (tmp_path / "cocotb" / "__init__.py").write_text("")
    real = reach.importlib.util.find_spec
    monkeypatch.setattr(reach.importlib.util, "find_spec", lambda name: SimpleNamespace(
        origin=str(tmp_path / "cocotb" / "__init__.py")) if name == "cocotb" else real(name))
    env = {"GITHUB_OUTPUT": str(tmp_path / "out"), "RUNNER_TEMP": str(tmp_path), "PATH": _usable_path()}
    create, append = reach.targets(tmp_path / "records", env)
    assert str(REPO) in create and str(REPO / "src" / "nirmaan") in create and str(tmp_path / "records") in create
    assert str(tmp_path) in create and str(tmp_path / "out") in append
    assert str(REPO / ".github" / "workflows" / "live-eval.yml") in append
    assert str(tmp_path / "cocotb") in create and str(tmp_path / "opt" / "bin" / "vvp") in append
    assert str(tmp_path / "opt" / "bin" / "nirmaan-seat-exec") in append  # M90: fw.test's wrapper
    assert str(tmp_path / "opt" / "bin" / "nirmaan-seat-model") in append  # gate W2C4: coverage.read's model wrapper
    assert reach.EXEC_NAME == seat.EXEC_NAME and reach.MODEL_NAME == seat.MODEL_NAME


@pytest.mark.parametrize("what", ["package", "cocotb", "tool", "wrapped", "path", "actions"])
def test_a_target_the_reach_test_cannot_determine_fails_it_never_shrinks_it(tmp_path, monkeypatch, what):
    """A None or a missing target must never read as denied: the reach test fails and no trial runs."""
    import nirmaan

    monkeypatch.setattr(reach, "WRAPPER", tmp_path / "opt" / "bin" / "vvp")
    monkeypatch.setattr(reach, "TOOLS", ("python3",))
    opt = _opt(tmp_path)
    env = {"PATH": _usable_path()}
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


# --- READ probes and the network (what the account may not read or reach) -------------------------------------


def test_the_account_gets_no_read_access_to_the_named_folders_and_no_network(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=1 if argv[1] == "-C" and len([c for c in calls if c[0] == argv[0]]) == 1
                               else 0)

    monkeypatch.setattr(seat.subprocess, "run", fake_run)
    monkeypatch.setattr(seat.shutil, "which", lambda name: f"/usr/sbin/{name}")
    seat.deny(999, [str(tmp_path)])
    assert calls[0] == ["setfacl", "-m", "u:nirmaan-seat:---", "--", str(tmp_path)]
    owner = ["-m", "owner", "--uid-owner", "999"]
    for tool, answer in (("iptables", "icmp-host-prohibited"), ("ip6tables", "icmp6-adm-prohibited")):
        tcp = ["OUTPUT", "-p", "tcp", *owner, "-j", "REJECT", "--reject-with", answer]
        drop = ["OUTPUT", *owner, "-j", "DROP"]
        # each checked, inserted first in the chain in order where missing, then both checked again
        assert [c for c in calls if c[0] == tool] == [[tool, "-C", *tcp], [tool, "-I", "OUTPUT", "1", *tcp[1:]],
                                                     [tool, "-C", *drop], [tool, "-C", *tcp], [tool, "-C", *drop]]
    (tmp_path / "file").write_text("x")
    (tmp_path / "link").symlink_to(tmp_path)
    for path in (tmp_path / "file", tmp_path / "link", tmp_path / "none"):
        with pytest.raises(seat.Refused, match="is not a folder"):
            seat.deny(999, [str(path)])
    monkeypatch.setattr(seat.shutil, "which", lambda name: None)
    with pytest.raises(seat.Refused, match="iptables is not installed"):
        seat.deny(999, [])


def test_the_action_takes_read_access_to_home_checkout_and_temporary_folder(monkeypatch):
    text = (REPO / ".github" / "actions" / "live-eval-seat" / "action.yml").read_text(encoding="utf-8")
    assert '--deny-read "$HOME" --deny-read "$GITHUB_WORKSPACE" --deny-read "$RUNNER_TEMP"' in text
    calls = []
    monkeypatch.setattr(seat, "install", lambda source, trees, folders, unreadable: calls.append(unreadable))
    monkeypatch.setattr(seat.os, "geteuid", lambda: 0)
    assert seat.main(["install", "--deny-read", "/home/runner", "--deny-read", "/x"]) == 0
    assert calls == [["/home/runner", "/x"]]


def test_the_held_out_files_are_every_reference_held_out_file_and_mutant():
    files = reach.held_out_files()
    for path in ("tests/fixtures/fw/axi4_lite/axi4_lite_regs_drv.c", "evals/firmware/axi4_lite/held_out_test.c",
                 "tests/fixtures/dv/crc8/crc8_block_cocotb.py",
                 "tests/fixtures/dv/crc8/mutants/crc8_block_poly_tap.v", "tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v"):
        assert str(REPO / path) in files
    assert all(Path(f).is_file() for f in files) and len(files) == len(set(files))


def test_a_held_out_file_that_does_not_exist_stops_the_reach_test(tmp_path):
    case = json.loads((REPO / "evals" / "dv" / "cocotb_crc.json").read_text(encoding="utf-8"))
    case["held_out"][0]["mutants"]["tests/fixtures/dv/crc8/crc8_block.v"].append("tests/fixtures/dv/crc8/none.v")
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    with pytest.raises(SystemExit, match="held-out files do not exist"):
        reach.held_out_files(tmp_path)


def test_the_read_canaries_are_readable_by_mode_and_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "held_out_files", lambda: ["/repo/held_out_test.c"])
    monkeypatch.setattr(reach, "ROOT", tmp_path / "repo")
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "home").mkdir()
    (tmp_path / "temp").mkdir()
    env = {"GITHUB_ACTIONS": "true", "HOME": str(tmp_path / "home"), "RUNNER_TEMP": str(tmp_path / "temp")}
    files, dirs, canaries = reach.read_targets(env, "c4nary", "n0nce")
    assert canaries == [tmp_path / "repo" / ".nirmaan-read-canary-n0nce", tmp_path / "temp" / ".nirmaan-read-canary-n0nce"]
    for canary in canaries:  # only the account's own denial keeps it out
        assert canary.read_text() == "c4nary\n" and canary.stat().st_mode & 0o777 == 0o644
    assert files == ["/repo/held_out_test.c", *(str(c) for c in canaries)]
    assert dirs == [str(tmp_path / "repo"), str(tmp_path / "repo" / ".git"), str(tmp_path / "home"),
                    str(tmp_path / "temp")]
    reach.remove_canaries(canaries)
    assert not any(c.exists() for c in canaries)
    for name in ("HOME", "RUNNER_TEMP"):  # in Actions both are required, never skipped
        with pytest.raises(reach.Unresolved, match=f"cannot determine {name}"):
            reach.read_targets({k: v for k, v in env.items() if k != name}, "c4nary", "n0nce")


def _probes(config: dict, monkeypatch) -> dict:
    """The probe module's tests as plain coroutines, with cocotb's decorator standing in."""
    monkeypatch.setitem(__import__("sys").modules, "cocotb", SimpleNamespace(test=lambda: (lambda f: f)))
    namespace: dict = {}
    exec(compile(reach.probe_module(config), "reach_probe_test.py", "exec"), namespace)  # noqa: S102
    return namespace


def _drive(coroutine) -> None:
    """Run a probe test that awaits nothing to its end (cocotb's scheduler is not needed for these)."""
    try:
        coroutine.send(None)
    except StopIteration:
        return
    raise AssertionError("the probe test awaited something")


def test_a_file_the_seat_can_read_is_never_counted_denied(tmp_path, monkeypatch, capsys):
    readable = tmp_path / "held_out.c"
    readable.write_text("secret")
    config = {"read_files": [str(readable)], "list_dirs": [], "network": []}
    with pytest.raises(AssertionError):
        _drive(_probes(config, monkeypatch)["reach_no_read"](None))
    assert f"REACH NOT DENIED: read {readable}: read 6 bytes" in capsys.readouterr().out
    with pytest.raises(AssertionError):
        _drive(_probes({**config, "read_files": [], "list_dirs": [str(tmp_path)]}, monkeypatch)["reach_no_read"](None))
    assert f"REACH NOT DENIED: list {tmp_path}: 1 entries" in capsys.readouterr().out
    if os.geteuid() != 0:  # a folder the account cannot enter: a permission error, so denied
        closed = tmp_path / "closed"
        closed.mkdir()
        (closed / "f").write_text("x")
        closed.chmod(0)
        try:
            config = {"read_files": [str(closed / "f")], "list_dirs": [str(closed)], "network": []}
            _drive(_probes(config, monkeypatch)["reach_no_read"](None))
        finally:
            closed.chmod(0o700)
        assert "REACH denied: read" in capsys.readouterr().out
    with pytest.raises(AssertionError):  # no target proves nothing
        _drive(_probes({"read_files": [], "list_dirs": [], "network": []}, monkeypatch)["reach_no_read"](None))


def test_a_refused_or_timed_out_connection_is_not_a_denial(monkeypatch, capsys):
    """Only EPERM or EACCES (the account's packets dropped) count, and ENETUNREACH for IPv6; a connection refused by
    a closed port reached the host, so it is not denied."""
    import errno
    import socket

    outcomes = {("1.1.1.1", 443): OSError(errno.EPERM, "x"), ("2606:4700:4700::1111", 443):
                OSError(errno.ENETUNREACH, "x"), ("127.0.0.1", 9): ConnectionRefusedError(errno.ECONNREFUSED, "x"),
                ("::1", 9): OSError(errno.EACCES, "x"), ("127.0.0.53", 53): None}

    class Fake:
        def __init__(self, *args):
            pass

        def settimeout(self, _):
            pass

        def connect(self, where):
            raise outcomes[where]

        def sendto(self, data, where):
            if outcomes[where]:
                raise outcomes[where]

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", Fake)
    config = {"network": [list(n) for n in reach.NETWORK]}
    with pytest.raises(AssertionError):
        _drive(_probes(config, monkeypatch)["reach_no_network"](None))
    out = capsys.readouterr().out
    assert f"REACH denied: tcp 1.1.1.1 port 443: PermissionError errno {errno.EPERM}" in out
    assert f"REACH denied: tcp6 2606:4700:4700::1111 port 443: OSError errno {errno.ENETUNREACH}" in out
    assert f"REACH NOT DENIED: tcp 127.0.0.1 port 9: ConnectionRefusedError errno {errno.ECONNREFUSED}" in out
    assert "REACH NOT DENIED: udp 127.0.0.53 port 53: sent" in out
    outcomes.update({("127.0.0.1", 9): OSError(errno.EPERM, "x"), ("127.0.0.53", 53): OSError(errno.EPERM, "x")})
    _drive(_probes(config, monkeypatch)["reach_no_network"](None))
    outcomes[("127.0.0.1", 9)] = OSError(errno.EHOSTUNREACH, "x")  # the rule's "prohibited" answer to TCP
    _drive(_probes(config, monkeypatch)["reach_no_network"](None))
    for kind_errno in (errno.ENETUNREACH, errno.ETIMEDOUT):  # IPv4 without a route, or a timeout: not shown denied
        outcomes[("1.1.1.1", 443)] = OSError(kind_errno, "x")
        with pytest.raises(AssertionError):
            _drive(_probes(config, monkeypatch)["reach_no_network"](None))


# --- Gates ET2 to ET4: the tools that read seat Verilog run as the seat account ---------------------------------


def test_the_tools_that_read_seat_verilog_are_wrapped_and_the_harness_agrees():
    """Gate ET2 (council/records/2026-11-22-eda-tools-seat-account.md): iverilog, verilator (a lint), yosys and sby
    are wrapped beside vvp, and eqy (gate W2C3 of council/records/2026-11-23-wave-2-close-meeting-1.md); the harness
    names the same programs and the same settings, and the reach test probes each one (vvp through cocotb). eqy is
    installed in the jobs from the same pinned suite as in CI's test job."""
    from nirmaan.integrations import eda

    assert seat.WRAPPED == ("vvp", "iverilog", "verilator", "yosys", "sby", "eqy") == eda.SEAT_TOOLS == reach.WRAPPED
    assert seat.MODEL_NAME == eda.SEAT_MODEL == reach.MODEL_NAME
    assert (seat.RUN_DIR_ENV, seat.INPUTS_ENV) == (eda.SEAT_RUN_DIR_ENV, eda.SEAT_INPUTS_ENV)
    assert {tool for tool, *_ in reach.TOOL_GATES} == set(seat.WRAPPED) - {"vvp"}
    assert "/opt/oss-cad-suite/bin" in seat.TOOL_PATH.split(":")
    setup = (REPO / ".github" / "actions" / "live-eval-setup" / "action.yml").read_text(encoding="utf-8")
    assert "tools: sby yices-smt2 eqy\n" in setup and "root: /opt\n" in setup  # not the runner's temporary folder
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "tools: sby yices-smt2 eqy\n" in ci  # the test job's eqy, from the same pinned suite
    flow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    assert flow.count("NIRMAAN_SEAT_TOOLS: /opt/nirmaan-seat/bin\n") == 3  # replay, live-eval, rejudge
    assert flow.count('--out "$RUNNER_TEMP/tool-reach/tool-reach.json"') == 3
    assert flow.count("name: live-eval-tool-reach-") == 3


def test_a_verilator_model_build_stays_with_the_runner_and_a_lint_does_not(monkeypatch):
    """Decision 6 of the ET record: the rule that keeps Verilator's model builds with the runner is stated and
    tested; every other wrapped command, and a Verilator lint, runs as the seat account."""
    assert seat.as_runner("/usr/bin/verilator", ["--cc", "--exe", "--build", "-Mdir", "obj", "a.v"])
    assert seat.as_runner("/usr/bin/verilator", ["--binary", "--top-module", "t", "a.v"])
    assert not seat.as_runner("/usr/bin/verilator", ["--lint-only", "-Wall", "a.v"])
    # gate W2C4: coverage.read's model build is the seat account's
    assert not seat.as_runner("/usr/bin/verilator", ["--cc", "--exe", "--build", "--coverage-line", "a.v"])
    for exe in ("/usr/bin/vvp", "/usr/bin/iverilog", "/usr/bin/yosys", "/opt/oss-cad-suite/bin/sby"):
        assert not seat.as_runner(exe, ["--cc"])
    execs = []
    monkeypatch.setattr(seat.os, "execv", lambda path, argv: execs.append((path, argv)) or (_ for _ in ()).throw(
        SystemExit(0)))
    with pytest.raises(SystemExit):
        seat.main(["wrap", "/usr/bin/verilator", "--", "--cc", "a.v"])
    assert execs[-1] == ("/usr/bin/verilator", ["/usr/bin/verilator", "--cc", "a.v"])  # no sudo: the runner's
    with pytest.raises(SystemExit):
        seat.main(["wrap", "/usr/bin/verilator", "--", "--lint-only", "a.v"])
    assert execs[-1][0] == "/usr/bin/sudo"


def test_an_input_is_a_file_the_runner_made_in_a_run_folder_reached_through_no_link(tmp_path):
    me = os.getuid()
    root = tmp_path / "tmp"
    seatdir = root / "nirmaan-flow-abc" / "stages" / "rtl"
    seatdir.mkdir(parents=True)
    good = seatdir / "a.v"
    good.write_text("module a; endmodule\n")
    assert seat.input_problem(str(good), me, root) is None
    (seatdir / "link.v").symlink_to(good)
    (root / "nirmaan-flow-link").symlink_to(root / "nirmaan-flow-abc")
    (root / "elsewhere").mkdir()
    (root / "elsewhere" / "a.v").write_text("x")
    (seatdir / "hard.v").write_text("x")
    os.link(seatdir / "hard.v", seatdir / "hard2.v")
    (seatdir / "sub").mkdir()
    cases = [(str(seatdir / "link.v"), "is a link"), (str(root / "nirmaan-flow-link" / "stages" / "rtl" / "a.v"),
             "is a link"), (str(root / "elsewhere" / "a.v"), "not inside a"), (str(tmp_path / "x.v"), "is not inside"),
             (str(seatdir / "none.v"), "does not exist"), (str(seatdir / "sub"), "is not a regular file"),
             (str(seatdir / "hard.v"), "has 2 names"), ("stages/rtl/a.v", "not an absolute, normal path"),
             (str(seatdir) + "/../rtl/a.v", "not an absolute, normal path"), (str(root / "nirmaan-x"), "not inside a")]
    for path, why in cases:
        problem = seat.input_problem(path, me, root)
        assert problem and why in problem, (path, problem)
    assert "does not belong to the runner" in seat.input_problem(str(good), me + 1, root)


def test_the_view_holds_the_run_directory_and_the_inputs_and_nothing_else(tmp_path):
    root = tmp_path / "tmp"
    run = root / "nirmaan-yosys-x"
    rtl = root / "nirmaan-flow-y" / "stages" / "rtl"
    judge = root / "nirmaan-flow-y" / "judge" / "held-out-1"
    for d in (run, rtl, judge):
        d.mkdir(parents=True)
    for f in (rtl / "a.v", judge / "tb.v", run / "synth.ys"):
        f.write_text("x")
    plan = seat.view_plan(run, run, [str(rtl / "a.v"), str(judge / "tb.v"), str(run / "synth.ys")], root)
    assert plan["mask"] == [str(root / "nirmaan-flow-y")]  # the sandbox is replaced by an empty folder
    assert plan["files"] == [str(rtl / "a.v"), str(judge / "tb.v")]  # holding only these, at their own paths
    assert plan["run_dir"] is None and plan["cwd"] == str(run)  # the run's directory is itself a top folder
    assert set(plan["ids"]) == set(plan["files"])
    # sby starts in its setup's folder, which is on the way to an input, and writes only the run's directory
    sby = seat.view_plan(run, rtl, [str(rtl / "a.v")], root)
    assert sby["cwd"] == str(rtl)
    with pytest.raises(seat.Refused, match="neither the run's directory nor a folder of its inputs"):
        seat.view_plan(run, judge, [str(rtl / "a.v")], root)
    # a run directory inside a sandbox (a tools-in-the-loop run): its folder is hidden too and the directory shown
    nested = root / "nirmaan-flow-y" / "runs" / "r1"
    nested.mkdir(parents=True)
    plan = seat.view_plan(nested, nested, [str(rtl / "a.v")], root)
    assert plan["mask"] == [str(root / "nirmaan-flow-y")] and plan["run_dir"] == str(nested)
    argv = seat.enter_argv(plan, ["/usr/bin/setpriv", "--", "/usr/bin/env", "-i", "/usr/bin/yosys"])
    assert argv[:5] == ["/usr/bin/python3", "-I", "/opt/nirmaan-seat/seat.py", "enter", "--plan"]
    assert json.loads(argv[5]) == plan and argv[6:8] == ["--", "/usr/bin/setpriv"]


def _beside_setup(tmp_path: Path) -> dict:
    """A sandbox as M68 leaves it for a proof (``model._place_beside``): an approved file, a setup that names it as
    ``m.v`` in its ``[files]``, and the link the platform placed beside the setup under that name. Beside it, a link
    to a file the run is not given, and a link to the approved file by a relative path."""
    root = tmp_path.resolve() / "tmp"
    box = root / "nirmaan-et5-fixtures-x" / "pytest" / "t0"
    approved = box / "approved" / "m.v"
    other = box / "host" / "secret.v"
    setup = box / "setup"
    for folder in (approved.parent, other.parent, setup):
        folder.mkdir(parents=True)
    approved.write_text("module m(input wire a, output wire b); assign b = a; endmodule\n")
    other.write_text("module secret; endmodule\n")
    sby = setup / "f.sby"
    sby.write_text("[options]\nmode bmc\ndepth 2\n\n[engines]\nsmtbmc\n\n[script]\nread -formal m.v\nprep -top m\n\n"
                   "[files]\nm.v\n")
    (setup / "m.v").symlink_to(approved)
    (setup / "out.v").symlink_to(other)
    (setup / "rel.v").symlink_to("../approved/m.v")
    run = root / "nirmaan-symbiyosys-y"
    run.mkdir(parents=True)
    return {"root": root, "approved": approved, "setup": setup, "sby": sby, "run": run}


def test_a_setup_opens_an_approved_file_linked_beside_it_inside_the_view(tmp_path):
    """M68's ``beside`` as the seat account (ET5 replay run 45119522138): sby starts in its setup's folder and opens each
    ``[files]`` name there, so the link the platform placed beside the setup is in the view, holding the approved file it
    names (an input the harness named), read only. A link to a file the run was not given, a link by any other text,
    and a link of another account's stay out of the view; nothing is added that is not a named input."""
    from nirmaan.integrations import eda

    me = os.getuid()
    s = _beside_setup(tmp_path)
    backend = next(b for b in eda.backends_for("formal.run") if b.name == "symbiyosys")
    job = eda.Job("formal.run", {"sby": str(s["sby"]), "sources": str(s["approved"])}, s["run"],
                  (str(s["approved"]),), None)
    inputs = eda.seat_inputs(backend, job)
    assert inputs == [str(s["approved"]), str(s["sby"])]  # the link's target is named; the link is not
    assert all(seat.input_problem(p, me, s["root"]) is None for p in inputs)
    plan = seat.view_plan(s["run"], s["setup"], inputs, s["root"], owner=me)
    in_view = set(plan["files"]) | set(plan["links"])
    for name in ("m.v", "f.sby"):  # what sby opens, relative to the folder it starts in
        assert str(s["setup"] / name) in in_view, name
    assert plan["links"] == {str(s["setup"] / "m.v"): str(s["approved"])}  # the named input, under the link's name
    assert set(plan["links"].values()) <= set(inputs) and str(s["approved"]) in plan["ids"]
    assert plan["mask"] == [str(s["root"] / "nirmaan-et5-fixtures-x")]  # the link's folder is hidden as before
    assert seat.view_plan(s["run"], s["setup"], inputs, s["root"], owner=me + 1)["links"] == {}  # not the runner's
    # A link to a link is not one (its text is no input's path); a link inside the run's directory is not looked at
    # (the directory is in the view as it is); a link beside the setup to an input inside the run's directory shows
    # that input, which the account may already read, held open since the check like the others.
    inside = s["run"] / "inside.v"
    inside.write_text("module inside; endmodule\n")
    (s["setup"] / "chain.v").symlink_to(s["setup"] / "m.v")
    (s["setup"] / "in.v").symlink_to(inside)
    (s["run"] / "m.v").symlink_to(s["approved"])
    plan = seat.view_plan(s["run"], s["setup"], [*inputs, str(inside)], s["root"], owner=me)
    assert plan["links"] == {str(s["setup"] / "in.v"): str(inside), str(s["setup"] / "m.v"): str(s["approved"])}
    assert str(inside) in plan["ids"] and plan["files"] == inputs
    assert seat.view_plan(s["run"], s["setup"], inputs, s["root"])["links"] == {}  # no owner: no link is looked at


def test_the_view_shows_a_beside_link_as_the_named_input_read_only(monkeypatch, tmp_path):
    """``enter`` places the link's path in the view as the input it names: the same file, held open since it was
    checked, bound read only on an empty file in the hidden folder; nothing is followed through the link itself."""
    s = _beside_setup(tmp_path)
    inputs = [str(s["approved"]), str(s["sby"])]
    plan = seat.view_plan(s["run"], s["setup"], inputs, s["root"], owner=os.getuid())
    mounts, placed, ran = [], [], []
    monkeypatch.setattr(seat.os, "O_PATH", getattr(os, "O_PATH", 0), raising=False)
    monkeypatch.setattr(seat.os, "unshare", lambda flags: None, raising=False)
    monkeypatch.setattr(seat.os, "CLONE_NEWNS", getattr(os, "CLONE_NEWNS", 0), raising=False)
    monkeypatch.setattr(seat.os, "chdir", lambda path: None)
    monkeypatch.setattr(seat.os, "execv", lambda exe, argv: ran.append(argv))
    monkeypatch.setattr(seat, "_mount", lambda *a: mounts.append(a))
    monkeypatch.setattr(seat, "_placeholder", lambda path: placed.append(path))
    seat.enter(plan, ["/usr/bin/setpriv", "--", "/usr/bin/sby"])
    link, approved = str(s["setup"] / "m.v"), str(s["approved"])
    assert placed == [approved, str(s["sby"]), link]  # each an empty file in the hidden folder, then bound
    bound = {target: source for source, target, _, flags, *_ in mounts if flags == seat.MS_BIND}
    assert bound[link] == bound[approved]  # the approved file's own descriptor, held since it was checked
    readonly = seat.MS_REMOUNT | seat.MS_BIND | seat.MS_RDONLY | seat.MS_NOSUID | seat.MS_NODEV
    assert (None, link, None, readonly) in mounts
    assert ran == [["/usr/bin/setpriv", "--", "/usr/bin/sby"]]


def test_run_refuses_an_input_the_runner_did_not_make_for_the_run(monkeypatch, tmp_path):
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    monkeypatch.setattr(seat, "_seat", lambda: type("P", (), {"pw_uid": 99999, "pw_gid": 99999})())
    monkeypatch.setattr(seat, "installed_exes", lambda: ["/usr/bin/yosys"])
    monkeypatch.setattr(seat, "STATE", tmp_path / "state")
    monkeypatch.setattr(seat, "LOCK", tmp_path / "state" / "lock")
    monkeypatch.setattr(seat, "GRANTS", tmp_path / "state" / "grants.json")
    monkeypatch.setattr(seat, "stop_seat", lambda uid: None)
    monkeypatch.setattr(seat, "cleanup", lambda: None)
    monkeypatch.setattr(seat, "run_dir_problem", lambda where, owner: None)
    ran = []
    monkeypatch.setattr(seat.subprocess, "Popen", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError))
    with pytest.raises(seat.Refused, match="a tool reads only files the runner made for this run"):
        seat.run(str(tmp_path), "/usr/bin/yosys", [], ["-s", "synth.ys"], run_dir=str(tmp_path),
                 inputs=["/home/runner/work/ip-nirmaan/ip-nirmaan/tests/fixtures/rtl/axil_timer/axil_timer.v"])
    assert ran == []  # nothing ran


def test_where_the_job_names_the_wrappers_a_seat_tool_never_runs_as_the_caller(tmp_path, monkeypatch):
    """Gate ET2, no fallback (as gate SC2 for fw.test): a wrapper that is missing, not root's or writable by another
    account refuses the run before any step, through the real backend; a Verilator model build is not asked for one."""
    from nirmaan.integrations import eda

    lint = [["verilator", "--lint-only", "-Wall", "a.v"]]
    build = [["verilator", "--cc", "--exe", "--build", "a.v"]]
    cocotb = [["iverilog", "-o", "sim.vvp", "a.v"], ["env", "GPI_USERS=x", "TOPLEVEL_LANG=verilog", "vvp", "sim.vvp"]]
    monkeypatch.delenv(eda.SEAT_TOOLS_ENV, raising=False)
    assert eda.seat_tools_problem(lint) is None and eda.seat_launch(lint[0]) == lint[0]  # elsewhere: as before
    monkeypatch.setenv(eda.SEAT_TOOLS_ENV, str(tmp_path))
    assert "the wrapper is not there" in eda.seat_tools_problem(lint)
    assert eda.seat_tools_problem(build) is None  # decision 6: a model build stays the caller's
    assert [eda.seat_tool(a) for a in (*lint, *build, *cocotb)] == ["verilator", None, "iverilog", "vvp"]
    (tmp_path / "verilator").write_text("#!/bin/sh\n")
    (tmp_path / "verilator").chmod(0o755)
    assert "not a regular file only root may write" in eda.seat_tools_problem(lint)  # this test's user is not root
    assert eda.seat_launch(cocotb[1]) == ["env", "GPI_USERS=x", "TOPLEVEL_LANG=verilog", str(tmp_path / "vvp"),
                                          "sim.vvp"]  # started by the wrapper's path, never by a name on PATH
    assert eda.seat_launch(build[0]) == build[0]
    (tmp_path / "a.v").write_text("module a(input wire x, output wire y); assign y = x; endmodule\n")
    backend = next(b for b in eda.backends_for("synth.run") if b.name == "yosys")
    outcome = eda.execute(backend, {"sources": str(tmp_path / "a.v"), "top": "a"})
    assert not outcome.succeeded and "never as the caller (gate ET2); nothing ran" in outcome.summary
    assert not outcome.references  # no step ran, so no log


def test_a_run_names_its_own_directory_and_every_file_it_was_given(tmp_path):
    """What the wrappers' view holds (gate ET2): the sources, the setup and every file its [files] names, the other
    files the parameters name, each resolved and existing."""
    from nirmaan.integrations import eda

    (tmp_path / "a.sv").write_text("module a; endmodule\n")
    (tmp_path / "props.sv").write_text("// properties\n")
    (tmp_path / "a.sby").write_text("[options]\nmode prove\n[files]\na.sv\nprops.sv\n# a comment\nmissing.sv\n")
    backend = next(b for b in eda.backends_for("formal.run") if b.name == "symbiyosys")
    job = eda.Job("formal.run", {"sby": str(tmp_path / "a.sby"), "sources": str(tmp_path / "a.sv")}, tmp_path / "run",
                  (str((tmp_path / "a.sv").resolve()),), None)
    assert eda.seat_inputs(backend, job) == [str((tmp_path / n).resolve()) for n in ("a.sv", "a.sby", "props.sv")]


def test_the_held_out_run_reads_its_case_files_from_copies_staged_for_the_run(tmp_path):
    """Gate ET4 (decision 3, item 1): a held-out check whose tool runs as the seat account in the live evaluation's
    jobs is given copies of the case files in the evaluation's sandbox, never the checkout's files, and the copy reads
    the same; a check of another tool is given the case files as before."""
    from nirmaan.evals import scorers
    from nirmaan.models import HeldOutCheck

    repo = tmp_path / "repo"
    (repo / "evals").mkdir(parents=True)
    (repo / "evals" / "tb.v").write_text("module tb; endmodule\n")
    seat_file = tmp_path / "sandbox" / "stages" / "rtl" / "a.v"
    seat_file.parent.mkdir(parents=True)
    seat_file.write_text("module a; endmodule\n")
    art = SimpleNamespace(kind="rtl_source", location=str(seat_file), task="t")
    engine = SimpleNamespace(state=SimpleNamespace(artifacts={"a1": art}, tool_runs={}))
    calls = []

    class Tools:
        def invoke(self, tool, **params):
            calls.append((tool, params))
            return "run-1", SimpleNamespace(succeeded=True, summary="ok")

    work = tmp_path / "sandbox" / "judge" / "check-1"
    for tool in ("simulator.run", "regmap.verify"):
        check = HeldOutCheck(name="c", tool=tool, seat_files={"sources": ("rtl_source",)},
                             case_files={"sources": ("evals/tb.v",)}, params={"top": "tb"})
        ctx = scorers.ScoreContext(engine, SimpleNamespace(artifacts=["a1"], id="t"), check, repo, Tools(), work)
        assert scorers.held_out_run(ctx).status.value == "passed"
    staged, given = calls[0][1]["sources"], calls[1][1]["sources"]
    assert staged[0] == str(seat_file) and Path(staged[1]).parent.parent == work and Path(staged[1]).name == "tb.v"
    assert Path(staged[1]).read_text() == "module tb; endmodule\n"
    assert given == [str(seat_file), str(repo / "evals" / "tb.v")]  # not a seat-account tool: as before
    from nirmaan.integrations.eda import HELD_OUT_STAGED
    assert HELD_OUT_STAGED == ("simulator.run", "lint.run", "synth.run")
    (tmp_path / "y").mkdir()
    (tmp_path / "y" / "tb.v").write_text("module other; endmodule\n")
    two = scorers._stage_cases(tmp_path / "two", {"sources": [repo / "evals" / "tb.v", tmp_path / "y" / "tb.v",
                                                              tmp_path / "x" / "tb.v"]})
    assert two == {"sources": [str(tmp_path / "two" / "1" / "tb.v"), str(tmp_path / "two" / "2" / "tb.v"),
                               str(tmp_path / "x" / "tb.v")]}  # two of one name apart; a path that is no file as given
    assert (tmp_path / "two" / "2" / "tb.v").read_text() == "module other; endmodule\n"


def test_the_tool_reach_probes_every_wrapped_tool_and_needs_each_wrapper_first_on_path(monkeypatch):
    """Gate ET3: the reach test checks every wrapper is first on PATH, and probes each tool with a control and three
    targets (the checkout, a runner-only file, the parent's environment), plus the held-out compile's two."""
    monkeypatch.setattr(reach.shutil, "which", lambda name: f"/opt/nirmaan-seat/bin/{name}" if name != "yosys"
                        else "/usr/bin/yosys")
    assert "yosys on PATH is /usr/bin/yosys, not the seat account's /opt/nirmaan-seat/bin/yosys" in reach.precheck()
    assert [t for t, *_ in reach.TOOL_GATES] == ["iverilog", "verilator", "yosys", "sby", "eqy"]
    assert [(g, b) for _, g, b, _ in reach.TOOL_GATES] == [("simulator.run", "icarus"), ("lint.run", "verilator-lint"),
                                                           ("synth.run", "yosys"), ("formal.run", "symbiyosys"),
                                                           ("equivalence.run", "eqy")]
    # a tool that read the target says nothing of not opening it, so the probe is not denied
    assert reach._opened(["syntax error"], ("Include file {} not found",), "/x")
    assert not reach._opened(["a.v:2: Include file /x not found"], ("Include file {} not found",), "/x")
    assert reach._opened(["a.v:2: Include file /y not found"], ("Include file {} not found",), "/x")


def test_the_tools_as_the_seat_account_change_no_fingerprint():
    """Gate ET7 (council/records/2026-11-22-eda-tools-seat-account.md): the change touches no file a fingerprint
    digests and no tool definition, so the default and whole-flow fingerprints are what they were."""
    from nirmaan.company.tools import TOOLS
    from nirmaan.runtime import harness

    digested = {*harness.CODE, *harness.LOOP_CODE, *harness.FLOW_CODE}
    for rel in ("nirmaan/integrations/eda.py", "nirmaan/evals/scorers.py"):
        assert rel not in digested, rel
    specs = json.dumps([spec.model_dump(mode="json") for spec in TOOLS])
    assert "NIRMAAN_SEAT" not in specs and "nirmaan-seat" not in specs  # no seat-account text reaches a seat


TOOL_REACH_RECORD = REPO / "evals" / "flow" / "tool_reach_record.json"
ET3_TOOLS = ("iverilog", "verilator", "yosys", "sby")


def test_the_committed_tool_reach_record_is_from_main_with_every_probe_denied_in_the_replay_and_rejudge_jobs():
    """Gate ET3 (decision 2, item 3): the committed record is a replay dispatched on main, holding the replay job's and
    the rejudge job's tool reach records, of one run and one commit, each with every wrapped tool probed through its
    gate as the seat account: every control passed and every probe denied."""
    record = json.loads(TOOL_REACH_RECORD.read_text())
    assert record["format"] == "nirmaan.tool-reach-record/1"
    parts = {"replay": record["replay"], "rejudge": record["rejudge"]}
    for job, part in parts.items():
        assert part["format"] == "nirmaan.tool-reach" and part["job"] == job and part["seat"] == "nirmaan-seat"
        assert part["seat_tools"] == "/opt/nirmaan-seat/bin" and part["every_denied"] is True, job
        assert part["probes"] and all(p["denied"] for p in part["probes"]), job
        # The tools gate ET3 names; a tool wrapped since (eqy, W2C3) has a record of its own, not this one.
        for tool, gate, _backend, _messages in [t for t in reach.TOOL_GATES if t[0] in ET3_TOOLS]:
            probes = [p for p in part["probes"] if p["tool"] == tool and p["gate"] == gate
                      and not p["probe"].startswith("held-out compile")]
            assert sum(p["target"] is None for p in probes) == 1, (job, tool)  # the control
            targets = [p["probe"] for p in probes if p["target"]]
            assert targets == ["checkout canary", "runner-only canary",
                               "credential canary in the parent's environment"], (job, tool)
        held = [p for p in part["probes"] if p["probe"].startswith("held-out compile")]
        assert len(held) == 2 and sum(p["target"] is not None for p in held) == 1, job
        assert any(p["gate"] == "formal.cover" for p in part["probes"]), job
    assert parts["replay"]["run_id"] == parts["rejudge"]["run_id"] and parts["replay"]["commit"] == \
        parts["rejudge"]["commit"]
    assert parts["replay"]["commit"][:8] in record["about"] and parts["replay"]["run_id"] in record["about"]
ET5_RECORD = REPO / "evals" / "flow" / "et5_replay_record.json"


def test_the_committed_et5_replay_record_is_from_main_names_the_timer_and_shows_exactly_what_et5_claims():
    """Gate ET5: the committed record is the replay of flow/axil-timer dispatched on main at c99ef1fe, run
    45073595509, of the same run and commit as the tool reach record: the RTL stage's lint, simulation and synthesis
    passed as the seat account, check 1 passed, check 2 passed clean with 4 of 4 mutants failing, and the re-judge was
    the same. It holds no controls or fixtures run, and says so."""
    record = json.loads(ET5_RECORD.read_text())
    reach_record = json.loads(TOOL_REACH_RECORD.read_text())
    assert record["format"] == "nirmaan.replay-record/1"
    run, manifest, trial = record["run"], record["manifest"], record["trial"]
    assert run["id"] == "45073595509" == reach_record["replay"]["run_id"]
    assert run["commit"].startswith("c99ef1fe") and run["commit"] == manifest["head_sha"] == \
        reach_record["replay"]["commit"]
    assert run["commit"][:8] in record["about"] and run["id"] in record["about"]
    assert set(run["jobs"]) == {"replay", "rejudge"} and all(j["conclusion"] == "success" for j in run["jobs"].values())
    assert all(run["id"] in j["url"] and j["id"] in j["url"] for j in run["jobs"].values())
    assert manifest["cases"] == ["flow/axil-timer"] and manifest["replay"] is True and manifest["trials"] == 1
    assert trial["case"] == "flow/axil-timer" and trial["passed"] is True and trial["replay"] is True
    for runs in (trial["gate_runs"], trial["rtl_stage_gate_runs"]):
        assert [(g["tool"], g["succeeded"]) for g in runs] == [("lint.run", True), ("simulator.run", True),
                                                               ("synth.run", True)]
    check1, check2 = trial["scores"]
    assert check1["name"] == "The reference testbench passes on the flow's RTL" and check1["status"] == "passed"
    assert check2["name"] == "The flow's testbench passes on the reference RTL and fails each timer mutant"
    assert check2["status"] == "passed" and len(check2["failed_runs"]) == 4  # 4 of 4 mutants
    by_run = {j["run"]: j for j in trial["judge_runs"]}
    assert by_run[check1["runs"][0]]["succeeded"] is True  # check 1, on the staged testbench
    assert by_run[check2["runs"][0]]["succeeded"] is True  # check 2 clean
    assert [by_run[r]["succeeded"] for r in check2["failed_runs"]] == [False] * 4  # each mutant failed
    assert record["rejudge"]["trials"] == [{"case": "flow/axil-timer", "trial": 1, "same": True, "differences": []}]
    assert trial["sha256_replay"] == trial["sha256_rejudged"]
    assert record["summary"]["cases"]["flow/axil-timer"]["passed"] == 1 == record["summary"]["cases"][
        "flow/axil-timer"]["n"]
    assert record["rejudged_summary"] == record["summary"]
    assert "records no run of the timer's controls or of the committed fixtures" in record["about"]


def test_the_eqy_probe_reads_its_target_from_the_gold_side_of_a_setup_the_gate_runs():
    """Gate W2C3 (council/records/2026-11-23-wave-2-close-meeting-1.md): eqy is probed through equivalence.run with a
    setup the gate accepts, whose gold side reads the file that includes the target and whose gate side reads another."""
    from nirmaan.integrations.equivalence import COMPARED  # noqa: F401  (registers the backend)
    from nirmaan.integrations.eda_guard import eqy_problem

    name, top, head, tail = reach.TOOL_FILES["eqy"]
    assert "read_verilog -sv reach_tool_gold.v" in reach.EQY_SETUP and name == "reach_tool_gold.v"
    assert "read_verilog -sv reach_tool_gate.v" in reach.EQY_SETUP and f"module {top}(" in reach.EQY_GATE
    assert head.startswith(f"module {top}(") and tail.endswith("endmodule\n")
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        setup = Path(d) / "reach_tool.eqy"
        setup.write_text(reach.EQY_SETUP)
        assert eqy_problem(setup) is None  # the control runs the gate's own checks, none bypassed


def test_the_coverage_probes_build_and_run_a_model_and_read_only_lines_it_printed():
    """Gate W2C4: the coverage probes include a target in the design (the build) and open it with $fopen in the
    testbench (the model); a line counts only as the model printed it, never as a tool echoed the source."""
    lines = reach.coverage_open("/x/t")
    assert '$fopen("/x/t", "r")' in lines and reach.COVERAGE_DENIED.format("/x/t") in lines
    assert reach.COVERAGE_OPENED.format("/x/t") in lines
    assert f"module {reach.COVERAGE_TOP};" in reach.COVERAGE_TB[0]
    assert '$display("NIRMAAN-SIM %0s 1 passed, 0 failed", nonce)' in reach.COVERAGE_TB[1]
    said = reach.COVERAGE_DENIED.format("/x/t")
    echoed = f'   12 | if (fd == 0) $display("{said}");'
    assert not reach._printed(["summary", echoed], said)  # a warning quoting the source is not the model's output
    assert reach._printed(["summary", f"$ vvp\n{said}\n"], said)
    assert reach._printed(["log", reach.COVERAGE_OPENED.format("/x/t") + ": CANARY"],
                          reach.COVERAGE_OPENED.format("/x/t"), start=True)


def test_coverage_builds_its_model_and_runs_it_as_the_seat_account_and_no_other_model_build_does(tmp_path,
                                                                                                    monkeypatch):
    """Gate W2C4: coverage.read's Verilator build is a seat-account run (``COVERAGE_BUILD``), and the model it built
    starts through ``SEAT_MODEL`` where the job names the wrappers, never as the caller; the verilator_coverage steps
    stay the caller's. Only that backend passes the flag, so the other model builds stay with the runner (gate ET9)."""
    import shlex

    from nirmaan.integrations import eda

    (tmp_path / "d.v").write_text("module d(input wire clk); endmodule\n")
    (tmp_path / "tb.v").write_text("module tb; d u(.clk(1'b0)); endmodule\n")
    backend = next(b for b in eda.backends_for("coverage.read") if b.name == "verilator-coverage")

    def steps(name: str) -> tuple[Path, list[list[str]]]:
        work = tmp_path / name
        work.mkdir()
        job = eda.Job("coverage.read", {"sources": f"{tmp_path / 'd.v'},{tmp_path / 'tb.v'}", "top": "tb"}, work,
                      (str(tmp_path / "d.v"), str(tmp_path / "tb.v")), "tb")
        return work, backend.steps(job)

    monkeypatch.delenv(eda.SEAT_TOOLS_ENV, raising=False)
    work, plain = steps("elsewhere")
    assert eda.COVERAGE_BUILD in plain[0] and plain[1][0] == str(work / "obj" / "Vtb")  # elsewhere: as before
    monkeypatch.setenv(eda.SEAT_TOOLS_ENV, str(tmp_path / "bin"))
    work, wrapped = steps("job")
    assert wrapped[1][:3] == [eda.SEAT_MODEL, str(work), str(work / "obj" / "Vtb")]
    assert [eda.seat_tool(a) for a in wrapped] == ["verilator", eda.SEAT_MODEL, None, None]
    assert eda.seat_launch(wrapped[1])[0] == str(tmp_path / "bin" / eda.SEAT_MODEL)  # by the wrapper's path
    assert eda.seat_launch(wrapped[2]) == wrapped[2]  # verilator_coverage: the caller's
    problem = eda.seat_tools_problem([wrapped[1]])
    assert problem and "the wrapper is not there" in problem and eda.SEAT_MODEL in problem
    assert eda.run_nonce(f"$ {shlex.join(wrapped[1])}\n") == wrapped[1][-1].split("=", 1)[1]  # the parser's nonce
    users = [p for p in (REPO / "src").rglob("*.py") if eda.COVERAGE_BUILD in p.read_text(encoding="utf-8")]
    assert users == [REPO / "src" / "nirmaan" / "integrations" / "eda.py"]
    assert (REPO / "src" / "nirmaan" / "integrations" / "eda.py").read_text(encoding="utf-8").count(
        f'"{eda.COVERAGE_BUILD}"') == 1  # the constant, which only the coverage backend and the rule use


def test_the_model_wrapper_runs_sudo_with_no_environment_and_the_run_directory(monkeypatch, capsys):
    run = "/tmp/nirmaan-verilator-coverage-x"
    argv = seat.model_argv(run, f"{run}/obj/Vtb", ["+nirmaan_nonce=ab"])
    assert argv == ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", "/opt/nirmaan-seat/seat.py", "run-model",
                    "--cwd", run, "--run-dir", run, "--exe", f"{run}/obj/Vtb", "--", "+nirmaan_nonce=ab"]
    text = seat.model_wrapper_text()
    assert text.startswith("#!/bin/sh\n") and text.endswith(
        'exec /usr/bin/python3 -I /opt/nirmaan-seat/seat.py model -- "$@"\n')
    assert seat.MODEL == Path("/opt/nirmaan-seat/bin/nirmaan-seat-model")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "canary")
    execs = []
    monkeypatch.setattr(seat.os, "execv", lambda path, argv: execs.append(argv) or (_ for _ in ()).throw(SystemExit(0)))
    with pytest.raises(SystemExit):
        seat.main(["model", "--", run, f"{run}/obj/Vtb", "+nirmaan_nonce=ab"])
    assert execs == [argv] and "canary" not in " ".join(execs[0]) and "--env" not in execs[0]
    assert seat.main(["model", "--", run]) == 126
    assert "nothing ran" in capsys.readouterr().err
    calls = []
    monkeypatch.setattr(seat, "run", lambda cwd, exe, env, rest, **kw: calls.append((cwd, exe, env, rest, kw)) or 0)
    monkeypatch.setattr(seat.os, "geteuid", lambda: 0)
    assert seat.main(argv[5:]) == 0
    assert calls == [(run, f"{run}/obj/Vtb", [], ["+nirmaan_nonce=ab"], {"built": True, "run_dir": run, "view": True})]


def test_a_built_model_runs_in_a_view_of_its_run_directory_and_only_from_inside_it(monkeypatch, tmp_path):
    """Gate W2C4: run-model runs the built program as the seat account in a view of its own (``enter``) that holds the
    run's directory and nothing else of its folder, with no environment; a program outside that directory never runs."""
    root = tmp_path / "tmp"
    box = root / "nirmaan-eval-x"
    run_dir = box / "judge" / "run"
    (run_dir / "obj").mkdir(parents=True)
    (box / "judge" / "reference.v").write_text("x")
    model = run_dir / "obj" / "Vtb"
    model.write_text("x")
    other = box / "judge" / "Vother"
    other.write_text("x")
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    monkeypatch.setattr(seat, "_seat", lambda: type("P", (), {"pw_uid": 99999, "pw_gid": 99999})())
    monkeypatch.setattr(seat, "STATE", tmp_path / "state")
    monkeypatch.setattr(seat, "LOCK", tmp_path / "state" / "lock")
    monkeypatch.setattr(seat, "GRANTS", tmp_path / "state" / "grants.json")
    monkeypatch.setattr(seat, "stop_seat", lambda uid: None)
    monkeypatch.setattr(seat, "cleanup", lambda: None)
    monkeypatch.setattr(seat, "run_dir_problem", lambda where, owner: None)
    monkeypatch.setattr(seat, "built_problem", lambda exe, where, owner: None)
    real_view = seat.view_plan
    monkeypatch.setattr(seat, "view_plan", lambda where, start, inputs, **kw: real_view(where, start, inputs, root, **kw))
    monkeypatch.setattr(seat, "grants_for", lambda where: [(str(where), "rwx")])
    monkeypatch.setattr(seat.subprocess, "run", lambda *a, **k: None)
    started = []

    class Done:
        returncode = 0

        def poll(self):
            return 0

    monkeypatch.setattr(seat.subprocess, "Popen", lambda argv, **k: started.append((argv, k)) or Done())
    with pytest.raises(seat.Refused, match="is not inside the run's directory"):
        seat.run(str(run_dir), str(other), [], [], built=True, run_dir=str(run_dir), view=True)
    assert started == []  # nothing ran
    assert seat.run(str(run_dir), str(model), [], ["+nirmaan_nonce=ab"], built=True, run_dir=str(run_dir),
                    view=True) == 0
    [(argv, kw)] = started
    assert argv[:4] == ["/usr/bin/python3", "-I", "/opt/nirmaan-seat/seat.py", "enter"] and kw["cwd"] == "/"
    plan = json.loads(argv[5])
    assert plan["mask"] == [str(box)] and plan["files"] == [] and plan["run_dir"] == str(run_dir)  # the folder hidden
    assert plan["cwd"] == str(run_dir)
    command = argv[argv.index("--") + 1:]
    assert command[0] == "/usr/bin/setpriv" and "--no-new-privs" in command
    assert command[command.index("-i") + 1:] == [*seat.BASE_ENV, str(model), "+nirmaan_nonce=ab"]  # no environment
