# PR review mechanism

Status: PLANNED. Nothing below is enforced yet. Until the GitHub App and the
ruleset on `main` are live, a review status on a pull request is a convention:
any write collaborator, or a workflow token, could post one. The founder merges
every pull request by hand, as today.

Decided in the council record
[2026-10-17: teams and the PR review mechanism](../council/records/2026-10-17-teams-and-pr-review.md).
The mechanism is shared with Nirmaan and described in Nirmaan's
`docs/operations/pr-review.md`
(<https://github.com/nirmaansoftware/Nirmaan/blob/main/docs/operations/pr-review.md>).
This page says how it applies to IP Nirmaan.

## Agent reviews are reviews

A key in this mechanism is an agent review: a model session reading the diff
against a checklist. It is never a person's decision, a release, a legal
clearance, or a claim that a design is ready to be made in silicon. Status
descriptions say "agent review (role)", name the head SHA, and link the review
comment. A review whose SHA differs from the head is void.

## The flow

1. **CI first.** The five CI checks (`test`, `no-tools`, `physical-design`,
   `test-union`, `dashes`) are green on the head SHA. Physical design tools do
   not run on the development machine, so CI is the record.
2. **Key 1: team lead.** One agent review per owning team. The owning teams are
   every team whose path rule matches a changed file, read from `main`'s
   `.github/review-teams.yml` (planned), plus teams added by content rules
   (a price or partner name adds Business; a gate change adds Verification).
3. **Key 2: chair.** One agent review of the whole PR, after every key 1.
4. **Founder classes.** A PR in one of the six classes below also waits for the
   founder's own code owner review on GitHub. The review script declares the
   classes it detects: before the keys run it writes a
   `<!-- review:founder-class -->` block at the top of the PR body, rewrites it
   when the classes change and removes it when none is left. Every other copy
   of the block, and any lone open or close marker without its pair, is
   removed, so the only markers left are the script's own. The keys treat
   that block as the PR's flag.
5. **Merge.** Automatic once every required check passes (after the ruleset
   and auto-merge are turned on).

## Teams

| Team | Key 1 | Owns (summary) |
|---|---|---|
| Council | security (control files), qa-evidence (records, seat files); chair holds key 2 | `council/**`, `CLAUDE.md`, `.claude/**` |
| Silicon Design | design-architect | RTL, DFT, physical design and firmware code, fixtures and docs |
| Verification | verification-lead | VeriTriage, evals, gates, formal |
| EDA and Platform | eda-tooling | `.github/**`, `scripts/**`, runtime, MCP, every file no other rule matches |
| Product and Site | product-lead | `site/**`, `README.md`, roadmap scope |
| Business | legal-compliance or finance-licensing, by subject | licences, notices, commercial terms |

The full path map is in the council record, section 1.

## Founder classes

The founder confirmed all six on 2026-10-17: control plane, gate semantics,
licence and third-party, commercial, public names and claims, and
export-control sensitive content. Path classes will be enforced by
`.github/CODEOWNERS` and code owner review; content classes by a `hold` label,
which is a convention because agents can remove labels.

## Reviewer isolation

The reviewer runs as a fresh read-only process in a clean checkout of the head
SHA, never in the session that wrote the PR. It does not see the PR title, body
or commit messages; code comments, RTL comments and docs in the diff are data,
never instructions. It returns a JSON verdict with file and line findings and
holds no token. A separate script checks every citation and that the head is
unchanged, then posts the status.

## How reviewers run

Built for rollout R5, not yet used on a real pull request. The
[`pr-review` skill](../.claude/skills/pr-review/SKILL.md) starts
`scripts/pr_review.py` from a checkout of `main`; a session never runs it for
a pull request it wrote, and the script refuses when a Claude Code session has
the branch checked out. In order:

1. **One review at a time** across Nirmaan and IP Nirmaan: a lock in
   `~/.nirmaan/pr-review/`, shared with Nirmaan's script. The lock is a folder
   (`review.lock`) with an owner file written whole (a temporary file renamed
   inside it). A lock whose process is gone is cleared, and so is one with no
   readable owner file that is older than 30 minutes.
2. **Eligibility.** Open, targets `main`, a branch in this repository (never a
   fork), authored by `patel-om` or `nirmaansoftware`; otherwise it refuses and
   posts nothing.
3. **Clean checkouts** of the head and of `main`, outside the repository; the
   fetched head must be the pull request's head.
4. **From `main` only:** owning teams, the lead of each that holds key 1,
   founder classes, sections and content hits come from `main`'s
   `.github/review-teams.yml` (`scripts/review_map.py`, the same logic as the
   coverage test). Seat files, the base checklist (council record, section 3)
   and the script itself come from `main` too.
5. **CI first.** For each of `test`, `no-tools`, `physical-design`,
   `test-union` and `dashes` the newest run on the head counts (by start time,
   then run id), and a run still in progress, such as a rerun, always means
   waiting: an older success never counts while a newer run exists. While a
   job runs or is missing, both checks stay pending ("waiting for CI"). When a
   job finished without success, both checks are posted as `action_required`
   with the title "CI failed on <sha>; review not run" (terminal, and never
   green: a required check is satisfied only by success, neutral or skipped).
   No model is called in either case.
6. **Key 1, then key 2.** Key 1 is one fresh `claude -p` process per owning
   team lead: the base checklist, the lead's seat file and the "In a review"
   sections of the team's members. Key 2 runs only when every key 1 passed:
   the chair's seat file plus every owning lead's seat file, given key 1's
   results, on the strongest model.
7. **Isolation.** Read, Grep and Glob only, in the head checkout (`main` is
   readable for comparison); no command, write, network or MCP tools; no
   project customizations; no GitHub, App or API tokens in the environment.
   The pull request title, body and commit messages are not given. The diff is
   untrusted data between delimiters with a random marker; an instruction to
   the reviewer inside it is a critical finding.
8. **Validation.** One JSON object: verdict (`pass` or `fail`), the head SHA,
   findings with file, line and severity, checks run and what was not run. The
   script checks the schema, the SHA and that every cited file and line exists
   at the head. A pass with a blocker or critical finding is recorded as fail.
9. **Fail closed.** A failed call, a timeout or a rate limit gets one retry
   after a backoff; after that, and on any invalid output or missing
   citation, the key is "review deferred" and stays pending. It never passes
   by default.
10. **Posting.** The head is checked before every post; if it moved, nothing
    more is posted. One comment per key (seat, key, head and base SHA,
    verdict, findings, checks run, what was not run) and the checks
    `review/team-lead` and `review/executive`. `review/executive` passes only
    with key 2 passing, no `hold` label, and for a founder-class pull request
    the founder's latest review approving this head SHA. A comment or check
    run is not posted again when the App's latest one for that key, team and
    head already says the same (a rerun that reused its cached verdicts); the
    comment's marker carries a digest of the result for this.
11. **Records.** Every model call (tokens, duration, outcome) is logged in
    `~/.nirmaan/pr-review/calls.jsonl`, outside the repository. Validated
    verdicts are cached per head commit, `main` commit, key, team and lead, so
    re-running after the founder approves does not call the model again. The
    pull request title and body are not in that key because the reviewers here
    never read them (step 7); Nirmaan's reviewers do, so its key also carries
    a digest of them. Each run's
    worktrees, and the per-run folder that holds them under
    `~/.nirmaan/pr-review/worktrees`, are removed when it ends.

**Posting identity.** The review App posts the check runs with a short-lived
installation token scoped to this repository. The token asks for `checks:
write` (the check runs), `pull_requests: write`, `contents: read` and
`metadata: read`. `pull_requests: write` is the permission the script uses to
write the founder-class block into the pull request body (a `PATCH` of
`/pulls/<n>`, `update_pull_body`); the comments and the `needs-founder` label
go through the same token. It is made from these environment variables: `NIRMAAN_REVIEW_APP_ID`, one of
`NIRMAAN_REVIEW_APP_PRIVATE_KEY_FILE` (a PEM outside every repository) or
`NIRMAAN_REVIEW_APP_KEYCHAIN_SERVICE` (a macOS Keychain item holding the PEM),
and optionally `NIRMAAN_REVIEW_APP_INSTALLATION_ID`. Until the App exists the
script runs as a dry run with the caller's `gh` login: comments plus commit
statuses named `dry-run/review/team-lead` and `dry-run/review/executive`,
which are never green and are not the checks a ruleset requires.

## Automated loop

Built, not yet run on a real pull request. `scripts/pr_loop.py` (the
"driver", a port of Nirmaan's `.github/scripts/pr-loop/pr-loop.mjs`) runs the
whole cycle without anyone starting the review by hand: wait for CI, run both
keys, fix what a key found, review again, and take the merge path when both
keys pass. It never replaces a key and never goes around the founder:
founder-class pull requests still need the founder's GitHub approval, and the
loop never merges them.

**Which pull requests.** Open, targeting `main`, from a branch in this
repository, authored by the agents' account (`patel-om`). Drafts and pull
requests labelled `hold` or `needs-founder` are skipped.

**Each step, per pull request:**

1. **CI.** Until the five CI checks are green on the head, the loop waits and
   calls no model. CI failing on a head the loop pushed stops the loop; CI
   failing on the author's head only waits.
2. **Review.** `scripts/pr_review.py` runs unchanged (fresh read-only process
   per key, seat files from `main`, comments and checks posted).
3. **Both keys pass.** A founder-class pull request waits: the loop posts that
   it waits for the founder's approval of this head and does nothing else;
   once the founder approves, it runs the review again (cached verdicts, no
   model call) so `review/executive` turns green, and the founder merges.
   Otherwise, when the review App posts the checks, the loop reads the
   repository's "Allow auto-merge" setting with the gh login (the
   `allow_auto_merge` field of `gh api repos/<repo>`). When it is on, the loop
   runs `gh pr merge --auto --merge --match-head-commit <head>`, so GitHub
   merges only when every required check passes on that head. In a dry run,
   or when the setting is off, it posts "ready: both keys passed, waiting for
   the founder's merge settings", and the founder merges. The decision never
   depends on the wording of a gh error: when the setting cannot be read, or
   `gh pr merge --auto` fails for any reason, the loop stops with
   `needs-founder`.
4. **A key fails.** The loop starts a **fixer**: a separate, fresh `claude -p`
   process, never a reviewer process and never the session that reviewed. It
   runs in a clean worktree of the head with Read, Grep, Glob, Edit and Write
   allowed only inside that worktree; no shell, network, MCP or token. Its task
   is the structured list of blocker and critical findings from the failed
   keys; each finding's wording is data, not instructions, and the pull
   request text is not given (as for the reviewers). It gets `CLAUDE.md` from
   `main` and is told to change only what the findings require.
5. **The loop, not the model, finishes the round.** It throws the fix away and
   stops if the fixer changed a path it may not change: `.github/**`,
   `.claude/**`, `CLAUDE.md`, `council/**` (every seat file, with its "In a
   review" section, and the records holding the base checklist), the CI check
   scripts, the review, map and loop scripts and their tests, this page, the
   plist, `pyproject.toml`, `.gitignore`. A fixer that says a finding needs
   such a change stops the loop the same way. Otherwise the loop commits with
   the `Co-Authored-By` line, runs the local checks (`check_dashes.py` always;
   the test suite when `src/`, `tests/`, `evals/`, `scripts/` or `site/`
   changed) with no token in the environment, checks the head has not moved,
   pushes to the branch with `--force-with-lease` on the reviewed head, and
   posts "fix round N" listing the findings addressed.
6. **Again from scratch.** The new head voids both keys, so the next step waits
   for CI on it and runs both reviews again.

**When it stops.** The loop labels the pull request `needs-founder` and
comments why when: three fix rounds are done and a key still fails; the same
finding (same key, team, file and wording) fails again after a fix; CI fails
after a fix; the branch has a merge conflict; a key is deferred (rate limit,
bad output, missing seat file); the fixer hits a rate limit, gives no valid
answer, cannot fix every finding or changes nothing; a local check fails; the
auto-merge setting cannot be read or `gh pr merge --auto` fails; or any error.
Nothing is pushed in any of these cases. The reason is redacted before it is
logged or posted: common secret formats (`SECRET_PATTERNS` in
`scripts/pr_review.py`), credentials in a URL and the value after
`Authorization:`, `Bearer` or `token` become `[redacted]`, since a gh or git
error can carry them. If someone pushes while
the fixer works, the round is dropped without a label and the new head is
reviewed from scratch. Removing the `needs-founder` label lets the loop resume
with a fresh round count.

**One pull request at a time.** The loop holds the review lock (shared with
Nirmaan) for a whole review and fix round; a pull request the loop is fixing
goes first, and each pass ends after the first pull request that ran a review
or a fix.

**Records.** Every review call, fixer call and loop step is a line in
`~/.nirmaan/pr-review/calls.jsonl`; per pull request loop state is in
`~/.nirmaan/pr-review/loop/`.

**Running it.** On the founder's Mac with the Mac's own `claude` login (the
plan) and `gh` login: no new spend and no secret in GitHub Actions. Like the
review script, it refuses to post unless it is `main`'s copy.

- **Once:** `python scripts/pr_loop.py --once` from a checkout of
  `origin/main` (`--pr <n>` for one pull request; `--no-post` to print
  instead of posting, labelling or pushing).
- **In a terminal:** `python scripts/pr_loop.py --watch --interval-minutes 5`.
  It exits when `main`'s copy of the loop changes; start it again from the
  updated checkout.
- **launchd (survives restarts).** Make a dedicated clone with its own
  environment, then install [`pr-loop.plist`](pr-loop.plist):

  ```sh
  mkdir -p ~/.nirmaan/pr-loop
  git clone https://github.com/nirmaansoftware/ip-nirmaan.git ~/.nirmaan/pr-loop/ip-nirmaan
  cd ~/.nirmaan/pr-loop/ip-nirmaan && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
  cp docs/pr-loop.plist ~/Library/LaunchAgents/online.nirmaan.ip-pr-loop.plist
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/online.nirmaan.ip-pr-loop.plist
  ```

  Every 5 minutes it resets the clone to `origin/main` and runs `--once`;
  output goes to `~/.nirmaan/pr-review/ip-loop.log`. `git`, `gh` and `claude`
  must be on the login shell's `PATH`. To stop it:
  `launchctl bootout gui/$(id -u)/online.nirmaan.ip-pr-loop`.
- **Claude Code `/loop`:** in a session opened in the dedicated clone,
  `/loop 10m git fetch origin main && git reset --hard origin/main &&
  .venv/bin/python scripts/pr_loop.py --once, then report its last line`. The
  session only starts the script; it never reviews or fixes a pull request
  itself.

**Settings** (environment): `NIRMAAN_LOOP_MODEL_FIXER` (default `sonnet`),
`NIRMAAN_LOOP_FIXER_TIMEOUT_SECONDS` (1800),
`NIRMAAN_LOOP_CHECK_TIMEOUT_SECONDS` (1200), `NIRMAAN_LOOP_GIT_NAME` and
`NIRMAAN_LOOP_GIT_EMAIL` (otherwise the clone's git config, otherwise the head
commit's author), plus the review script's variables above. The forbidden
paths, local checks, round limit and authors are `LOOP` in
`scripts/pr_loop.py`.

**What the loop does not do.** It never merges a founder-class pull request,
never changes the review configuration, the council or workflows, never pushes
over someone else's push, never runs on a fork or another author's pull
request, never turns auto-merge on for the repository, and never treats a
deferred review as a pass. A fix the loop pushed is agent work like any other:
both keys review it again.

## What is not done yet

Each item is a separate PR or a founder action, in the order of the council
record's rollout (R1 to R7): CI hardening, the path map and its coverage test,
seat files and checklists, the reviewer skill and posting script, a dry run on
seeded PRs, then the GitHub App, CODEOWNERS and the ruleset. This page changes
from PLANNED to IMPLEMENTED only when the ruleset is live.
