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
| WF6 | The dispatch edit to `runner.py` merges after WF1 is met and before the pull request that names the default harness, or else only with a later change that restarts every group for another reason; the flow module may merge later; the runner option carries the true pass-through note, the per-stage record and a clean re-judge test | eda-tooling |
| WF7 | A test shows the flow module's edit changes the whole-flow fingerprint and not the default; from the pull request that names the default harness onward, no whole-flow pull request changes the default fingerprint, shown by that test on each one | ai-engineer |
| WF8 | The stop rule of decision 3 is shown by a test before any whole-flow trial | qa-evidence |
| WF9 | Both cases run only in the named CI job, default harness, one attempt; the job fails on a changed checkout; the record is re-judged from a fresh checkout before the read; the credential test is recorded before the first register block trial | security |
| WF10 | Forty trials, fixed in a committed plan before the first; never beside wave 2's first live batch; one read; no re-run counts | verification-lead |
| WF11 | The count is stated only as k of n with its interval, per group, at ten or more planned trials complete; never pooled, never called a level; case (a) is never described as independent verification | qa-evidence |
| WF12 | No whole-flow figure or measure name on the site, the README or the landing brief from this record; a later one needs a committed record, key 1 review and the founder's answer on the name | product-lead |
| WF13 | The whole-flow job renames or skips no required check, adds no third-party action, pins actions by SHA, passes inputs through `env`, and the weekly scheduled run excludes whole-flow cases | eda-tooling |

## Open, for the founder

1. This ruling, to confirm or overrule.
2. The public name of the measure, if it is ever to appear outside the
   repository's records. Inside them it is "whole-flow pass count".

## Addendum (2026-11-18): no strict driver test when latency is not visible

This addendum states one part of the chair's ruling of 2026-11-17 that the
record above leaves out, and points to the run that part asks for. It adds
no decision of its own. It changes no code, case, record or level, and no
gate's wording.

### Who decided what

- The chair ruled the part below on 2026-11-17, in its follow-up to decision
  2 on the same day, together with the whole-range rule (decision 2, "Judge
  controls", fourth item, and gate WF4). It was written into the internal
  build notes for the code lane and not into this record. That was an
  omission in the record, corrected here.
- `council/README.md` gives no process for an addendum to a record. No seat
  was convened for this one: it decides no new question, and it follows the
  addendum of 2026-11-15 to
  `council/records/2026-11-14-pilot-retrospective.md`, which was added
  without convening seats for it and changed no decision. Like the ruling,
  it is not a founder decision, and the founder can overrule it.
- Owners are as in the ruling: firmware-engineer (driver checks and
  controls, gate WF5), verification-lead (the controls as a rule, gate WF4).

### The part left out

Decision 2 asks for a fixture testbench and a fixture driver test written to
the conforming RTL's one choice, each failing on the reference RTL. The
chair's ruling went on, in substance: if a driver test cannot observe latency
through the HAL at all, that is recorded by a run; then no strict driver test
exists, checks 6 and 7 cannot fail for being stricter than the latency bound,
and the controls record says so.

So the strict driver test is owed only if a driver test can see latency. If a
recorded run shows that it cannot, the fixture driver test is dropped from
decision 2's controls and from what gates WF4 and WF5 ask for; the strict
testbench stays. This holds while the HAL gives a driver test no clock and
no cycle count.

### The run

Pull request #324 (merged 2026-11-18) recorded it in
`evals/flow/controls_record.json`, control `driver-reference`, from CI run
44236131264 on 2a87386:

- The reference driver and driver test pass on the reference RTL (6 checks,
  45 cycles, 20 bus transfers) and on the conforming RTL
  `tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v` (6 checks,
  65 cycles, 20 bus transfers). The two RTLs differ in cycles; the test sees
  the same transfers.
- `tests/test_whole_flow_controls.py`
  (`test_the_control_gets_the_verdict_it_expects`) fails unless the bus
  transfers logged by those two runs are identical, on every CI run. The
  record keeps each run's verdict and summary, not the transfers themselves.
- `src/nirmaan/integrations/firmware_harness/nirmaan_hal.h` gives a driver
  test `read32` and `write32`, each returning a response code, and nothing
  else: no clock and no cycle count.

The condition is therefore met, and no strict driver test is owed. The
statement itself is not a field of the record file: it is in the
`driver-reference` entry of the controls manifest, `evals/flow/controls.json`,
whose verdicts the record holds, and in `docs/WHOLE_FLOW.md` ("Freedom left
open", and the judge controls list). The strict testbench control is in the
record (`regs-tb-strict2`: check 3 fails on the reference RTL).

This addendum closes no gate. What WF4 still needs from the whole-flow runner
(the reference flow through every seated stage, a planted upstream fault, and
check 5) is unchanged.
