# Council record: the top-up's re-run trials at the one read (2026-11-15)

The pilot retrospective
(`council/records/2026-11-14-pilot-retrospective.md`, decision 1) fixed a
top-up of 35 trials and one read of the levels. During the top-up the plan's
usage limit was reached, nine trials failed without a model answer, and seven
of them were run again. This record rules whether those seven re-runs count at
the one read, and whether the read happens now.

Three seats gave round 1 positions independently (verification-lead,
qa-evidence, design-architect); the chair decided. The meeting was kept to the
seats that own the evidence: the top-up, the read and the level rule
(verification-lead), the claims (qa-evidence), and gate G11 with the RTL
skills measured (design-architect). Read against ip-nirmaan `main` at b0bc225
and the head of #287 at 00675f1. The chair and the seats ran their checks on
scratch copies outside the repository. This record changes no code, record,
level or gate: it applies decisions 1, 10 and 11 of the retrospective as
written.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below. The founder was away. That the council
rules now is the answer of the orchestrator, on the founder's in-session
instruction of 2026-11-14. It is not a founder decision, and the founder can
overrule it. Nothing here is reserved for the founder: it adds no spending,
contract, counsel, sending, public name or licence term.

## The question

For the one read, do the seven re-run trials count?

- (A) Yes: the run's purpose was 35 judged attempts and the limit is an
  infrastructure fault.
- (B) No: the count was fixed in advance, so the re-runs do not count and the
  limit failures stay failed. The evidence set is the planned 35.
- (C) Something else, for example the limit failures listed as infrastructure
  failures and never judged.

## Facts checked

1. The retrospective, in its own words
   (`council/records/2026-11-14-pilot-retrospective.md`):
   - decision 1d (lines 121 to 127): the top-up is "fixed here before any
     trial runs", 5 trials on each of the 7 pilot cases, 35 in all;
   - decision 1e (lines 129 to 134): "Every trial stays counted" and "There is
     no second round and no extension";
   - decision 1f: six or more Practised with all twelve at Knowledge meets the
     exit; fewer, and the pilot closes with the shortfall recorded and those
     skills are measured again in the first evidence batch on the harness
     chosen under decision 4;
   - decision 10 (lines 310 to 316): a record's trial count is fixed before
     the run, never by outcome, and the runner "stops after any record that
     shows a plan-limit message";
   - decision 11 (lines 330 to 333): "An interrupted trial stays a failed
     trial." A proposal to replace a trial whose model call never started was
     not adopted, because "it would make a level easier to reach, and the
     runner's stop rule already limits the loss to one trial".
2. The level rule. `docs/CAPABILITY_LEVELS.md` lines 28 to 35: on a tool-judged
   case a trial with no judge run is a failed trial of its group and "is never
   left out". `practised()` in `src/nirmaan/evals/levels.py` does that
   (`judged = bool(trial.judge_runs)`, counted in `unjudged`). No list takes a
   single such trial out of its group: `not_tool_judged` is a property of the
   case, `without_knowledge` and `calibration` are labels set at run time, and
   `refused_records` holds whole records.
3. What happened (qa-evidence and verification-lead read the trial files). At
   2026-11-15 08:36Z the limit was reached. The runner's check did not
   recognise the message and ran on. Nine trials failed within about 2
   seconds each, with no model answer and no judge run:
   - 2 in `evals/results/2026-11-15-claude-code-claude-opus-5-5-11`
     (rtl/apb-gpio), on `main`;
   - 7 that the runner held out of the repository (rtl/apb-gpio 2,
     rtl/axil-timer 5), now in #287 as the records ending `-limit-12`,
     `-limit-13` and `-limit-14`.
   After the reset the runner ran those 7 again. The re-runs are on `main` as
   the 2026-11-15 records ending `-12`, `-13` and `-14` (#280, #282, #284).
   So 42 attempts exist: the planned 35, nine of them limit failures, and 7
   re-runs.
4. The batch plan is private. This record rests on the count of 35 that
   decision 1d commits, not on the plan.
5. Current groups under each reading, computed by the chair with
   `scripts/capability_levels.py`, unmodified, on scratch copies, and
   recomputed by qa-evidence. Passed of trials, then the Wilson lower bound.
   This is not the read.

   | Skill | All 42 attempts | The planned 35 (re-runs out) | The 7 held-back failures out (`main` at b0bc225) |
   |---|---|---|---|
   | rtl_design | 32 of 42, 0.615, counts | 26 of 35, 0.579, counts | 32 of 35, 0.776, counts |
   | arbitration | 9 of 10, counts | the same | the same |
   | buffering_flow_control | 18 of 20, counts | the same | the same |
   | pipeline_design | 5 of 5, counts | the same | the same |
   | axi | 15 of 23, 0.449, no | 10 of 18, 0.337, no | 15 of 18, 0.608, counts |
   | fsm_design | 7 of 13, 0.291, no | 2 of 8, 0.071, no | 7 of 8, 0.529, counts |
   | apb | 12 of 20, 0.387, no | 11 of 18, 0.386, no | 12 of 18, 0.438, no |
   | control_logic_design | 4 of 10, 0.168, no | 3 of 8, 0.137, no | 4 of 8, 0.215, no |
   | Practised | 4 | 4 | 6 |

   The first two readings give the same level for every skill. Only the third
   reaches six, the number in decision 1f, and it is `main` today only because
   seven failed trials are not yet in it.
6. Two sentences in the records are wrong (qa-evidence, verification-lead; the
   chair confirmed both):
   - in #287 at 00675f1, the last sentence of `causes.md` in the record ending
     `-limit-12` says the `not_tool_judged` rule leaves these trials out, "so
     these records do not move any level". The same pull request's
     `capability/levels.json` counts them and moves two levels;
   - on `main`, the last sentence of `causes.md` in the record ending `-11`
     calls the later trials "the trials that replace them". Decision 11
     refused replacement.
7. The three records in #287 carry the manifest ids of the re-run records on
   `main` (ending `-12`, `-13`, `-14`); the directory names differ. The level
   code loads both sets and refuses neither (verification-lead).

## Decisions

### 1. The re-runs earn nothing; the limit failures stay failed

The seven re-runs are attempts 36 to 42. They are the replacement that
decision 11 refused and the extension that decision 1e rules out. They raise
no level at the read. The nine limit failures are trials of the planned 35 and
stay failed trials of their groups, as the level rule already counts them.

How the read expresses this without a code change:

- Nothing is deleted, moved or relabelled. The re-run records stay on `main`
  as committed, and the seven held-back failures are merged (#287). Every
  attempt that was made is in the repository.
- The read is taken from `capability/levels.json` on `main` once #287 is
  merged, as the level code computes it from all 42 attempts.
- A skill is Practised at the read only if its group also counts on the
  planned 35: the same script, unmodified, on a scratch copy without the
  three re-run records. Where the two differ, the planned 35 decide. The
  re-runs add trials and passes to a group, so this check can only lower a
  level, never raise one.
- The exit addendum gives both counts for every group the incident touched.

On today's records the two agree on every skill (fact 5), so the committed
file and the rule say the same thing.

Owner verification-lead. First pull request: the exit addendum of decision 1e.

Why not (A) as worded. The purpose of a fixed count is that nobody adds
trials after seeing a result. A limit is an infrastructure fault, and decision
11 already weighed exactly that case and kept the trial failed. Its second
reason, that the stop rule limits the loss to one trial, did not hold in this
run: the stop rule failed and the loss was nine. That is a defect in the
runner to repair (decision 4), not a ground to change the count after the
outcome is known.

Why not (C). It needs a new list in the level code or a false label on a
record, it removes failed trials after their effect was seen, and it is the
only reading that reaches the exit number. A level rule is never changed
between a run and its read.

All three seats took this position. design-architect named it (A) and
verification-lead "(B) by rule, (A) by code": the difference is in the label,
not the result.

### 2. Read now, with no code or rule change first

The read happens once these are merged, in this order:

1. #287, with the sentence of fact 6 corrected to say that the trials count
   as failed in their groups;
2. the correction of the sentence in the record ending `-11` (fact 6), in a
   pull request that touches no trial file.

No level rule, harness file or part of the bundle changes before the read
(gate RT3 of the retrospective). The read is the one read of decision 1e:
there is no second.

Owner verification-lead.

### 3. What the read may claim

- The count of Practised skills from decision 1's reading, and whether the
  exit of decision 1f is met on it. The figure of six on `main` at b0bc225 is
  never cited: it leaves out seven failed trials.
- For axi and fsm_design, that the group fell short with limit failures in
  it, and that those failures ran no model work and say nothing about the
  skill either way. The judged-only counts (axi 15 of 18, fsm_design 7 of 8)
  may be stated only with the label "not a level".
- Skills short of the bar follow decision 1f: measured again in the first
  evidence batch on the harness chosen under decision 4 of the retrospective.

Owner design-architect (gate G11); qa-evidence checks the addendum's claims.

### 4. Before the next evidence batch

- The runner stops at the first trial that returns no model answer, judged by
  the trial's structure and not by the wording of a message, shown by a test
  on the message this run met.
- The runner never holds a record out of the repository and never gives two
  records one id.
- Whether an infrastructure failure gets its own class (listed, never judged)
  goes to a later meeting. If adopted it applies only to batches whose plan
  is committed after the change, never to the pilot's records, and it is a
  gate semantics change that the Founder Proxy reviews. The proposal not
  adopted in decision 11 of the retrospective may be heard again there, since
  the reason given against it did not hold in this run.

Owners: eda-tooling (runner), verification-lead (rule).

## Positions not adopted

- design-architect: the next batch plan should give fsm_design and
  control_logic_design a second case, because each rests on one. Not decided
  here: it belongs to that batch's plan (owner verification-lead).

No seat dissented from decisions 1 to 4.

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| RR1 | The read is taken only after #287 and the correction to the record ending `-11` are merged, with both sentences of fact 6 corrected | qa-evidence |
| RR2 | A skill is Practised at the read only if its group counts both in `capability/levels.json` and on the planned 35; the addendum gives both counts | verification-lead |
| RR3 | No record of the batch or the top-up is deleted, moved or relabelled, and no level rule changes, before the read | verification-lead |
| RR4 | No page, record or pull request cites six Practised from `main` at b0bc225 | qa-evidence |
| RR5 | No evidence batch starts until the runner's stop rule of decision 4 is shown by a test | eda-tooling |

## Open, for the founder

1. This ruling, to confirm or overrule.
