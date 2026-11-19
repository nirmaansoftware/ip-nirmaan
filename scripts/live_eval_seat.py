"""Seat code in the live evaluation runs as an account of its own (gates WF9 and WF17; docs/LIVE_EVAL_EVIDENCE.md, 6).

GitHub's runner user has passwordless sudo, owns the checkout, the installed package and the records, and its
``nirmaan`` process holds the plan token, which any process of the same user can read in ``/proc/<pid>/environ``.
A cocotb test module is code by design (docs/GATE_INPUTS.md, section 4), and cocotb runs it inside ``vvp``. So in
the live evaluation's jobs ``vvp`` is a wrapper that runs the real ``vvp`` as ``nirmaan-seat``: a system account with
no password, no sudo rule, no group but its own, ``no_new_privs`` set (so no setuid program, sudo included, gives
it more), and an environment holding only cocotb's own settings. It may write only the run's own directory; every
other grant is taken back when the run ends. The harness code is unchanged: the wrapper is first on ``PATH``.

``fw.test`` runs the co-simulation it builds (the seat's C linked with the harness, M90) by path, not through
``PATH``, so it has a wrapper of its own: where ``nirmaan-seat-exec`` is on ``PATH``, ``fw.test`` runs the built
program through it, in a folder of its own inside the run's directory (``nirmaan.integrations.firmware``). That runs
as the same account, with ``no_new_privs`` and an empty environment; the program must be one the runner built in the
same run directory.

Modes, each run by the workflow or by the wrapper:

- ``install`` (as root, from ``.github/actions/live-eval-seat``): make the account, copy this file to
  ``/opt/nirmaan-seat/seat.py`` (root's, so seat code cannot change it) and write the ``vvp`` wrapper beside it.
- ``wrap EXE ARGS`` (as the runner, from the wrapper): keep cocotb's settings from the environment and drop the
  rest, then ``sudo`` to ``run``.
- ``run`` (as root, through sudo): stop any seat process left over, give the seat account the run's directory, run
  ``EXE`` as the seat account, then ``cleanup``.
- ``exec DIR EXE ARGS`` (as the runner, from ``nirmaan-seat-exec``): pass nothing of the environment, then ``sudo``
  to ``run-built``.
- ``run-built`` (as root, through sudo): as ``run``, with ``DIR`` as the seat's folder, for a program the runner
  built in the same run directory (``built_problem``), with an empty environment. A run ended by a signal ends this
  process by the same signal, so the harness sees the signal as it would without the account.
- ``cleanup`` (as root): stop every seat process, give every file the seat account made in a run directory back to
  the runner (a link or any other non-regular file it made there is removed first, so nothing the harness reads
  afterwards leads elsewhere), take back every grant, and remove what it left in the shared temporary folders.

``fw.build`` compiles the seat's C and ``fw.test`` compiles and links it; both run the compiler as the runner. Seat C
runs only in ``fw.test``'s last step, as the seat account where ``nirmaan-seat-exec`` is installed. A live trial of a
case that runs seat C is still refused (``scripts/live_eval_ci.py``): lifting that is a change of its own.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pwd
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

SEAT = "nirmaan-seat"
HOME = Path("/opt/nirmaan-seat")
INSTALLED = HOME / "seat.py"
BIN = HOME / "bin"
STATE = Path("/run/nirmaan-seat")
GRANTS = STATE / "grants.json"
LOCK = STATE / "lock"
#: The programs that run seat code, wrapped by name. cocotb runs a test module inside ``vvp``.
WRAPPED = ("vvp",)
#: The wrapper ``fw.test`` runs its built co-simulation through (``nirmaan.integrations.firmware.SEAT_EXEC``).
EXEC_NAME = "nirmaan-seat-exec"
EXEC = BIN / EXEC_NAME
#: Where a run's directory must be: one the harness made in the temporary folder (``eda.run_directory``).
RUN_ROOT = Path("/tmp")
RUN_PREFIX = "nirmaan-"
#: The shared folders the seat account can write without a grant; what it leaves there is removed.
SHARED = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))
#: What the seat's environment may carry from the harness's: cocotb's own settings (``cocotb_runner._cocotb``).
KEEP_ENV = re.compile(r"^(COCOTB_[A-Z0-9_]+|GPI_USERS|PYGPI_[A-Z0-9_]+|TOPLEVEL_LANG|TOPLEVEL|PYTHONPATH|"
                      r"RANDOM_SEED|LIBPYTHON_LOC)$")
#: A name that could hold a credential is never passed, whatever ``KEEP_ENV`` says (as eda.SECRET_ENV_RE).
SECRET = re.compile(r"TOKEN|SECRET|KEY|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|SESSION", re.IGNORECASE)
#: The seat's environment before cocotb's settings: no home, the system's programs, a locale.
BASE_ENV = ("HOME=/nonexistent", "PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8")
SYSCTLS = {"fs/protected_hardlinks": "1", "fs/protected_symlinks": "1"}


class Refused(Exception):
    pass


# --- As the runner ----------------------------------------------------------------------------------------------


def kept_env(env: Mapping[str, str]) -> list[str]:
    """The ``NAME=VALUE`` settings the seat's run is given: cocotb's own, never one that could be a credential."""
    return [f"{k}={v}" for k, v in sorted(env.items()) if KEEP_ENV.match(k) and not SECRET.search(k)]


def wrap_argv(exe: str, args: Sequence[str], cwd: str, env: Mapping[str, str], script: str = str(INSTALLED)) -> list[str]:
    """The sudo command that runs ``exe`` as the seat account in ``cwd``. Nothing is given to a shell."""
    argv = ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", script, "run", "--cwd", cwd, "--exe", exe]
    for pair in kept_env(env):
        argv += ["--env", pair]
    return [*argv, "--", *args]


def wrapper_text(exe: str, script: str = str(INSTALLED)) -> str:
    return (f"#!/bin/sh\n# Runs {exe} as {SEAT} (scripts/live_eval_seat.py; docs/LIVE_EVAL_EVIDENCE.md, section 6).\n"
            f"exec /usr/bin/python3 -I {script} wrap {exe} -- \"$@\"\n")


def exec_argv(where: str, exe: str, args: Sequence[str], script: str = str(INSTALLED)) -> list[str]:
    """The sudo command that runs a built program ``exe`` as the seat account in ``where``, with no environment."""
    return ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", script, "run-built", "--cwd", where, "--exe", exe, "--",
            *args]


def exec_wrapper_text(script: str = str(INSTALLED)) -> str:
    return (f"#!/bin/sh\n# Runs DIR EXE ARGS: a program fw.test built, as {SEAT} (scripts/live_eval_seat.py; "
            f"docs/LIVE_EVAL_EVIDENCE.md, section 6).\nexec /usr/bin/python3 -I {script} exec -- \"$@\"\n")


# --- As root ------------------------------------------------------------------------------------------------------


def run_dir_problem(cwd: Path, owner: int, root: Path = RUN_ROOT) -> str | None:
    """Why ``cwd`` is not a run directory the harness made, or None. ``cwd`` is already resolved."""
    try:
        rel = cwd.relative_to(root)
    except ValueError:
        return f"{cwd} is not inside {root}"
    if not rel.parts or not rel.parts[0].startswith(RUN_PREFIX):
        return f"{cwd} is not inside a {root}/{RUN_PREFIX}* directory"
    here = root
    for part in rel.parts:
        here = here / part
        info = os.lstat(here)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            return f"{here} is not a directory"
        if info.st_uid != owner:
            return f"{here} does not belong to the runner (uid {info.st_uid}, not {owner})"
    return None


def built_problem(exe: Path, cwd: Path, owner: int, root: Path = RUN_ROOT) -> str | None:
    """Why ``exe`` is not a program the runner built in the run directory that holds ``cwd``, or None.

    Both are already resolved. The program must be inside the same ``root/nirmaan-*`` directory as ``cwd``, every
    folder from there down to it the runner's own and not a link, and itself a regular file of the runner's that no
    other account may write, with no set-id bit, that the seat account may run."""
    top = root / cwd.relative_to(root).parts[0]
    try:
        rel = exe.relative_to(top)
    except ValueError:
        return f"{exe} is not inside the run directory {top}"
    if not rel.parts:
        return f"{exe} is the run directory, not a program in it"
    here = top
    for part in rel.parts:
        here = here / part
        info = os.lstat(here)
        if stat.S_ISLNK(info.st_mode):
            return f"{here} is a link"
        if info.st_uid != owner:
            return f"{here} does not belong to the runner (uid {info.st_uid}, not {owner})"
        if here != exe and not stat.S_ISDIR(info.st_mode):
            return f"{here} is not a directory"
    info = os.lstat(exe)
    if not stat.S_ISREG(info.st_mode):
        return f"{exe} is not a regular file"
    if info.st_mode & (stat.S_IWOTH | stat.S_ISUID | stat.S_ISGID):
        return f"{exe} is writable by other accounts or set-id (mode {stat.S_IMODE(info.st_mode):o})"
    if not info.st_mode & stat.S_IXOTH:
        return f"{exe} cannot be run by other accounts (mode {stat.S_IMODE(info.st_mode):o})"
    return None


def passed_on(code: int) -> int:
    """The exit status for a run that ended with ``code``: a run ended by a signal ends this process by the same
    signal (no core is written), so the caller sees what it would have seen without the account. Only if that
    fails, ``128 + N``."""
    if code >= 0:
        return code
    signum = -code
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.signal(signum, signal.SIG_DFL)
    except (OSError, ValueError):  # SIGKILL keeps its default; it still ends this process below
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    os.kill(os.getpid(), signum)
    return 128 + signum


def grants_for(cwd: Path, root: Path = RUN_ROOT) -> list[tuple[str, str]]:
    """What the seat account is given: passage through each folder above the run's directory, and the directory."""
    rel = cwd.relative_to(root)
    above = [root.joinpath(*rel.parts[:n]) for n in range(1, len(rel.parts))]
    return [*((str(p), "--x") for p in above), (str(cwd), "rwx")]


def _seat() -> pwd.struct_passwd:
    return pwd.getpwnam(SEAT)


def _seat_pids(uid: int) -> list[int]:
    pids = []
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                if os.stat(f"/proc/{entry}").st_uid == uid:
                    pids.append(int(entry))
            except FileNotFoundError:
                pass
    return pids


def stop_seat(uid: int) -> None:
    """Kill every process of the seat account, and wait until none is left."""
    for _ in range(100):
        pids = _seat_pids(uid)
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.05)
    raise SystemExit(f"{SEAT}: processes {_seat_pids(uid)} would not stop")


def _load_grants() -> dict:
    try:
        return json.loads(GRANTS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"owner": None, "paths": []}


def _save_grants(data: dict) -> None:
    tmp = GRANTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, GRANTS)


def _reclaim(run_dir: Path, uid: int, owner: tuple[int, int]) -> None:
    """Give back to the runner what the seat account made in ``run_dir``; remove what is not a file or folder."""
    if not run_dir.is_dir() or run_dir.is_symlink():
        return
    for top, dirs, files in os.walk(run_dir, topdown=False, followlinks=False):
        for name in [*files, *dirs]:
            path = os.path.join(top, name)
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                continue
            if info.st_uid != uid:
                continue
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                os.unlink(path)
            else:
                os.lchown(path, *owner)
    info = os.lstat(run_dir)
    if info.st_uid == uid:
        os.lchown(run_dir, *owner)


def _sweep(uid: int) -> None:
    """Remove what the seat account left in the shared temporary folders, outside any run directory."""
    for shared in SHARED:
        if not shared.is_dir():
            continue
        for top, dirs, files in os.walk(shared, topdown=False, followlinks=False):
            for name in files:
                path = os.path.join(top, name)
                try:
                    if os.lstat(path).st_uid == uid:
                        os.unlink(path)
                except OSError:
                    pass
            for name in dirs:
                path = os.path.join(top, name)
                try:
                    if os.lstat(path).st_uid == uid:
                        if os.path.islink(path):
                            os.unlink(path)
                        else:
                            os.rmdir(path)
                except OSError:
                    pass


def cleanup() -> None:
    seat = _seat()
    stop_seat(seat.pw_uid)
    data = _load_grants()
    if data.get("owner"):
        owner = tuple(data["owner"])
        for path, mode in reversed(data["paths"]):
            if mode == "rwx":
                _reclaim(Path(path), seat.pw_uid, owner)  # type: ignore[arg-type]
    for path, _ in reversed(data.get("paths", [])):
        if os.path.lexists(path):
            subprocess.run(["setfacl", "-x", f"u:{SEAT}", "--", path], check=False)
    _save_grants({"owner": None, "paths": []})
    _sweep(seat.pw_uid)


def run(cwd: str, exe: str, env: Sequence[str], args: Sequence[str], built: bool = False) -> int:
    """Run ``exe`` as the seat account in ``cwd``; its exit status, negative for a signal (``built``) or ``128 + N``.

    ``built``: ``exe`` is a program the runner built in the same run directory (``built_problem``), run with no
    environment of the caller's; otherwise one of the wrapped programs, with cocotb's settings."""
    owner = (int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    seat = _seat()
    if seat.pw_uid in owner or owner[0] == 0:
        raise Refused(f"{SEAT}: the caller must be the runner, not uid {owner[0]}")
    bad = [pair.split("=", 1)[0] for pair in env if built or not KEEP_ENV.match(pair.split("=", 1)[0])
           or SECRET.search(pair.split("=", 1)[0])]
    if bad:
        raise Refused(f"{SEAT}: refusing to pass {', '.join(bad)}")
    if not built and exe not in installed_exes():
        raise Refused(f"{SEAT}: {exe} is not a program this account runs")
    STATE.mkdir(mode=0o700, exist_ok=True)
    stop_seat(seat.pw_uid)  # a run left behind by a stopped step, so it frees the lock
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cleanup()
        where = Path(os.path.realpath(cwd))
        problem = run_dir_problem(where, owner[0])
        if problem:
            raise Refused(f"{SEAT}: {problem}; {exe} runs only in a run directory (nothing ran)")
        if built:
            exe = os.path.realpath(exe)
            problem = built_problem(Path(exe), where, owner[0])
            if problem:
                raise Refused(f"{SEAT}: {problem}; only a program the runner built in this run runs (nothing ran)")
        grants = grants_for(where)
        _save_grants({"owner": list(owner), "paths": grants})  # recorded first, so a crash leaves them to cleanup
        for path, mode in grants:
            subprocess.run(["setfacl", "-m", f"u:{SEAT}:{mode}", "--", path], check=True)
        parent = os.getppid()
        os.umask(0o022)
        proc = subprocess.Popen(["/usr/bin/setpriv", f"--reuid={seat.pw_uid}", f"--regid={seat.pw_gid}",
                                 "--clear-groups", "--no-new-privs", "--inh-caps=-all", "--",
                                 "/usr/bin/env", "-i", *BASE_ENV, *env, exe, *args], cwd=where)
        stop = []

        def forward(signum, _frame):
            stop.append(signum)

        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, forward)
        while proc.poll() is None:
            if stop or os.getppid() != parent:  # stopped, or sudo was killed (eda._stop_tree): end the run
                stop_seat(seat.pw_uid)
            time.sleep(0.05)
        cleanup()
    code = proc.returncode
    return code if built or code >= 0 else 128 - code


def installed_exes() -> list[str]:
    try:
        return json.loads((HOME / "exes.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def others_writable(path: str) -> bool:
    """Whether any account may write ``path`` by its mode: a world-writable folder with the sticky bit (``/tmp``)
    lets others add files but not replace the runner's, so it is not counted."""
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not info.st_mode & stat.S_IWOTH:
        return False
    return not (stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX)


def harden(trees: Sequence[str], folders: Sequence[str]) -> list[str]:
    """Take write access from other accounts: everything in each of ``trees``, and each of ``folders`` with what is
    directly in it. GitHub's hosted runner makes its tool cache (the Python the package is installed in, with its
    ``site-packages`` and console scripts) writable by every account; seat code could otherwise replace the judge's
    code or a tool a gate runs. Returns what it changed."""
    changed = []

    def fix(path: str) -> None:
        if others_writable(path):
            os.chmod(path, stat.S_IMODE(os.lstat(path).st_mode) & ~stat.S_IWOTH)
            changed.append(path)

    for tree in trees:
        if not os.path.isdir(tree):
            continue
        fix(tree)
        for top, dirs, files in os.walk(tree, followlinks=False):
            for name in [*dirs, *files]:
                fix(os.path.join(top, name))
    for folder in folders:
        if os.path.isdir(folder) and not os.path.islink(folder):
            fix(folder)
            for name in os.listdir(folder):
                fix(os.path.join(folder, name))
    return changed


def install(source: Path, trees: Sequence[str] = (), folders: Sequence[str] = ()) -> None:
    """Make the account and the wrappers, and take write access to ``trees`` and ``folders`` from other accounts.
    Fails unless the kernel guards against link tricks in shared folders."""
    for name, want in SYSCTLS.items():
        have = Path("/proc/sys", name).read_text().strip()
        if have != want:
            raise Refused(f"{name} is {have}, not {want}")
    for tool in ("setfacl", "setpriv"):
        if shutil.which(tool) is None:
            raise Refused(f"{tool} is not installed")
    try:
        _seat()
    except KeyError:
        subprocess.run(["useradd", "--system", "--user-group", "--no-create-home", "--home-dir", "/nonexistent",
                        "--shell", "/usr/sbin/nologin", SEAT], check=True)
    subprocess.run(["passwd", "--lock", SEAT], check=True, stdout=subprocess.DEVNULL)
    seat = _seat()
    groups = subprocess.run(["id", "-nG", SEAT], check=True, capture_output=True, text=True).stdout.split()
    if groups != [SEAT]:
        raise Refused(f"{SEAT} is in groups {groups}, not only its own")
    exes = []
    BIN.mkdir(parents=True, exist_ok=True)
    for name in WRAPPED:
        real = shutil.which(name, path=os.defpath + ":/usr/local/bin")
        if real is None:
            raise Refused(f"{name} is not installed")
        exes.append(str(Path(real).resolve()))
        (BIN / name).write_text(wrapper_text(exes[-1]), encoding="utf-8")
    EXEC.write_text(exec_wrapper_text(), encoding="utf-8")
    shutil.copyfile(source, INSTALLED)
    (HOME / "exes.json").write_text(json.dumps(exes), encoding="utf-8")
    for path in (HOME, BIN, *(BIN / n for n in WRAPPED), EXEC):
        os.chown(path, 0, 0)
        os.chmod(path, 0o755)
    for path in (INSTALLED, HOME / "exes.json"):
        os.chown(path, 0, 0)
        os.chmod(path, 0o644)
    STATE.mkdir(mode=0o700, exist_ok=True)
    changed = harden(trees, folders)
    print(f"{SEAT}: took write access from other accounts on {len(changed)} paths in {', '.join(trees)} and the "
          f"folders on PATH")
    print(f"{SEAT}: uid {seat.pw_uid}, groups {groups}; {', '.join(f'{BIN / n} runs {e}' for n, e in zip(WRAPPED, exes))}; "
          f"{EXEC} runs what fw.test builds")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run seat code in the live evaluation as an account of its own.")
    sub = parser.add_subparsers(dest="mode", required=True)
    setup = sub.add_parser("install")
    setup.add_argument("--harden-tree", action="append", default=[], help="a tree other accounts may not write")
    setup.add_argument("--harden-path", default="", help="a PATH whose folders other accounts may not write")
    wrap = sub.add_parser("wrap")
    wrap.add_argument("exe")
    wrap.add_argument("args", nargs=argparse.REMAINDER)
    built = sub.add_parser("exec")
    built.add_argument("args", nargs=argparse.REMAINDER)
    one = sub.add_parser("run")
    one.add_argument("--cwd", required=True)
    one.add_argument("--exe", required=True)
    one.add_argument("--env", action="append", default=[])
    one.add_argument("args", nargs=argparse.REMAINDER)
    run_built = sub.add_parser("run-built")
    run_built.add_argument("--cwd", required=True)
    run_built.add_argument("--exe", required=True)
    run_built.add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("cleanup")
    args = parser.parse_args(argv)
    rest = args.args[1:] if getattr(args, "args", [])[:1] == ["--"] else getattr(args, "args", [])
    try:
        if args.mode == "wrap":
            command = wrap_argv(args.exe, rest, os.getcwd(), os.environ)
            os.execv(command[0], command)
        if args.mode == "exec":
            if len(rest) < 2:
                raise Refused(f"{EXEC_NAME}: give the seat's folder and the program to run (nothing ran)")
            command = exec_argv(rest[0], rest[1], rest[2:])
            os.execv(command[0], command)
        if os.geteuid() != 0:
            raise Refused(f"{args.mode} runs as root")
        if args.mode == "install":
            install(Path(__file__).resolve(), args.harden_tree,
                    [f for f in args.harden_path.split(os.pathsep) if f and f != str(BIN)])
            return 0
        if args.mode == "cleanup":
            cleanup()
            return 0
        if args.mode == "run-built":
            return passed_on(run(args.cwd, args.exe, [], rest, built=True))
        return run(args.cwd, args.exe, args.env, rest)
    except Refused as refused:
        print(refused, file=sys.stderr, flush=True)
        return 126


if __name__ == "__main__":
    sys.exit(main())
