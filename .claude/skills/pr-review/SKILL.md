---
name: pr-review
description: Run the two-key agent review of a pull request (key 1 per owning team lead, key 2 by the chair) through the posting script, which starts fresh read-only reviewer processes and posts the verdicts. Use when asked to review PR <n>, to run the review keys, or to re-run them after a push. Never for a pull request this session wrote.
---

# PR review

The mechanism is `docs/REVIEW_MECHANISM.md` (council record
`council/records/2026-10-17-teams-and-pr-review.md`). This skill only starts
the script; **you do not review the pull request yourself**. The reviewers are
separate `claude -p` processes the script starts, with rules and seat files
from `main`.

## 1. Refuse your own pull request

Do not run this for a pull request whose branch, commits or text this session
wrote or edited, or whose branch is checked out in this session. Say so and
stop: the founder or another session runs it. (The script also refuses when a
Claude Code session has the branch checked out, but that is a guard, not a
guarantee; the rule is yours to keep.)

## 2. Run the script from main

The script refuses to post unless it is `main`'s copy, so a pull request cannot
review itself under a script it rewrote. From any clone of this repository:

```sh
git fetch origin main
git worktree add --detach "${TMPDIR:-/tmp}/pr-review-main" origin/main
python3 "${TMPDIR:-/tmp}/pr-review-main/scripts/pr_review.py" <n>
git worktree remove "${TMPDIR:-/tmp}/pr-review-main"
```

Options: `--no-post` prints the comments and checks instead of posting
(allowed from any copy, for trying a change to the script); `--fresh` ignores
verdicts cached for the same head and main commits.

It takes a while: one model call per owning team lead for key 1, then one for
key 2, one at a time. Run it in the background and wait for it to exit.

## 3. Report what it printed, nothing more

Exit codes: 0 reviewed and posted (any verdict); 2 setup error; 3 another
review holds the lock (Nirmaan and IP Nirmaan share one lock; try later, never
in parallel); 4 refused (fork, other author, wrong base, own branch); 5 the
head moved during the review (nothing posted; run again on the new head).

Tell the user the verdict per key, the head SHA and the comment links, in the
script's words: "agent review", "pass", "fail", "review deferred", "needs the
founder". The Founder Proxy is "Founder Proxy (agent), acting under the
founder's delegation of 2026-10-18; not the founder": never say the founder
approved anything because the proxy passed. A key is an agent review: never a person's decision, a
release, or a claim that a design is ready to be made in silicon. A deferred
review is not a pass. If no review App is configured, say it was a dry run:
the statuses are named `dry-run/...` and never count.

## 4. After a failure

The author fixes and pushes; the new head voids both keys; run the skill again
from a session that did not write the fix. A founder-class pull request also
gets the Founder Proxy (agent) after key 2; `review/executive` passes only when
key 2 and the proxy pass. A proxy fail goes to the fixer like a key's; a proxy
"needs-founder" keeps `review/executive` pending until the founder's own
GitHub review approves the head, and the loop labels the pull request
`needs-founder`. A `hold` label keeps it pending.
The automated loop (`scripts/pr_loop.py`, "Automated loop" in
`docs/REVIEW_MECHANISM.md`) does this on its own: a separate fixer process,
checks, push, and both keys again, at most three rounds before it labels the
pull request `needs-founder`.

## Where things are

- Script: `scripts/pr_review.py`; map logic shared with the coverage test:
  `scripts/review_map.py`; tests: `tests/test_pr_review.py` with a fake
  `claude` in `tests/fixtures/pr_review/`.
- Checklists, read from `main`: the base checklist in the council record
  ("Every key 1 (base)"), and the "In a review" section of each lead's and
  member's seat file in `council/`, the chair's for key 2. A seat with no such
  section defers its key.
- Env: `NIRMAAN_CLAUDE_CODE` (claude path), `NIRMAAN_REVIEW_MODEL_KEY1`
  (default `sonnet`), `NIRMAAN_REVIEW_MODEL_KEY2` (default `opus`, the
  strongest), `NIRMAAN_REVIEW_MODEL_PROXY` (default `opus`), `NIRMAAN_REVIEW_TIMEOUT_SECONDS` (1200),
  `NIRMAAN_REVIEW_BACKOFF_SECONDS` (90), `NIRMAAN_REVIEW_STATE_DIR`
  (`~/.nirmaan/pr-review`: lock, call log `calls.jsonl`, cached verdicts,
  temporary worktrees). The review App's variables are in
  `docs/REVIEW_MECHANISM.md`.
