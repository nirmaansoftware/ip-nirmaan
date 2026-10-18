#!/usr/bin/env python3
"""A fake `claude` for tests/test_pr_review.py. No model is called.

It reads scenario.json next to itself (the reviewer's environment is an
allowlist, so the scenario cannot come through the environment), answers the
next response in order, and records each call to calls.jsonl beside it.
Response types: verdict, result, stdout, sleep, rate_limit, error. A verdict's
"extra" adds keys (such as the Founder Proxy's founder_reasons).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

here = Path(__file__).resolve().parent
scenario = json.loads((here / "scenario.json").read_text())
counter = here / "counter.json"
n = json.loads(counter.read_text())["n"] if counter.exists() else 0
counter.write_text(json.dumps({"n": n + 1}))
r = scenario["responses"][min(n, len(scenario["responses"]) - 1)]
stdin = sys.stdin.read()
with open(here / "calls.jsonl", "a") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "env": sorted(os.environ), "stdin": stdin}) + "\n")
m = re.search(r"Head SHA: ([0-9a-f]{40})", stdin)
head = m.group(1) if m else None


def ok(text):
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text,
                      "usage": {"input_tokens": 100, "output_tokens": 20}, "modelUsage": {"fake-model": {}}}))


kind = r["type"]
if kind == "verdict":
    ok(json.dumps({"verdict": r["verdict"], "sha": r.get("sha") or head, "findings": r.get("findings", []),
                   "checks_run": ["read the diff"], "not_run": ["simulation (no command tools)"], **r.get("extra", {})}))
elif kind == "result":
    ok(r["text"])
elif kind == "stdout":
    print(r["text"])
elif kind == "sleep":
    time.sleep(r["seconds"])
    ok("{}")
elif kind == "rate_limit":
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "API Error: 429 rate limit exceeded"}))
else:
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "something broke"}))
    sys.exit(1)
