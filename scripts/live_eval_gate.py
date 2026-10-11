"""Decide whether the scheduled live evaluation runs (M45).

The workflow `.github/workflows/live-eval.yml` runs this first. It runs the
evaluation only when the repository secret CLAUDE_CODE_OAUTH_TOKEN is present
(from `claude setup-token`, so the run uses the owner's Claude plan). Without
it, it writes `enabled=false` to $GITHUB_OUTPUT and every later step is
skipped: the job stays green and spends nothing. It never prints the secret.
See docs/LIVE_EVAL_EVIDENCE.md.
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
        print(f"Live evaluation skipped: the repository secret {SECRET} is not set. "
              "Add it to enable the weekly run (docs/LIVE_EVAL_EVIDENCE.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
