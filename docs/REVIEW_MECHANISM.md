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

## What is not done yet

Each item is a separate PR or a founder action, in the order of the council
record's rollout (R1 to R7): CI hardening, the path map and its coverage test,
seat files and checklists, the reviewer skill and posting script, a dry run on
seeded PRs, then the GitHub App, CODEOWNERS and the ruleset. This page changes
from PLANNED to IMPLEMENTED only when the ruleset is live.
