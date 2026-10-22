# Council record: two reviews per pull request head (2026-10-18)

Chaired by the chair seat, round 2, after 18 independent positions on one
brief. Read against ip-nirmaan `main` at b1f8c37 (the Founder Proxy merged) and
the open #117 at 27ae019. This record holds no usage, cost or effort figure;
those stay in the internal minutes. The brief, the positions, the minutes and
the work-item list (R0 to R13, named below) are internal documents kept outside
this public repository; each work item that lands is its own pull request, and
this record states every decision in full without them.

**Checked again on 2026-10-19** against `main` at f650396, after #117 merged.
The decisions below are left as the meeting made them; where `main` has since
moved, a dated note says so. The 2026-10-18 capability build-out record that
this record cites (its sections 5 and 12) is not on `main` yet: it is pull
request #118, still open on 2026-10-20.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

This record changes no script, check or gate. Each pull request that
implements a decision here is reviewed on its own, including by the Founder
Proxy against its rule on weakening a review gate.

## The question

The founder asked for every pull request to be reviewed correctly with the
quickest turnaround, preferably exactly two reviews per head (minimum and
maximum two), with CI left as it is. The founder delegated the design to this
meeting; changes to `.github/**`, the review scripts and `council/**` stay
founder class.

## What "two reviews" means

A review is one agent verdict on one head SHA: key 1 and key 2. These are not
reviews and do not count: the fixer, a transport retry, one citation repair of
the same verdict (decision 5), calibration runs, and the founder's own GitHub
approval. A new head after a fix round gets its own two reviews.

After the work items below, every head that is not founder class gets exactly
two reviews. A founder-class head gets two reviews once the founder approves the
fold in decision 3; until then the Founder Proxy stays a third call.

## Decisions

### 1. Key 1 becomes one composite call per head

Supported by every seat that took a view (eda-tooling, ai-engineer,
finance-licensing, verification-lead, design-architect, dft-engineer,
physical-design-engineer, firmware-engineer, legal-compliance, security,
brand-content, site-engineer, partnerships, product-lead, market-research,
tax-accounts). No seat opposed.

1. **One call, one speaker.** The key-1 seat for a head is the lead of the
   owning team that comes first in a fixed precedence list written as data in
   `.github/review-teams.yml` on `main`: Council (security on control files,
   qa-evidence on records and seat files), Verification, Business
   (legal-compliance on licences, finance-licensing on commercial terms),
   Silicon Design, Product and Site, EDA and Platform. That seat's file is
   loaded whole. Content keys are kept (the 2026-10-18 capability
   build-out record, section 5, rule 7): the seat that holds the content key speaks.
2. **What loads.** The "In a review" section of every owning team's lead, plus
   every member checklist whose trigger matches, read verbatim from `main`.
   Member checklists are chosen by path and content triggers written as data
   in `.github/review-teams.yml`, not by team membership. A firmware-only PR
   stops carrying the DFT list; a gate change in `company/workflows.py` starts
   carrying it.
3. **Always loaded.** legal-compliance's three fail items load on every head.
   They are short, and export control has no detector today.
4. **Verdict shape.** The verdict has one required entry per loaded checklist
   (name, owning team, status pass, fail or not applicable, findings with
   citations). The script defers the verdict when an entry is missing,
   duplicated or names a checklist that was not loaded. Any checklist that
   fails fails key 1. A checklist that a trigger selected but that is missing
   on `main` defers the review, as a missing lead section does today.
5. **Export-control flag: proposed to the founder, not decided here** ("For
   the founder", item 7; it takes effect only by the founder's own decision).
   The proposal: every key-1 verdict carries `export_control` (yes or no, with
   cited lines). A missing flag defers. "Yes" adds founder class F and routes
   the head to the founder with no further model call.
6. **Key 2 sees what key 1 loaded.** Key 2 receives the list of loaded
   checklists and key 1's entries, inside the untrusted-data fence, so it checks
   each cited item rather than re-reviewing from scratch.
7. **Loop identity.** The fix-round fingerprint, cache name and carry file use a
   fixed key-1 identity, so a fix that adds an owning team cannot defeat the
   "same finding twice" stop. (Note, 2026-10-19: #117 merged with no
   carry-over, so there is no carry file; the fingerprint and cache name
   remain.)
8. **Switch only on evidence.** The composite call ships off by default. It is
   switched on by its own pull request only after an A/B run on the seeded sets
   (decision 6) shows it catches every domain seed at least as often as the
   per-team calls, with no regression on Verification seeds.

**Checklist gaps to close before the switch.**
- brand-content, site-engineer and tax-accounts have no "In a review" section
  on `main`; each seat writes a short one.
- dft-engineer: triggers on `at_least("test_coverage"` and the DFT and MBIST
  stages in `src/nirmaan/company/workflows.py`, and on the DFT and MBIST
  fixtures.
- firmware-engineer: triggers on `require_irq` and `require_bus_error_trap`.
- physical-design-engineer: triggers on the `physical-design` job in
  `.github/workflows/ci.yml` (tool list, test list, image and tool pins), the PD
  fixtures and the PD docs.
- legal-compliance: the `export_control` flag above, and a content rule for
  specification text and export-sensitive RTL; knowledge-area rules land with
  P1-10.
- product-lead and brand-content: review markers around the site hero, mapped
  to public names and claims, as the partners section is today.
- design-architect: `knowledge/design/**` routes to Silicon Design (with P1-10).

**Disagreed.** eda-tooling proposed one entry per team; dft-engineer,
verification-lead and security asked for one per checklist. Chosen: per
checklist, because a team entry can hide a member list that was never applied.
design-architect asked for an answer to every checklist item; chosen: per
checklist, with item-level citations only on findings, to keep verdicts short
and reduce citation deferrals. Revisit if the domain seeds show misses.
physical-design-engineer noted that one bad citation would void every team's
review in a composite; decision 5 answers that.

### 2. Who holds the keys

Unchanged from the 2026-10-18 capability buildout record, section 5: content
keys stay, the chair holds key 2 on every head today, and the first non-chair
key 2 needs a council decision, a passed seeded set and a founder-class PR.
Two additions (security, tax-accounts): anything that picks a reviewer is read
only from founder-class files on `main`, never from `org_chart.py`; and when a
derived key 2 would be the founder or a role that reports to the founder, key 2
is the chair. The founder is never an agent key.

### 3. The Founder Proxy: fold it into key 2, if the founder agrees

Supported: security, verification-lead, ai-engineer, finance-licensing,
firmware-engineer, legal-compliance, brand-content, market-research,
eda-tooling (as a mechanism). Kept separate: partnerships. No view:
design-architect, qa-evidence, physical-design-engineer, others.

**Recommended to the founder:** on a founder-class head, key 2 is one call on
the strongest model that loads the chair's seat file and
`council/founder-proxy.md` from `main`, and returns pass, fail or
needs-founder with one line per reason. Every comment keeps the wording "acting
under the founder's delegation of 2026-10-18; not the founder". (Note,
2026-10-20: the Proxy's seat file on `main` now says "acting under the
founder's delegation of 2026-10-20".)

**This meeting cannot make that change.** legal-counsel: the founder delegated a
"third-reviewer role"; folding it changes what was delegated, and the proxy's
own item 6 reserves "when the proxy runs" to the founder. The fold therefore
needs a new dated founder record and the founder's own GitHub approval of the
pull request that implements it. Until then the proxy stays the third call on
founder-class heads.

**Before the fold switches on:** the folded key 2 runs offline beside the proxy
on the founder-class seeds and on replays of recent founder-class heads, and
must return needs-founder on every head the proxy does (ai-engineer,
qa-evidence).

**Kept either way, settled now:**
- **A founder floor in the script** (security). A head that touches the review
  machinery gets needs-founder from the script, with no model call deciding it:
  `scripts/pr_review.py`, `scripts/review_map.py`, `scripts/pr_loop.py`,
  `.github/**`, `council/founder-proxy.md`, `council/chair.md`, the base
  checklist record, `.claude/skills/pr-review/**` and the review tests
  (`tests/test_review_teams.py`, `tests/test_pr_review.py`,
  `tests/test_pr_loop.py`, `tests/conftest.py`), which also become founder
  class. The floor itself is settled; this path list is the proposal, and its
  scope is the founder's ("For the founder", item 2). (Note, 2026-10-20: the
  founder's record of that date,
  `council/records/2026-10-20-founder-proxy-widened.md`, withdraws the
  founder floor.) The same floor covers `LICENSE`, `NOTICE`, vendored licence files and
  an `export_control: yes` flag (legal-compliance, legal-counsel). Reason:
  CODEOWNERS is gone, so a control-plane change now merges on one model's
  reading of "weakening"; the founder's record already reserves weakening the
  gates, licence terms and export control. A floor is a strengthening and needs
  no extra review.
- **Wider proxy items** (partnerships, brand-content): any new or changed public
  statement about a named client, design partner or customer returns
  needs-founder (removing a name does not); a new capability, performance or
  compliance claim on a public page returns needs-founder unless a founder
  record delegates it. Both change the proxy's seat file, so both wait for the
  founder's approval. (Note, 2026-10-19: no pull request for them is open; the
  proxy's seat file on `main` is unchanged, and the question stays with the
  founder, "For the founder", item 3.)
- **Classes C (licence and third-party) and F (export control)** end with the
  founder's own GitHub approval of the head; no agent pass closes them.
  (Note, 2026-10-20: see "The founder's answers" below for the Founder
  Proxy's seat file on `main` since 30b5825.)
- **`council/README.md`** "What stays with the founder" still says founder-class
  pull requests wait for the founder's own approval on GitHub, which no longer
  matches the live proxy (legal-counsel). It is corrected to describe the proxy
  and the floor. (Note, 2026-10-20: `council/README.md` on `main` now
  describes the Founder Proxy and the founder's widening of that date; the
  floor is withdrawn.)

**Disagreed.** partnerships wanted the proxy kept as a separate gate; its
concern (partner claims escaping) is met by the wider item, not by a third call.
security accepted the fold but said it is the founder's call, which this record
agrees with. site-engineer noted that the `<meta>` and `<title>` trigger sends
routine SEO edits to the founder classes; narrowing a founder class is reserved
to the founder, so it is listed as a founder question, not decided.

### 4. Key 2 runs after key 1, on the current models

Sequential: eda-tooling, ai-engineer, finance-licensing, design-architect,
physical-design-engineer. Parallel: security.

Key 2 keeps running only after key 1 passes. Reason: in sequence, a failing head
never spends a key-2 call; in parallel the saving is under a minute on passing
heads, while each fix-round push restarts the long `physical-design` job, so
fewer pushes and shorter lock holds matter more. security's two reasons are met
another way: key 1's output reaches key 2 only inside the untrusted-data fence
(work item R5), and independence is measured by testing key 2 alone on seeds
with key 1 forced to pass (decision 6). Revisit if the turnaround split shows
key-2 queueing dominates.

Models stay as they are (key 1 the current mid model, key 2 and the proxy the
strongest). No model, prompt or seat-section change without a recorded
calibration rerun (ai-engineer, qa-evidence). design-architect's proposal to
move key 1 on floor paths to the strongest model waits for the domain seeds.
The prompt is reordered so fixed rules and checklists come first and per-head
facts follow, provided security confirms the nonce fence holds.

**Disagreed.** security (parallel keys). Recorded as dissent.

### 5. Speed

1. **Turnaround metric** (product-lead, market-research, eda-tooling,
   ai-engineer). T is the time from the first head whose required CI is all
   green to the merge commit, from GitHub check-run completion and merge times
   joined to the call log and loop events. It is split into queue wait, review
   calls, fix rounds, conflict updates and founder or proxy wait, reported
   weekly and internal only, beside the catch rate so speed is never the only
   number. Founder-class heads are reported on their own line. The target is
   set internally and is called met only after a measured baseline.
2. **Lock** (eda-tooling, ai-engineer). The shared lock is held only during
   model calls, never during the fixer or local tests. It changes in both
   repositories in one pair, since the lock is shared. More than one slot is
   considered only after the composite call lands.
3. **Citation validation** (qa-evidence, eda-tooling, ai-engineer,
   verification-lead, security). Strip a worktree prefix from cited paths.
   Accept an explicit `main:path:line` citation when that line exists on
   `main`. A bad citation on a minor or info finding drops that finding with a
   note; the verdict stands. A bad citation on a major, blocker or critical
   finding gets one repair of the same verdict with the error shown, then
   defers. A verdict with a bad citation can never become a pass by repair or
   drop. A finding that matches a "Fails when" line is a blocker by rule
   (site-engineer). The call log records verdict status, findings by severity
   and the validation error.
4. **Protected-path findings** (eda-tooling). A finding on a path the fixer may
   not touch skips the fixer and labels the pull request `author-fix`; a new
   head clears it. The fixer stays barred from protected paths (security,
   firmware-engineer).
5. **Shape rules** (product-lead), enforced by the loop with the rule named in
   its comment: one owning team per pull request where possible; founder-class
   paths not mixed with ordinary paths; generated files and mechanical renames
   in their own pull request; no stacked pull requests; a soft cap on changed
   lines outside fixtures and generated files; and a hard rule that the diff
   fits the review's size limit uncut. Only the hard rule stops a review.
6. **Sync provenance** (site-engineer). For a sync pull request the script
   checks the named Nirmaan commit and the hashes of the shared files and gives
   "match" or "no match" to both keys as a fact; no match fails closed.

**Disagreed.** market-research proposed a lower soft cap; product-lead's
evidence that merge time follows stops and waits, not size, was preferred.
eda-tooling would defer a bad major citation with no repair; one repair was
chosen because the #113 and #117 deferrals were not defects.

### 6. Quality with two reviews

Supported by qa-evidence, verification-lead, ai-engineer, security,
finance-licensing and every domain seat that listed seeds.

1. **Seeded sets per seat, outside both repositories**, because reviewers can
   search the head and `main`. No marker in title, body or branch name. Seeds
   cover every "Fails when" line, clean controls, one cross-team pull request
   with one bad half, injection cases (an instruction in a filename, a code
   comment and an RTL comment; a gate weakening dressed as a strengthening),
   and the domain seeds the seats listed (DFT, physical design, firmware,
   Silicon Design, legal, Business, partner claims, public copy). Each seed runs
   several times through the real script without posting. Only aggregates and
   seed digests are ever committed.
2. **Key 2 and the proxy are tested alone**, with key 1 forced to pass.
3. **Metrics per seat:** catch rate, false fails on clean controls, deferral
   rate, each with its sample size. Thresholds are set by qa-evidence after the
   first run.
4. **Weekly audit:** a sample of merged pull requests per repository is
   reviewed by a fresh reviewer that held neither key on it; qa-evidence labels
   the findings; every escape becomes a seed. Existing key-2 fails on heads key
   1 passed are labelled as catches or false fails. Reverts and fixes of merged
   pull requests are tracked (market-research). The founder gets a weekly list
   of control-plane pull requests that merged without the founder's review,
   which with the floor should be empty.
5. **Rerun rule**, written into `docs/REVIEW_MECHANISM.md`: a recorded
   calibration rerun is required before any change to a reviewer's prompt,
   seat review section, checklist, model, the composite switch or the fold.

### 7. #117 merges only after three changes

security reproduced that `git patch-id --stable` gives the same id when a Python
`return` moves out of an `if`, so a different head could inherit a pass.
eda-tooling and #117's own key 1 found the same.

1. Carry-over is keyed on the exact diff bytes of the pull request (a hash of
   the diff, not a patch-id), the required CI is green on the new head, and the
   carried verdict is revalidated against it.
2. No carry-over when Verification owns the pull request (verification-lead:
   graded code may have moved on `main`) or when the head is in founder class A.
3. Carry-over is void when `NOTICE`, `LICENSE` or a vendored licence file
   changed on `main` since the reviewed head (legal-compliance).

**Disagreed.** physical-design-engineer judged patch-id safe for PD paths; the
reproduced whitespace case decides it.

**Note, 2026-10-19: #117 merged without a carry-over.** Before it merged, the
verdict carry-over was removed from #117 altogether (commit ddeed45, which
keeps this loop the same as Nirmaan's decision M4 that a new push voids both
keys), so every new head is reviewed from scratch and items 1 to 3
above apply to no code on `main`. #117 merged (f650396) with the rest of its
scope: one step for every open pull request each pass, only the tests related
to the changed files in a fix round's local check (CI still runs the whole
suite), and a pass every 60 seconds (`docs/pr-loop.plist`). Should a
carry-over be proposed again, items 1 to 3 are its minimum conditions.

### 8. Order of work

One series owns `scripts/pr_review.py`, `scripts/pr_loop.py`,
`scripts/review_map.py` and `.github/review-teams.yml`: one pull request at a
time (product-lead, security, eda-tooling, physical-design-engineer). Calibration
sets are built in parallel, outside the repositories. #118, #120, #121, #122 and
#114 do not touch those files and go ahead; the checklist pull request waits for
#118, which edits `council/README.md`.

Order: #117 amended; the founder floor; metrics; loop speed; fencing; checklist
sections, proxy wording and hero markers (in parallel, `council/**` and `site/**`
only); the composite call (off); the A/B and switch; the fold (when the founder
decides); P1-05 with a corrected file list (CODEOWNERS no longer exists; the
founder-class tests move into the floor pull request); P1-10 with P1-11, written
as trigger data. The full list is in the work items.

(Note, 2026-10-19: "#117 amended" is done in the sense of the note under
decision 7: #117 merged with the carry-over removed, so work item R1 has no
remaining code change. The founder floor is next in the series.) (Note,
2026-10-20: the founder's record of that date withdraws the founder floor, so
it is not built.)

## Gates

| Gate | Owner seat |
|---|---|
| #117 carry-over uses exact diff bytes, never on Verification-owned or class A heads, void on licence-file changes (2026-10-19: met by removal; #117 merged with no carry-over) | security (eda-tooling implements) |
| Floor returns needs-founder on every listed path with no model deciding (2026-10-20: withdrawn by the founder's record of that date) | security |
| T defined, measured from GitHub and the call log, baseline before any target is called met | product-lead |
| Lock free during fixer and local tests, in both repositories | eda-tooling |
| No path from a bad citation to a pass | qa-evidence |
| PR-controlled strings and key 1's output fenced | security |
| Every member checklist loads by trigger; missing entry or checklist defers | verification-lead |
| brand-content, site-engineer, tax-accounts sections written and loaded | qa-evidence |
| Composite switched on only after the A/B on seeds | verification-lead |
| Fold only after the founder's record and approval, and the shadow match | ai-engineer (security key 1) |
| Seeded sets per seat, key 2 and proxy alone, weekly audit, rerun rule | qa-evidence |
| Export-control flag on every key 1; class F detected (once the founder decides item 7) | legal-compliance |

## For the founder

These wait for the founder's own decision; the council does not make them.

1. **The fold** (decision 3): a new dated founder record and the founder's own
   approval of the pull request that implements it. Until then the proxy stays.
2. **The floor's scope** (decision 3): the list of review-machinery paths, and
   whether all of `council/**` should also go to the founder outright, as the
   brief's wording suggests.
3. **The proxy's wider items** (partner statements, public capability claims):
   they change the proxy's seat file.
4. **Narrowing the `<meta>` and `<title>` trigger** (site-engineer): narrowing a
   founder class is the founder's alone. Not proposed by this record.
5. **The capability buildout record, section 12 item 4** ("approval of the
   founder-class P1 PRs"): whether it means the founder or the proxy.
6. Every pull request in the work items that touches the review machinery will
   wait for the founder's own approval once the floor is live, and the proxy
   already reserves most of them today. (Note, 2026-10-20: the floor is
   withdrawn; see "The founder's answers".)
7. **The export-control flag** (decision 1, item 5): export control waits for
   the founder and for counsel's scope.

## Open questions, sent to owners

- security: the exact floor path list, and whether the prompt reorder keeps the
  nonce fence.
- ai-engineer: whether a second lock slot is affordable after the composite
  lands.
- qa-evidence: thresholds after the first calibration run.
- product-lead: the T baseline.
- legal-compliance: content patterns for specification text and export-sensitive
  RTL; scope waits for counsel.

## Dissent

- security: key 1 and key 2 should run in parallel, for independence and
  injection isolation.
- partnerships: keep the Founder Proxy as a separate gate.
- eda-tooling: one verdict entry per team; no citation repair on major findings.
- design-architect: an answer per checklist item, and the strongest model for
  key 1 on floor paths if domain seeds miss.
- physical-design-engineer: patch-id carry-over is safe for PD paths.
- market-research: a lower soft cap on pull request size.

## The founder's answers

The items under "For the founder" are the founder's to decide and to record.
This council record does not record the founder's answers.

**Note, 2026-10-20.** The founder's record of that date
(`council/records/2026-10-20-founder-proxy-widened.md`) says that the Founder
Proxy now decides founder-class pull requests except new spending,
contracts/counsel and sending; that it decides the open founder items
(capability record items 1, 2, 3, 10 and the #128 reading); and that the
founder floor is withdrawn. It names none of the items under "For the founder"
in this record. The Proxy's seat file on `main` (`council/founder-proxy.md`)
also sends export control to the founder and fails a change that weakens a
review gate. The council's reading, resting only on the first clause: a
founder-class pull request that carries one of the items under "For the
founder" is reviewed by the Founder Proxy, and waits for the founder where it
adds spending, touches contracts, counsel or export control, or turns on
sending. This record records no answer from the founder to any item.
