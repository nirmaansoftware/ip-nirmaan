"""Decide whether a dispatched live evaluation runs (M45, W2-L1-CI).

The live job of `.github/workflows/live-eval.yml` runs this first. It runs
trials only when CLAUDE_CODE_OAUTH_TOKEN, a secret of the `live-eval`
environment (from `claude setup-token`, so the run uses the owner's Claude
plan), is present. Without it, it writes `enabled=false` to $GITHUB_OUTPUT
and the job stops before anything is installed or spent. It never prints the
secret. See docs/LIVE_EVAL_EVIDENCE.md.
"""

from __future__ import annotations

import os
import sys

SECRET = "CLAUDE_CODE_OAUTH_TOKEN"


def main() -> int:
    enabled = bool(os.environ.get(SECRET, "").strip())
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.write(f"enabled={'true' if enabled else 'false'}\n")
    if enabled:
        print(f"{SECRET} is set: the live evaluation runs.")
    else:
        print(f"Live evaluation skipped: the secret {SECRET} of the live-eval environment is not set. "
              "Add it there to run trials (docs/LIVE_EVAL_EVIDENCE.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
