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
