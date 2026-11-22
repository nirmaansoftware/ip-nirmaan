"""The reach test (gate WF17): what seat code can reach in this job, tried through the real cocotb path.

`.github/workflows/live-eval.yml` runs it in every job that runs seat code, after the seat account is made
(``scripts/live_eval_seat.py``) and before any trial or re-judge. It writes a cocotb test module whose tests try,
as seat code would, to:

- run as the runner, or with a group other than the seat account's own;
- run a command through ``sudo`` without a password;
- write to the checkout, the installed package (the ``nirmaan`` package, the Python it runs in, its
  ``site-packages`` and console script), any folder on ``PATH`` or any program a gate runs, the seat account's
  own wrapper, the records folder, the runner's temporary folder or the step's command files (``GITHUB_ENV``,
  ``GITHUB_OUTPUT``, ``GITHUB_PATH``);
- find a credential: two canary values this script puts in its own environment (one under a credential's name,
  which the M53 runner removes, one under a plain name, which only the seat account's empty environment keeps
  out), in its own environment or in ``/proc/<pid>/environ`` of any process, or in a file only the runner may
  read; or signal the harness;
- read what the judge keeps from the seat (READ probes): every reference answer, held-out case file and mutant
  the eval cases name, all in the checkout, a canary file this script writes into the checkout and into the
  runner's temporary folder (readable by every account by its mode, so only the account's own denial stops it),
  and a listing of the checkout, its ``.git``, the runner's home and its temporary folder;
- reach the network: a TCP connection out (IPv4 and IPv6), a TCP connection on the loopback address (IPv4 and IPv6),
  and a UDP packet to the local name server.

and one control, that it can write its own run directory. The module runs through ``simulator.run``'s cocotb
backend (``eda.execute``), so through the ``vvp`` the trials use. The test passes only when cocotb's verdict is
a pass and every probe test is in the results, passed: every probe denied. Otherwise it exits 1 and the job
stops before any trial.

``fw.test`` runs the program it builds from seat C through a wrapper of its own, ``nirmaan-seat-exec``, as the same
account (M90). Its credential test (``scripts/live_eval_fw_reach.py``) tries the same targets from compiled C through
``fw.test``, and the workflow runs it as a gate (``--require-denied``) for a whole-flow case.

The tools that read seat-written Verilog run as the same account (gates ET2 to ET4 of
``council/records/2026-11-22-eda-tools-seat-account.md``), and a second part of this test probes each through the
real backend, by ``PATH`` (``tool_reach``): Icarus through ``simulator.run``, Verilator through ``lint.run``, Yosys
through ``synth.run``, SBY (with the Yosys and the solver it starts) through ``formal.run`` and ``formal.cover``. It
runs in a process of its own whose real environment holds two canaries (one under a credential's name), so that
process stands for the parent that holds the token. For each tool:

- a control: seat files only the runner and the seat account may read (mode 0600, read by the seat account through
  the grant its run gets) pass the gate, so the tool read them; with the runner-only canary below denied through the
  same tool, its process is the seat account;
- three probes, each a seat file that includes one target by absolute path: a canary file in the checkout (readable by
  every account by its mode), a runner-only canary file (mode 0600, in a folder every account may enter), and the
  parent's ``/proc/<pid>/environ``. Each target exists and the runner can read it first, so a denial proves something.
  A probe is denied only when the run fails with the tool's own message that it could not open that target, and no
  canary value is in the run's log, summary or result file. The screen (``eda_guard``) refuses an include by absolute
  path, so these probes reach the tool with the screen bypassed inside this process only, and say so in their
  output.

And for the held-out checks' compile (decision 3, item 2): through ``simulator.run``, a seat file with a judge file
staged for the run as the held-out checks stage theirs (``nirmaan.evals.scorers``): the account reads that judge file,
and a canary placed beside it (readable by every account by its mode) is denied. Every result is written to
``--out`` as the tool reach record; the job stops before any trial unless every probe is denied and every control
passed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pwd
import secrets
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAT = "nirmaan-seat"
WRAPPER = Path("/opt/nirmaan-seat/bin/vvp")
#: The wrapper fw.test runs its built program through, beside ``WRAPPER`` (M90; scripts/live_eval_seat.py).
EXEC_NAME = "nirmaan-seat-exec"
#: Credential-named and plain-named canaries; neither may reach seat code.
CANARY_SECRET, CANARY_PLAIN = "CLAUDE_CODE_OAUTH_TOKEN", "NIRMAAN_REACH_CANARY"
#: The probe tests, by name; each must be in cocotb's results and pass.
PROBES = ("reach_identity", "reach_no_sudo", "reach_no_write", "reach_no_credential", "reach_no_signal",
          "reach_no_read", "reach_no_network", "reach_own_directory")
#: Where the network probe tries to go: (kind, address, port). Each is denied only on EPERM or EACCES, or, for TCP,
#: EHOSTUNREACH, the "prohibited" answer the seat account's rule gives at once (``scripts/live_eval_seat.py``; on the
#: loopback address nothing else gives it), and for IPv6 ENETUNREACH (no route at all). A timeout proves nothing.
#: IPv6 loopback (``::1``) has a route on every runner, so it is the target that shows the ``ip6tables`` rule itself.
NETWORK = (("tcp", "1.1.1.1", 443), ("tcp6", "2606:4700:4700::1111", 443), ("tcp", "127.0.0.1", 9),
           ("tcp6", "::1", 9), ("udp", "127.0.0.53", 53))
#: The programs gates run (eda.py backends) and the harness's own entry point.
TOOLS = ("nirmaan", "iverilog", "vvp", "verilator", "yosys", "sby", "yices-smt2", "make", "cc", "python", "python3",
         "git", "node", "npm")
DESIGN = "module reach_probe(input wire clk);\nendmodule\n"
#: The programs that run as the seat account, each wrapped first on ``PATH`` (``scripts/live_eval_seat.py``).
WRAPPED = ("vvp", "iverilog", "verilator", "yosys", "sby")
#: Gate ET3: each tool, the gate and backend it is probed through, and what it prints when it cannot open an include
#: (``{}`` is the target's path). Verilator says "File not found" for a file it may not read, and "Cannot find include
#: file" for one it cannot see.
TOOL_GATES = (("iverilog", "simulator.run", "icarus", ("Include file {} not found",)),
              ("verilator", "lint.run", "verilator-lint", ("Cannot find include file: '{}'", "File not found: {}")),
              ("yosys", "synth.run", "yosys", ("Can't open include file `{}'",)),
              ("sby", "formal.run", "symbiyosys", ("Can't open include file `{}'",)))
#: A seat file for each tool: (file name, top, text before the include, text after it).
TOOL_FILES = {
    "iverilog": ("reach_tool_sim.v", "reach_tool_sim", "module reach_tool_sim;\n",
                 "reg [8*64-1:0] nonce;\ninitial begin\n$display(\"REACH TOOL control __NONCE__\");\n"
                 "if ($value$plusargs(\"nirmaan_nonce=%s\", nonce)) $display(\"NIRMAAN-SIM %0s 1 passed, 0 failed\", "
                 "nonce);\n$finish;\nend\nendmodule\n"),
    "verilator": ("reach_tool_lint.v", "reach_tool_lint", "module reach_tool_lint;\n", "endmodule\n"),
    "yosys": ("reach_tool_synth.v", "reach_tool_synth", "module reach_tool_synth(input wire a, output wire y);\n",
              "assign y = a;\nendmodule\n"),
    "sby": ("reach_tool_formal.sv", "reach_tool_formal", "module reach_tool_formal(input wire clk);\n",
            "reg r = 1'b0;\nalways @(posedge clk) r <= !r;\nalways @(posedge clk) if (r) assert (r);\n"
            "always @(posedge clk) cover (r);\nendmodule\n"),
}
SBY_SETUP = ("[options]\nmode prove\n\n[engines]\nsmtbmc yices\n\n[script]\nread -formal reach_tool_formal.sv\n"
             "prep -top reach_tool_formal\n\n[files]\nreach_tool_formal.sv\n")

PROBE = r'''"""Reach probe (scripts/live_eval_reach.py): seat code trying what it must not do. Every test passes only on denial."""
import errno, json, os, pwd, subprocess
import cocotb

CONFIG = json.loads(__CONFIG__)
DENIED = (errno.EACCES, errno.EPERM, errno.EROFS)


def _say(ok, what, detail):
    print(f"REACH {'denied' if ok else 'NOT DENIED'}: {what}: {detail}", flush=True)
    return ok


def _write(path, create):
    """True when opening ``path`` for writing is refused by permission."""
    target = os.path.join(path, ".nirmaan-reach-" + CONFIG["nonce"]) if create else path
    flags = os.O_WRONLY | (os.O_CREAT | os.O_EXCL if create else os.O_APPEND)
    try:
        fd = os.open(target, flags, 0o644)
    except OSError as exc:
        return _say(exc.errno in DENIED, f"write {target}", f"{type(exc).__name__} errno {exc.errno}")
    os.close(fd)
    if create:
        os.unlink(target)
    return _say(False, f"write {target}", "opened for writing")


@cocotb.test()
async def reach_identity(dut):
    seat = pwd.getpwnam(CONFIG["seat"])
    ok = [_say(os.getuid() == os.geteuid() == seat.pw_uid, "uid", f"{os.getuid()} (seat {seat.pw_uid})"),
          _say(os.getuid() != CONFIG["runner_uid"], "not the runner", f"runner uid {CONFIG['runner_uid']}"),
          _say(set(os.getgroups()) <= {seat.pw_gid} and os.getgid() == seat.pw_gid, "groups",
               f"gid {os.getgid()}, groups {os.getgroups()}")]
    assert all(ok)


@cocotb.test()
async def reach_no_sudo(dut):
    ok = []
    for argv in (["sudo", "-n", "true"], ["sudo", "-n", "-u", CONFIG["runner"], "true"]):
        proc = subprocess.run(["/usr/bin/" + argv[0], *argv[1:]], capture_output=True, text=True)
        ok.append(_say(proc.returncode != 0, " ".join(argv), f"exit {proc.returncode} {proc.stderr.strip()[:120]}"))
    assert all(ok)


@cocotb.test()
async def reach_no_write(dut):
    ok = [_write(p, True) for p in CONFIG["create_in"]] + [_write(p, False) for p in CONFIG["append_to"]]
    assert ok and all(ok)


@cocotb.test()
async def reach_no_credential(dut):
    values = [v.encode() for v in CONFIG["canaries"]]
    ok = [_say(not any(v.decode() in x for v in values for x in os.environ.values()), "own environment",
               ", ".join(sorted(os.environ)))]
    harness = 0
    for pid in [p for p in os.listdir("/proc") if p.isdigit()]:
        try:
            with open(f"/proc/{pid}/environ", "rb") as f:
                data = f.read()
        except PermissionError:
            harness += int(pid) == CONFIG["harness_pid"]
            continue
        except OSError:
            continue
        if any(v in data for v in values):
            ok.append(_say(False, f"/proc/{pid}/environ", "holds a canary"))
    ok.append(_say(harness == 1, f"/proc/{CONFIG['harness_pid']}/environ (the harness)",
                   "unreadable" if harness else "readable or gone"))
    try:
        with open(CONFIG["secret_file"], "rb") as f:
            ok.append(_say(False, CONFIG["secret_file"], f"read {len(f.read())} bytes"))
    except OSError as exc:
        ok.append(_say(exc.errno in DENIED, CONFIG["secret_file"], f"{type(exc).__name__} errno {exc.errno}"))
    assert all(ok)


@cocotb.test()
async def reach_no_signal(dut):
    try:
        os.kill(CONFIG["harness_pid"], 0)
    except OSError as exc:
        assert _say(exc.errno == errno.EPERM, "signal the harness", f"{type(exc).__name__} errno {exc.errno}")
    else:
        assert _say(False, "signal the harness", "allowed")


@cocotb.test()
async def reach_no_read(dut):
    ok = []
    for path in CONFIG["read_files"]:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as exc:
            ok.append(_say(exc.errno in DENIED, f"read {path}", f"{type(exc).__name__} errno {exc.errno}"))
        else:
            ok.append(_say(False, f"read {path}", f"read {len(data)} bytes"))
    for path in CONFIG["list_dirs"]:
        try:
            names = os.listdir(path)
        except OSError as exc:
            ok.append(_say(exc.errno in DENIED, f"list {path}", f"{type(exc).__name__} errno {exc.errno}"))
        else:
            ok.append(_say(False, f"list {path}", f"{len(names)} entries"))
    assert ok and all(ok)


@cocotb.test()
async def reach_no_network(dut):
    import socket

    ok = []
    for kind, host, port in CONFIG["network"]:
        family = socket.AF_INET6 if kind == "tcp6" else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_DGRAM if kind == "udp" else socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            if kind == "udp":
                sock.sendto(b"\x00", (host, port))
            else:
                sock.connect((host, port))
        except OSError as exc:
            denied = (exc.errno in DENIED or (kind != "udp" and exc.errno == errno.EHOSTUNREACH)
                      or (kind == "tcp6" and exc.errno == errno.ENETUNREACH))
            ok.append(_say(denied, f"{kind} {host} port {port}", f"{type(exc).__name__} errno {exc.errno}"))
        else:
            ok.append(_say(False, f"{kind} {host} port {port}", "sent" if kind == "udp" else "connected"))
        finally:
            sock.close()
    assert ok and all(ok)


@cocotb.test()
async def reach_own_directory(dut):
    path = os.path.join(os.getcwd(), "reach-control.txt")
    with open(path, "w") as f:
        f.write("written by the seat account\n")
    print(f"REACH control: wrote {path}", flush=True)
'''


class Unresolved(SystemExit):
    """A target the reach test cannot name: the test fails, since a probe of nothing would read as denied."""

    def __init__(self, what: str) -> None:
        super().__init__(f"reach test: cannot determine {what}, so no probe of it can show it denied; no trial ran")


def _need(value, what: str):
    """``value``, or fail the reach test: a target never falls back to nothing."""
    if value is None or value == "" or value == []:
        raise Unresolved(what)
    return value


def targets(records: Path, env: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Folders seat code must not create a file in, and files it must not open for writing; each one exists.

    Fails closed: a target it cannot determine (the package's file, cocotb, a program a gate runs, the programs
    the seat account runs, and in Actions the runner's temporary folder, the step's command files and the
    installed package's metadata) or one that does not exist stops the test, never shrinks it."""
    import nirmaan

    package = Path(_need(nirmaan.__file__, "the nirmaan package's file")).resolve().parent
    purelib = Path(_need(sysconfig.get_paths().get("purelib"), "site-packages"))
    create = [ROOT, ROOT / "src" / "nirmaan", ROOT / "scripts", ROOT / "evals", ROOT / ".git", package, purelib,
              Path(_need(sys.executable, "the Python")).resolve().parent, WRAPPER.parent, records]
    append = [ROOT / "pyproject.toml", ROOT / "scripts" / "live_eval_ci.py", ROOT / ".github" / "workflows" /
              "live-eval.yml", package / "__init__.py", package / "integrations" / "cocotb_runner.py",
              Path(sys.executable).resolve(), WRAPPER, WRAPPER.parent / EXEC_NAME, WRAPPER.parent.parent / "seat.py"]
    installed = sorted(purelib.glob("__editable__*nirmaan*")) + sorted(purelib.glob("*nirmaan*.pth"))
    in_actions = env.get("GITHUB_ACTIONS") == "true"
    append += _need(installed, f"the installed package's files in {purelib}") if in_actions else installed
    # Every folder on PATH and every program a gate or the harness runs: seat code that could put a program of its
    # own there, or change one, would run as the runner at the next gate.
    folders = [Path(d) for d in _need(env.get("PATH"), "PATH").split(os.pathsep) if d]
    create += [d for d in folders if d.is_dir()]
    for tool in TOOLS:
        append.append(Path(_need(shutil.which(tool, path=env.get("PATH")), f"{tool} on PATH")).resolve())
    exes = WRAPPER.parent.parent / "exes.json"
    try:  # the programs the wrappers run as the seat account
        wrapped = json.loads(exes.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        wrapped = None
    append += [Path(e) for e in _need(wrapped, f"the programs the seat account runs ({exes})")]
    found = importlib.util.find_spec("cocotb")
    create.append(Path(_need(found.origin if found else None, "the cocotb package")).resolve().parent)
    names = ("RUNNER_TEMP", "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH", "GITHUB_STEP_SUMMARY")
    for name in names:
        value = _need(env.get(name), name) if in_actions else env.get(name)
        if not value:
            continue
        path = Path(value)
        if name == "RUNNER_TEMP":
            create.append(path)
        else:
            path.touch(exist_ok=True)
            append.append(path)
    missing = [str(p) for p in [*create, *append] if not p.exists()]
    if missing:
        raise SystemExit(f"reach test: these targets do not exist, so a refusal would prove nothing: {missing}")
    return [str(p) for p in dict.fromkeys(create)], [str(p) for p in dict.fromkeys(append)]


def held_out_files(evals: Path = ROOT / "evals") -> list[str]:
    """Every reference answer, held-out case file and mutant the eval cases name, as paths in the checkout.

    Fails closed: a named file that does not exist stops the test, so a refusal of it proves something."""
    from nirmaan.evals.cases import load_cases

    named: list[str] = []
    for case in load_cases(evals, flow=None):
        named += [f.path for f in case.reference]
        for check in case.held_out:
            named += [p for paths in check.case_files.values() for p in paths]
            named += [p for original, mutants in check.mutants.items() for p in (original, *mutants)]
    files = [Path(p) if Path(p).is_absolute() else ROOT / p for p in dict.fromkeys(named)]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise SystemExit(f"reach test: these held-out files do not exist, so a refusal would prove nothing: {missing}")
    return [str(f) for f in _need(files, "the held-out files of the eval cases")]


def read_targets(env: Mapping[str, str], canary: str, nonce: str) -> tuple[list[str], list[str], list[Path]]:
    """Files seat code must not read and folders it must not list, and the canary files written for the probe.

    A canary file holds ``canary`` and is readable by every account by its mode (0644), in the checkout and, in
    Actions, in the runner's temporary folder: only a denial of the account itself keeps it out. The caller removes
    the canaries (``remove_canaries``) before the checkout is hashed."""
    in_actions = env.get("GITHUB_ACTIONS") == "true"
    homes = [Path(_need(env.get("HOME"), "HOME"))] if in_actions else [Path(p) for p in (env.get("HOME"),) if p]
    temps = [Path(_need(env.get("RUNNER_TEMP"), "RUNNER_TEMP"))] if in_actions else []
    dirs = [ROOT, ROOT / ".git", *homes, *temps]
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        raise SystemExit(f"reach test: these folders do not exist, so a refusal would prove nothing: {missing}")
    files = held_out_files()
    canaries = []
    try:
        for folder in (ROOT, *temps):
            path = folder / f".nirmaan-read-canary-{nonce}"
            canaries.append(path)
            path.write_text(canary + "\n", encoding="utf-8")
            path.chmod(0o644)
    except OSError:
        remove_canaries(canaries)
        raise
    return [*files, *(str(c) for c in canaries)], [str(d) for d in dict.fromkeys(dirs)], canaries


def remove_canaries(canaries: Sequence[Path]) -> None:
    for path in canaries:
        path.unlink(missing_ok=True)


def probe_module(config: dict) -> str:
    return PROBE.replace("__CONFIG__", repr(json.dumps(config)))


def results_problem(xml_text: str | None) -> str | None:
    """Why cocotb's results do not show every probe passed, or None."""
    if not xml_text:
        return "cocotb wrote no results"
    seen: dict[str, bool] = {}
    for case in ET.fromstring(xml_text).iter("testcase"):
        name = case.get("name", "")
        seen[name] = not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
    missing = [p for p in PROBES if p not in seen]
    failed = [p for p in PROBES if p in seen and not seen[p]]
    extra = [n for n in seen if n not in PROBES]
    parts = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"not denied in {', '.join(failed)}"]
                                                                          if failed else [])
    parts += [f"unexpected tests {', '.join(extra)}"] if extra else []
    return "; ".join(parts) or None


def precheck() -> str | None:
    """Why seat code here would not run as the seat account at all, or None."""
    for name in WRAPPED:
        found = shutil.which(name)
        if found is None or Path(found) != WRAPPER.parent / name:
            return f"{name} on PATH is {found}, not the seat account's {WRAPPER.parent / name}"
    try:
        pwd.getpwnam(SEAT)
    except KeyError:
        return f"no {SEAT} account"
    return None


def reach(records: Path) -> int:
    from nirmaan.integrations import cocotb_runner  # noqa: F401  (registers the backend)
    from nirmaan.integrations.eda import execute, read_output, select_backend, temporary_runs
    from nirmaan.runtime.tools import Params

    problem = precheck()
    if problem:
        print(f"::error::reach test: {problem}; no trial ran", flush=True)
        return 1
    create, append = targets(records, os.environ)
    params: Params = {"backend": "cocotb", "sources": "", "top": "reach_probe", "cocotb": "", "timeout": "300"}
    backend, why = select_backend("simulator.run", params)
    if backend is None:
        print(f"::error::reach test: no cocotb backend: {why}", flush=True)
        return 1
    canaries = [secrets.token_hex(16), secrets.token_hex(16)]
    nonce, file_canary = secrets.token_hex(8), secrets.token_hex(16)
    read_files, list_dirs, canary_files = read_targets(os.environ, file_canary, nonce)
    os.environ[CANARY_SECRET], os.environ[CANARY_PLAIN] = canaries
    work = secret = None
    try:  # the canaries leave the checkout and the environment whatever happens
        # A run folder of the harness's kind (``/tmp/nirmaan-*``): the seat account's tools read their inputs only from
        # one. The runner-only file is in a folder of its own, outside the run's view.
        work = Path(tempfile.mkdtemp(prefix="nirmaan-reach-probe-"))
        secret = Path(tempfile.mkdtemp(prefix="nirmaan-reach-secret-"))
        secret_file = secret / "credential"
        secret_file.write_text(secrets.token_hex(16))
        secret_file.chmod(0o600)
        config = {"seat": SEAT, "runner": pwd.getpwuid(os.getuid()).pw_name, "runner_uid": os.getuid(),
                  "harness_pid": os.getpid(), "nonce": nonce, "create_in": create, "append_to": append,
                  "canaries": canaries, "secret_file": str(secret_file), "read_files": read_files,
                  "list_dirs": list_dirs, "network": [list(n) for n in NETWORK]}
        test = work / "reach_probe_test.py"
        test.write_text(probe_module(config))
        design = work / "reach_probe.v"
        design.write_text(DESIGN)
        params = {**params, "sources": str(design), "cocotb": str(test)}
        with temporary_runs():
            outcome = execute(backend, params)
            log = Path(outcome.outputs["log"]).read_text(encoding="utf-8") if "log" in outcome.outputs else ""
            results = outcome.outputs.get("results")
            xml_text = read_output(Path(results)) if results else None
    finally:
        del os.environ[CANARY_SECRET], os.environ[CANARY_PLAIN]
        for folder in (work, secret):
            if folder is not None:
                shutil.rmtree(folder, ignore_errors=True)
        remove_canaries(canary_files)
    for line in log.splitlines():
        if line.startswith("REACH ") or "TESTS=" in line:
            print(line, flush=True)
    problem = results_problem(xml_text)
    if any(value in text for value in (*canaries, file_canary) for text in (log, xml_text or "")):
        problem = "; ".join(filter(None, (problem, "a canary value is in the run's log or results")))
    if outcome.succeeded and problem is None:
        print(f"reach test: every probe denied ({len(PROBES)} cocotb tests as {SEAT}, {len(create)} folders and "
              f"{len(append)} files not written, {len(read_files)} files not read and {len(list_dirs)} folders not "
              f"listed, {len(NETWORK)} network targets not reached, {len(canaries) + 1} canaries in no log)", flush=True)
        return 0
    print(f"::error::reach test: {problem or outcome.summary}; no trial ran", flush=True)
    print(log, flush=True)
    return 1


# --- Gate ET3: the tools that read seat-written Verilog, as the seat account ---------------------------------------


def tool_reach(out: Path | None) -> int:
    """Run the tool probes (``tools_child``) in a process whose real environment holds two canaries; 0 only when every
    probe is denied and every control passed."""
    canaries = {CANARY_SECRET: secrets.token_hex(16), CANARY_PLAIN: secrets.token_hex(16)}
    record = out or Path(tempfile.mkdtemp(prefix="nirmaan-reach-record-")) / "tool-reach.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--tools-child", "--out", str(record)],
                          env={**os.environ, **canaries})
    if proc.returncode != 0 or not record.is_file():
        print(f"::error::reach test: a tool probe was not denied, or a control failed (exit {proc.returncode}); no "
              f"trial ran", flush=True)
        return 1
    data = json.loads(record.read_text(encoding="utf-8"))
    if not data.get("every_denied") or any(v in record.read_text(encoding="utf-8") for v in canaries.values()):
        print("::error::reach test: the tool reach record does not show every probe denied; no trial ran", flush=True)
        return 1
    return 0


def _write(path: Path, text: str, mode: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def _opened(texts: Sequence[str], messages: Sequence[str], target: str) -> bool:
    """Whether the tool said it could not open ``target``: one of its own messages, naming it, is in the log."""
    return not any(m.format(target) in t for m in messages for t in texts)


def tools_child(out: Path) -> int:
    """The tool probes, run in the process ``tool_reach`` starts (its environment holds the canaries)."""
    from nirmaan.evals.scorers import _stage
    from nirmaan.integrations import eda
    from nirmaan.integrations.eda import execute, select_backend, temporary_runs

    canaries = [_need(os.environ.get(CANARY_SECRET), CANARY_SECRET), _need(os.environ.get(CANARY_PLAIN), CANARY_PLAIN)]
    nonce = secrets.token_hex(8)
    file_canaries = [secrets.token_hex(16) for _ in range(3)]
    secret_values = [*canaries, *file_canaries]
    box = Path(tempfile.mkdtemp(prefix="nirmaan-reach-tools-")).resolve()
    other = Path(tempfile.mkdtemp(prefix="nirmaan-reach-runner-")).resolve()
    other.chmod(0o755)  # every account may enter it, so only the file's own mode keeps the account out
    in_checkout = ROOT / f".nirmaan-tool-canary-{nonce}"
    results: list[dict] = []
    real_check, real_sby = eda.check_inputs, eda.sby_problem

    def run(tool: str, gate: str, name: str, params: dict, bypass: bool):
        backend, why = select_backend(gate, {"backend": name})
        if backend is None:
            raise SystemExit(f"reach test: {gate} has no {name} backend here: {why}; no trial ran")
        if bypass:
            print(f"REACH tool {tool}: the screen is bypassed for this probe only, so the include reaches the tool",
                  flush=True)
            eda.check_inputs = eda.sby_problem = lambda *_a, **_k: None
        try:
            outcome = execute(backend, {"backend": name, "timeout": "300", **params})
        finally:
            eda.check_inputs, eda.sby_problem = real_check, real_sby
        texts = [outcome.summary]
        for ref in outcome.references:
            texts.append(Path(ref).read_text(encoding="utf-8", errors="replace"))
        return outcome, texts

    def note(tool: str, gate: str, probe: str, target: str | None, ok: bool, detail: str, texts: Sequence[str]):
        leaked = [n for n, v in enumerate(secret_values) if any(v in t for t in texts)]
        ok = ok and not leaked
        detail += f"; canary values in the log, summary or result: {len(leaked)}"
        results.append({"tool": tool, "gate": gate, "probe": probe, "target": target, "denied": ok, "detail": detail})
        print(f"REACH tool {'denied' if ok else 'NOT DENIED'}: {tool} ({gate}) {probe}"
              f"{f' {target}' if target else ''}: {detail}", flush=True)

    try:
        _write(in_checkout, f'initial $display("CANARY {file_canaries[0]}");\n', 0o644)
        runner_only = _write(other / f"runner-only-{nonce}", f'initial $display("CANARY {file_canaries[1]}");\n',
                             0o600)
        targets = [("checkout canary", str(in_checkout)), ("runner-only canary", str(runner_only)),
                   ("credential canary in the parent's environment", f"/proc/{os.getpid()}/environ")]
        for what, target in targets:  # each exists and the runner can read it, so a denial proves something
            with open(target, "rb") as f:
                data = f.read()
            if what.startswith("credential") and canaries[0].encode() not in data:
                raise SystemExit(f"reach test: the canary is not in {target}, so no probe of it proves anything")
        with temporary_runs():
            for tool, gate, name, messages in TOOL_GATES:
                file, top, head, tail = TOOL_FILES[tool]
                tail = tail.replace("__NONCE__", nonce)
                for n, (what, target) in enumerate([("control", None), *targets]):
                    here = box / tool / str(n)
                    text = head + (f'`include "{target}"\n' if target else "") + tail
                    source = _write(here / file, text, 0o600)  # the runner's and, by its grant, the seat account's
                    params: dict = {"sources": str(source), "top": top}
                    if tool == "sby":
                        params = {"sources": str(source), "sby": str(_write(here / "reach_tool_formal.sby", SBY_SETUP,
                                                                              0o600))}
                    outcome, texts = run(tool, gate, name, params, bypass=target is not None)
                    if target is None:
                        ok = outcome.succeeded and (tool != "iverilog" or f"REACH TOOL control {nonce}" in texts[1])
                        note(tool, gate, "control (seat files of mode 0600 read and passed)", None, ok,
                             outcome.summary[:200], texts)
                        if tool == "sby":  # the cover run of the same setup, through formal.cover
                            cover, ctexts = run(tool, "formal.cover", "symbiyosys-cover", params, bypass=False)
                            note(tool, "formal.cover", "control (seat files of mode 0600 read and passed)", None,
                                 cover.succeeded, cover.summary[:200], ctexts)
                        continue
                    denied = not outcome.succeeded and not _opened(texts, messages, target)
                    note(tool, gate, what, target, denied, outcome.summary[:200], texts)
            # Decision 3, item 2: the held-out checks' compile reads the run's own judge file and nothing beside it.
            judge_src = _write(box / "judge-source" / "reach_judge.v",
                               f'module reach_judge;\ninitial $display("REACH JUDGE {nonce}");\nendmodule\n', 0o644)
            for n, beside in enumerate((False, True)):
                staged = _stage(box / "judge" / f"check-{n}", {"sources": [judge_src]}, None)["sources"][0]
                canary = _write(Path(staged).parent / f"beside-{nonce}",
                                f'initial $display("CANARY {file_canaries[2]}");\n', 0o644)
                include = f'`include "{canary}"\n' if beside else ""
                seat_tb = _write(box / "held-out" / str(n) / "reach_seat_tb.v",
                                 f"module reach_seat_tb;\n{include}reach_judge j();\nreg [8*64-1:0] nonce;\n"
                                 "initial begin #1\nif ($value$plusargs(\"nirmaan_nonce=%s\", nonce)) "
                                 "$display(\"NIRMAAN-SIM %0s 1 passed, 0 failed\", nonce);\n$finish;\nend\n"
                                 "endmodule\n", 0o644)
                outcome, texts = run("iverilog", "simulator.run", "icarus",
                                     {"sources": f"{seat_tb},{staged}", "top": "reach_seat_tb"}, bypass=beside)
                if beside:
                    denied = not outcome.succeeded and not _opened(texts, TOOL_GATES[0][3], str(canary))
                    note("iverilog", "simulator.run", "held-out compile: a canary beside the staged judge file",
                         str(canary), denied, outcome.summary[:200], texts)
                else:
                    ok = outcome.succeeded and f"REACH JUDGE {nonce}" in texts[1]
                    note("iverilog", "simulator.run", "held-out compile control (the staged judge file is read)",
                         None, ok, outcome.summary[:200], texts)
    finally:
        eda.check_inputs, eda.sby_problem = real_check, real_sby
        in_checkout.unlink(missing_ok=True)
        shutil.rmtree(box, ignore_errors=True)
        shutil.rmtree(other, ignore_errors=True)
    every = bool(results) and all(r["denied"] for r in results)
    record = {"format": "nirmaan.tool-reach", "seat": SEAT, "every_denied": every, "probes": results,
              "commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
              "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"), "job": os.environ.get("GITHUB_JOB"),
              "seat_tools": os.environ.get(eda.SEAT_TOOLS_ENV) or None}
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    denied = sum(r["denied"] for r in results)
    print(f"reach test: tools as {SEAT}: {denied} of {len(results)} probes and controls as required", flush=True)
    return 0 if every else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test what seat code can reach in this job, through cocotb.")
    parser.add_argument("--records", type=Path, help="the records folder seat code must not write")
    parser.add_argument("--out", type=Path, default=None, help="where the tool reach record is written")
    parser.add_argument("--tools-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.tools_child:
        return tools_child(args.out)
    if args.records is None:
        parser.error("--records is required")
    return reach(args.records) or tool_reach(args.out)


if __name__ == "__main__":
    sys.exit(main())
