"""The credential test for seat C (G3 council record 2026-11-17, decision 4; second addendum, decision 2, item 1).

Before the first register block trial the council asks whether compiled seat C, run through ``fw.test`` in the
named job, can read the environment of its parent or of any process it can see, run a command as another user
without a password, or write to the checkout, the installed package or the records folder, and that the result be
recorded. This script asks exactly that, through the real path: it writes a driver test in C (``PROBE`` below,
built with the canaries and targets of this run) and runs it with ``fw.test``'s co-simulation backend
(``eda.execute``) against the reference AXI4-Lite register block, as a seat's test would run.

The probe's parent is a Python process this script starts with two canaries in its real environment (one under
the credential name ``CLAUDE_CODE_OAUTH_TOKEN``, one under a plain name), as the trials step's ``nirmaan`` process
holds the plan token, and a runner-only file. Its tests try to:

- run as the runner account (``fw_reach_identity``);
- run ``sudo -n true`` and ``sudo -n -u <runner> true`` (``fw_reach_no_sudo``);
- create a file in the checkout, ``src/nirmaan``, ``scripts``, ``evals``, the installed package, ``site-packages``
  and the records folder (``fw_reach_no_write``);
- find a canary in its own environment or in ``/proc/<pid>/environ`` of any process (``fw_reach_no_credential``);
- read its parent's and the harness's ``/proc/<pid>/environ`` at all (``fw_reach_no_parent_environ``);
- read the runner-only file (``fw_reach_no_secret_file``);
- signal the harness (``fw_reach_no_signal``);

and, as the control, write its own run directory (the test fails unless it can). A probe is denied only on EACCES, EPERM or EROFS (for sudo: a
refusal, not a missing program); anything else is "NOT DENIED", so a probe that proves nothing never reads as
denied.

Two modes. By default it RECORDS: it prints every probe, writes the result (``--out``) and exits 0 when every probe
ran, whatever they found; it exits 1 only when the probe did not run or a probe is missing from its output. With
``--require-denied`` it is a gate: it exits 1 unless every probe is denied. Today ``fw.test`` runs seat C by path,
as the runner, so the expected record is "not denied", and ``scripts/live_eval_ci.py`` refuses a live trial of a
case that runs seat C (exit 6). When ``fw.test`` runs seat C as the seat account (a harness change), the workflow
switches this step to ``--require-denied`` for such a case. See docs/LIVE_EVAL_EVIDENCE.md, section 6.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "nirmaan.fw-reach/1"
#: Credential-named and plain-named canaries, in the harness's real environment.
CANARY_SECRET, CANARY_PLAIN = "CLAUDE_CODE_OAUTH_TOKEN", "NIRMAAN_FW_REACH_CANARY"
INNER = "NIRMAAN_FW_REACH_INNER"
#: The probe tests, by name; each must report at least one line, and is denied only when every line is.
PROBES = ("fw_reach_identity", "fw_reach_no_sudo", "fw_reach_no_write", "fw_reach_no_credential",
          "fw_reach_no_parent_environ", "fw_reach_no_secret_file", "fw_reach_no_signal")
CONTROL = "fw_reach_own_directory"
RTL = ROOT / "tests" / "fixtures" / "rtl" / "axi4_lite" / "axi4_lite_regs.v"
TOP = "axi4_lite_regs"
LINE = re.compile(r"^FW-REACH (denied|NOT DENIED|control ok|control FAILED): (\w+): (.*)$")

PROBE = r"""/*
 * Credential test for seat C under fw.test (scripts/live_eval_fw_reach.py, G3 council record 2026-11-17,
 * decision 4 and second addendum, decision 2, item 1). Not a driver test and not a seat answer: written for one
 * run, with that run's canaries and targets. Each test passes only when the access is denied.
 */
#define _POSIX_C_SOURCE 200809L
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "nirmaan_hal.h"

extern char **environ;

static const char *const CANARIES[] = {__CANARIES__};
static const char *const CREATE_IN[] = {__CREATE_IN__};
static const long RUNNER_UID = __RUNNER_UID__;
static const long HARNESS_PID = __HARNESS_PID__;
static const char SECRET_FILE[] = __SECRET_FILE__;
static const char RUNNER[] = __RUNNER__;
static const char NONCE[] = __NONCE__;

#define COUNT(a) (sizeof (a) / sizeof (a)[0])

static char buf[1 << 20];

static int refused(int err) {
    return err == EACCES || err == EPERM || err == EROFS;
}

static int say(int denied, const char *probe, const char *what, const char *detail) {
    printf("FW-REACH %s: %s: %s: %s\n", denied ? "denied" : "NOT DENIED", probe, what, detail);
    fflush(stdout);
    return denied;
}

static int holds_canary(const char *data, size_t n) {
    size_t i, k;
    for (k = 0; k < COUNT(CANARIES); ++k) {
        const size_t m = strlen(CANARIES[k]);
        for (i = 0; m > 0 && i + m <= n; ++i) {
            if (memcmp(data + i, CANARIES[k], m) == 0) return 1;
        }
    }
    return 0;
}

/* Up to cap bytes of path into buf; the count, or -1 with errno set. */
static long slurp(const char *path, size_t cap) {
    long total = 0;
    ssize_t got;
    const int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    while ((size_t)total < cap && (got = read(fd, buf + total, cap - (size_t)total)) > 0) total += (long)got;
    close(fd);
    return total;
}

static int probe_identity(void) {
    char detail[256];
    snprintf(detail, sizeof detail, "uid %ld, euid %ld, gid %ld (runner uid %ld)", (long)getuid(), (long)geteuid(),
             (long)getgid(), RUNNER_UID);
    return say((long)getuid() != RUNNER_UID && (long)geteuid() != RUNNER_UID, "fw_reach_identity", "not the runner",
               detail);
}

/* The exit code of argv run with no input or output, 127 when it could not run, -1 when it could not start. */
static int run_quiet(char *argv[]) {
    int status = 0;
    pid_t pid;
    fflush(NULL);
    pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        const int null = open("/dev/null", O_RDWR);
        if (null >= 0) {
            dup2(null, 0);
            dup2(null, 1);
            dup2(null, 2);
        }
        execv(argv[0], argv);
        _exit(127);
    }
    if (waitpid(pid, &status, 0) < 0) return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
}

static int probe_sudo(void) {
    char runner[256], detail[256], sudo[] = "/usr/bin/sudo", n[] = "-n", u[] = "-u", yes[] = "/usr/bin/true";
    char *root[5], *as_runner[7];
    int code, all = 1;
    snprintf(runner, sizeof runner, "%s", RUNNER);
    root[0] = sudo; root[1] = n; root[2] = yes; root[3] = NULL;
    as_runner[0] = sudo; as_runner[1] = n; as_runner[2] = u; as_runner[3] = runner; as_runner[4] = yes;
    as_runner[5] = NULL;
    code = run_quiet(root);
    snprintf(detail, sizeof detail, "exit %d%s", code, code == 127 || code < 0 ? " (could not run: nothing proven)" : "");
    all &= say(code > 0 && code != 127, "fw_reach_no_sudo", "sudo -n true", detail);
    code = run_quiet(as_runner);
    snprintf(detail, sizeof detail, "exit %d%s", code, code == 127 || code < 0 ? " (could not run: nothing proven)" : "");
    all &= say(code > 0 && code != 127, "fw_reach_no_sudo", "sudo -n -u <runner> true", detail);
    return all;
}

static int probe_write(void) {
    char path[4096], detail[256];
    size_t i;
    int all = 1;
    for (i = 0; i < COUNT(CREATE_IN); ++i) {
        int fd, err;
        snprintf(path, sizeof path, "%s/.nirmaan-fw-reach-%s", CREATE_IN[i], NONCE);
        fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0644);
        err = errno;
        if (fd >= 0) {
            close(fd);
            unlink(path);
            all &= say(0, "fw_reach_no_write", CREATE_IN[i], "created a file (removed again)");
            continue;
        }
        snprintf(detail, sizeof detail, "errno %d (%s)", err, strerror(err));
        all &= say(refused(err), "fw_reach_no_write", CREATE_IN[i], detail);
    }
    return all;
}

static int probe_credential(void) {
    char path[64], detail[256];
    struct dirent *entry;
    DIR *proc;
    size_t i;
    int all = 1, mine = 0, read_ok = 0, found = 0;
    for (i = 0; environ != NULL && environ[i] != NULL; ++i) mine |= holds_canary(environ[i], strlen(environ[i]));
    all &= say(!mine, "fw_reach_no_credential", "own environment", mine ? "holds a canary" : "no canary");
    proc = opendir("/proc");
    if (proc == NULL) return say(0, "fw_reach_no_credential", "/proc", "cannot list /proc: nothing proven");
    while ((entry = readdir(proc)) != NULL) {
        char *end;
        long n;
        const long pid = strtol(entry->d_name, &end, 10);
        if (entry->d_name[0] < '0' || entry->d_name[0] > '9' || *end != '\0') continue;
        snprintf(path, sizeof path, "/proc/%ld/environ", pid);
        n = slurp(path, sizeof buf);
        if (n < 0) continue;
        ++read_ok;
        if (holds_canary(buf, (size_t)n)) {
            ++found;
            all &= say(0, "fw_reach_no_credential", path, "holds a canary");
        }
    }
    closedir(proc);
    snprintf(detail, sizeof detail, "%d environments readable, %d holding a canary", read_ok, found);
    all &= say(found == 0, "fw_reach_no_credential", "/proc/<pid>/environ of every process", detail);
    return all;
}

static int one_environ(const char *who, long pid) {
    char path[64], detail[256];
    long n;
    int err;
    snprintf(path, sizeof path, "/proc/%ld/environ", pid);
    n = slurp(path, sizeof buf);
    err = errno;
    if (n >= 0) {
        snprintf(detail, sizeof detail, "%s: read %ld bytes, %s", path, n,
                 holds_canary(buf, (size_t)n) ? "a canary among them" : "no canary among them");
        return say(0, "fw_reach_no_parent_environ", who, detail);
    }
    snprintf(detail, sizeof detail, "%s: errno %d (%s)", path, err, strerror(err));
    return say(refused(err), "fw_reach_no_parent_environ", who, detail);
}

static int probe_parent(void) {
    const long parent = (long)getppid();
    int all = one_environ("the parent", parent);
    if (parent != HARNESS_PID) all &= one_environ("the harness", HARNESS_PID);
    return all;
}

static int probe_secret_file(void) {
    char detail[256];
    const long n = slurp(SECRET_FILE, sizeof buf);
    const int err = errno;
    if (n >= 0) {
        snprintf(detail, sizeof detail, "read %ld bytes", n);
        return say(0, "fw_reach_no_secret_file", SECRET_FILE, detail);
    }
    snprintf(detail, sizeof detail, "errno %d (%s)", err, strerror(err));
    return say(refused(err), "fw_reach_no_secret_file", SECRET_FILE, detail);
}

static int probe_signal(void) {
    char detail[256];
    const int code = kill((pid_t)HARNESS_PID, 0);
    const int err = errno;
    if (code == 0) snprintf(detail, sizeof detail, "allowed");
    else snprintf(detail, sizeof detail, "errno %d (%s)", err, strerror(err));
    return say(code != 0 && err == EPERM, "fw_reach_no_signal", "signal 0 to the harness", detail);
}

static void control(void) {
    char path[4096], here[3800];
    FILE *f;
    if (getcwd(here, sizeof here) == NULL) {
        printf("FW-REACH control FAILED: fw_reach_own_directory: no working directory\n");
        return;
    }
    snprintf(path, sizeof path, "%s/fw-reach-control.txt", here);
    f = fopen(path, "w");
    if (f != NULL && fputs("written by the probe\n", f) >= 0 && fclose(f) == 0) {
        printf("FW-REACH control ok: fw_reach_own_directory: wrote %s\n", path);
    } else {
        printf("FW-REACH control FAILED: fw_reach_own_directory: could not write %s\n", path);
    }
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;
    hal->read32(hal->ctx, 0u, &value); /* one transfer, so the run reports one */
    nirmaan_test_result("fw_reach_identity", probe_identity(), NULL);
    nirmaan_test_result("fw_reach_no_sudo", probe_sudo(), NULL);
    nirmaan_test_result("fw_reach_no_write", probe_write(), NULL);
    nirmaan_test_result("fw_reach_no_credential", probe_credential(), NULL);
    nirmaan_test_result("fw_reach_no_parent_environ", probe_parent(), NULL);
    nirmaan_test_result("fw_reach_no_secret_file", probe_secret_file(), NULL);
    nirmaan_test_result("fw_reach_no_signal", probe_signal(), NULL);
    control();
    printf("FW-REACH done\n");
    fflush(stdout);
}
"""


def c_string(value: str) -> str:
    """A C string literal for ``value``; printable ASCII only, so no escape can change what the probe names."""
    if not all(" " <= ch <= "~" for ch in value):
        raise SystemExit(f"fw reach test: {value!r} is not printable ASCII; no probe ran")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Unresolved(SystemExit):
    """A target the test cannot name: it fails, since a probe of nothing would read as denied."""

    def __init__(self, what: str) -> None:
        super().__init__(f"fw reach test: cannot determine {what}, so no probe of it can show it denied; no probe ran")


def _need(value, what: str):
    """``value``, or fail the test: a target never falls back to nothing."""
    if value is None or value == "":
        raise Unresolved(what)
    return value


def targets(records: Path, package_file: str | None = None, purelib: str | None = None) -> list[str]:
    """Folders seat C must not create a file in; each must be named and exist, so a refusal proves something.

    Fails closed: the package's file or ``site-packages`` that cannot be determined, or a folder that does not
    exist, stops the test (no probe runs, the job fails); it never shrinks the list."""
    if package_file is None:
        import nirmaan

        package_file = nirmaan.__file__
    package = Path(_need(package_file, "the nirmaan package's file")).resolve().parent
    purelib = Path(_need(purelib if purelib is not None else sysconfig.get_paths().get("purelib"), "site-packages"))
    folders = [ROOT, ROOT / "src" / "nirmaan", ROOT / "scripts", ROOT / "evals", package, purelib, records]
    missing = [str(p) for p in folders if not p.is_dir()]
    if missing:
        raise SystemExit(f"fw reach test: these targets do not exist, so a refusal would prove nothing: {missing}")
    return [str(p) for p in dict.fromkeys(folders)]


def probe_source(config: Mapping) -> str:
    fill = {"__CANARIES__": ", ".join(c_string(c) for c in config["canaries"]),
            "__CREATE_IN__": ", ".join(c_string(p) for p in config["create_in"]),
            "__RUNNER_UID__": f"{int(config['runner_uid'])}L", "__HARNESS_PID__": f"{int(config['harness_pid'])}L",
            "__SECRET_FILE__": c_string(config["secret_file"]), "__RUNNER__": c_string(config["runner"]),
            "__NONCE__": c_string(config["nonce"])}
    text = PROBE
    for key, value in fill.items():
        text = text.replace(key, value)
    return text


def parse(log: str) -> dict:
    """Each probe's lines and verdict from the run's log; a probe with no line is missing, never denied."""
    lines: dict[str, list[str]] = {}
    verdicts: dict[str, bool] = {}
    control: list[str] = []
    for raw in log.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        kind, name, detail = m.groups()
        if name == CONTROL:
            control.append(f"{kind[len('control '):]}: {detail}")
            continue
        lines.setdefault(name, []).append(f"{kind}: {detail}")
        verdicts[name] = verdicts.get(name, True) and kind == "denied"
    probes = {p: {"denied": verdicts.get(p, False), "lines": lines.get(p, [])} for p in PROBES}
    missing = [p for p in PROBES if p not in lines]
    return {"probes": probes, "missing": missing, "control": control,
            "control_ok": bool(control) and all(c.startswith("ok:") for c in control),
            "done": any(raw.strip() == "FW-REACH done" for raw in log.splitlines()),
            "every_probe_denied": not missing and all(v["denied"] for v in probes.values())}


def inner(records: Path, out: Path) -> int:
    """Run the probe under fw.test, as this process's child, and write what it found. This process is the harness."""
    from nirmaan.integrations import firmware  # noqa: F401  (registers the fw.test backends)
    from nirmaan.integrations.eda import execute, select_backend, temporary_runs

    canaries = [os.environ[CANARY_SECRET], os.environ[CANARY_PLAIN]]
    work = Path(tempfile.mkdtemp(prefix="fw-reach-"))
    secret_file = work / "credential"
    secret_file.write_text(secrets.token_hex(16))
    secret_file.chmod(0o600)
    runner = pwd.getpwuid(os.getuid())
    config = {"canaries": canaries, "create_in": targets(records), "runner_uid": os.getuid(),
              "runner": runner.pw_name, "harness_pid": os.getpid(), "secret_file": str(secret_file),
              "nonce": secrets.token_hex(8)}
    probe = work / "fw_reach_probe.c"
    probe.write_text(probe_source(config))
    backend, why = select_backend("fw.test", {})
    if backend is None:
        print(f"::error::fw reach test: no fw.test backend: {why}; no probe ran", flush=True)
        return 1
    try:
        with temporary_runs():
            outcome = execute(backend, {"sources": str(probe), "rtl": str(RTL), "top": TOP, "timeout": "600"})
            log = (Path(outcome.references[0]).read_text(encoding="utf-8", errors="replace")
                   if outcome.references else "")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    found = parse(log)
    result = {"format": FORMAT, "tool": "fw.test", "backend": backend.name, "rtl": str(RTL.relative_to(ROOT)),
              "account": {"user": runner.pw_name, "uid": os.getuid()}, "summary": outcome.summary,
              "targets": config["create_in"], **found}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not found["done"] or found["missing"]:
        print(log, flush=True)
    return 0


def git_head() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run(records: Path, out: Path, require_denied: bool, env: Mapping[str, str]) -> int:
    """Start the harness with the canaries in its real environment, then read and judge what it wrote."""
    if not records.is_dir():
        print(f"::error::fw reach test: the records folder {records} does not exist; no probe ran", flush=True)
        return 1
    out.unlink(missing_ok=True)  # only what this run's probe writes is read
    child = {**env, CANARY_SECRET: secrets.token_hex(16), CANARY_PLAIN: secrets.token_hex(16), INNER: "1"}
    code = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--records", str(records), "--out",
                           str(out)], env=child).returncode
    if code != 0 or not out.is_file():
        print(f"::error::fw reach test: the probe did not run (exit {code}); nothing is recorded as denied", flush=True)
        return 1
    result = json.loads(out.read_text(encoding="utf-8"))
    result["head"] = git_head()
    result["run"] = {k: env.get(v) for k, v in (("id", "GITHUB_RUN_ID"), ("attempt", "GITHUB_RUN_ATTEMPT"),
                                                ("job", "GITHUB_JOB"), ("ref", "GITHUB_REF"))}
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, probe in result["probes"].items():
        for line in probe["lines"]:
            print(f"FW-REACH {name}: {line}", flush=True)
    for line in result["control"]:
        print(f"FW-REACH {CONTROL} (control): {line}", flush=True)
    if not result["control_ok"]:
        print("::error::fw reach test: the control could not write its own run directory, so no refusal proves "
              "anything; nothing is recorded as denied", flush=True)
        return 1
    if not result["done"] or result["missing"]:
        print(f"::error::fw reach test: the probe did not finish (missing {', '.join(result['missing']) or 'none'}; "
              f"{result['summary']}); nothing is recorded as denied", flush=True)
        return 1
    reached = [n for n, p in result["probes"].items() if not p["denied"]]
    if not reached:
        print(f"fw reach test: every probe denied ({len(PROBES)} probes under fw.test)", flush=True)
        return 0
    message = (f"fw reach test: seat C under fw.test is NOT confined: not denied in {', '.join(reached)} (account "
               f"{result['account']['user']})")
    if require_denied:
        print(f"::error::{message}; no trial ran", flush=True)
        return 1
    print(f"::warning::{message}. Recorded, not a gate: a live trial of a case that runs seat C stays refused "
          "(scripts/live_eval_ci.py, exit 6).", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test what seat C can reach under fw.test in this job, and record it.")
    parser.add_argument("--records", type=Path, required=True, help="the records folder seat C must not write")
    parser.add_argument("--out", type=Path, required=True, help="where the result is written (JSON)")
    parser.add_argument("--require-denied", action="store_true", help="fail unless every probe is denied")
    args = parser.parse_args(argv)
    if os.environ.get(INNER) == "1":
        return inner(args.records.resolve(), args.out.resolve())
    return run(args.records.resolve(), args.out.resolve(), args.require_denied, dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
