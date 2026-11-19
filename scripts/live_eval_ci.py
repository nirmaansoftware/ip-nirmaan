"""Run live evaluation trials in GitHub Actions, one at a time (`.github/workflows/live-eval.yml`).

Cases whose seat output is executable code by design (cocotb tests, firmware) run only in CI, never on the
owner's machine. The workflow calls this script in two ways:

- ``check``: prints the harness fingerprint (``harness_sha256``) the trials will run in, for the case and the
  options given, with the Claude Code version read from the installed CLI. It refuses a CLI that is not the
  pinned one (`.github/live-eval/package.json`) and, with ``--require-expected``, a fingerprint that differs
  from the expected one.
- ``trials``: the same check, then ``nirmaan eval run <case> --trials 1`` once per trial, so every trial is its
  own record. It stops at once on exit 3 (a trial with no model answer, as on a plan or usage limit, RR5) or a
  limit line in the output, on any exit but 0 or 1, and when a record is not what was asked for. A stopped or
  failed trial is kept as it is and never run again; no later trial starts.
- ``confined`` (gate WF17: every job that runs seat code): exit 6 unless the case named by CASE runs no seat C or
  this job's credential test record (``FW_REACH``) shows it confined; the replay and re-judge steps run it before they
  run seat code.
- ``tree``: the checkout's tree hash (gate WF17): the commit, and every file git tracks or would add, plus every
  file under ``src/``, ``scripts/`` and ``evals/`` ignored or not, by path, type, mode and content. The workflow
  takes it before and after the trials and fails on any change; the counting re-judge refuses records from a job
  whose two hashes differ.

A live trial (``check --require-expected`` and ``trials``) of a case that runs seat-written C (``fw.build``,
``fw.test``, the firmware seat, or a whole flow with a firmware stage) is refused before anything runs. Since M90
``fw.test`` runs the program it builds as the seat account in these jobs (``scripts/live_eval_seat.py``), and the
credential test (``scripts/live_eval_fw_reach.py --require-denied``) gates every job that runs seat C; lifting this
refusal is a change of its own (for the register block flow, after gates WF15 to WF19 of the G3 council record).

A whole-flow case (``flow/...``, G3 council record 2026-11-17, decision 4) runs only when named, one trial per
dispatch (each dispatch is one slot of the committed batch plan), on the default harness, in the whole-flow
fingerprint (``harness_sha256(flow="whole")``); every record must carry ``flow: whole``. The register block flow
(``flow/axi4-lite-regs-driver``) has a firmware stage, so it stays refused (above); the timer flow
(``flow/axil-timer``) links no seat C and runs.

The options come from the environment (CASE, TRIALS, KNOWLEDGE, PURPOSE, HARNESS, EXPECTED), as the workflow
sets them, so no input is expanded inside a shell command. Nothing here prints a credential. Exit codes: 0 every
trial ran (passed or failed), 2 bad input, 3 stopped on a limit, 4 fingerprint or record mismatch, 5 stopped on
another exit, 6 a case that runs seat C refused (above, and ``confined``). See docs/LIVE_EVAL_EVIDENCE.md, section 6.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_FILE = ROOT / ".github" / "live-eval" / "package.json"
CLI_PACKAGE = "@anthropic-ai/claude-code"
#: The wording of a plan, usage or spend limit, in case a limit ever comes back without exit 3.
LIMIT = re.compile(r"hit your .*limit|usage limit|spend(ing)? limit", re.IGNORECASE)
MAX_TRIALS = 20
BAD_INPUT, STOPPED_LIMIT, MISMATCH, STOPPED_OTHER, UNCONFINED = 2, 3, 4, 5, 6
#: Tools that build or run seat-written C, and the seat that uses them: a live trial of a case with either is refused.
#: regmap.verify, fw.soc_test and Verilator's --binary run no seat-written host code (docs/LIVE_EVAL_EVIDENCE.md, 6).
SEAT_C_TOOLS, SEAT_C_SEATS = ("fw.build", "fw.test"), ("firmware",)
#: Where a step that runs seat code finds its job's credential test record (``live_eval_fw_reach.py --out``).
FW_REACH_ENV = "FW_REACH"
#: Folders hashed whole, ignored files included: the judge's code, the scripts the workflow runs, the cases.
TREE_WHOLE = ("src", "scripts", "evals")
NIRMAAN = ("nirmaan",)

Runner = Callable[[Sequence[str]], tuple[int, str]]


class Stop(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def pinned_cli() -> str:
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))["dependencies"][CLI_PACKAGE]


def installed_cli() -> str | None:
    from nirmaan.runtime.claude_code import find_claude, read_version

    executable = find_claude()
    return read_version(executable) if executable else None


def options(env: dict[str, str]) -> dict:
    """The run's options from the environment, each checked before anything runs."""
    from nirmaan.evals.records import PURPOSES
    from nirmaan.runtime.harness import VARIANTS

    case = env.get("CASE", "").strip()
    known = {c.id: c.flow for c in _cases()}  # G3: a whole-flow case is known only when named
    if case not in known:
        raise Stop(BAD_INPUT, f"unknown case {case!r}; name one case ID from `nirmaan eval list` or a whole-flow case")
    trials = env.get("TRIALS", "1").strip()
    if not trials.isdigit() or not 1 <= int(trials) <= MAX_TRIALS:
        raise Stop(BAD_INPUT, f"trials must be a whole number from 1 to {MAX_TRIALS}, not {trials!r}")
    knowledge = env.get("KNOWLEDGE", "on").strip()
    if knowledge not in ("on", "off"):
        raise Stop(BAD_INPUT, f"knowledge must be on or off, not {knowledge!r}")
    purpose = env.get("PURPOSE", "evidence").strip()
    if purpose not in PURPOSES:
        raise Stop(BAD_INPUT, f"unknown purpose {purpose!r}; known: {', '.join(PURPOSES)}")
    harness = env.get("HARNESS", "default").strip()
    if harness not in VARIANTS:
        raise Stop(BAD_INPUT, f"unknown harness variant {harness!r}; known: {', '.join(VARIANTS)}")
    if known[case] == "whole" and (int(trials) != 1 or harness != "default"):
        raise Stop(BAD_INPUT, f"a whole-flow case runs one trial per dispatch on the default harness (gate WF9; each "
                              f"dispatch is one slot of the batch plan), not trials {trials} on harness {harness}")
    return {"case": case, "trials": int(trials), "knowledge": knowledge, "purpose": purpose, "harness": harness,
            "expected": env.get("EXPECTED", "").strip(), "flow": known[case]}


def _cases() -> list:
    from nirmaan.evals import load_cases

    return load_cases(ROOT / "evals", flow=None)


def fw_reach_problem(env: Mapping[str, str], head: str | None) -> str | None:
    """Why the credential test record named by ``FW_REACH`` does not show, for this job, that seat C under
    ``fw.test`` runs confined, or None. Every field is required; a record that says nothing proves nothing."""
    where = env.get(FW_REACH_ENV, "").strip()
    if not where:
        return f"no credential test record ({FW_REACH_ENV} is not set)"
    try:
        record = json.loads(Path(where).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"the credential test record {where} cannot be read ({type(exc).__name__})"
    run = record.get("run") or {}
    want = {"id": env.get("GITHUB_RUN_ID"), "attempt": env.get("GITHUB_RUN_ATTEMPT"), "job": env.get("GITHUB_JOB")}
    if not all(want.values()) or any(run.get(k) != v for k, v in want.items()):
        return f"the credential test record is not this job's (run {run}, this job {want})"
    if not head or record.get("head") != head:
        return f"the credential test record is of commit {record.get('head')}, not this checkout's {head}"
    if record.get("format") != "nirmaan.fw-reach/1" or record.get("tool") != "fw.test":
        return "the credential test record is not one of scripts/live_eval_fw_reach.py's"
    if record.get("require_denied") is not True:
        return "the credential test ran without --require-denied"
    if not (record.get("every_probe_denied") is True and record.get("done") is True and record.get("control_ok") is True
            and record.get("missing") == [] and record.get("seat_exec")):
        return "the credential test record does not show every probe denied with the seat wrapper in use"
    return None


def _head() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def seat_c_use(case_id: str) -> str | None:
    """What of this case runs seat-written C (its tools and seats), or None when nothing does.

    A whole flow seats every stage it lists, so a firmware stage anywhere in it runs seat C at its own
    before-review checks, whichever stage is judged."""
    case = next(c for c in _cases() if c.id == case_id)
    tools = sorted({h.tool for h in case.held_out if h.tool in SEAT_C_TOOLS})
    seats = sorted({case.seat, *(case.exercised if case.flow == "whole" else ())} & set(SEAT_C_SEATS))
    what = [*tools, *(f"the {s} stage" if case.flow == "whole" else f"the {s} seat" for s in seats)]
    return ", ".join(what) or None


def confined_problem(case_id: str, env: Mapping[str, str] | None = None) -> str | None:
    """Why this job may not run this case's seat code, or None (``confined``).

    Gate WF17 (G3 council record 2026-11-17, second addendum, decision 2, item 1) covers every job that runs seat
    code, so every job that runs seat C (the replay of a reference answer, the counting re-judge) runs it only after
    the credential test of that same job showed it confined (``fw_reach_problem``). A case that runs no seat C needs
    nothing more than the cocotb reach test."""
    what = seat_c_use(case_id)
    if what is None:
        return None
    problem = fw_reach_problem(os.environ if env is None else env, _head())
    if problem is None:
        return None
    return (f"case {case_id} runs seat-written C ({what}); this job runs it only after its own credential test shows "
            f"seat C confined under fw.test (gate WF17, M90): {problem}. Nothing ran")


def seat_c_problem(case_id: str) -> str | None:
    """Why a live trial of this case, which runs seat C, is refused, or None (``seat_c_use``)."""
    what = seat_c_use(case_id)
    if what:
        return (f"case {case_id} runs seat-written C ({what}); live trials of it stay refused (gate WF17: fw.test runs "
                "it as the seat account since M90, and only a change of its own lifts this; for the register block "
                "flow, after gates WF15 to WF19). No trial ran")
    return None


def tree_manifest(root: Path, run: Callable[[Sequence[str]], str] | None = None) -> list[str]:
    """One line per file: path, type, mode and content hash (a link: its target). The commit comes first."""
    def git(args: Sequence[str]) -> str:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout

    run = run or git
    paths = {p for p in run(["ls-files", "-z", "--cached", "--others", "--exclude-standard"]).split("\0") if p}
    for top in TREE_WHOLE:
        for folder, dirs, files in os.walk(root / top):
            dirs.sort()
            paths.update(str((Path(folder) / f).relative_to(root)) for f in files)
            paths.update(str((Path(folder) / d).relative_to(root)) for d in dirs if (Path(folder) / d).is_symlink())
    lines = [f"commit {run(['rev-parse', 'HEAD']).strip()}"]
    for rel in sorted(paths):
        path = root / rel
        try:
            info = path.lstat()
        except FileNotFoundError:
            lines.append(f"missing {rel}")
            continue
        mode = f"{info.st_mode & 0o7777:o}"
        if path.is_symlink():
            lines.append(f"link {mode} {rel} -> {os.readlink(path)}")
        elif path.is_file():
            lines.append(f"file {mode} {rel} {hashlib.sha256(path.read_bytes()).hexdigest()}")
        else:
            lines.append(f"other {mode} {rel}")
    return lines


def tree_digest(lines: Sequence[str]) -> str:
    return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def check(opts: dict, *, require_expected: bool, cli: str | None) -> str:
    """The fingerprint the trials will run in; refuses a CLI other than the pin, or a fingerprint not expected."""
    from nirmaan.runtime.harness import harness_sha256

    pin = pinned_cli()
    if cli != pin:
        raise Stop(MISMATCH, f"Claude Code is {cli or 'not installed'}, not the pinned {pin}")
    flow = opts.get("flow", "seat")
    digest = harness_sha256(knowledge=opts["knowledge"] == "on", cli=cli, variant=opts["harness"], flow=flow)
    print(f"harness: {digest} (case {opts['case']}, harness {opts['harness']}, knowledge {opts['knowledge']}, "
          f"purpose {opts['purpose']}, flow {flow}, Claude Code {cli})", flush=True)
    if require_expected and not opts["expected"]:
        raise Stop(BAD_INPUT, "name the expected harness fingerprint (sha256:...) before any trial runs")
    if opts["expected"] and opts["expected"] != digest:
        raise Stop(MISMATCH, f"harness fingerprint {digest} is not the expected {opts['expected']}; no trial ran")
    return digest


def command(opts: dict, out: Path) -> list[str]:
    argv = [*NIRMAAN, "eval", "run", opts["case"], "--runtime", "claude-code", "--trials", "1",
            "--purpose", opts["purpose"], "--out", str(out)]
    if opts["knowledge"] == "off":
        argv.append("--without-knowledge")
    if opts["harness"] != "default":
        argv += ["--harness", opts["harness"]]
    return argv


def record_problem(record: Path, opts: dict, digest: str, cli: str) -> str | None:
    """Why the record a trial wrote is not the trial that was asked for, or None."""
    from nirmaan.evals.records import trial_path

    path = trial_path(record, opts["case"], 1)
    if not path.is_file():
        return f"no trial file {path.relative_to(record)} in {record.name}"
    trial = json.loads(path.read_text(encoding="utf-8"))
    result = trial.get("result") or {}
    seen = {"purpose": trial.get("purpose"), "knowledge": trial.get("knowledge"),
            "harness variant": trial.get("harness_variant"), "harness": result.get("harness"),
            "Claude Code": result.get("cli"), "flow": trial.get("flow", "seat")}
    wanted = {"purpose": opts["purpose"], "knowledge": opts["knowledge"], "harness variant": opts["harness"],
              "harness": digest, "Claude Code": cli, "flow": opts.get("flow", "seat")}
    wrong = [f"{k} {seen[k]!r}, expected {wanted[k]!r}" for k in wanted if seen[k] != wanted[k]]
    answers = [a if isinstance(a, dict) else {} for a in trial.get("answers") or []]
    wrong += [f"an answer's harness {a.get('harness')!r}" for a in answers if a.get("harness") != digest]
    return "; ".join(wrong) or None


def stream(argv: Sequence[str]) -> tuple[int, str]:
    """Run one ``eval run``, printing its output as it comes, and return its exit code and output."""
    lines: list[str] = []
    with subprocess.Popen(list(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
    return proc.returncode, "".join(lines)


def run_trials(opts: dict, out: Path, digest: str, cli: str, run: Runner = stream) -> int:
    """Each trial once, in order; the first stop ends the batch. Returns 0 when every trial ran."""
    out.mkdir(parents=True, exist_ok=True)
    n, passed = opts["trials"], 0
    for number in range(1, n + 1):
        print(f"--- trial {number} of {n}: {opts['case']}", flush=True)
        before = set(out.iterdir())
        code, output = run(command(opts, out))
        made = sorted(set(out.iterdir()) - before)
        tail = (f"Trials {number + 1} to {n} did not start." if number + 1 < n
                else f"Trial {n} did not start." if number < n else "")
        if code == STOPPED_LIMIT or LIMIT.search(output):
            raise Stop(STOPPED_LIMIT, f"STOP: trial {number} hit a plan or usage limit (exit {code}). It is "
                                      f"recorded as failed and is never run again. {tail}".strip())
        if code not in (0, 1):
            raise Stop(STOPPED_OTHER, f"STOP: trial {number} ended with exit {code}. It is a failed trial and is "
                                      f"never run again. {tail}".strip())
        if len(made) != 1:
            raise Stop(MISMATCH, f"STOP: trial {number} wrote {len(made)} records, not 1. {tail}".strip())
        problem = record_problem(made[0], opts, digest, cli)
        if problem:
            raise Stop(MISMATCH, f"STOP: trial {number} record {made[0].name}: {problem}. {tail}".strip())
        passed += code == 0
        print(f"trial {number} of {n}: {'PASS' if code == 0 else 'FAIL'} -> {made[0].name}", flush=True)
    print(f"done: {n} of {n} trials ran, {passed} passed", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    # Not the module docstring: ``python -OO`` strips it to None.
    parser = argparse.ArgumentParser(description="Run live evaluation trials in GitHub Actions, one at a time.")
    sub = parser.add_subparsers(dest="mode", required=True)
    one = sub.add_parser("check", help="print the harness fingerprint and check it")
    one.add_argument("--require-expected", action="store_true")
    many = sub.add_parser("trials", help="run the trials one at a time")
    many.add_argument("--out", type=Path, required=True)
    sub.add_parser("confined", help="exit 6 unless this job's credential test shows the case's seat C confined")
    tree = sub.add_parser("tree", help="print the checkout's tree hash")
    tree.add_argument("--write", type=Path, help="also write the manifest the hash is taken over")
    args = parser.parse_args(argv)
    if args.mode == "tree":
        lines = tree_manifest(ROOT)
        if args.write:
            args.write.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(tree_digest(lines), flush=True)
        return 0
    if args.mode == "confined":  # gate WF17: the replay and re-judge steps, before they run seat code
        case = os.environ.get("CASE", "").strip()
        if not case:
            print("name the case (CASE) whose seat code this job runs", file=sys.stderr, flush=True)
            return BAD_INPUT
        try:
            problem = confined_problem(case)
        except StopIteration:
            print(f"unknown case {case!r}", file=sys.stderr, flush=True)
            return BAD_INPUT
        if problem:
            print(f"::error::{problem}", file=sys.stderr, flush=True)
            return UNCONFINED
        print(f"case {case}: " + ("seat C confined by this job's credential test" if seat_c_use(case)
                                  else "runs no seat C"), flush=True)
        return 0
    try:
        opts = options(dict(os.environ))
        cli = installed_cli()
        live = args.mode == "trials" or getattr(args, "require_expected", False)
        digest = check(opts, require_expected=live, cli=cli)
        unconfined = seat_c_problem(opts["case"]) if live else None
        if unconfined:
            raise Stop(UNCONFINED, unconfined)
        if args.mode == "check":
            return 0
        return run_trials(opts, args.out, digest, cli or "")
    except Stop as stop:
        print(stop, file=sys.stderr, flush=True)
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
