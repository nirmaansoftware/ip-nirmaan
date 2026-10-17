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
   founder's own code owner review on GitHub.
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
   `~/.nirmaan/pr-review/`, shared with Nirmaan's script.
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
5. **CI first.** Until `test`, `no-tools`, `physical-design`, `test-union`
   and `dashes` are green on the head, both checks stay pending and no model is
   called.
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
    the founder's latest review approving this head SHA.
11. **Records.** Every model call (tokens, duration, outcome) is logged in
    `~/.nirmaan/pr-review/calls.jsonl`, outside the repository.

**Posting identity.** The review App posts the check runs with a short-lived
installation token scoped to this repository, from these environment
variables: `NIRMAAN_REVIEW_APP_ID`, one of
`NIRMAAN_REVIEW_APP_PRIVATE_KEY_FILE` (a PEM outside every repository) or
`NIRMAAN_REVIEW_APP_KEYCHAIN_SERVICE` (a macOS Keychain item holding the PEM),
and optionally `NIRMAAN_REVIEW_APP_INSTALLATION_ID`. Until the App exists the
script runs as a dry run with the caller's `gh` login: comments plus commit
statuses named `dry-run/review/team-lead` and `dry-run/review/executive`,
which are never green and are not the checks a ruleset requires.

## What is not done yet

Each item is a separate PR or a founder action, in the order of the council
record's rollout (R1 to R7): CI hardening, the path map and its coverage test,
seat files and checklists, the reviewer skill and posting script, a dry run on
seeded PRs, then the GitHub App, CODEOWNERS and the ruleset. This page changes
from PLANNED to IMPLEMENTED only when the ruleset is live.
