"""Turnaround report: T for each merged pull request, printed to stdout only.

Council record 2026-10-18 on the review loop (decision 5, item 1). T is the
time from the first head of a pull request whose required CI is all green to
its merge. Both ends come from GitHub: the completion time of the last required
CI job on that head (the newest run of each job counts, as in the review) and
the pull request's `merged_at`. T is split, from the call log and the loop's
events in `~/.nirmaan/pr-review/calls.jsonl`, into:

- review: model calls for key 1, key 2 and the Founder Proxy within T (their
  durations, retries included; reused verdicts take no time);
- fix: each fix round, from the start of the fixer call to the loop's "fixed"
  event (the fixer, the local checks and the push);
- founder or proxy wait: from each "stopped" event (the needs-founder label)
  to the next "resumed" event, or to the merge;
- update: from each "updated" event (the loop merged main into the branch) to
  the next "ci-green-seen" event;
- queue and CI: the rest (waiting for the loop and for CI on later heads).

Founder-class pull requests (the review script's founder-class block in the
body) are reported on their own line. The report writes no file; its figures
are internal and stay out of the repository.

Usage: python scripts/turnaround_report.py [--since YYYY-MM-DD] [--repo owner/name]
           [--required a,b,c] [--state-dir DIR]
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_review  # noqa: E402

REVIEW_KEYS = {1, 2, "proxy"}
FOUNDER_BLOCK = pr_review.FOUNDER_BLOCK_OPEN


def parse_time(text) -> datetime | None:
    if not text:
        return None
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def green_at(required: list[str], runs: list[dict]) -> datetime | None:
    """When the required CI finished green on one head, or None when it is not
    all green (the newest run of each job counts)."""
    if pr_review.required_ci(required, runs)["state"] != "green":
        return None
    times = []
    for name in required:
        newest = max((r for r in runs if r["name"] == name), key=pr_review._newest_first_key)
        times.append(parse_time(newest.get("completed_at")))
    return None if any(t is None for t in times) else max(times)


def turnaround(pull: dict, runs_by_sha: dict, log: list[dict], required: list[str]) -> dict | None:
    """T and its split for one merged pull request. `pull`: number, merged_at,
    body; `runs_by_sha`: its commits' check runs, in commit order; `log`: the
    call log lines of this repository. None when no head was ever green."""
    greens = [t for t in (green_at(required, runs) for runs in runs_by_sha.values()) if t is not None]
    merged = parse_time(pull.get("merged_at"))
    if not greens or merged is None:
        return None
    start = min(greens)
    mine = sorted(((parse_time(line.get("time")), line) for line in log if line.get("pr") == pull["number"]),
                  key=lambda x: x[0] or start)
    within = [(t, line) for t, line in mine if t is not None and start <= t <= merged]
    events = [(t, line) for t, line in within if line.get("kind") == "loop"]

    def next_event(after: datetime, name: str) -> datetime | None:
        return next((t for t, line in events if t > after and line.get("event") == name), None)

    review = sum((line.get("duration_ms") or 0) for _, line in within
                 if line.get("kind") is None and line.get("key") in REVIEW_KEYS and line.get("outcome") != "reused") / 1000
    fix = 0.0
    for t, line in within:
        if line.get("kind") is None and line.get("key") == "fixer":
            began = t - timedelta(milliseconds=line.get("duration_ms") or 0)
            done = next((u for u, e in events if u >= t and e.get("event") == "fixed" and e.get("round") == line.get("round")), None)
            fix += ((done or t) - began).total_seconds()
    wait = sum(((next_event(t, "resumed") or merged) - t).total_seconds() for t, line in events if line.get("event") == "stopped")
    update = sum(((next_event(t, "ci-green-seen") or t) - t).total_seconds() for t, line in events if line.get("event") == "updated")
    total = (merged - start).total_seconds()
    return {"pr": pull["number"], "founder_class": FOUNDER_BLOCK in (pull.get("body") or ""), "start": start, "merged": merged,
            "t": total, "review": review, "fix": fix, "wait": wait, "update": update,
            "queue": max(0.0, total - review - fix - wait - update)}


def percentile(values: list[float], q: float) -> float:
    """The nearest-rank percentile (q in 0..100) of a non-empty list."""
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]


def minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}m"


def render(rows: list[dict]) -> str:
    lines = []
    for r in sorted(rows, key=lambda r: r["merged"]):
        lines.append(f"#{r['pr']:<5} {'founder class' if r['founder_class'] else 'not founder class':<17} T {minutes(r['t']):>8}  "
                     f"review {minutes(r['review'])}  fix {minutes(r['fix'])}  founder/proxy wait {minutes(r['wait'])}  "
                     f"update {minutes(r['update'])}  queue and CI {minutes(r['queue'])}  "
                     f"(green {r['start'].isoformat()}, merged {r['merged'].isoformat()})")
    for label, founder in (("not founder class", False), ("founder class", True)):
        ts = [r["t"] for r in rows if r["founder_class"] is founder]
        lines.append(f"{label}: n={len(ts)}" + (f", median T {minutes(percentile(ts, 50))}, p90 T {minutes(percentile(ts, 90))}" if ts else ""))
    return "\n".join(lines)


def gh_json(args: list[str]):
    return json.loads(subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True, timeout=300).stdout)


def collect(repo: str, since: datetime, required: list[str], log: list[dict], gh=gh_json) -> list[dict]:
    rows = []
    for page in range(1, 11):
        pulls = gh([f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}"])
        for p in pulls:
            merged = parse_time(p.get("merged_at"))
            if merged is None or merged < since:
                continue
            shas = [c["sha"] for c in gh([f"repos/{repo}/pulls/{p['number']}/commits?per_page=100"])]
            runs_by_sha = {}
            for sha in shas:
                runs = gh([f"repos/{repo}/commits/{sha}/check-runs?per_page=100"])["check_runs"]
                runs_by_sha[sha] = [{"id": r.get("id"), "name": r["name"], "status": r["status"], "conclusion": r.get("conclusion"),
                                     "started_at": r.get("started_at"), "completed_at": r.get("completed_at")} for r in runs]
            row = turnaround({"number": p["number"], "merged_at": p["merged_at"], "body": p.get("body")}, runs_by_sha,
                             [line for line in log if line.get("repo") == repo], required)
            if row:
                rows.append(row)
        if len(pulls) < 100 or all((parse_time(p.get("updated_at")) or since) < since for p in pulls):
            break
    return rows


def read_log(state_dir: Path) -> list[dict]:
    path = Path(state_dir) / "calls.jsonl"
    out = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(raw))
            except ValueError:
                continue
    return out


def main(argv: list[str]) -> int:
    def arg(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    since = parse_time(arg("--since")) if arg("--since") else datetime.now(timezone.utc) - timedelta(days=7)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    repo = arg("--repo") or pr_review.CONFIG["repo"]
    required = arg("--required").split(",") if arg("--required") else pr_review.CONFIG["required_ci"]
    state_dir = Path(arg("--state-dir") or pr_review.defaults()["state_dir"])
    rows = collect(repo, since, required, read_log(state_dir))
    print(f"Turnaround for {repo}, merged since {since.isoformat()} (internal; not for the repository)")
    print(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
