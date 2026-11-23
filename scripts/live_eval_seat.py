"""Seat code in the live evaluation runs as an account of its own (gates WF9 and WF17; docs/LIVE_EVAL_EVIDENCE.md, 6).

GitHub's runner user has passwordless sudo, owns the checkout, the installed package and the records, and its
``nirmaan`` process holds the plan token, which any process of the same user can read in ``/proc/<pid>/environ``.
A cocotb test module is code by design (docs/GATE_INPUTS.md, section 4), and cocotb runs it inside ``vvp``. So in
the live evaluation's jobs ``vvp`` is a wrapper that runs the real ``vvp`` as ``nirmaan-seat``: a system account with
no password, no sudo rule, no group but its own, ``no_new_privs`` set (so no setuid program, sudo included, gives
it more), and an environment holding only cocotb's own settings. It may write only the run's own directory; every
other grant is taken back when the run ends. The harness code is unchanged: the wrapper is first on ``PATH``.

The tools that read seat-written Verilog run the same way (gates ET2 to ET4 of
``council/records/2026-11-22-eda-tools-seat-account.md``): ``iverilog``, ``yosys``, ``sby`` (and with it the Yosys and
the solver it starts), ``eqy`` (and the Yosys, SBY and solvers it starts; gate W2C3 of
``council/records/2026-11-23-wave-2-close-meeting-1.md``), and ``verilator`` when it lints (``--lint-only``) or builds
the coverage run's model (``--coverage-line``, which only ``coverage.read`` passes; gate W2C4). Every other Verilator
model build (the simulator build, the co-simulation builds of ``fw.test`` and ``regmap.verify``) stays with the runner
by that rule (``as_runner``; decision 6 of the ET record; gate ET9 waits on those builds). Such a tool reads its inputs where the
harness keeps them, in the eval sandbox beside files the account may not read, so each run gets a view of its own:
the program runs in a mount namespace of its own in which every ``/tmp/nirmaan-*`` folder holding one of the run's
input files is replaced by an empty folder that holds only those input files, each at its own path and read only, and
the run's own directory. A link of the runner's beside an input whose text is exactly another input's path (M68's
``beside``: an approved file linked beside the setup that names it) is in the view too, as that input's own file, read
only (``beside_links``); so the account reads no file it was not given. The harness names both in the step's environment (``RUN_DIR_ENV``, ``INPUTS_ENV``, set by
``nirmaan.integrations.eda``); the root helper refuses an input that is not a regular file of the runner's inside a
``/tmp/nirmaan-*`` folder the runner made, reached through no link, so no file outside those folders (none of the
checkout) is ever an input. What the account may read elsewhere, outside the folders its view replaces, depends on file
modes and the ``--deny-read`` entries below, and is not claimed beyond the targets the reach test probes. Which files of
those folders are inputs is the harness's naming: a file a setup's ``[files]`` names is an input only when it is the
run's own, inside the setup's folder or one of the run's sources (``eda.own_file``, gate ET17 of the ET record's third
addendum), whether or not the screen ran, so a setup's ``[files]`` makes no file outside the setup's folder an input
but the run's sources.

``fw.test`` runs the co-simulation it builds (the seat's C linked with the harness, M90) by path, not through
``PATH``, so it has a wrapper of its own: where ``nirmaan-seat-exec`` is on ``PATH``, ``fw.test`` runs the built
program through it, in a folder of its own inside the run's directory (``nirmaan.integrations.firmware``). That runs
as the same account, with ``no_new_privs`` and an empty environment; the program must be one the runner built in the
same run directory.

``coverage.read`` runs the model it built from seat HDL by path too, so it has a wrapper of its own (gate W2C4):
where the job names the wrappers, the harness starts that program as ``nirmaan-seat-model RUN_DIR PROGRAM ARGS``
(``nirmaan.integrations.eda.seat_model``). That runs as the same account, with ``no_new_privs`` and an empty
environment, in a view of its own that holds the run's own directory and nothing else of the run folders; the program
must be one the runner built in that run directory.

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
- ``wrap`` keeps a Verilator model build with the runner (``as_runner``): it runs the real program, as the caller,
  with the caller's environment, as if the wrapper were not there.
- ``run`` (as root, through sudo): stop any seat process left over, give the seat account the run's directory (and
  read access to each input file other accounts may not read by its mode), run ``EXE`` as the seat account in a view
  of its own (``enter``), then ``cleanup``.
- ``enter`` (as root, from ``run``): make the run's own mount namespace and its view, then run the command it is
  given (``setpriv``, which drops to the seat account) in the run's folder.
- ``model RUN_DIR EXE ARGS`` (as the runner, from ``nirmaan-seat-model``): pass nothing of the environment, then
  ``sudo`` to ``run-model``.
- ``run-model`` (as root, through sudo): as ``run-built``, in a view of the run's own directory (``enter``), the
  program inside it.
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
import ctypes
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
#: The programs that run seat code, wrapped by name. cocotb runs a test module inside ``vvp``; the others read
#: seat-written Verilog (gate ET2 of council/records/2026-11-22-eda-tools-seat-account.md; ``eqy``, gate W2C3 of
#: council/records/2026-11-23-wave-2-close-meeting-1.md).
WRAPPED = ("vvp", "iverilog", "verilator", "yosys", "sby", "eqy")
#: Where ``install`` looks for each wrapped program: the system's folders, then the OSS CAD Suite the live evaluation's
#: tool action unpacks, root's, outside the runner's temporary folder, which the seat account may not read.
TOOL_PATH = os.defpath + ":/usr/local/bin:/opt/oss-cad-suite/bin"
#: The step's environment names the run's own directory and its input files (``nirmaan.integrations.eda``).
RUN_DIR_ENV = "NIRMAAN_SEAT_RUN_DIR"
INPUTS_ENV = "NIRMAAN_SEAT_INPUTS"
#: The wrapper ``fw.test`` runs its built co-simulation through (``nirmaan.integrations.firmware.SEAT_EXEC``).
EXEC_NAME = "nirmaan-seat-exec"
EXEC = BIN / EXEC_NAME
#: The wrapper ``coverage.read`` runs the model it built through (``nirmaan.integrations.eda.SEAT_MODEL``; gate W2C4).
MODEL_NAME = "nirmaan-seat-model"
MODEL = BIN / MODEL_NAME
#: The Verilator runs that are the seat account's: a lint, and the coverage run's model build (gate W2C4).
VERILATOR_SEAT_FLAGS = frozenset({"--lint-only", "--coverage-line"})
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


def as_runner(exe: str, args: Sequence[str]) -> bool:
    """Whether this command stays with the runner: a Verilator run that is neither a lint nor the coverage run's model
    build (``--coverage-line``, gate W2C4), so one of the other model builds (decision 6 of
    council/records/2026-11-22-eda-tools-seat-account.md; gate ET9). Every other wrapped command runs as the seat
    account."""
    return Path(exe).name == "verilator" and not VERILATOR_SEAT_FLAGS & set(args)


def run_inputs(env: Mapping[str, str]) -> tuple[str | None, list[str]]:
    """The run's own directory and its input files, as the harness names them in the step's environment."""
    run_dir = env.get(RUN_DIR_ENV) or None
    try:
        inputs = json.loads(env.get(INPUTS_ENV) or "[]")
    except ValueError:
        raise Refused(f"{SEAT}: {INPUTS_ENV} is not a JSON list (nothing ran)") from None
    if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
        raise Refused(f"{SEAT}: {INPUTS_ENV} is not a list of paths (nothing ran)")
    return run_dir, inputs


def wrap_argv(exe: str, args: Sequence[str], cwd: str, env: Mapping[str, str], script: str = str(INSTALLED)) -> list[str]:
    """The sudo command that runs ``exe`` as the seat account in ``cwd``. Nothing is given to a shell."""
    argv = ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", script, "run", "--cwd", cwd, "--exe", exe]
    for pair in kept_env(env):
        argv += ["--env", pair]
    run_dir, inputs = run_inputs(env)
    if run_dir:
        argv += ["--run-dir", run_dir]
    for path in inputs:
        argv += ["--input", path]
    return [*argv, "--", *args]


def wrapper_text(exe: str, script: str = str(INSTALLED)) -> str:
    return (f"#!/bin/sh\n# Runs {exe} as {SEAT} (scripts/live_eval_seat.py; docs/LIVE_EVAL_EVIDENCE.md, section 6).\n"
            f"exec /usr/bin/python3 -I {script} wrap {exe} -- \"$@\"\n")


def exec_argv(where: str, exe: str, args: Sequence[str], script: str = str(INSTALLED)) -> list[str]:
    """The sudo command that runs a built program ``exe`` as the seat account in ``where``, with no environment."""
    return ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", script, "run-built", "--cwd", where, "--exe", exe, "--",
            *args]


def model_argv(run_dir: str, exe: str, args: Sequence[str], script: str = str(INSTALLED)) -> list[str]:
    """The sudo command that runs a model the run built, ``exe``, as the seat account in the run's directory ``run_dir``,
    with no environment and a view of that directory only (gate W2C4)."""
    return ["/usr/bin/sudo", "-n", "/usr/bin/python3", "-I", script, "run-model", "--cwd", run_dir, "--run-dir", run_dir,
            "--exe", exe, "--", *args]


def model_wrapper_text(script: str = str(INSTALLED)) -> str:
    return (f"#!/bin/sh\n# Runs RUN_DIR EXE ARGS: a model coverage.read built from seat HDL, as {SEAT} "
            f"(scripts/live_eval_seat.py; docs/LIVE_EVAL_EVIDENCE.md, section 6).\n"
            f"exec /usr/bin/python3 -I {script} model -- \"$@\"\n")


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


def input_problem(path: str, owner: int, root: Path = RUN_ROOT) -> str | None:
    """Why ``path`` is not an input file the runner made for this run, or None: it must be written as an absolute,
    normal path, inside a ``root/nirmaan-*`` folder, every folder from there down to it the runner's own and not a link,
    and itself a regular file of the runner's with no other name (one link), reached through no link."""
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        return f"{path} is not an absolute, normal path"
    try:
        rel = Path(path).relative_to(root)
    except ValueError:
        return f"{path} is not inside {root}"
    if len(rel.parts) < 2 or not rel.parts[0].startswith(RUN_PREFIX):
        return f"{path} is not inside a {root}/{RUN_PREFIX}* folder"
    here = root
    for part in rel.parts:
        here = here / part
        try:
            info = os.lstat(here)
        except FileNotFoundError:
            return f"{here} does not exist"
        if stat.S_ISLNK(info.st_mode):
            return f"{here} is a link"
        if info.st_uid != owner:
            return f"{here} does not belong to the runner (uid {info.st_uid}, not {owner})"
        if here != Path(path) and not stat.S_ISDIR(info.st_mode):
            return f"{here} is not a directory"
    if not stat.S_ISREG(info.st_mode):
        return f"{path} is not a regular file"
    if info.st_nlink != 1:
        return f"{path} has {info.st_nlink} names"
    return None


def top_of(path: Path, root: Path = RUN_ROOT) -> Path:
    """The ``root/nirmaan-*`` folder ``path`` is in."""
    return root / path.relative_to(root).parts[0]


def beside_links(run_dir: Path, inputs: Sequence[str], owner: int) -> dict[str, str]:
    """The links the view also holds, each with the input it names: in each folder that holds an input outside the
    run's own directory, a link of the runner's whose text is exactly the path of one of the inputs. That is the link
    M68's ``beside`` places (``nirmaan.runtime.model._place_beside``): an approved file, linked under its own name beside
    a setup that names its files relative to itself (``sby`` opens a ``[files]`` name in the setup's folder). The
    harness names the file the link leads to (``nirmaan.integrations.eda.seat_inputs``), never the link. In the view the
    link's path holds that input's own file, so the account reads no file it was not given, under one more name. Every
    other link, and a link of another account's, stays out of the view. The inputs are already checked
    (``input_problem``), so each folder is one the runner made, reached through no link."""
    named = set(inputs)
    folders = dict.fromkeys(Path(p).parent for p in inputs if not Path(p).is_relative_to(run_dir))
    links = {}
    for folder in folders:
        for entry in sorted(os.scandir(folder), key=lambda e: e.name):
            if not entry.is_symlink() or entry.stat(follow_symlinks=False).st_uid != owner:
                continue
            target = os.readlink(entry.path)
            if target in named:
                links[entry.path] = target
    return links


def view_plan(run_dir: Path, cwd: Path, inputs: Sequence[str], root: Path = RUN_ROOT, owner: int | None = None) -> dict:
    """What the run sees (``enter``): each top folder that holds an input outside the run's own directory, or the run's
    own directory itself, is replaced by an empty one holding only those inputs, the links beside them that name one of
    them (``beside_links``, looked for only when ``owner``, the runner, is given) and that directory; and the folder the
    run starts in. All are already checked (``run_dir_problem``, ``input_problem``). The folder must be the run's own
    directory or one inside it, or a folder on the way to one of the inputs (``sby`` starts in its setup's folder)."""
    outside = [Path(p) for p in dict.fromkeys(inputs) if not Path(p).is_relative_to(run_dir)]
    mask = sorted({str(top_of(p, root)) for p in outside} | ({str(top_of(run_dir, root))}
                                                               if top_of(run_dir, root) != run_dir else set()))
    shown = [str(p) for p in outside]
    rebind = str(run_dir) if top_of(run_dir, root) != run_dir else None
    on_way = any(p.is_relative_to(cwd) and cwd.is_relative_to(top_of(p, root)) for p in outside)
    if not (cwd.is_relative_to(run_dir) or on_way):
        raise Refused(f"{SEAT}: {cwd} is neither the run's directory nor a folder of its inputs (nothing ran)")
    links = beside_links(run_dir, inputs, owner) if owner is not None else {}
    held = dict.fromkeys([*shown, *links.values(), *([rebind] if rebind else [])])
    return {"mask": mask, "files": shown, "links": links, "run_dir": rebind, "cwd": str(cwd),
            "ids": {p: list(_identity(p)) for p in held}}


def _identity(path: str) -> tuple[int, int]:
    info = os.lstat(path)
    return info.st_dev, info.st_ino


MS_RDONLY, MS_NOSUID, MS_NODEV, MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 1, 2, 4, 32, 4096, 16384, 1 << 18


def _mount(source: str | None, target: str, fstype: str | None, flags: int, data: str | None = None) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p] * 3 + [ctypes.c_ulong, ctypes.c_char_p]

    def enc(text: str | None) -> bytes | None:
        return text.encode() if text is not None else None

    if libc.mount(enc(source), enc(target), enc(fstype), flags, enc(data)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, f"mount {source} on {target}: {os.strerror(err)}")


def _placeholder(path: str) -> None:
    """An empty file at ``path`` in the view's hidden folder (with the folders above it), for a file to be bound on."""
    os.makedirs(os.path.dirname(path), mode=0o755, exist_ok=True)
    os.close(os.open(path, os.O_CREAT | os.O_WRONLY | os.O_CLOEXEC, 0o644))


def _bind_read_only(fd: int, path: str) -> None:
    _mount(f"/proc/self/fd/{fd}", path, None, MS_BIND)
    _mount(None, path, None, MS_REMOUNT | MS_BIND | MS_RDONLY | MS_NOSUID | MS_NODEV)


def enter(plan: dict, command: Sequence[str]) -> int:
    """As root: give this process a mount namespace of its own holding the run's view (``view_plan``), go to the run's
    folder and run ``command`` in it (``setpriv``, which drops to the seat account). Fails closed: a file that is not
    the one checked, or a mount that fails, stops it before the command runs. A link of ``beside_links`` is placed as
    the input it names, bound from that input's descriptor held since the check; the link itself is never followed."""
    os.unshare(os.CLONE_NEWNS)
    _mount(None, "/", None, MS_REC | MS_PRIVATE)
    held = {}
    for path, (dev, ino) in plan["ids"].items():  # held open before the view hides them
        fd = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (dev, ino):
            raise Refused(f"{SEAT}: {path} changed after it was checked (nothing ran)")
        held[path] = fd
    os.umask(0o022)
    for top in plan["mask"]:
        _mount("nirmaan-seat", top, "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755,size=1m")
    for path in plan["files"]:
        _placeholder(path)
        _bind_read_only(held[path], path)
    for path, target in plan["links"].items():
        _placeholder(path)
        _bind_read_only(held[target], path)
    if plan["run_dir"]:
        os.makedirs(plan["run_dir"], mode=0o755, exist_ok=True)
        _mount(f"/proc/self/fd/{held[plan['run_dir']]}", plan["run_dir"], None, MS_BIND)
    for fd in held.values():
        os.close(fd)
    os.chdir(plan["cwd"])
    os.execv(command[0], list(command))
    return 126  # not reached


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


def run(cwd: str, exe: str, env: Sequence[str], args: Sequence[str], built: bool = False, run_dir: str | None = None,
        inputs: Sequence[str] = (), view: bool = False) -> int:
    """Run ``exe`` as the seat account in ``cwd``; its exit status, negative for a signal (``built``) or ``128 + N``.

    ``built``: ``exe`` is a program the runner built in the same run directory (``built_problem``), run with no
    environment of the caller's; otherwise one of the wrapped programs, with cocotb's settings, in a view of its own
    (``view_plan``): ``run_dir`` (``cwd`` when not given) and the ``inputs``, nothing else of the run folders.
    ``view`` (a built model, gate W2C4): the built program too runs in a view of its own, of ``run_dir``, and must be
    inside ``run_dir``."""
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
        start = Path(os.path.realpath(cwd))
        viewed = view or not built
        where = Path(os.path.realpath(run_dir)) if run_dir and viewed else start
        problem = run_dir_problem(where, owner[0])
        if problem:
            raise Refused(f"{SEAT}: {problem}; {exe} runs only in a run directory (nothing ran)")
        if built:
            exe = os.path.realpath(exe)
            problem = built_problem(Path(exe), where, owner[0])
            if not problem and view and not Path(exe).is_relative_to(where):
                problem = f"{exe} is not inside the run's directory {where}"
            if problem:
                raise Refused(f"{SEAT}: {problem}; only a program the runner built in this run runs (nothing ran)")
        bad = [why for why in (input_problem(p, owner[0]) for p in inputs) if why]
        if bad:
            raise Refused(f"{SEAT}: {'; '.join(bad)}; a tool reads only files the runner made for this run (nothing "
                          f"ran)")
        plan = view_plan(where, start, inputs, owner=owner[0]) if viewed else None
        grants = grants_for(where) + [(p, "r--") for p in dict.fromkeys(inputs)
                                      if not os.lstat(p).st_mode & stat.S_IROTH]
        _save_grants({"owner": list(owner), "paths": grants})  # recorded first, so a crash leaves them to cleanup
        for path, mode in grants:
            subprocess.run(["setfacl", "-m", f"u:{SEAT}:{mode}", "--", path], check=True)
        parent = os.getppid()
        os.umask(0o022)
        command = ["/usr/bin/setpriv", f"--reuid={seat.pw_uid}", f"--regid={seat.pw_gid}", "--clear-groups",
                   "--no-new-privs", "--inh-caps=-all", "--", "/usr/bin/env", "-i", *BASE_ENV, *env, exe, *args]
        if plan is None:
            proc = subprocess.Popen(command, cwd=where)
        else:
            proc = subprocess.Popen(enter_argv(plan, command), cwd="/")
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


def enter_argv(plan: dict, command: Sequence[str], script: str = str(INSTALLED)) -> list[str]:
    """The root command that makes the run's view and runs ``command`` in it (``enter``)."""
    return ["/usr/bin/python3", "-I", script, "enter", "--plan", json.dumps(plan), "--", *command]


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
        real = shutil.which(name, path=TOOL_PATH)
        if real is None:
            raise Refused(f"{name} is not installed")
        exes.append(str(Path(real).resolve()))
        (BIN / name).write_text(wrapper_text(exes[-1]), encoding="utf-8")
    EXEC.write_text(exec_wrapper_text(), encoding="utf-8")
    MODEL.write_text(model_wrapper_text(), encoding="utf-8")
    shutil.copyfile(source, INSTALLED)
    (HOME / "exes.json").write_text(json.dumps(exes), encoding="utf-8")
    for path in (HOME, BIN, *(BIN / n for n in WRAPPED), EXEC, MODEL):
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
    print(f"{SEAT}: uid {seat.pw_uid}, groups {groups}; {', '.join(f'{BIN / n} runs {e}' for n, e in zip(WRAPPED, exes))}; "
          f"{EXEC} runs what fw.test builds; {MODEL} runs the model coverage.read builds")


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
    built = sub.add_parser("exec")
    built.add_argument("args", nargs=argparse.REMAINDER)
    model = sub.add_parser("model")
    model.add_argument("args", nargs=argparse.REMAINDER)
    one = sub.add_parser("run")
    one.add_argument("--cwd", required=True)
    one.add_argument("--exe", required=True)
    one.add_argument("--env", action="append", default=[])
    one.add_argument("--run-dir", default=None)
    one.add_argument("--input", action="append", default=[])
    one.add_argument("args", nargs=argparse.REMAINDER)
    view = sub.add_parser("enter")
    view.add_argument("--plan", required=True)
    view.add_argument("args", nargs=argparse.REMAINDER)
    run_built = sub.add_parser("run-built")
    run_built.add_argument("--cwd", required=True)
    run_built.add_argument("--exe", required=True)
    run_built.add_argument("args", nargs=argparse.REMAINDER)
    run_model = sub.add_parser("run-model")
    run_model.add_argument("--cwd", required=True)
    run_model.add_argument("--run-dir", required=True)
    run_model.add_argument("--exe", required=True)
    run_model.add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("cleanup")
    args = parser.parse_args(argv)
    rest = args.args[1:] if getattr(args, "args", [])[:1] == ["--"] else getattr(args, "args", [])
    try:
        if args.mode == "wrap":
            if as_runner(args.exe, rest):  # a Verilator model build: the runner's, as without the wrapper
                os.execv(args.exe, [args.exe, *rest])
            command = wrap_argv(args.exe, rest, os.getcwd(), os.environ)
            os.execv(command[0], command)
        if args.mode == "exec":
            if len(rest) < 2:
                raise Refused(f"{EXEC_NAME}: give the seat's folder and the program to run (nothing ran)")
            command = exec_argv(rest[0], rest[1], rest[2:])
            os.execv(command[0], command)
        if args.mode == "model":
            if len(rest) < 2:
                raise Refused(f"{MODEL_NAME}: give the run's directory and the program to run (nothing ran)")
            command = model_argv(rest[0], rest[1], rest[2:])
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
        if args.mode == "run-built":
            return passed_on(run(args.cwd, args.exe, [], rest, built=True))
        if args.mode == "run-model":
            return passed_on(run(args.cwd, args.exe, [], rest, built=True, run_dir=args.run_dir, view=True))
        if args.mode == "enter":
            try:
                return enter(json.loads(args.plan), rest)
            except OSError as exc:  # a mount, a folder or the command: nothing ran as the seat account
                raise Refused(f"{SEAT}: the run's view could not be made: {exc} (nothing ran)") from None
        return run(args.cwd, args.exe, args.env, rest, run_dir=args.run_dir, inputs=args.input)
    except Refused as refused:
        print(refused, file=sys.stderr, flush=True)
        return 126


if __name__ == "__main__":
    sys.exit(main())
