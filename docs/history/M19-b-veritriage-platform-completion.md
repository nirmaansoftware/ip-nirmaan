# VeriTriage Milestone 19 - Platform Completion

Written 2026-09-05 on a branch cut from the 2026-08-04 VeriTriage tree (PR #4),
as VeriTriage's own milestone 19, and merged after v1.24.0. In this
repository's numbering M19 became the Nirmaan organizational OS
(`M19-organizational-os.md`), so this entry takes the letter `b`. The branch
proposed v1.15.0; that version number was already taken by the M19
organizational OS, so this work carries no version of its own. Design doc:
`docs/PLATFORM_COMPLETION.md`.

The milestone with no new subsystem. It closes the four items the
VeriTriage-era future-work list (now in `context-before-M43.md`, items 5.1,
5.2, 5.3, and 5.6) had been carrying as "designed, not built", and it is
deliberately the last one that can be described that way.

**OCP and Wishbone packs (was 5.1).** The last two open interconnects. Same
shape as APB/AHB: concepts, a transfer state machine, patterns with
playbooks, real spec references. OCP covers request/response handshake
stalls, SResp ERR/FAIL accepted as data, precise bursts delivering a length
they did not declare, and out-of-order responses within one thread. Wishbone
covers phases that never terminate, ERR consumed as data, RTY livelock, and
CYC/STB framing violations. Eight fixtures, one per pattern. 44 packs, 100
patterns. No matcher, reasoning or report change was needed, which was the
point of the seam.

**The learning feedback loop (was 5.3).** M4 designed `FeedbackRecord` and
left the readers unbuilt; M13 built the readers for the recommendation votes
and stopped short of acting on them. Both halves now close:

* A `rule-gaps` learner groups failures by signature digest and counts
  engineer overrules, speaking only after two judgments and two overrules.
  It proposes no rule and edits no pack: a gap is an argument for human
  attention. Surfaced in the dashboard as "Needs a New Rule", computed there
  straight from history so the dashboard still needs no learning store.
* `useful_recommendations` / `false_recommendations` become a weight table
  that reorders the advice a run produces. A reorder only, deterministic,
  and inert without history. Applied in the pipeline only when a learning
  context was recalled.

The guarantee is tested directly: advice may move, the graph, classification,
signals and ranked hypotheses may not.

**Reference resolution (was 5.2).** `Reference.uri` had been a hook with
nothing behind it. The two uses pull in opposite directions (a company spec
database cannot ship here; fetching public specs would put a network call in
a deterministic pipeline), so a registry settles both. The built-in resolver
is a static offline catalogue of public standards; a test parses the package
and fails if it ever imports `urllib`, `requests`, `httpx`, `socket` or
`subprocess`. A site adds its own resolver above the catalogue in priority so
an internal mirror shadows the public page. Resolution happens at the report
boundary and copies rather than mutates, because packs are process-wide
constants.

**Cross-regression diffing (was 5.6).** "It worked yesterday, what landed
since?" Both halves existed and had never been introduced: the regression
database has recorded `execution.git_commit` since v0.4.0, and the M7
provider seam can list commits. New `CHANGE_RANGE` capability and an optional
`changes_between()` defaulting to `None`, so every existing provider keeps
working. The honesty rule drove the design: an unanswerable question returns
`None`, while an empty commit list is a real answer meaning both runs were
built from the same code, which points at the environment rather than the
RTL. Keeping those distinguishable required a raw git runner, because the
existing one collapses "succeeded with no output" into `None`. The manifest
provider stopped claiming every capability: an export cannot answer a live
range query. Reachable as `WorkspaceServices.changes_since_last_green()`.

**Real bug found and fixed on the way.** There is one reasoning rule per
failure pattern, and each rule called `match_patterns` itself, so a single
analysis ran one full pass over every pattern, clause and node *per pattern*:
roughly 100 passes to use one row of each. Quadratic in pattern count, and
invisible until this milestone's eight new patterns made the suite time jump.
Rules built together now share one pass, memoized on the Evidence Graph by
weak reference and compared by identity, so it can neither serve a stale
result nor keep a graph alive. `analyze()` is about 9x faster (10 runs:
0.863s to 0.095s) and the VeriTriage suite of the time dropped from 48.9s to
23.5s while gaining 65 tests. `test_pattern_rules_share_a_single_match_pass`
fails if the passes come back.

**Eight defect fixes** from an adversarial review of the branch (its last
commit), each confirmed by running code and each with a test: two wrong
reference links (the catalogue became an ordered list, most specific first,
and a test pins all 43 built-in citations); three wrong regression-diff
answers (an inverted range now checked with `merge-base --is-ancestor`, the
newest green run as the baseline even without a commit, and truncation
reported in `RegressionDiff.truncated`); a crash comparing naive and
timezone-aware `created_at` values (naive read as UTC); a rule-gap summary
that ran two sentences together and reported the alphabetically first cause
instead of the most reported one; and a `_SharedMatchPass` docstring that
overclaimed, now backed by a node and edge count check.

New tests: 78 across the branch (763 passed, 1 skipped in the VeriTriage-only
suite of the time). New package: `references/`. New modules:
`learning/learners/gaps.py`, `feedback/reweight.py`,
`engineering/regression_diff.py`.

**Follow-ups named at the time, still open:**
- Live link validation for public specs. It would put a network call in a
  deterministic pipeline; if wanted, it belongs in a separate offline check
  of the catalogue in CI, not in `analyze()`.
- Nothing consumes `RuleGap` beyond the dashboard. An agent that read gaps as
  memory would need care, because it edges toward learning influencing a
  conclusion.
- Nothing surfaces the regression diff in the HTML report, the CLI, or MCP
  yet; it is reachable only as a `WorkspaceServices` method.

**Merged after v1.24.0.** The merge kept `main`'s structure: no version bump,
this history file instead of a `context.md` entry, `main`'s README with the
pack counts updated, and the roadmap counts block regenerated (44 packs).
