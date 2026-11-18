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
  read; or signal the harness.

and one control, that it can write its own run directory. The module runs through ``simulator.run``'s cocotb
backend (``eda.execute``), so through the ``vvp`` the trials use. The test passes only when cocotb's verdict is
a pass and every probe test is in the results, passed: every probe denied. Otherwise it exits 1 and the job
stops before any trial.

``fw.test`` runs seat C by path, so the seat account does not reach it yet; ``scripts/live_eval_ci.py`` refuses a
live trial of a case that runs seat C. Its probe lands with that confinement.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import secrets
import shutil
import sys
import sysconfig
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAT = "nirmaan-seat"
WRAPPER = Path("/opt/nirmaan-seat/bin/vvp")
#: Credential-named and plain-named canaries; neither may reach seat code.
CANARY_SECRET, CANARY_PLAIN = "CLAUDE_CODE_OAUTH_TOKEN", "NIRMAAN_REACH_CANARY"
#: The probe tests, by name; each must be in cocotb's results and pass.
PROBES = ("reach_identity", "reach_no_sudo", "reach_no_write", "reach_no_credential", "reach_no_signal",
          "reach_own_directory")
#: The programs gates run (eda.py backends) and the harness's own entry point.
TOOLS = ("nirmaan", "iverilog", "vvp", "verilator", "yosys", "sby", "yices-smt2", "make", "cc", "python", "python3",
         "git", "node", "npm")
DESIGN = "module reach_probe(input wire clk);\nendmodule\n"

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
async def reach_own_directory(dut):
    path = os.path.join(os.getcwd(), "reach-control.txt")
    with open(path, "w") as f:
        f.write("written by the seat account\n")
    print(f"REACH control: wrote {path}", flush=True)
'''


def targets(records: Path, env: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Folders seat code must not create a file in, and files it must not open for writing; each one exists."""
    import nirmaan

    package = Path(nirmaan.__file__).resolve().parent
    purelib = Path(sysconfig.get_paths()["purelib"])
    create = [ROOT, ROOT / "src" / "nirmaan", ROOT / "scripts", ROOT / "evals", ROOT / ".git", package, purelib,
              Path(sys.executable).resolve().parent, WRAPPER.parent, records]
    append = [ROOT / "pyproject.toml", ROOT / "scripts" / "live_eval_ci.py", ROOT / ".github" / "workflows" /
              "live-eval.yml", package / "__init__.py", package / "integrations" / "cocotb_runner.py",
              Path(sys.executable).resolve(), WRAPPER, WRAPPER.parent.parent / "seat.py"]
    append += sorted(purelib.glob("__editable__*nirmaan*")) + sorted(purelib.glob("*nirmaan*.pth"))
    # Every folder on PATH and every program a gate or the harness runs: seat code that could put a program of its
    # own there, or change one, would run as the runner at the next gate.
    create += [Path(d) for d in env.get("PATH", "").split(os.pathsep) if d and Path(d).is_dir()]
    for tool in TOOLS:
        found = shutil.which(tool, path=env.get("PATH"))
        if found:
            append.append(Path(found).resolve())
    exes = WRAPPER.parent.parent / "exes.json"
    if exes.is_file():  # the programs the wrappers run as the seat account
        append += [Path(e) for e in json.loads(exes.read_text(encoding="utf-8"))]
    try:
        import cocotb

        create.append(Path(cocotb.__file__).resolve().parent)
    except ImportError:
        pass
    for name in ("RUNNER_TEMP",):
        if env.get(name):
            create.append(Path(env[name]))
    for name in ("GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH", "GITHUB_STEP_SUMMARY"):
        if env.get(name):
            path = Path(env[name])
            path.touch(exist_ok=True)
            append.append(path)
    missing = [str(p) for p in [*create, *append] if not p.exists()]
    if missing:
        raise SystemExit(f"reach test: these targets do not exist, so a refusal would prove nothing: {missing}")
    return [str(p) for p in dict.fromkeys(create)], [str(p) for p in dict.fromkeys(append)]


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
    vvp = shutil.which("vvp")
    if vvp is None or Path(vvp) != WRAPPER:
        return f"vvp on PATH is {vvp}, not the seat account's {WRAPPER}"
    try:
        pwd.getpwnam(SEAT)
    except KeyError:
        return f"no {SEAT} account"
    return None


def reach(records: Path) -> int:
    from nirmaan.integrations import cocotb_runner  # noqa: F401  (registers the backend)
    from nirmaan.integrations.eda import execute, read_output, select_backend, temporary_runs

    problem = precheck()
    if problem:
        print(f"::error::reach test: {problem}; no trial ran", flush=True)
        return 1
    create, append = targets(records, os.environ)
    canaries = [secrets.token_hex(16), secrets.token_hex(16)]
    os.environ[CANARY_SECRET], os.environ[CANARY_PLAIN] = canaries
    work = Path(tempfile.mkdtemp(prefix="reach-probe-"))
    secret_file = work / "credential"
    secret_file.write_text(secrets.token_hex(16))
    secret_file.chmod(0o600)
    config = {"seat": SEAT, "runner": pwd.getpwuid(os.getuid()).pw_name, "runner_uid": os.getuid(),
              "harness_pid": os.getpid(), "nonce": secrets.token_hex(8), "create_in": create, "append_to": append,
              "canaries": canaries, "secret_file": str(secret_file)}
    test = work / "reach_probe_test.py"
    test.write_text(probe_module(config))
    design = work / "reach_probe.v"
    design.write_text(DESIGN)
    params = {"backend": "cocotb", "sources": str(design), "top": "reach_probe", "cocotb": str(test), "timeout": "300"}
    backend, why = select_backend("simulator.run", params)
    if backend is None:
        print(f"::error::reach test: no cocotb backend: {why}", flush=True)
        return 1
    try:
        with temporary_runs():
            outcome = execute(backend, params)
            log = Path(outcome.outputs["log"]).read_text(encoding="utf-8") if "log" in outcome.outputs else ""
            results = outcome.outputs.get("results")
            xml_text = read_output(Path(results)) if results else None
    finally:
        del os.environ[CANARY_SECRET], os.environ[CANARY_PLAIN]
        shutil.rmtree(work, ignore_errors=True)
    for line in log.splitlines():
        if line.startswith("REACH ") or "TESTS=" in line:
            print(line, flush=True)
    problem = results_problem(xml_text)
    if outcome.succeeded and problem is None:
        print(f"reach test: every probe denied ({len(PROBES)} cocotb tests as {SEAT}, {len(create)} folders, "
              f"{len(append)} files, {len(canaries)} canaries)", flush=True)
        return 0
    print(f"::error::reach test: {problem or outcome.summary}; no trial ran", flush=True)
    print(log, flush=True)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test what seat code can reach in this job, through cocotb.")
    parser.add_argument("--records", type=Path, required=True, help="the records folder seat code must not write")
    args = parser.parse_args(argv)
    return reach(args.records)


if __name__ == "__main__":
    sys.exit(main())
