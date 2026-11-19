"""Seat code in the live evaluation runs as an account of its own (gates WF9 and WF17; docs/LIVE_EVAL_EVIDENCE.md, 6).

GitHub's runner user has passwordless sudo, owns the checkout, the installed package and the records, and its
``nirmaan`` process holds the plan token, which any process of the same user can read in ``/proc/<pid>/environ``.
A cocotb test module is code by design (docs/GATE_INPUTS.md, section 4), and cocotb runs it inside ``vvp``. So in
the live evaluation's jobs ``vvp`` is a wrapper that runs the real ``vvp`` as ``nirmaan-seat``: a system account with
no password, no sudo rule, no group but its own, ``no_new_privs`` set (so no setuid program, sudo included, gives
it more), and an environment holding only cocotb's own settings. It may write only the run's own directory; every
other grant is taken back when the run ends. The harness code is unchanged: the wrapper is first on ``PATH``.

The account may not read what the judge keeps from it: ``install`` gives it an ACL entry with no permission on
each folder named by ``--deny-read`` (the workflow names the runner's home, the checkout and the runner's
temporary folder, so every reference answer, held-out test and mutant in the checkout), whatever the folders'
modes allow other accounts. And it has no network: every packet the account sends, IPv4 or IPv6, loopback
included, is stopped (``owner`` rules first in ``OUTPUT``): a TCP connection is refused at once with an ICMP
"prohibited" answer, and any other packet is dropped, so its send fails with EPERM. The
reach test (``scripts/live_eval_reach.py``) probes both.

Modes, each run by the workflow or by the wrapper:

- ``install`` (as root, from ``.github/actions/live-eval-seat``): make the account, copy this file to
  ``/opt/nirmaan-seat/seat.py`` (root's, so seat code cannot change it) and write the ``vvp`` wrapper beside it.
- ``wrap EXE ARGS`` (as the runner, from the wrapper): keep cocotb's settings from the environment and drop the
  rest, then ``sudo`` to ``run``.
- ``run`` (as root, through sudo): stop any seat process left over, give the seat account the run's directory, run
  ``EXE`` as the seat account, then ``cleanup``.
- ``cleanup`` (as root): stop every seat process, give every file the seat account made in a run directory back to
  the runner (a link or any other non-regular file it made there is removed first, so nothing the harness reads
  afterwards leads elsewhere), take back every grant, and remove what it left in the shared temporary folders.

``fw.build`` and ``fw.test`` run the seat's C by path, not through ``PATH``, so this does not reach them; a live
trial of a case that runs seat C is refused (``scripts/live_eval_ci.py``) until it does.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pwd
import re
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


def run(cwd: str, exe: str, env: Sequence[str], args: Sequence[str]) -> int:
    owner = (int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    seat = _seat()
    if seat.pw_uid in owner or owner[0] == 0:
        raise Refused(f"{SEAT}: the caller must be the runner, not uid {owner[0]}")
    bad = [pair.split("=", 1)[0] for pair in env if not KEEP_ENV.match(pair.split("=", 1)[0])
           or SECRET.search(pair.split("=", 1)[0])]
    if bad:
        raise Refused(f"{SEAT}: refusing to pass {', '.join(bad)}")
    if exe not in installed_exes():
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
    return 128 - code if code < 0 else code


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


#: The firewall programs whose ``OUTPUT`` chain drops the seat account's packets.
FIREWALLS = ("iptables", "ip6tables")


def deny_read_argv(path: str) -> list[str]:
    """The ACL entry that takes every permission on ``path`` from the seat account, whatever the mode allows."""
    return ["setfacl", "-m", f"u:{SEAT}:---", "--", path]


def network_rules(uid: int, tool: str) -> list[list[str]]:
    """The ``OUTPUT`` rules, in order, that stop every packet of ``uid``: a TCP connection is refused at once with an
    ICMP "prohibited" answer (a dropped one would only time out, which proves nothing), and every other packet is
    dropped, so its send fails with EPERM."""
    prohibited = "icmp6-adm-prohibited" if tool == "ip6tables" else "icmp-host-prohibited"
    owner = ["-m", "owner", "--uid-owner", str(uid)]
    return [["OUTPUT", "-p", "tcp", *owner, "-j", "REJECT", "--reject-with", prohibited],
            ["OUTPUT", *owner, "-j", "DROP"]]


def deny(uid: int, unreadable: Sequence[str]) -> None:
    """Take read access to each folder of ``unreadable`` and the network from the seat account. Fails closed: a
    folder that is not one, or a rule that does not hold afterwards, stops the install."""
    for path in unreadable:
        if os.path.islink(path) or not os.path.isdir(path):
            raise Refused(f"{path} is not a folder, so the account's read access to it cannot be taken")
        subprocess.run(deny_read_argv(path), check=True)
    for tool in FIREWALLS:
        if shutil.which(tool) is None:
            raise Refused(f"{tool} is not installed")
        rules = network_rules(uid, tool)
        for position, rule in enumerate(rules, start=1):
            if subprocess.run([tool, "-C", *rule], capture_output=True).returncode != 0:
                subprocess.run([tool, "-I", rule[0], str(position), *rule[1:]], check=True)
        for rule in rules:
            subprocess.run([tool, "-C", *rule], check=True)


def install(source: Path, trees: Sequence[str] = (), folders: Sequence[str] = (),
            unreadable: Sequence[str] = ()) -> None:
    """Make the account and the wrappers, take write access to ``trees`` and ``folders`` from other accounts, and
    take read access to ``unreadable`` and the network from the seat account (``deny``). Fails unless the kernel
    guards against link tricks in shared folders."""
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
    shutil.copyfile(source, INSTALLED)
    (HOME / "exes.json").write_text(json.dumps(exes), encoding="utf-8")
    for path in (HOME, BIN, *(BIN / n for n in WRAPPED)):
        os.chown(path, 0, 0)
        os.chmod(path, 0o755)
    for path in (INSTALLED, HOME / "exes.json"):
        os.chown(path, 0, 0)
        os.chmod(path, 0o644)
    STATE.mkdir(mode=0o700, exist_ok=True)
    changed = harden(trees, folders)
    print(f"{SEAT}: took write access from other accounts on {len(changed)} paths in {', '.join(trees)} and the "
          f"folders on PATH")
    deny(seat.pw_uid, unreadable)
    print(f"{SEAT}: no read access to {', '.join(unreadable) or 'no folder'}; every packet it sends is stopped")
    print(f"{SEAT}: uid {seat.pw_uid}, groups {groups}; {', '.join(f'{BIN / n} runs {e}' for n, e in zip(WRAPPED, exes))}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run seat code in the live evaluation as an account of its own.")
    sub = parser.add_subparsers(dest="mode", required=True)
    setup = sub.add_parser("install")
    setup.add_argument("--harden-tree", action="append", default=[], help="a tree other accounts may not write")
    setup.add_argument("--harden-path", default="", help="a PATH whose folders other accounts may not write")
    setup.add_argument("--deny-read", action="append", default=[], help="a folder the seat account may not read")
    wrap = sub.add_parser("wrap")
    wrap.add_argument("exe")
    wrap.add_argument("args", nargs=argparse.REMAINDER)
    one = sub.add_parser("run")
    one.add_argument("--cwd", required=True)
    one.add_argument("--exe", required=True)
    one.add_argument("--env", action="append", default=[])
    one.add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("cleanup")
    args = parser.parse_args(argv)
    rest = args.args[1:] if getattr(args, "args", [])[:1] == ["--"] else getattr(args, "args", [])
    try:
        if args.mode == "wrap":
            command = wrap_argv(args.exe, rest, os.getcwd(), os.environ)
            os.execv(command[0], command)
        if os.geteuid() != 0:
            raise Refused(f"{args.mode} runs as root")
        if args.mode == "install":
            install(Path(__file__).resolve(), args.harden_tree,
                    [f for f in args.harden_path.split(os.pathsep) if f and f != str(BIN)], args.deny_read)
            return 0
        if args.mode == "cleanup":
            cleanup()
            return 0
        return run(args.cwd, args.exe, args.env, rest)
    except Refused as refused:
        print(refused, file=sys.stderr, flush=True)
        return 126


if __name__ == "__main__":
    sys.exit(main())
