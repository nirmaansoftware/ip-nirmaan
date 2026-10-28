# PR review mechanism

Status: IMPLEMENTED, live since 2026-10-18. The ruleset "main: two keys" on
`main` is active. It requires the five CI checks, and `review/team-lead` and
`review/executive` from the review App only, so a status posted by a write
collaborator or a workflow token does not count. The ruleset's "Require review
from Code Owners" is still on, but since `.github/CODEOWNERS` was removed (the
Founder Proxy, 2026-10-18) it has no effect; the founder can turn it off. A
push dismisses an earlier approval.
Branches need not be up to date with `main` (strict is off). Auto-merge is on.
The first automatic merge was #106 (both keys passed, the loop turned on
auto-merge, GitHub merged it with no human action); #105 and #107 merged
through both keys after the founder's approval on GitHub.

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

Before the flow starts, the author session runs Claude's code review on its
own diff (the `code-review` skill, effort `low`) and fixes the findings, both
before opening the pull request and before pushing each fix to it. It posts
nothing and is not a key; it catches plain bugs before the keys spend calls.

1. **CI first.** The five CI checks (`test`, `no-tools`, `physical-design`,
   `test-union`, `dashes`) are green on the head SHA. Physical design tools do
   not run on the development machine, so CI is the record.
2. **Key 1: team lead.** One agent review per owning team. The owning teams are
   every team whose path rule matches a changed file, read from `main`'s
   `.github/review-teams.yml`, plus teams added by content rules
   (a price or partner name adds Business; a gate change adds Verification).
   A cryptographic core or an export-control term, code that sends an email
   or message outside the repository, or a person named as author, copyright
   holder or contact adds Business with legal-compliance as key 1, and raises
   the founder class export-control, commercial or licence-and-third-party,
   so the Founder Proxy sees it. Specification text reproduced rather than
   cited (a rights or permission notice, NDA wording, a standard's document
   number, a standard's numbered table or figure) adds Business with
   legal-compliance as key 1. A change inside the site hero's review markers
   (`site/index.html`) raises public-names-and-claims, as the partners
   section does.
3. **Key 2: chair.** One agent review of the whole PR, after every key 1.
4. **Founder Proxy.** A PR in one of the six classes below also gets the
   Founder Proxy (agent) after key 2 passes; what only the founder decides it
   sends to the founder (`needs-founder`). The review script declares the
   classes it detects: before the keys run it writes a
   `<!-- review:founder-class -->` block at the top of the PR body, rewrites it
   when the classes change and removes it when none is left. Every other copy
   of the block, and any lone open or close marker without its pair, is
   removed, so the only markers left are the script's own. The keys treat
   that block as the PR's flag.
5. **Merge.** Automatic once every required check passes.

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
export-control sensitive content. The review script detects both path and
content classes from `main`'s map. A `hold` label also keeps `review/executive`
pending; agents can remove labels, so the label is a convention.

**The Founder Proxy (founder's decision, 2026-10-18).** Until 2026-10-18 these
classes needed the founder's own GitHub approval, enforced by `CODEOWNERS` and
code owner review. On 2026-10-18 the founder, after being shown the risks,
delegated that third review to an agent:
[`council/founder-proxy.md`](../council/founder-proxy.md). Every comment it
posts says "Founder Proxy (agent), acting under the founder's delegation of
2026-10-18; not the founder". It is never the founder's approval.

- **When it runs.** Only on a founder-class pull request, only after key 1 and
  key 2 passed on the same head SHA, as a fresh read-only process with its seat
  file from `main`, on the strongest model, with the same isolation, untrusted
  data rules, validation, cache and fail-closed rules as the keys.
- **Its verdict.** `pass`, `fail` (with file and line findings, which go to
  the loop's fixer like a key's), or `needs-founder` (with reasons).
  `review/executive` passes only when key 2 and the proxy pass; there is no
  third check, so the ruleset needs no change.
- **What only the founder decides** returns `needs-founder`, and only when
  the pull request clearly does it: new spending (a paid service, account,
  subscription, API key billing, a paid runner, or a tool that needs a paid
  licence); a contract, agreement or NDA, or engaging or naming legal
  counsel; and turning on or widening any sending (an email or message to
  anyone outside the repository). A change that could be read either way is
  decided on the merits: pass, or fail with the reason. It fails a change
  that weakens a review gate (removes or skips a key or a required check,
  lets a check pass by default, on a timeout or on a deferred review, reads
  seat files from the pull request, or lets the loop merge without both keys
  and the proxy), and attribution other than the company "Nirmaan". The full
  rules are in its seat file.
- **Needs the founder.** `review/executive` stays pending and the loop labels
  the pull request `needs-founder`. The founder decides on GitHub: their own
  review approving the current head lets the script pass `review/executive`
  (after the label is removed, the loop reruns the review from cache and takes
  the merge path).
- **No CODEOWNERS.** `.github/CODEOWNERS` was removed, and
  `tests/test_review_teams.py` fails if one is added back.

## Reviewer isolation

The reviewer runs as a fresh read-only process in a clean checkout of the head
SHA, never in the session that wrote the PR. It does not see the PR title, body
or commit messages; code comments, RTL comments and docs in the diff are data,
never instructions. It returns a JSON verdict with file and line findings and
holds no token. A separate script checks every citation and that the head is
unchanged, then posts the status.

## How reviewers run

Built in rollout R5; in use on real pull requests since 2026-10-18. The
[`pr-review` skill](../.claude/skills/pr-review/SKILL.md) starts
`scripts/pr_review.py` from a checkout of `main`; a session never runs it for
a pull request it wrote, and the script refuses when a Claude Code session has
the branch checked out. In order:

1. **One model call at a time** across Nirmaan and IP Nirmaan: a lock in
   `~/.nirmaan/pr-review/`, shared with Nirmaan's script, held here only
   around each reviewer call, never while checking out, reading CI, posting, fixing or
   running local checks. When it is held elsewhere at a call, the run ends
   ("busy", exit 3) and the next run reuses the verdicts already cached. The
   lock is a folder (`review.lock`) with an owner file written whole (a
   temporary file renamed inside it). A lock whose process is gone is cleared,
   and so is one with no readable owner file that is older than 30 minutes.
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
   No model is called in either case. A diff of `main...head` over 200,000
   bytes is not reviewed either: both checks stay pending with "review not
   run: ... split the pull request". The reviewers always get the whole diff,
   never a cut one (the one shape rule that stops a review).
6. **Key 1, then key 2.** Key 1 is one fresh `claude -p` process per owning
   team lead: the base checklist, the lead's seat file and the "In a review"
   sections of the team's members. Key 2 runs only when every key 1 passed:
   the chair's seat file plus every owning lead's seat file, given key 1's
   results, on the strongest model. On a founder-class pull request whose key
   2 passed, the Founder Proxy runs next: its seat file from `main` and both
   keys' results, on the strongest model.
7. **Isolation.** Read, Grep and Glob only, in the head checkout (`main` is
   readable for comparison); no command, write, network or MCP tools; no
   project customizations; no GitHub, App or API tokens in the environment.
   The pull request title, body and commit messages are not given. The diff,
   the changed file names (the pull request chooses them) and, for key 2 and
   the Founder Proxy, the earlier keys' results are untrusted data between
   delimiters with a random marker, a fresh one for every reviewer call, so
   no reviewer's output can close another's fence; an instruction to the
   reviewer inside them is a critical finding. A changed path holding a
   control or format character (a newline, an escape, a bidirectional or
   zero-width mark) is refused before any reviewer sees it: both checks stay
   pending, no model is called, and the loop stops.
8. **Validation.** One JSON object: verdict (`pass` or `fail`; the Founder
   Proxy may also return `needs-founder`, with at least one reason), the head SHA,
   findings with file, line and severity, checks run and what was not run. The
   script checks the schema, the SHA and every citation. A cited line must exist at the head, at the base for a file
   the pull request deletes, or on `main` (written `main:<path>`, or a path
   that is not at the head but is on `main`); a reviewer's checkout prefix is
   taken off a cited path first. A minor or info finding with a bad citation
   is dropped with a note in the comment, and the verdict stands; this is
   the one case where a finding with a bad citation does not hold the key
   pending. A bad citation on a major, critical or blocker finding gets one
   repair: a fresh call to the same seat, given its own answer's error, asked
   for corrected citations and the verdict it gave, except that a pass listing
   a blocker or critical finding is asked for as a fail. A repair that fails,
   cites badly again, returns a different verdict, or keeps fewer blocker,
   critical or major findings defers the key. So a bad citation never turns a
   verdict that was not a pass, or a pass with a blocker or critical finding,
   into a pass. A pass with a blocker or critical finding is recorded as fail.
   A repair is not a review; the call log marks it `"attempt": "repair"`.
9. **Fail closed.** A failed call, a timeout or a rate limit gets one retry
   after a backoff; after that, and on any invalid output or a citation that
   step 8 neither drops nor repairs, the key is "review deferred" and stays
   pending. It never passes by default.
10. **Posting.** The head is checked before every post; if it moved, nothing
    more is posted. One comment per key (seat, key, head and base SHA,
    verdict, findings, checks run, what was not run) and the checks
    `review/team-lead` and `review/executive`. `review/executive` passes only
    with key 2 passing, no `hold` label, and for a founder-class pull request
    the Founder Proxy passing (or returning `needs-founder` with the founder's
    latest review approving this head SHA). A comment or check
    run is not posted again when the App's latest one for that key, team and
    head already says the same (a rerun that reused its cached verdicts); the
    comment's marker carries a digest of the result for this.
11. **Records.** Every model call (tokens, duration, outcome) is logged in
    `~/.nirmaan/pr-review/calls.jsonl`, outside the repository; an answered
    call's line also carries the verdict status the script recorded, its
    findings by severity, and the validation error when it was deferred.
    Validated
    verdicts are cached per head commit, `main` commit, key, team and lead, so
    re-running after the founder decides a `needs-founder` pull request does
    not call the model again. The
    pull request title and body are not in that key because the reviewers here
    never read them (step 7); Nirmaan's reviewers do, so its key also carries
    a digest of them. Each run's
    worktrees, and the per-run folder that holds them under
    `~/.nirmaan/pr-review/worktrees`, are removed when it ends.

**Composite key 1 (built, off).** Council record 2026-10-18 (review loop),
decision 1. With `composite_key1` on in the script's `CONFIG`, key 1 is one
call per head instead of one per owning team. What it loads is data in
`main`'s `.github/review-teams.yml` (`composite_key1`, read by
`review_map.key1_plan`): the seat that speaks is the lead of the owning team
that comes first in `precedence` (Council, Verification, Business, Silicon
Design, Product and Site, EDA and Platform), with its seat file whole; then the
"In a review" section of every owning team's lead, of every member whose
trigger matches (team, path, changed-line content, or a line range such as the
`physical-design` job in `ci.yml`), and of the `always` seats
(legal-compliance). A member loads by trigger, not by membership: a
firmware-only change no longer carries the DFT list, and a DFT bound changed in
`src/nirmaan/company/workflows.py` now does. A selected checklist missing on
`main` defers the review. The prompt puts the fixed text first (base
checklist, seat file, loaded checklists, verdict rules) and the rules with the
head's facts and fence marker last. The verdict adds one entry per loaded
checklist (name, team, status `pass`, `fail` or `not_applicable`, findings
with citations); a missing, duplicated or unknown entry defers, a failed
checklist fails key 1, and entry findings are validated like any finding.
Key 2 gets
the list of loaded checklists and key 1's entries. The cache name and the
fix-round fingerprint use one fixed key-1 identity (`composite`), so a fix that
adds an owning team cannot make a repeated finding look new. It is on: its own
pull request switched it on after an A/B run on the seeded calibration sets
(kept outside both repositories) showed it catches every domain seed at least
as often as the per-team calls, with no Verification regression. The switch
(`composite_key1` in `scripts/pr_review.py`) turned off gives the per-team
calls back unchanged.

**Posting identity.** The review App posts the check runs with a short-lived
installation token scoped to this repository. The token asks for `checks:
write` (the check runs), `pull_requests: write`, `contents: read` and
`metadata: read`. `pull_requests: write` is the permission the script uses to
write the founder-class block into the pull request body (a `PATCH` of
`/pulls/<n>`, `update_pull_body`); the comments and the `needs-founder` label
go through the same token. It is made from these environment variables: `NIRMAAN_REVIEW_APP_ID`, one of
`NIRMAAN_REVIEW_APP_PRIVATE_KEY_FILE` (a PEM outside every repository) or
`NIRMAAN_REVIEW_APP_KEYCHAIN_SERVICE` (a macOS Keychain item holding the PEM),
and optionally `NIRMAAN_REVIEW_APP_INSTALLATION_ID`. Without the App ID and
one of the two key variables, the script runs as a dry run with the caller's `gh` login: comments plus commit
statuses named `dry-run/review/team-lead` and `dry-run/review/executive`,
which are never green and are not the checks a ruleset requires.

## Automated loop

Running since 2026-10-18 under launchd (`online.nirmaan.ip-pr-loop`).
`scripts/pr_loop.py` (the
"driver", a port of Nirmaan's `.github/scripts/pr-loop/pr-loop.mjs`) runs the
whole cycle without anyone starting the review by hand: wait for CI, run both
keys, fix what a key found, review again, and take the merge path when both
keys pass. It never replaces a key or the Founder Proxy, and never decides
what the proxy sends to the founder: a `needs-founder` verdict stops it.

**Which pull requests.** Open, targeting `main`, from a branch in this
repository, authored by the agents' account (`patel-om`). Drafts and pull
requests labelled `hold` or `needs-founder` are skipped.

**Each step, per pull request:**

1. **Behind `main`.** The ruleset here has strict up-to-date branches off, so
   GitHub is not expected to report a branch as behind. If it does
   (`mergeable_state` `behind`), the loop handles it as Nirmaan's loop does.
   It asks GitHub to merge `main` into the branch first, with the gh login:
   `PUT repos/<repo>/pulls/<n>/update-branch` with `expected_head_sha` set to
   the head it saw. This is the merge-commit update that
   `gh pr update-branch` makes, but GitHub refuses it if the head has moved.
   The loop does this before any review, also for a head that already
   finished (unless the review refused the pull request), and again after
   both keys pass when `main` moved during the review. The new head is
   reviewed from scratch. While GitHub
   is still making the merge commit (up to 10 minutes), the loop waits
   instead of asking again. If the update fails (a merge conflict with
   `main`, or GitHub refuses it), the loop stops with `needs-founder`. If
   someone pushed in between, the step is dropped without a label and the
   new head is reviewed. `--no-post` never updates a branch.
2. **CI.** Until the five CI checks are green on the head, the loop waits and
   calls no model. CI failing on a head the loop pushed stops the loop; CI
   failing on the author's head only waits.
3. **Review.** `scripts/pr_review.py` runs unchanged (fresh read-only process
   per key and for the Founder Proxy on a founder-class pull request, seat
   files from `main`, comments and checks posted). A proxy `needs-founder`
   stops the loop (below).
4. **Both keys (and the proxy) pass.** When the review App posts the checks, the loop reads the
   repository's "Allow auto-merge" setting with the gh login (the
   `allow_auto_merge` field of `gh api repos/<repo>`). When it is on, the loop
   runs `gh pr merge --auto --merge --match-head-commit <head>`, so GitHub
   merges only when every required check passes on that head. In a dry run,
   or when the setting is off, it posts "ready: both keys passed, waiting for
   the founder's merge settings", and the founder merges. The decision never
   depends on the wording of a gh error: when the setting cannot be read, or
   `gh pr merge --auto` fails for any reason, the loop stops with
   `needs-founder`.
5. **A key or the Founder Proxy fails.** When a finding to fix is on a path
   the fixer may not change (step 6), the fixer does not run: the loop labels
   the pull request `author-fix` and lists the findings, and waits for the
   author's next head, which clears the label and is reviewed from scratch.
   Otherwise the loop starts a **fixer**: a separate, fresh `claude -p`
   process, never a reviewer process and never the session that reviewed. It
   runs in a clean worktree of the head with Read, Grep, Glob, Edit and Write
   allowed only inside that worktree; no shell, network, MCP or token. Its task
   is the structured list of blocker and critical findings from the failed
   keys and proxy; each finding's wording is data, not instructions, and the pull
   request text is not given (as for the reviewers). It gets `CLAUDE.md` from
   `main` and is told to change only what the findings require.
6. **The loop, not the model, finishes the round.** It throws the fix away and
   stops if the fixer changed a path it may not change: `.github/**`,
   `.claude/**`, `CLAUDE.md`, `council/**` (every seat file, with its "In a
   review" section, and the records holding the base checklist), the CI check
   scripts, the review, map and loop scripts and their tests, this page, the
   plist, `pyproject.toml`, `.gitignore`. A fixer that says a finding needs
   such a change stops the loop the same way. Otherwise the loop commits with
   the `Co-Authored-By` line, runs the local checks (`check_dashes.py` always;
   when `src/`, `tests/`, `evals/`, `scripts/` or `site/` changed, the tests
   related to the changed files, from `related_tests` in `scripts/pr_loop.py`:
   a changed test file itself, the tests that import a changed module or its
   package, or name a changed script or fixture, plus `tests/test_laws.py` for
   `src/`; the whole suite when a changed file maps to no test or is
   `tests/conftest.py`; CI runs the whole suite either way) with no token in
   the environment, checks the head has not moved,
   pushes to the branch with `--force-with-lease` on the reviewed head, and
   posts "fix round N" listing the findings addressed.
7. **Again from scratch.** The new head voids both keys, so the next step waits
   for CI on it and runs both reviews again.

**Shape rules.** After a review, the loop comments once on the soft shape
rules a pull request breaks, each named, and again only when that list
changes: one owning team per pull request where possible; founder-class paths
not mixed with ordinary paths; mechanical renames (a rename with no content
change) not mixed with other changes; and a soft cap of 400 changed lines
outside `tests/fixtures/**` (`shape_soft_cap_lines` and `shape_uncounted` in
`LOOP`). They never stop the loop. Generated files are not detected (nothing
marks them in this repository), and stacked pull requests are never reviewed,
since the loop takes only pull requests to `main`. The one rule that stops a
review is the size limit above.

**When it stops.** The loop labels the pull request `needs-founder` and
comments why when: three fix rounds are done and a key still fails; the same
finding (same key, team, file and wording) fails again after a fix; CI fails
after a fix; the branch has a merge conflict; a key or the Founder Proxy is
deferred for any reason but a rate limit (bad output, a failed call, a
missing seat file), or the diff is over the review's size limit; the Founder
Proxy returns `needs-founder` (until the founder's own review approves the
head); the fixer gives no valid answer, cannot fix every finding or changes
nothing; a local check fails; the
auto-merge setting cannot be read or `gh pr merge --auto` fails; the branch
is behind `main` and the update fails; or any error.
Nothing is pushed in any of these cases. The reason is redacted before it is
logged or posted: common secret formats (`SECRET_PATTERNS` in
`scripts/pr_review.py`), credentials in a URL and the value after
`Authorization:`, `Bearer` or `token` become `[redacted]`, since a gh or git
error can carry them. If someone pushes while
the fixer works, the round is dropped without a label and the new head is
reviewed from scratch. Removing the `needs-founder` label lets the loop resume
with a fresh round count.

**Rate limits pause, they do not stop.** When every deferred key (or the
Founder Proxy) was deferred only by a rate limit (the plan's session, weekly
or usage limit, or a 429, after its one retry), or the fixer hits one, the
loop does not label the pull request and does not stop. The key's check
stays pending, nothing is pushed, and the pass ends. Then the loop makes no
model call for any pull request for `rate_limit_pause_minutes` (30, `LOOP`
in `scripts/pr_loop.py`), and afterwards reviews the same head again. The
pause is the file `loop/rate-limit-pause.json` in the state directory. It
has the same name and format as the Nirmaan loop's pause file, since both
loops run on one plan: a limit either loop hits pauses both. A fix round cut
short by a limit does not count its findings as seen. A `--no-post` run
writes no pause. Any other deferral still stops the loop, and so does a limit
whose retry failed some other way.

**One model call at a time, every pull request each pass.** The shared lock
is held only around each reviewer call (step 1 of "How reviewers run"); the
fixer and the local checks run without it, so the other repository's reviews
go on meanwhile. One pass at a time runs for this repository: the pass holds
its own lock (`loop-nirmaansoftware_ip-nirmaan.lock` in the same folder), and
a second pass that finds it held ends at once. Each pass
takes one step on every open pull request, one the loop is fixing first, then
by number, so a pull request waiting for CI, or one that just ran a review or a
fix, never holds up the others; the steps run one after another, so reviews
still run one at a time. The check that the loop is `main`'s copy runs once,
before each pass, so the pass ends early when `main` may have moved: after the
pass's own auto-merge (GitHub may merge at once), and when `main`'s sha on
origin, read before each step, differs from the one the pass started with
(the founder's merge, the other loop, any merge) or cannot be read. The pull
requests after that wait for the next pass, which refetches `main` and checks
the copy again. A merge that lands while a step runs is seen only before the
next step; the review itself always fetches `main` afresh.

**Records.** Every review call, fixer call and loop step is a line in
`~/.nirmaan/pr-review/calls.jsonl`; per pull request loop state is in
`~/.nirmaan/pr-review/loop/`.

**Turnaround (T).** The time from the first head of a pull request whose
required CI is all green (GitHub's completion time of the last required job,
the newest run of each counting) to its merge (GitHub's `merged_at`).
`scripts/turnaround_report.py` prints T for the pull requests merged since a
date (`--since`, default seven days), split into review calls, fix rounds,
founder or proxy wait (a stop to the next resume), branch updates, and queue
and CI (the rest), with founder-class pull requests on their own line and a
median and 90th percentile for each. It reads GitHub with the gh login and the
call log, prints to the terminal and writes no file; its figures are internal
and are not committed, and a target is called met only after a measured
baseline. For it the loop logs `ci-green-seen` (once per head, with GitHub's CI
completion time), `verdict-posted` (once the review has posted, with each
key's status) and `merged` (once, with GitHub's merge time, when a pull
request the loop finished is no longer open).

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
  environment and the settings file, then install
  [`pr-loop.plist`](pr-loop.plist):

  ```sh
  mkdir -p ~/.nirmaan/pr-loop
  git clone https://github.com/nirmaansoftware/ip-nirmaan.git ~/.nirmaan/pr-loop/ip-nirmaan
  cd ~/.nirmaan/pr-loop/ip-nirmaan && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
  # once: write ~/.nirmaan/pr-loop/env (below)
  cp docs/pr-loop.plist ~/Library/LaunchAgents/online.nirmaan.ip-pr-loop.plist
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/online.nirmaan.ip-pr-loop.plist
  ```

  The plist holds no settings. Its command first sources
  `~/.nirmaan/pr-loop/env`, the same shell file the Nirmaan loop sources, so
  copying a newer plist keeps them. The file holds paths and IDs only, never
  a key's contents:

  ```sh
  export PATH="$HOME/.nirmaan/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
  export NIRMAAN_CLAUDE_CODE="$HOME/.nirmaan/bin/claude"
  export NIRMAAN_REVIEW_APP_ID=<the App ID>
  export NIRMAAN_REVIEW_APP_INSTALLATION_ID=<the installation ID>
  export NIRMAAN_REVIEW_APP_PRIVATE_KEY_FILE=<path to the PEM, outside every repository>
  ```

  `PATH` must reach `git`, `gh` and `claude`. Without the file, a run stops
  before the loop starts and the log says so. To re-install after the plist
  changes on `main`: `launchctl bootout gui/$(id -u)/online.nirmaan.ip-pr-loop`,
  then the `cp` and `launchctl bootstrap` lines above. Every minute it
  resets the clone to `origin/main` and runs `--once`; output, including the
  `git` steps', goes to `~/.nirmaan/pr-review/ip-loop.log`. To stop it:
  `launchctl bootout gui/$(id -u)/online.nirmaan.ip-pr-loop`.
- **Claude Code `/loop`:** in a session opened in the dedicated clone,
  `/loop 10m git fetch origin main && git reset --hard origin/main &&
  .venv/bin/python scripts/pr_loop.py --once, then report its last line`. The
  session only starts the script; it never reviews or fixes a pull request
  itself.

**Settings** (environment): `NIRMAAN_REVIEW_MODEL_PROXY` (the Founder Proxy's
model, default `opus`), `NIRMAAN_LOOP_MODEL_FIXER` (default `sonnet`),
`NIRMAAN_LOOP_FIXER_TIMEOUT_SECONDS` (1800),
`NIRMAAN_LOOP_CHECK_TIMEOUT_SECONDS` (1200), `NIRMAAN_LOOP_GIT_NAME` and
`NIRMAAN_LOOP_GIT_EMAIL` (otherwise the clone's git config, otherwise the head
commit's author), plus the review script's variables above. Under launchd,
set them in `~/.nirmaan/pr-loop/env`. The forbidden
paths, local checks, round limit and authors are `LOOP` in
`scripts/pr_loop.py`.

**What the loop does not do.** It never merges a pull request whose Founder
Proxy verdict is `needs-founder` without the founder's own GitHub review
approving its head, never changes the review configuration, the council or workflows, never pushes
over someone else's push, never runs on a fork or another author's pull
request, never turns auto-merge on for the repository, and never treats a
deferred review as a pass. A fix the loop pushed is agent work like any other:
both keys review it again.

## Rollout

Done in the order of the council record's rollout (R1 to R7): CI hardening,
the path map and its coverage test, seat files and checklists, the reviewer
skill and posting script, a dry run on seeded PRs, then the GitHub App,
CODEOWNERS and the ruleset (R7, 2026-10-18). This page moved from PLANNED to
IMPLEMENTED after the first pull requests merged through both keys.
