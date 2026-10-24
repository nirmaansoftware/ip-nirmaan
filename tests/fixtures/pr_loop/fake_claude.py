#!/usr/bin/env python3
"""A fake `claude` for tests/test_pr_loop.py: answers the reviewer processes
and the fixer process. No model is called.

It reads scenario.json next to itself (the processes get a token-free
allowlisted environment, so nothing comes through the environment) and records
every call to calls.jsonl beside it.

scenario.json: {"reviews": [...], "fixes": [...]}, each list used in order (the
last entry repeats).
  review: {"verdict", "findings"?, "extra"?} or {"type": "rate_limit" | "session_limit" | "error"}
    ("extra" adds keys, such as the Founder Proxy's founder_reasons)
  fix: {"status"?, "edits"?: {path: text}, "not_addressed"?: [{id, reason}],
        "human_move"?: {"git_dir", "ref", "sha"}, "type"?: "rate_limit" | "session_limit" | "garbage"}
  session_limit is the plan's limit as claude reports it (subtype "success",
  is_error set); error is a failed call that is not a limit.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
scenario = json.loads((here / "scenario.json").read_text())
argv = sys.argv[1:]
is_fixer = "Edit" in argv[argv.index("--tools") + 1]
kind = "fixes" if is_fixer else "reviews"
counter = here / f"counter-{kind}.json"
n = json.loads(counter.read_text())["n"] if counter.exists() else 0
counter.write_text(json.dumps({"n": n + 1}))
entries = scenario.get(kind) or [{}]
r = entries[min(n, len(entries) - 1)]
stdin = sys.stdin.read()
with open(here / "calls.jsonl", "a") as handle:
    handle.write(json.dumps({"kind": kind, "argv": argv, "cwd": os.getcwd(), "env": sorted(os.environ), "stdin": stdin}) + "\n")


def ok(value):
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(value),
                      "structured_output": value, "usage": {"input_tokens": 100, "output_tokens": 20}, "modelUsage": {"fake-model": {}}}))


if r.get("type") == "rate_limit":
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "API Error: 429 rate limit exceeded"}))
elif r.get("type") == "session_limit":
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "You've hit your session limit \u00b7 resets 10pm (Asia/Calcutta)"}))
elif r.get("type") == "error":
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "the process crashed"}))
elif not is_fixer:
    head = re.search(r"Head SHA: ([0-9a-f]{40})", stdin).group(1)
    ok({"verdict": r.get("verdict", "pass"), "sha": head, "findings": r.get("findings", []),
        "checks_run": ["read the diff"], "not_run": ["simulation (no command tools)"], **r.get("extra", {})})
elif r.get("type") == "garbage":
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "I fixed it!"}))
else:
    findings = json.loads(re.search(r"# Findings to fix[^\n]*\n\n(.*?)\n\nFix the findings now", stdin, re.S).group(1))
    for path, text in (r.get("edits") or {}).items():
        target = Path(os.getcwd()) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    move = r.get("human_move")
    if move:
        subprocess.run(["git", "--git-dir", move["git_dir"], "update-ref", move["ref"], move["sha"]], check=True)
    not_addressed = r.get("not_addressed", [])
    skipped = {x["id"] for x in not_addressed}
    ok({"status": r.get("status", "fixed"), "addressed": [f["id"] for f in findings if f["id"] not in skipped],
        "not_addressed": not_addressed, "summary": "Changed what the findings asked for."})
