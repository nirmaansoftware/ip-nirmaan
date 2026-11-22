# Council record: RTL pilot retrospective (P3-R, 2026-11-14)

The capability build-out record
(`council/records/2026-10-18-capability-buildout.md`, section 10, gate G11,
owner design-architect) ends the RTL pilot with "a retrospective that decides
format and process changes". This is that retrospective. It also decides the
items that later work put on its agenda: the causes of the failed live trials
and the harness variants to compare, frontier cases, whole-flow cases, outside
calibration, where held-out files live, and which wave 2 (Verification) work
that waited for it may start.

Eighteen seats gave round 1 positions independently; the chair decided. Read
against ip-nirmaan `main` at fbbf479. Nothing in the repository was changed by
the meeting: this record changes no code, document, check or gate. Each pull
request that implements a decision is reviewed on its own.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

## Who decided what

- The council decided every item below except the two marked otherwise.
- The founder was away. Two founder items were answered by the orchestrator
  session, on the founder's in-session instruction of 2026-11-14 to keep work
  moving and answer open questions with its own recommendation. They are cited
  below as "orchestrator, on the founder's in-session instruction of
  2026-11-14". They are not founder decisions, and the founder can overrule
  either:
  - usage for four follow-on runs (the harness variants, the frontier trials,
    the outside calibration calls, the whole-flow trials) is approved, one
    batch at a time, each stopping on any plan-limit message;
  - the visibility of held-out files is not changed. The council recommends an
    option (decision 9) and the founder decides.
- The top-up batch of decision 1 is not one of those four runs. It starts only
  on the orchestrator's answer under the same instruction, or the founder's.

## Facts checked

On `main` at fbbf479, checked by the chair or by the seat named:

1. Eight skills have a knowledge document and a check record
   (`knowledge/design/`, `capability/records/knowledge/`), and
   `capability/levels.json` totals read knowledge 8, practised 0, proven 0.
   The four pilot skills on the Knowledge track (rtl_microarchitecture,
   rtl_lint, synthesis_awareness, reset_design) have no document and no check
   record (qa-evidence; the chair confirmed). The brief said all twelve were at
   Knowledge; that was wrong.
2. `evals/results/` holds two records, both of case rtl/rr-arbiter:
   `evals/results/2026-11-14-claude-code-claude-opus-5-5` (3 trials) and
   `evals/results/2026-11-14-claude-code-claude-opus-5-5-2` (2 trials), merged
   in #203. `capability/levels.json` shows the arbitration group at 4 of 5,
   lower bound 0.376, not counted.
3. `knowledge/design/rtl_design.md` lines 105 to 106 say an optional
   `[tasks]` section "runs, say, a proof and a cover from one file". The gates
   refuse exactly that: `src/nirmaan/integrations/eda.py:648` (formal.run) and
   `:751` (the cover check). The tool descriptions a seat is shown
   (`src/nirmaan/company/tools.py:144-150`) say nothing about single-task
   setups.
4. `knowledge/design/pipeline_design.md:98` says "Prove every parameter
   combination as its own task", which reads as the same refused construct
   (design-architect).
5. `src/nirmaan/company/tools.py` is not among the fingerprinted files
   (`CODE`, `src/nirmaan/runtime/harness.py:152-165`), yet its parameter
   descriptions reach the prompt (`docs/HARNESS.md`, "Changes to the harness
   since M73"). An edit there changes what every seat reads and makes no group
   stale (qa-evidence and ai-engineer, independently; the chair confirmed).
6. A skill digest covers that skill's own card and document only
   (`src/nirmaan/evals/cases.py:76-87`). Correcting rtl_design.md makes the
   rtl_design group stale and no other.
7. A changed harness code file makes every group stale. A new Claude Code
   version starts a separate group that never pools with the old one
   (`docs/CAPABILITY_LEVELS.md` lines 52 to 73). Must-fail controls are
   required for skills of the design and verification domains
   (`src/nirmaan/company/evidence.py:13`); apb and axi are domain protocols.
8. The seat runs with no tools (`docs/HARNESS.md` line 30): it answers in text
   and sees no gate message before its attempt is spent.
9. The review stops a diff over 200,000 bytes (`docs/REVIEW_MECHANISM.md`
   line 172).

Not on `main` yet. The batch's other records are in pull requests #204 to #206
and a queue behind them, and become checkable as each merges. From those
records, as the batch reported them: 31 trials with knowledge documents and 31
without, every trial re-judged the same; with documents 22 passed, without 27.
Of the 9 failed trials with documents, 6 followed the `[tasks]` sentence and
were refused before review, 2 were the seat's own faults caught by its own
simulation gate, and 1 never reached the model (a plan limit). No case defect
was found. Every trial used one attempt. This record names no level from those
records: a level is what `capability/levels.json` shows after a merge.

## Decisions

Each decision names its owner seat and its first pull request.

### 1. Pilot exit (G11): not met; correct the documents, one fixed top-up, one read

The exit is not met on `main`'s own facts: 8 of 12 skills at Knowledge, none
Practised.

a. **Knowledge track.** The four missing documents and their check records are
   written now, under decision 3. Owner design-architect. First pull request:
   the four documents (one batch); the check records follow in their own.

b. **Corrections.** rtl_design.md "Proof setup" is corrected to what the gates
   accept: exactly one `.sby`, no `[tasks]` section, `mode prove`, `[files]`
   listing every submitted RTL file, and the platform's own cover rerun.
   pipeline_design.md:98 is corrected likewise. The two notes owed under
   decision 7 for the seat's own faults go into rtl_design.md in the same
   change, so the document changes once. The gates do not loosen to match a
   document (eda-tooling: the cover check rewrites only an unprefixed `mode`
   line, so a task setup would not map to one verdict). Owner
   design-architect. First pull request: the correction to both documents; new
   check records with the gate-claims field (decision 3) follow in their own,
   from a different session.

c. **All eight documents are checked for gate claims before the top-up.** A
   correction is only a sentence that a gate contradicts, cited by path and
   line in the check record. This matters because a correction makes that
   skill's group stale: it must never be a way to shed failed trials.
   qa-evidence holds key 1 on those records.

d. **The top-up, fixed here before any trial runs.** 5 trials on each of the 7
   pilot cases, 35 in all, with knowledge documents, on the same model, the
   same harness fingerprint and the same Claude Code version as the batch. No
   harness code file, and no file in decision 4's bundle, changes on `main`
   before the read. The runner confirms the user-level instruction file that
   reaches seat calls is byte-identical to the batch's. Records are split as
   in decision 10. A plan-limit stop resumes until all 35 are done.

e. **One read.** Levels are read once from `capability/levels.json`, after
   every evidence record of the batch and the top-up is merged. A group that
   counts earlier, mid-queue, decides nothing. Every trial stays counted,
   including the six refused `[tasks]` trials in the apb, axi and
   buffering_flow_control groups, whose digests did not change. There is no
   second round and no extension.

f. **Outcome.** Six or more Practised with all twelve at Knowledge: the exit is
   met. Fewer: the pilot closes with the shortfall recorded here by an
   addendum, and those skills are measured again in the first evidence batch
   on the harness chosen under decision 4.

Owner of the top-up and the read: verification-lead; of G11: design-architect.
First pull request: the first top-up record, after (b) and (c) are merged.

Why this and not the others. Exiting now would close the pilot on a known
document defect. Fixing the harness first would make every group stale before
any could count. Seats differed on the top-up's shape: product-lead wanted only
the short and borderline skills topped up, ai-engineer a total of 10 per skill,
verification-lead and design-architect 5 on every case. The chair chose 5 on
every case because it is uniform, cannot be read as chosen after seeing which
cases failed, and gives the restarted groups a full count.

### 2. The ablation: met as a run, with no measured benefit

The exit item "the ablation run" is met when the records without documents are
on `main`, where the levels generator lists them apart. They never count toward
a level, so they queue behind the evidence records and may merge after decision
4's bundle. What it showed: on these cases the documents gave no measured
benefit, the intervals overlap, and one document sentence cost six trials. The
cases are near the model's ceiling, so the run could not have shown a benefit.
The Knowledge level means a document was checked against its sources, not that
it helps. Every later live batch carries an arm without documents on the same
cases, its size fixed in the batch plan. Owner verification-lead. First pull
request: the first record without documents.

### 3. Format and process: kept, plus a gate-claims check

- Kept: the card (at most 2,000 characters), the document (at most 12,000;
  8,000 for a document that reaches many seats), three sessions per skill,
  evals first in their own pull request, 3 or 4 documents per pull request.
- **Gate claims, in the check record.** The check record gains a field: every
  sentence that names a tool, gate, mode, option, section or file rule is
  listed with the gate code that confirms it (path and line) or a test id. A
  sentence about an option the gate restricts says that it is restricted. A
  sentence about a tool with no gate behind it is marked unverified. Owner
  qa-evidence, with verification-lead for the levels generator. First pull
  request: the field in `capability/records/knowledge/README.md`, the schema
  check and the reviewer checklist line.
- **Gate claims, mechanical.** Each pre-run refusal is declared as data on its
  tool, and a test fails when a knowledge sentence names a refused construct
  without saying so; a second test runs every `.sby` example under
  `knowledge/` through the gate's own checks. Owner eda-tooling. First pull
  request: the test over `knowledge/` (no prompt change). Rendering the
  refusals into the seat's contract waits for decision 4's bundle.
- The Sources rule is restated in every wave 2 writing brief: sources an agent
  can read in full; summarise and cite; no tables, register maps or figures;
  no member-only or vendor EDA text. Owner legal-compliance.

Disagreement: eda-tooling wanted the mechanical test instead of a field; four
seats wanted the field. Both are adopted: the field covers sentences no parser
can read, the test cannot be forgotten.

### 4. Causes accepted; two harness variants; one bundle, then a quiet window

The cause tally stands: of the failures, most were gate refusals whose message
named the fault and which the seat never saw.

- **Variants.** (1) Tools in the loop: the seat calls brokered lint,
  simulation and formal during its attempt. (2) Three attempts with repair
  text against one. The knowledge cap variant is dropped: no trial was declined
  or cut.
- **Baseline.** The default harness, run again in the same batch on the same
  commit with arms interleaved, never the pilot's records. Counts are fixed in
  the batch plan before the first trial. Frontier cases (decision 5) carry the
  pass-rate comparison; pilot cases carry the secondary measures (refusals,
  proofs submitted, attempts used) and a no-regression check. A variant trial
  carries its variant label, is listed apart and never counts toward a level.
- **Tools in the loop is its own milestone**, with these conditions (security,
  eda-tooling): brokered tools only, through the tool broker under the seat's
  role, no shell, file or network tool; no credential in a tool run's
  environment; paths limited to the seat's workspace, so held-out files are
  unreachable; a cap on calls and time per attempt, a timeout being a failed
  attempt; every call recorded; in-loop runs advisory, the platform's gate
  runs alone judging; the server code and tool pins in the fingerprint.
- **The bundle** (the named-variants milestone) is one fingerprint change: the
  single-task rule in the formal tools' contract; the tool definitions brought
  into the fingerprint (fact 5); seat calls that load no user-level
  instruction file, shown by a canary test; and the `--harness <name>` switch
  with the attempts variant.
- **Order.** The bundle merges only after decision 1's read. From that merge
  until the pull request that names the default harness, a quiet window: any
  harness change may merge (tools in the loop, the whole-flow runner option),
  and no evidence trial runs. Wave 2's live batch and the re-measured pilot
  skills run after the default is named.

Owners: ai-engineer (variants, the default), eda-tooling (bundle, broker),
security (conditions). First pull request: the bundle, opened as a draft now
and made ready after the read; it is control plane, so the Founder Proxy
reviews it. Tools in the loop reserves its own milestone number when it starts.

### 5. Frontier cases: run now, privately, as calibration

The three frontier cases run now from the local copy, after a recorded case
validation (the reference passes, every mutant fails). Counts with and without
documents are fixed in a private plan before the first trial. The records stay
private, are labelled calibration for good, and are never relabelled or pooled.
The cases are not pushed. Their purpose is headroom and case sanity; the
variant comparison of decision 4 uses its own baseline arm. Usage: orchestrator,
on the founder's in-session instruction of 2026-11-14. Owner verification-lead.
No pull request until decision 9 is settled by the founder.

security preferred waiting for decision 9 as the safer course. The chair chose
to run because nothing is pushed and no held-out file enters a prompt.

### 6. Whole-flow trials credit no skill

A whole-flow trial (no upstream stage fixed, only the final block judged) gives
one verdict that cannot say which skill earned it. It credits no skill level.
Its records form their own labelled group, keyed by every digest in the flow,
listed apart and never pooled with fixed-upstream trials. A record lists the
stages and the skills exercised and keeps stage boundaries visible. Where a
flow ends in firmware, the driver's register map comes from the RTL stage's
output, not the specification. The runner option lands inside decision 4's
quiet window. Owners: verification-lead (rule), eda-tooling (runner). First
pull request: the runner option with the labelled group, control plane.

market-research, partnerships and product-lead see the whole-flow pass rate as
the number a buyer reads first. The chair agrees it is its own measure, and
none of it reaches a public page until a committed record backs it.

### 7. Two standing rules

- **Failure to curriculum.** Every failed live trial labelled "model" yields a
  knowledge note or a must-fail case, or a written reason why not, listed in
  the batch's pull request and naming the failing run.
- **Gate claims.** Decision 3's check applies to every knowledge document in
  every wave. A sentence about a tool that the gate refuses is a defect,
  however the source reads.

Owner verification-lead for the first, qa-evidence for the second. First pull
request: both rules in `knowledge/README.md` with decision 3's field.

### 8. Outside calibration: RTLLM only, after the default harness is named

One baseline before wave 2's live batch: the RTLLM set through the merged
adapter, with and without documents, compared only with our own bare-model
run. Conditions (legal-compliance): the copy stays private with its upstream
licence and commit pin; no problem text, testbench or reference in any
committed file, record or transcript; records carry ids, digests, counts,
source and a credit line, as `docs/OUTSIDE_CALIBRATION.md` sets out. CVDP is
not run until a qualified lawyer has read its tool-label terms, which is the
founder's to arrange. VerilogEval is not used. No calibration figure goes on a
public page. Usage: orchestrator, on the founder's in-session instruction of
2026-11-14. Owner ai-engineer. First pull request: the RTLLM calibration
record.

### 9. Held-out files: the council's recommendation to the founder

Not decided here. Nothing changes until the founder decides (orchestrator, on
the founder's in-session instruction of 2026-11-14).

Recommended: a private store for the held-out bytes of new and frontier cases,
with a public manifest of digests, so a public record names exactly which
held-out bytes judged it. Each digest covers the whole file with a private
salt per case, and files are listed by opaque id. Existing cases stay public
and are marked as exposed. Held-out bytes are pulled only by the live runner
and by trusted jobs (never a job that runs pull request content), and never
appear in a log or an uploaded artifact. No paid plan is assumed; any spending
is the founder's. A pushed branch is no protection. Whether reference RTL meant
for sale stays public is a separate question for the founder, and a later
removal does not recall earlier copies. A private store also changes what a
future evaluation agreement must say about confidentiality (legal-counsel).

Seven seats gave a view (security, eda-tooling, legal-compliance,
finance-licensing, market-research, legal-counsel, tax-accounts); none
preferred staying public. Owner of the follow-up, once decided: eda-tooling,
with security.

### 10. Record splits and trial time

- A record's trial count is fixed in the batch plan before the run, never by
  outcome. Each part holds whole trials, is a complete record with its own
  rejudge, and is sized from measured bytes to stay well under the review's
  limit. Groups pool across records, so splitting changes no level.
- Evidence records queue ahead of records that never count.
- The runner stops after any record that shows a plan-limit message and
  resumes until the planned count is done.
- The planning estimate in `docs/LIVE_EVAL_EVIDENCE.md` is replaced by one
  computed from the committed records, and a batch is planned on the largest
  case's measured mean with a margin. A wave whose trials include long tool
  runs measures one real run first and keeps large artifacts out of the diff
  by digest (physical-design-engineer, dft-engineer).

Owner verification-lead; ai-engineer for the estimate. First pull request: the
estimate, once the pilot's records are merged.

### 11. Trial counts, interrupted trials, protocols

- More than 5 trials is allowed. The count is uniform across the batch, fixed
  in a committed plan before the first trial, and read once.
- An interrupted trial stays a failed trial. ai-engineer proposed that a trial
  whose model call never started be replaced, for later records only. The
  chair did not adopt it: it would make a level easier to reach, and the
  runner's stop rule already limits the loss to one trial.
- `protocols` joins `MUST_FAIL_DOMAINS`. Every apb and axi case already
  carries a must-fail control, so no level moves. Owner verification-lead.
  First pull request: that one-line gate change with its test, gate semantics,
  so the Founder Proxy reviews it.

### 12. Practice leads

No RTL practice lead was needed, and one would not have caught the `[tasks]`
sentence: the checklist was missing, not the reviewer. For wave 2 no practice
lead is seated at the start. The path rule for `knowledge/verification/**`
(team Verification, key 1 verification-lead, with Business as for other
knowledge paths) lands by itself in a founder-class pull request, so documents
are not held up. A department's lead is seated later, in the hiring pull
request, only when the review loop's records show that department's pull
requests waiting on key 1. Names stay with the founder. Owner
verification-lead. First pull request: the path rule.

This departs from the wave 2 plan's five leads at the start. security wanted
none or one; design-architect wanted leads only as each department's work
arrives.

### 13. Wave 2 items that waited for this meeting

| Item | Ruling | Must follow |
|---|---|---|
| Skills batches, one per department | start now | card format unchanged; at each release, regenerate the site's counts and run the release checks of gates G8 and G9 (site-engineer) |
| Knowledge documents | start per department once its skills batch, the path rule of decision 12 and the field of decision 3 are merged | decisions 3 and 7; the Sources rule in the brief; 3 or 4 per pull request; 8,000 characters for broad documents |
| Check records | with each document batch | the gate-claims field; a different session |
| The two eval cases that need the skills batches | start after those batches | ordinary cases stay public until decision 9 is settled |
| Hiring pull request | waits | decision 12 |
| Live batch | waits for the default harness of decision 4 | a committed plan with counts, an arm without documents, cause labels, decision 10 |

Owner verification-lead (wave owner). First pull request: the first
department's skills batch.

## Dissent and positions not adopted

- ai-engineer: replace a trial whose model call never started (decision 11).
- ai-engineer: the group digest should cover every document the packet
  carried, not only the skill's own. Not adopted now: it is a level-rule
  change that would restart every group, and belongs to a later meeting with
  the re-measured pilot's records in hand.
- security: wait for decision 9 before any frontier trial (decision 5).
- eda-tooling: a mechanical test instead of a check-record field (decision 3).
- product-lead: top up only the short and borderline skills (decision 1).
- verification-lead: the top-up's usage is the founder's to grant. Kept as a
  gate below.
- legal-counsel: counsel should review before any calibration result is
  published. Kept: no calibration figure goes on a public page (decision 8).

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| RT1 | The corrected documents and their new check records, with gate claims, are merged before the first top-up trial | design-architect |
| RT2 | The top-up starts only on the orchestrator's answer under the founder's instruction, or the founder's; 35 trials, fixed here | verification-lead |
| RT3 | No harness code file and no part of the bundle merges before the one read of decision 1 | ai-engineer |
| RT4 | No evidence trial between the bundle's merge and the pull request that names the default harness | ai-engineer |
| RT5 | Tools in the loop merges only with every condition of decision 4 shown by a test | security |
| RT6 | Variant, whole-flow, frontier and calibration trials carry labels and never count toward a level | verification-lead |
| RT7 | No knowledge pull request passes key 1 with a gate sentence that cites no gate | qa-evidence |
| RT8 | No held-out byte of a frontier case is pushed, logged or uploaded before the founder settles decision 9 | security |
| RT9 | No level, projection or calibration figure on a public page beyond what `capability/levels.json` shows | brand-content |

## Open, for the founder

1. Decision 9: where held-out files live, and whether reference RTL meant for
   sale stays public.
2. The two orchestrator answers above, to confirm or overrule, and the top-up's
   usage (gate RT2).
3. A lawyer's reading of the CVDP terms, if that set is wanted (decision 8).
4. Names, if a practice lead is seated later (decision 12).

## Addendum (2026-11-15): the one read, and the pilot exit

This addendum is the record that decisions 1e and 1f call for. It adds the
read and its outcome. It changes no decision, code, record, level or gate
above.

### Who decided what

- The council fixed the rule: decision 1 above, and
  `council/records/2026-11-15-pilot-topup-reruns.md` (the ruling) for the
  top-up's re-run trials.
- That the read ran now, and this addendum with it: orchestrator, on the
  founder's in-session instruction of 2026-11-14. It is not a founder
  decision, and the founder can overrule it.
- Owner of the read: verification-lead; of gate G11: design-architect.
  qa-evidence checks the claims below (the ruling, decision 3).

### What was read

Read once, on `main` at 482ff5a, after `scripts/capability_levels.py --check`
reported that `capability/levels.json` matches the records. Gate RR1 of the
ruling held: #287 was merged, and both sentences the ruling named were
corrected (`causes.md` in
`evals/results/2026-11-15-claude-code-claude-opus-5-5-limit-12` and in
`evals/results/2026-11-15-claude-code-claude-opus-5-5-11`).

`evals/results/` holds 45 records. Every trial is re-judged the same, and
the levels generator refuses no record (`refused_records` is empty):

| Set | Records | Trials | Passed | Counts toward a level |
|---|---|---|---|---|
| The batch, with documents | 14, dated 2026-11-14, ending `opus-5-5` to `opus-5-5-14` | 31 | 22 | yes |
| The batch, without documents | 14, dated 2026-11-14, ending `without-knowledge` to `without-knowledge-14` | 31 | 27 | never (decision 2) |
| The top-up, the planned 35 | 11, dated 2026-11-15, ending `opus-5-5` to `opus-5-5-11`, and 3 ending `-limit-12` to `-limit-14` | 35 | 26 | yes |
| The top-up's re-runs | 3, dated 2026-11-15, ending `-12`, `-13`, `-14` | 7 | 6 | in the file, but they raise no level (the ruling) |

Every trial that counts ran on model claude-opus-5-5, harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`,
Claude Code 2.1.325.

### The plan-limit incident, in full

1. Decision 1d fixed the top-up at 35 trials, 5 on each of the 7 pilot cases.
2. On 2026-11-15 at 08:36Z the plan's usage limit was reached. The runner's
   check did not recognise the message and ran on. Nine trials failed within
   about 2 seconds each, with no model answer and no judge run.
3. Two of the nine were recorded as failed at once: trials 2 and 3 of
   `evals/results/2026-11-15-claude-code-claude-opus-5-5-11` (rtl/apb-gpio).
4. The other seven (rtl/apb-gpio 2, rtl/axil-timer 5) were first held out of
   the repository by the runner. They were committed later, in #287, as the
   records ending `-limit-12`, `-limit-13` and `-limit-14`.
5. After the limit reset the runner ran those seven slots again. The re-runs
   were merged before the failures they followed, as the 2026-11-15 records
   ending `-12` (rtl/apb-gpio, 1 of 2 passed), `-13` and `-14`
   (rtl/axil-timer, 5 of 5 passed).
6. So 42 top-up attempts exist: the planned 35, nine of them limit failures,
   and 7 re-runs. Nothing was deleted, moved or relabelled.
7. The ruling: the re-runs are attempts 36 to 42 and raise no level; the nine
   limit failures stay failed trials of their groups (decision 11 above); a
   skill is Practised at the read only if its group counts both in
   `capability/levels.json` and on the planned 35.
8. The batch of 2026-11-14 had one such trial of its own: trial 2 of
   `evals/results/2026-11-14-claude-code-claude-opus-5-5-12` (rtl/axil-timer).
   It was recorded as failed at the time and is counted so.

The limit failures ran no model work. They say nothing about a skill either
way, and they count as failed trials because the rule was fixed before the
run.

### The read

Two counts per group, as gate RR2 requires. "All attempts" is
`capability/levels.json` on `main`. "Planned 35" is the same script,
unmodified, on a scratch copy without the three re-run records. Each cell is
passed of trials, then the 95 percent Wilson lower bound. The bar is at least
5 trials and a lower bound of at least 0.5 (`docs/CAPABILITY_LEVELS.md`).

| Skill | Level | All attempts | Planned 35 | Trials no judge ran on | Digest | Why |
|---|---|---|---|---|---|---|
| rtl_design | Practised | 32 of 42, 0.615 | 26 of 35, 0.579 | 9 | 012eb9b7 | counts on both; all 7 cases, top-up only |
| arbitration | Practised | 9 of 10, 0.596 | the same | 1 | 53dff4b1 | counts on both; rtl/rr-arbiter, batch and top-up pooled |
| buffering_flow_control | Practised | 18 of 20, 0.699 | the same | 2 | 9ce453d4 | counts on both; rtl/skid-buffer and rtl/sync-fifo, pooled |
| pipeline_design | Practised | 5 of 5, 0.566 | the same | 0 | 7a9c0840 | counts on both; rtl/skid-buffer, top-up only |
| axi | Knowledge | 15 of 23, 0.449 | 10 of 18, 0.337 | 8 | 171d2446 | lower bound under 0.5 on both |
| apb | Knowledge | 12 of 20, 0.387 | 11 of 18, 0.386 | 7 | 5eb05f03 | lower bound under 0.5 on both |
| fsm_design | Knowledge | 7 of 13, 0.291 | 2 of 8, 0.071 | 6 | c4aaa4ba | lower bound under 0.5 on both; rests on rtl/axil-timer alone |
| control_logic_design | Knowledge | 4 of 10, 0.168 | 3 of 8, 0.137 | 5 | 3979d44f | lower bound under 0.5 on both; rests on rtl/apb-gpio alone |
| rtl_microarchitecture | Knowledge | no trial | no trial | | | document and check record count; no eval case names the skill |
| rtl_lint | Knowledge | no trial | no trial | | | the same |
| synthesis_awareness | Knowledge | no trial | no trial | | | the same |
| reset_design | Knowledge | no trial | no trial | | | the same |

Notes on the table:

- The two counts give the same level for every skill, so the committed file
  and the ruling agree.
- A digest is the first 8 hex digits of the group's skill digest in
  `capability/levels.json`. Every group above is on the harness, model and
  Claude Code version named under "What was read".
- rtl_design and pipeline_design were corrected under decision 1b, so their
  batch groups are stale (rtl_design 22 of 31, pipeline_design 5 of 5) and
  only the top-up counts for them. The other six digests did not change, so
  the batch and the top-up pool, and every batch trial stays counted,
  including the six refused `[tasks]` trials (decision 1e).
- Every one of the twelve has a document under `knowledge/` and a check
  record under `capability/records/knowledge/` that counts
  (`knowledge/architecture/rtl_microarchitecture.md`; the other eleven under
  `knowledge/design/`). The four written under decision 1a are at Knowledge
  for the first time.
- For axi and fsm_design the group fell short with limit failures in it.
  Without the top-up's five rtl/axil-timer limit failures, and with every
  other trial kept, axi is 15 of 18 and fsm_design 7 of 8: not a level, and
  stated only under that label (the ruling, decision 3, which calls these
  the judged-only counts).
- apb and control_logic_design fall short on any reading. rtl/apb-gpio has
  a model failure of its own (`causes.md` in the 2026-11-15 record ending
  `-12`).
- Nothing is Proven.

### Outcome: the exit is not met

Decision 1f needs six or more Practised with all twelve at Knowledge. The
read gives twelve of twelve at Knowledge and four Practised (rtl_design,
arbitration, buffering_flow_control, pipeline_design). The exit is short by
two. This was the one read: there is no second round and no extension
(decision 1e).

The pilot closes with this shortfall recorded. The other exit items stand as
decided above: the ablation run is met as a run (decision 2, its 14 records
are on `main`), and this record is the retrospective.

### What happens next, as already decided

- The eight skills short of Practised (axi, apb, fsm_design,
  control_logic_design, rtl_microarchitecture, rtl_lint, synthesis_awareness,
  reset_design) are measured again in the first evidence batch on the harness
  chosen under decision 4 (decision 1f; decision 13, the live batch). The four
  from the Knowledge track need an eval case that names them before any trial
  can count.
- Gate RT3 no longer holds the bundle of decision 4: its pull request may be
  made ready. From its merge until the pull request that names the default
  harness, the quiet window of decision 4 applies and no evidence trial runs
  (gate RT4).
- No evidence batch starts until the runner stops at the first trial with no
  model answer, shown by a test, and never holds a record out of the
  repository (the ruling, decision 4 and gate RR5).
- Whether an infrastructure failure gets its own class goes to a later
  meeting and never applies to the pilot's records (the ruling, decision 4).
- A second case for fsm_design and control_logic_design is a question for
  that batch's plan (the ruling, positions not adopted).

### Open, for the founder

5. This read and its outcome, and the ruling it rests on, to confirm or
   overrule.

## Addendum (2026-11-22): the W2-L1 read

This addendum records the one read of W2-L1, the first evidence batch on the
default harness, which the pilot's outcome above and the wave 2 table call
for. Its plan, with the counts fixed before trial 1 and all 153 slots, is
`evals/plans/2026-11-18-w2-l1.md`. This addendum adds the read and its
outcome. It changes no decision, code, record, count, level or gate above.

### Who decided what

- The rule is the batch plan's, fixed before trial 1: one read, after every
  one of the 153 records has merged, with no top-up, extension, replacement
  or second read. A trial stopped by a plan limit stays failed and is never
  run again (`council/records/2026-11-15-pilot-topup-reruns.md`).
- Nothing was chosen at the read: it ran once the last record part merged.
- Owner of the read: verification-lead (the wave owner). qa-evidence checks
  the claims below.

### What was read

Read once, on `main` at 45a22c8, the merge of the last of the 32 record parts
(#373 to #424). `scripts/capability_levels.py --check` reports that
`capability/levels.json` matches the records, and the levels generator
refuses no record (`refused_records` is empty). All 153 records are on
`main`, failed ones included; each holds one trial, and every trial is
re-judged the same (`rejudge.json` in each record).

| Arm | Trials | Passed | Counts toward a level |
|---|---|---|---|
| E, with knowledge documents | 136, 8 on each of the 17 cases | 119 | yes |
| N, without knowledge documents | 17, 1 on each case | 13 | never |

Every arm E trial ran on the default harness (attempts-3)
`sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`,
model claude-opus-5-5, Claude Code 2.1.325, from `main` 01adfe9. Arm N ran on
the same harness without documents,
`sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39`.

### The read

Each row is the skill's counted group in `capability/levels.json` at 45a22c8.
The interval is the 95 percent Wilson interval. The bar is at least 5 trials
and a lower bound of at least 0.5 (`docs/CAPABILITY_LEVELS.md`). "No judge"
counts trials the file marks unjudged: the work was refused before review,
and such a trial is a failed trial of its group. A digest is the first 8 hex
digits of the group's skill digest.

| Skill | Cases | Passed of n | Wilson interval | No judge | Digest | Level |
|---|---|---|---|---|---|---|
| apb | rtl/apb-gpio, rtl/apb-regs | 14 of 16 | 0.640 to 0.965 | 0 | 5eb05f03 | Practised |
| axi | rtl/axi4-lite-regs, rtl/axil-timer | 16 of 16 | 0.806 to 1.000 | 0 | 171d2446 | Practised |
| fsm_design | rtl/axil-timer | 8 of 8 | 0.676 to 1.000 | 0 | c4aaa4ba | Practised |
| control_logic_design | rtl/apb-gpio | 6 of 8 | 0.409 to 0.929 | 0 | 3979d44f | Knowledge |
| directed_testing | dv/directed-irq-ctrl, dv/random-crc, dv/scoreboard-mac | 24 of 24 | 0.862 to 1.000 | 0 | 6bf35095 | Practised |
| constrained_random | dv/random-crc | 8 of 8 | 0.676 to 1.000 | 0 | 7e497fa2 | Practised |
| reference_modelling | dv/scoreboard-mac | 8 of 8 | 0.676 to 1.000 | 0 | 69565f35 | Practised |
| code_coverage | dv/coverage-irq-ctrl | 7 of 8 | 0.529 to 0.978 | 0 | b5a1c9b8 | Practised |
| equivalence_checking | dv/equiv-gray | 5 of 8 | 0.306 to 0.863 | 0 | 98c09011 | Knowledge |
| formal_verification | dv/formal-credit-counter | 8 of 8 | 0.676 to 1.000 | 0 | 496f8d92 | Practised |
| sva | dv/formal-credit-counter | 8 of 8 | 0.676 to 1.000 | 0 | dd2c6a58 | Practised |
| assertion_coverage | dv/formal-credit-counter | 8 of 8 | 0.676 to 1.000 | 0 | 9a2e389e | Practised |
| model_checking | dv/prove-deep-counter | 8 of 8 | 0.676 to 1.000 | 0 | ad51c9e6 | Practised |
| verification_planning | dv/plan-irq-ctrl | 6 of 8 | 0.409 to 0.929 | 2 | 930e0e5f | Knowledge |
| root_cause_analysis | debug/root-cause-uart-tx | 7 of 8 | 0.529 to 0.978 | 1 | b65cd62f | Practised |
| failure_triage | debug/triage-three-bugs | 0 of 8 | 0.000 to 0.324 | 8 | 1a7f2700 | Knowledge |
| python_verification | dv/cocotb-crc, CI only | no trial | | | | Knowledge |
| rtl_design | the seven RTL cases | 54 of 56 | 0.879 to 0.990 | 0 | 012eb9b7 | Practised |
| arbitration | rtl/rr-arbiter | 8 of 8 | 0.676 to 1.000 | 0 | 53dff4b1 | Practised |
| buffering_flow_control | rtl/skid-buffer, rtl/sync-fifo | 16 of 16 | 0.806 to 1.000 | 0 | 9ce453d4 | Practised |
| pipeline_design | rtl/skid-buffer | 8 of 8 | 0.676 to 1.000 | 0 | 7a9c0840 | Practised |
| systemverilog | dv/directed-irq-ctrl | 8 of 8 | 0.676 to 1.000 | 0 | b6d97df5 | Practised, see below |

Notes on the table:

- The batch's 17 target skills are the first seventeen rows: the four pilot
  skills with a case (apb, axi, fsm_design, control_logic_design) and the
  thirteen wave 2 verification skills with a case. Twelve reach Practised:
  apb, axi, fsm_design, directed_testing, constrained_random,
  reference_modelling, code_coverage, formal_verification, sva,
  assertion_coverage, model_checking and root_cause_analysis. Five stay at
  Knowledge: control_logic_design, equivalence_checking,
  verification_planning, failure_triage and python_verification.
- rtl_design, arbitration, buffering_flow_control and pipeline_design are
  not targets. Their pilot groups went stale when the harness changed, so
  before this batch they were at Knowledge (`capability/levels.json` at
  01adfe9 showed 40 Knowledge and none Practised). Their cases were in the batch,
  and on the current harness all four are Practised again.
- systemverilog is Practised by the level rule, has no knowledge document,
  and is not a W2-L1 target: dv/directed-irq-ctrl names it, and the levels
  test allows a skill to be Practised with no document (#408). It is in the
  file's totals, but it is not a result of the batch.
- python_verification has no trial. Its one case, dv/cocotb-crc, has the seat
  write executable test code, so it runs only in CI, under its own 9-slot
  list, and those trials have not run. directed_testing is read on its 24
  trials of the three other cases only.
- The older pilot groups of eight of these skills stay in the file, each
  marked stale (the harness changed). They count toward nothing.
- After the read, `capability/levels.json` shows 17 Practised, 24 Knowledge
  and 0 Proven. Nothing is Proven.

### Arm N, reported only

Arm N never counts toward a level and is reported beside the read only.
With documents, 119 of 136 trials passed (Wilson interval 0.809 to 0.920);
without documents, 13 of 17 (0.527 to 0.904). At one trial per case the arm
shows only a batch-wide difference: the intervals overlap, and no skill or
case conclusion follows. Its four failed trials:

- slot 57, dv/random-crc: stopped by a plan limit with no model answer (see
  below);
- slot 76, debug/root-cause-uart-tx: model;
- slot 152, dv/plan-irq-ctrl: model;
- slot 153, debug/triage-three-bugs: the same missing input as every arm E
  trial of that case.

### Caveats

- Thirteen of the targets with trials rest on one case each: fsm_design,
  control_logic_design, constrained_random, reference_modelling,
  code_coverage, equivalence_checking, formal_verification, sva,
  assertion_coverage, model_checking, verification_planning,
  root_cause_analysis and failure_triage. A level on one case says how the
  model did on that case.
- Slot 57 (`evals/results/2026-11-19-claude-code-claude-opus-5-5-without-knowledge`)
  is a plan-limit trial in arm N. It is committed as failed, was never run
  again, and counts toward no level.
- failure_triage scored 0 of 8 because of a missing input, not a measurement
  of the model. Nothing the triage seat receives names the testbench's
  verdict-line contract (the plusarg and the verdict format), so the repro
  gate refused every testbench and no judge ran (`causes.md` in each of the
  eight records). Fixing that changes the skill's card or document, so its
  group goes stale and it needs a new batch.
- The other nine failed arm E trials are labelled the model's in their
  `causes.md` (root-cause-uart-tx 1, plan-irq-ctrl 2, equiv-gray 3,
  coverage-irq-ctrl 1, apb-gpio 2).
- code_coverage and root_cause_analysis are Practised at 7 of 8, the
  smallest count that clears the bar; one more failure in either would have
  left it at Knowledge.
- Any level that `capability/levels.json` showed on `main` while only part of
  the batch was merged is an interim figure and is not cited here.

### Outcome

Seventeen skills are Practised on the current harness: twelve of the batch's
17 targets, the four RTL skills above, and systemverilog. This was the one
read of W2-L1: there is no top-up, extension or second read. It does not
reopen the pilot exit, which closed with its shortfall recorded in the
addendum above.

### What remains, as already planned

- The nine CI trials of dv/cocotb-crc wait for the live-eval workflow to be
  able to run them; until then python_verification stays at Knowledge.
- rtl_microarchitecture, rtl_lint, synthesis_awareness, reset_design and the
  fifteen wave 2 verification skills that no case names had no trial; each
  needs an eval case before a trial can count.
- A second case for the single-case skills, and the failure_triage input,
  are left to a later plan; this read decides neither.

### Open, for the founder

6. This read and its outcome, to confirm or overrule.
