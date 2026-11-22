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
