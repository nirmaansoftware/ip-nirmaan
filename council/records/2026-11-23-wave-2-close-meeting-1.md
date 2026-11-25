# Council record: wave 2 (Verification) close, meeting 1 (2026-11-23)

Wave 2 of the capability build-out
(`council/records/2026-10-18-capability-buildout.md`) is closing. Its first
live batch, W2-L1, was read once
(`council/records/2026-11-14-pilot-retrospective.md`, addendum of
2026-11-22). Since that read the wave has corrected one skill card, added
notes to three knowledge documents, written new documents and added second
eval cases, so several groups are stale and several skills have a case that
no trial has run. A second evidence batch, the re-measure batch, is wanted
before the wave's exit is judged.

This is meeting 1 of two. It rules on what must be true before that batch
runs: its cases, how it relates to the groups W2-L1 already read, where it
may run, and the exit items that do not depend on its outcome. It gives no
exit verdict. Meeting 2, after the one read of the batch, gives the verdict
as an addendum to this record.

Ruling, in short:

- **No practice lead is seated.** The condition of decision 12 of the pilot
  retrospective is not met.
- **Three skills are named exceptions to "Practising skills have evals"**:
  log_analysis, regression_intelligence and regression_management. Each is
  recorded as not measured, with what an honest case would need.
- **The second cases are confirmed, except one.** `rtl/apb-gpio-reset` is
  not a second case for control_logic_design: it is the same task as
  `rtl/apb-gpio` with another judge.
- **The re-measure batch is one committed plan, fixed counts, one read.** It
  may add trials on new cases to groups W2-L1 read, under the conditions of
  decision 4. A case W2-L1 read is run again only where a skill it names
  changed.
- **Every trial of the batch runs in CI as the seat account, none on the
  owner's machine**, after gates ET1 to ET4 and ET8 of
  `council/records/2026-11-22-eda-tools-seat-account.md` are met on `main`.
  This answers the question that record left open for security.
- **The plan check's section field and the triage tool's history stay as
  they are for this batch**; both are recorded follow-ups with owners.

Seven seats gave round 1 positions, each as a read-only process of its own
that saw no other position: verification-lead (the wave owner), qa-evidence,
security, ai-engineer, eda-tooling, design-architect and product-lead; the
chair decided. The meeting was kept to the seats that own its questions, as
`council/records/2026-11-22-eda-tools-seat-account.md` and
`council/records/2026-11-19-seat-c-live-refusal.md` were. Read against
ip-nirmaan `main` at 54d3b7c9; the chair rechecked the facts below at
b1eb4933 (the merge of ip#441, which landed during the meeting). No trial
ran, no workflow was dispatched, and this record changes no code, case,
eval record, level, card, document, fingerprint or digest.

A key is an agent review. Nothing here is a person's approval, a release, or
a claim that a design is ready to be made in silicon.

## Who decided what

- The council decided every item below. The founder can overrule any of it.
- The founder was away. Under the founder's in-session instruction of
  2026-11-22 to keep work moving and answer open questions by a meeting or
  by its own recommendation, the orchestrator session had given five interim
  answers. They are not founder decisions and were not council rulings. The
  council confirms, narrows or overrules each in decision 5.
- Reserved for the founder and not decided here: the usage for the batch
  (decision 5, item 4), a paid or founder-obtained source for systemverilog
  (decision 8), and names, had a lead been seated.
- This record loosens no gate and lifts no refusal. It adds conditions
  before a live trial may run.

## Facts checked

Each line was checked by the chair at b1eb4933 unless a seat is named as the
source. "Inference" marks what nobody ran.

1. Levels. `capability/levels.json`: 17 Practised, 24 at Knowledge, none
   Proven, and four skills with no level because their document changed
   after its check record or has none yet (equivalence_checking,
   verification_planning, control_logic_design, cdc_verification).
   `scripts/capability_levels.py --check` passes (qa-evidence).
2. Stale since the W2-L1 read. failure_triage (its card now names the
   plusarg and the verdict line, ip#438), equivalence_checking (ip#431; the
   open ip#443 changes it again), verification_planning and
   control_logic_design (notes, ip#439). root_cause_analysis is not stale:
   the same card correction is the draft ip#442. Its group, 7 of 8, stops
   counting when that pull request merges, not when it is marked ready, and
   the committed levels file in it must be regenerated first (qa-evidence).
3. New cases, each on a block no other case uses: `dv/formal-rr-arbiter`
   and `dv/equiv-updown` (ip#429), `dv/coverage-tick-timer` and
   `dv/plan-tick-timer` (ip#436), `debug/root-cause-debounce` and
   `debug/triage-pwm-gen` (ip#441), and, open, `dv/fcov-lifo4` (ip#446), the
   first case that names functional_coverage. Each uses the seat and the
   scorer of the skill's first case (verification-lead).
4. `rtl/apb-gpio-reset` (ip#321) has the same request, upstream files,
   constraints, seat and skills as `rtl/apb-gpio`. It differs by one
   sentence of expected behaviour and by its judge, one must-fail mutant
   where `rtl/apb-gpio` has four and a formal check (design-architect,
   verification-lead, qa-evidence, each from the two case files). The seat
   is given the same task in both.
5. How a group is formed. The key is skill, model, skill digest, harness
   fingerprint and CLI version (`src/nirmaan/evals/levels.py:306`). The
   case, the plan, the machine and the versions of the EDA tools are not in
   it. So trials on a changed digest start a new group, and trials on an
   unchanged digest join the group W2-L1 read: `dv/formal-rr-arbiter` joins
   formal_verification, sva and assertion_coverage; `dv/coverage-tick-timer`
   joins code_coverage; `rtl/apb-gpio` joins apb and rtl_design;
   `dv/cocotb-crc` joins directed_testing. Each of those groups is Practised
   today, so more trials can keep or lower its level (ai-engineer,
   qa-evidence).
6. The live evaluation's CI job pins the same CLI version as W2-L1
   (`.github/live-eval/package.json`), and the default harness fingerprint
   computed there is W2-L1's, `sha256:0ef27db1...` (ai-engineer). A trial in
   CI lands in the same groups as W2-L1's trials, which ran on the owner's
   machine with other versions of Verilator, Yosys and Icarus (inference
   from the tool sets; the records do not name tool versions).
7. On the owner's machine there is no seat account: every gate tool runs as
   the owner, behind the input screen only
   (`docs/LIVE_EVAL_EVIDENCE.md:302`). The record of 2026-11-22 found that
   screen passing seat Verilog that a tool then acts on, and did not name it
   as a control (its decision 1).
8. What the open build of gates ET2 to ET4 (ip#444) leaves with the runner
   account: a Verilator run that is not a lint. `coverage.read` builds seat
   HDL into a Verilator model and runs the built program by its path
   (`src/nirmaan/integrations/eda.py:856-859`). So in CI, as built, the
   coverage cases would run a program built from seat-written HDL as the
   runner, in the step that holds the credential, with the screen as the
   only control (security, eda-tooling; the chair read both places).
9. The live evaluation's job installs SBY and Yices and no `eqy`
   (`.github/actions/live-eval-setup/action.yml:33-36`), and ip#444 does not
   wrap `eqy`. An equivalence trial there would have no judge (ai-engineer,
   eda-tooling).
10. Gate ET1's pull request (ip#445) is open and its tests fail: the
    repaired screen refuses a netlist the flow itself generates. Gate ET1 is
    not met (security, eda-tooling).
11. The three skills of decision 2. `regression.run` is a contract with no
    binding (`src/nirmaan/company/tools.py:135`). The triage binding runs
    with history off (`src/nirmaan/integrations/veritriage.py:59`) and is
    given no database (`veritriage.py:39-43`), so turning the flag on alone
    records nothing. A seat's packet does carry regression_management and
    regression_intelligence where its role provides the planned capability
    (`src/nirmaan/runtime/context.py:298-300`); no gate judges either.
    log_analysis reaches no packet a planned request produces (eda-tooling,
    with a planning probe; ip#441 says the same of the debug stages).
12. `veritriage.py` is in `harness.CODE`
    (`src/nirmaan/runtime/harness.py:289`), and tool definitions are in the
    fingerprint. Turning history on, or binding `regression.run`, changes
    the default fingerprint and makes every counted group stale
    (ai-engineer, eda-tooling).
13. The plan check. `check_against_specs` (`src/nirmaan/vplan.py:325-354`)
    never compares a requirement's `section`; the field is optional
    (`vplan.py:198`), and `docs/VERIFICATION_PLAN.md` lists it as
    optional. The four committed plans already match their specifications'
    sections (eda-tooling, by a local comparison). `vplan.py` is in no
    fingerprint. The expected behaviour text of `dv/plan-tick-timer` says
    "source and section", which is more than the gate judges
    (verification-lead, eda-tooling).
14. Key 1. The five verification departments are units of one Verification
    review team, so no record ever held a wait per department
    (qa-evidence). For the team, measured by verification-lead from the
    review loop's records and the verdict comments: its median key-1 wait
    was inside or below the other teams' range in every period measured, and
    its long waits were session-limit pauses and one loop outage.
15. The founder's approval of live batches
    (`council/records/2026-10-18-capability-buildout.md`, commit 3c9fe7d2)
    names "wave 2 Verification's batch", one batch, "through the local CLI".
    W2-L1 was that batch (qa-evidence, verification-lead).
16. Item 11 of the build-out record, recomputed on 54d3b7c9 with
    `build_organization()` (design-architect): no two active sibling units
    under `verification` hold the same skill set. The units that coincide
    are placeholders with no skill of their own:
    `verification.dynamic.gate_level_power` and `.emulation`;
    `verification.processor.isa`, `.models` and `.accelerator`.
17. Failure to curriculum. `scripts/failure_curriculum.py` on the W2-L1
    records lists nine model-labelled failures with documents and two
    without, none answered yet. The rule allows a note, a must-fail case or
    a written reason (`docs/CAPABILITY_LEVELS.md`, "Failures feed the
    curriculum"); a card change is none of these (qa-evidence).

## Decisions

### 1. Practice leads: not triggered

No lead is seated, and the exit item "managers and leads" stands on the five
department director roles alone. Decision 12 of the pilot retrospective
seats a lead only when the review loop's records show a department's pull
requests waiting on key 1. They do not (fact 14). All six seats with a view
agreed.

The records cannot show a wait per department at all today. The council
orders no work to build that measurement for its own sake. If a later wave
records key-1 time per department, the condition is met when one
department's median wait is at least twice the others' over twenty or more
heads, with limit pauses and outages left out. verification-lead restates
the fact at each wave close. Names stay with the founder.

Owner: verification-lead.

### 2. "Practising skills have evals": three named exceptions

functional_coverage is met by its case once ip#446 merges. log_analysis,
regression_intelligence and regression_management are recorded as
exceptions, in these words: tool available, no eval case, not measured, at
Knowledge. None is described as a Practising capability on any public page.

What an honest case needs, per skill (fact 11):

| Skill | Needs before a case can name it |
|---|---|
| log_analysis | a workflow stage or refinement that plans it for a seat that reads logs |
| regression_management | a bound `regression.run` that a gate can judge |
| regression_intelligence | a database for the triage binding, history on, a history seeded per trial, and a test that one trial's history cannot reach another's |

The second and third change the default fingerprint (fact 12), so they are
not built during this wave's close. They are planned with a later wave's
batch and return to the council before they merge. The route of editing the
three cards so that the tier no longer computes was rejected by every seat
that spoke: the seats would still hold the tools, so the cards would
misdescribe them.

The list is closed. A test fails when any other skill that computes as
Practising by tool has no case and is not on the list (product-lead). Owner:
verification-lead for the list and its test in
`docs/EVAL_SKILLS_MUST_FAIL.md`; eda-tooling for the three builds;
brand-content for the public wording, with gate RT9.

### 3. Second cases

1. Confirmed as second cases: `dv/formal-rr-arbiter` (formal_verification,
   sva, assertion_coverage), `dv/equiv-updown` (equivalence_checking),
   `dv/coverage-tick-timer` (code_coverage), `dv/plan-tick-timer`
   (verification_planning), `debug/root-cause-debounce`
   (root_cause_analysis), `debug/triage-pwm-gen` (failure_triage).
   `dv/fcov-lifo4` is confirmed as functional_coverage's first case.
2. `rtl/apb-gpio-reset` is not a second case for control_logic_design
   (fact 4): one task, two judges, and the second judge was written from a
   failure already seen. It stays in the repository as a must-fail control
   and runs in no evidence batch until a ruling says how its trials would
   count. control_logic_design remains a single-case skill; a second case on
   a different control structure belongs to the Design wave.
3. These skills wait on one case, each recorded as an open item of the
   wave: constrained_random, reference_modelling and model_checking (the
   next verification batch's plan; owner verification-lead); fsm_design,
   arbitration, pipeline_design and control_logic_design (the Design wave;
   owner design-architect); systemverilog (a knowledge document first,
   decision 8). python_verification gets its first trials in this batch
   (decision 4).
4. Before trial 1, a committed test shows what a `use sat` setup does to
   the mutants of `dv/equiv-updown`, as
   `tests/test_dv_crc_gray_evals.py` shows for `dv/equiv-gray`, since that
   strategy is what failed in W2-L1 (verification-lead).

### 4. The re-measure batch

**The rule for groups already read.** W2-L1's figures stay as recorded;
nothing here tops up, extends or reads W2-L1 again. A later batch may add
trials to a group that was read only if: its committed plan names the group
with its count and passes before trial 1; the trials are on a case the group
has not run, or on a case of item 2 below; and the read shows the batch's
own trials beside the pooled figure, with the commit and the environment
each batch was judged on. A case already read is run again only when the
digest of a skill it names has changed, and then the plan names every other
group its trials join. `dv/coverage-irq-ctrl` and `dv/formal-credit-counter`
are not run again: for an unchanged skill that is a top-up.

**Cases.** Thirteen, in three kinds:

| Case | New group for | Joins a group W2-L1 read |
|---|---|---|
| dv/equiv-gray, dv/equiv-updown | equivalence_checking | |
| dv/plan-irq-ctrl, dv/plan-tick-timer | verification_planning | |
| debug/triage-three-bugs, debug/triage-pwm-gen | failure_triage | |
| debug/root-cause-uart-tx, debug/root-cause-debounce | root_cause_analysis (after ip#442) | |
| rtl/apb-gpio | control_logic_design | apb, rtl_design |
| dv/fcov-lifo4 | functional_coverage (first group) | |
| dv/formal-rr-arbiter | | formal_verification, sva, assertion_coverage |
| dv/coverage-tick-timer | | code_coverage |
| dv/cocotb-crc | python_verification (first group) | directed_testing |

`rtl/apb-gpio` is the one case W2-L1 read that runs again, because
control_logic_design's document changed; the plan says that its trials also
join apb and rtl_design. `dv/cocotb-crc`'s trials were planned by W2-L1 and
never ran; this batch's plan takes them over and says so.

**Counts and arms.** As W2-L1: eight trials with knowledge documents and one
without on every case, fixed in the committed plan before trial 1. The arm
without documents counts toward no level. With thirteen cases that is 117
slots.

**Where it runs.** In the live evaluation's CI job, as the seat account,
from one commit, with one tool set. No trial of this batch runs on the
owner's machine (fact 7). security, eda-tooling and ai-engineer asked for
this; verification-lead left it to security. Before trial 1, on `main`:

1. gates ET1, ET2, ET3 and ET4 of the record of 2026-11-22 are met, ET8's
   documents are merged, and ET7's statement holds (no fingerprint moved);
2. `eqy` is installed in the job and runs as the seat account with its
   probe, or the two equivalence cases are left out of the plan (fact 9);
3. for each case whose gates or held-out checks build or run a program from
   seat-written HDL outside the wrapped tools (`coverage.read` today, fact
   8): the build and the run are made as the seat account with a probe
   through that gate, or take the form of decision 3, item 3 of the record
   of 2026-11-22, or the case is left out of the plan. The plan lists, for
   every case, each tool its gates and checks run and which account runs
   it;
4. every case's reference answer is replayed through its gates and held-out
   checks in that job on the batch's commit, passing, with every mutant
   failing as in the test job. This is the check that a different tool set
   judges as the first one did (fact 6).

A case left out under items 2 or 3 is named in the plan with the reason, is
not run later as part of this batch, and is carried as owed evidence to
meeting 2. Gates ET5 and ET6 are the timer's and gate ET9 is the register
block flow's; none of the three is a condition of this batch, but item 3
applies ET9's concern to this batch's own cases.

Residual risk, as security states it. With all of the above: screen classes
nobody has found, parser faults in a tool, and files any account may read.
The council accepts that, since the seat account is the control it named. A
batch with any tool left as the runner behind the screen alone, in CI or on
the owner's machine, is not accepted by this council; it would be the
founder's to accept, and security advises against it.

**Merged before the plan is committed:** ip#443 and ip#446; ip#442, by
itself and last of the content changes, so that no trial of
`debug/root-cause-debounce` can join the old 7 of 8 group; fresh check
records for equivalence_checking, verification_planning and
control_logic_design; the test of decision 3, item 4; the text correction of
decision 6; and the builds of items 1 to 3.

**Frozen from trial 1 until the read:** every file in `harness.CODE`, the
tool definitions, the CLI pin, the batch's case files, the card and document
of every skill a batch case names (the pooled ones included), the gate code
the batch's checks run, and the job's tool set. The plan states the commit,
the fingerprints and the digests of that gate code, `src/nirmaan/vplan.py`
included, and a dispatch is made only when they match.

**Stops and the read.** A trial that ends on a plan limit, a screen refusal
or a tool denied as the seat account is a failed trial, committed, never
removed and never run again. No top-up, extension, replacement or second
read. The read is taken once, after every record has merged, and is meeting
2. For each pooled group it gives W2-L1's figure, the batch's own figure and
the pooled figure; the level is the one `capability/levels.json` computes.

**The whole-flow batch.** The two batches draw on the same plan limits and
are never interleaved: one records its last trial before the other
dispatches its first. Which runs first is left to the orchestrator session.
The pull requests of gates ET1 to ET4 move digests the whole-flow plan pins,
so that plan's amendment (gate ET6) merges before its slot 1 whichever batch
runs first.

Owners: verification-lead (the plan, the counts, the read); security (where
it runs, items 1 to 3); ai-engineer (the groups, the freeze, the
fingerprints); eda-tooling (the job's tools and item 4).

### 5. The orchestrator session's five interim answers

1. **A pull request that moves a pinned group digest may merge before the
   whole-flow batch's slot 1 if a plan amendment follows.** Confirmed,
   narrowed: the amendment merges before any dispatch; a change that would
   move a default fingerprint returns to the council (gate ET7); and a
   bypass found during a freeze stops dispatch, since no freeze keeps a
   known bypass in place (security).
2. **The root_cause_analysis card is corrected together with the new debug
   cases, just before the batch.** Confirmed, with the order of decision 4:
   ip#442 merges before the plan is committed.
3. **No live dispatch until gates ET1 to ET9 are met.** Confirmed in
   substance and restated: for the timer the record of 2026-11-22 governs;
   for this batch the conditions are those of decision 4, which do not
   include ET9 itself and add the rule for programs built from seat HDL.
4. **The batch is covered by the founder's approval of a wave 2 batch.**
   Overruled. That approval named one batch through the local CLI, and
   W2-L1 was it (fact 15). The re-measure batch, and running it in CI, is a
   new ask and goes to the founder now. The gates above will take time to
   meet. If the founder has not answered when every other gate is met, the
   form of gate RT2 of the pilot retrospective applies: the batch may start
   on the orchestrator session's answer under the founder's instruction,
   recorded as such and not as a founder decision. No seat proposed that
   last sentence; the chair adds it from the RT2 precedent, and it is
   recorded under dissent.
5. **The exit item on Practising skills is not met by editing cards; cases
   where a stage plans the skill, exceptions otherwise.** Confirmed, with
   the corrected reason of fact 11 and the wording of decision 2.

### 6. The plan check's section field, and the triage tool's history

**Section placement is not part of the planning contract today** (fact 13;
verification-lead owns the contract), and the gate is not changed before the
batch. verification-lead decides in the next verification wave whether it
should become part of it; if so, the gate change is a gate-semantics pull
request made with that wave's plan, so that verification_planning is
measured under the gate that judges it. Before trial 1 the expected
behaviour text of `dv/plan-tick-timer` is corrected to say only what the
gate judges. eda-tooling proposed making the change now, since the skill is
already stale and no committed plan would be refused; not adopted, because
the owner of the contract says the field is outside it and the batch should
measure the contract as documented.

**History off is a deliberate default that the regression card has outgrown**
(facts 11 and 12). It stays off for this batch. Turning it on is a recorded
follow-up that returns to the council, because it changes the default
fingerprint, would let one trial's history reach the next unless each trial
has its own store, and must name the control that keeps one project's
records apart from another's (security).

Owners: verification-lead (the contract and the case text); eda-tooling,
with ai-engineer and security, for history.

### 7. Item 11: placeholders, and the processor models unit

Item 11 speaks of practices. A placeholder with no skill of its own is not
one, so the coinciding placeholders of fact 16 do not breach it, and the
item is met for the wave. `verification.processor.models` is not activated
now and reference_modelling does not move: the move changes role ids, golden
plans and holders and moves no level. It is an open item for the processor
wave. design-architect noted that activating it would thin the testing unit
and held that only weakly.

Owner: design-architect.

### 8. The remaining exit items

1. waveform_debug has no knowledge document because no source was found
   that an agent may read in full. systemverilog is Practised by trials with
   no knowledge document; the language standard is a source the founder
   would have to obtain. Both are named exceptions, labelled so wherever
   they are counted. security_verification leaves this wave for the Security
   wave.
2. python_verification: its trials are in this batch (decision 4), in CI
   only, as before.
3. An example for Debug in CI is not required for the exit. Any statement
   about examples says two, simulation and formal.
4. The trial without documents on `debug/root-cause-uart-tx` keeps its
   "model" label, as does the failed trial with documents on the same case.
   The seat's inputs held a testbench that follows the convention, and a
   label is not changed after the outcome is seen. Both are answered in the
   curriculum list with a written reason that cites ip#442; a card change is
   not written as a note (fact 17).
5. The curriculum answers for all eleven failures are listed in the pull
   request of meeting 2's addendum, each path existing on `main` by then.

Owners: verification-lead (items 2, 4, 5); qa-evidence (the labels and the
list); product-lead (items 1 and 3).

## Positions not adopted, and dissent

- eda-tooling: trials run in CI form groups separate from W2-L1's unless
  the plan shows equal tool versions. Not adopted: the group key is the
  level rule's, and changing it restarts every group. Its concern is met in
  part by decision 4 (the replay of every reference answer, the batch's own
  figure beside the pooled one). Whether tool versions belong in the
  fingerprint is open for ai-engineer, for the meeting that reads this
  batch.
- eda-tooling: change the plan check now (decision 6). Recorded as dissent.
- qa-evidence: control_logic_design measured on `rtl/apb-gpio-reset` alone,
  so that no case already read runs again. Not adopted: that case's judge is
  the weaker of the two (fact 4). qa-evidence's wording for pooled groups is
  adopted otherwise, with that one exception written into it.
- ai-engineer, verification-lead and qa-evidence: the usage for the batch is
  not covered. Adopted. ai-engineer and qa-evidence said the founder
  decides; the chair's fallback to the form of gate RT2 goes beyond what
  they asked and is recorded here as their dissent.
- security: a new gate numbered in the ET series. Adopted in substance as
  gates W2C2 to W2C4 below; the ET record is not renumbered.
- design-architect: activate the processor models unit (weakly held;
  decision 7).

No seat dissented from seating no lead, from the three exceptions, from
refusing `rtl/apb-gpio-reset` as a second case, from keeping the batch off
the owner's machine, or from leaving history off for this batch.

## Gates

Each is met on `main` before trial 1 of the re-measure batch unless it says
otherwise.

| Gate | Condition | Owner seat |
|---|---|---|
| W2C1 | One committed plan: the cases of decision 4, eight trials with documents and one without per case, every pooled group named with its count and passes, the stop rules, the freeze list, the commit, fingerprints and gate-code digests, one read | verification-lead |
| W2C2 | No trial of the batch on the owner's machine; every trial in the live evaluation's job as the seat account; gates ET1 to ET4 met, ET8's documents merged, ET7's statement shown | security |
| W2C3 | `eqy` installed and run as the seat account with its probe, or the equivalence cases left out and named | security |
| W2C4 | Each case that builds or runs a program from seat HDL outside the wrapped tools has that build and run as the seat account with a probe, or the fallback form, or is left out and named; the plan's table of tools and accounts per case | security |
| W2C5 | Every batch case's reference answer replayed in the job on the batch's commit: passes, and every mutant fails | eda-tooling |
| W2C6 | Merged before the plan: ip#443, ip#446, then ip#442 by itself; fresh check records for the three changed documents; the `use sat` test for `dv/equiv-updown`; the text correction of `dv/plan-tick-timer` | verification-lead |
| W2C7 | The freeze of decision 4 from trial 1 to the read; a dispatch only on the plan's stated values | ai-engineer |
| W2C8 | The batch starts only on the founder's answer on usage, or on the orchestrator session's answer in the form of gate RT2 if the founder has not answered when gates W2C1 to W2C7 are met | verification-lead |
| W2C9 | The two batches are never interleaved | ai-engineer |
| W2C10 | Before meeting 2: the closed list of three exceptions and its test; the public wording of decision 2 | verification-lead |
| W2C11 | At the read: for each pooled group, W2-L1's figure, the batch's own and the pooled one, with each batch's commit and environment; the eleven curriculum answers listed | qa-evidence |

## Open

For the founder:

1. This ruling, to confirm or overrule.
2. Usage for the re-measure batch, run in CI (decision 5, item 4; gate
   W2C8).
3. A copy of the language standard for a systemverilog knowledge document,
   if wanted (decision 8).

For later meetings:

4. Meeting 2: the read and the exit verdict, as an addendum here.
5. ai-engineer: whether EDA tool versions belong in the harness fingerprint.
6. eda-tooling, ai-engineer, security: history for the triage binding and a
   bound `regression.run` (decisions 2 and 6).
7. verification-lead: section placement in the planning contract; second
   cases for constrained_random, reference_modelling and model_checking.
8. design-architect: second cases for the Design skills, how
   `rtl/apb-gpio-reset`'s trials would count, and the processor models unit.

## Addendum (2026-11-23): running the batch's trials in parallel

The committed plan of the re-measure batch
(`evals/plans/2026-11-23-w2-remeasure.md`) runs one trial at a time. The
founder, in session, 2026-11-23: approved running the wave 2 re-measure
batch's trials in parallel to save time. The direction is the founder's.
This addendum rules on how the batch may run several trials at once, and on
what must be true before it does.

Ruling, in short:

- **Width three, inside a window of three consecutive slots** (decision P1).
  No slot is dispatched while a slot three or more places before it is
  unfinished, so one event can fail at most one counted trial of any group.
- **After the first plan or usage limit the batch runs one at a time to its
  end** (decision P1). That bounds what a limit can cost the evidence
  through parallel running to two more failed trials than the plan as
  committed, once. Any other event that ends running trials can still end
  up to three (decision P4, item 8).
- **The workflow gets an opt-in input** (decision P2). With it, a dispatch
  of a case that is neither a whole-flow nor a firmware case gets a
  concurrency group of its own, so no run is queued behind another and
  GitHub never cancels one. Without it every dispatch behaves as today. The
  whole-flow timer stays one at a time.
- **One slot, one run, bound before the next dispatch; records in slot
  order** (decision P3).
- **A stop closes dispatch and cancels no running trial** (decision P4).
  Trials already running end as they end and are committed. Nothing is run
  again.
- **The replays of gate W2C5 are the first use of the mechanism** (decision
  P5).
- **The workflow change merges only after the timer case's last planned
  trial is recorded** (decision P6).
- **The plan is amended before trial 1** (decision P7).

It changes no code, case, eval record, level, fingerprint or digest: the
changes it orders are made by their own pull requests. It changes no count,
case, arm or slot of the batch, and not the one read. It lifts no refusal
and changes no gate's condition: a failed trial stays a failed trial,
nothing is run again, and conditions are added before trial 1. One thing
that kept a gate changes, by the founder's direction: the workflow's single
group kept one trial at a time and kept the two batches apart (gate W2C9),
and for this batch the dispatcher's rules keep the width and that gate
instead (decision P2, item 9; decision P3). No trial ran and no workflow
was dispatched for the meeting.

### Who decided what

- The founder decided that the batch's trials run in parallel. The council
  decided every item below, and the founder can overrule any of it.
- Not decided here and still the founder's: the usage for the batch (gate
  W2C8 stands as written). This addendum approves no usage.
- One cost of the direction is stated for the founder under "Open": what a
  limit can cost at width three (decision P1).

Five seats gave round 1 positions, each as a read-only process of its own
that saw no other answer to the brief: ai-engineer, verification-lead,
security, qa-evidence and eda-tooling; the chair decided. The seats read
ip-nirmaan `main` at ede43ba1 and a copy of the private tooling that
dispatches the batch. The seats had no shell; nothing was run. The chair
rechecked the facts below at ede43ba1 and recomputed fact PF6 from section
12 of the plan.

### Facts checked

PF1 to PF10 number this addendum's facts; "fact" with a bare number still
means the list above.

- PF1. The workflow has one concurrency group for every dispatch, replays
  included: `group: live-eval`, `cancel-in-progress: false`
  (`.github/workflows/live-eval.yml:81-83`). A group holds one running and
  one pending run, and a newer pending run cancels the older one (GitHub's
  documented behaviour; both plans state it:
  `evals/plans/2026-11-23-w2-remeasure.md:103-105`,
  `evals/plans/2026-11-22-g3-whole-flow.md:44-45`).
- PF2. Each job runs on a hosted runner of its own, and every artifact name
  carries the run's id (`live-eval.yml:88`, `:201`, `:315`, `:206`). Two
  runs share no checkout, no seat account and no file. They share the one
  secret of the `live-eval` environment, so the one plan (inference:
  nothing else in the workflow couples two runs; security, eda-tooling).
- PF3. The workflow file is in no fingerprint: `harness.CODE`, `LOOP_CODE`
  and `FLOW_CODE` name only files under `src/`
  (`src/nirmaan/runtime/harness.py:257-292`). It is in the group "Workflow,
  tool set and CLI pin", which both plans pin at the same digest
  (`evals/plans/2026-11-23-w2-remeasure.md:304`,
  `evals/plans/2026-11-22-g3-whole-flow.md:531`). Any edit to it moves that
  digest in both plans and no fingerprint (ai-engineer, eda-tooling).
- PF4. The whole-flow plan marks its gate WF9 met for the timer citing the
  concurrency block by line (`evals/plans/2026-11-22-g3-whole-flow.md:816`,
  citing `live-eval.yml:81-82`), and freezes the workflow group from the
  timer's slot 1 until its last trial is recorded (its lines 554-557)
  (qa-evidence, security, verification-lead).
- PF5. Decision 11 of `council/records/2026-11-14-pilot-retrospective.md`
  kept an interrupted trial a failed trial, and refused a replacement,
  because "the runner's stop rule already limits the loss to one trial".
  With several trials running at once on one plan, a limit that ends one
  can end every trial then running (inference; no seat knows a way to read
  the plan's remaining allowance from a script, so no rule may rest on
  one). At width W that reason no longer holds: one event can fail up to W
  trials (qa-evidence, ai-engineer).
- PF6. Section 12 of the plan, recomputed by the chair. Two arm E slots
  whose cases name a skill in common are never fewer than four slots apart
  (slots 12 and 16, 73 and 77, 86 and 90 are four apart). Two arm E slots
  of one case are never fewer than eleven apart. So any three consecutive
  slots, and any four, hold at most one arm E trial of any group; five do
  not (slots 12 to 16). The brief said adjacent slots are always different
  cases; four seats corrected it: slots 28 and 29 are both `rtl/apb-gpio`,
  arm E and then arm N. Arm N counts toward no level.
- PF7. An 8-trial group needs 7 passes to count as Practised
  (`evals/plans/2026-11-23-w2-remeasure.md:126-127`), so one failed trial is
  the whole margin of a single-case group (ai-engineer, verification-lead).
- PF8. No test asserts this workflow's concurrency block. The tests of that
  kind pin other workflows (`tests/test_ci.py:64`,
  `tests/test_loop_cloud.py:542`) (four seats).
- PF9. The workflow sets no run name, and a record's manifest carries the
  commit and the times but no run id and no slot
  (`src/nirmaan/evals/records.py:270-277`). So which run is which slot is
  known only to whatever dispatched it, and then to the record pull request
  (qa-evidence). The levels count records by path
  (`src/nirmaan/evals/levels.py:248`), so the order runs finish in changes
  no figure (inference, qa-evidence).
- PF10. `firmware/axi4-lite-driver` runs live seat C under gate SC7
  (`live-eval.yml:38-42`). No case of the batch is a `flow/` or `firmware/`
  case (`evals/plans/2026-11-23-w2-remeasure.md:38-50`) (security).

### Decisions

#### P1. Width three, a window of three slots, and one at a time after a limit

1. At most three trials of the batch run at once. The number is fixed in
   the plan amendment before trial 1 and is never raised during the batch.
2. The window. A slot is dispatched only when every slot three or more
   places before it has finished, its counting re-judge included. So the
   slots in flight always lie within three consecutive slot numbers, and by
   fact PF6 one event can fail at most one arm E trial of any group. This is
   what the plan's order was designed to keep (its section 3), restated for
   several trials at once. A committed test reads section 12 and the stated
   width and fails if any window of that width holds two arm E slots whose
   cases name a skill in common.
3. After the first trial of the batch that ends on a plan or usage limit,
   the width is one from then until the batch's last slot. It is a rule of
   the plan, applied mechanically, never a choice made during the batch.
   With it, parallel running can cost the batch at most two failed trials
   more than the plan as committed would have lost to that same limit, once,
   each in a different group.
4. No rule may rest on reading the plan's remaining allowance (fact PF5).
5. The width is in no fingerprint and no group key. Putting it there would
   split every group pooled with W2-L1 (ai-engineer).

Why three. ai-engineer recommended three and would accept four;
verification-lead set four as the most the order allows; eda-tooling asked
for no more than three; security asked for a small number; qa-evidence took
no view on the number. Three is inside every bound a seat gave, and it
leaves one slot of margin under the window that fact PF6 allows.

Why a rolling window and not aligned waves. ai-engineer asked for waves
(slots 1 to 3, then 4 to 6, each wave whole before the next). The window is
verification-lead's and qa-evidence's form. It keeps the property ai-engineer
wanted from waves, and each dispatch still gets its own check (decision P3).
Recorded under dissent.

Owners: verification-lead (the number, the window and its test);
ai-engineer (item 3 and item 5).

#### P2. The workflow: an opt-in input and a group per run

1. `.github/workflows/live-eval.yml` gets one new input, `parallel`, a
   boolean whose default is false, and this concurrency block:

   ```
   concurrency:
     group: ${{ inputs.parallel && !startsWith(inputs.case, 'flow/') && !startsWith(inputs.case, 'firmware/') && format('live-eval-run-{0}', github.run_id) || 'live-eval' }}
     cancel-in-progress: false
   ```

   With the input false, and for every `flow/` and `firmware/` case
   whatever the input says, the group is `live-eval`, as today. Otherwise
   the run is alone in a group of its own: it is never queued behind another
   run and no run can cancel it. (Amended 2026-11-23 by the seventh addendum to
   `council/records/2026-11-17-g3-whole-flow-cases.md`, decision T3,
   item 1: the block gains a first clause that puts a dispatch of
   `flow/axil-timer` with the input in one of two groups by its arm; every
   other `flow/` case and every `firmware/` case stay in `live-eval`, and
   the cases of this batch keep the group per run. The block above is left
   as this addendum ruled it.)
2. The `replay` job and the `live-eval` job each get a guard as their
   first step, which fails the job when `parallel` is true and the case is
   a `flow/` or `firmware/` case. In the `live-eval` job that is before any
   step that reads the secret; the `replay` job reads none. (Amended
   2026-11-23 by the seventh addendum to
   `council/records/2026-11-17-g3-whole-flow-cases.md`, decision T3,
   items 3 and 4: the guard refuses a `firmware/` case and every `flow/`
   case other than `flow/axil-timer`, and a second guard refuses any
   dispatch whose case is not written in its exact form.)
3. `inputs.parallel` appears in the concurrency group and in those two
   guard steps and nowhere else: not in `env:`, not in a `run:` line, so it
   cannot reach a trial or a record (eda-tooling).
4. No new permission, no new use of the secret, no query of other runs from
   inside a job, and the artifact download stays on the same run. The
   environment and its main-only rule are unchanged (security).
5. Only this batch's 13 cases, in its slots and its replays of gate W2C5,
   are dispatched with `parallel` true. Any other use needs a council
   ruling. The whole-flow timer and the register block are never dispatched
   with it. (Amended 2026-11-23 by the seventh addendum to
   `council/records/2026-11-17-g3-whole-flow-cases.md`, decision T3,
   item 7: the timer's slots, its second measured run, the replay of gate
   ET5's record and a shake-out are dispatched with it. It read: "The
   whole-flow timer and the register block are never dispatched with it."
   The register block is still never dispatched with it.)
6. It changes no file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE` and no
   tool definition, so no fingerprint moves (fact PF3). It moves the digest
   of the group "Workflow, tool set and CLI pin" in both plans.
7. Tests, written failing first, merged with the change: the exact
   concurrency block; the input's type and default; that a `flow/` and a
   `firmware/` case resolve to `live-eval` whatever the input; the guard as
   the first step of both jobs, before the first step that reads the secret
   in the `live-eval` job; that
   `inputs.parallel` appears only where item 3 says; and that the secret
   appears in exactly the steps it appears in today.
8. `docs/LIVE_EVAL_EVIDENCE.md` ("One dispatch runs at a time") is corrected
   in the same pull request.
9. With groups per run GitHub no longer keeps the two batches apart or
   holds the width: gate W2C9 and the width rest on whatever dispatches the
   batch (decision P3, items 4 and 5). The plan amendment says so
   (eda-tooling).

Why a group per run and not numbered lanes. eda-tooling and ai-engineer
asked for a `lane` input with one group per lane, so that GitHub itself
holds the width. Under lanes a third dispatch to a busy lane cancels the
queued one. security would not accept any mechanism under which GitHub
cancels a queued run; qa-evidence and verification-lead chose the group per
run as well. The council takes the form in which nothing can be cancelled
and puts the width on the dispatcher, under the conditions of decision P3.
Recorded under dissent.

Owners: security (items 1 to 5); eda-tooling (items 6 to 9 and the build).

#### P3. Order, and which run is which slot

1. Slots are first dispatched in strictly increasing slot order, arm N
   where the plan puts it. Nothing is reordered by a result.
2. A slot is marked attempted before its own dispatch, as today. The
   dispatch check of the plan's section 7 is made before every dispatch,
   one check at a time, and the commit each run reports is checked as today.
3. One slot, one run. The run's id is taken from the response to the
   dispatch and written beside the slot before the next dispatch is made.
   A run is never identified by the time it was created. If the id cannot
   be bound, dispatch stops and a person binds it; the run is not cancelled.
4. The width is counted on the dispatcher's own bound runs. One dispatcher
   process at a time.
5. A run of the workflow that the dispatcher did not start, queued or
   running, stops new dispatches until it has ended. This is what now keeps
   the two batches apart (gate W2C9) and keeps any other dispatch out of the
   batch's run window.
6. Records reach `main` in slot order, none held out, failed ones included,
   whatever order the runs finish in. A slot's record waits for every
   earlier slot's.
7. Two trials of one case may run at the same time; the window makes that
   possible only for slots 28 and 29 (fact PF6), one of which is arm N.

Owners: qa-evidence (items 3 and 6); verification-lead (items 1, 2 and 7);
security (items 4 and 5).

#### P4. Stops

1. Any stop in any running trial closes dispatch at once: a plan or usage
   limit, an interrupted trial, a job-level stop, a record that is not the
   trial asked for, a re-judge that did not finish or did not hold, a
   changed tool set, a run the dispatcher did not start, a run whose id
   could not be bound.
2. Nothing in flight is cancelled: cancelling a running trial makes a
   failed trial. The one cancel that remains is the
   plan's own (section 7): a run whose commit fails the dispatch check is
   cancelled before its trial, on the dispatcher's own bound run, and only
   while its trial step has not started.
3. Every trial already dispatched ends as it ends, is classified by itself
   and is committed as it is (decision 4 above; decision 11 of the pilot
   retrospective). Nothing is run again and nothing is replaced.
4. A job-level stop that ran no trial is dispatched again, as the plan
   already says, alone and before any later slot that has not been
   dispatched. The read names every slot dispatched after a later one.
5. After a limit, dispatch resumes only when the limit has reset and every
   trial that was in flight has been classified, and then at width one
   (decision P1, item 3). After a stop that waits for a person today, it
   waits for a person as today, once nothing is in flight.
6. A changed tool set seen in one run: the trials already running stay
   trials, so up to three trials can have run on it. The plan's section 5
   says "the trial that ran"; the amendment says "every trial already
   dispatched", and the read names each.
7. Decision 11's reason, that a stop loses one trial, does not hold for
   this batch (fact PF5). The rule it supported stands: a failed trial is
   never replaced. Parallel running can only lower a pass count, so no
   level becomes easier to reach (qa-evidence).
8. The rule of one at a time bounds limits only. An event of another kind
   that ends running trials, such as an outage or a replaced secret, can
   end up to three at once; each is a failed trial, committed and never run
   again, and the read names the event and its slots. A stop that ends no
   trial (a re-judge that did not hold, a changed tool set, a record
   mismatch) fails nothing in flight.

Owners: verification-lead (the rules); ai-engineer (item 5's width);
eda-tooling (item 6).

#### P5. The replays of gate W2C5

The 13 replays may run in parallel, and they are the first use of the
mechanism: they use no model, no token and no environment, so a fault in
the routing, in binding a run to its row or in keeping each run's artifacts
apart costs no trial. They are dispatched with `parallel` true, after the
workflow change and the plan amendment have merged, on the amended values,
with three in flight at least once. Each is judged as the plan's section 11
says today. All 13 pass before slot 1, and the plan's dated addition names
each run. (Noted 2026-11-23: by the seventh addendum to
`council/records/2026-11-17-g3-whole-flow-cases.md`, decision T3, items 10
and 11, the input is used first by the timer; these replays are its first
use for this batch's cases, and they are still dispatched only after the
timer's last planned trial is recorded.)

Owner: eda-tooling.

#### P6. When the workflow change merges

After the timer case's last planned trial is recorded, and before the
replays of gate W2C5. All five seats said so. A merge before or during the
timer's slots would move a digest the whole-flow plan pins and change the
lines its gate WF9 cites as met (fact PF4). Nothing of this batch can be
dispatched before that point in any case (the plan's section 10; gate W2C9),
so the order costs the batch nothing it could have used.

(Amended 2026-11-23 by the seventh addendum to
`council/records/2026-11-17-g3-whole-flow-cases.md`, decision T3, items 9
and 11. The first sentence read: "After the timer case's last planned trial
is recorded, and before the replays of gate W2C5." It now reads: the
workflow change, extended as that addendum says, merges before the
whole-flow plan's addition of its gate WF32 is computed and before the
timer's second measured run; if it has not merged by then, only after the
timer case's last planned trial is recorded, and never in between. The
whole-flow plan restates the moved digest and gate WF9's evidence in that
addition, before the timer's slot 1. Gate W2C9 is not changed: nothing of
this batch, a replay included, is dispatched before the timer case's last
planned trial is recorded.)

The whole-flow plan still pins the old digest for the register block. Its
dated addition before slot 21 restates the moved digest with the pull
request that moved it, and restates the evidence of gate WF9 against the
workflow as it then is: a whole-flow case is always in the group
`live-eval`. (Amended 2026-11-23 by the same addendum: the register block
is always in the group `live-eval`; a timer dispatch with the input is in
one of the timer's two groups.)

From slot 1 of this batch the workflow file is frozen with the rest (gate
W2C7).

Owners: eda-tooling (the order of merging); ai-engineer (gate W2C9 and the
whole-flow plan's addition).

#### P7. The plan amendment, and the read

One plan amendment pull request, merged before the replays and so before
trial 1, after the workflow change. It changes no count, case, arm, slot or
value other than the one moved digest. It states:

1. the width, the window rule and the rule of one at a time after the first
   limit (decision P1), and that the number is never raised;
2. the input and the concurrency block word for word, which cases may be
   dispatched with it, and that the width and gate W2C9 rest on the
   dispatcher (decision P2);
3. the moved digest of "Workflow, tool set and CLI pin", the commit it was
   computed on and the pull request that moved it;
4. section 3 rewritten: the dispatch sentences
   (`evals/plans/2026-11-23-w2-remeasure.md:102-105`) and the sentence that
   a stop "does not land on one case" (`:88`), which becomes what fact PF6
   shows; the run binding of decision P3;
5. section 5: "every trial already dispatched" (`:200-202`);
6. section 7: the check before every dispatch, one at a time;
7. section 8: the stop rules of decision P4, the limit stop (`:347-348`)
   included;
8. section 10: "no slot is dispatched while any run of the workflow is
   queued or running" (`:404`) becomes "while any run that is not this
   batch's own";
9. section 11: the replays of decision P5;
10. that runs share one secret and one plan and nothing else (fact PF2);
11. that decision 11's reason does not hold here and its rule does
    (decision P4, item 7).

After the amendment no text says "one at a time" of this batch, except of
the width after a limit.

The read (gate W2C11) adds: the width; that trials overlapped; for each
slot its run and the slots whose runs overlapped it; every stop event with
the slots then in flight and their labels; each group's failed trials by
label; every slot dispatched after a later one; the point from which the
batch ran one at a time; any run cancelled before its trial under decision
P4, item 2; and that no running trial was cancelled and nothing was held
out or run again. Never said: that running trials at once had no effect on a result,
or that this batch and W2-L1 ran under the same dispatch conditions. W2-L1
ran one trial at a time.

Owners: verification-lead (the amendment); qa-evidence (the read and the
wording).

### Positions not adopted, and dissent

- ai-engineer: aligned waves, each whole before the next, one check per
  wave, no pull request merged during a wave. Not adopted (decision P1).
- eda-tooling and ai-engineer: numbered lanes, so that GitHub holds the
  width and the width sits in the pinned workflow digest. Not adopted
  (decision P2). eda-tooling's fail-closed default, its rule on where the
  input may appear and its tests are adopted.
- verification-lead: a width of four allowed. Not adopted; three is inside
  its bound.
- security: a tag in the run's name as a second way to identify a run. Not
  adopted: it needs another input, and the dispatch response is enough or
  dispatch stops (decision P3, item 3).
- The chair considered stepping the width down by one at each limit. No
  seat proposed it, so it is not adopted; ai-engineer's rule is.

No seat dissented from: the opt-in default; keeping whole-flow and firmware
cases in the one group; cancelling nothing on a stop; committing every
trial and running none again; the replays as the first use; or merging the
workflow change after the timer's last trial. (Noted 2026-11-23: this is
what the seats held at this meeting. The seventh addendum to
`council/records/2026-11-17-g3-whole-flow-cases.md`, a later meeting on the
founder's direction for the timer, amends the second and the last of these
for the timer; see the notes in decisions P2 and P6.)

### Gates added

Each is met on `main` before trial 1 of the batch unless it says otherwise.
The conditions of gates W2C1 to W2C11 stand as written; what keeps gate
W2C9 for this batch is decision P3, item 5.

| Gate | Condition | Owner seat |
|---|---|---|
| W2C12 | The plan amendment of decision P7 merged: width three, the window, one at a time after the first limit, the rewritten sections, the moved digest; the committed test of the window against section 12 | verification-lead |
| W2C13 | The workflow change of decision P2, with its tests and the corrected document, and no fingerprint moved | security |
| W2C14 | That change, extended as the seventh addendum to `council/records/2026-11-17-g3-whole-flow-cases.md` says, merges before the whole-flow plan's addition of gate WF32 is computed and before the timer's second measured run, or else only after the timer case's last planned trial is recorded, never in between; the whole-flow plan restates the digest and gate WF9's evidence before the timer's slot 1, and again for the register block before its slot 21. (Amended 2026-11-23 by that addendum, decision T3, item 9. It read: "That change merges only after the timer case's last planned trial is recorded; before the register block's slot 21 the whole-flow plan restates the digest and gate WF9's evidence".) | eda-tooling |
| W2C15 | One slot, one run, bound from the dispatch response before the next dispatch; a run the dispatcher did not start stops dispatch; records in slot order | qa-evidence |
| W2C16 | A stop closes dispatch and cancels no running trial; every trial already dispatched is committed; nothing is run again; width one after the first limit | ai-engineer |
| W2C17 | The 13 replays of gate W2C5 dispatched with the input, three in flight at least once, all passing, each named in the plan's dated addition | eda-tooling |
| W2C18 | At the read: what decision P7 asks the read to add, and nothing it forbids | qa-evidence |

### Build specification, for the build lane

Nothing here is built by this addendum. In order:

1. Before the timer's last trial is recorded: nothing merges. The workflow
   pull request may be prepared and kept as a draft.
2. One pull request, control plane: the workflow change of decision P2,
   items 1 to 4, the tests of item 7 and the document of item 8. It states
   that no fingerprint moves and names the moved group digest.
3. One pull request: the plan amendment of decision P7, with the test of
   decision P1, item 2.
4. The dispatcher (private tooling, not in this repository) carries
   decisions P1, P3 and P4, with tests of its own for the window, the run
   binding, the stops and the slot order of records.
5. The replays of decision P5, then the plan's dated addition, then slot 1
   under gate W2C8.
6. Before the register block's slot 21: the whole-flow plan's dated
   addition of decision P6.

### Open, for the founder

1. This addendum, to confirm or overrule.
2. What the direction can cost, stated once: a plan or usage limit reached
   while three trials run can fail all three, where the plan as committed
   would have lost one. Each is a failed trial of its group and is never run
   again, and for a single-case group of eight one failed trial is the
   whole margin for Practised (fact PF7). The council bounds this to one
   such event from a limit (decision P1, item 3; decision P4, item 8). If
   the founder wants the width kept
   after a limit, or no parallel running, that is the founder's to say
   before trial 1.

## Note (2026-11-23): read with the G3 record's seventh addendum

The seventh addendum to `council/records/2026-11-17-g3-whole-flow-cases.md`
rules on running the whole-flow timer's slots two at a time, by the
founder's direction. For the addendum above it amends decision P2, items 1,
2 and 5 (the timer, by name, may be dispatched with the input, in two
groups by arm; a second guard on the case's form), decision P6 and gate
W2C14 (the workflow change merges before the timer's second measured run),
and notes decision P5. Each is noted in place. Gate W2C9 stands exactly as
written, and so do the width, the window, the stops and every other gate of
this batch.

## Addendum (2026-11-25): meeting 2, the read of the re-measure batch and the exit verdict

This addendum is meeting 2 of the wave 2 close. It has two parts. Part 1
holds the rulings that do not depend on how the re-measure batch came out.
The seats gave them, and the chair decided them, while the batch was still
running, and Part 1 was committed and pushed before the batch's last record
merged, so that the rule of the verdict was fixed before anyone read the
outcome. Part 2 is the one read of the batch (gates W2C11 and W2C18) and
the exit verdict.

A key is an agent review. Nothing here is a person's approval, a release, a
warranty of capability, or a claim that a design is ready to be made in
silicon. A level is a measured figure of an agent seat on named eval cases
under a stated input contract. The verdict is a statement about measured
eval trials, decided by the council under the founder's delegation, and the
founder can overrule it.

### Who decided what

- The council decided every item of Part 1. The founder was away and can
  overrule any of it.
- The rules of the read were fixed before slot 1 by meeting 1, its
  addendum on parallel trials and the committed plan
  (`evals/plans/2026-11-23-w2-remeasure.md`). Part 1 adds the rule of the
  verdict and what the read must and must not say. Nothing was chosen at
  the read.
- Reserved for the founder and not decided here: the usage for any later
  batch (decision M4), a source for systemverilog (meeting 1, decision 8),
  names, and any public wording of the verdict.
- This addendum loosens no gate and lifts no refusal. It changes no code,
  case, eval record, level, card, document, fingerprint or digest. The
  changes it orders are made by their own pull requests, each after the
  batch's last record is on `main`.

### Part 1: fixed before the read

Eighteen seats gave round 1 positions, each as a read-only process of its
own that saw no other position. Every seat was told not to open the
batch's records or the current `capability/levels.json`, and to state no
figure of the batch. The seats read ip-nirmaan `main` at 7c4587f2. Eleven
seats gave a view on one item or more; tax-accounts gave none, and
market-research, finance-licensing, legal-counsel, legal-compliance,
partnerships and site-engineer spoke only to wording, usage or public
pages. No trial ran and no workflow was dispatched for the meeting.

#### Facts checked

MF1 to MF9 number this addendum's facts. qa-evidence checked MF1 to MF4,
MF6 and MF8 against the code and the committed records; the seat named
checked the others.

- MF1. Before slot 1 (`capability/levels.json` at f4292ff7): 16 Practised,
  29 at Knowledge, none Proven. Of the batch's skills,
  equivalence_checking, verification_planning, failure_triage,
  root_cause_analysis, control_logic_design, functional_coverage and
  python_verification had no counted group; code_coverage,
  formal_verification, sva, assertion_coverage, directed_testing, apb and
  rtl_design were Practised and are pooled by the batch.
- MF2. The pull requests of gate W2C6 are merged, and the closed list of
  three exceptions and its test are on `main`
  (`docs/EVAL_SKILLS_MUST_FAIL.md`, section 6; ip#450). brand-content
  searched `README.md`, `site/` and `docs/LANDING_PAGE_BRIEF.md`: no page
  names a level, and the three skills are described nowhere as a
  Practising capability. Gate W2C10 is met.
- MF3. `scripts/failure_curriculum.py`, given the record keys of W2-L1
  dated 2026-11-18 and 2026-11-19, lists thirteen model-labelled failures
  with no answer: the eleven of W2-L1 (nine with documents, two without)
  and two calibration records of the harness comparison on `rtl/apb-gpio`
  with the same fault as W2-L1's two failures on that case. Given a path
  where it expects a key, the script reports no failure and exits 0
  (verification-lead, qa-evidence).
- MF4. How a seat is told to cite a run. The system text of every work
  seat says: list in `tool_runs` only run IDs from the citation list
  (`src/nirmaan/runtime/harness.py:98`). The citation list shows each run
  only as a token, `[run:<id>]` (`src/nirmaan/runtime/prompt.py:44-53`;
  `src/veritriage/models/ai.py:114-116`). The answer's `tool_runs` entries
  are taken as written (`src/nirmaan/runtime/model.py:392`), and an entry
  that is not a recorded run is refused by rule P5
  (`src/nirmaan/runtime/base.py:364-373`,
  `src/nirmaan/work/policy.py:254-256`). The bare id is never shown alone.
  The harness itself adds every run it made before the answer to the
  result (`model.py:410`, `:420`), and `Prompt.resolve` already maps a
  token to its id (`prompt.py:83-84`) but is not used for `tool_runs`
  (ai-engineer). Only the failure_triage card asks for a cited session
  (`src/nirmaan/company/skills.py:513`).
- MF5. Each of those files is in `harness.CODE` or the harness settings
  (`harness.py:159`, `:279-292`), so a change to the system text, the
  prompt or the parsing moves the default fingerprint and makes every
  counted group of every skill stale. A card or document sentence moves
  one skill's digest only.
- MF6. A surviving mutant's run is dropped in the must-fail scorer: it is
  in the score's summary and in neither list of runs
  (`src/nirmaan/evals/scorers.py:259-260`), so the record's `judge_runs`
  (`src/nirmaan/evals/records.py:172-176`) cannot carry it. `scorers.py`
  is the pinned group "Held-out scorers" of both committed plans and is in
  no harness fingerprint. The level rule asks only whether `judge_runs` is
  empty (`src/nirmaan/evals/levels.py:342`), and the re-judge compares
  status only (`records.py:473-480`) (eda-tooling, ai-engineer).
- MF7. No committed test compares a whole-flow slot record with the
  plan's stage tables for the register block, and
  `tests/test_whole_flow.py` refuses any whole-flow record outside
  `evals/results/g3-timer/`, so that file changes before the record of
  slot 21 can merge in any case (eda-tooling).
- MF8. The check record of equivalence_checking passed with stale line
  citations noted, and the document's seat-facing text names the kind of
  error that case's held-out mutants make (ip#455).
- MF9. No committed record sets a number of Practised skills that a wave
  must reach. The build-out record sets a share for the pilot only
  (product-lead).

#### M1. The rule of the verdict

The verdict has three forms, and they mean this (product-lead):

- "Met": every exit item met, with no exception. Not available to this
  wave: meeting 1 already named exceptions (its decisions 2 and 8).
- "Met with named exceptions": the wave's work is closed and was measured
  once. It says nothing about how many skills are Practised. The next
  wave may start.
- "Not met": the measurement or an exit item is unsound. The next wave
  does not start on this wave's levels.

The verdict is "met with named exceptions" when all of these hold:

1. all 117 records are on `main` and were read once;
   `scripts/capability_levels.py --check` passes and the levels generator
   refuses no record; `scripts/failure_curriculum.py --strict` finds no
   failed trial of the batch without a label; no `causes.md` label of the
   batch changed after its record merged; and every record was made on the
   values the plan names;
2. every exit item of the wave is met or is an exception named by meeting
   1 or by this addendum;
3. every skill of the batch has the level the level rule computes,
   whatever it is, stated with its group; each skill of the batch that is
   not Practised after the read is carried as an open item with an owner
   seat.

It is "not met" only when item 1 fails, or a pooled or new group does not
count for a reason other than its pass count (trials without a clean
re-judge are the case the plan's section 8 leaves open; such a group gives
"not met" until the council rules on it), or an exit item is neither met
nor a named exception.

There is no floor on the number of Practised skills. Every seat that spoke
to it said so (verification-lead, qa-evidence, ai-engineer, eda-tooling,
design-architect, product-lead, dft-engineer, physical-design-engineer,
partnerships): no committed record gives a number (fact MF9), the level
rule already judges pass counts, and a number chosen while part of the
batch was merged could not be shown to be free of the outcome.

The verdict's sentence is never quoted alone: the computed levels and the
list of exceptions go with it.

Owner: verification-lead.

#### M2. What the read says, added to gates W2C11 and W2C18

The read also states:

1. the commit of the levels file it reads, and for each figure its group
   key (ai-engineer, qa-evidence);
2. for gates W2C2 to W2C4, in the plan's words and no wider: where every
   trial, replay and re-judge ran, which account ran the tools that read
   seat files, and that W2-L1's part of each pooled group ran on the
   owner's machine without the seat account (security);
3. that pooled groups mix versions of the EDA tools that W2-L1's records
   do not name, as a limit of the pooled figures
   (physical-design-engineer; meeting 1, fact 6);
4. beside the figure of equivalence_checking, fact MF8;
5. if control_logic_design is Practised: "one case, one control
   structure" (design-architect);
6. that round 1 of this meeting was held before the read.

Never said, beyond the plan's list: a rate "of judged trials" or any count
that leaves refused trials out; that a refused trial would have passed;
"harness defect" as a fact (the label is an inference); that the seat can
or cannot triage; that a card change caused a difference from W2-L1's
group; an expected level after a fix; that a skill is capable, strong or
ready; "sandboxed", "isolated" or "safe"; that the language standard was
read or used for systemverilog; "verified", "certified", "guaranteed" or
"production ready" of the wave.

Owner: qa-evidence.

#### M3. Trials refused on the form of a cited run

Some trials of the batch never reached review because the seat wrote a
run in `tool_runs` in the token form and rule P5 refused it (fact MF4).
The lane that ran the batch labelled each before its record merged, as the
plan's section 8 requires. The read states them so:

1. each is a failed trial of its group; no count leaves them out;
2. each is listed under "the trials no judge ran", with its label as
   written; no label is changed;
3. no curriculum line is owed for a label that is not "model";
4. the read lists every refusal of this form, for every group, from the
   committed `causes.md` files only;
5. the read gives the mechanism of fact MF4 in plain words, says that the
   link from it to each refusal is an inference, as the label does, says
   whether other trials of the same cases passed under the same contract,
   and calls each affected figure a figure of the seat under this input
   contract. No rate is given without that.

All five seats with a view agreed (verification-lead, qa-evidence,
ai-engineer, eda-tooling, product-lead).

Owner: verification-lead; qa-evidence for the wording.

#### M4. The fix for the cited run, and measuring again

1. First, after the batch's last record is on `main`: one sentence on the
   failure_triage card and in its document that the `tool_runs` field
   takes the bare run id. It moves that skill's digest only; the pull
   request shows that no other skill's digest moves. The document's stale
   line citation (`knowledge/verification/failure_triage.md:147`) is
   corrected in the same change.
2. Second, the harness resolves an entry of `tool_runs` that is one whole
   listed token, with or without its brackets, to its run id, and the
   system text states the form. Conditions (security): the unwrap is
   exact and is made before the filters for runs of other tasks and
   advisory runs; nothing partial, case-folded or nearest is matched; no
   tool name or label stands for a run; no id is taken from prose; an
   unknown entry is never dropped silently and still goes to rule P5,
   whose meaning does not change; and a test shows an unrecorded run
   refused in either form. This change moves the default fingerprint
   (fact MF5), so it never merges alone: it merges with the next planned
   change that restarts every group, it returns to the council first
   (gate ET7 of `council/records/2026-11-22-eda-tools-seat-account.md`),
   and its pull request states the old and the new fingerprint and every
   group it makes stale.
3. No sentence is added to another skill's card now. Every work seat reads
   the same system text, so every seat is exposed (fact MF4); only
   failure_triage's card asks for a cited session, and a sentence
   elsewhere would make a group stale with no recorded failure behind it.
4. failure_triage is never measured again inside this batch. It is
   measured again only under a new committed plan, in the next
   verification batch, as a new group, in both arms, and that plan says
   that the sentence of item 1 was written after these refusals were seen
   and is part of what is measured. The usage for that batch is a new ask
   to the founder (meeting 1, decision 5, item 4); nothing here approves
   it (finance-licensing).

ai-engineer added: if no change that restarts every group is planned by
the time the next verification batch's plan is written, it would bring
item 2 forward and accept the re-measure of every group. Not ruled now; it
returns with that plan.

Owners: verification-lead (items 1 and 4); ai-engineer, with security
(item 2).

#### M5. A note on testbenches and parameter values

A knowledge note is wanted: a testbench is built at every parameter value
the requirements name. Every seat that spoke agreed. It is written from
open sources that an agent can read in full, each with its access type and
licence check, summarised and cited and never copied; it holds no text,
signal name, requirement id or parameter value of the timer case; and it
is checked by a different session than the one that wrote it
(legal-compliance, `knowledge/README.md`).

Where it goes. The two trials that failed this way were whole-flow trials
in which the RTL stage's seat wrote the testbench, and the testbench rules
that seat reads are in `knowledge/design/rtl_design.md`
(design-architect). So the note goes there, as one line of that section,
because a note that does not reach the seat that failed does not answer
the failure. It makes rtl_design's counted group stale, and no other
group. It therefore merges after the register block's slot 40, so that
both whole-flow cases run on one document, and together with the committed
plan of the batch that measures rtl_design again. verification-lead may
put the same rule in `knowledge/verification/directed_testing.md` with the
next verification batch's plan; that is its choice as owner of that
document and is not required here.

Not adopted: verification-lead asked for the note in
`directed_testing.md` now, because it costs the smaller group. Recorded
under dissent. Also carried, from the same seat: the whole-flow testbench
is written by a stage that holds no verification skill (owner
design-architect, with verification-lead).

Owners: verification-lead's lane writes it; design-architect holds key 1
on it.

#### M6. A surviving mutant's run in the record

A surviving mutant's run is carried into `judge_runs`. The fix is in
`src/nirmaan/evals/scorers.py`, where the run is dropped, for both
must-fail scorers; the test, in `tests/test_nirmaan_eval_must_fail.py`,
fails first and shows the run in `judge_runs` with `succeeded: true`. It
moves the pinned group "Held-out scorers" of both plans and no
fingerprint. So it merges after this batch's last record, and then either
before the register block's slot 21, with the moved digest restated in
that case's dated addition, or after slot 40, never in between. No
committed record is rewritten; records made before it keep the gap, and
the verdict of each is still held by its re-judge. No level moves (fact
MF6).

Owner: eda-tooling; qa-evidence checks.

#### M7. The register block, before slot 21

eda-tooling's condition in the eighth addendum to
`council/records/2026-11-17-g3-whole-flow-cases.md` is confirmed. Before
slot 21:

1. the dispatcher refuses slots 21 to 40 when the whole-flow plan holds
   no stage tables for the register block, with no fall back to the
   timer's, and the showing of decision F3, item 5 of that record is made
   again on a register block record; firmware-engineer asked that it add
   one copy with the firmware stage's skill digest changed and one with
   the firmware stage not run after a completed RTL stage;
2. in `tests/test_whole_flow.py`, one pull request: the table test covers
   the register block's rows, and a new test checks every committed slot
   record against decision F3, item 3, with item 5's refused copies and
   one accepted stopped record as cases. It runs in the ordinary test job,
   with no secret and no dispatch. It controls what merges, not what is
   dispatched;
3. the register block's dated addition states, per arm, the firmware
   stage's skills and digest, the parameters its held-out checks use, and
   where the driver ran (firmware-engineer).

A checker under `scripts/` that the dispatcher calls is a follow-up, not a
condition. Item 2 as a condition is eda-tooling's and security's;
verification-lead and firmware-engineer held that a repository check is a
follow-up. The chair takes the condition: the file must change before the
record of slot 21 can merge in any case (fact MF7), and a gate that rests
on private tooling alone is a seat's statement and not a control.
Recorded under dissent.

Owners: eda-tooling (items 1 and 2); firmware-engineer reads item 3.

#### M8. The curriculum answers for W2-L1

Meeting 1, decision 8, item 5 asked for the eleven answers in the pull
request of this addendum. They are given there, one line per failure, in
the form `scripts/failure_curriculum.py` reads, with these rulings
(verification-lead, qa-evidence):

| Failures | Case | Answer |
|---|---|---|
| two, with documents | `dv/plan-irq-ctrl` | note: `knowledge/verification/verification_planning.md` (ip#439) |
| three, with documents | `dv/equiv-gray` | note: `knowledge/verification/equivalence_checking.md` (ip#431, ip#443, ip#453) |
| one, with documents | `dv/coverage-irq-ctrl` | must-fail: `evals/dv/coverage_tick_timer.json` (ip#436); that its mutant is of the same class as the survivor is an inference, and the line says so |
| two, with documents | `rtl/apb-gpio` | note: `knowledge/design/control_logic_design.md` (ip#439). `evals/rtl/apb_gpio_reset.json` is not given as the answer: it merged before these failures |
| one, with documents | `debug/root-cause-uart-tx` | no: a written reason that cites ip#442; a card change is not a note |
| one, without documents | `debug/root-cause-uart-tx` | no: the same reason, citing ip#442 (meeting 1, decision 8, item 4) |
| one, without documents | `dv/plan-irq-ctrl` | no: the arm without documents; the fault is answered by the note of the first row |

The two calibration records of fact MF3 are answered in the same list with
the note of the fourth row, since the script lists them with these keys
and they show the same fault. The script is run with record keys only
(fact MF3), and its output is quoted in the pull request.

Owner: verification-lead; qa-evidence checks the list.

#### M9. Open items of meeting 1

1. **EDA tool versions and the fingerprint** (meeting 1, open item 5).
   Ruled: tool versions do not enter the default fingerprint. It would
   make the fingerprint depend on the machine and restart every group, and
   a gate's verdict is held by the re-judge. Instead each trial records
   the versions of the tools it ran, in a field of the record outside
   every fingerprint, from the next verification batch on (owner
   eda-tooling; ai-engineer checks). For physical design a version line is
   not enough: before the first counted trial of a physical-design skill,
   the identity of the tool image and of the library and rule files is in
   the record and in that batch's fingerprint; decided with that wave's
   plan (owner ai-engineer, with eda-tooling and
   physical-design-engineer).
2. **The equivalence_checking text** (fact MF8). Reworded after the
   batch, in one change with the corrected line citations, so the group
   goes stale once; the read carries the caveat (decision M2, item 4).
   Owner verification-lead.
3. **Stale citations in a check record.** Stale line numbers alone do not
   fail a check record when the checker verified each sentence at the
   head and the record carries the current location. A sentence that
   could not be verified fails it. A machine check of cited lines is a
   follow-up (owner qa-evidence).
4. **`rtl/apb-gpio-reset`.** Ruled: its trials never enter any group's
   count, since it is one task with `rtl/apb-gpio` and would count one
   answer twice (meeting 1, fact 4). It stays a must-fail control and, if
   ever run, is reported beside `rtl/apb-gpio` (design-architect).
5. **Carried, not ruled:** history for the triage binding and a bound
   `regression.run` (the next verification batch's wave, with the next
   change that restarts every group; eda-tooling, ai-engineer, security);
   section placement in the planning contract and second cases for
   constrained_random, reference_modelling and model_checking (the next
   verification batch's plan; verification-lead); second cases for
   fsm_design, arbitration, pipeline_design and control_logic_design (the
   Design wave; design-architect); the processor models unit (the
   processor wave; design-architect, whose weak dissent of meeting 1 is
   not renewed).

#### M10. Practice leads, restated

Meeting 1, decision 1 asked verification-lead to restate the fact at each
wave close. The review's records still hold no wait per department: every
key-1 verdict names the team. For the team, the median key-1 wait since
meeting 1 was not above the other teams', and the long waits lay inside
session-limit pauses. The condition is not met; no lead is seated.

Owner: verification-lead.

#### Positions not adopted, and dissent (Part 1)

- verification-lead: the testbench note in `directed_testing.md` now
  (decision M5). Not adopted.
- verification-lead and firmware-engineer: the repository check for the
  register block as a follow-up (decision M7). Not adopted.
- verification-lead: the rule of the verdict merged before any seat reads
  the batch. Adopted in substance: Part 1 was committed and pushed before
  the batch's last record merged, and it merges with Part 2 in one pull
  request, since a pull request merged during the batch would have gone
  through the same review loop the batch's records were using.
- ai-engineer: the harness fix brought forward if no change that restarts
  every group is planned (decision M4). Not ruled.
- qa-evidence and verification-lead named `records.py` for decision M6;
  eda-tooling and ai-engineer showed the run is dropped in `scorers.py`.
  The chair takes the owners' file.

No seat dissented from the rule of the verdict, from having no floor,
from how the refused trials are stated, or from the order of the two
fixes.

#### Gates added

| Gate | Condition | Owner seat |
|---|---|---|
| W2C19 | The read states what decisions M2 and M3 ask and nothing they forbid | qa-evidence |
| W2C20 | After the batch's last record: the failure_triage sentence of decision M4, item 1, moving one digest; failure_triage measured again only under a new committed plan, on the founder's answer on usage | verification-lead |
| W2C21 | The harness change of decision M4, item 2 merges only with a planned change that restarts every group, after a council ruling, with security's conditions and their test | ai-engineer |
| W2C22 | The note of decision M5 in `knowledge/design/rtl_design.md`, after slot 40 and with the plan that measures rtl_design again | design-architect |
| W2C23 | The scorer change of decision M6, after this batch's last record and outside slots 21 to 40 | eda-tooling |
| W2C24 | Before slot 21: decision M7, items 1 to 3 | eda-tooling |
| W2C25 | From the next verification batch: each trial records the versions of the tools it ran (decision M9, item 1) | eda-tooling |

### Part 2: the read and the verdict

Part 1 above was committed (`b39f7f3d`) and pushed before the batch's last
record merged. This part was written after it.

#### What was read

Read once, on `main` at `188b66a9`, the merge of the records of slots 111
to 117 (ip#567). The record pull requests are ip#548 to ip#567, twenty of
them, in slot order.

- `scripts/capability_levels.py --check` reports that
  `capability/levels.json` matches the records, and the levels generator
  refuses no record (`refused_records` is empty). Each group's n, passes,
  trials no judge ran and level below are the ones that file holds at
  `188b66a9`, and each interval is `wilson()` of
  `src/nirmaan/evals/records.py` on that n and those passes. This batch's
  own share of a pooled group, the passes per case and the arm without
  documents are counted by script from the trial files of the committed
  records. Nothing was counted by hand, and the code that reads the
  records did not change between slot 1
  and this read: between `f4292ff7`, the commit slot 1 ran on, and
  `188b66a9`, `main` changed only under `evals/results/w2-remeasure/` and
  in `capability/levels.json`.
- All 117 records are on `main` under
  `evals/results/w2-remeasure/slot-NNN/`, failed ones included, one trial
  in each, and every trial re-judges the same (`rejudge.json` in each
  record).
- Every trial ran on the default harness with its attempts, one trial per
  dispatch, seat model `claude-opus-5-5`, Claude Code 2.1.325, purpose
  `evidence`: the 104 trials with documents on fingerprint
  `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`,
  the 13 without on
  `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39`.
  Each record's case digest, and each skill digest of a trial with
  documents, equals the plan's section 6. Recomputed at `188b66a9`, both
  default fingerprints equal the plan's section 6 (ai-engineer, gate
  W2C7).
- `scripts/failure_curriculum.py --strict`, given the 117 record keys
  (fact MF3), lists sixteen model-labelled failures and no failed trial
  without a label. Each of the 27 failed trials has a
  `causes.md` beside its record, and each of those files has one commit:
  no label changed after its record merged.
- W2-L1 was not read again. Its figures below are those of its one read,
  as the plan's section 4 states them.

#### Corrections to Part 1's facts, found at round 2

Part 1 stays as it was pushed. ai-engineer found these at round 2:

- Fact MF4 names `Prompt.resolve`. The method is `WorkPrompt.resolve`
  (`src/nirmaan/runtime/prompt.py:83-84`), and it matches a token with its
  brackets only. Every entry of this form in the batch was written without
  brackets, the case decision M4, item 2 already covers.
- Fact MF4 says the harness adds every run it made before the answer. At
  `model.py:420` it also adds the runs of the checks made after the
  answer; `model.py:410`, the escalation path, adds only those made
  before.
- Added to fact MF4: a bare id of a run made for another task is dropped
  with a remark and refuses nothing (`model.py:393-396`). Written as a
  token, the same entry is not a recorded run, passes that filter and
  goes to rule P5.
- "The bare id is never shown alone" is read from the code. No committed
  record holds a rendered prompt, only its hash, so no record shows it.
- Fact MF5 says each file fact MF4 names is in `harness.CODE` or the
  harness settings. Two are in neither: `src/nirmaan/work/policy.py`
  (rule P5) and `src/nirmaan/company/skills.py` (the card, which is in the
  skill digest). Its conclusion stands: the change of decision M4, item 2
  is in the system text and the parsing and moves the default
  fingerprint.

#### The read: new groups

Trials with documents only. Each group's key is the skill, the seat model,
the skill digest of the plan's section 6, the fingerprint and the CLI
version above. The interval is the 95 percent Wilson interval. The level
is the one `capability/levels.json` computes.

| Skill | Cases | n | Passed | Trials no judge ran | Wilson interval | Level |
|---|---|---|---|---|---|---|
| equivalence_checking | `dv/equiv-gray`, `dv/equiv-updown` | 16 | 16 | 0 | 0.8064 to 1.0 | Practised |
| verification_planning | `dv/plan-irq-ctrl`, `dv/plan-tick-timer` | 16 | 16 | 0 | 0.8064 to 1.0 | Practised |
| failure_triage | `debug/triage-three-bugs`, `debug/triage-pwm-gen` | 16 | 7 | 9 | 0.231 to 0.6682 | Knowledge |
| root_cause_analysis | `debug/root-cause-uart-tx`, `debug/root-cause-debounce` | 16 | 15 | 0 | 0.7167 to 0.9889 | Practised |
| control_logic_design | `rtl/apb-gpio` | 8 | 4 | 0 | 0.2152 to 0.7848 | Knowledge |
| functional_coverage | `dv/fcov-lifo4` | 8 | 8 | 0 | 0.6756 to 1.0 | Practised |
| python_verification | `dv/cocotb-crc` | 8 | 8 | 0 | 0.6756 to 1.0 | Practised |

- failure_triage: this is a figure of the seat under this input contract
  (decision M3); see "The failed trials, by label". The same is said of
  code_coverage's pooled figure below, for the reason given there.
- equivalence_checking: the document's seat-facing text names the kind of
  error the held-out mutants of `dv/equiv-gray` make, and its check record
  passed with stale line citations noted (fact MF8). That narrows what
  that case's control measures.
- functional_coverage, python_verification and control_logic_design each
  rest on one case. For control_logic_design the levels file also holds
  W2-L1's eight trials of the same case on that batch's skill digest, 6
  passed; that group is stale, counts toward nothing and is not pooled,
  and nothing is concluded from setting it beside this one.

#### The read: pooled groups

For each group W2-L1 read: W2-L1's figure, this batch's own figure on its
case, and the pooled figure. No level is computed from either batch alone.

| Skill | W2-L1: n, passed | This batch: case | This batch: n, passed | Pooled: n, passed | Wilson interval | Level |
|---|---|---|---|---|---|---|
| formal_verification | 8, 8 | `dv/formal-rr-arbiter` | 8, 8 | 16, 16 | 0.8064 to 1.0 | Practised |
| sva | 8, 8 | `dv/formal-rr-arbiter` | 8, 8 | 16, 16 | 0.8064 to 1.0 | Practised |
| assertion_coverage | 8, 8 | `dv/formal-rr-arbiter` | 8, 8 | 16, 16 | 0.8064 to 1.0 | Practised |
| code_coverage | 8, 7 | `dv/coverage-tick-timer` | 8, 0 | 16, 7 | 0.231 to 0.6682 | Knowledge |
| directed_testing | 24, 24 | `dv/cocotb-crc` | 8, 8 | 32, 32 | 0.8928 to 1.0 | Practised |
| apb | 16, 14 | `rtl/apb-gpio` | 8, 4 | 24, 18 | 0.551 to 0.88 | Practised |
| rtl_design | 56, 54 | `rtl/apb-gpio` | 8, 4 | 64, 58 | 0.8102 to 0.9563 | Practised |

code_coverage was Practised before this batch and is at Knowledge after
it. The rows of apb and rtl_design add trials on a case each group had
already run, the one exception decision 4 of meeting 1 allows. Every
failed trial of both groups is on `rtl/apb-gpio`, where 10 of the 16
pooled trials passed; `rtl/apb-regs` passed 8 of 8 and rtl_design's other
five cases 40 of 40. Each level is the group's and says nothing of one
case.

#### Per case

The passes among each case's eight trials with documents, as a
description. No interval and no level is given per case.

| Case | Passed of 8 |
|---|---|
| `dv/equiv-gray` | 8 |
| `dv/equiv-updown` | 8 |
| `dv/plan-irq-ctrl` | 8 |
| `dv/plan-tick-timer` | 8 |
| `debug/triage-three-bugs` | 3 |
| `debug/triage-pwm-gen` | 4 |
| `debug/root-cause-uart-tx` | 7 |
| `debug/root-cause-debounce` | 8 |
| `rtl/apb-gpio` | 4 |
| `dv/fcov-lifo4` | 8 |
| `dv/formal-rr-arbiter` | 8 |
| `dv/coverage-tick-timer` | 0 |
| `dv/cocotb-crc` | 8 |

#### The arm without documents

The 13 trials without documents, listed apart. They count toward no
level. Eight of the 13 passed: slots 14, 29, 44, 45, 59, 60, 89 and 117.
Five did not: slots 15, 30, 74, 75 and 103 (below). In the arm with
documents 82 of 104 passed. At one trial per case the arm without
documents shows at most a batch-wide difference, and no conclusion per
skill or per case follows; nothing is said here about whether documents
help.

#### Commits and environments

- W2-L1: `main` at 01adfe9, the owner's machine, the local CLI, without
  the seat account; its records do not name the versions of the EDA tools.
- This batch: every trial ran in the `live-eval` job of the workflow and
  was re-judged in the `rejudge` job of the same run; the replays of gate
  W2C5 ran in the workflow's `replay` job and were re-judged in its
  `rejudge` job. No trial, replay or re-judge ran on the owner's machine.
- As the plan's section 5 states and no wider: in these jobs the tool
  steps named in the plan's table of tools and accounts per case ran as
  the account `nirmaan-seat`; one program, `verilator_coverage`, ran as
  the runner, on the coverage data file a seat's run produced, and read
  no seat HDL; `vplan.check` and `veritriage.investigate` are harness code
  that reads seat text as data. The committed records do not name an
  account: this rests on the workflow and its setup at each slot's commit,
  which did not change during the batch. Not claimed: anything about
  files every account may read beyond the probed targets, a fault in a
  tool's own parser, or any screen class nobody has found.
- The reach test. The committed records of this batch hold no reach
  record, so no committed record shows, for a run of this batch, which
  probes were denied; the one committed reach record
  (`evals/flow/tool_reach_record.json`) is of a run before the batch. At
  every slot's commit the workflow runs the reach test in both jobs,
  before the trial and before the re-judge, and the job stops unless
  every probe is denied and every control passed. By the operator's
  account, which is not a repository control: the saved job logs of all
  117 runs were read for this by security, and in every run, in both
  jobs, the reach test's closing lines read that every probe was denied
  and every probe and control was as required. The reach records
  themselves were not read here.
- The slots ran on twelve heads of `main`, each with
  every value of the plan's section 6 equal: `f4292ff7`, `9646f5b3`,
  `8258034c`, `d83d6aaa`, `f3ad96fe`, `7c4587f2`, `643d1120`, `3b435921`,
  `ac4cf264`, `6e21f719`, `eb6197ff` and `5dce09d5`; the table below gives
  each slot's.
- By the dispatcher's ledger, which reads each run's log, all 117 runs
  reported the same versions in both jobs: Icarus Verilog 12.0-2build2,
  Verilator 5.020-1, Yosys 0.33-5build2, cocotb 2.1.0 and Claude Code
  2.1.325, the versions of the plan's section 5, with no difference in
  any run. The ledger does not read the versions of SymbiYosys, Yices and
  `eqy`: they come from the OSS CAD Suite release the workflow's action
  checks by sha256 on every use, which is in a pinned group equal on all
  twelve heads. It does not read the patch release of Python or the
  versions of `make` and the C++ compiler, which the plan does not pin.
  No committed record of this batch carries a tool version: they are in
  each run's log and in the ledger (gate W2C25).
- So each pooled group mixes trials judged on two tool sets, and mixes
  trials whose tools ran as the seat account with W2-L1's trials, which
  ran on the owner's machine without it. W2-L1's tool set is named
  nowhere. This batch's is named by the plan's section 5 and by the
  operator's ledger; its trial records do not name it either.
- The replays of gate W2C5 (the plan's section 13) ran once per case
  before slot 1, in the `replay` and `rejudge` jobs, with the same five
  versions in their logs. In each, the case's reference answer passed
  every tool before review and every held-out check, every mutant failed
  where a check must fail, and the re-judge gave the same verdict. That
  shows that the job's tool set gives the expected verdict on each case's
  reference answer and mutants, once. It does not show what W2-L1's tool
  set was, that the two tool sets are the same, or that they judge a
  seat's answer alike.

#### The failed trials, by label

27 of the 117 trials failed: 22 with documents and 5 without. Each label
is the one in the `causes.md` beside the record, written before the
record merged, unchanged.

**Trials no judge ran.** Thirteen of the 117: the eleven below, refused
on the form of a cited run, and two trials without documents in which the
seat escalated before review (slots 30 and 103, in the table of "model"
labels). The other fourteen failed trials were judged.

**Refused on the form of a cited run.** Eleven trials, all on the two
triage cases; no failed trial of another group was refused this way:

| Case | With documents (slots) | Without documents (slot) |
|---|---|---|
| `debug/triage-three-bugs` | 27, 39, 63, 88, 110 | 15 |
| `debug/triage-pwm-gen` | 22, 34, 71, 83 | 75 |

Label of each, the same words in all eleven: "knowledge/harness defect
(inference, the model contributing): the card asks the triage to cite a
VeriTriage session; the seat listed the run in the form `run:run-NNNN`,
which no run has, and P5 refused it in every attempt". In each, every gate of every attempt ran and succeeded,
the seat wrote the run in `tool_runs` in the token form (`run:run-NNNN`)
in all three attempts, rule P5 refused each submission before review, and
the held-out check is "not run". The mechanism is fact MF4: the seat is
told to list run IDs from the citation list, that list shows a run only
as a token, and the field takes the bare id. That this is why each of
these trials was refused is an inference, as the label says. Seven other
trials of the same two cases, under the same contract, reached review and
passed (three on `debug/triage-three-bugs`, four on
`debug/triage-pwm-gen`); each of the seven listed the run by its bare id,
slot 51 after one attempt in the token form. The label gives its own
reason for "the model contributing": the seat wrote the same form three
times after the refusal named it. Each of the nine
with documents is a failed trial of failure_triage's group; no count
leaves them out. They are not labelled "model", and no curriculum line is
owed for them. Nothing is said of what any of them would have done had it
reached review.

The same form was written in single attempts of nine other trials. This
is read from the seat's answers in the committed records, since a trial
that passed has no `causes.md`. Eight of them then passed on a later
attempt: slots 6, 43, 67, 79 and 114 (`debug/root-cause-uart-tx`), 86
(`debug/root-cause-debounce`), 35 (`dv/cocotb-crc`) and 51
(`debug/triage-three-bugs`, one of the seven passes above). The ninth is
slot 103, without documents, labelled "model"; its `causes.md` notes the
refusal. In each, the seat's next answer says the attempt was refused for
the run it listed; a record holds no refusal text of its own for an
attempt of a trial that later passed, so that rule P5 refused each of
these attempts is the seat's account and an inference. No figure changes:
each is a figure of the default harness with its three attempts. In all,
20 of the 117 trials listed a run in the token form in one attempt or
more (ai-engineer, qa-evidence, verification-lead).

**Trials labelled "model".** Sixteen. The thirteen with documents were
judged and failed. Of the three without documents, slot 74 was judged and
failed, and slots 30 and 103 never reached review: the plan check refused
the plan's format, the seat escalated on its third attempt, and the
held-out check is "not run".

| Slot | Case | Arm | The label's words |
|---|---|---|---|
| 9 | `dv/coverage-tick-timer` | E | the testbench never runs periodic mode with IE clear |
| 21, 33 | `dv/coverage-tick-timer` | E | the testbench never writes LOAD while the count runs |
| 58, 70, 82, 93, 104 | `dv/coverage-tick-timer` | E | the testbench does not catch a LOAD write that changes the running count, req:TMR-LOAD-LATE |
| 74 | `dv/coverage-tick-timer` | N | the testbench does not catch a LOAD write that changes the running count, req:TMR-LOAD-LATE |
| 64, 111 | `rtl/apb-gpio` | E | the seat's RTL leaves DATA_IN unknown after reset |
| 76 | `rtl/apb-gpio` | E | the seat's RTL leaves PSLVERR unknown on a read |
| 100 | `rtl/apb-gpio` | E | the seat's testbench names a signal its RTL does not have |
| 90 | `debug/root-cause-uart-tx` | E | the repro does not fail the shift-register variant uart_tx_alt_reload |
| 30 | `dv/plan-irq-ctrl` | N | without documents: the plan did not follow the plan check's format, and the seat escalated |
| 103 | `dv/plan-tick-timer` | N | without documents: the plan did not follow the plan check's format, and the seat escalated |

By group, trials with documents: failure_triage, nine, all refused on the
form of a cited run; code_coverage, eight, all "model" (slots 9, 21, 33,
58, 70, 82, 93, 104); control_logic_design, apb and rtl_design, the same
four each, all "model" (slots 64, 76, 100, 111, one case naming three
skills); root_cause_analysis, one, "model" (slot 90). No other group has a
failed trial. The five failed trials without documents belong to no
group.

**`dv/coverage-tick-timer`.** All nine trials (eight with documents, and
slot 74 without) failed the held-out must-fail check, and none failed on
coverage: in every record the judge's clean run and cover run succeeded,
inside the case's bounds. Each record's `scores` names the first mutant
that survived the seat's testbench; the scorer stops there, so the
mutants after it were not run in that trial. In eight trials (slots 21,
33, 58, 70, 74, 82, 93 and 104) the first mutant failed and the second,
`tick_timer_load_late_applies.v`, survived. In slot 9 the first three
failed, that one among them, and the fourth,
`tick_timer_irq_ie_ignored_periodic.v`, survived. The reference testbench
fails all four mutants: a committed test asserts it in the test job, and
the replay of gate W2C5 showed it on this batch's tool set. The approved
RTL the seat is handed shows both behaviours. So the coverage gate and
the scorer judged as built (eda-tooling), and each label stands as
written. The surviving mutant's own run is in no record's `judge_runs`
(fact MF6); it is named in the score's summary, and the re-judge
reproduced the status.

What the seat was given is narrower than the case file reads
(verification-lead). The case's specification states both rules
(TMR-LOAD-LATE, TMR-IRQ), but by the code the coverage stage depends on
the RTL and the testbench stages and not on the specification stage
(`src/nirmaan/company/workflows.py:877`), and the words "write LOAD while
the timer runs" are in the case's `constraints`, which are for people and
are not sent to a seat (`docs/SEAT_EVALUATION.md`). Several of these
records carry the seat's note that the specification or the coverage
bounds were not in its inputs. The prompt itself is not in a record, only
its hash. Whether the seat saw the specification, and whether that is why
eight of the nine testbenches did not catch the LOAD rule, is not
established. It is carried, and it is settled before the curriculum
answer for these trials is written. On W2-L1's case of the same stage 7
of 8 passed. So code_coverage's pooled figure, like failure_triage's, is
a figure of the seat under this input contract. No label is changed, and
the level is the one the rule computes.

**`rtl/apb-gpio`.** The four labels stand as written, and design-architect
read the four records against them at this read. In slots 64, 76 and 111
the seat's RTL has both input sample registers in its reset branch (fact,
from the answer in each record), so the inference those three labels
carry, that a register is left unreset, is not what the records show. In
each of the three the input is widened in an `always @*` block, and in
none of the case's five passing trials of this batch is it. That the
unknown value comes from that block, which a simulator does not run until
one of its inputs changes, is design-architect's inference from a rerun
outside the record, on another version of the simulator than the batch's;
the records do not establish it. In slot 100 the signal the testbench
names is in the seat's own RTL; it is absent from the case's RTL, on
which the must-fail check runs the seat's testbench (fact). The first
failure of slots 64 and 111 is the same check and message as W2-L1's two
failures on this case, and these trials ran on the document that holds
the note of ip#439. Nothing is said of whether that note changed any
result.

The failure-to-curriculum rule applies to these sixteen trials. The
answers are owed and are not given here: verification-lead gives them in a
pull request of its own, one line per failure, as for the timer case
(ip#546). A change they produce to a card or a document follows the
decisions of Part 1 where one applies.

#### Trials in parallel (gate W2C18)

- **The width.** Three, as the plan fixes it. It was never raised, and the
  batch never ran at width one: no trial ended on a plan or usage limit.
- **That trials overlapped.** Every slot's run overlapped the run of one
  or more other slots; the table below names them. At most three were in
  flight at once.
- **The order.** Slots were dispatched in strictly increasing slot order,
  1 to 117. No slot was dispatched after a later one.
- **The other batch (gate W2C9).** No whole-flow dispatch was made from
  slot 1 to slot 117. The dispatcher's check before each of the 117
  dispatches found the timer's batch finished and no run of the workflow
  queued or running but this batch's own, and `main` gained no whole-flow
  record between `f4292ff7` and `188b66a9`.
- **Stops.** One, before slot 1: the dispatcher's first start closed
  before any dispatch because it could not reach GitHub; nothing was in
  flight, and it was started again. From slot 1 to slot 117 no stop
  closed dispatch. No run was cancelled, before its trial or during it; no
  trial was interrupted; nothing was held out, replaced or run again; and
  no job-level stop caused a slot to be dispatched twice.
- **Records.** They reached `main` in slot order. Two events on the
  records side closed no dispatch: a stop of the merge mechanism on one
  record pull request (ip#552), cleared, and a network failure in the
  records tooling after the last dispatch.

Which run was which slot, the width, the order of dispatch, the overlap,
the stops and the tool versions each run reported are the dispatcher's
ledger and log, which are tooling outside this repository: this is the
operator's account, not a repository control. The commit and the result of each slot
are from its committed record.

| Slot | Case | Arm | Run | Commit | Runs that overlapped it (slots) | Result |
|---|---|---|---|---|---|---|
| 1 | `dv/equiv-gray` | E | 45518907089 | `f4292ff7` | 2, 3 | passed |
| 2 | `debug/triage-three-bugs` | E | 45518963968 | `f4292ff7` | 1, 3, 4 | passed |
| 3 | `rtl/apb-gpio` | E | 45519022973 | `f4292ff7` | 1, 2, 4, 5 | passed |
| 4 | `dv/plan-irq-ctrl` | E | 45519820395 | `f4292ff7` | 2, 3, 5, 6 | passed |
| 5 | `dv/formal-rr-arbiter` | E | 45520041929 | `f4292ff7` | 3, 4, 6, 7 | passed |
| 6 | `debug/root-cause-uart-tx` | E | 45520303692 | `f4292ff7` | 4, 5, 7, 8 | passed |
| 7 | `dv/fcov-lifo4` | E | 45520850009 | `f4292ff7` | 5, 6, 8, 9 | passed |
| 8 | `dv/equiv-updown` | E | 45520944212 | `f4292ff7` | 6, 7, 9 | passed |
| 9 | `dv/coverage-tick-timer` | E | 45521481562 | `f4292ff7` | 7, 8, 10, 11 | failed, judged |
| 10 | `debug/triage-pwm-gen` | E | 45522142375 | `f4292ff7` | 9, 11, 12 | passed |
| 11 | `dv/cocotb-crc` | E | 45522198738 | `f4292ff7` | 9, 10, 12 | passed |
| 12 | `dv/plan-tick-timer` | E | 45522693456 | `f4292ff7` | 10, 11, 13, 14 | passed |
| 13 | `debug/root-cause-debounce` | E | 45523358156 | `9646f5b3` | 12, 14, 15 | passed |
| 14 | `dv/equiv-gray` | N | 45523417523 | `9646f5b3` | 12, 13, 15 | passed |
| 15 | `debug/triage-three-bugs` | N | 45523642635 | `9646f5b3` | 13, 14, 16, 17 | failed, no judge ran |
| 16 | `dv/plan-irq-ctrl` | E | 45524581224 | `9646f5b3` | 15, 17, 18 | passed |
| 17 | `dv/formal-rr-arbiter` | E | 45524636184 | `9646f5b3` | 15, 16, 18 | passed |
| 18 | `debug/root-cause-uart-tx` | E | 45524987627 | `9646f5b3` | 16, 17, 19, 20 | passed |
| 19 | `dv/fcov-lifo4` | E | 45525654085 | `9646f5b3` | 18, 20, 21 | passed |
| 20 | `dv/equiv-updown` | E | 45525711654 | `9646f5b3` | 18, 19, 21 | passed |
| 21 | `dv/coverage-tick-timer` | E | 45525932379 | `9646f5b3` | 19, 20, 22, 23 | failed, judged |
| 22 | `debug/triage-pwm-gen` | E | 45526706979 | `8258034c` | 21, 23, 24 | failed, no judge ran |
| 23 | `dv/cocotb-crc` | E | 45526793225 | `8258034c` | 21, 22, 24 | passed |
| 24 | `dv/plan-tick-timer` | E | 45527141731 | `8258034c` | 22, 23 | passed |
| 25 | `debug/root-cause-debounce` | E | 45528175307 | `8258034c` | 26, 27 | passed |
| 26 | `dv/equiv-gray` | E | 45528221772 | `8258034c` | 25, 27 | passed |
| 27 | `debug/triage-three-bugs` | E | 45528283294 | `8258034c` | 25, 26, 28, 29 | failed, no judge ran |
| 28 | `rtl/apb-gpio` | E | 45529151651 | `d83d6aaa` | 27, 29, 30 | passed |
| 29 | `rtl/apb-gpio` | N | 45529200384 | `d83d6aaa` | 27, 28, 30 | passed |
| 30 | `dv/plan-irq-ctrl` | N | 45529525294 | `d83d6aaa` | 28, 29 | failed, no judge ran |
| 31 | `dv/fcov-lifo4` | E | 45530680186 | `d83d6aaa` | 32, 33 | passed |
| 32 | `dv/equiv-updown` | E | 45530734811 | `d83d6aaa` | 31, 33 | passed |
| 33 | `dv/coverage-tick-timer` | E | 45530785114 | `d83d6aaa` | 31, 32 | failed, judged |
| 34 | `debug/triage-pwm-gen` | E | 45531859688 | `d83d6aaa` | 35, 36 | failed, no judge ran |
| 35 | `dv/cocotb-crc` | E | 45531906500 | `d83d6aaa` | 34, 36, 37 | passed |
| 36 | `dv/plan-tick-timer` | E | 45531958356 | `d83d6aaa` | 34, 35, 37 | passed |
| 37 | `debug/root-cause-debounce` | E | 45532812778 | `d83d6aaa` | 35, 36, 38, 39 | passed |
| 38 | `dv/equiv-gray` | E | 45533047016 | `d83d6aaa` | 37, 39, 40 | passed |
| 39 | `debug/triage-three-bugs` | E | 45533099355 | `d83d6aaa` | 37, 38, 40, 41 | failed, no judge ran |
| 40 | `rtl/apb-gpio` | E | 45533575064 | `d83d6aaa` | 38, 39, 41, 42 | passed |
| 41 | `dv/plan-irq-ctrl` | E | 45533795045 | `d83d6aaa` | 39, 40, 42 | passed |
| 42 | `dv/formal-rr-arbiter` | E | 45534409911 | `d83d6aaa` | 40, 41, 43, 44 | passed |
| 43 | `debug/root-cause-uart-tx` | E | 45534892271 | `d83d6aaa` | 42, 44, 45 | passed |
| 44 | `dv/formal-rr-arbiter` | N | 45534945581 | `d83d6aaa` | 42, 43, 45 | passed |
| 45 | `debug/root-cause-uart-tx` | N | 45535429990 | `f3ad96fe` | 43, 44, 46, 47 | passed |
| 46 | `debug/triage-pwm-gen` | E | 45536012424 | `f3ad96fe` | 45, 47, 48 | passed |
| 47 | `dv/cocotb-crc` | E | 45536066390 | `f3ad96fe` | 45, 46, 48 | passed |
| 48 | `dv/plan-tick-timer` | E | 45536383099 | `f3ad96fe` | 46, 47, 49, 50 | passed |
| 49 | `debug/root-cause-debounce` | E | 45536970878 | `f3ad96fe` | 48, 50, 51 | passed |
| 50 | `dv/equiv-gray` | E | 45537023982 | `f3ad96fe` | 48, 49, 51 | passed |
| 51 | `debug/triage-three-bugs` | E | 45537275360 | `f3ad96fe` | 49, 50, 52, 53 | passed |
| 52 | `rtl/apb-gpio` | E | 45537899842 | `f3ad96fe` | 51, 53, 54 | passed |
| 53 | `dv/plan-irq-ctrl` | E | 45537991480 | `f3ad96fe` | 51, 52, 54 | passed |
| 54 | `dv/formal-rr-arbiter` | E | 45538372818 | `f3ad96fe` | 52, 53 | passed |
| 55 | `debug/root-cause-uart-tx` | E | 45539265181 | `7c4587f2` | 56, 57 | passed |
| 56 | `dv/fcov-lifo4` | E | 45539310386 | `7c4587f2` | 55, 57, 58 | passed |
| 57 | `dv/equiv-updown` | E | 45539357785 | `7c4587f2` | 55, 56 | passed |
| 58 | `dv/coverage-tick-timer` | E | 45540224639 | `7c4587f2` | 56, 59, 60 | failed, judged |
| 59 | `dv/fcov-lifo4` | N | 45540298479 | `7c4587f2` | 58, 60 | passed |
| 60 | `dv/equiv-updown` | N | 45540347210 | `7c4587f2` | 58, 59 | passed |
| 61 | `debug/root-cause-debounce` | E | 45541344745 | `7c4587f2` | 62, 63 | passed |
| 62 | `dv/equiv-gray` | E | 45541383506 | `7c4587f2` | 61, 63 | passed |
| 63 | `debug/triage-three-bugs` | E | 45541427304 | `7c4587f2` | 61, 62, 64, 65 | failed, no judge ran |
| 64 | `rtl/apb-gpio` | E | 45542124414 | `7c4587f2` | 63, 65, 66 | failed, judged |
| 65 | `dv/plan-irq-ctrl` | E | 45542183505 | `7c4587f2` | 63, 64, 66 | passed |
| 66 | `dv/formal-rr-arbiter` | E | 45542528271 | `643d1120` | 64, 65 | passed |
| 67 | `debug/root-cause-uart-tx` | E | 45543592204 | `643d1120` | 68, 69 | passed |
| 68 | `dv/fcov-lifo4` | E | 45543640220 | `643d1120` | 67, 69, 70 | passed |
| 69 | `dv/equiv-updown` | E | 45543711842 | `643d1120` | 67, 68 | passed |
| 70 | `dv/coverage-tick-timer` | E | 45544560506 | `643d1120` | 68, 71, 72 | failed, judged |
| 71 | `debug/triage-pwm-gen` | E | 45544674109 | `643d1120` | 70, 72 | failed, no judge ran |
| 72 | `dv/cocotb-crc` | E | 45544726850 | `643d1120` | 70, 71 | passed |
| 73 | `dv/plan-tick-timer` | E | 45545771016 | `3b435921` | 74, 75 | passed |
| 74 | `dv/coverage-tick-timer` | N | 45545814003 | `3b435921` | 73, 75 | failed, judged |
| 75 | `debug/triage-pwm-gen` | N | 45545873791 | `3b435921` | 73, 74, 76, 77 | failed, no judge ran |
| 76 | `rtl/apb-gpio` | E | 45546830513 | `3b435921` | 75, 77, 78 | failed, judged |
| 77 | `dv/plan-irq-ctrl` | E | 45546875810 | `3b435921` | 75, 76, 78 | passed |
| 78 | `dv/formal-rr-arbiter` | E | 45547078616 | `3b435921` | 76, 77 | passed |
| 79 | `debug/root-cause-uart-tx` | E | 45548301332 | `3b435921` | 80, 81 | passed |
| 80 | `dv/fcov-lifo4` | E | 45548344833 | `3b435921` | 79, 81, 82 | passed |
| 81 | `dv/equiv-updown` | E | 45548392634 | `3b435921` | 79, 80 | passed |
| 82 | `dv/coverage-tick-timer` | E | 45549210359 | `3b435921` | 80, 83, 84 | failed, judged |
| 83 | `debug/triage-pwm-gen` | E | 45549318430 | `3b435921` | 82, 84, 85 | failed, no judge ran |
| 84 | `dv/cocotb-crc` | E | 45549365044 | `3b435921` | 82, 83, 85 | passed |
| 85 | `dv/plan-tick-timer` | E | 45550024035 | `ac4cf264` | 83, 84, 86, 87 | passed |
| 86 | `debug/root-cause-debounce` | E | 45550453062 | `ac4cf264` | 85, 87, 88 | passed |
| 87 | `dv/equiv-gray` | E | 45550495106 | `ac4cf264` | 85, 86, 88 | passed |
| 88 | `debug/triage-three-bugs` | E | 45550708919 | `ac4cf264` | 86, 87, 89, 90 | failed, no judge ran |
| 89 | `dv/cocotb-crc` | N | 45551419031 | `ac4cf264` | 88, 90, 91 | passed |
| 90 | `debug/root-cause-uart-tx` | E | 45551469299 | `ac4cf264` | 88, 89, 91 | failed, judged |
| 91 | `dv/fcov-lifo4` | E | 45551796124 | `ac4cf264` | 89, 90, 92, 93 | passed |
| 92 | `dv/equiv-updown` | E | 45552433945 | `ac4cf264` | 91, 93, 94 | passed |
| 93 | `dv/coverage-tick-timer` | E | 45552494730 | `ac4cf264` | 91, 92, 94, 95 | failed, judged |
| 94 | `debug/triage-pwm-gen` | E | 45552860752 | `ac4cf264` | 92, 93, 95, 96 | passed |
| 95 | `dv/cocotb-crc` | E | 45553321724 | `6e21f719` | 93, 94, 96, 97 | passed |
| 96 | `dv/plan-tick-timer` | E | 45553536540 | `6e21f719` | 94, 95, 97, 98 | passed |
| 97 | `debug/root-cause-debounce` | E | 45554009760 | `6e21f719` | 95, 96, 98, 99 | passed |
| 98 | `dv/equiv-gray` | E | 45554233193 | `6e21f719` | 96, 97, 99, 100 | passed |
| 99 | `debug/triage-three-bugs` | E | 45554443322 | `6e21f719` | 97, 98, 100, 101 | passed |
| 100 | `rtl/apb-gpio` | E | 45554792178 | `6e21f719` | 98, 99, 101, 102 | failed, judged |
| 101 | `dv/plan-irq-ctrl` | E | 45554993164 | `6e21f719` | 99, 100, 102 | passed |
| 102 | `dv/formal-rr-arbiter` | E | 45555328060 | `6e21f719` | 100, 101, 103, 104 | passed |
| 103 | `dv/plan-tick-timer` | N | 45555950335 | `6e21f719` | 102, 104, 105 | failed, no judge ran |
| 104 | `dv/coverage-tick-timer` | E | 45555997657 | `6e21f719` | 102, 103, 105 | failed, judged |
| 105 | `debug/triage-pwm-gen` | E | 45556191070 | `6e21f719` | 103, 104 | passed |
| 106 | `dv/cocotb-crc` | E | 45557063352 | `eb6197ff` | 107, 108 | passed |
| 107 | `dv/plan-tick-timer` | E | 45557109140 | `eb6197ff` | 106, 108 | passed |
| 108 | `debug/root-cause-debounce` | E | 45557158117 | `eb6197ff` | 106, 107 | passed |
| 109 | `dv/equiv-gray` | E | 45558036770 | `eb6197ff` | 110, 111 | passed |
| 110 | `debug/triage-three-bugs` | E | 45558118671 | `eb6197ff` | 109, 111, 112 | failed, no judge ran |
| 111 | `rtl/apb-gpio` | E | 45558177839 | `eb6197ff` | 109, 110, 112, 113 | failed, judged |
| 112 | `dv/plan-irq-ctrl` | E | 45558915172 | `5dce09d5` | 110, 111, 113, 114 | passed |
| 113 | `dv/formal-rr-arbiter` | E | 45559264628 | `5dce09d5` | 111, 112, 114, 115 | passed |
| 114 | `debug/root-cause-uart-tx` | E | 45559482487 | `5dce09d5` | 112, 113, 115, 116 | passed |
| 115 | `dv/fcov-lifo4` | E | 45559725898 | `5dce09d5` | 113, 114, 116, 117 | passed |
| 116 | `dv/equiv-updown` | E | 45560218439 | `5dce09d5` | 114, 115, 117 | passed |
| 117 | `debug/root-cause-debounce` | N | 45560334380 | `5dce09d5` | 115, 116 | passed |

Not said, here or in any text that draws on this read: that running
trials at once had an effect on a result, or that it had none; that this
batch and W2-L1 ran under the same dispatch conditions (W2-L1 ran one
trial at a time); that the two batches ran on the same tools; or anything
decision M2 forbids.

#### The exit items

The build-out record names item 11 as a wave exit criterion and gives wave
2 as "the five-department cut, must-fail scorers"; the other items are
those the wave's plan set and meeting 1 ruled on. No committed record
sets a number of Practised skills (fact MF9).

| Exit item | State | Where |
|---|---|---|
| The five-department cut and must-fail scorers | Met: Verification is cut into five departments; the must-fail scorers judge the wave's cases | build-out record, section 10; meeting 1, fact 14; `docs/EVAL_SKILLS_MUST_FAIL.md` |
| Managers and leads | Met: five department director roles; no practice lead seated, the condition not met | meeting 1, decision 1; decision M10 |
| Skills at Knowledge | Met with named exceptions: of the 34 verification skills, 32 have a level (12 Practised, 20 at Knowledge); waveform_debug has none and is a named exception (no source an agent may read in full); security_verification has none and leaves for the Security wave. systemverilog is not one of the 34 (its domain is the hardware language); it is Practised by trials with no knowledge document, a named exception | meeting 1, decision 8 |
| Practising skills have evals | Met with three named exceptions, each "tool available, no eval case, not measured, at Knowledge": log_analysis, regression_intelligence, regression_management. The list is closed and its test is on `main` | meeting 1, decision 2; fact MF2 |
| Evidence on those evals | Met: every skill a batch case names has a group, read once (above). Three of those groups do not count as Practised; they are carried | this part |
| Examples in CI | Met: two, simulation and formal | meeting 1, decision 8 |
| Item 11 of the build-out record | Met | meeting 1, decision 7 |
| Metrics | Met: review throughput and usage were measured privately, in the pilot's form. No figure is given in this record | build-out record, section 10 |
| Curriculum answers for W2-L1 | Met when the pull request of this addendum lists them: thirteen lines, the eleven of W2-L1 and the two calibration records, as decision M8 rules; key 1 checks the list against the script's output. The answers for this batch's sixteen trials labelled "model" are owed and carried | decision M8 |

#### Decisions M5 and M8 after the read

Neither ruling changes; each was fixed before the read. Two facts are new
(design-architect).

- **Decision M5.** Its cost is now known: the group the note makes stale
  is rtl_design's pooled group of 64 trials on seven cases, and from the
  note's merge until a new group counts rtl_design holds no counted
  group. The answers owed for slots 64, 76, 100 and 111 concern how a
  combinational block and a testbench are written, which
  `knowledge/design/rtl_design.md` holds. So every line that changes that
  document, the note of decision M5 and any such answer, merges in one
  change under gate W2C22, and the group goes stale once.
- **Decision M8, fourth row.** The answer is given as ruled. The four
  records it answers (W2-L1's two and the two calibration records) also
  have both sample registers in the reset branch and the same `always @*`
  widening (fact, from the records). The note of ip#439, and the mutant of
  `rtl/apb-gpio-reset`, describe a register left out of the reset branch,
  which those records do not show. The answer's line says so, and a
  corrected answer is carried.

#### The verdict

By the rule of decision M1, fixed before the read:

1. all 117 records are on `main` and were read once; the levels check
   passes; no record is refused; no failed trial is without a label; no
   label changed; every record was made on the plan's values;
2. every exit item is met or is a named exception (the table above);
3. every skill of the batch has the level the level rule computes, stated
   with its group in the tables above, and no group fails to count for a
   reason other than its pass count: the three groups that do not count
   (failure_triage, control_logic_design and the pooled code_coverage)
   each have one reason, a Wilson lower bound under 0.5 (0.231, 0.215 and
   0.231). The nine trials of failure_triage that no judge ran are failed
   trials of that group by the rule fixed before the read (decision M3,
   item 1), so they are part of its pass count and not a separate reason.
   Each of the three skills is carried below with an owner seat.

**Wave 2 (Verification) exit: met with named exceptions.** It means that
the wave's work is closed and was measured once. It says nothing about
how many skills are Practised, and it is never quoted without the levels
and the exceptions beside it:

- After the read `capability/levels.json` holds 20 skills Practised, 25
  at Knowledge and none Proven. Five skills became Practised
  (equivalence_checking, verification_planning, root_cause_analysis,
  functional_coverage, python_verification) and one, code_coverage, is no
  longer Practised.
- Of the 34 verification skills, twelve are Practised: assertion_coverage,
  constrained_random, directed_testing, equivalence_checking,
  formal_verification, functional_coverage, model_checking,
  python_verification, reference_modelling, root_cause_analysis, sva and
  verification_planning. Twenty are at Knowledge, and two have no level
  (waveform_debug and security_verification).
- Three skills of the batch are at Knowledge after the read:
  failure_triage (7 of 16 passed; no judge ran in 9), code_coverage
  (pooled 7 of 16; 0 of 8 in this batch; it was Practised before) and
  control_logic_design (4 of 8, one case). The figures of failure_triage
  and code_coverage are figures of the seat under this input contract.
  apb and rtl_design stay Practised on their pooled figures; this batch's
  own trials on `rtl/apb-gpio` passed 4 of 8.
- Named exceptions: log_analysis, regression_intelligence and
  regression_management (not measured); waveform_debug (no document);
  systemverilog (Practised by trials, no knowledge document; the language
  standard was not read or used); security_verification (moved to the
  Security wave).

This was the one read of the batch. There is no top-up, extension,
replacement or second read. The freeze of the plan's section 7 ends when
this addendum merges.

#### Carried, with an owner seat each

| Item | Owner |
|---|---|
| code_coverage, at Knowledge after the read: first, what the coverage seat is given on `dv/coverage-tick-timer` (render the case's prompt with no model and compare it with the records' prompt hash); then the curriculum answer for its nine failed trials (eight with documents, and slot 74 without); then a new measurement under the next verification batch's plan. A change to the stage's dependencies or to the case is a change of its own, returns to the council and is never made together with the trials it would grade | verification-lead; ai-engineer checks the prompt |
| failure_triage, at Knowledge: the sentence of decision M4, item 1, then a new measurement under a new committed plan (gate W2C20); the harness change (gate W2C21), which also ends the refused attempts in other groups, and whose return to the council also shows a test in which an advisory run and a run of another task, each written in the token form, are dropped as the bare id is | verification-lead; ai-engineer, with security |
| Rule P5's file, `src/nirmaan/work/policy.py`, is outside the default fingerprint: whether it joins `harness.CODE`, decided with the change of gate W2C21 | ai-engineer |
| control_logic_design, at Knowledge on one case: a second case on another control structure, in the Design wave | design-architect |
| The curriculum answers for the batch's sixteen trials labelled "model": verification-lead's lane writes the list in a pull request of its own; for slots 64, 76, 100 and 111 design-architect gives the answer and holds key 1 on any note | verification-lead; design-architect |
| The note of ip#439 and the W2-L1 answer on `rtl/apb-gpio`, against what the records show (both samples reset, the input widened in an `always @*` block): a corrected answer, and whether the note and the mutant of `rtl/apb-gpio-reset` stay as they are | design-architect, with verification-lead |
| `knowledge/design/rtl_design.md` changes once: the note of gate W2C22 and any answer for slots 64, 76, 100 and 111 that is a line of that document, in one change; the stage that writes the whole-flow testbench | design-architect, with verification-lead |
| The three closed exceptions and what each needs before a case can name it | eda-tooling (the builds); verification-lead (the list and its test) |
| waveform_debug and systemverilog documents, if a source is obtained | verification-lead |
| security_verification: no level; its document and its case belong to the Security wave | security |
| Single-case skills: constrained_random, reference_modelling, model_checking, functional_coverage, python_verification (the next verification batch's plan); fsm_design, arbitration, pipeline_design (the Design wave) | verification-lead; design-architect |
| A surviving mutant's run in the record, for both must-fail scorers (gate W2C23) | eda-tooling |
| The register block before slot 21 (gate W2C24). Its dated addition also restates "Gate backends": the whole-flow plan last states the value the timer's twenty trials ran on, and does not state the value ip#522 moved it to, `sha256:17c4b3d7d52e73db75f486dff7507dd1eacf3c8cd97a75f287a108f9e003203f`, which is the value on `main` at `188b66a9`. If the scorer change of gate W2C23 merges before slot 21, the same addition restates "Held-out scorers". A checker under `scripts/` that the dispatcher calls is the follow-up of decision M7 | eda-tooling |
| Tool versions in each record (gate W2C25), the OSS CAD Suite release and the compiler's version included; the three apt packages and the runner image are not pinned by the repository; tool and library identity for physical design | eda-tooling, with ai-engineer |
| The equivalence_checking text and its line citations, reworded in one change; a machine check of the lines a check record cites | verification-lead; qa-evidence |
| `scripts/failure_curriculum.py` reports no failure and exits 0 when given a path where it expects a key (fact MF3): refuse an argument that matches no record | verification-lead; qa-evidence checks |
| History for the triage binding, a bound `regression.run`, section placement in the planning contract, the processor models unit | as decision M9, item 5 |
| The practice-lead fact, restated at the next wave close (decision M10) | verification-lead |
| The exit items of the next wave, written into a committed record before its first batch | product-lead, with that wave's owner seat |
| Any public line about this verdict: a separate pull request, with the exceptions beside it | brand-content, with product-lead |

**What the next wave may assume.** The next wave may start (decision M1).
It may assume only the levels that `capability/levels.json` holds at
`188b66a9`, each with its group and the limits stated in this read, and
nothing of a carried item until that item's own pull request has merged:
no fix of decision M4, no note of decision M5, and no new measurement of
failure_triage, code_coverage or control_logic_design. A skill at
Knowledge here is not planned, staffed or described as Practised by a
later wave. Where a later wave relies on apb or rtl_design it reads both
figures, the pooled one and this batch's 4 of 8 on `rtl/apb-gpio`. The
three closed exceptions, waveform_debug and security_verification are not
measured, and no wave treats them as measured.

#### Seat statements

Seven seats read the draft of Part 2, each as a read-only process of its
own that saw no other seat's answer: verification-lead, qa-evidence,
ai-engineer, eda-tooling, security, design-architect and product-lead.
Each checked its own items against the committed records at `188b66a9`;
several also read the private dispatcher's ledger and logs, and none ran
it. The chair took every correction the seats required; where two seats
worded the same sentence, the owner's wording stands. No seat dissented
from the read or from the verdict. An agent's read is not a person's
approval.

- **verification-lead** (owner of the read). States this as the batch's
  one read and accepts "met with named exceptions". code_coverage is at
  Knowledge by the rule, and its labels stay. The read must not say the
  seat was asked to write LOAD while the timer runs: that text is for
  people, and by the code the coverage stage is not handed the
  specification; what the seat saw is carried and settled before those
  failures are answered. It owes the sixteen curriculum lines in a pull
  request of its own. Its dissents of Part 1 stand as recorded.
- **qa-evidence** (gates W2C11, W2C18 and W2C19). Recomputed every figure
  of the read from the 117 committed records and the levels file: counts,
  intervals, levels and totals reproduce, and no label changed. It passed
  the draft on condition of eight corrections, all taken. The W2-L1
  curriculum answers are checked on the pull request with the script.
- **ai-engineer** (gates W2C7, W2C9, W2C16 and W2C21). Every figure sits
  in one group key, recomputed at `188b66a9`; the freeze held; the width
  stayed three, with no limit, cancel or second run. Twenty of the 117
  trials wrote a run in the token form. It renews, with that as evidence,
  its position that the harness change be brought forward if no change
  that restarts every group is planned; not ruled, it returns with the
  next verification batch's plan.
- **eda-tooling** (gates W2C5, W2C17 and W2C23 to W2C25). The tool
  versions are the dispatcher's ledger, and no committed record carries
  one yet. The replays show the job judges each reference answer and
  mutant as expected, once, and say nothing of W2-L1's tools. On the tick
  timer the coverage gate and the scorer judged as built. Nothing here is
  signoff.
- **security** (gates W2C2 to W2C4). The trials ran in CI with the named
  tool steps as the seat account, as the plan claims and no wider. That
  every probe was denied in every run is the operator's account from
  saved job logs. Nothing in the stops is a security event. The harness
  change for cited runs stays behind gate W2C21 with its conditions.
- **design-architect.** The three Design figures are right. In the trials
  that read unknown after reset the sample registers are reset; the note
  of ip#439 describes another fault, and a corrected answer is carried.
  Only simulation and formal on small configurations ran; nothing here
  says a block is ready for silicon.
- **product-lead.** The verdict is the one decision M1 gives. It closes
  the wave's work and says nothing about how good the seats are. No
  public page changes with this addendum; any public line is a separate
  pull request and the founder's to word.

#### Open, for the founder

1. This read and this verdict, to confirm or overrule, including that
   code_coverage fell from Practised to Knowledge.
2. Usage for a later batch that measures failure_triage and code_coverage
   again. Nothing here approves it.
3. A source for a systemverilog document, and one for waveform_debug that
   an agent may read in full, if wanted (meeting 1, decision 8).
4. Any public wording of this verdict, and whether any public page shows
   a level or a count of Practised skills. Until the founder says so,
   none does.
5. For information: the batch's parallel runs shared the one secret of
   the `live-eval` environment, and the residual of the seat account is
   the one the plan's section 5 states and decision 4 of meeting 1
   accepts.
