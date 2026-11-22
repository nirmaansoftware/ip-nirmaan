# Council record: whole-flow cases (G3, 2026-11-17)

The pilot retrospective
(`council/records/2026-11-14-pilot-retrospective.md`, decision 6) ruled that a
whole-flow trial credits no skill level and forms its own labelled group. A
whole-flow trial is one where a request goes in, every work stage is seated by
the model, and only the final block is judged. This record fixes what the code
that follows needs: how such a trial is counted and listed, the two first
cases with their must-fail controls, the shape of the runner option and its
place in the harness fingerprint, and the counts and timing.

Eight seats gave round 1 positions independently (verification-lead,
eda-tooling, ai-engineer, qa-evidence, design-architect, firmware-engineer,
security, product-lead); the chair decided. The meeting was kept to the seats
that own the evidence and the level rule (verification-lead), the runner and
CI (eda-tooling), the harness (ai-engineer), the cases (design-architect,
firmware-engineer), the claims (qa-evidence), security, and the buyer's
reading (product-lead). The precedent is
`council/records/2026-11-15-pilot-topup-reruns.md`, which seated three. Read
against ip-nirmaan `main` at b5b7967. The chair recounted committed trial
files and computed interval bounds with a short script on a read-only copy; it
ran no design tool. This record changes no code, case, record, level or gate.
No whole-flow trial has run, and this record states no whole-flow result.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below. The founder was away. That the council
rules now is the answer of the orchestrator, on the founder's in-session
instruction of 2026-11-14. It is not a founder decision, and the founder can
overrule it. The use of the plan for whole-flow trials was answered the same
way in the retrospective ("Who decided what", lines 29 to 31). One item is
kept for the founder: any public name for the measure of decision 1, if it is
ever to appear outside the repository's records (see "Open, for the
founder").

## Facts checked

The chair checked each line below in the worktree at b5b7967 unless a seat is
named as the source.

1. Prior rulings. Decision 6 of the retrospective is at lines 244 to 258;
   gates RT4, RT6 and RT9 at lines 391, 393 and 396. Decisions 10 and 11
   (lines 308 and 326 onward) fix counts before a run, keep an interrupted
   trial a failed trial, and read once. The ruling of 2026-11-15 adds: re-runs
   earn nothing, nothing is relabelled, and no level rule changes between a
   run and its read.
2. Credit today. `src/nirmaan/evals/levels.py:256-257` credits every skill in
   a case's `skills`, in a group keyed by skill, model, skill digest, harness
   and CLI. Only three labels take a trial out: `knowledge: off`, a purpose
   other than evidence (a mixed record is refused, 209 to 213), and a harness
   variant (238 to 244). There is no whole-flow list, so an unlabelled
   whole-flow record that named skills would be credited. A case may name no
   skill (`src/nirmaan/models/evaluation.py:79`).
3. Digests. A trial records digests only for the case's own skills
   (`src/nirmaan/evals/records.py:164`). No record today holds a digest for a
   skill another stage was given.
4. The runner. `_prepare` fixes every upstream work stage through
   `_fix_upstream` (`src/nirmaan/evals/runner.py:121-155, 171-187`). The
   fixture's review note says "as reviewed in the repository, not here"
   (`runner.py:164`): true of a reference document, false of a model's. Model
   calls, gate runs and attestations are read for the seat task only
   (`runner.py:285, 290-299`); `EvalResult` holds one seat, one status and one
   attempt count (`evaluation.py:154-157`).
5. Fingerprint. `nirmaan/evals/runner.py` is in `CODE`
   (`src/nirmaan/runtime/harness.py:273`), so any edit to it changes every
   harness fingerprint. `records.py`, `levels.py` and `models/evaluation.py`
   are not in `CODE` (263 to 276). A variant may set only `attempts` and
   `tools` (`tests/test_harness.py:221-227`). The tools-in-loop variant adds a
   `loop` section with its own code digests, which is absent from the default
   fingerprint (`harness.py:326-328`, `docs/HARNESS.md:118-122`).
6. Levels now. `capability/levels.json` totals: knowledge 40, practised 0,
   proven 0; its `calibration` and `variants` lists are empty. Every pilot
   group is stale on the harness (qa-evidence), so a further fingerprint
   change loses no group that counts.
7. The stages (qa-evidence ran the planner for both requests). The timer
   request plans requirements, interface-spec, microarchitecture and
   rtl-implementation; the register block request adds firmware, which depends
   on interface-spec and rtl-implementation. The rtl-implementation stage
   outputs both RTL and testbench from one seat. The three specification
   stages have no before-review check, only the review record.
8. No register map artifact. A `register_map` output exists only from the
   `register-map` stage, planned when the request asks for a register map, and
   that stage depends on interface-spec, not on the RTL
   (`src/nirmaan/company/workflows.py:588-595`). Neither request plans it. The
   `device_drivers` skill card says the map header is written "from the
   approved interface specification, never from the RTL"
   (`src/nirmaan/company/skills.py:630`), and
   `evals/firmware/axi4_lite/driver_api.md` lines 5 to 10 say the same.
   Decision 6 says the map comes "from the RTL stage's output, not the
   specification". The two wordings disagree, and no artifact stands behind
   either.
9. The judge. The must-fail scorer first runs the seat's test on the reference
   RTL and fails the check if that clean run fails
   (`src/nirmaan/evals/scorers.py:194-198`). `evals/rtl/axi4_lite_regs.json`
   line 18 says a different but valid latency or response choice fails the
   reference testbench. So a fair judge of a whole flow needs a fixed input
   that pins what the reference files check.
10. Fixed inputs that exist. `evals/spec/axi4_lite/requirements.md` pins
    offsets, port names, strobes, the error response and a latency bound for
    the register block (design-architect, firmware-engineer). The timer has no
    requirements document: `tests/fixtures/rtl/axil_timer/` holds an interface
    specification and a microarchitecture only. Task inputs are stored as file
    paths that parameterize a task's tools
    (`src/nirmaan/runtime/model.py:210-213`); that a document given this way
    reaches the requirements seat as text is not shown.
11. The driver case. `evals/firmware/axi4_lite_driver.json` has two held-out
    checks and no mutant. `device_drivers` is in the "software" domain
    (`skills.py:627`), outside `MUST_FAIL_DOMAINS`
    (`src/nirmaan/company/evidence.py:15`). A wrong-map header fixture exists
    (`tests/fixtures/fw/axi4_lite/axi4_lite_regs_map_wrong.h`). The held-out
    test checks a misaligned read and no unmapped write
    (`evals/firmware/axi4_lite/held_out_test.c:63-70`).
12. The stop rule. `no_model_answer` is true only when every recorded answer
    has no text (`records.py:183-190`). In a whole flow a limit met at a later
    stage leaves earlier answers with text, so the rule would not fire
    (qa-evidence; read from the code, not run).
13. CI. `.github/workflows/live-eval.yml` runs a fixed command with five
    trials on fixed seats (58 to 59), installs no RISC-V compiler (34), pins a
    CLI version (44) and never commits its record (8). Nothing in
    `src/nirmaan` checks that a run is in CI (security): the rule in
    `docs/GATE_INPUTS.md` lines 126 to 135, that code-by-design cases run in
    CI, is kept by procedure.
14. Corrections to the brief (qa-evidence; the chair recounted). The brief
    said the model "passed most" single-seat trials on these blocks. The
    committed trials with documents are 7 passed of 13 on rtl/axil-timer, six
    of them with no judge run, and 8 passed of 10 on rtl/axi4-lite-regs, two
    with no judge run. Every trial used one attempt. There is no committed
    live trial of firmware/axi4-lite-driver. The sentence that the cases are
    near the model's ceiling is decision 2 of the retrospective (lines 152 to
    161), not the addendum.
15. Not checked from the repository. The H3 batch, its plan, its arms and its
    state are in private plans. No H3 plan or record is on `main` at b5b7967.
    Every statement below about H3 rests on the orchestrator's account.
16. Interval bounds, from the formula the levels use (not results). At five
    trials the 95 percent lower bound is 0.566 for five passes and 0.376 for
    four. At ten it is 0.722, 0.596 and 0.490 for ten, nine and eight
    (ai-engineer; the chair recomputed).

## Decisions

### 1. Crediting: no skill, no level, no bar; one listed count

Decision 6 stands. A whole-flow trial credits no skill and no level.

- **The measure.** One measure, named "whole-flow pass count" in the
  repository's records: passed of planned trials, written "k of n" with its
  95 percent Wilson interval, per group. It is never a bare percentage, never
  called a level or a score, has no bar, and is never pooled across cases,
  arms or with fixed-upstream trials.
- **When it may be stated.** Only for a group whose planned count is complete
  and is at least ten trials. Below that the trials are listed one by one and
  no count is stated.
- **The group key.** Case digest, model, harness fingerprint, CLI and flow
  digest. The flow digest is a hash over the sorted list of (stage, skill,
  skill digest) for every skill each seated stage was given, as it was given
  in that arm. The record holds that list per stage. Fixed inputs are case
  files, so the case digest covers them.
- **Where it is listed.** Under a new `whole_flow` list in
  `capability/levels.json`, never under `skills` and never in the totals.
- **Two locks.** The label (decision 3) takes the trial out of the levels. A
  whole-flow case also names no skill in `skills` and lists the skills
  exercised in a separate field, so the existing rule credits nothing even if
  a label is lost.
- **Counting.** Decisions 10 and 11 and the ruling of 2026-11-15 apply as
  written: counts fixed in a committed plan, an interrupted or unjudged trial
  is a failed trial of its group, no re-run earns anything, one read.
- **Failures.** A failed trial records the first stage that did not complete.
  A cause is stated as fact only where that stage's own gate refused, with the
  run id. The three specification stages have no check (fact 7), so a cause
  placed there is an inference and is labelled so. The failure-to-curriculum
  rule (retrospective, decision 7) applies to trials labelled "model" and
  names the failing run. No per-stage figure is ever stated as a skill rate.

Who disagreed. On the name: verification-lead "whole-flow pass count",
ai-engineer "flow pass count", product-lead "whole-flow pass rate";
qa-evidence wanted a plain count and no name that reads like a level. The
chair chose a count: "rate" invites a percentage without its n. On the
minimum: product-lead proposed five, the floor the levels use;
verification-lead and ai-engineer ten. The chair chose ten: at five trials
one failure already puts the lower bound under one half (fact 16), so a count
of five says too little to state. No seat asked for a bar.

Owner verification-lead (rule); qa-evidence checks every statement of the
measure. First pull request: the label and the list (decision 3, "The label
and the list").

### 2. The two cases and their must-fail controls

**What pins the contract.** Each case has a fixed requirements document, given
with the request as the customer's input. It is "request in": it is written
before the flow and is no stage's output. The requirements stage stays seated
and must carry the document forward; a pin lost there is a real failure of
the flow. Interface specification and microarchitecture are the seats' own.
The record names every fixed input with its digest and says which stages were
seated.

That the document's text reaches the requirements seat is not shown today
(fact 10). The runner change must show it by a test. If it cannot be done
honestly, the requirements stage is fixed to the document instead and every
such trial is labelled "seated from interface-spec"; it is then never
described as every stage seated (design-architect).

The judge assumes only behaviour at the ports that the fixed document states.
Where the document leaves a range, the judge accepts the whole range. Every
held-out check and every mutant cites a statement in the fixed document.

**The same rule binds the flow's own tests.** The fixed document says in
words that a testbench or a driver test must accept every behaviour the
document allows, and must not require one choice inside a range. A flow's
testbench or driver test that is stricter than the fixed document (for
example one that requires exactly two cycles where the document allows up to
two) fails on the reference RTL, and that is a failure of the flow, recorded
with the cause "test stricter than the contract". It is not treated as a
fault of the judge. Checks 3, 6 and 7 of case (b), and the clean run of the
timer's must-fail check, rest on this rule.

**Limit of the claim.** With this much pinned, a pass shows that a contract
was carried through the seated stages to a working block, in simulation and
small formal runs only. It does not show that the model wrote a
specification unaided, and it proves no block.

**(a) Timer: request to RTL with its testbench.**

- Request: "Create an AXI4-Lite timer peripheral with an interrupt."
- Fixed input: a new timer requirements document, stating as port-level
  behaviour everything the reference testbench checks (module and port names,
  the address width range including a width above four, the map and access
  types, count length and its reference edge, stop, restart, interrupt and
  error response rules). It does not exist yet (fact 10).
- Seated: requirements, interface-spec, microarchitecture, rtl-implementation.
- Final block: the rtl-implementation stage's RTL and testbench.
- Verdict: the reference testbench passes on the flow's RTL; and the flow's
  testbench passes on the reference RTL and fails each of the four committed
  timer mutants. The two case proofs of the single-seat case run on case files
  only (qa-evidence), so they are not part of this verdict.
- Name: this case is never described as specification, RTL, then
  verification. One seat writes the RTL and its testbench (fact 7).

**(b) Register block: request to RTL and its driver.**

- Request: "Create an AXI4-Lite register block and its driver."
- Fixed inputs: `evals/spec/axi4_lite/requirements.md` (or a copy under the
  case's own folder), and the case's own copy of the driver programming
  interface, because the held-out test links against its names. The record
  labels the trial "driver interface fixed". The single-seat firmware case and
  its documents stay untouched.
- Seated: the four stages above, then firmware.
- Final block: the flow's RTL and the flow's driver.
- Verdict, all required:
  1. the reference testbench passes on the flow's RTL;
  2. the map check (`regmap.verify`) passes on the flow's RTL;
  3. the flow's testbench passes on the reference RTL and fails each of the
     three committed register block mutants;
  4. the driver alone builds under the strict flags;
  5. the held-out test passes on the flow's driver against the flow's own
     RTL, with the top taken from the RTL stage's declared entry;
  6. the held-out test passes on the flow's driver against the reference RTL;
  7. the flow's driver and driver test pass on the reference RTL and fail the
     RTL mutants that are visible through the driver.
  A pass on the reference RTL alone is never reported as a whole-flow pass.
- The held-out test for this case is the case's own copy, with an
  unmapped-write check added (fact 11), so the single-seat case's digest does
  not change.

**Where the register map comes from.** No map artifact exists in this flow
(fact 8), and this record adds none. Decision 6's sentence is applied as
follows: no reference specification, reference map or reference RTL is handed
to the firmware seat. It works from the flow's own approved interface
specification and the flow's own approved RTL, and from the two fixed inputs.
The judge never trusts the seat's map header: the held-out test reads at the
offsets the fixed requirements pin, on the flow's RTL. The case's copy of the
driver interface says the offsets are the requirements document's and that
the header must agree with the flow's approved RTL. The request is not
reworded to plan the `register-map` stage: that stage is written from the
interface specification, so it would not meet decision 6 either, and it
changes the flow under test. The disagreement between the skill card and
decision 6 (fact 8) is not settled here; a card change is its own pull
request (owner firmware-engineer, with design-architect).

**Judge controls.** Before any live trial, each case is proven by replays with
no model call, run in CI, committed with their records:

- the reference flow passes every check;
- a planted fault fails: for the timer, a flow ending in a mutant RTL, and a
  weak testbench; for the register block, the reference driver with the
  wrong-map header under the map's name, the reference driver on the strobe
  and unmapped-write mutants, and fixture drivers with a swallowed bus error,
  an all-strobes byte write and a sticky last response;
- a second conforming RTL that uses each freedom the fixed document leaves
  open passes the checks that run on the flow's RTL (the reference testbench,
  the map check and the held-out test: checks 1, 2 and 5). This shows the
  judge's own files hold no hidden reference choice;
- the reference testbench and the reference driver test, which accept the
  whole range, pass on both the reference RTL and the conforming RTL; and a
  fixture testbench and a fixture driver test written to the conforming
  RTL's one choice fail on the reference RTL. This shows that a test which
  follows the rule above passes on either RTL, and that the checks on the
  reference RTL (3, 6 and 7) catch a test that does not. Those checks are
  fair by the rule, which the fixed document states to the seats, and not by
  the conforming RTL alone.
  (Amended 2026-11-18 for the fixture driver test: see the addendum at the
  end of this record.)
  (Amended again 2026-11-18: the fixture driver test is required again. See
  the second addendum.)

Who disagreed. On the driver's RTL: design-architect and product-lead held
that the flow's own RTL is the pass condition and the reference run a
diagnostic; firmware-engineer and verification-lead required both. The chair
chose both. The must-fail control needs a known good RTL, and the scorer
already fails a test that does not pass on the reference (fact 9), so the
reference is in the verdict either way; stating it as a check is plainer
than calling it a diagnostic. Its fairness is not assumed: it rests on the
rule that a test accepts the whole range the fixed document allows, stated
to the seats in that document, and on the controls above, and no trial runs
until those controls are recorded. On the map: firmware-engineer asked that
the case's driver interface say the header is derived from the approved RTL.
Adopted in part: the wording
above does not contradict the skill card the seat is also given. On the
requirements stage: all four seats with a view took the fixed document as a
fair "request in"; design-architect's fallback is kept as the labelled
exception above.

Owners: design-architect (fixed documents, timer and RTL checks),
firmware-engineer (driver checks and controls), verification-lead (the
controls as a rule). First pull request: the case files, fixed documents and
fixtures.

### 3. The runner option and the fingerprint

- **A case-level field.** A whole flow is a property of the case (a field
  such as `flow: whole`), inside the case digest. It is not a harness variant:
  a variant may set only run options (fact 5), and a whole flow must still
  name a harness. It is not a command-line flag: a flag could run a
  single-seat case whose reference files encode upstream choices. The runner
  writes the label from the case; no operator types it.
- **Fingerprint.** The fingerprint's `run` section says the flow is whole, so
  a whole-flow trial has its own harness hash. The flow code lives in its own
  module, digested in a flow-only section that is present only for a
  whole-flow run, as the `loop` section is for tools in the loop. A test
  shows that an edit to the flow module changes the whole-flow fingerprint
  and leaves the default fingerprint unchanged. The dispatch into that module
  is one edit to `runner.py`, and is the one restart of every group
  (decision 4, "Code", says when it may merge). Until the flow module is
  merged, the dispatch refuses a whole-flow case with a plain message.
- **Intermediate stages.** Each is seated through the unchanged `run_task`,
  so its own before-review checks run for real. Review and approval are a
  pass-through by the harness, under its own actor name, not the fixture's.
  The note says the stage's output was not reviewed, and either names the
  gate runs that passed or says the stage has no check: "submitted, not
  checked". The words "reviewed in the repository" are never used for a
  model's output. A model reviewer is a later arm with its own label, not
  part of the first batch.
- **A failed intermediate stage.** The flow stops. Later stages are recorded
  as not run, the final checks as not run, and the trial is a failed trial
  that stays in its group's count. There is never a fallback to a reference
  document.
- **The record.** Per stage: task, stage, role, the actors that submitted,
  reviewed and approved, status, attempts, every gate run id, the skills given
  with their digests, the model, the model call counts, and every raw answer
  in order. Attestations are checked on every stage. The record names the
  repository commit. A test shows a whole-flow record re-judges clean.
- **The label and the list.** Its own label, not a purpose: `flow: whole`.
  The runner writes it in three places: the record's name, the manifest and
  every trial. Two of them are read: the manifest's label or the trial's
  label, either alone, takes a trial out of the levels. The name is for a
  reader and is never read by the levels code.
  A record that mixes whole-flow and single-seat trials is refused. The
  trials are listed under `whole_flow` in `capability/levels.json`. No trial
  runs under another label to be renamed later: that is a relabel, which the
  ruling of 2026-11-15 forbids.
- **The stop rule.** For a whole-flow run, the runner stops at the first
  trial whose last model call returned no model answer, judged by the trial's
  structure, shown by a test. The rule for single-seat runs is not changed by
  this record.

Who disagreed. On where the flow code sits: security and eda-tooling wanted
it in `CODE`, so that it can never sit outside the fingerprint; ai-engineer
wanted its own module in a flow-only section, so that a later flow fix does
not restart the groups of the first evidence batch. The chair chose the
flow-only section: every whole-flow trial still carries the digest of the
code that ran it, which is what security asked for, and a fix to flow code
does not make unrelated skill groups stale. On the reviewer: eda-tooling and
ai-engineer chose the pass-through; verification-lead allowed a model
reviewer if seated; security and qa-evidence required a true note and a
separate actor. The chair chose the pass-through: a second model seat adds
variance that one verdict cannot separate. On the label: qa-evidence showed
that the calibration purpose would keep the trials out of the levels today
but would need a later rename. All seats that spoke chose a separate label.

Owners: eda-tooling (runner, record, CI), ai-engineer (fingerprint),
verification-lead (label, list). First pull request: the label and the list,
which touch no file in `CODE`; then the runner option's two parts. All are
gate semantics or control plane, so the Founder Proxy reviews them.

### 4. Counts and timing

- **Counts.** Ten trials per case per arm; two arms, with documents and
  without; the named default harness only; one attempt. Two cases, so forty
  trials. The plan is committed before the first trial, with the arms
  interleaved, and is read once.
  Amended 2026-11-19 by the third addendum: "one attempt" is removed; the
  trials run with the attempts the named default harness sets.
  Amended 2026-11-19 by the fourth addendum: "read once" becomes one read
  per case; one plan still fixes all forty before the first trial.
- **Code.** No runner or harness code changes until the H3 batch's last trial
  is recorded (fact 15). The runner option is then in two parts. The first
  is the one dispatch edit to `runner.py`, with the fingerprint entries: it
  changes the default fingerprint, so it merges only inside the window,
  before the pull request that names the default harness. The second is the
  flow module, which is outside the default fingerprint (decision 3): it may
  merge in the window or later, as long as its test shows the default
  fingerprint unchanged. If the dispatch edit misses the window, it is not
  merged on its own after the read of wave 2's first live batch: fact 6
  covers only today's stale groups, and that edit would make the groups just
  read stale. It then waits for the next change that restarts every group
  for another reason and merges with it. From the pull request that names
  the default harness onward, no whole-flow pull request changes the default
  fingerprint.
- **Trials.** After the pull request that names the default harness (gate RT4
  of the retrospective). Never beside wave 2's first live batch: the two
  never interleave and never share a run window, because an interrupted trial
  stays a failed trial in either. The order is after that batch's last trial
  is recorded. If that batch is not ready to start when every gate below is
  met, the whole-flow batch may run first, whole, and the live batch starts
  only after its last trial is recorded. The committed plan says which.
- **Where.** Both cases run in one named CI job, on one CLI version and one
  tool set. The register block flow must (fact 13); the timer flow runs there
  too so that one harness group holds the batch. The job fails if the
  checkout changed after the run, and the record is re-judged from a fresh
  checkout before the read. Every record reaches the repository by a pull
  request, in plan order; none is held out. The weekly scheduled run never
  picks up a whole-flow case.
  Amended 2026-11-19 by the fourth addendum: "so that one harness group
  holds the batch" is struck; both cases still run only in the named job.
- **Before the first register block trial.** Whether a seat's compiled code
  can read the plan credential from the parent process in that job is tested
  and the result recorded (security; not tested today). If it can, the seat's
  code runs under another account or the batch waits.

Who disagreed. On order: verification-lead and product-lead proposed a
labelled side batch beside the live batch; ai-engineer preferred after it.
The chair chose never beside: no buyer is waiting (product-lead), the live
batch is evidence for levels and goes first, and a shared window puts both
counts at risk. On the timer: security allowed it on a local machine;
eda-tooling, verification-lead and ai-engineer wanted CI for both. The chair
chose CI for both.

Owners: verification-lead (plan, counts, read), eda-tooling (job),
security (conditions), ai-engineer (order against the default harness).
First pull request: the batch plan.

## Positions not adopted, and dissent

- design-architect, product-lead: the driver judged on the flow's own RTL
  only, the reference run a diagnostic. Not adopted (decision 2). Recorded as
  dissent.
- product-lead: a minimum of five trials before the measure is stated, and
  the name "whole-flow pass rate". Not adopted (decision 1).
- security, eda-tooling: the flow code inside `CODE`. Not adopted in the
  letter; its purpose is kept by the flow-only section and its test
  (decision 3).
- verification-lead, product-lead: the trials as a side batch beside wave 2's
  first live batch. Not adopted (decision 4).
- security: the timer flow may run locally. Not used (decision 4).
- firmware-engineer: the case's driver interface to say the map header is
  derived from the approved RTL. Adopted in part (decision 2).
- A model reviewer for intermediate stages, and a request that plans the
  `register-map` stage, are left for a later meeting or a later case.
- eda-tooling: whether the extended stop rule should also apply to
  single-seat runs with several attempts. Not decided here.

No seat dissented from keeping decision 6, from a case-level field, from the
pass-through with a true note, from a separate label, or from running the
trials only after the default harness is named.

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| WF1 | No file in `CODE` and no harness code changes before the H3 batch's last trial is recorded (H3 state not checked from the repository) | eda-tooling |
| WF2 | The `flow: whole` label, the `whole_flow` list, the refusal of mixed records and a test that such a trial never enters a skill group are merged before the first whole-flow trial; no trial runs under another label | verification-lead |
| WF3 | The fixed documents are committed before any trial; every held-out check and mutant cites a statement in them; the pull request that commits them changes no existing check | design-architect |
| WF4 | For each case the judge controls are committed with recorded CI runs before the first trial: the reference passes; a planted fault fails; a conforming RTL passes the checks on the flow's RTL; the range-accepting reference tests pass on both RTLs and a test written to one choice fails on the reference RTL. The fixed document states the whole-range rule to the seats | verification-lead |
| WF5 | The driver controls of decision 2 exist as fixtures and are shown failing in a recorded run, and the unmapped-write check is in the case's held-out test, before the first register block trial | firmware-engineer |
| WF14 | Added 2026-11-18 by the addendum, which also amends what WF4 and WF5 ask for on the driver side: the reach guard test and the recorded wait-probe control are merged, and `docs/WHOLE_FLOW.md` and the `driver-reference` text in `evals/flow/controls.json` are corrected, before the first register block trial | firmware-engineer |
| WF15 | Added 2026-11-18 by the second addendum: the strict fixture driver test and the strict fixture driver are committed and recorded as that addendum's decision 1 asks, on the build the trials will use, before the first register block trial. WF4 and WF5 are not met for the register block before this | firmware-engineer |
| WF16 | Added 2026-11-18 by the second addendum: the object screen of its decision 2 is merged and in force for every whole-flow check that links seat-written C, with its allow list, its refused fixtures and its probes of what it does not stop recorded, before the first register block trial | eda-tooling |
| WF17 | Added 2026-11-18 by the second addendum, which states what WF9 needs: the reach test in the named job, the other account unless every probe is denied, and the counting re-judge in a job that ran no seat code, before the first register block trial | security |
| WF18 | Added 2026-11-18 by the second addendum: the driver and its tests run in a process of their own with only the bus interface carried across, and the fixtures' expected results are recorded again, before any second register block batch and before any whole-flow figure leaves the repository's records | security |
| WF19 | Added 2026-11-18 by the second addendum: the texts of its decision 3 are true on `main` before the first register block trial, and the register block count is never stated without the residual of decision 2 | qa-evidence |
| WF6 | The dispatch edit to `runner.py` merges after WF1 is met and before the pull request that names the default harness, or else only with a later change that restarts every group for another reason; the flow module may merge later; the runner option carries the true pass-through note, the per-stage record and a clean re-judge test | eda-tooling |
| WF7 | A test shows the flow module's edit changes the whole-flow fingerprint and not the default; from the pull request that names the default harness onward, no whole-flow pull request changes the default fingerprint, shown by that test on each one | ai-engineer |
| WF8 | The stop rule of decision 3 is shown by a test before any whole-flow trial | qa-evidence |
| WF9 | Both cases run only in the named CI job, default harness, one attempt; the job fails on a changed checkout; the record is re-judged from a fresh checkout before the read; the credential test is recorded before the first register block trial. Amended 2026-11-19 by the third addendum: "one attempt" is removed, the default's attempts apply | security |
| WF10 | Forty trials, fixed in a committed plan before the first; never beside wave 2's first live batch; one read; no re-run counts. Amended 2026-11-19 by the fourth addendum: one read per case, after that case's last planned trial is recorded | verification-lead |
| WF11 | The count is stated only as k of n with its interval, per group, at ten or more planned trials complete; never pooled, never called a level; case (a) is never described as independent verification | qa-evidence |
| WF12 | No whole-flow figure or measure name on the site, the README or the landing brief from this record; a later one needs a committed record, key 1 review and the founder's answer on the name | product-lead |
| WF13 | The whole-flow job renames or skips no required check, adds no third-party action, pins actions by SHA, passes inputs through `env`, and the weekly scheduled run excludes whole-flow cases | eda-tooling |
| WF20 | Added 2026-11-19 by the third addendum, which also amends WF9 ("one attempt" is removed; the default's attempts apply): the committed plan states the attempts, both expected fingerprints, the main count and the derived count word for word, before the first trial | verification-lead |
| WF21 | Added 2026-11-19 by the third addendum: tests of the CI command (no attempts option, expected fingerprint required) and of a whole-flow stage's first-attempt prompt, and one line in `docs/HARNESS.md`, before the first trial | ai-engineer |
| WF22 | Added 2026-11-19 by the third addendum: a test of the stop rule on three attempts, with an unanswered call inside a stage, before the first trial | qa-evidence |
| WF23 | Added 2026-11-19 by the third addendum: what a failed run's log excerpt can carry back to a seat on a retry, stated from recorded reach tests, before the first trial of each case | security |
| WF24 | Added 2026-11-19 by the fourth addendum, which also amends WF10 (one read per case): one committed plan fixes both cases' counts and rules before the timer's first trial; a dated plan addition states the register block's values and every difference before its first trial | verification-lead |
| WF25 | Added 2026-11-19 by the fourth addendum: nothing that changes a batch's fingerprints, flow digests, case files or gate code merges between that case's first slot and its last planned trial; the `fw.test` change merges outside the timer's batch and shows the default fingerprint unchanged | ai-engineer |
| WF26 | Added 2026-11-19 by the fourth addendum: no combined figure and no comparison between the two cases; the timer's read says the register block case has not run; the register block's read names the card and document changes made after the timer's results were known | qa-evidence |

## Open, for the founder

1. This ruling, to confirm or overrule.
2. The public name of the measure, if it is ever to appear outside the
   repository's records. Inside them it is "whole-flow pass count".

## Addendum (2026-11-18): the fixture driver test of decision 2

This addendum amends one control of decision 2 and what gates WF4 and WF5 ask
for on the driver side, and adds gate WF14. It is a decision made on
2026-11-18. It changes no code, case, eval record or level, and nothing else
in the ruling.

### Who decided what

- Three seats gave round 1 positions independently (firmware-engineer,
  verification-lead, qa-evidence); the chair decided. The meeting was kept to
  the seats that own gate WF5, gate WF4 and the claims. Read against
  ip-nirmaan `main` at ae48843. Seats were read only; nothing was simulated
  for the meeting.
- Why a meeting. Pull request #324 (the judge controls) built no fixture
  driver test and said in `docs/WHOLE_FLOW.md` that none can exist. Key 2
  and the Founder Proxy (agent) each recorded on #324 that a control the
  council had decided was replaced without a recorded amendment. No earlier
  committed record holds a ruling that allows it, so the council rules now.
  `council/README.md` gives no shorter process for amending a record.
- As for the ruling: the council decided; it is not a founder decision, and
  the founder can overrule it. Nothing here is reserved for the founder.

### Facts checked

1. Decision 2's fourth judge control asks for a fixture driver test written
   to the conforming RTL's one choice that fails on the reference RTL. The
   one choice the register block's document leaves open is response latency,
   1 or 2 cycles (`evals/flow/axi4_lite/requirements.md`, lines 50 to 56).
   The reference RTL answers after 1, the conforming RTL
   `tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v` after 2.
2. The run. `evals/flow/controls_record.json` (CI run 44243160870 on
   fdc8e7c), control `driver-reference`: the reference driver and driver
   test pass on the reference RTL (6 checks, 45 cycles, 20 bus transfers) and
   on the conforming RTL (6 checks, 65 cycles, 20 bus transfers).
   `tests/test_whole_flow_controls.py`
   (`test_the_control_gets_the_verdict_it_expects`) requires the bus
   transfers the two runs log to be identical: offset, value, strobe and
   response. The record holds verdicts and summaries, not the transfers; the
   equality is shown by that test passing in the named run. Control
   `regs-tb-strict2`: the strict testbench fails check 3 on the reference
   RTL.
3. The run shows one test, the reference driver test, which is written to
   accept the whole range. It does not show that no driver test can see
   latency. That rests on reading the harness (facts 4 to 6), which no test
   guards today.
4. `src/nirmaan/integrations/firmware_harness/nirmaan_hal.h`: a driver test
   gets `read32` and `write32`. Each returns only after the response
   (`axil_manager.cpp`), with the data and the response code. The cycle
   count is internal to the harness and printed only in the run's summary
   line. The block has four plain registers and no state that depends on
   elapsed cycles (firmware-engineer, verification-lead; inference from the
   source).
5. The sentence in `docs/WHOLE_FLOW.md` that the HAL "has no clock or cycle
   count" is too wide for the harness as a whole. `nirmaan_irq.h`, on the
   same include path, gives `nirmaan_irq_wait(seen, cycles)`, which advances
   the clock, and the harness fails a run at 5000000 cycles
   (`axil_manager.cpp`, `kMaxCycles`). A test that spends cycles to just
   under that limit would pass on the reference RTL and fail on the
   conforming RTL (inference; not run). That is the opposite direction to
   the control: the reference RTL uses the fewest cycles the document
   allows, so no test can fail it for using more.
6. A driver test is host C linked into the harness process. A test could
   read the host clock, or (firmware-engineer, inference, not run) reach the
   harness's own output through the operating system. Neither is a test
   written to the HAL and the driver interface, and wall time is not
   latency. Not checked by any seat: whether a simulator symbol is reachable
   from a test's C.

### Decision

**The fixture driver test is not required for the register block; three
things are required in its place.** All three seats took this option; no
seat held that the fixture can be built as decision 2 words it.

The control's purpose is to show that checks 6 and 7 catch a driver test
stricter than the document. Through `read32`, `write32` and the driver
interface, on this block, no driver test can be strict about latency in the
direction that fails the reference RTL. This is shown by the harness's
construction and by the recorded run together, not by the run alone. The
control is therefore empty for this block, not merely hard to build.
(Withdrawn 2026-11-18 by the second addendum: a driver test's C can read a
cycle count through the simulator's runtime, so the control is not empty.)

Decision 2's fourth judge control now reads, for the driver side: the
reference driver test passes on both RTLs with identical bus transfers, in a
recorded run. The fixture testbench written to one choice stays as ruled.
The other driver controls of decision 2 (the wrong-map header, the two
mutants, the three fixture drivers) stay as ruled. In place of the fixture
driver test:

1. **A reach guard.** A test that needs no design tool pins what a driver
   test can reach under `fw.test`: the members of `nirmaan_hal` and the
   exported C functions of the host harness, as an exact listed set. Its
   failure message names this addendum and the return condition.
2. **A wait probe.** A fixture driver test that calls `nirmaan_irq_wait`
   between transfers is recorded passing on both RTLs with identical bus
   transfers. It is an expected pass, named as an attempt to see latency
   that does not.
3. **A return condition.** The fixture driver test of decision 2 is required
   again, before the next trial, for any case where the HAL or the harness
   gains a cycle count, a timeout or a non-blocking access that a driver
   test can read, or where the block has a register whose value depends on
   elapsed cycles, or where the fixed document leaves open a choice visible
   in data or response codes.

`docs/WHOLE_FLOW.md` ("Freedom left open" and the judge controls list) and
the `driver-reference` text in `evals/flow/controls.json` are corrected to
this scope: "through `read32` and `write32` on this block", shown by the
harness's construction and the run, with the cycle limit's direction stated.

Until gate WF14 is met, WF4 and WF5 are not met for the register block. This
addendum closes no gate. What WF4 still needs from the whole-flow runner
(the reference flow through every seated stage, a planted upstream fault,
and check 5) is unchanged.

Who disagreed. Not on the option. On what replaces the control:
verification-lead asked for the wait probe; qa-evidence asked for a committed
best-effort strict fixture using the wait and the cycle limit, recorded as
passing on both RTLs; firmware-engineer asked for neither. The chair took
the probe: it is one fixture that meets both requests, and it puts the one
clock a test can advance on the record. A fixture that runs to the cycle
limit is not required: it would fail the conforming RTL, which proves
nothing about checks 6 and 7, and it is a long run for no control. All three
asked for the guard and the return condition.

Owners: firmware-engineer (the guard, the probe, the corrected texts);
verification-lead (the control as a rule, gate WF4); qa-evidence checks the
corrected claims.

### Positions not adopted, and open

- qa-evidence: a strict fixture that uses the cycle limit. Not required, for
  the reason above.
- Open, for security: whether a driver test's host C should be screened or
  confined so that it cannot reach the harness's output or the host clock
  (fact 6). It is a question about the gate's integrity, not about this
  control, and it is not decided here.
- Open, for firmware-engineer: whether a simulator symbol is reachable from
  a test's C (fact 6). The reach guard's pull request answers it.
- Both open items are decided in the second addendum, below.

### Gate

| Gate | Condition | Owner seat |
|---|---|---|
| WF14 | The reach guard test and the recorded wait-probe control are merged, and `docs/WHOLE_FLOW.md` and the `driver-reference` text in `evals/flow/controls.json` are corrected, before the first register block trial | firmware-engineer |

## Second addendum (2026-11-18): what a driver test's host C can reach

This addendum answers the two items the first addendum left open, withdraws
one sentence of it, requires the fixture driver test of decision 2 again for
the register block, and adds gates WF15 to WF19. It is a decision made on
2026-11-18. It changes no code, case, eval record or level. Code it needs is
listed as gates.

### Who decided what

- Five seats gave round 1 positions independently (security,
  firmware-engineer, verification-lead, eda-tooling, qa-evidence); the chair
  decided. The meeting was kept to the seats that own gate WF9 and the open
  security item, gates WF5 and WF14, gate WF4, the build, and the claims.
  Read against ip-nirmaan `main` at 3595450 and the draft pull request #336
  (branch `g3-wf14`, head dfce3a9, not merged). Seats were read only; nothing
  was compiled or simulated for the meeting.
- Why a meeting. The pull request for gate WF14 answered the first addendum's
  open question for firmware-engineer: a simulator symbol is reachable from a
  test's C, and through it a cycle count. The first addendum's exemption
  rested on the opposite, unchecked.
- As for the ruling: the council decided; it is not a founder decision, and
  the founder can overrule it. No seat found anything reserved for the
  founder. The pull request that adds the screen of decision 2 changes what a
  gate refuses, so it is in a founder class and goes to the Founder Proxy
  (agent) by the usual rule.

### Facts checked

The chair checked each line below unless a seat is named as the source.

1. The build. Under `fw.test` each C file of the seat is compiled by the host
   `cc` with `-std=c11 -Wall -Wextra -Werror -pedantic`
   (`src/nirmaan/integrations/firmware.py:43`, `:277-295`), and one
   `verilator --cc --exe --build` step links the objects into one image with
   the manager and Verilator's runtime (`:513-537`). No step inspects the
   objects. `src/nirmaan/integrations/eda_guard.py` screens Verilog, Yosys,
   SBY, EQY and SDC input; it screens no C.
2. The channel. `tests/fixtures/fw/reach/simulator_clock_probe.c` on #336
   declares `Verilated::s_lastContextp` by its mangled name, finds the
   simulation time in the object it points to, and times one `read32` and one
   `write32`. It includes only the two harness headers and three C library
   headers. In CI run 44318772521 on dfce3a9, job 134851827249
   (`test (shard 1/3)`, concluded success), it printed: reference RTL,
   `read32 2 cycles, write32 2 cycles`; `axi4_lite_regs_lat2.v`,
   `read32 3 cycles, write32 3 cycles`. One job of that run had not finished
   when the chair read it, so the run had no conclusion. In run 44315985333
   on the earlier head 6771b56 the same test is a pass in the junit file of
   job 134842092762, with no timing line in the log. None of this is on
   `main` or in a committed record; a CI log expires.
3. The record on #336. `evals/flow/controls_record.json` there names run
   44315985333 and job 134842092511 for all 21 controls. That job failed,
   and in it the test of the new `driver-wait-probe` control failed on the
   record entry that did not yet exist (qa-evidence; the chair confirmed the
   job and its conclusion). The first addendum's standard is a test passing
   in the named run.
4. The image. The manager hands the test `{nullptr, bus_read, bus_write}`
   (`firmware_harness/axil_manager.cpp:240`); the cycle count, the pass and
   fail counts and the model pointer are file-local objects of the same image
   (`:46-50`). A test or a driver can therefore reach them, and the run's
   nonce, by address arithmetic from `hal->read32`, naming no symbol
   (security, firmware-engineer; inference, not run).
   `docs/GATE_INTEGRITY.md:144-150` states that residual and defers running
   test code out of process.
5. Whose code. In a register block trial the model writes the driver and the
   driver test (decision 2 (b)). Checks 5 and 6 link the judge's held-out
   test with the model's driver in one image; check 7 runs the model's driver
   and driver test. Check 7 is the only check that runs the seat's driver
   test. No recorded control fails check 7 on its clean run: the one control
   that fails check 7 fails by a surviving mutant (verification-lead).
6. The job. `.github/workflows/live-eval.yml` gives the plan token to the
   trials step (131 to 135); a gate's steps run with credential names removed
   from the environment, as the same user. The package is installed from the
   checkout in place (`.github/actions/live-eval-setup/action.yml:28`), and
   the re-judge step runs in the same job, on the same checkout, after the
   trials (142 to 146). The workflow holds no changed-checkout check and no
   fresh checkout, and the repository holds no credential test for this job
   (security). So gate WF9 is not met today.
7. The fingerprint. Neither `firmware.py` nor `firmware_harness/` is in
   `CODE`, `LOOP_CODE` or `FLOW_CODE` (`src/nirmaan/runtime/harness.py:251-287`).
   The default fingerprint digests every tool definition, so an edit to the
   `fw.test` definition in `src/nirmaan/company/tools.py` restarts every
   group (eda-tooling). A screen inside `firmware.py` restarts nothing and
   still changes what the gate does for the committed single-seat firmware
   case and for a re-judge of its records.
8. The SoC run. `fw.soc_test` builds freestanding firmware for a simulated
   CPU, which has no host reach, but any firmware can read
   `NIRMAAN_SOC_CYCLES` (`firmware_soc/nirmaan_soc.h:18`). The case's checks
   use host co-simulation.

### Decision 1: the return condition is met; the fixture is owed again

**By its words the condition is not met; by its purpose it is, and the
purpose governs.** Nothing was gained: the HAL and the harness are as they
were. But the control was dropped because it was held to be empty, and that
rested on what a test written to the HAL can see, with the simulator symbol
unchecked. A test's C reads a cycle count, and the count differs by RTL
(fact 2). So the control was never empty, and decision 2 requires it. The
four seats with a view all read it so; eda-tooling had none.

The first addendum's sentence "The control is therefore empty for this
block, not merely hard to build" is withdrawn. Its sentence about `read32`,
`write32` and the driver interface stands only as a statement about a test
that uses nothing else.

The return condition now reads: the fixture driver test of decision 2 is
required, before the next trial, for any case where a seat-written test can
read a cycle count, a timeout or a non-blocking access by any means in the
image or the machine it runs in, or where the block has a register whose
value depends on elapsed cycles, or where the fixed document leaves open a
choice visible in data or response codes. A case whose checks run on
`fw.soc_test` meets it by fact 8.

What is owed for the register block, before the first trial:

1. **A strict fixture driver test.** The reference driver test with one
   added, named check that times one `read32` and one `write32` and passes
   only at the counts the conforming RTL gives. It is a judge control,
   labelled in its file as reaching outside the HAL on purpose. With the
   reference driver it passes on `axi4_lite_regs_lat2.v`, and in check 7's
   own configuration it fails on the reference RTL: by a failed result of
   that one named check, with no build error, no harness error and no crash,
   and with the same bus transfers on both RTLs.
2. **A strict fixture driver.** Decision 2 names checks 3, 6 and 7 as the
   checks that catch strictness, and the driver is seat-written C in the
   same image. A fixture driver that is strict the same way is recorded
   passing check 5 on the conforming RTL and failing check 6 on the
   reference RTL.
3. **The control follows the channel.** On the build the trials will use,
   for each route by which a recorded probe reads a cycle count, either the
   route is recorded as refused or unreadable, or a strict fixture that uses
   that route is recorded failing as in 1 and 2. A fixture may and must use
   whatever route is open. When a route is closed, the same fixture files
   stay and their expected result changes to the refusal, in a recorded run.
   A screen of symbol names alone does not close the count unless a recorded
   probe of address arithmetic shows it unreadable.
4. The record is a committed one, from a CI run that concluded success, and
   it holds the cycle counts.

Who disagreed. On whether closing the channel ends the debt:
verification-lead held that only a record ends it and the fixtures are built
either way; security, firmware-engineer and qa-evidence held that a closed
channel, shown by a recorded run, leaves the control empty with the files
kept as must-refuse inputs. The chair took item 3, which is
verification-lead's rule stated per route: the fixtures are committed in
every case, and what they must do depends on what a recorded probe shows.
On the strict driver: only verification-lead asked for it; the chair took
it, because decision 2 names check 6.

Owners: firmware-engineer (the fixtures and their record, gate WF15);
verification-lead (the rule, gate WF4).

### Decision 2: screen now, by account now, a process of its own next

The rule this is weighed against: code a seat writes must not reach anything
the judge does not intend it to reach. Today it does not hold inside the
image (fact 4) or on the runner (fact 6), and the code is a model's. No
screen of C makes it hold: `docs/GATE_INPUTS.md`, section 4, says so, and
every seat that proposed a screen listed what it does not stop. So the
answer is both, in a fixed order, and each part is claimed only for what a
recorded must-fail fixture shows it stops.

**Before the first register block trial.**

1. **The account.** The test decision 4 asked for is run in the named job,
   through `fw.test`, with compiled C: can it read the environment of its
   parent or of any process it can see, run a command as another user
   without a password, or write to the checkout, the installed package or
   the records folder. The result is recorded. Unless every probe is denied,
   seat-written C is built and run as another account that can do none of
   these, with an empty environment; otherwise the batch waits. The re-judge
   that counts runs in a job that ran no seat code, on a fresh checkout,
   from the uploaded record, and the trial job fails on a changed checkout.
   This is what gate WF9 already asks; it is now stated (gate WF17).
2. **The object screen.** Between the compile steps and the link, the seat's
   objects are checked: every undefined symbol is on an allow list, however
   it was declared (an asm label, a weak reference, a mangled name); no
   defined global collides with a name of the harness or of the C library
   the harness reports through; no object carries code that runs before
   `main`. The seat's own lines of the preprocessed source carry no asm. A
   hit is a recorded failed check with its reason, with nothing run, decided
   here in advance; it is never a removed or repeated trial. The allow list
   is fixed from a recorded CI run that lists the undefined symbols of every
   committed fixture, reference answer and held-out test.
3. **What the screen is called.** A tripwire. It stops reach by name. It
   does not stop address arithmetic from an allowed pointer, a memory scan,
   what the allowed C library calls can do, or anything the account allows.
   The simulator clock probe and one fixture per construct the screen
   claims to refuse are recorded as refused, as a verdict distinct from a
   failed test. A probe of address arithmetic toward the cycle count is
   recorded with its real result, which decides decision 1, item 3.
4. **Where the screen sits** is the build pull request's choice, on two
   conditions. It is in force for every whole-flow check that builds or
   links seat-written C. If it sits in the shared `fw.build` and `fw.test`
   backends, that pull request shows by a recorded run that every committed
   fixture, reference answer and held-out test still gets the result it got,
   lists any committed firmware trial whose re-judge would change, and says
   in `docs/GATE_INTEGRITY.md` that the gate changed without a fingerprint
   change.
5. **When it may merge.** Gate WF1 is read by its purpose to cover
   `firmware.py` and `firmware_harness/`: no edit before the H3 batch's last
   trial is recorded, unless the orchestrator records that H3 has no
   `fw.test` case. No edit to the `fw.test` or `fw.build` tool definitions
   outside the window of gate WF6.
6. **The residual, stated.** `docs/GATE_INTEGRITY.md` and
   `docs/WHOLE_FLOW.md` say, before the first trial: in checks 5, 6 and 7
   model-written C shares the harness's process, and in 5 and 6 the judge's
   own test; from there it could reach the nonce and the counts and print a
   verdict (an inference from the sources, not run); the screen does not
   stop that. Every counted trial keeps its driver and driver test in its
   record. Before the read, security reads the seat C of every register
   block trial that passed, and any reach outside the HAL it finds is stated
   beside the count. That reading changes no trial's result: the count stays
   what the judge recorded.

**After the first batch.** Running the driver and its tests in a process of
their own, with only `read32`, `write32`, the wait, the two handler
callbacks and the test result carried across, is no longer left undated. It
is required before any second register block batch and before any whole-flow
figure leaves the repository's records (gate WF18). The handlers run before
an access returns and may make bus accesses of their own, so what carries
the calls across must allow that, and the interrupt and bus-error tests must
still fail on a broken design (firmware-engineer). When it merges, the
fixtures of decision 1 are recorded again with their new expected results.
It still leaves the model's driver and the judge's test in one client
process, and leaves the account as the only limit on files and system calls;
its texts say so.

Options not taken. Neither before the first trial: refused; security
objected and no seat proposed it. Hiding the runtime's symbols at the link:
it means leaving Verilator's own build step, stops no more than the allow
list, and fails as a link error where a recorded refusal is wanted
(eda-tooling). Moving the checks to the SoC run: a different case, and one
with a cycle count in reach (fact 8).

Who disagreed. On placement: security held that the screen can sit in the
whole-flow judge alone; eda-tooling placed it in `firmware.py` and warned
that the fingerprint would not show the change. The chair set the two
conditions of item 4 and left the choice to the pull request. No seat asked
for the separate process before the first trial. The chair records that the
rule is therefore knowingly not met inside the image for the first batch,
and that this is accepted only because the count credits no level, stays
inside the repository's records, and keeps every seat file readable.

Owners: security (the account, the reading, the conditions; gates WF17 and
WF18); eda-tooling (the screen and the job; gate WF16); firmware-engineer
(the HAL across a process boundary).

### Decision 3: the gates, #336, and the claims

Pull request #336 changes, then merges; it does not wait for the screen. It
changes eight files, none under `src/` or `.github/`, so gates WF1, WF6, WF7
and WF13 do not hold it (eda-tooling). Gate WF14 is met by it only when:

- `evals/flow/controls_record.json` is taken from a run in which every
  control's test passes, and names that run and job;
- the probe's cycle counts are in a committed record with head and job, and
  the reach test's text claims no more than it asserts;
- `docs/WHOLE_FLOW.md` no longer says the simulator channel is "not the
  fixture control" or that the guard "covers" it. The guard pins the files,
  declarations and build options it lists. It closes nothing, and it does
  not pin the simulator's version, which also decides the symbols
  (qa-evidence, inference);
- the texts cite this addendum and say the fixture driver test is owed.

Meeting gate WF14 closes neither WF4 nor WF5.

What the record and the documents may say, after a green run on the head
that merges: the guard pins what it lists; the wait probe passes on both
RTLs with the same bus transfers; a driver test's C reads the simulator's
time through `Verilated::s_lastContextp` and measures more cycles per call
on the conforming RTL, with the run and job named.

What they must not say: that no driver test can be strict about latency,
without the words "that uses only `read32`, `write32` and the driver
interface"; that the control is empty; that the return condition was not met
because nothing was gained; that the probe measures the document's latency
of 1 or 2 (it reports 2 and 3 per call); that a seat's C is screened or
confined, before the code and its must-fail fixtures are merged; that the
screen confines; anything about a model-written test using the channel
(none has run). `docs/WHOLE_FLOW.md` names gates WF1 to WF19.

Owner: qa-evidence (gate WF19); firmware-engineer makes the changes to
#336.

### Positions not adopted, and open

- security: the screen in the whole-flow judge only. Left to the pull
  request (decision 2, item 4).
- firmware-engineer, qa-evidence: a channel closed before the fixture is
  built leaves nothing owed. Adopted only per route, with the files
  committed either way (decision 1, item 3).
- Not adopted: a reading by security that changes a trial's result. The
  count stays the judge's; the finding is stated beside it.
- Open, for security: whether a fixture that prints a forged verdict by
  address arithmetic is committed to a public repository, or the path stays
  a stated inference until the separate process closes it. Security decides
  in the pull request for gate WF16.
- Open, for eda-tooling: whether the other account needs a change to
  `src/nirmaan/integrations/eda.py` or can be switched on from the workflow
  alone.

### Gates

Each is met before the first register block trial unless it says otherwise.
WF15, WF16 and WF18 do not hold the timer case, which links no seat-written
C; gate WF9 holds both cases as before.

| Gate | Condition | Owner seat |
|---|---|---|
| WF15 | The strict fixture driver test and the strict fixture driver are committed and recorded as decision 1 asks (items 1 to 4), on the build the trials will use. WF4 and WF5 are not met for the register block before this | firmware-engineer |
| WF16 | The object screen of decision 2 (items 2 to 5) is merged and in force for every whole-flow check that builds or links seat-written C: the allow list from a recorded run; the clock probe and one fixture per refused construct recorded as refused; the address-arithmetic probe recorded with its real result | eda-tooling |
| WF17 | Gate WF9, stated: the reach test of decision 2, item 1, is recorded from the named job; seat-written C runs as the other account unless every probe is denied; the counting re-judge runs in a job that ran no seat code, on a fresh checkout; the trial job fails on a changed checkout | security |
| WF18 | The driver and its tests run in a process of their own with only the HAL's calls carried across; the interrupt and bus-error tests still fail on a broken design; the fixtures of decision 1 are recorded again. Before any second register block batch and before any whole-flow figure leaves the repository's records | security |
| WF19 | The texts of decision 3 and the residual of decision 2, item 6, are true on `main`; #336 meets the four conditions of decision 3; the register block count is never stated without that residual; security's reading of the passed trials' seat C is done before the read | qa-evidence |

Code these gates need, for the build lane (this meeting wrote none): the
two strict fixtures, their controls and record (WF15); the object screen,
its allow list, its fixtures and probes, and the corrected
`docs/GATE_INTEGRITY.md` (WF16); the reach test, the other-account launch
and the separate re-judge job in the workflow (WF17); the out-of-process
harness (WF18); the changes to #336 and the document texts (WF14, WF19).

## Third addendum (2026-11-19): attempts under the default harness named by H3

This addendum amends two words of the ruling. Decision 4 and gate WF9 say
"the named default harness only; one attempt". Since ip#347 the default
harness gives three attempts, so the two can no longer both hold. The forty
trials run on the default harness as it is named, three attempts for each
seated stage, and "one attempt" is removed from decision 4 and gate WF9. One
derived count, fixed before the first trial, is read beside the main count
from the same records. It is a decision made on 2026-11-19. It changes no
code, case, eval record or level. Code it needs is listed as gates. No
whole-flow trial has run, and this addendum states no whole-flow result.

### Who decided what

- Three seats gave round 1 positions independently (verification-lead and
  ai-engineer, who own decision 4's counts and its order against the default
  harness, and qa-evidence for the claims); the chair decided. Read against
  ip-nirmaan `main` at e5844ff. Seats were read only; no trial, design tool
  or test ran for the meeting. The chair and two seats computed harness
  fingerprints with the repository's own function on a read-only copy.
- Why a meeting. The pull request that put the two cases on the CI job
  (ip#354) runs them on the default harness and passes no attempts option.
  Its check cites gate WF9 (`scripts/live_eval_ci.py:102-104`) while
  enforcing only the harness name, so the merged path already departs from
  WF9 as written. This addendum does not say ip#354 met WF9 as written.
- This is an amendment, not a reading. No committed text says what the
  record intended by "one attempt", and this addendum does not claim to
  know. Either choice drops one of the record's two clauses: three attempts
  drops "one attempt"; one attempt is, by `docs/HARNESS.md` ("any number but
  3 is another harness"), not "the named default harness only".
- As for the ruling: the council decided; it is not a founder decision, and
  the founder can overrule it. No seat found anything reserved for the
  founder.

### Facts checked

The chair checked each line below at e5844ff unless a seat is named.

1. The words. Decision 4, "Counts" (lines 400 to 403) and gate WF9 (line
   493) each name the default harness and one attempt as separate items.
   Decision 4, "Trials" (line 420 on) makes the trials wait for the pull
   request that names the default harness. The record's fact 5 notes that a
   variant may set `attempts`, and its dissent list leaves "single-seat runs
   with several attempts" undecided (line 469). The record says nothing on a
   named default with more than one attempt.
2. Then and now. At b5b7967, the commit the record was read against,
   `VARIANTS["default"]` was empty, so a default run gave a seat the case's
   attempts, one (qa-evidence, from `git show`). ip#347 merged on 2026-11-18
   (01adfe9): `VARIANTS["default"]` sets attempts 3
   (`src/nirmaan/runtime/harness.py:176-180`), with the repair text and an
   excerpt of the failed run's log after a refusal
   (`src/nirmaan/runtime/prompt.py:294-320`).
3. The flow runner gives the run's attempts to every seated stage
   (`src/nirmaan/evals/flow.py:159, 192`). The record keeps each stage's
   attempts used (`flow.py:216`) and every raw answer in order; the trial's
   `attempts` is the largest of its stages (`flow.py:239-241`). The held-out
   judge runs after the stage loop (`flow.py:226-229`), so no retry follows a
   held-out check (qa-evidence).
4. Fingerprints, whole flow, Claude Code 2.1.325, computed by the chair and
   recomputed by ai-engineer and qa-evidence. Default (three attempts): with
   documents
   `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc`,
   without
   `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975`.
   With `--attempts 1`: with documents
   `sha256:d6723621041af1fcb2f7166ff70ee6739cbec61852dd509cc5401cb7e9da1ca5`,
   without
   `sha256:7d5ea9b54caf09a2617b28e1ae6ae6b7e73943e376db6383cee14e0138b07fe6`.
   The single-seat default is
   `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`
   under either choice. These are today's values; the plan recomputes them on
   the commit the trials run.
5. Labels. An `--attempts 1` run keeps `harness_variant: default`
   (`src/nirmaan/evals/records.py:367-374`), so only its fingerprint would
   say it ran one attempt. Whole-flow trials group by case digest, model,
   harness fingerprint, CLI, flow digest and purpose
   (`src/nirmaan/evals/levels.py:201-232`), state a count only from ten
   trials (`WHOLE_FLOW_MIN`), and never count toward a level.
6. The CI path. `scripts/live_eval_ci.py:102-104` refuses a whole-flow case
   on any harness but `default` and any trial count but one; lines 172 and
   183 to 189 pass no attempts option; `.github/workflows/live-eval.yml` has
   no attempts input. Neither file is in `harness.CODE`.
7. The stop rule. `flow_stopped` reads the last recorded answer
   (`src/nirmaan/evals/records.py:210-216`). Its test builds trials by hand
   (`tests/test_whole_flow_runner.py:218-221`). What a model call with no
   answer does in the middle of a stage that has attempts left is read from
   the code by qa-evidence (declined, not retried), not shown by a test.
8. Prompts. That the default's first attempt is the old default's prompt,
   prompt for prompt, is tested for a single seat (`tests/test_harness.py`).
   No test shows it for a stage of a whole flow.
9. Not checked from the repository. The state of wave 2's first live batch is
   in private plans; only its fingerprint (fact 4, the single-seat default)
   is confirmed. The H3 figures in `docs/HARNESS.md` are that document's
   statement; the frontier records are private. `evals/results` holds no
   whole-flow record.

### Decision 1: the default harness as named; "one attempt" is removed

1. Decision 4, "Counts", now reads: ten trials per case per arm; two arms,
   with documents and without; the named default harness only, with the
   attempts that default sets, today three for each seated stage. Gate WF9
   now reads "default harness, with the default's attempts" where it said
   "default harness, one attempt". Nothing else in either changes: forty
   trials, one committed plan, arms interleaved, one read.
2. No whole-flow trial of the forty runs with an attempts option. The
   dispatch expects the whole-flow default fingerprints (fact 4, recomputed
   on the trials' commit and CLI pin).
3. No split. Twenty trials on each attempts setting would leave five per
   case per arm, under the ten at which decision 1 of the ruling allows a
   count. All three seats opposed a split.
4. The measured run. Decision 10 of the retrospective asks a wave with long
   tool runs to measure one real run first. One whole-flow run of the timer
   case, purpose calibration, on the same fingerprint, is that run. It is
   outside the forty, groups apart by its purpose, never counts, and is not
   stated as a result. It runs after the plan of gate WF10 is committed and
   after wave 2's first live batch is read.

Why. The record made the trials wait for the named default and on it only;
that harness is what the product now runs and what wave 2's per-skill
evidence runs on, so a stage's seat in a whole flow has the settings, code
and attempts of the seat in that evidence, and the flow is the one thing
that differs. On one attempt two things would differ, no per-skill evidence
would exist on that setting, and the CI path would need an option that makes
the trials another harness. The three-attempt record also holds what a
one-attempt run would have needed at each stage (decision 2); a one-attempt
record cannot be read the other way. No trial has run, so this changes no
rule between a run and its read (ruling of 2026-11-15).

What it costs, stated plainly. A trial may now make more model calls and run
longer, so it is more exposed to an interruption, and an interrupted trial
stays a failed trial of its group (decision 11). The main count measures
completion with up to two repairs per stage after a machine refusal, not a
first answer. H3's evidence for the default is weak by its own account
(`docs/HARNESS.md`), and it measured single seats only.

### Decision 2: one derived count, fixed before the first trial

1. Definition. For each group, j of n: the trials that passed and in which
   every stage records one attempt. n is the group's planned count, the same
   n as the main count k of n. It is read from each stage's recorded
   attempts, at the same single read, and the read lists each stage's
   attempts for every trial.
2. Its name in the repository's records: "passed with every stage on its
   first attempt". It is a description of trials on the default
   fingerprint.
3. It is reported only if the committed plan (gate WF10) holds this
   definition word for word before the first trial. It changes no main
   figure, makes no group, arm or second read, and never enters a level.

### Decision 3: what may and may not be claimed

May be claimed: that this addendum amends decision 4 and gate WF9; the
fingerprints of fact 4 as computed; the two counts as defined, per group.

Never claimed, here or in the plan, the records or the read:

- what the record "meant" by one attempt;
- that the derived count is a result on a one-attempt harness: no trial on
  that fingerprint exists. Unless the test of gate WF21 shows the two
  first-attempt prompts the same, no sentence says such a trial took the
  path a one-attempt trial takes;
- a comparison of either count with the single-seat trials of the record's
  fact 14 (one attempt, the old default, fixed upstream stages, stale
  groups), or with wave 2's per-skill evidence as the same measure. The
  counts are never pooled and never a level (gate WF11);
- that retries help a whole flow: k against j at ten is no test of that; nor
  any per-stage rate pooled across cases or arms;
- H3's frontier figures as a committed record;
- any time, usage or cost figure;
- that forty trials can run today. The register block flow stays refused
  until its own gates are met.

### Positions not adopted, and open

No seat dissented from the ruling: all three chose the default harness as
named, with one derived count fixed in advance, and all three called it an
amendment. Differences, and how the chair chose:

- verification-lead read "named default" as the governing clause and "one
  attempt" as a description of the default of its day. qa-evidence held that
  no committed text supports any statement of intent. The chair sided with
  qa-evidence: the addendum amends and claims no intent.
- The wording of the derived count: "no stage refused" (qa-evidence), trial
  attempts equal to one (ai-engineer), every stage on its first attempt
  (verification-lead). The chair defined it by the recorded field (every
  stage records one attempt), which is the same set under all three.
- verification-lead: no timer trial before the register block flow can run,
  unless "one read" is amended per case. Not decided here: it is outside
  this meeting's question. Decision 4's one read of forty stands, and
  starting or reading the timer's twenty alone needs its own ruling before
  the plan is committed. Recorded as verification-lead's standing
  condition.
- Open, for security (not seated at this meeting): on a retry, an excerpt of
  the failed run's log returns to the seat, which one attempt did not do.
  For the register block that log comes from seat-written C, which today
  runs as the runner's account (`evals/flow/credential_test_record.json`).
  Gate WF23 puts the question to its owner.

### Gates

Each is met before the first whole-flow trial unless it says otherwise.

| Gate | Condition | Owner seat |
|---|---|---|
| WF9 (amended) | As before, with "default harness, with the default's attempts" for "default harness, one attempt" | security |
| WF20 | The committed plan of gate WF10 states: the default harness and its attempts for each seated stage; both expected fingerprints, recomputed on the trials' commit and CLI pin; the main count; the derived count of decision 2 word for word, and that it changes no main figure; the measured run of decision 1, item 4. A derived count not in the plan before the first trial is never reported | verification-lead |
| WF21 | Tests show that the whole-flow CI command carries no attempts option and that a whole-flow dispatch with no expected fingerprint is refused; a test shows whether a whole-flow stage's first-attempt prompt is the same on one attempt and on three, and the texts follow its result (decision 3); `docs/HARNESS.md` says the default gives each seated stage of a whole flow three attempts. None touches a file in `harness.CODE` | ai-engineer |
| WF22 | With gate WF8: a test on three attempts in which a stage's second model call returns no answer shows what the runner does and that the stop rule fires. If it shows a trial can pass with an unanswered call inside it, that returns to the council before the first trial | qa-evidence |
| WF23 | Security states, from recorded reach tests, what a failed run's log excerpt can carry back to a seat on a retry: for the timer flow before the first trial; for the register block flow with gates WF17 to WF19, before its first trial | security |

Code these gates need, for the build lane (this meeting wrote none): the
tests of WF21 and WF22 and the one line in `docs/HARNESS.md`. No attempts option is added anywhere. If the test of
WF21 finds that a whole-flow dispatch can run with no expected fingerprint
(not checked by this meeting), that refusal is added to
`scripts/live_eval_ci.py`, which is outside `harness.CODE`. No harness file
changes, so no fingerprint changes. The plan of WF20 is a document.

## Fourth addendum (2026-11-19): one read per case

This addendum amends "read once" in decision 4 and "one read" in gate WF10.
The forty trials stay forty, ten per case per arm, fixed in one committed
plan before the first trial of either case. Each case is now read once, by
itself, after its own last planned trial is recorded, so the timer's twenty
may run and be read before the register block flow can start. It adds gates
WF24 to WF26. It is a decision made on 2026-11-19. It changes no code, case,
eval record or level. No whole-flow trial has run, and this addendum states
no whole-flow result.

### Who decided what

- Three seats gave round 1 positions independently (verification-lead, who
  owns the plan, the counts and the read; qa-evidence for the claims;
  ai-engineer for the harness, the fingerprint and the order); the chair
  decided. Read against ip-nirmaan `main` at e5844ff and the third addendum.
  Seats were read only; no trial, design tool or test ran for the meeting.
  qa-evidence did not read the third addendum's text, so what it said on the
  derived count was conditional; the chair read it.
- Why a meeting. The third addendum recorded verification-lead's standing
  condition, that no timer trial starts before the register block flow can
  run unless "one read" is amended per case, and said that starting or
  reading the timer's twenty alone needs its own ruling before the plan is
  committed. This is that ruling.
- This is an amendment, not a reading. The record as written is one plan of
  forty, read once. All three seats called their answer an amendment.
- Security was not seated. No seat found a reach question on the timer path
  beyond gate WF23, which is already security's, and which stands.
- As for the ruling: the council decided; it is not a founder decision, and
  the founder can overrule it. No seat found anything reserved for the
  founder.

### Facts checked

The chair checked each line below at e5844ff unless a seat is named.

1. The words. Decision 4, "Counts": "The plan is committed before the first
   trial, with the arms interleaved, and is read once." Gate WF10: "Forty
   trials, fixed in a committed plan before the first; never beside wave 2's
   first live batch; one read; no re-run counts". Decision 1, "Counting":
   "one read". Decision 4, "Where": the timer flow runs in the named job
   "so that one harness group holds the batch". The sources are decision 11
   of the retrospective
   (`council/records/2026-11-14-pilot-retrospective.md:326-328`: uniform,
   fixed in a committed plan before the first trial, read once) and the
   ruling of 2026-11-15 (no rule changes between a run and its read).
2. Groups. Whole-flow trials group by case, case digest, model, harness
   fingerprint, CLI, flow digest and purpose
   (`src/nirmaan/evals/levels.py:212-213`), and a count is written only from
   ten trials (`WHOLE_FLOW_MIN`, `levels.py:82`, `226-230`). Decision 1
   forbids pooling across cases or arms. So under any option there are four
   groups of ten and no figure for forty or for twenty. Nothing in the code
   holds the plan or a read: a group's count is written to the generated
   list when its tenth record is there (qa-evidence).
3. Nothing is blind. Every record reaches `main` by a pull request, in plan
   order, and none is held out (decision 4, "Where"). So each trial's
   verdict is public when its record merges. With one read of forty the
   timer's slots 1 to 20 would be as visible before slots 21 to 40 as they
   are under this addendum (verification-lead, inference).
4. What can run. `scripts/live_eval_ci.py:115-127` (`seat_c_problem`)
   refuses the register block case, exit 6, and returns nothing for the
   timer case, which links no seat-written C.
   `evals/flow/credential_test_record.json` (run 44401041085, taken on the
   branch of ip#354, in the `replay` job) records every probe not denied
   for seat C under `fw.test`. The register block flow waits for `fw.test`
   to run seat C as the seat account, for the credential test to show every
   probe denied, and for gates WF15 to WF19. Neither case can start today:
   wave 2's first live batch is not read, both requirements documents are
   listed in `evals/flow/requirements_check_pending.json` (gate WF3), and
   no plan is committed (gate WF10).
5. What the fingerprint holds (ai-engineer; the chair read the lists). The
   default fingerprint digests the twelve files of `harness.CODE`
   (`src/nirmaan/runtime/harness.py:280-293`) and each tool definition's
   fields, not the bytes of `tools.py`; a whole-flow fingerprint adds
   `run.flow` and the digest of `FLOW_CODE`, `nirmaan/evals/flow.py`
   (`harness.py:271`). It holds the knowledge flag, never a card's or a
   document's text. `src/nirmaan/integrations/eda.py`,
   `src/nirmaan/integrations/firmware.py`, `scripts/live_eval_seat.py`,
   `scripts/live_eval_ci.py` and the workflow are outside it. The timer's
   seat account was added with no harness edit
   (`scripts/live_eval_seat.py:9`). So the `fw.test` change may show in no
   fingerprint (inference: its files are eda-tooling's to choose), and two
   trials with equal fingerprints need not have run the same gate code.
6. What a card or document change moves. The skill digest covers the card
   and the document (`src/nirmaan/evals/cases.py:78-90`), and the flow
   digest covers every seated stage's skills
   (`src/nirmaan/evals/flow.py:146-149`). A card change moves both arms'
   flow digests, a document change the with-documents arm's only. The flow
   digest is in the group key (fact 2), so such a change inside a group's
   ten trials splits the group under ten, and no count can then be stated
   (ai-engineer).
7. The overlap. Field `exercised` of `evals/flow/axil_timer.json` and
   `evals/flow/axi4_lite_regs_driver.json`: the three specification stages
   are given the same skills in both cases; rtl-implementation is given
   `axi`, `fsm_design` and `rtl_design` in the timer and `axi` and
   `rtl_design` in the register block, which adds firmware with
   `device_drivers`. Five skills are shared (verification-lead,
   qa-evidence; the chair read both files).
8. Not checked from the repository. The state of wave 2's first live batch,
   and the build plan that orders the forty as timer slots 1 to 20 and
   register block slots 21 to 40, are private.

### Decision 1: one plan of forty, one read per case

1. Decision 4, "Counts", now ends: the plan is committed before the first
   trial of either case, with the arms interleaved within each case, and
   each case is read once, after its last planned trial is recorded. Gate
   WF10 now reads: forty trials, ten per case per arm, fixed in one
   committed plan before the first trial of either case; never beside wave
   2's first live batch; one read per case; no re-run counts. "One read" in
   decision 1, "Counting", means one read of each case. Where gate WF9, gate
   WF19 and the third addendum say "the read", they mean the read of the
   case concerned.
2. Decision 4, "Where": the words "so that one harness group holds the
   batch" are struck. Both cases still run only in the one named CI job.
   The two cases may now carry different dates, commits, flow digests and
   gate code, and the plan states each (decision 2).
3. The timer's twenty are slots 1 to 20 and may start when the timer's own
   gates are met. This addendum lifts none of them: the read of wave 2's
   first live batch, gates WF3, WF4, WF8, WF9 and WF17 for the timer, WF10
   as amended, and what the third addendum requires before the first trial,
   its measured run included. The register block's twenty are slots 21 to
   40 and start when its gates are met.
4. No split by arm, and no other split. Each read is of two complete groups
   of ten.
5. verification-lead's standing condition is met by its second half: "one
   read" is amended per case. The seat withdrew the first half.

Why. A single read of forty protects no number, because no figure may span
the two cases (fact 2), and it hides nothing, because every record is public
as it merges (fact 3). What "read once" protects is that a count is fixed
before any outcome is known and that no rule changes between a run and its
read. Both are kept, for each case, by fixing both cases' counts and rules
in one plan before the timer's first trial (decision 2). No trial has run,
so this changes no rule between a run and its read. Waiting would hold a
case whose gates can be met behind a case whose remaining code has no date,
and would leave no whole-flow evidence at all if the register block flow
never becomes runnable.

What it costs, stated plainly. The two cases are no longer one batch on one
harness state. They are two measurements, taken at different times, and
nothing may be said that treats them as one (decision 4). The register
block's batch is planned and run by people and agents who know the timer's
results; decision 2 limits what that knowledge can touch, and the register
block's read says so.

### Decision 2: what is fixed before the timer's first trial, and what may change

1. **Fixed for both cases, in the one committed plan, before slot 1.** Ten
   trials per arm; two arms; the interleave and the slot order within each
   case; the default harness with its attempts; one trial per dispatch; the
   main count and the third addendum's derived count, word for word; the
   stop rule; that an interrupted or unjudged trial is a failed trial; no
   re-run, no top-up, no early stop, no extension. None of these changes
   for the register block after the timer's slot 1, except by a council
   ruling that records that the timer's results were known.
2. **The plan addition.** The values that cannot be computed until the
   register block flow can run are not guessed. A dated addition to the
   same plan, committed before slot 21, states for the register block: the
   commit; the case digest; both expected fingerprints and both expected
   flow digests, recomputed on that commit and CLI pin; the digests of the
   gate code outside the fingerprint (fact 5); and, line by line, every one
   of these that differs from the timer's, with the pull request that
   caused it. The plan states the same values for the timer before slot 1.
3. **What may change for the register block between the two batches.** Only
   what a gate that exists today requires: its case files and controls
   (gates WF3, WF15, WF16), `fw.test` as the seat account and the
   credential test (WF17), the texts of WF19, and what WF23 finds. Its
   held-out checks, mutants and scorers change only as those gates
   require. Any other change to the case or its judge after the timer's
   slot 1 returns to the council.
4. **The freeze inside a batch.** From a case's first slot until its last
   planned trial is recorded, nothing merges that changes a file in
   `harness.CODE` or `FLOW_CODE`, a tool definition, the CLI pin, that
   case's files, the card or document of a skill that case exercises, or
   the gate code outside the fingerprint that the case's checks run
   (`src/nirmaan/integrations/`, the seat account script,
   `scripts/live_eval_ci.py`, the workflow). A slot is dispatched only on
   the digests the plan states. The `fw.test` change therefore merges
   before the timer's slot 1 or after the timer's last trial is recorded.
5. **The `fw.test` change and the fingerprint.** Decision 4, "Code",
   already rules that no whole-flow pull request changes the default
   fingerprint after the default harness is named. That pull request shows
   it by the test of gate WF7. If it cannot be built without a file in
   `harness.CODE` or a tool definition, it returns to the council before it
   merges.
6. **The curriculum.** The failure-to-curriculum rule (decision 1,
   "Failures"; retrospective, decision 7) applies to the timer's failed
   trials labelled "model" as written. It is not suspended until the
   register block's read. A change it produces merges only outside a
   batch's freeze (item 4): after the timer's last trial is recorded and
   before the register block's slot 21, or after slot 40. Every change,
   from any cause, to the card or document of a skill given to a register
   block stage between the timer's slot 1 and slot 21 is listed in the
   plan addition with its pull request and the skill digest before and
   after. The register block's read says that those cards or documents
   were changed after the timer's results were known, and names the pull
   requests.

### Decision 3: if the register block flow never runs

The timer's read stands alone. Slots 21 to 40 are then "not run": they are
never failed trials, no count is stated for them, and the plan is not
closed by counting them. No date is set by which the register block must
start. Until its read exists, every statement of a timer count carries the
sentence "the register block case has not run".

### Decision 4: what may and may not be said

May be said, after the timer's read: for each of its two groups, the
whole-flow pass count as decision 1 of the ruling words it, k of 10 with
its interval, with the case, case digest, model, harness fingerprint, CLI,
flow digest and arm; the third addendum's derived count for the same
groups, from the same records, at that read; that the register block case
has not run. After the register block's read: the same for its two groups,
always with the residual of the second addendum (decision 2, item 6), only
after security's reading of the passed trials' seat C (gate WF19), and with
the sentence of decision 2, item 6 above where it applies.

Never said, in a plan, a record, a read or any other text:

- a combined figure: none for forty, none for a case across its two arms,
  none across the two reads; and no percentage without its n;
- "the whole-flow batch", "the whole-flow result" or "the whole flow" for
  the timer's twenty alone. They are "the timer case's twenty trials";
- a comparison between the two cases, in either direction. They differ in
  case, date, flow digest and possibly gate code;
- that the two cases ran on the same harness because their fingerprints are
  equal (fact 5). The plan's digests are what may be cited;
- that a later register block count shows the effect of a curriculum
  change, or that documents help beyond the two arm counts stated side by
  side with their intervals;
- a timer count in any text before the timer's read. The generated list in
  `capability/levels.json` writes a group's count when its tenth record
  merges (fact 2); that is not the read, and nothing cites it before the
  read;
- a count for slots that did not run, or those slots as failed trials;
- anything the ruling and its addenda already forbid: a level, a score or a
  bar, a per-stage skill rate, case (a) as independent verification (gate
  WF11), any figure outside the repository's records (gates WF12 and
  WF18), any time, usage or cost figure.

### Positions not adopted, and open

No seat chose to wait, and no seat dissented from one read per case. All
three asked that both cases' counts and rules be fixed before the timer's
first trial. Differences, and how the chair chose:

- The plan. qa-evidence and verification-lead asked for one plan of forty
  holding both cases' design; ai-engineer asked for two plans, because the
  register block's fingerprints cannot be computed on a commit that does
  not exist yet. The chair took one plan with a dated addition (decision
  2, items 1 and 2): the design is fixed once, and no value is guessed.
- The curriculum. qa-evidence's first position was that nothing which
  alters a skill or document given to a register block stage merges before
  the register block's read, with a stated plan amendment as the fallback.
  verification-lead and ai-engineer applied the rule as written, with each
  change listed. The chair took the rule as written with qa-evidence's
  fallback made the requirement (decision 2, item 6): the register block
  has no date, the measure credits no level, and holding the product's
  curriculum for an undated case costs more than a stated difference
  between two counts that are never compared. qa-evidence's first position
  is recorded as dissent on this item.
- One read after slot 40 with the timer run early. Named in the brief as
  an option. Not taken: qa-evidence showed the generated list would hold
  counts the council called unread, and if the register block never ran
  the timer's records would be merged and never read.
- ai-engineer: one pinned commit for each batch. Adopted as pinned digests
  (decision 2, item 4), because every record merges to `main` during the
  batch, so the commit moves while the listed files do not.
- Open, for eda-tooling: which files the `fw.test` seat account change
  touches (second addendum, same open item). Decision 2, item 5 says what
  follows from the answer.
- Open, for security (not seated): to confirm, in the plan's pull request,
  that the timer path raises no reach question beyond gate WF23.

### Gates

Each is met before the timer's first trial unless it says otherwise.

| Gate | Condition | Owner seat |
|---|---|---|
| WF10 (amended) | Forty trials, ten per case per arm, fixed in one committed plan before the first trial of either case; never beside wave 2's first live batch; one read per case, after that case's last planned trial is recorded; no re-run counts | verification-lead |
| WF24 | The committed plan states this amendment, the items of decision 2, item 1 for both cases, and the timer's values of decision 2, item 2. The plan addition for the register block (decision 2, items 2 and 6) is committed before slot 21. A change to a fixed item after slot 1 is made only by a council ruling | verification-lead |
| WF25 | The freeze of decision 2, item 4 holds for each batch, and each slot is dispatched only on the digests its plan states; the `fw.test` change merges outside the timer's batch and its pull request shows the default fingerprint unchanged by the test of gate WF7, or it returns to the council | ai-engineer |
| WF26 | Every statement of a whole-flow count follows decision 4: the timer's read carries "the register block case has not run" until that case is read; the register block's read names the changes of decision 2, item 6; no combined figure and no comparison between the cases anywhere | qa-evidence |

Code these gates need, for the build lane (this meeting wrote none): none
is required. The plan and its addition are documents. If the build lane
wants the pinned digests of decision 2, item 4 checked by the dispatch
script, that check goes in `scripts/live_eval_ci.py`, outside
`harness.CODE`, and merges before the timer's slot 1.

## Note (2026-11-19): read with the seat C record

`council/records/2026-11-19-seat-c-live-refusal.md` rules on the live
refusal of cases that run seat C. For this record it confirms a reading of
gate WF17 (its decision 3), adds conditions before the first register block
trial and one line to gate WF18 (its decision 2 and gate SC9), and requires
the compile of seat C to be closed before any such trial (its decision 4).
It changes nothing else here.

## Note (2026-11-22): read with the EDA tools record

`council/records/2026-11-22-eda-tools-seat-account.md` rules on the second
reach question security raised on the timer path under the fourth addendum's
open item (the plan's section 14): the tools that read seat-written Verilog
run as the seat account before the timer's slot 1, and the input screen is
repaired, under its gates ET1 to ET8; gate ET9 returns the register block
flow's Verilator model builds to security before slot 21. It changes nothing
else here.
