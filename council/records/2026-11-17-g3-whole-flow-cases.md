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

## Fifth addendum (2026-11-23): a trial whose flow stops before its last stage

This addendum settles, before the timer's slot 1, which group a whole-flow
trial belongs to when its flow stops before its last stage, what is checked
on such a trial's record, and whether the measured run of the plan's
section 10 stands. It amends "The group key" in decision 1 and adds gates
WF27 to WF30. It is a decision made on 2026-11-23.

Ruling, in short:

- **Decision 3 rules.** A trial whose intermediate stage does not complete
  "is a failed trial that stays in its group's count". The code that reads
  the records does not do that today: it keys a group on the trial's own
  flow digest, and a stopped trial's digest covers only the stages it
  seated. The read's code is changed, before slot 1, so that a stopped
  trial is counted in its arm's group (decision F2; gate WF27).
- **The flow code, the records and the fingerprints do not change.** No
  file in `harness.CODE` or `FLOW_CODE` is touched, a trial's recorded flow
  digest is never rewritten, and no pinned value of the plan moves.
- **The plan states each stage's values.** A dated addition gives, for each
  arm, every stage's skills and skill digests and the digest over the first
  n stages, and the check made on a slot's record is stated there, stage by
  stage, no weaker than the comparison of the whole digest (decision F3;
  gates WF28 and WF29).
- **The measured run stands** as the run of the plan's section 10 and as
  the run gate ET10 reads. No second run is owed (decision F1).

It changes no code, case, eval record, level, fingerprint or digest by
itself. It makes one stated exception to a rule another record set:
decision F1, item 5 narrows decision C of the EDA tools record's addendum,
which gate ET13 holds, for the sentences named there and no others. It
loosens no other gate. No trial ran and no workflow was dispatched for the
meeting.

### Who decided what

The council decided every item below. The orchestrator called the meeting
because the plan (`evals/plans/2026-11-22-g3-whole-flow.md`, section 1)
leaves a change to a fixed item to a council ruling, and the group rule is
this record's. It is not a founder decision, and the founder can overrule
it. No seat found anything reserved for the founder in it: it adds no
spending, contract, counsel, sending, public name or licence term. The pull
request that changes `src/nirmaan/evals/levels.py` is in a founder class by
path (gate semantics, `.github/review-teams.yml`) and goes to the Founder
Proxy (agent) by the usual rule.

Four seats gave round 1 positions independently, each as its own read-only
process that saw no other answer to the brief: verification-lead (the plan,
the counts, the group rule and the read), ai-engineer (the harness and the
fingerprint), qa-evidence (the claims) and eda-tooling (the runner, the
record and CI). The chair decided. Security was not seated: no seat found a
reach or gate question in the brief, and the chain of gate ET10
(`council/records/2026-11-22-eda-tools-seat-account.md`) stays security's
as written. The seats read ip-nirmaan `main` at bbcf06a9 and the trial
record of run 45196235508 as the run's `live-eval` and `rejudge` jobs
uploaded it. That record is not committed at the time of this meeting. The
seats had no shell. The chair recomputed the digests below on bbcf06a9 with
the repository's own functions on a read-only checkout; no design tool ran.

A key is an agent review. Nothing here is a person's approval, a release,
or a claim that a design is ready to be made in silicon.

### Facts checked

The chair checked each line at bbcf06a9 unless a seat is named.

1. The words. Decision 1, "The group key": "Case digest, model, harness
   fingerprint, CLI and flow digest. The flow digest is a hash over the
   sorted list of (stage, skill, skill digest) for every skill each seated
   stage was given, as it was given in that arm." Decision 3, "A failed
   intermediate stage": "The flow stops. Later stages are recorded as not
   run, the final checks as not run, and the trial is a failed trial that
   stays in its group's count." For a trial that stops early the two
   cannot both hold as the code reads them (qa-evidence, eda-tooling).
2. The flow code follows decision 1 to the letter. `run_flow` adds a
   stage's skills to the digest's input only when it seats that stage
   (`src/nirmaan/evals/flow.py:187-189`); a stage after a stop is recorded
   "not run" with no skills (`flow.py:178-181`); the trial's digest is over
   what was given (`flow.py:255`, the function at `flow.py:146-149`). So a
   stopped trial's flow digest covers the stages up to and including the
   one that did not complete.
3. The read's code keys on that digest. `_whole_flow_groups`
   (`src/nirmaan/evals/levels.py:201-232`) groups by case, case digest,
   model, harness fingerprint, CLI, the trial's `flow_digest` and purpose
   (`levels.py:212-213`), and writes a count only from ten trials
   (`WHOLE_FLOW_MIN`, `levels.py:82`). So a stopped trial forms a group of
   its own, its arm's group stays under ten, and no count is written for
   the arm. Membership would depend on how far a trial got, and the trials
   left out would all be failed ones (verification-lead, inference).
4. The measured run. Run 45196235508 was dispatched from `main` at
   bbcf06a9 with purpose `calibration`, with documents. Its trial record
   carries the plan's case digest, the plan's with-documents whole-flow
   fingerprint (`sha256:d90b3c18...`) and the plan's CLI pin; both jobs
   ended with success, and the trial file the `rejudge` job uploaded
   equals the one the `live-eval` job uploaded, field by field. Its flow
   stopped before its last stage: three of its four stages were seated
   and the last is recorded "not run". The stop is the one decision 3
   describes, an intermediate stage that did not complete. It is not the stop rule of gate WF8: that rule
   (`flow_stopped`, `src/nirmaan/evals/records.py:213-217`) reads a last
   answer with no text and an error, and it is false for this record.
5. The digests. The record's flow digest is
   `sha256:4ff378d26fdeb8f6daab2aaebfbe8395e44ec663e0ad7f7d7eaf1a155b971315`.
   The plan's with-documents flow digest (section 23.1) is
   `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312`.
   Recomputed on bbcf06a9 with the steps `run_flow` takes to assemble each
   stage's skills, without running a stage: the timer with documents gives
   the plan's value over four stages and the record's value over the first
   three, and each of the record's three seated stages records the same
   skills and skill digests. No pinned value differs.
6. A digest over the first stages does not name an arm or a case. In the
   same recomputation the digests over the first one and the first two
   stages are equal in the timer's two arms, and the digests over the first
   three stages of the register block equal the timer's in each arm. The
   harness fingerprint differs by arm and the case digest by case.
7. What is in a fingerprint or a pinned group. `harness.CODE` is twelve
   files (`src/nirmaan/runtime/harness.py:280-293`) and `FLOW_CODE` is
   `nirmaan/evals/flow.py` (`harness.py:271`). `src/nirmaan/evals/levels.py`,
   `src/nirmaan/evals/records.py` and `src/nirmaan/models/evaluation.py`
   are in neither, and in none of the seven groups of the plan's section
   23.1 (ai-engineer; the chair read the lists). A change to `flow.py`
   moves both whole-flow fingerprints, on one of which the measured run
   ran.
8. What a record holds. Each seated stage records its skills and their
   digests (`EvalStage.skills`, `src/nirmaan/models/evaluation.py:251-252`),
   so a record can be checked stage by stage. The plan states the two
   whole-flow digests and no per-stage value.
9. The check that stopped. The script that dispatches the slots is outside
   the repository. Its operator reports that it compares a record's flow
   digest with the plan's whole-flow value and stopped on the measured
   run's record for that reason. `scripts/live_eval_ci.py` holds no flow
   digest check (eda-tooling). The plan's section 8 names "record mismatch"
   among the job-level stops and says that a record that exists "is a trial
   and is committed as it is".
10. Tests today. `tests/test_capability_levels.py:502-506` shows two flow
    digests as two groups. No test states the group of a stopped trial.
11. The plan's words. Section 18.1 says the flow digests are computed "as a
    replay computes them before any stage runs". The code assembles a
    stage's skills when it seats the stage (fact 2), so those words fit
    only a flow that runs to its last stage (qa-evidence).

### Decisions

#### F1. The measured run stands

1. Run 45196235508 is the measured run of the plan's section 10 and the
   run gate ET10 is read on. It ran on the commit, case digest, fingerprint
   and CLI the plan states. Its reach records are the ones gate ET10 is
   read on; that chain is committed and read as the EDA tools record
   already rules, and this addendum does not state that gate met. Decision
   A3 of that record reads "one run" as one run that passed its gates, and
   no seat found a gate of this run that failed.
2. No second measured run is owed. The difference between the record's
   flow digest and the plan's is fully explained by fact 5 and no pinned
   value moved, so it is not a mismatch between what ran and what the plan
   states. A second run made because this one stopped early would be a run
   chosen by its outcome (verification-lead).
3. What the run measured is less than a flow that seats every stage. The
   plan's dated addition (decision F3) says, in these words and no more,
   that the measured run's flow stopped before its last stage, that its
   flow digest covers the stages it seated, and that what it measured of a
   record's size is therefore a lower bound; the plan's rule for a record
   over the review's size limit (its section 20.2) stands.
4. The record of the measured run is treated as the plan and the EDA tools
   record already rule; this addendum changes nothing about where or
   whether it is committed. It belongs to no group of the forty and is
   never counted.
5. An exception to decision C of the EDA tools record's addendum, which
   forbids stating "anything of its trial's outcome, stages or attempts".
   It has two parts, and neither reaches further.
   - The plan's dated addition and the pull requests that carry it may
     state the two things of item 3: that the flow stopped before its
     last stage, and that its flow digest covers the stages it seated.
   - This addendum alone also states, in its facts 4 and 5 and nowhere
     else, how many of the run's stages were seated, that the stop is the
     one decision 3 describes and not the stop rule of gate WF8, and the
     record's flow digest beside the plan's. The ruling rests on these and
     cannot be checked without them. No other text repeats them; a text
     that needs them cites this addendum.
   Nothing else of the run's stages is stated anywhere, here included:
   not which stage, not why the flow stopped, not what a stage answered,
   no attempt count. Decision C stands in every other respect, and
   qa-evidence's read under gate ET13 is made against it as narrowed here.
   (Corrected 2026-11-23 by the chair, after the meeting, on the review
   of the pull request that carried this addendum. As first merged, the
   item allowed "the two things of item 3" to this addendum too, while
   facts 4 and 5 already stated the further facts named above. The
   correction makes the item say what the addendum states; it adds no
   statement about the run. No seat was asked again, and eda-tooling's
   dissent below, that no text should say anything of the run's stages,
   stands against the item as corrected.)
6. How the private script's row for the run is marked is its operator's,
   under this decision: the run stands, and it is not a job-level stop to
   be dispatched again.

All four seats held that the run stands. Owner: verification-lead (the plan's
words); security keeps gate ET10; qa-evidence reads the texts (gate ET13).

#### F2. A stopped trial is counted in its arm's group

1. **The reading.** Where decision 1's group key and decision 3 differ for
   a trial that stops early, decision 3 rules: the trial is a failed trial
   of the group its flow belongs to. "The group key" in decision 1 now
   ends: a trial whose flow stops before its last stage is placed by the
   stages it seated (fifth addendum, decision F2), and its own flow digest
   is listed with it.
2. **Where the fix is.** In the code that reads the records,
   `_whole_flow_groups` in `src/nirmaan/evals/levels.py`, and nowhere
   else. `flow.py` is not changed: the record keeps saying what each
   seated stage was given, and a stage that was not seated was given
   nothing. A record's flow digest is never rewritten or added to.
3. **The rule.** Within one set of case, case digest, model, harness
   fingerprint, CLI and purpose:
   - Trials are placed in the order of how many stages they seated, most
     first.
   - A trial fits a group when its stage names and their order equal the
     group's and every stage the trial seated records exactly the skills
     and skill digests the group holds for that stage. A group holds the
     stage values of the first trial placed in it.
   - A trial that fits no group starts one. A trial that fits one group
     joins it. A trial that fits more than one is listed apart as
     unplaced, with the groups it fits named; none of those groups is
     given a count, and the question returns to the council.
   For trials that seat every stage this is today's grouping by flow
   digest, and a test shows it. A group in which no trial seated every
   stage is still a group, and its count is written from ten trials like
   any other.
4. **Counting.** A stopped trial is a failed trial: no judge ran on it,
   and the existing rule already counts a trial no judge ran on as failed.
   The minimum of ten, the Wilson interval and the rule against pooling
   are unchanged.
5. **The listing.** Each trial keeps its recorded `flow_digest` and gains
   the stage at which the flow stopped, empty for a flow that reached its
   last stage. A group shows the flow digest of the first trial placed in
   it and whether that digest covers every stage. Where no trial of a
   group seated every stage, the read cites the plan's whole-flow digest
   for the arm from the plan's addition (decision F3).
6. **At the read.** The read lists each stopped trial with the stage at
   which it stopped. As decision 1, "Failures", already rules, a cause is
   stated as fact only where that stage's own gate refused, and no
   per-stage figure is stated as a skill rate.
7. **When it merges.** Before the timer's slot 1. The rule that reads a
   batch is never changed between a run and its read (ruling of
   2026-11-15), so this is not left for later. No whole-flow trial that
   counts has run.

Who disagreed, and how the chair chose. No seat chose to leave the list as
it is and count by hand at the read: the generated list would then never
write the arm's count, and the read would rest on a step no test holds.
No seat chose to change `flow.py`: it would move both whole-flow
fingerprints, leave the measured run on a superseded fingerprint, reopen
what gates ET5 and ET10 state on the pinned values, and make a record claim
skills for a stage that was never seated. On the rule itself the seats
differed. ai-engineer proposed to group by the six other fields alone and
to write a count only where every trial's seated stages agree: a trial can
then never fit two groups. verification-lead and eda-tooling proposed to
place a stopped trial by its seated stages among groups keyed as today.
The chair took the second: complete trials stay keyed by flow digest, as
decision 1 and the existing test have it, and two complete flows on
different cards are never listed as one group. From ai-engineer's position
the chair took that the rule must work when no trial of an arm seats every
stage. For a trial that fits two groups, verification-lead asked that
neither group be given a count and eda-tooling that it return to the
council; the chair took both. Under the freeze of the fourth addendum
(decision 2, item 4) this cannot arise inside a batch unless a card or a
document changed, which the dispatch check stops.

Owner: verification-lead (the rule and the list); ai-engineer confirms that
the change moves no fingerprint and no pinned value; qa-evidence reads the
tests.

#### F3. The plan's per-stage values, and the check on a slot's record

1. **The values.** A dated addition to the plan, merged before slot 1,
   states for each arm of the timer: the stage names in order; each
   stage's skills and their digests; and the digest over the first n
   stages for every n, the last of which is the whole-flow digest of
   section 23.1. They are computed on `main` by the steps `run_flow` takes
   to assemble each stage's skills, and the addition names the command.
   The check of the plan's section 7 before each dispatch covers them.
2. **The words.** The same addition corrects section 18.1's sentence of
   fact 11 and carries the words of decision F1, item 3.
3. **The check on a slot's record.** Every comparison made today stays:
   case, purpose, arm, flow label, harness variant, case digest,
   fingerprint, CLI. In place of the one comparison of the flow digest
   with the whole-flow value:
   - the record's stage names and order equal the plan's;
   - the seated stages come first and every later stage is "not run",
     with no skills, attempts, model calls or gate runs; where a stage is
     "not run", every stage before the last seated one is completed and
     the last seated one is not;
   - each seated stage's skills and digests equal the plan's for the arm,
     exactly;
   - the record's flow digest equals the digest recomputed from its own
     seated stages by the definition (`flow.py:146-149`), and equals the
     plan's digest over that number of stages.
   For a flow that seats every stage this is the comparison made today
   and more. For a stopped flow it checks every skill that was given; the
   stages not seated were given nothing, and their values are pinned at
   dispatch by section 7.
4. **What a stop is.** A record that passes item 3 with a stage "not run"
   is a failed trial of its slot. It is not a record mismatch and does not
   stop the batch. The stop rule of gate WF8 and the other stops of the
   plan's section 8 are unchanged, and a record that fails item 3 stops
   the batch as today.
5. **The script.** The dispatching script is outside the repository, so
   the plan's addition states item 3 in words that a reader can check, and
   the script's operator shows, before slot 1, that the script accepts the
   measured run's record under item 3 and refuses a copy of it with a
   stage's skill digest changed, with a stage's skills removed, with a
   seated stage after a "not run" one, and with the flow digest changed.

All four seats asked for the per-stage values and for this check; they
differed only in wording. Owner: verification-lead (the plan's addition);
eda-tooling (the script's check); qa-evidence reads the addition.

#### F4. The other batches

1. **The re-measure batch** (`evals/plans/2026-11-23-w2-remeasure.md`) is
   single-seat. A single-seat trial has no stages and no flow digest, and
   the change of decision F2 is inside `_whole_flow_groups`. No effect; a
   test shows that the change leaves `capability/levels.json` as it is.
2. **The register block.** Decisions F2 and F3 apply to slots 21 to 40 as
   written. The plan addition the fourth addendum requires before slot 21
   also states, for each arm, the five stages' values and the digest over
   the first n stages. The first three stages' values equal the timer's
   (fact 6); the case digest keeps the two cases apart, and a test shows
   that a stopped trial of one case never joins a group of the other.

#### F5. What may and may not be said

May be said, at a case's read: that a trial's flow stopped before its last
stage and at which stage; that it is a failed trial of its group; its own
flow digest beside the group's.

Never said, adding to decision 4 of the fourth addendum: a count from which
stopped trials are left out, or a second count "of the flows that reached
the last stage"; a stopped trial's digest as a group or an arm of its own;
that a stage "fails" at some rate; a cause for a stop beyond what decision
1, "Failures", allows; anything of the measured run beyond decision F1,
items 3 and 5.

Owner: qa-evidence.

### Positions not adopted, and open

- eda-tooling held that the measured run meets the plan's section 10 only
  in part, because it gives a lower bound on a record's size, and that no
  text should say anything of its stages. The chair ruled that it stands
  and that the plan says the lower bound in so many words (decision F1,
  items 3 and 5). Recorded as dissent on the wording.
- ai-engineer's grouping by six fields alone: not taken, for the reason
  given under decision F2.
- A new field in the record that states the whole flow's digest, written
  by code outside `flow.py`: named in the brief, chosen by no seat. It
  would state in a record what the plan already pins.
- Open, for verification-lead: qa-evidence raised, as an inference from the
  measured run's record, a question about why its flow stopped. Under
  decision F1, item 5 this record states nothing of it. It is in the
  internal minutes. If it leads to a proposal that changes a file in
  `harness.CODE` or `FLOW_CODE`, a tool definition, a card or a document
  before slot 1, the pinned values move and the fourth addendum and the
  EDA tools record say what is then owed; such a proposal returns to the
  council.
- Not checked from the repository: the dispatching script and its row for
  the measured run are private (fact 9).

### Gates

Each is met before the timer's slot 1.

| Gate | Condition | Owner seat |
|---|---|---|
| WF27 | `_whole_flow_groups` places a trial whose flow stopped early by the rule of decision F2, item 3, and lists it as item 5 says; tests show the cases of the build specification below; no file in `harness.CODE` or `FLOW_CODE` changes and no value of the plan's section 23.1 moves | verification-lead |
| WF28 | The plan's dated addition states the timer's per-stage values and the digests over the first n stages for both arms, the check of decision F3, item 3, the corrected sentence of section 18.1 and the words of decision F1, item 3; a test shows the stated values give the stated digests | verification-lead |
| WF29 | The dispatching script checks a slot's record as decision F3, items 3 and 4 say, shown as item 5 says, before slot 1 | eda-tooling |
| WF30 | Every statement about a stopped trial follows decision F5, and every statement about the measured run follows decision F1, items 3 and 5 | qa-evidence |

### Build specification, for the build lane

This meeting wrote no code and no plan text.

1. `src/nirmaan/evals/levels.py`, `_whole_flow_groups` only (gate WF27).
   Tests, in `tests/test_capability_levels.py`, that fail on bbcf06a9 and
   pass on the change:
   - nine trials that seat every stage and one stopped at an intermediate
     stage, same arm: one group, n of ten, the stopped trial failed and
     listed with its own digest and its stopping stage;
   - ten stopped trials whose seated stages agree: one group of ten with
     a count;
   - a stopped trial whose seated stage records a different skill digest
     stays apart from the group;
   - a trial stopped at the first or the second stage joins the group of
     its own fingerprint and never the other arm's, although the digests
     over those stages are equal;
   - a stopped trial of another case, with equal values on the stages it
     seated, never joins;
   - a stopped trial that fits two groups is listed unplaced and neither
     group has a count;
   - two flow digests of complete trials are still two groups, and
     `capability/levels.json` is unchanged by the change.
2. The plan's dated addition (gate WF28), documents only, with a test that
   reads the addition's table and rebuilds every stated digest with
   `flow_digest`.
3. The dispatching script's check (gate WF29), outside the repository.
4. Nothing in `flow.py`, `records.py`, the record format, a case, a card,
   a document or the workflow.

### Open, for the founder

Nothing.

## Sixth addendum (2026-11-23): what a later stage is told of the pass-through

This addendum takes up the item the fifth addendum left open for
verification-lead, before the timer's slot 1 and before any proposal
existed: whether what the whole-flow pass-through shows the seat of a later
stage is a defect of the harness. It amends the note of decision 3,
"Intermediate stages", amends decision F1 of the fifth addendum, and adds
gates WF31 to WF35. It is a decision made on 2026-11-23.

Ruling, in short:

- **It is a defect of the harness, in how the pass-through is shown, not
  in the note's truth.** A later stage's seat is shown the earlier stage's
  output as `approved` beside a record that reads "Independent review by"
  a named role and then "not reviewed", marked substantiated, and nothing
  says the harness made that record by the evaluation's rule. The separate
  actor that decision 3 asked for never reaches a seat (decision P1).
- **The note's words change, in `flow.py` only, before slot 1.** The note
  says of itself that no reviewer judged the stage and that the harness
  recorded the review and approval by the evaluation's rule. It gives a
  seat no instruction. No file in `harness.CODE`, no card, document, case
  file, engine or constitution text changes (decision P2; gate WF31).
- **Both whole-flow fingerprints move, and what rests on them is made
  again.** A dated plan addition restates them; gate ET5 is open again by
  its own words; a second measured run is owed on the new fingerprint, by
  the answer of gate ET10's owner. Run 45196235508 is no longer the run of
  the plan's section 10 for slot 1 (decision P3; gates WF32 and WF33).
- **A trial that stops because a seat escalated at a stage with no check
  is never labelled "model"** and feeds no curriculum change; its cause is
  an inference and is worded as decision P4 says (gate WF34).

It changes no code, case, eval record, plan text, level, fingerprint or
digest by itself. It loosens no gate. No trial ran and no workflow was
dispatched for the meeting.

### Who decided what

The council decided every item below. The orchestrator called the meeting
because the fifth addendum says that a proposal that changes a file in
`harness.CODE` or `FLOW_CODE`, a tool definition, a card or a document
before slot 1 "returns to the council". It is not a founder decision, and
the founder can overrule it. No seat found anything reserved for the
founder in it: it adds no spending, contract, counsel, sending, public name
or licence term. The pull request that changes `src/nirmaan/evals/flow.py`
is in a founder class by path (`.github/review-teams.yml`) and goes to the
Founder Proxy (agent) by the usual rule.

Five seats gave round 1 positions independently, each as its own read-only
process that saw no other answer to the brief: verification-lead (the plan,
the counts, the read and the failure label), ai-engineer (the harness and
the fingerprint), qa-evidence (the claims), eda-tooling (the runner, the
record and CI) and design-architect (what a careful architect does with
such an input). The chair decided. After round 1 the chair asked security,
as the owner of gate ET10
(`council/records/2026-11-22-eda-tools-seat-account.md`), for owner facts on
that gate only; security gave no position on the agenda. The seats read
ip-nirmaan `main` at 24278dce, whose `src/`, `evals/`, `knowledge/` and
`tests/` equal those of bbcf06a9. The seats had no shell. The chair ran a
replay of the timer's reference answer, with no model, on a read-only
checkout and read the prompt each stage is sent; no design tool ran beyond
that replay's own checks.

The seats also read the uploaded record of the measured run
(run 45196235508) and the prompts rebuilt from it. Under decision C of the
EDA tools record's addendum, as the fifth addendum's decision F1, item 5
narrows it, this addendum states nothing of that run's stages, answers or
attempts, and nothing of why its flow stopped. What the seats found there
is in the internal minutes. Every fact below is a fact of the code or of a
replay with no model, and the ruling can be checked from them alone.

A key is an agent review. Nothing here is a person's approval, a release,
or a claim that a design is ready to be made in silicon.

### Facts checked

The chair checked each line at 24278dce unless a seat is named.

1. The pass-through. After a stage reaches review, the harness reviews it
   with an approve verdict and approves it, as the stage's reviewer role
   and approver role, under the actor name `eval-flow-passthrough`, with
   one of two notes (`src/nirmaan/evals/flow.py:48-49`, `198-208`):
   "Whole-flow evaluation: not reviewed. Before-review checks passed:
   {runs}." or "Whole-flow evaluation: not reviewed. This stage has no
   before-review check: submitted, not checked." These are decision 3's
   words.
2. How the engine stores it. A review that approves becomes an evidence
   record whose description is "Independent review by" the actor's role, a
   colon, and the note, marked substantiated
   (`src/nirmaan/work/engine.py:432-437`). The actor's name is stored in
   another field of that record (`engine.py:436`), and the view a prompt is
   built from does not carry that field
   (`src/nirmaan/runtime/context.py:317-322`; qa-evidence). So the
   separate actor of decision 3 is in the record and never in a prompt.
3. What the next seat is sent. Each upstream output is rendered as
   `Upstream artifact ... (<kind>, approved)`
   (`src/nirmaan/runtime/prompt.py:259`) and listed for citation as
   `(approved)` (`prompt.py:139-141`). The review is rendered as
   `Evidence ... review_record, substantiated: Independent review by
   <role>: Whole-flow evaluation: not reviewed. ...`
   (`prompt.py:265-268`). The replay of the timer's reference answer shows
   these lines in the prompt of the second, third and fourth stage, in both
   arms; the fourth stage is sent two such records.
4. What else the same prompt says. The constitution, with "P6 Independent
   review: Critical work requires independent review; nobody approves their
   own work." and "P7 Conflicts escalate: Conflicting outputs require
   escalation before approval." (`prompt.py:87-90`,
   `src/nirmaan/company/governance.py:123-126`). The system prompt: "Never
   claim that a tool ran, or that anything was verified or approved" and
   "If the evidence does not support a conclusion, escalate instead of
   guessing." (`src/nirmaan/runtime/harness.py:92-106`). Nothing in a
   stage's prompt says what "Whole-flow evaluation" is or who made the
   approval.
5. What an escalation does. A seat that escalates leaves its task in a
   status that is not a reviewed one (`src/nirmaan/evals/runner.py:61`);
   the flow stops (`flow.py:199`, `223-224`) and, by decision 3, the trial
   is a failed trial of its group. The three specification stages have no
   check, so by decision 1, "Failures", a cause placed there is an
   inference.
6. The single-seat comparison. There the upstream stages are fixed by the
   fixture, whose review note gives its reason: "Evaluation fixture:
   <files>, as reviewed in the repository, not here."
   (`src/nirmaan/evals/runner.py:163-165`).
7. What a change moves. `flow.py` is `FLOW_CODE`
   (`src/nirmaan/runtime/harness.py:271`): an edit moves both whole-flow
   fingerprints and neither single-seat default (the test of gate WF7,
   `tests/test_whole_flow_dispatch.py`). The flow digests cover skills
   only (`flow.py:146-149`) and do not move; `flow.py` is in none of the
   seven groups of the plan's section 23.1. `prompt.py`, `context.py` and
   `evals/runner.py` are `harness.CODE` (`harness.py:280-293`): an edit
   moves the single-seat defaults, on which every single-seat group and
   the re-measure batch rest. A card or a knowledge document moves its
   skill's digest; a case file moves the case digest.
8. Text outside every fingerprint. `src/nirmaan/work/engine.py` (the words
   "Independent review by") and `src/nirmaan/company/governance.py` (the
   constitution) are in neither list and in no pinned group, and their
   text reaches every seat's prompt, single-seat included. An edit there
   would change prompts with no fingerprint moving (ai-engineer,
   qa-evidence, eda-tooling).
9. What holds the note today. `tests/test_whole_flow_runner.py:85-86`
   asks that every stage's note starts "Whole-flow evaluation: not
   reviewed." and line 92 that a stage with no check carries
   `NOTE_UNCHECKED`; `docs/whole_flow/09-runner-flow-module.md` quotes
   both notes. No committed record under `evals/` quotes them.
10. What rests on the whole-flow fingerprints. The plan's section 7: a
    slot is dispatched only on the stated values, and "a difference stops
    the dispatch until a plan amendment pull request is merged". Decision
    E4, item 4 of the EDA tools record: verification-lead's statement of
    gate ET5 "holds only while the values of the plan's tables on the
    commit the measured run is dispatched from equal those on the run's
    commit". Gate ET10: the measured run's reach records, with "the values
    of the plan's section 18.1 on that commit equal to those on slot 1's
    commit"; section 18.1 and the tables that replace it list both
    whole-flow fingerprints. The fifth addendum's decision F1, item 2
    ruled no second measured run owed because "no pinned value moved". The
    freeze of `FLOW_CODE` (fourth addendum, decision 2, item 4) starts at
    slot 1, and no slot has run.
11. Security, as owner of gate ET10, on a change to the note's words
    alone: the gate cannot be met on run 45196235508 as it is worded, and
    a run on the new commit is owed, which is a second measured run unless
    the gate is reworded; the reach of the tools as the seat account does
    not depend on the note (the note is written by the harness's own actor
    after a stage has run, and neither the reach test nor the seat account
    script reads `flow.py`), so there is no reach reason for or against
    the change; gates ET11, ET15, ET17, WF17 and WF23 do not depend on a
    fingerprint value.

### Decisions

#### P1. It is a defect of the harness

1. What a later stage's seat is shown contradicts itself, and the harness
   wrote every part of the contradiction: the label `approved`, the words
   "Independent review by" a role in which nobody reviewed anything, the
   mark "substantiated", and "not reviewed" in the same line (facts 1 to
   3). The note is true. The line it is set in is not, and decision 3's
   own safeguard, the separate actor, is not shown (fact 2).
2. The same prompt tells the seat that conflicting outputs are escalated
   and that it escalates where the evidence does not support a conclusion
   (fact 4). A seat that stops on this input follows the rules it is
   given. Decision 3 chose the pass-through over a model reviewer because
   "a second model seat adds variance that one verdict cannot separate";
   as it is shown, the pass-through adds a cause of its own that a count
   cannot separate from the seats' work either (verification-lead,
   inference).
3. This is so at every later stage of every trial, in both arms and in
   both cases (fact 3). It is a fact of the code and does not rest on any
   run. How often a seat would stop on it is not known and this addendum
   states no rate.
4. What is not the harness's: what an earlier seat writes in its own file
   about the state of its own work. That is the seat's text. No ruling
   here touches it.

Four seats held this (verification-lead, ai-engineer, qa-evidence,
design-architect). eda-tooling held that the note is true and that a
seat's choice on it is behaviour to measure, "with one confound the
harness itself adds", the line of fact 2. Owner of the finding:
ai-engineer.

#### P2. The note's words change, in `flow.py` only, before slot 1

1. **Before slot 1.** After slot 1 the flow code is frozen, and a trial is
   never run again. Twenty trials, then twenty more, would each put the
   line of P1 to three or four seats, and a read could then claim only a
   count "under the note as shown". The cost of the change now is what
   decision P3 lists, and none of it is a counted trial.
2. **Where.** The two note constants of `src/nirmaan/evals/flow.py`, and
   that module's own description of them. Nothing else:
   - not `prompt.py`, `context.py` or `evals/runner.py`: the single-seat
     defaults must stay (fact 7);
   - not `engine.py` or `governance.py`: a change to what seats are sent
     with no fingerprint moving is a hidden harness change (fact 8);
   - not a card, a knowledge document or the system prompt: each moves
     digests the finding gives no reason to move, and tells every seat
     something;
   - not a case file: a customer's document does not speak for the
     evaluation.
3. **The words.** Each note keeps its first sentence and its last, and
   gains one sentence between them:
   - "Whole-flow evaluation: not reviewed. No reviewer judged this stage:
     the evaluation harness recorded this review and approval itself, by
     the evaluation's rule, so that later stages receive it as input;
     'approved' here records that rule, not a judgement. Before-review
     checks passed: {runs}."
   - "Whole-flow evaluation: not reviewed. No reviewer judged this stage:
     the evaluation harness recorded this review and approval itself, by
     the evaluation's rule, so that later stages receive it as input;
     'approved' here records that rule, not a judgement. This stage has no
     before-review check: submitted, not checked."
   The added sentence is qa-evidence's, taken as written. Every seat that
   chose a change offered a sentence of this kind.
4. **What the note does not say.** It gives a seat no instruction: not to
   proceed, not that there is no conflict, not what to assume. It states
   who made the record and by what rule, which is what a seat in an
   organization would be told of a stage passed on without review.
   Whether a seat then proceeds or escalates stays the seat's, and stays
   measured.
5. **Decision 3, amended.** "Intermediate stages" now reads, after "The
   note says the stage's output was not reviewed": "says that no reviewer
   judged it and that the harness recorded the review and approval by the
   evaluation's rule (sixth addendum, decision P2)". The rest stands: a
   true note, the separate actor, and the words "reviewed in the
   repository" never used for a model's output.
6. **What is left, and said.** The words "Independent review by" and the
   mark "substantiated" still stand before the note, because they are the
   engine's and the prompt's (fact 2), and those are not changed. The note
   now answers them in the same line. An earlier seat's own words about
   its own work are untouched (P1, item 4). A seat may still stop on what
   it is shown; decision P4 says how such a trial is worded.

Who disagreed. eda-tooling chose no change to code before slot 1: a dated
plan addition that states what the seats are shown and a replay test of
those lines, for the reasons that every other course moves a pinned value
and reopens gates ET5 and ET10, that the changed note does not remove what
an earlier seat writes in its own file, and that one run is not a rate.
The chair did not take it: the line is the harness's own, it is put to
every later stage of forty trials that cannot be run again, and what it
costs to change is owed once, before any counted trial. eda-tooling's
condition for the case that the note changes, that it does not tell a seat
to proceed, is adopted (item 4). Recorded as dissent.

On the words. ai-engineer asked for a last sentence, "The next stage works
from it as it is."; design-architect for "Later stages proceed on it as an
unreviewed input and state what they assume of it."; verification-lead for
"The approval and this record are not a conflict between outputs; a
conflict in the files' content is still yours to raise." None is taken:
each tells a seat what to do or how to read its own rules, which
qa-evidence and eda-tooling refused, and the count would then measure the
instruction. ai-engineer's and design-architect's point, that a seat in an
organization is told when work is passed on at risk, is met by the
sentence adopted, which says so as a fact.

Owners: eda-tooling (the change and its tests); ai-engineer (the
fingerprints, gate WF7); qa-evidence reads the texts.

#### P3. What is owed because both whole-flow fingerprints move

1. **The plan.** A dated addition restates both whole-flow fingerprints,
   recomputed on the merge commit of the change, with the pull request
   that moved them, and shows the two single-seat defaults, both flow
   digests, the case digest and the seven group digests unchanged (the
   plan's section 7). (Amended 2026-11-23 by the seventh addendum, decision
   T3, item 9: the values are recomputed on a commit that holds this change
   and the workflow change of that addendum; the digest of the group
   "Workflow, tool set and CLI pin" is moved by that change and named with
   its pull request, and the other six group digests are shown unchanged.)
   It replaces the two fingerprint rows of section 23.1
   for every later check. It also states, with `path:line`, the lines a
   later stage is sent (facts 1 to 4, with the new note) and the words of
   decision P4. Owner: verification-lead; ai-engineer recomputes.
2. **Gate ET5.** By decision E4, item 4 of the EDA tools record,
   verification-lead's statement no longer holds once a value of the
   plan's tables moves. That record's procedure applies again as written:
   a replay of `flow/axil-timer` with `controls`, with no model and no
   token, on a commit that holds the change; its record committed beside
   the earlier ones with its test; verification-lead's statement on that
   pull request's head. This addendum does not reword gate ET5 or decision
   E4.
3. **A second measured run.** By the answer of gate ET10's owner
   (fact 11), a measured run on the new fingerprint is owed: the run of
   the plan's section 10, made as that section says, with documents, after
   the change, the plan addition and the record of item 2 are on `main`,
   and with every pinned value recomputed on its commit. Gate ET10 is not
   reworded; it is read on the second run. Gates ET11, ET15, ET17, WF17
   and WF23 are not affected.
4. **Decision F1 of the fifth addendum, amended.** Items 1 and 2 ruled
   that run 45196235508 is the measured run and that no second run is
   owed, on the ground that no pinned value had moved. A pinned value now
   moves, by this council's ruling, on a defect that is a fact of the code
   (decision P1, item 3). From the merge
   of the change, "the measured run" in the plan, in gate ET10 and in
   decision F1, items 3 to 6 means the second run. Item 5's first
   exception covers it in the same words and no others.
5. **Run 45196235508.** It is a run that was made and it is not hidden.
   Its reach records are committed as uploaded, as records only, in the
   layout of decision R2 of the EDA tools record's second addendum, under
   `tool_reach_measured_run_superseded_45196235508` (the index and the
   folder), and are never read as the gate ET10 file (security; the
   precedents are decision E4, item 6 and decision R2, item 5 of that
   record). Its trial record is treated as decision F1, item 4 says. What
   it measured of a record's size may still be used to pack records; no
   figure from it is stated. The sentences decision F1, item 3 allows are
   still the only ones said of it.
6. **The second run's outcome changes nothing by itself.** This is ruled
   before it runs. Whether its flow seats every stage or stops, it stands
   as the measured run if its gates hold, slot 1 is not held for it, and
   the note is not changed again on its account. It is one run, outside
   the forty, never counted and never stated as a result. A further
   proposal to change a fingerprint file returns to the council, and after
   slot 1 only by a ruling that records that results were known.
7. **Gates WF27 to WF29 of the fifth addendum** touch no fingerprint file
   and state no fingerprint value. They stand. The plan addition of gate
   WF28 and the one of item 1 may be one addition or two.

All five seats and security agreed on what a moved fingerprint owes;
eda-tooling's dissent is on moving it (P2). Owners: verification-lead (the
plan, gate ET5's statement); eda-tooling (the replay record and the
dispatch); security keeps gate ET10.

#### P4. A trial that stops because a seat escalated

1. Decision 1, "Failures", stands: a failed trial records the first stage
   that did not complete, and at a stage with no check a cause is an
   inference and is labelled so.
2. A whole-flow trial whose flow stops because a seat escalated at a stage
   with no check is never labelled "model". The failure-to-curriculum rule
   does not apply to it: a document that taught seats to go on past an
   approval nobody made would teach the opposite of the organization's
   own rules (verification-lead). All five seats held this.
3. The read's words for such a trial: "stopped at <stage>: the seat
   escalated; cause not established (an inference where one is given)".
   Where the escalation's own text names the state of its upstream inputs,
   the read may add "on the status of its upstream inputs under the
   pass-through", marked as an inference. It never says the trial shows a
   gap in a skill, and no per-stage figure is stated (decision 1).
4. This holds with the changed note as it would have held without it. The
   trial is still a failed trial of its group, counted as the fifth
   addendum's decision F2 says.

Owner: verification-lead (the read); qa-evidence reads every statement.

#### P5. Text that reaches a prompt outside every fingerprint

1. Fact 8 is a gap in what the fingerprint covers. It is not closed before
   slot 1: closing it changes `harness.CODE` or the fingerprint's own
   make-up and restarts every group.
2. Until it is closed, the freeze inside a batch (fourth addendum,
   decision 2, item 4; the plan's section 7) also names
   `src/nirmaan/work/engine.py` and `src/nirmaan/company/governance.py`:
   nothing merges that changes either between a case's first slot and its
   last planned trial. The plan addition of P3, item 1 says so. This adds
   a condition and loosens none.
3. ai-engineer lists every file whose text reaches a seat's prompt and is
   in no fingerprint, and proposes how the fingerprint covers them, with
   the next change that restarts every group for another reason, and not
   inside a batch.

Raised by ai-engineer, qa-evidence and eda-tooling; the freeze words are
verification-lead's. Owner: ai-engineer.

#### P6. What may and may not be said

1. Any text may state facts 1 to 11 and this ruling, and that a replay of
   the reference answer with no model shows the lines a later stage is
   sent.
2. No text, this one included, states which stage of run 45196235508
   stopped, why its flow stopped, what a seat answered, whether a seat
   escalated or went on, or any count of either. Decision C stands as the
   fifth addendum narrowed it, for that run and for the second measured
   run.
3. The change of P2 is described as what it is: the pass-through now says
   who made the record. It is never described as a fix shown to work. No
   replay can show how a model reads the new words (ai-engineer), and one
   run is not a rate.
4. The timer's read says that the note's words were changed before slot 1
   by this addendum, and what a later stage is sent.

Owner: qa-evidence (gate WF34, and gates WF30 and ET13 as they stand).

### Positions not adopted, and open

- eda-tooling: no code change before slot 1. Not adopted (decision P2).
  Recorded as dissent.
- ai-engineer, design-architect, verification-lead: a further sentence in
  the note that tells the next stage how to go on. Not adopted
  (decision P2, "On the words").
- verification-lead, ai-engineer and qa-evidence offered labels that name
  the harness as the cause of such a stop ("harness (inference)", "harness
  condition (inference)"). Not taken as the read's words: once the note is
  changed, a stop of this kind has no established cause, and decision P4
  says only that.
- design-architect held that no item is in a founder class. The change to
  `flow.py` is in one by path; the review's map decides, not this record.
- Open, for ai-engineer: decision P5, item 3.
- Not known: how often a seat stops on the note, before or after the
  change. This addendum states no rate and rests on none.

### Gates

Gates WF31 to WF34 are met before the timer's slot 1.

| Gate | Condition | Owner seat |
|---|---|---|
| WF31 | The two notes of `src/nirmaan/evals/flow.py` carry the words of decision P2, item 3; no other file in `harness.CODE` or `FLOW_CODE`, no engine or constitution text, no card, document, case file or tool definition changes; tests show the cases of the build specification below; the test of gate WF7 shows both single-seat defaults unchanged | eda-tooling |
| WF32 | A dated plan addition restates both whole-flow fingerprints on the merge commit of gate WF31's change and shows every other pinned value unchanged, states what a later stage is sent, the words of decision P4 and the freeze words of decision P5, item 2. Amended 2026-11-23 by the seventh addendum, decision T3, item 9: on a commit that holds gate WF31's change and that addendum's workflow change, with the digest of the group "Workflow, tool set and CLI pin" moved by the latter and named with its pull request | verification-lead |
| WF33 | Gate ET5 is stated again on a new replay record, and a second measured run is made on the new fingerprint, as decision P3, items 2 to 6 say; the reach records of run 45196235508 are committed as records only under the name of item 5; slot 1 is not dispatched before the chain of gate ET10 is complete on the second run | verification-lead |
| WF34 | Every statement about a trial stopped by an escalation follows decision P4, and every statement about the note, the change and either measured run follows decision P6 | qa-evidence |
| WF35 | The list and the proposal of decision P5, item 3, with the next change that restarts every group; nothing of it merges inside a batch | ai-engineer |

### Build specification, for the build lane

This meeting wrote no code and no plan text.

1. `src/nirmaan/evals/flow.py`: `NOTE_CHECKED` and `NOTE_UNCHECKED` take
   the two texts of decision P2, item 3, exactly; the module's opening
   description says the same. No other line of logic changes.
2. Tests:
   - `tests/test_whole_flow_runner.py:85-86` and `:92` pass as written;
   - a replay of each whole-flow case with no model, in both arms: for
     every stage after the first, the rendered prompt holds, for each
     stage it builds on, one line with "review_record, substantiated:
     Independent review by", that stage's reviewer role and the whole note
     of that stage; every stage's recorded note equals one of the two
     texts; "reviewed in the repository" appears in none;
   - the test of gate WF7 (`tests/test_whole_flow_dispatch.py`), with the
     four fingerprints before and after in the pull request's text: the
     two whole-flow ones moved, the two single-seat defaults equal.
3. `docs/whole_flow/09-runner-flow-module.md` quotes the new notes.
4. A committed record that quotes an earlier note is the record of its
   run and is not rewritten. If a test compares a committed record's note
   with a fresh replay's, the build lane stops and asks the chair.
5. The plan's dated addition (gate WF32), documents only, after the
   change merges.
6. The replay record of decision P3, item 2, then the second measured run
   and the chain of gate ET10 on it, then slot 1. The reach records of run
   45196235508 may be committed at any point before slot 1.
7. Nothing in `prompt.py`, `context.py`, `evals/runner.py`, `engine.py`,
   `governance.py`, the record format, a case, a card or a document.

### Open, for the founder

Nothing.

## Seventh addendum (2026-11-23): the timer's slots two at a time

The committed plan (`evals/plans/2026-11-22-g3-whole-flow.md`) runs the
timer's twenty slots one at a time. The founder, in session, 2026-11-23:
approved running the G3 timer slots two at a time, with safeguards, to save
time. The direction is the founder's. This addendum rules on how, and on
what must be true before slot 1. It adds gates WF36 to WF41. It amends, each
in its own record and each with a note in place: gate ET15 and decision R3,
item 4 of `council/records/2026-11-22-eda-tools-seat-account.md` (second
addendum); and decisions P2, P5 and P6 and gate W2C14 of the addendum to
`council/records/2026-11-23-wave-2-close-meeting-1.md` ("the re-measure
parallel addendum" below; its decisions are always named with that record,
because the sixth addendum above has decisions P1 to P6 of its own). It
also amends two phrases of the sixth addendum above (decision T3, item 9).
It is a decision made on 2026-11-23.

Ruling, in short:

- **Width two, inside a window of two consecutive slots** (decision T1).
  Odd slots run with documents and even slots without, so the two trials in
  flight are always one of each arm, and one event can fail at most one
  trial of each of the timer's two groups. The number is fixed in the plan
  before slot 1 and never raised.
- **One at a time, to slot 20, after the first trial that ends on a plan or
  usage limit, is interrupted, or ends with no model answer** (decision T1).
- **The workflow holds the width for the timer** (decision T3). With the
  opt-in input `parallel`, a timer dispatch runs in one of two concurrency
  groups, one for each arm, so GitHub itself never runs two trials of one
  arm at once and never more than two timer runs. The register block, every
  other `flow/` case and every `firmware/` case stay refused. A second guard
  refuses any dispatch whose case is not written in its exact form.
- **The workflow change merges now**, before the plan addition of gate WF32,
  the replay record of gate ET5 and the second measured run, so that the
  pinned values are restated once and every run before slot 1 uses the
  workflow file the slots use (decision T3).
- **Gate ET15 is reworded for width two** (decision T2), in the words of its
  owner, security. A finished run's reach records are downloaded, verified
  by digest and pushed to a branch of the repository before the next
  dispatch; a finished run whose records show a probe not denied closes
  dispatch at once; the reach folders of every slot three or more places
  back are on `main`. The order on `main` and the test of gate ET16 do not
  change.
- **Gate W2C9 stays exactly as it is** (decision T3, item 11). The
  re-measure batch dispatches nothing, its replays included, before the
  timer's last planned trial is recorded.
- **A stop closes dispatch and cancels no running trial; every trial
  dispatched is committed; nothing is run again** (decision T4).

It changes no code, case, eval record, plan text, level, fingerprint or
digest by itself: the changes it orders are made by their own pull
requests. It changes no count, case, arm or slot, and not the one read. A
failed trial stays a failed trial and nothing is run again.

It does change what two gates rest on, and it says so. Gate ET15 asked for
every earlier run's reach folder on `main` before any dispatch; from this
addendum it asks for that of slots three or more places back, and for a
verified, pushed copy of the rest. That is a looser condition on where the
records are at the time of a dispatch, made by the gate's owner for the
founder's direction, with two conditions added that the gate did not have
(decision T2, items 1 and 2). And the workflow's single group, which kept
the timer one at a time, is replaced for the timer by two groups. No trial
ran and no workflow was dispatched for the meeting.

### Who decided what

- The founder decided that the timer's slots run two at a time, with
  safeguards. The council decided every item below, and the founder can
  overrule any of it.
- One cost of the direction is stated for the founder under "Open": what
  one event can cost at width two (decision T1, item 3).
- One preference of security needs a repository setting that only the
  founder changes, and is listed under "Open". No ruling here rests on it.

Five seats gave round 1 positions, each as a read-only process of its own
that saw no other answer to the brief: security, ai-engineer,
verification-lead, qa-evidence and eda-tooling; the chair decided. The
seats read ip-nirmaan `main` at 0362c9ad, the draft pull request ip#470 and
a copy of the private tooling that dispatches the batch. The seats had no
shell; nothing was run. After round 1 the chair asked security, as the
owner of gate ET15 and of the workflow's guard, four owner questions on
points other seats had raised; security answered them without seeing any
other position beyond what the questions quoted, and its answers are
adopted where this addendum says so. The chair rechecked the facts below at
0362c9ad.

The pull requests that change `.github/workflows/live-eval.yml` and this
record are in a founder class by path and go to the Founder Proxy (agent)
by the usual rule. A key is an agent review. Nothing here is a person's
approval, a release, or a claim that a design is ready to be made in
silicon.

### Facts checked

TF1 to TF15 number this addendum's facts.

- TF1. Slots 1 to 20 are all `flow/axil-timer`; odd slots run with
  documents and even slots without
  (`evals/plans/2026-11-22-g3-whole-flow.md:59-60`, `:218-239`). Whole-flow
  trials group by case, case digest, model, harness fingerprint, CLI, flow
  digest and purpose, and a count is written only from ten trials (the
  plan, section 2); the two arms have different fingerprints. So the timer
  has two groups of ten, with no level and no bar, and any two adjacent
  slots are one trial of each group. Slots two apart are of the same arm.
- TF2. No slot has been dispatched. By the sixth addendum above the
  pass-through note changes before slot 1 (gate WF31), both whole-flow
  fingerprints move and the plan restates them (gate WF32), and a new
  replay record and a second measured run are owed before slot 1 (gate
  WF33). None of the three was on `main` at 0362c9ad.
- TF3. The timer is one at a time today in three places: the plan ("The
  next slot is dispatched only after the whole run, `live-eval` and
  `rejudge`, has finished", line 73; and lines 43-45); the workflow's one
  concurrency group, `group: live-eval`, `cancel-in-progress: false`
  (`.github/workflows/live-eval.yml:88-90`); and whatever dispatches the
  batch, which refuses while any run of the workflow is queued or running.
- TF4. Gate WF9 (line 497 above) names no concurrency group and does not
  say "one at a time". The plan's evidence row for it (line 818) cites "the
  named job and its concurrency group (`.github/workflows/live-eval.yml:81-82`,
  `:199`)", as read at `02cfa87f` (the plan's line 807). At 0362c9ad those
  lines are the `controls` input and the condition of the replay upload;
  the group is at lines 88-90. The row for gate WF17 (line 819) cites
  `:250-253`, which is now the checkout step. So both rows are owed again
  whatever is decided here (qa-evidence, security, ai-engineer,
  eda-tooling).
- TF5. Each job runs on a hosted runner of its own
  (`live-eval.yml:95`, `:225`, `:339`) and every artifact name carries the
  run's id. Two runs share no checkout, no seat account and no file. They
  share the one secret of the `live-eval` environment, so the one plan
  (inference, as fact PF2 of the re-measure parallel addendum), and one
  cache entry, the tool suite's archive, whose sha256 is checked on every
  use (`.github/actions/oss-cad-suite/action.yml:18-23`, `:36`;
  eda-tooling).
- TF6. The workflow file is in no fingerprint (`harness.CODE`, `LOOP_CODE`
  and `FLOW_CODE` name only files under `src/`,
  `src/nirmaan/runtime/harness.py:257-293`). It is in the group "Workflow,
  tool set and CLI pin", which the plan pins (line 1266). Gate ET10 asks
  that the values on the measured run's commit "equal those on the commit
  slot 1 is dispatched from" (the plan, lines 858-859). So a workflow edit
  merged after the second measured run and before slot 1 would owe a third
  measured run, and one merged after slot 1 is forbidden by the freeze
  (fourth addendum, decision 2, item 4, which names the workflow).
- TF7. The re-measure parallel addendum ruled, for the single-seat
  re-measure batch: an opt-in input `parallel` whose group expression and
  guard refuse every `flow/` and `firmware/` case (its decision P2, items
  1, 2 and 5: "The whole-flow timer and the register block are never
  dispatched with it"); that the workflow change "merges only after the
  timer case's last planned trial is recorded" (its decision P6, gate
  W2C14), because a merge before or during the timer's slots "would move a
  digest the whole-flow plan pins and change the lines its gate WF9 cites
  as met"; and gate W2C9, "The two batches are never interleaved". ip#470
  is the draft that builds its decision P2.
- TF8. The timer flow links no seat C and runs; the register block flow has
  a firmware stage and stays refused (`scripts/live_eval_ci.py:34-37`). That
  refusal is one "a change of its own lifts" (the plan, lines 39-41), so it
  is not a lasting ground for keeping the register block out of anything.
- TF9. A trial that is interrupted or ends on a plan or usage limit is a
  failed trial of its group, committed, never run again (the plan, section
  8). Decision 11 of `council/records/2026-11-14-pilot-retrospective.md`
  rested that on "the runner's stop rule already limits the loss to one
  trial" (its line 333). With two trials running on one plan, a limit that
  ends one can end both (inference; no seat knows a way to read the plan's
  remaining allowance from a script).
- TF10. Gate ET15 has two texts. Decision R3, item 4 of the EDA tools
  record's second addendum: "unless the commit it is dispatched from holds
  the reach folder of every earlier run of every slot, with digests equal
  to the files the dispatcher downloaded"; its gate row: "each file equal
  by digest to what the run uploaded"; the plan quotes the row (lines
  864-866). Neither says what a run still in flight owes. As written it
  allows a width of one only (qa-evidence).
- TF11. As written, gate ET15 would also deadlock at width two (inference;
  verification-lead and ai-engineer, each alone). Slot N stops at job level
  with no trial while slot N+1 runs and writes its record. Dispatching slot
  N again would need slot N+1's reach folder on `main`; decision R3, item 3
  keeps it off `main` until slot N's record is there.
- TF12. GitHub compares strings with `==` ignoring case (GitHub's
  documented behaviour; not run for the meeting), and the trial
  command strips the case's name before it looks it up
  (`scripts/live_eval_ci.py:101`). So a guard that tests the case's name
  by prefix or by equality does not see the name the command will run: in
  ip#470 as drafted, a timer case written with a leading space would get a
  group of its own and pass the guard (inference from the two lines;
  security). Nothing was dispatched to show it.
- TF13. The test of gate ET16 fails a tree in which a slot has reach
  records while a lower slot has reach records and no record
  (`tests/test_whole_flow.py:284-288`). Branches need not be up to date
  with `main` and auto-merge is on (`docs/REVIEW_MECHANISM.md:10`). So a
  reach pull request opened before its turn would carry a failing check,
  or could merge out of order on an old base (eda-tooling).
- TF14. No committed record holds a run's `parallel` input or its
  concurrency group. A record's manifest carries its commit and its start
  and finish times (`src/nirmaan/evals/records.py:270-277`), and a slot's
  reach index names its run (the plan, section 20.2) (qa-evidence).
- TF15. Whatever dispatches the batch today falls back, when the dispatch
  call returns no run, to the run created after the call, on the ground
  that no other run was active. At width two that ground is gone (security,
  ai-engineer, eda-tooling).

### Decisions

#### T1. Width two, a window of two slots, and one at a time after an event

1. At most two trials of the timer are in flight at once. The number is
   fixed in the plan addition before slot 1 and is never raised.
2. The window. Slot k is first dispatched only when every slot numbered
   k-2 or lower has finished: every job of its run concluded, the counting
   re-judge included, and the run classified. So the slots in flight are
   always two adjacent slots, one of each arm (fact TF1). The window is
   counted by slot, not by run (verification-lead).
3. What one event can cost. An event that ends every trial in flight ends
   at most one trial of each group, where one at a time loses one trial of
   one group. Each is a failed trial of its group, committed and never run
   again. The council accepts this for the timer: the groups have no bar
   and no level, and the loss falls on both arms alike. All five seats
   accepted it. Width three would put two trials of one arm in one window
   (fact TF1), so two is the most this plan's order allows (ai-engineer).
4. After the first trial of the batch that ends on a plan or usage limit,
   is interrupted, or ends with no model answer, the width is one from then
   until slot 20. It is a rule of the plan, applied on the class of the
   stop and never on a result, and it is never undone. It is ai-engineer's
   rule; verification-lead asked that only a limit lower the width. The
   chair took the wider rule because the groups are ten each and an outage
   or a throttled answer is as shared between two running trials as a
   limit is.
5. After such an event, dispatch resumes only when every trial that was in
   flight has been classified and, for a limit, the limit has reset.
6. No rule rests on reading the plan's remaining allowance (fact TF9).
7. The width is in no fingerprint and no group key.
8. What the interleave does not give. Two trials that run together are not
   independent: they share one plan and one secret, and an event that
   reaches both cannot be told from the counts. Running two at a time may
   add retried calls, which touches the derived count ("passed with every
   stage on its first attempt") before the main count (verification-lead).
   No text draws a paired figure from the overlap (decision T5).

Why a rolling window and not aligned pairs: no seat chose pairs; the
window gives the same bound and each dispatch keeps its own check.

Owners: verification-lead (the number, the window); ai-engineer (items 4
to 7).

#### T2. Gate ET15 at width two

Security is the gate's owner and gave these words; the chair asked it to
settle the points of facts TF11 and TF13, and it did.

1. **The gate, reworded.** From slot 1, slot k of the timer case is
   dispatched, a first time or again after a stop, only if:
   - (a) every run dispatched earlier that has finished has had every reach
     artifact of every job downloaded, each file's sha256 equal to the
     index the dispatcher wrote for that run. "Finished" means every job
     concluded, the re-judge included, and the run classified. A run still
     in flight owes nothing until it finishes;
   - (b) for each such run whose reach folder is not yet on `main`, the
     verified files are on a branch of the repository, at a commit whose
     only change against its parent, a commit of `main`, adds exactly that
     run's files in the layout of decision R3, item 1. The dispatcher reads
     that commit back from GitHub, not from its own copy: the branch
     resolves to it and every file's digest equals the index. It writes the
     commit down before the next dispatch;
   - (c) the commit dispatched from holds the reach folder of every run of
     every slot numbered k-3 or lower, each file equal by digest to the
     index;
   - (d) for a second or later dispatch of a stopped slot k: (c) holds; the
     commit dispatched from also holds the reach folder of every earlier
     run of slot k itself; no lower slot is waiting to be dispatched again;
     and no slot above k has its first dispatch before slot k's new run has
     finished.
2. **A probe not denied closes dispatch.** A finished run whose downloaded
   reach records show a probe not denied, a reach gate that failed, or a
   reach artifact missing closes dispatch at once, whether or not anything
   of it is on `main`, and it stays closed until what decision A3 of the
   EDA tools record's addendum asks for that run has been done. The trial
   then in flight is not cancelled: its own reach test ran before its
   trial and runs before its re-judge, and it is committed in its order.
   This is new: the gate as written did not read the records' content
   (ai-engineer, qa-evidence, eda-tooling and security each asked for it).
3. **The branch.** The pull request of a run's reach records is opened only
   when the order of decision R3, item 3 allows, and its head is the commit
   of item 1 (b), or the files' digests are checked again before it
   merges. The branch is never rewritten or deleted before its folder is on
   `main`; if it changes, dispatch closes. Nothing in the repository
   enforces that last sentence today: it is a rule for whatever dispatches,
   and no text calls it a control (security).
4. **Why (c) is three back.** Under the window every slot numbered k-2 or
   lower has finished when slot k is dispatched, so (c) never waits on a
   run in flight. verification-lead gave two back; security chose three
   and would accept two, on the ground that (a) and (b) carry the gate and
   the number only bounds how far `main` may trail. The chair took the
   owner's number. Recorded under dissent.
5. **No deadlock.** In the case of fact TF11, dispatching slot N again
   needs nothing of slot N+1: (d) waits only on slot N-1's record and on
   slot N's own earlier runs, and slot N+1's reach records wait on their
   branch until slot N's record is on `main`.
6. **The reasons of decision R3, item 4, restated.** "None held out" stays
   a check: every finished run's files are verified and public before the
   next dispatch. An artifact that is not kept is no loss: the files are on
   a branch of the repository. "A denial that failed is on `main` before
   any further trial" no longer holds as it was written. What holds is
   this: a denial that failed closes dispatch before any further dispatch
   (item 2), and at most the one trial then in flight ends after it,
   behind its own reach gate. Every text that gives that reason gives it
   in these words (qa-evidence).
7. **What does not change.** The order on `main` (decision R3, item 3), one
   pull request for one run's reach records or for records and never both,
   and everything the test of gate ET16 holds. The test gains one passing
   case: a slot whose recording run is on a later commit than the next
   slot's, as a second dispatch after a stop produces (verification-lead).
   Gates ET10, ET11, ET13 and ET16 are not reworded.

Owners: security (the gate); verification-lead (item 7).

#### T3. The workflow: two groups for the timer, two guards, merged now

1. **The change is that of ip#470, extended, in one pull request.** The
   input `parallel` stays a boolean whose default is false. The concurrency
   block becomes:

   ```
   concurrency:
     group: ${{ inputs.parallel && inputs.case == 'flow/axil-timer' && (inputs.knowledge == 'off' && 'live-eval-timer-off' || 'live-eval-timer-on') || inputs.parallel && !startsWith(inputs.case, 'flow/') && !startsWith(inputs.case, 'firmware/') && format('live-eval-run-{0}', github.run_id) || 'live-eval' }}
     cancel-in-progress: false
   ```

   With the input false, and for every `firmware/` case and every `flow/`
   case other than the timer whatever the input says, the group is
   `live-eval`, as today. A timer dispatch with the input runs in
   `live-eval-timer-on` or `live-eval-timer-off` by its `knowledge` input,
   a replay of the timer included. The re-measure batch's single-seat
   cases keep the group per run that the re-measure parallel addendum gave
   them.
2. **Why two groups by arm and not a group per run.** ai-engineer and
   eda-tooling gave the timer a group per run, as ip#470 gives the
   single-seat cases; then GitHub holds no width and it rests on the
   dispatcher alone, which is private and which no public text may cite.
   security made the two groups a must-have: GitHub then never runs two
   timer trials of one arm together and never more than two timer runs,
   and that is a fact of the workflow file anybody can read. It also meets
   qa-evidence's condition that the width not rest on a private ledger.
   The chair took security's form. In a group GitHub keeps one running and
   one pending run, and a newer pending run cancels an older pending one.
   Under the window of decision T1 no timer run is ever pending: a slot is
   dispatched only when the last slot of its arm has finished. A pending
   run can arise only from a dispatch outside the window, which is a fault
   of the dispatcher; a pending run that is cancelled has run no trial,
   and it is a job-level stop of its slot. For the re-measure batch
   security refused any mechanism under which GitHub cancels a queued run,
   and the council took a group per run there. Here security asked for
   groups that can hold a pending run, on the ground that a width held
   only by the dispatcher is a promise; the two rulings differ, and this
   one is for the timer only. Recorded under dissent for ai-engineer and
   eda-tooling.
3. **The guard on `parallel`.** The first step of the `replay` job and of
   the `live-eval` job fails the job when `parallel` is true and the case
   is a `firmware/` case or a `flow/` case other than `flow/axil-timer`,
   replays included. In the `live-eval` job it comes before the checkout
   and before any step that reads the secret.
4. **The guard on the case's form** (fact TF12). A step of its own, in both
   of those jobs, before the checkout: it reads the case only from the
   job's environment, never as text placed in a `run:` line, fails unless
   the name matches `^[a-z0-9][a-z0-9/_.-]*$`, and refuses `..`. It does
   not read `inputs.parallel` and applies to every dispatch. The `rejudge`
   job runs only when one of those two jobs uploaded records, and a guard
   that fails skips the trials step; a test holds that dependency. The
   guard may also be the first step of `rejudge`.
5. `inputs.parallel` appears in the concurrency group and in the two
   steps of item 3 and nowhere else: not in `env:`, not in a `run:` line.
   No new permission, no new use of the secret (it is read where it is
   read today), no query of other runs from inside a job, and the
   environment and its main-only rule are unchanged.
6. **F-b is refused.** No seat chose to admit every `flow/` case and leave
   the register block to the trial command's own refusal: that refusal is
   one its own change lifts (fact TF8), and "never dispatched with it"
   would then rest on nothing (security, qa-evidence, eda-tooling,
   ai-engineer, verification-lead).
7. **Which dispatches may use `parallel`.** For the timer: its slots; the
   second measured run; the replay of gate ET5's record; and the shake-out
   of item 10. A timer replay with the input runs only before slot 1 or
   after slot 20's record. For the re-measure batch: what its own addendum
   says. Nothing else without a council ruling. The register block is
   never dispatched with it: before its slot 21 the question returns to
   the council, and its slots run one at a time unless a ruling says
   otherwise.
8. **It moves no fingerprint** (fact TF6) and no tool definition. It moves
   the digest of "Workflow, tool set and CLI pin" in both plans.
9. **It merges now.** Before the plan addition of gate WF32 is computed,
   before the replay record that states gate ET5 again, and before the
   second measured run; the change of gate WF31 and this one merge in
   either order. All five seats said so. Then the plan restates its values
   once, on a commit that holds both, and the replay record, the second
   measured run and every slot run on one workflow file (fact TF6). Two
   phrases of the sixth addendum above are amended to allow it: in its
   decision P3, item 1 and in gate WF32, "recomputed on the merge commit of
   the change" reads "recomputed on a commit that holds the change of gate
   WF31 and the workflow change of the seventh addendum", and "the seven
   group digests unchanged" and "every other pinned value unchanged" read
   with "except the digest of the group Workflow, tool set and CLI pin,
   which the workflow change moves and the addition names with its pull
   request". A further edit to the workflow file after the second measured
   run owes a third (fact TF6); from slot 1 the file is frozen as before.
10. **The shake-out, before the plan addition.** From `main`, on a commit
    whose `live-eval.yml` is the merged one, with no model and no token:
    two replays of the timer with `parallel` true, one with documents and
    one without, in flight together, each judged as a replay is judged
    today; a replay of the register block and a replay of a `firmware/`
    case with `parallel` true, each refused at the guard of item 3; a
    dispatch whose case is not in the exact form, refused at the guard of
    item 4; and two replays without the input, the second of which waits
    for the first in `live-eval`. The plan addition names each run, its
    commit and the sha256 of the workflow file on it (security).
    eda-tooling and ai-engineer asked for it: a workflow fault found after
    the second measured run would owe a third, and a real dispatch is the
    only proof of an expression that tests can only model. security first
    refused `parallel` for any replay of a `flow/` case and withdrew that
    on the chair's question: the `replay` job reads no secret, and in the
    arm's group a replay can never overlap a trial of that arm.
11. **Gate W2C9 stays exactly as it is.** ai-engineer, its owner, and every
    other seat said so. With the workflow change on `main` early, the
    re-measure batch's replays (its gate W2C5) could be dispatched earlier
    in principle. They are not: nothing of that batch, a replay included,
    is dispatched before the timer's last planned trial is recorded, and
    the re-measure plan's section 10 is not changed. During the timer's
    batch any run of the workflow that the dispatcher did not start, in
    any group, closes dispatch until it has ended.
12. **The second measured run and the replay of gate ET5's record are
    dispatched with `parallel` true**, each alone. The plan's section 10
    makes the measured run "by the same dispatch as a slot".
13. **Gate WF9's evidence** is stated again in the plan addition, on the
    commit it is computed on, by line: the named job; the concurrency
    block word for word and the two groups a timer dispatch resolves to;
    one trial per dispatch on the default harness; the expected
    fingerprint; the hashed checkout; the counting re-judge. So is the
    row of gate WF17 (fact TF4). "One at a time" is said only of the
    trials inside one dispatch. Gate WF9 itself is not reworded: it names
    no group (fact TF4).
14. **Tests**, written failing first, in the workflow's pull request: the
    exact concurrency block; the input's type and default; the group for
    the timer with each `knowledge` value, with and without `replay`; that
    the register block, any other `flow/` case and a `firmware/` case
    resolve to `live-eval` whatever the input; a single-seat case with and
    without the input; the timer's name in another letter case and with
    surrounding space, refused by the guard of item 4; that every case id
    under `evals/` matches that guard's form; both guards' places, before
    the checkout and before the first step that reads the secret; where
    `inputs.parallel` appears; the secret read exactly where it is read
    today; and the dependency of `rejudge` on the two jobs (item 4). The
    evaluator the tests use gains `==` and `!=`, ignoring case as GitHub
    does. ip#470's tests that hold the timer in `live-eval` with the
    input, and its comment that the timer stays one at a time, change.
    `docs/LIVE_EVAL_EVIDENCE.md` is corrected in the same pull request.

Owners: security (items 1 to 7); eda-tooling (items 8 to 10, 12, 14 and
the build); ai-engineer (item 11 and the digest); qa-evidence (item 13).

#### T4. Order, binding and stops with two in flight

1. Slots are first dispatched in strictly increasing slot order. Nothing is
   reordered by a result.
2. A slot is marked attempted before its own dispatch. The check of the
   plan's section 7 is made before every dispatch, one check at a time, on
   `main` as it then is, and the commit each run reports is checked as
   today.
3. One slot, one run. The run's id is taken from the response to the
   dispatch and written beside the slot before anything else is
   dispatched. A run is never identified by the time it was created (fact
   TF15). If the id cannot be bound, dispatch stops and a person binds it;
   the run is not cancelled.
4. The width is counted on the dispatcher's own bound runs, by one
   dispatcher process. A run of the workflow that it did not start, queued
   or running, in any group, closes dispatch until that run has ended.
5. Any stop in any running trial closes dispatch at once: a plan or usage
   limit, an interrupted trial, a trial with no model answer, a job-level
   stop, a record that is not the trial asked for, a re-judge that did not
   finish or did not hold, a reach gate that failed, a finding of decision
   T2, item 2, a record or file over the review's size limit, a run that
   was not the dispatcher's, a run whose id could not be bound.
6. Nothing in flight is cancelled because of another run's outcome, and no
   run whose trial step has started is ever cancelled: cancelling a
   running trial makes a failed trial. The one cancel that remains is the
   plan's own (section 7): a run whose commit fails the dispatch check is
   cancelled on the dispatcher's own bound run, only while its trial step
   has not started. If that step has started, the run is left to end, is
   classified, and dispatch stays closed.
7. Every trial already dispatched ends as it ends, is classified by
   itself and is committed as it is. Nothing is run again and nothing is
   replaced.
8. A job-level stop that ran no trial is dispatched again as the plan
   says, under decision T2, item 1 (d): before any slot above it is first
   dispatched. The run that was beside it is not touched. The read names
   every slot dispatched after a higher one.
9. A stop that waits for a person today waits for a person as today, once
   nothing is in flight.
10. Records reach `main` in slot order, none held out, failed ones
    included, whatever order the runs finish in (decision R3, item 3).
11. Decision 11's reason, that a stop loses one trial, does not hold for
    this batch (fact TF9). The rule it supported stands: a failed trial is
    never replaced. Running two at a time can only lower a count.
12. The rule of decision T1, item 4 bounds one event. An event of another
    kind that ends running trials, such as a replaced secret, ends at most
    two, one of each group; each is a failed trial, and the read names the
    event and its slots.

Owners: verification-lead (items 1, 2, 5 to 9); qa-evidence (items 3 and
10); security (item 4); ai-engineer (items 11 and 12).

#### T5. The plan addition, the read, and what may be said

1. **One dated addition to the plan, merged before the replay record of
   gate ET5, the second measured run and slot 1**, after the workflow
   change, the change of gate WF31 and the shake-out. It may be the same
   addition as gate WF32's and gate WF28's, if it lists each moved value
   with the pull request that moved it. It changes no count, case, arm or
   slot. It states:
   - the width, the window and the rule of decision T1, item 4, and that
     the number is never raised; it joins the list of what is fixed
     (section 1);
   - section 2, lines 43-45, and section 3, line 73, rewritten: the window
     in place of "only after the whole run"; the dispatch command with
     `-f parallel=true`; the two groups;
   - section 7: the check before every dispatch, one at a time;
   - section 8: an event can fail the two trials in flight, one of each
     group; the rules of decision T4, items 5 to 9 and 12; the limit stop
     as decision T1, items 4 and 5 give it; that decision 11's reason does
     not hold here and its rule does;
   - section 20: gate ET15 in the words of decision T2, item 1, with items
     2, 3 and 6;
   - the concurrency block and both guards word for word, which dispatches
     may use the input, and that for the timer GitHub holds the width
     through the two groups while the window and the order rest on the
     dispatcher;
   - the moved digest of "Workflow, tool set and CLI pin", the commit it
     was computed on and the pull request that moved it;
   - the rows of gates WF9 and WF17 again (decision T3, item 13);
   - the runs of the shake-out;
   - that runs share one secret and one plan, and the tool archive's cache
     entry, and nothing else (fact TF5);
   - what the read adds (item 3).
   After it no text says "one at a time" of the timer's slots, except of
   the width after an event and of the trials inside one dispatch.
2. **A committed test of the overlap** (qa-evidence), in
   `tests/test_whole_flow.py`, on `main` before slot 1 and holding at
   every commit after: among the committed slot records of the timer, any
   two whose manifests' times overlap are records of adjacent slots (fact
   TF14). It passes while no slot record exists. It shows from the
   committed records, and not from any private file, that no more than two
   trials ran together and never two of one arm. It reads the times and
   states none.
3. **The read adds**: the width; that trials overlapped; for each slot its
   run, its commit and the slot whose run overlapped it, if any; whether
   it ran after the point from which the batch ran one at a time, and that
   point; every stop event with the slots then in flight and their labels;
   each group's failed trials by label; every slot dispatched after a
   higher one; any run cancelled before its trial under decision T4, item
   6; and that no running trial was cancelled and nothing was held out or
   run again.
4. **Never said**: that running two at a time had no effect on a result,
   or that it had one; that the interleave makes the two arms comparable,
   or any figure for a pair of overlapping trials; that the timer and any
   batch that ran one at a time ran under the same dispatch conditions;
   which concurrency group a given run used, as a fact of that run (no
   record holds it, fact TF14): a text may say what the workflow file gives
   for the inputs the plan fixes, and what the test of item 2 shows.
5. Every statement about the measured runs follows decision P6 of the
   sixth addendum above and decision C of the EDA tools record as they
   stand. No time, usage or cost figure enters any text.

Owners: verification-lead (the addition, the read); qa-evidence (the
wording, items 2 and 4).

### Positions not adopted, and dissent

- ai-engineer and eda-tooling: a group per run for the timer, as for the
  single-seat cases. Not adopted (decision T3, item 2). Recorded as
  dissent. Their case named exactly, their refusal of F-b, and
  eda-tooling's tests are adopted.
- verification-lead: gate ET15's bound at two slots back. Not adopted: the
  owner chose three and would accept two (decision T2, item 4). Recorded
  as dissent.
- verification-lead: only a limit lowers the width. Not adopted (decision
  T1, item 4).
- security, in round 1: `parallel` refused for every replay of a `flow/`
  case; a reach pull request open before the next dispatch; a clause "at
  most two finished runs are off `main`". Each was changed by security
  itself on the chair's questions: the first withdrawn (decision T3, item
  10); the second replaced by a pushed, verified commit (decision T2, item
  1 (b), on eda-tooling's fact TF13); the third follows from (c), (d) and
  the window and is left to the dispatcher to assert.
- eda-tooling: the change of gate WF31 merges first, then the workflow
  change. Not fixed: either order, both before the plan addition (decision
  T3, item 9).
- qa-evidence: either a committed record holds each run's `parallel`
  input, or no text says which group a run used. The second is adopted
  (decision T5, item 4); the record format is not changed.
- qa-evidence asked that every amended ruling be noted in its own record
  with the old text quoted. Adopted: the notes are in the two other
  records, made by this pull request.

No seat dissented from: width two with the rolling window; the timer named
exactly; refusing the register block, every other `flow/` case and
`firmware/`; merging the workflow change before the second measured run;
keeping gate W2C9 as it is; cancelling nothing on a stop; committing every
trial and running none again; or leaving the order on `main` and gate
ET16's test as they are.

### Gates

Gates WF36 to WF38 are met before the timer's slot 1. Gates WF39 and WF40
hold from slot 1 to slot 20, and gate WF41 at the read.

| Gate | Condition | Owner seat |
|---|---|---|
| WF36 | The workflow change of decision T3, items 1 to 5, with the tests of item 14 and the corrected document, merged before the plan addition of gate WF32 is computed and before the second measured run; no fingerprint moved | security |
| WF37 | The shake-out of decision T3, item 10, on the merged workflow file, every run named in the plan addition; the replay of gate ET5's record and the second measured run dispatched with `parallel` true, each alone | eda-tooling |
| WF38 | The plan addition of decision T5, item 1, with the moved digest and the rows of gates WF9 and WF17 stated again; the committed test of decision T5, item 2 and the added case of decision T2, item 7 | verification-lead |
| WF39 | Gate ET15 as decision T2 words it holds before every dispatch from slot 1: items 1 to 3; the order on `main` unchanged | security |
| WF40 | One slot, one run, bound from the dispatch response; the window; a run the dispatcher did not start closes dispatch; a stop closes dispatch and cancels no running trial; every trial dispatched is committed; nothing is run again; width one after the first event of decision T1, item 4 | ai-engineer |
| WF41 | At the read: what decision T5, item 3 asks the read to add, and nothing item 4 forbids | qa-evidence |

Gate W2C9 of the wave 2 close record stands as written. Its gate W2C14 and
the EDA tools record's gate ET15 are reworded in their own tables, each
with a note.

### Build specification, for the build lane

Nothing here is built by this addendum. In order:

1. The change of gate WF31 (sixth addendum) and, in either order, one pull
   request, control plane: the workflow change of decision T3, items 1 to
   5, the tests of item 14 and `docs/LIVE_EVAL_EVIDENCE.md`. It states that
   no fingerprint moves and names the moved group digest. It is the change
   of ip#470, extended; whether it is that pull request or one that
   replaces it is its author's.
2. The shake-out of decision T3, item 10, on `main`.
3. One pull request, or more: the plan addition of decision T5, item 1,
   which may be gate WF32's and gate WF28's, with every pinned value
   recomputed on a commit that holds items 1 and 2's changes; the test of
   decision T5, item 2 and the added case of decision T2, item 7 in
   `tests/test_whole_flow.py`. No file of a pinned group changes.
4. Whatever dispatches the batch (private tooling, not in this repository)
   carries decisions T1, T2 and T4, with tests of its own before slot 1:
   the window by slot; binding each run to its slot from the dispatch
   response, with no fallback by time; the width counted on its own bound
   runs; a run it did not start; each stop of decision T4, item 5 arriving
   while another run is in flight; a limit with two in flight and the
   width one after it, kept in its state and not in memory; no cancel of a
   run whose trial step has started; gate ET15's four clauses, the read
   back of the pushed commit, and a finished run that shows a probe not
   denied; the second dispatch of a stopped slot beside a running one
   (fact TF11); and the order of reach and record pull requests.
5. The replay record that states gate ET5 again, then the second measured
   run and the chain of gate ET10 on it (sixth addendum, gate WF33), each
   dispatched with `parallel` true; then slot 1.
6. The re-measure batch: its plan amendment (gate W2C12 of the wave 2
   close record) restates the moved digest on the merged commit, as that
   record's decision P7 says; nothing of it is dispatched before the
   timer's last planned trial is recorded.
7. Before the register block's slot 21: the dated addition the fourth
   addendum asks for restates the values for that case, and the question
   of its width returns to the council (decision T3, item 7).

### Open, for the founder

1. This addendum, to confirm or overrule.
2. What the direction can cost, stated once: an event that ends both
   running trials fails one trial in each of the timer's two groups, where
   the plan as committed would have lost one trial in one group. Each is a
   failed trial and is never run again. The council bounds this to one
   such event from a limit, an interruption or a trial with no answer
   (decision T1, item 4). If the founder wants the width kept after such
   an event, or no running two at a time, that is the founder's to say
   before slot 1.
3. Security's preference, not a condition of any gate here: a repository
   rule that blocks rewriting and deleting the branches that hold reach
   records before they merge (decision T2, item 3). Repository rules are
   the founder's to set.

## Eighth addendum (2026-11-25): the read of the timer case's twenty trials

This addendum records the one read of the timer case, `flow/axil-timer`,
slots 1 to 20 of the committed plan
(`evals/plans/2026-11-22-g3-whole-flow.md`). It is the read gate WF41 names.
It adds the read and nothing else: it changes no decision, code, case,
record, count, level or gate above. The register block case has not run.

A key is an agent review. Nothing here is a person's approval, a release, or
a claim that a design is ready to be made in silicon.

### Who decided what

- The rule was fixed before slot 1, by the plan and the addenda above: one
  read per case, after the case's last planned trial is recorded, two groups
  of ten, no split, no re-run, no top-up, no extension and no second read
  (the plan's sections 2, 5, 8 and 11; fourth addendum, decision 1). What
  the read adds and what it never says are the plan's section 24.12
  (decision T5, items 3 to 5; fifth addendum, decision F5; sixth addendum,
  decisions P4 and P6).
- Nothing was chosen at the read. It was taken once, after the record of
  slot 20 merged.
- Owner of the read: verification-lead. qa-evidence reads every statement
  (gates WF26, WF30 and WF41). eda-tooling, as owner of gate WF29, and
  ai-engineer, as owner of gate WF40, ruled on how the showing of those two
  gates is stated ("Gates WF29 and WF40" below). The seats' statements are
  under "Seat statements".

### What was read

Read once, on `main` at `904bb511`, the merge of the record of slot 20
(ip#543). The reach pull requests are the even numbers ip#502 to ip#520 and
ip#524 to ip#542, and the record pull requests the odd numbers ip#503 to
ip#521 and ip#525 to ip#543, one run or one slot each, in slot order, each
record after the pull request of its run's reach records.

- `scripts/capability_levels.py --check` reports that
  `capability/levels.json` matches the records, and the levels generator
  refuses no record (`refused_records` is empty).
- The figures below are the two groups that `_whole_flow_groups`
  (`src/nirmaan/evals/levels.py`) writes for `flow/axil-timer` under
  `whole_flow` in that file, with each trial as that list holds it. Nothing
  was counted by hand, and the code that reads the records did not change
  between slot 1 and this read.
- All twenty records are on `main` under `evals/results/g3-timer/slot-NN/`,
  failed ones included, one trial in each, and every trial is re-judged the
  same (`rejudge.json` in each record). Each slot holds one reach folder, of
  one run, whose index names the slot, the run and the commit of the
  record's manifest (`reach/<run>/reach-index.json`; the test of gate ET16
  in `tests/test_whole_flow.py` holds at `904bb511`).
- Every trial ran on the default harness with its attempts, one trial per
  dispatch, model `claude-opus-5-5`, Claude Code 2.1.325, case digest
  `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3`,
  purpose `evidence`.

### The read

The whole-flow pass count, per group, k of 10 with its 95 percent Wilson
interval. It is not a level or a score, it has no bar, it credits no skill,
and it is never pooled. The register block case has not run.

| Group | Arm | Harness fingerprint | Flow digest | Whole-flow pass count | Wilson interval |
|---|---|---|---|---|---|
| A | with documents (odd slots) | `sha256:56c5fac7d788bb34f84b263db1a50b896aba5779387bfed63a0a07975e4dcd72` | `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312` | 4 of 10 | 0.1682 to 0.6873 |
| B | without documents (even slots) | `sha256:7e8ba68dd60b395186441ba4c27392659189a603b59705fa2cc3d4dbf5c4a83c` | `sha256:b8608edecf2013dddfaec85e947106316f9a561a8ec74c7e3d99a7f53f8323c0` | 4 of 10 | 0.1682 to 0.6873 |

Each group's flow digest is the digest of the first trial placed in it, it
covers every stage, and it equals the plan's flow digest for the arm
(section 24.1). The two counts are stated side by side with their intervals,
as the plan's section 11 allows, and nothing more is said of the arms. There
is no figure for twenty and none for the case across its arms.

**The derived count**, "passed with every stage on its first attempt", by
the definition the plan's section 5 held word for word before slot 1: group
A, 4 of 10; group B, 4 of 10. It is a description of trials on the default
fingerprint, from the same records at this read. In every one of the twenty
trials every stage that was seated records one attempt, so in each group
the trials counted here are the trials that passed. It changes no main
figure and is not a result on a one-attempt harness.

**Each trial.** "Attempts" lists the recorded attempts of the four stages in
order (`requirements`, `interface-spec`, `microarchitecture`,
`rtl-implementation`); "not run" is a stage the flow did not seat. "Own
flow digest" is the trial's recorded `flow_digest`, by its first 8 hex
digits. "Run beside" is the slot whose run had jobs running together with
this slot's run (see "Two at a time" below).

| Slot | Group | Run | Commit | Run beside | Trial | Attempts | Own flow digest |
|---|---|---|---|---|---|---|---|
| 1 | A | 45315168823 | `1e9c560b` | slot 2 | failed, judged | 1, 1, 1, 1 | `a1aea0d3` |
| 2 | B | 45315184979 | `1e9c560b` | slot 1 | failed, judged | 1, 1, 1, 1 | `b8608ede` |
| 3 | A | 45318904373 | `1e9c560b` | slot 4 | passed | 1, 1, 1, 1 | `a1aea0d3` |
| 4 | B | 45323667674 | `881a77d9` | slot 3 | failed, stopped | 1, 1, 1, not run | `9d94c405` |
| 5 | A | 45330921164 | `29399c1a` | none | passed | 1, 1, 1, 1 | `a1aea0d3` |
| 6 | B | 45337185043 | `3e615771` | none | passed | 1, 1, 1, 1 | `b8608ede` |
| 7 | A | 45343158122 | `2f0dfc01` | none | failed, stopped | 1, 1, 1, not run | `4ff378d2` |
| 8 | B | 45351486006 | `3eedbff3` | none | passed | 1, 1, 1, 1 | `b8608ede` |
| 9 | A | 45367262139 | `90fabb76` | none | failed, stopped | 1, 1, 1, not run | `4ff378d2` |
| 10 | B | 45375624519 | `9b31bd27` | none | failed, stopped | 1, 1, 1, not run | `9d94c405` |
| 11 | A | 45382857575 | `1bcff2ae` | none | passed | 1, 1, 1, 1 | `a1aea0d3` |
| 12 | B | 45390568718 | `9cdf3ad6` | none | failed, stopped | 1, 1, 1, not run | `9d94c405` |
| 13 | A | 45397981621 | `47061e02` | none | failed, stopped | 1, 1, not run, not run | `a89b7aa8` |
| 14 | B | 45408522143 | `8c969f2a` | none | passed | 1, 1, 1, 1 | `b8608ede` |
| 15 | A | 45418598815 | `ec219a1f` | none | failed, judged | 1, 1, 1, 1 | `a1aea0d3` |
| 16 | B | 45428397475 | `3e97fbfe` | none | failed, stopped | 1, 1, 1, not run | `9d94c405` |
| 17 | A | 45440516870 | `508e55ff` | none | passed | 1, 1, 1, 1 | `a1aea0d3` |
| 18 | B | 45448895134 | `68bf6c3e` | none | passed | 1, 1, 1, 1 | `b8608ede` |
| 19 | A | 45458015129 | `6f102a46` | none | failed, stopped | 1, 1, 1, not run | `4ff378d2` |
| 20 | B | 45467216245 | `e058183a` | none | failed, stopped | 1, 1, 1, not run | `9d94c405` |

Each slot's commit is the `head_sha` of its record's manifest and the commit
of its reach index. The commits differ because records and reach folders
merged between dispatches; that the dispatch check of the plan's section 7
ran before every dispatch is the account of the dispatcher's operator; what
the repository shows is that from `1e9c560b` to `904bb511` nothing changed
outside `evals/results/g3-timer/` and `capability/levels.json`, and that
every record carries the case digest, the fingerprint, the CLI and the
per-stage skill digests of its arm, for each stage it seated. No slot ran on
a second value of any pinned group.

### The failed trials, by label

**Trials whose flow stopped before its last stage.** Each is a failed trial
of its group: no judge ran on it, and it is counted as decision F2 says.
Its own flow digest, in the table above, is the plan's digest over the
stages it seated (section 24.2), beside the group's. In each, the stage
named has no check, its recorded status is `escalated`, it records one
attempt and one model call, and no answer of the trial records an error. In
the words of decision P4:

| Slot | Group | The read's words |
|---|---|---|
| 4 | B | stopped at `microarchitecture`: the seat escalated; cause not established |
| 7 | A | stopped at `microarchitecture`: the seat escalated; cause not established (an inference: on the status of its upstream inputs under the pass-through) |
| 9 | A | stopped at `microarchitecture`: the seat escalated; cause not established |
| 10 | B | stopped at `microarchitecture`: the seat escalated; cause not established |
| 12 | B | stopped at `microarchitecture`: the seat escalated; cause not established (an inference: on the status of its upstream inputs under the pass-through) |
| 13 | A | stopped at `interface-spec`: the seat escalated; cause not established |
| 16 | B | stopped at `microarchitecture`: the seat escalated; cause not established (an inference: on the status of its upstream inputs under the pass-through) |
| 19 | A | stopped at `microarchitecture`: the seat escalated; cause not established |
| 20 | B | stopped at `microarchitecture`: the seat escalated; cause not established |

The inference is given only where the escalation's own recorded text (the
stage's `note` in the trial record) names the review or approval status of
its upstream inputs: slots 7, 12 and 16. Decision P4 leaves the inference
optional, and the read gives it nowhere else.
None of these trials is labelled "model", the failure-to-curriculum rule
does not apply to them, and none is said to show a gap in a skill (decision
P4). No count is stated from which they are left out, and no figure is
stated for a stage.

**Trials that reached the judge and failed.** In each, every stage was
seated, the before-review checks of `rtl-implementation` passed, and the
first held-out check, "The reference testbench passes on the flow's RTL",
passed. The second held-out check, "The flow's testbench passes on the
reference RTL and fails each timer mutant", failed, as the record's `scores`
state:

| Slot | Group | Label | What the record's `scores` state |
|---|---|---|---|
| 1 | A | model | the flow's testbench passed on the reference RTL (judge run `run-0005`), three mutants failed it (judge runs `run-0006` to `run-0008`) and one mutant survived it; the score's summary names the surviving mutant's run as `run-0009`, which the record's `judge_runs` does not list (run 45315168823) |
| 2 | B | model | the flow's testbench passed on the reference RTL (judge run `run-0005`), three mutants failed it (judge runs `run-0006` to `run-0008`) and one mutant survived it; the score's summary names the surviving mutant's run as `run-0009`, which the record's `judge_runs` does not list (run 45315184979) |
| 15 | A | model | the flow's testbench did not pass on the reference RTL (judge run `run-0005` of run 45418598815) |

The label "model" is the label of the trial, given by verification-lead at
this read from the record: every stage was seated, the stage's own checks
passed, the judge ran and re-judges the same, and the fixed requirements
document states what the flow's testbench must do. It names no stage and no
skill; at which stage the rule was lost is not established. No `causes.md`
is committed beside any failed slot's record at `904bb511`, so
`scripts/failure_curriculum.py` lists every failed trial of the timer case
as unlabelled.

The failure-to-curriculum rule (retrospective, decision 7; the plan's
section 9) applies to the trials of slots 1, 2 and 15. The answer is owed
and is not given here. verification-lead gives it in a pull request of its
own, which commits a `causes.md` beside each failed slot's record, with the
labels and words of this read unchanged, and states for each of the trials
of slots 1, 2 and 15 a knowledge note, a must-fail case or a written reason
why not, naming the failing run. A change it makes to a card or a document
merges only outside a batch's freeze, the re-measure batch's included, and
one to a skill given to a register block stage is listed in the register
block's dated addition, as section 9 says. This read changes no card and no
document.

**The include listing** (the plan's section 18.5). For each passed trial
(group A: slots 3, 5, 11 and 17; group B: slots 6, 8, 14 and 18), no HDL
file a seat wrote, in any stage's recorded answer at any attempt, holds an
`` `include `` directive.

### Two at a time

- **The width.** Two, as the plan's section 24.6 fixes it. It was never
  raised.
- **That runs overlapped, and that no two trials' own times did.** Decision
  T5, item 3 asks the read to say that trials overlapped. By the committed
  records no two trials' own times overlap (next bullet). What overlapped
  are runs: the runs of slots 1 and 2 had jobs running together, and so had
  the runs of slots 3 and 4, two adjacent slots, one of each arm, each time.
  From slot 5 to slot 20 no run had a job running while another slot's run
  did. This is read from the job times GitHub holds for the run ids above.
  They are not a committed record of this repository; a reader can check
  them by run id. This read reads those times and states none.
- **What the committed records show.** Among the committed slot records, no
  two manifests' times (`started_at` to `finished_at`, the time of the trial
  itself) overlap, so the committed test of decision T5, item 2
  (`tests/test_whole_flow.py`) holds at `904bb511` with no overlapping pair
  to check. The trials of slots 1 and 2, and of slots 3 and 4, ran inside
  runs that had jobs running together. Nothing about any result is
  concluded from this bullet or the one above.
- **The point from which the batch ran at width one.** There is none. No
  trial ended on a plan or usage limit, was interrupted, or ended with no
  model answer (no answer in any of the twenty records carries an error),
  so the rule of section 24.6 was never applied and no slot ran after such
  a point. That one run ran at a time from slot 5 is not that
  rule: clause (c) of gate ET15 (section 24.9) holds slot k until the reach
  folders of slots k-3 and lower are on `main`.
- **Order.** Slots were first dispatched in strictly increasing slot order.
  No slot was dispatched after a higher one, and no slot was dispatched a
  second time: the workflow's runs between the dispatch of slot 1 and the
  end of slot 20's run are exactly the twenty runs above, each a first
  attempt, each dispatched from `main`.
- **Stop events.** No trial stopped the batch: there was no limit, no
  interrupted trial, no trial with no model answer, no job-level stop, no
  record that was not the trial asked for, no re-judge that did not finish
  or did not hold, no reach gate that failed, no finding of section 24.9,
  item 2, no record or file over the review's size limit, no run of the
  workflow that the dispatcher did not start, and no run whose id could not
  be bound. Dispatch was closed twice by the dispatcher's own check under
  section 24.9, item 3, each time with no slot in flight:
  1. After slot 4 had finished and before slot 5 was dispatched. The branch
     the dispatcher had pushed for the reach records of slot 2's run no
     longer resolved to the commit the dispatcher had written down. The
     branch held one more commit, a merge of `main` made when that branch
     was the head of the pull request ip#504 and the review loop updated
     it. The reach files were equal by digest to the index, and they are
     the files on `main`. The branch was added to, not rewritten: the
     written commit stayed its ancestor. Security reads it as no security
     event. Dispatch resumed after ip#504 merged. For slots 3 to 19 the pull
     request of a run's reach records was opened from a branch of its own,
     made at the pushed commit and never forced, so the branch the
     dispatcher checks was not a pull request's head; the review loop
     updated those pull request branches, and the files' digests were
     checked again before each merge by the test of gate ET16. No dispatch
     followed slot 20, so the dispatcher pushed no branch for it; its pull
     request, ip#542, was opened from one commit that adds the run's five
     files and was not updated.
  2. After slot 18 had finished and before slot 19 was dispatched. The
     dispatcher read back the branch it had just pushed for slot 18's run
     before GitHub served it, and found no branch. The branch resolved to
     the pushed commit when read again, and dispatch resumed. The dispatcher
     was changed to read such a branch again for a bounded time; a branch at
     any other commit still fails at once. Security reads it as no security
     event.
  The two closes are the account of the dispatcher's operator, from tooling
  that is outside this repository; no committed record holds them; of the
  first, GitHub shows the two commits of ip#504, the second a merge of
  `main`. Section 24.9, item 3 is a rule for whatever dispatches, not a
  control.
- **Cancelled, held out, run again.** No run was cancelled before its trial
  under the one cancel of section 24.8. No running trial was cancelled.
  Nothing was held out and nothing was run again: twenty dispatches, twenty
  runs, twenty records.

### What a later stage is sent

The words of the pass-through note were changed before slot 1 by the sixth
addendum (ip#487): the note now says who made the record. A later stage is
sent what the plan's section 24.4 states, as a replay of the reference
answer with no model shows it: each upstream output rendered as approved,
and the harness's own review of it rendered as a `review_record`,
substantiated, "Independent review by" the reviewer's role, with the whole
note, beside the constitution's P6 and P7 and the system prompt's words on
claims and escalation. The change is not described as a fix shown to work,
and this read states no rate of any kind for it.

### Gates WF29 and WF40

Both gates rest on the dispatcher, which is tooling outside this repository.
What follows is each gate owner's ruling on what may be said of it here, in
the owner's words.

**Gate WF29** (owner: eda-tooling). The dispatching script is outside this
repository. This paragraph is the account of its operator and the gate
owner's own read of the script, its tests and its output; it is not a
repository control and no committed record holds it. Before slot 1 the
operator made the showing that the plan's section 24.2 and decision F3, item
5 ask of the script, on the record of run 45295715357, the measured run of
section 24.3, which is the run the gate's owner names. The copies were the
four that item 5 names, and each was refused for the change made to it. The
output is kept private because it prints stage names. Nothing more is said
of that record, and nothing of its stages, attempts or outcome follows: the
check of decision F3, item 3 passes a record whose flow seats every stage
and a record whose flow stops alike.

What the committed records show, and a reader can check on `main` at
`904bb511`: each of the twenty slot records meets the four items of the
check of section 24.2 against that section's two tables for its arm: the
stage names and their order; the seated stages first and every later stage
"not run" with no skills, attempts, model calls or gate runs, and in a
stopped trial every stage before the last seated one completed and the last
seated one not; each seated stage's skills and digests, exactly; and a flow
digest equal to the one recomputed from its own seated stages and to the
table's digest over that number of stages. The trials whose flow stopped
(slots 4, 7, 9, 10, 12, 13, 16, 19 and 20) were each committed as a failed
trial of its slot and none stopped the batch, as decision F3, item 4 says.
The gate's owner recomputed this from the committed files with a script of
its own, not the dispatcher's; it shows the records, not the script.

**Gate WF40** (owner: ai-engineer). Gate WF40 held from slot 1 to slot 20.
The committed records and GitHub's run list show: each slot has one run and
one record, whose manifest and reach index name that run and its commit;
every run is a first attempt dispatched from `main`; none was cancelled; and
the workflow has no other run between the dispatch of slot 1 and the end of
slot 20's run. So every trial dispatched is committed, nothing was run
again, no run existed that the dispatcher did not start, and no running
trial was cancelled. No trial ended on a limit, was interrupted, or ended
with no model answer, so the width was never lowered. That each run was
bound to its slot from the response to its dispatch, and that the window was
held, is the account of the dispatcher's operator; the run list is
consistent with it. The dispatcher is tooling outside this repository. Its
operator reports that it carried a test of its own for each element of the
seventh addendum's build specification, item 4, passing before slot 1; that
it was changed at each of the two closes above, with no slot in flight, in
nothing this gate names; and that after the second change its tests, with
one added for it, passed again. The gate's owner read the dispatcher, its
tests and its ledger and did not run them. This is the operator's account
and not a control of this repository; no committed record holds it.

### What is not said

Under the plan's sections 11 and 24.12 and decisions T5, F5, P4 and P6, this
read does not say, and no text may draw from it: that running two at a time
had an effect on a result, or that it had none; that the interleave makes
the two arms comparable, or any figure for a pair of trials whose runs
overlapped; that the timer and any batch that ran with one trial in flight
ran under the same dispatch conditions; which concurrency group a run used,
as a fact of that run; a count from which stopped trials are left out; that
a stage fails at some rate; that documents help, or do not, beyond the two
counts side by side with their intervals; a combined figure; a level, a
score or a bar; the timer case as independent verification; anything of
either measured run; or any time, usage or cost figure. The twenty trials
are "the timer case's twenty trials", and every statement of either count
carries "the register block case has not run".

### Seat statements

Five seats read the draft of this addendum, each as a read-only process of
its own that saw no other seat's answer: verification-lead, qa-evidence,
eda-tooling, ai-engineer and security. Each checked the facts of its own
item against the committed records at `904bb511`; eda-tooling, ai-engineer
and security also read the private dispatcher, its tests and its ledger, and
none ran it. The chair took every correction the seats asked for; where two
seats worded the same sentence, the owner's wording stands. No seat
dissented from the read.

- **verification-lead** (owner of the read). States this read as the timer
  case's read: 4 of 10 with documents and 4 of 10 without, each 0.1682 to
  0.6873; the register block case has not run. It rebuilt the per-slot table
  from the twenty records, confirmed the label "model" for slots 1, 2 and 15
  and the inference for slots 7, 12 and 16 only, and owes the answer under
  the failure-to-curriculum rule as written above. Its narrower reading of
  decision P4's "state of its upstream inputs" (review or approval status)
  is its own and is marked so. For a later pull request, outside a batch: a
  surviving mutant's run is not carried into a record's `judge_runs`; the
  verdict is still held by the re-judge.
- **qa-evidence** (gates WF26, WF30 and WF41). Passed the read with nine
  corrections, all taken: the include listing for passed trials only; no
  count of failed or labelled trials across the two arms; the pull request
  numbers; the overlap stated of runs and not of trials, from GitHub's job
  times, named as not a committed record; the dispatch check as the
  operator's account; the full list of stops that did not occur; and the two
  closes kept, as the operator's account. It read the filled text of "Gates
  WF29 and WF40" and of this section before the merge (the pull request
  carries that read).
- **eda-tooling** (gate WF29). Gate WF29 was met before slot 1, on the
  record its owner names; the words above are the words it allows. Recorded
  at its request: the gate rests on a private tool and on the owner's
  private read, so it is a seat's statement and not a control, and
  eda-tooling would rather the check lived in the repository for the
  register block. Before slot 21 the dispatcher must refuse to dispatch the
  register block without that case's per-stage values, and the showing of
  decision F3, item 5 is owed again on them. Its dissents recorded in the
  addenda above stand and are not reopened.
- **ai-engineer** (gate WF40). Gate WF40 held, in the words above. The read
  changes this record only, so no fingerprint and no pinned value moves; it
  recomputed both whole-flow fingerprints at `904bb511` and they equal the
  table above. Its recorded dissent, a group per run for the timer, stands
  as recorded; this read gives no ground for or against it and is not cited
  either way (decision T5, item 4).
- **security** (gates WF36, WF39 and ET15). Gate ET15 as the plan's section
  24.9 words it held before every dispatch as far as the records show: the
  commit of each slot k holds the reach folder of every slot k-3 or lower,
  equal by digest to its index; every reach record holds only denied probes;
  no reach gate failed and no artifact is missing; and nothing under
  `.github`, `scripts` or `src` changed on `main` between slot 1's commit
  and `904bb511`. Clauses (a) and (b) at the moment of each dispatch rest on
  the dispatcher's private ledger. Neither close is a security event. No
  dissent. A note for the founder is under "Open".

### Outcome

The timer case is read: 4 of 10 with documents and 4 of 10 without, each
with the interval 0.1682 to 0.6873, on the groups named above; the register
block case has not run. This was the one read of the timer case. There is
no top-up, extension, replacement or second read.

### What remains, as already planned

- The register block's twenty slots (21 to 40) wait for their own gates and
  for the dated plan addition that states their values. Until that case is
  read, every statement of a timer count carries "the register block case
  has not run".
- The trials labelled "model" are owed their answer under the
  failure-to-curriculum rule (verification-lead), outside any batch's
  freeze.

### Open, for the founder

1. This read and its outcome, to confirm or overrule.
2. For information, from security, on item 3 of the seventh addendum's open
   list (a repository rule for the branches that hold reach records before
   they merge): a rule that blocks only rewriting and deleting would not
   have stopped the first close above, since an update merge is neither. If
   the founder sets a rule before slot 21, it would restrict updates to the
   dispatcher's own branches and leave the pull request branches open to
   the review loop. No gate rests on it.
