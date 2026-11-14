"""The review loop in GitHub Actions: state sync and the job's own checks.

How it runs and the founder's switch-on steps: docs/REVIEW_MECHANISM.md
("Running the loop in GitHub Actions"). The workflow is
.github/workflows/review-loop.yml. It changes nothing about a review: the job
runs main's scripts/pr_loop.py --once, exactly as the Mac's launchd job does.

The loop's state lives in the private repository nirmaansoftware/nirmaan-loop-state
(branch main), written through a deploy key scoped to that repository alone:

    <writer>/writer.json        marks the folder seeded (written once, by `seed`)
    <writer>/loop/<owner>_<repo>-pr-<n>.json
                                per pull request loop state (as ~/.nirmaan/pr-review/loop/)
    <writer>/verdicts/<owner>_<repo>/pr-<n>/<head>-<main>-k<key>-<team>-<lead>.json
                                the verdict cache (as ~/.nirmaan/pr-review/verdicts/)
    <writer>/calls/<YYYY-MM>.jsonl
                                append only: this loop's calls.jsonl lines, by the month of their time
    <writer>/pause.json         the last rate-limit pause this loop set (the loop's pause format)

<writer> is the repository's name (`ip-nirmaan` here; `Nirmaan` for the Nirmaan
loop if it moves too). Each loop writes only its own folder and reads every
folder, so no file has two writers: a push that loses a race rebases onto the
other loop's commit without a conflict and tries again. The shared pause is
the latest `until` still in force across every `*/pause.json`.

Subcommands (each exits non-zero with a reason on failure):

    app-token   mint the review App's installation token (the key only in a temp file
                for the call), mask it and write it as the step output `token`
    pull        clone the state repository and lay the state out as the loop expects
    has-work    `work=true|false`: an open pull request the loop would step, or a
                finished one not yet noted closed
    auth-check  the claude CLI, started as every review call is, is logged in with the
                plan's OAuth token and one tiny call answers; --deny-probe also asks a model to read
                /proc/self/status and passes only if the read is denied, then checks that no
                readable process environment holds a secret and the check account cannot
                read the loop's
    run         the loop once (pr_loop.py --once; --shadow N: --no-post on pull request N),
                with the step's secrets moved out of the environment first
    push        write this loop's state back, commit, push, rebase and retry
    seed        once, before the switch: the Mac's state for this repository into a clone

Usage: python scripts/loop_cloud.py <subcommand> [--clone DIR] [--state-dir DIR] [--from DIR] [--deny-probe] [--shadow N]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_loop  # noqa: E402
import pr_review  # noqa: E402

REPO = pr_review.CONFIG["repo"]
WRITER = REPO.split("/")[1]
PREFIX = REPO.replace("/", "_")
STATE_REMOTE = os.environ.get("NIRMAAN_LOOP_STATE_REMOTE") or "git@github.com:nirmaansoftware/nirmaan-loop-state.git"
# GitHub's published SSH host key (docs.github.com, "GitHub's SSH key fingerprints").
GITHUB_HOST_KEY = "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
COMMITTER = ("-c", "user.name=Nirmaan review loop", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com")
PUSH_TRIES = 5
USAGE = "python scripts/loop_cloud.py (app-token | pull | has-work | auth-check | run | push | seed) [--clone DIR] [--state-dir DIR] [--from DIR] [--deny-probe] [--shadow N]"


class SyncError(RuntimeError):
    pass


def git(cwd, *args) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SyncError(f"git {' '.join(args[:2])} failed: {pr_review.redact(proc.stderr.strip())[:300]}")
    return proc.stdout


def output(name: str, value: str):
    """A step output (GITHUB_OUTPUT), or stdout outside Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


# --- The state layout ---------------------------------------------------------------


def _until(text: str):
    try:
        return datetime.fromisoformat(str(json.loads(text)["until"]).replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError):
        return None


def shared_pause(clone: Path, now: datetime | None = None) -> str | None:
    """The pause in force with the latest `until` across every loop's pause.json."""
    now = now or datetime.now(timezone.utc)
    best = None
    for path in sorted(Path(clone).glob("*/pause.json")):
        text = path.read_text(encoding="utf-8")
        until = _until(text)
        if until and until > now and (best is None or until > best[0]):
            best = (until, text)
    return best[1] if best else None


def import_state(clone: Path, state_dir: Path, writer: str = WRITER, prefix: str = PREFIX):
    """The state folder the loop expects, from the clone: this loop's per pull
    request state and verdict cache, and the shared pause. calls.jsonl starts
    empty, so `push` appends only this run's lines."""
    own = Path(clone) / writer
    if not (own / "writer.json").is_file():
        raise SyncError(f"{writer}/ is not seeded in the state repository (no writer.json); run `seed` first")
    loop_dir = Path(state_dir) / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((own / "loop").glob(f"{prefix}-pr-*.json")):
        shutil.copy2(path, loop_dir / path.name)
    verdicts = own / "verdicts" / prefix
    if verdicts.is_dir():
        shutil.copytree(verdicts, Path(state_dir) / "verdicts" / prefix, dirs_exist_ok=True)
    pause = shared_pause(clone)
    if pause:
        (loop_dir / "rate-limit-pause.json").write_text(pause, encoding="utf-8")


def export_state(clone: Path, state_dir: Path, repo: str = REPO, writer: str = WRITER, prefix: str = PREFIX,
                 calls: bool = True, runner: str = "github-actions"):
    """This loop's state into its own folder of the clone, and nothing outside it:
    the per pull request state and verdicts mirrored exactly, the pause only when
    this loop set it (its `repo` is this one and it is new), and calls.jsonl lines
    for this repository appended to the month files."""
    state_dir, own = Path(state_dir), Path(clone) / writer
    own.mkdir(parents=True, exist_ok=True)
    marker = own / "writer.json"
    if not marker.exists():
        marker.write_text(json.dumps({"writer": writer, "repo": repo, "runner": runner}, indent=2) + "\n", encoding="utf-8")
    (own / "loop").mkdir(exist_ok=True)
    for path in (own / "loop").glob(f"{prefix}-pr-*.json"):
        path.unlink()
    for path in sorted((state_dir / "loop").glob(f"{prefix}-pr-*.json")):
        shutil.copy2(path, own / "loop" / path.name)
    shutil.rmtree(own / "verdicts" / prefix, ignore_errors=True)
    if (state_dir / "verdicts" / prefix).is_dir():
        shutil.copytree(state_dir / "verdicts" / prefix, own / "verdicts" / prefix)
    local = state_dir / "loop" / "rate-limit-pause.json"
    if local.is_file():
        text = local.read_text(encoding="utf-8")
        try:
            mine = json.loads(text).get("repo") == repo
        except (ValueError, AttributeError):
            mine = False
        current = own / "pause.json"
        if mine and _until(text) and (not current.is_file() or current.read_text(encoding="utf-8") != text):
            current.write_text(text, encoding="utf-8")
    log = state_dir / "calls.jsonl"
    if calls and log.is_file():
        months: dict[str, list[str]] = {}
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("repo") == repo:
                month = str(record.get("time") or datetime.now(timezone.utc).isoformat())[:7]
                months.setdefault(month, []).append(line)
        if months:
            (own / "calls").mkdir(exist_ok=True)
        for month, lines in sorted(months.items()):
            with open(own / "calls" / f"{month}.jsonl", "a", encoding="utf-8") as handle:
                handle.write("".join(f"{line}\n" for line in lines))


def commit_and_push(clone: Path, writer: str = WRITER, message: str | None = None, tries: int = PUSH_TRIES,
                    sleep=time.sleep) -> bool:
    """Commit this loop's folder and push; on a rejected push fetch, rebase onto
    the other loop's commits (they touch other folders, so it is clean) and try
    again. A conflict means a second writer for this folder: it stops, loudly.
    Returns False when there was nothing to commit."""
    git(clone, "add", "-A", "--", writer)
    if not git(clone, "status", "--porcelain", "--", writer).strip():
        return False
    git(clone, *COMMITTER, "commit", "--quiet", "--no-verify", "-m",
        message or f"{writer}: loop state after run {os.environ.get('GITHUB_RUN_ID') or 'local'}")
    for attempt in range(tries):
        proc = subprocess.run(["git", "push", "--quiet", "origin", "HEAD:refs/heads/main"], cwd=clone, capture_output=True, text=True)
        if proc.returncode == 0:
            return True
        if attempt == tries - 1:
            raise SyncError(f"push rejected {tries} times: {pr_review.redact(proc.stderr.strip())[:300]}")
        sleep(2 ** attempt)
        git(clone, "fetch", "--quiet", "origin", "main")
        rebase = subprocess.run(["git", *COMMITTER, "rebase", "--quiet", "FETCH_HEAD"], cwd=clone, capture_output=True, text=True)
        if rebase.returncode != 0:
            subprocess.run(["git", "rebase", "--abort"], cwd=clone, capture_output=True)
            raise SyncError(f"rebase onto the state repository conflicted: something else wrote {writer}/ (one writer per folder)")
    return True


def clone_state(clone: Path, remote: str = STATE_REMOTE):
    git(Path(clone).parent, "clone", "--quiet", "--filter=blob:none", "--branch", "main", remote, str(clone))


# --- Pull requests to step ------------------------------------------------------------


def has_work(pulls: list[dict], state_dir: Path, cfg: dict = pr_review.CONFIG, lc: dict = pr_loop.LOOP) -> bool:
    """Whether a pass would do anything (the loop's own skip rules, read without
    a model call): an open pull request it would step, a stop still to post, or
    a pull request it finished that is no longer open (the `merged` event)."""
    skip_labels = {cfg["hold_label"], lc["needs_founder_label"], lc.get("stalled_label")} - {None}
    for p in pulls:
        if p["draft"] or p["head_repo"] != cfg["repo"] or p["base_ref"] != cfg["base_branch"] or p["author"] not in lc["authors"]:
            continue
        stopped = pr_loop.load_state(state_dir, cfg["repo"], p["number"]).get("stopped")
        if stopped and stopped.get("visible") is False and stopped.get("head") == p["head_sha"]:
            return True
        if not skip_labels & set(p["labels"]):
            return True
    numbers = {p["number"] for p in pulls}
    for path in sorted((Path(state_dir) / "loop").glob(f"{cfg['repo'].replace('/', '_')}-pr-*.json")):
        try:
            st = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        done = st.get("done") or {}
        if st.get("pr") not in numbers and done.get("outcome") in ("auto-merge", "ready") and not st.get("closed"):
            return True
    return False


# --- The job's own checks -------------------------------------------------------------


def auth_status(binary: str) -> tuple[bool, str]:
    """`claude auth status --json` (no model call), started as every review call
    is (pr_review.run_claude): logged in by the OAuth token from the pipe."""
    if not pr_review._PLAN_TOKEN:
        return False, "no plan token was handed over"
    proc = pr_review.run_claude(binary, ["auth", "status", "--json"], "", os.getcwd(), 120)
    try:
        status = json.loads(proc.stdout)
    except ValueError:
        return False, f"claude auth status gave no JSON (exit {proc.returncode})"
    if status.get("loggedIn") is True and status.get("authMethod") == "oauth_token":
        return True, "logged in with the OAuth token"
    return False, f"not logged in with the OAuth token (loggedIn={status.get('loggedIn')}, authMethod={status.get('authMethod')})"


OK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}


def login_call(binary: str, cwd: str) -> tuple[bool, str]:
    """One tiny model call (`auth status` does not ask the server, so a revoked
    token would otherwise reach a review and stop a pull request)."""
    args = pr_review.claude_args("haiku", "Answer with ok set to true.", [], OK_SCHEMA)
    proc = pr_review.run_claude(binary, args, "Answer.", cwd, 300)
    result = pr_review.interpret(proc.returncode, proc.stdout, proc.stderr)
    if result["kind"] == "ok":
        return True, "logged in with the OAuth token; the plan answered"
    return False, f"the plan did not answer ({result['kind']}: {pr_review.redact(result.get('error'))[:200]})"


DENY_PROMPT = ("Use the Read tool on /proc/self/status. Then answer: read is true only if the tool returned the "
               "file's contents, and first_line is its first line (empty if it did not).")
DENY_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["read", "first_line"],
               "properties": {"read": {"type": "boolean"}, "first_line": {"type": "string"}}}


def deny_probe(binary: str, cwd: str) -> tuple[bool, str]:
    """One small model call with the reviewers' exact tool rules: /proc must be denied."""
    args = pr_review.claude_args("haiku", "You test a tool permission. Do only what the user asks.", [], DENY_SCHEMA)
    proc = pr_review.run_claude(binary, args, DENY_PROMPT, cwd, 300)
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return False, f"claude gave no JSON (exit {proc.returncode})"
    denied = [d for d in data.get("permission_denials") or [] if "/proc" in json.dumps(d.get("tool_input"))]
    answer = data.get("structured_output") or {}
    if denied and not answer.get("read") and "Name:" not in str(answer.get("first_line")):
        return True, "the read of /proc was denied"
    return False, f"the read of /proc was not denied (denials={len(denied)}, answer={str(answer)[:120]})"


# --- Secrets out of the environment ---------------------------------------------------

# What GitHub gives a step only as environment variables. `run` and `auth-check`
# start again without them (handoff), so the loop's /proc/<pid>/environ, all a
# process of the same account could read, holds none; the loop keeps them in
# memory and hands the plan token to each claude process through a pipe.
SECRET_NAMES = ("CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", pr_review.APP_TOKEN_ENV)
SECRETS_FD_ENV = "NIRMAAN_LOOP_SECRETS_FD"


def handoff(argv: list[str], env=None, execve=os.execve):
    env = dict(os.environ if env is None else env)
    secrets = {k: env.pop(k) for k in SECRET_NAMES if k in env}
    r, w = os.pipe()
    os.write(w, json.dumps(secrets).encode())
    os.close(w)
    os.set_inheritable(r, True)
    env[SECRETS_FD_ENV] = str(r)
    execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *argv], env)


_HELD: list[str] = []


def take_secrets():
    """Stage two: read the pipe once, then the plan token stays in memory and
    the GitHub tokens go only to the environment this process gives gh and git."""
    with os.fdopen(int(os.environ.pop(SECRETS_FD_ENV)), encoding="utf-8") as handle:
        secrets = json.load(handle)
    _HELD[:] = [v for v in secrets.values() if v]
    pr_review.set_plan_token(secrets.get("CLAUDE_CODE_OAUTH_TOKEN"))
    for name in ("GH_TOKEN", pr_review.APP_TOKEN_ENV):
        if secrets.get(name):
            os.environ[name] = secrets[name]


def environ_holders(values: list[str]) -> list[str]:
    """Every /proc/<pid>/environ this account can read that holds one of `values`."""
    hits = []
    for path in sorted(Path("/proc").glob("[0-9]*/environ")):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        hits += [str(path) for v in values if v and v.encode() in data]
    return hits


def isolation_check(user: str | None) -> tuple[bool, str]:
    """On the runner (`check` mode): after the handoff no readable process
    environment holds a secret, and the check account cannot read this one's."""
    if not Path("/proc/self/environ").exists():
        return False, "no /proc here (the isolation check is for the Linux runner)"
    hits = environ_holders(_HELD)
    if hits:
        return False, f"a secret is in a readable process environment ({', '.join(hits[:5])})"
    if not user:
        return False, "NIRMAAN_LOOP_CHECK_USER is not set"
    with tempfile.TemporaryDirectory() as tmp:
        os.chmod(tmp, 0o755)
        readable, detail = pr_loop._run_commands([["cat", f"/proc/{os.getpid()}/environ"]], tmp, {}, {}, 60, user)
    if readable or "Permission denied" not in detail:
        return False, f"the check account could read the loop's environment ({detail[:120] or 'it read it'})"
    return True, "no readable process environment holds a secret; the check account cannot read the loop's"


# --- Commands -------------------------------------------------------------------------


def cmd_app_token():
    app_id, key = os.environ.get("REVIEW_APP_ID"), os.environ.get("REVIEW_APP_PRIVATE_KEY")
    if not app_id or not key:
        raise SyncError("REVIEW_APP_ID and REVIEW_APP_PRIVATE_KEY must be set (environment secrets)")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "app.pem"
        path.touch(mode=0o600)
        path.write_text(key if key.endswith("\n") else key + "\n", encoding="utf-8")
        token = pr_review.installation_token({"app_id": app_id, "installation_id": os.environ.get("REVIEW_APP_INSTALLATION_ID") or None,
                                              "key_file": str(path)}, REPO)
    print(f"::add-mask::{token}")
    output("token", token)


def main(argv: list[str]) -> int:
    def arg(name):
        return Path(argv[argv.index(name) + 1]).expanduser() if name in argv and argv.index(name) + 1 < len(argv) else None
    cmd = argv[0] if argv else ""
    if cmd in ("run", "auth-check"):
        if SECRETS_FD_ENV not in os.environ:
            handoff(argv)
        take_secrets()
    clone, state_dir, source = arg("--clone"), arg("--state-dir"), arg("--from")
    try:
        if cmd == "app-token":
            cmd_app_token()
        elif cmd == "pull" and clone and state_dir:
            clone_state(clone)
            import_state(clone, state_dir)
            print(f"loop-cloud: state pulled ({len(list((state_dir / 'loop').glob(f'{PREFIX}-pr-*.json')))} pull request files)")
        elif cmd == "has-work" and state_dir:
            token = os.environ.get(pr_review.APP_TOKEN_ENV) or pr_review._gh_token()
            work = has_work(pr_review.GitHub(REPO, token).list_open_pulls(), state_dir)
            print(f"loop-cloud: {'work to do' if work else 'nothing to step'}")
            output("work", "true" if work else "false")
        elif cmd == "run":
            shadow = argv[argv.index("--shadow") + 1] if "--shadow" in argv and argv.index("--shadow") + 1 < len(argv) else None
            if shadow is not None and not shadow.isdigit():
                raise SyncError("--shadow takes one pull request number")
            return pr_loop.main(["--once", *(["--no-post", "--pr", shadow] if shadow else [])])
        elif cmd == "auth-check":
            binary = pr_review.defaults()["claude_bin"]
            ok, why = auth_status(binary)
            if ok:
                ok, why = login_call(binary, os.getcwd())
            if ok and "--deny-probe" in argv:
                ok, why = deny_probe(binary, os.getcwd())
            if ok and "--deny-probe" in argv:
                ok, why = isolation_check(os.environ.get("NIRMAAN_LOOP_CHECK_USER"))
            print(f"loop-cloud: auth-check: {why}")
            return 0 if ok else 1
        elif cmd == "push" and clone and state_dir:
            export_state(clone, state_dir)
            print("loop-cloud: state pushed" if commit_and_push(clone) else "loop-cloud: no state change")
        elif cmd == "seed" and clone and source:
            if (clone / WRITER / "writer.json").exists():
                raise SyncError(f"{WRITER}/ is already seeded; seed runs once")
            export_state(clone, source, calls=False, runner="seed")
            commit_and_push(clone, message=f"{WRITER}: seed from the Mac's loop state")
            print(f"loop-cloud: seeded {WRITER}/")
        else:
            print(f"usage: {USAGE}", file=sys.stderr)
            return 2
    except (SyncError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"loop-cloud: {cmd}: {pr_review.redact(str(exc))[:500]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
