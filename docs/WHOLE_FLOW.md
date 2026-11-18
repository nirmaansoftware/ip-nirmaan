# Whole-flow cases (G3, M87)

Source: `council/records/2026-11-17-g3-whole-flow-cases.md` (gates WF1 to
WF19, with its two addenda of 2026-11-18), which applies decision 6 of the
pilot retrospective
(`council/records/2026-11-14-pilot-retrospective.md`). A whole-flow trial puts
a request in, seats every work stage with the model, and judges only the final
block. It credits no skill and no level.

The record splits the build into pull requests. This document grows with them.

## The label and the list (M87)

**The case.** `EvalCase.flow` is `"seat"` (every case so far) or `"whole"`. It
is a property of the case, inside its digest; it is neither a harness variant
nor a command-line flag (decision 3). A whole-flow case names no skill in
`skills` and fixes no upstream stage (`upstream` is empty: every work stage is
seated). It lists the skills each seated stage exercises in `exercised`
(stage to skills), which nothing credits. `validate_case` refuses a whole-flow
case that names a skill, fixes a stage, lists nothing exercised, or lists a
skill outside the catalog or a stage outside the planned workflow, and a
single-seat case that lists anything exercised.

**Two locks.** The label takes the trial out of the levels; the empty `skills`
means the existing rule credits nothing even if a label is lost.

**The trial and the manifest.** `EvalTrial.flow` and `EvalRunManifest.flow`
carry the label. `EvalTrial.stages` (one `EvalStage` per seated stage: task,
role, the actors that submitted, reviewed and approved it, status, attempts,
gate runs, the skills given with their digests, model calls, tokens and the
pass-through note) and `EvalTrial.flow_digest` are defined here and filled by
the whole-flow runner (a later pull request).

**Nothing changes for a single-seat run.** A case, manifest or trial whose
`flow` is `"seat"` dumps exactly as before these fields existed (they are left
out at their defaults), so no case digest changes and no record file gains a
key. No file in `harness.CODE` is touched, so no harness fingerprint changes.

**The reader.** `levels.practised()` checks the label first, before the
calibration, ablation and variant labels and before the skill loop: either the
manifest's label or the trial's alone puts the trial under `whole_flow` in
`capability/levels.json`, and nowhere else. The record's name is never read. A
record that mixes whole-flow and single-seat trials is refused
(`records.is_whole_flow`). A replay or an attested whole-flow record is
refused as any other.

**The listed count.** Trials are grouped by case, case digest, model, harness,
CLI version and flow digest, and by purpose, so a calibration trial is never
pooled with evidence. Arms are apart already: a run without knowledge is a
different harness. Every trial is listed one by one with whether a judge ran.
A group's "whole-flow pass count" (`count`: `n`, `passed`, `unjudged` and the
95 percent Wilson interval) is written only from `WHOLE_FLOW_MIN` (10) trials;
whether the planned count of the group is complete is the committed batch
plan's (decision 4), which this file does not hold. A trial no judge ran on is
a failed trial of its group. The count is never a level, a score or a bare
percentage, has no bar, is never in the totals and is never pooled across
groups (WF11).

**Default case sets.** `load_cases(root)` returns single-seat cases only;
`flow="whole"` or `flow=None` asks for the others. So `eval run`, the levels
and the shipped-case checks never see a whole-flow case, and the weekly or any
default run cannot pick one up. Until the whole-flow runner is merged,
`record_run` refuses a whole-flow case before it writes anything: a whole-flow
case never runs as a single-seat case.

Tests: `tests/test_whole_flow.py` and the whole-flow section of
`tests/test_capability_levels.py`.

## The two cases (M87, second pull request)

Both live under `evals/flow/` and load only with `load_cases(..., flow="whole")`.
Nothing existing is edited: the single-seat cases and their files keep their
digests (WF3).

| Case | Request | Seat (judged) | Fixed inputs | Checks |
|---|---|---|---|---|
| `flow/axil-timer` | "Create an AXI4-Lite timer peripheral with an interrupt." | rtl-implementation (RTL and its testbench) | `evals/flow/axil_timer/requirements.md` (new) | 2 |
| `flow/axi4-lite-regs-driver` | "Create an AXI4-Lite register block and its driver." | firmware | `evals/flow/axi4_lite/requirements.md`, `evals/flow/axi4_lite/driver_api.md` (the case's copies) | 7 |

**The fixed documents.** The timer document is new: it states, as behaviour
at the ports, every rule the reference testbench checks and every rule a
mutant breaks, each with a `[req:TMR-...]` tag. The register block document is
a copy of `evals/spec/axi4_lite/requirements.md` with tags on section 1, a
section 4, and three rules split or made exact so that each tag states only
what is judged (`AXIL-NO-PROT`, `AXIL-PARAMS-DEFAULT`, `AXIL-B2B`). Both state the rule that binds the flow's own tests: a test accepts
every behaviour the document allows and never requires one choice inside a
range (`TMR-TEST-RANGE`, `AXIL-TEST-RANGE`). The driver interface copy says the
offsets and reset value are the requirements document's and that the map
header must agree with the approved RTL; it never says "from the interface
specification" or "derived from the RTL" (decision 2, "Where the register map
comes from").

**Citations.** `evals/flow/<block>/citations.json` (a data file, never a case)
names, for every held-out check and every mutant, the tags or headings of the
fixed documents it rests on, and lists under `not_judged`, with the reason,
every tag no check or mutant rests on: the tags the RTL stage's own gates
cover (`TMR-CLEAN`, `AXIL-SYNTH`, `AXIL-FORMAL`), and the timer rules the
reference testbench never exercises. Where the testbench reaches only part of
a rule, the rule is split and the unreached part has its own tag, listed as
not judged: the parameter defaults (`TMR-ADDR-WIDTH-RANGE`, which also holds
the timer's widths 5 to 7, and `AXIL-PARAMS-DEFAULT`), "no other ports"
(`TMR-PORTS-ONLY`, `AXIL-NO-PROT`), and, for the timer, readiness (`TMR-READY`), the read value at the accepting edge
(`TMR-READ-VALUE`), `COUNT` while a count runs (`TMR-COUNT-READ`), a periodic
`LOAD` of 0, a `CTRL` write on a count
end (`TMR-CTRL-WINS`), the edge `irq` changes on after a write, what a
synchronous reset does to a pending response or a held half write
(`TMR-RESET-EDGE`), and the testbench checking every requirement
(`TMR-TB-ALL`; the must-fail check holds it only to the four mutants). A test
checks both ways: each cited tag or heading exists, and each tag is cited or
listed.

**The reference testbenches.** Each case's check 1 runs its own copy of the
single-seat reference testbench: `evals/flow/axil_timer/axil_timer_tb.v` and
`evals/flow/axi4_lite/axi4_lite_regs_tb.v`. A copy keeps every check of the
original, in order and word for word, except the named exemptions in
`TB_COPY_EXEMPT` (`tests/test_whole_flow_cases.py`), and adds the checks an independent
check found missing: for the timer, RDATA held still while a running `COUNT`
is read under backpressure, a `STATUS` clear on the edge a one-shot count
ends, and a reset while `EXPIRED` is set; for the register block, a new
request accepted in the cycle after a response is taken, and reset while a
write or read response waits or with only the address or only the data of a
write accepted. A second round, after another independent check, added for
the timer: every port's width, each `LOAD` strobe alone and none, `CTRL` bits
31:3 and `STATUS` bits 31:1 reading as zero, a write and a read at every
unmapped address (all 256 at `ADDR_WIDTH` 8) with nothing changed, `irq` held
high through 100000 cycles and through writes that neither clear `EXPIRED`
nor write `IE` 0, timed counts of 300 and 65539 cycles, the value a stop
leaves in `COUNT` from all 32 bits of `LOAD` (so `TMR-STOP-EDGE` is now
judged), thirty periods and periods of 300, write halves 40 cycles apart,
and 40 cycles of backpressure; and a write that leaves its address, data and
strobes unknown while it does not offer them. For the register block: every
register bit, each strobe alone, a write and a read at every unmapped address,
write halves 40 cycles apart, back-to-back requests after responses that
waited on `READY`, and no response valid after the first reset edge. A rule
over time ("stays high until", "any gap", "until `EN` is written 1 again") is
checked over these bounded runs, as any simulation checks it. The single-seat
cases keep running the originals, so their digests, and the recorded trials
that hold those digests, stay as they are. The one exemption is the register block original's "AWREADY in reset"
check: no flow document states READY during reset, the
single-seat interface specification does not require it, and only the
single-seat `microarchitecture.md` does (line 74, a design choice given to
that seat), while in a whole flow the RTL stage writes its own
microarchitecture, so a conforming block may hold `AWREADY` low in reset.
`AXIL-TEST-RANGE` says a testbench checks
only what the document states, and the judge assumes only behaviour the fixed
document states (the council record, lines 206 to 208); so a conforming block
must not fail it. The
original keeps it; a block that holds `AWREADY` low in reset passes the copy
and fails the original (shown by run in ip#339). A test holds both, and fails on any other dropped or
altered check.

**The held-out tests.** The register block case's held-out test is its own
copy of the firmware case's, with an unmapped (misaligned) write added, so the
`okay_unmapped` mutant is visible through the driver. Check 5 runs on the
flow's own RTL with its top from the RTL stage's declared entry; the whole-flow
runner resolves `rtl_source` from that stage.

**Freedom left open.** The register block document allows a response 1 or 2
cycles after its request. `tests/fixtures/rtl/axi4_lite/variants/` holds a
second conforming RTL that answers after 2 (`axi4_lite_regs_lat2.v`) and a
testbench written to that one choice (`axi4_lite_regs_tb_strict2.v`). The timer
document leaves no choice open: its readiness, response timing, count length
and every response are exact (the timer's interface specification already
fixed them, and the reference testbench times a write to the edge,
`evals/flow/axil_timer/axil_timer_tb.v` lines 395 to 398), so the timer has no
conforming variant and no strict testbench. A driver test that uses only
`read32`, `write32` and the driver interface cannot be strict about latency on
this block: each call returns only after the response, with the data and the
response code, and nothing in the block depends on elapsed cycles. That is
shown by the harness's construction, which the reach guard pins (gate WF14,
below), and by the judge controls' run together, not by the run alone. But the
HAL is not all a driver test can reach, so the register block has a strict
fixture driver test and a strict fixture driver after all (the record's second
addendum of 2026-11-18, gate WF15, below).
`nirmaan_irq_wait(seen, cycles)` (`nirmaan_irq.h`) lets cycles pass,
and the harness ends a run at 5000000 cycles. A test that spends cycles near
that limit fails the slower RTL, never the reference, which answers in the
fewest cycles the document allows; so the limit cannot make a test that fails
the reference RTL for latency. A test's host C can also reach the host C
library and the simulator's runtime, and through the runtime the simulation
time (below).

**Fixtures for the controls.** Three wrong drivers (a swallowed bus error,
`write_byte` with every strobe, a sticky `last_response`) under
`tests/fixtures/fw/axi4_lite/`, and a weak timer testbench
(`axil_timer_tb_weak.v`, named `_weak`, not `_tb_fail`, since it passes on the
reference RTL, unlike every `_tb_fail.v` in `docs/IP_BLOCKS.md`; both lanes at
`ADDR_WIDTH` 4, so `decode_alias` passes it).

**The requirements seat (fact 10, settled).** A file given through a case's
`inputs` is task memory: it parameterizes the task's tools and is never
rendered into a prompt (`runtime/prompt.py`), and the requirements task builds
on no stage, so no approved upstream file carries it either.
`tests/test_whole_flow_cases.py` shows neither the document's text nor its
path reaches the requirements seat. Putting the document into the request text
is no way out: the planner then reads other features from it
(`existing_design`, `width_change`, `performance`), which changes what each
seat is given. So the document is to be given another way:
`runtime/context.py` carries task memory `document.<name>` (`<digest> <path>`)
into that task's packet as an upstream file of kind `customer_document`,
marked as customer input, whole, citable (as a `document`, never an artifact,
so the provenance check never refuses a draft that cites it) and withheld once
its bytes change. Only the platform may write it (no seat answer writes
memory, and the CLI and the eval runner write only `input.` keys), only the
task it is given to sees it, and no single-seat case gives one, so their
prompts are byte for byte as before
(`tests/test_flow_requirements_document.py`). The whole-flow runner (part 4b)
gives the fixed documents to the requirements stage this way and is the only
writer of a `document.` key, so its trials are seated at every stage, never
"seated from interface-spec". `runtime/context.py` and `runtime/prompt.py` are
`harness.CODE` files, so this change merges in the window with the dispatch
edit.

## The judge controls (M87, third pull request)

Gates WF4 and WF5 need each case's judge proven by replays with no model call,
run in CI, before the first trial. `evals/flow/controls.json` lists 25
controls. Each is a seat answer made of committed files and the whole-flow
case's own held-out checks it must pass or fail, sometimes with the RTL a
check runs on put in another's place. `tests/test_whole_flow_controls.py` runs
each as a single-seat case through the real runner, gates, scorers and broker
(`evaluate`), with no change to `runner.py`: the seat replays the files, its
own before-review checks run, and the judge rules. A control's seat reaches
review, so a failed check is the judge's verdict. The tool-backed tests need
the EDA tools; CI's test job names them in `NIRMAAN_REQUIRE_EDA`, so there they
run and never skip.

What they show:

- the reference passes: the timer's checks 1 and 2, the register block's
  checks 1 to 3, and checks 4, 6 and 7 for the reference driver;
- each planted fault fails: the reference testbench fails a flow ending in
  each register block mutant and in three of the timer mutants; the fourth,
  `decode_alias`, is refused by the seat's own lint gate, so that flow stops
  before review (the reference testbench catching it is shown by the must-fail
  check of `timer-reference`); the weak timer testbench and a testbench that
  checks next to nothing fail the must-fail checks; the held-out test fails
  the wrong map header under the map's name, the three wrong drivers, and the
  reference driver on `wstrb_ignored` and `okay_unmapped`;
- the conforming RTL (`axi4_lite_regs_lat2.v`) passes the checks that run on
  the flow's RTL (1 and 2; check 5 runs on it only in the strict driver's
  control, below), and the held-out test passes on it;
- the range-accepting reference tests pass on both RTLs, and the testbench
  written to the variant's one choice fails check 3 on the reference RTL.
  Known limit: check 3 runs the flow's testbench on the reference RTL alone,
  so a testbench strict about the reference's own choice (a response exactly
  1 cycle after its request) passes it, though it fails on the conforming
  RTL. No change: the council record accepts this, since checks 3, 6 and 7
  are "fair by the rule, which the fixed document states to the seats, and
  not by the conforming RTL alone"
  (`council/records/2026-11-17-g3-whole-flow-cases.md`, lines 301 to 303);
- `fw.test` works under the must-fail scorer (check 7: the clean run passes
  and `wstrb_ignored` and `okay_unmapped` are caught);
- `b_before_w` is not visible through the HAL: under the must-fail scorer
  with that mutant alone, the reference driver test passes on it. The ruling
  assumed so and left it out of check 7; this run records it;
- the reference driver test passes on both RTLs with the same bus transfers.
  That shows one test. That a driver test that uses only `read32`, `write32`
  and the driver interface cannot be strict about latency on this block rests
  on the harness's construction (the reach guard) and this run together;
- the wait probe (`driver-wait-probe`, gate WF14): a driver test that calls
  `nirmaan_irq_wait` between transfers passes on both RTLs with the same bus
  transfers, an attempt to see latency that does not;
- the strict fixtures (gate WF15, section below): a driver test and a driver
  that are strict about latency through the simulator's clock pass on the
  conforming RTL and fail checks 7 and 6 on the reference RTL, and the SoC's
  cycle counter is refused before review.

Each control prints one `FLOW-CONTROL` line with its verdicts and run
summaries. `evals/flow/controls_record.json` keeps those lines from a named
CI run (the check record, not an eval record), and the test holds every later
run to the verdicts it records.

Left for the whole-flow runner: the reference flow replayed through every
seated stage, a flow with a planted upstream fault, and check 5, which takes
the RTL from another stage.

## What a driver test can reach (gate WF14)

The council record's addendum of 2026-11-18 replaced decision 2's fixture
driver test for the register block with three things, which gate WF14 asks
for before the first register block trial:

- **The reach guard.** The guard tests in
  `tests/test_nirmaan_firmware_reach.py` need no tool. They pin, as exact
  lists: the members of `nirmaan_hal` and every declaration of
  `nirmaan_hal.h` and `nirmaan_irq.h`; the external definitions of each
  host manager (`axil_manager.cpp`, `apb_manager.cpp`: the six `extern "C"`
  functions and `main`; everything else, and all of `harness_report.h`, is in
  an anonymous namespace); the files in the harness directory, which is on a
  driver test's include path; the registered managers; the headers each
  harness file includes; and the literal options of the Verilator build. Any
  addition, or an edit to a listed declaration, fails with the return
  condition in its message. (The same file's simulator test, below, needs the
  firmware tools and runs in CI.)
- **The wait probe**, the control above, recorded in
  `evals/flow/controls_record.json`.
- **The return condition.** The fixture driver test is required again, before
  the next trial, for any case where the HAL or the harness gains a cycle
  count, a timeout or a non-blocking access that a driver test can read, or
  where the block has a register whose value depends on elapsed cycles, or
  where the fixed document leaves open a choice visible in data or response
  codes.

The addendum left open whether a simulator symbol is reachable from a test's
C. It is. Under `fw.test` a driver test is host C linked into one image with
the harness and Verilator's runtime, and C can name a C++ symbol by its
mangled name. `tests/fixtures/fw/reach/simulator_clock_probe.c` reads
`Verilated::s_lastContextp`, the harness's own simulation context, finds the
simulation time in it, and times a `read32` and a `write32` in cycles: each
takes more cycles on `axi4_lite_regs_lat2.v` than on the reference RTL. The
tool-backed test in the guard file runs it on both RTLs, in CI only. This is
neither a HAL call nor the driver interface. The guard pins the files,
declarations and build options it lists; it closes nothing, and it does not
pin the simulator's version, which also decides the symbols. The second
addendum decided what follows: the fixture control is owed again (gate WF15,
below), and what a driver test's host C may reach is for gates WF16 to WF18.

## The strict fixtures (gate WF15)

The record's second addendum of 2026-11-18 (decision 1) withdrew the first
addendum's "the control is empty for this block" and requires, before the
first register block trial, a strict fixture driver test and a strict fixture
driver, and for each route by which a recorded probe reads a cycle count
either the route refused or a strict fixture using it recorded failing. Four
controls in `evals/flow/controls.json` do this. Each is a flow whose RTL stage
ended in the conforming RTL: the control's `upstream_rtl` replaces the base
case's upstream RTL with a copy of `axi4_lite_regs_lat2.v` under the
reference's file name, so the seat's own checks run on it before review, as
they would in a whole flow, and check 5 runs on it.

- `driver-strict-latency-test`: the reference driver with
  `tests/fixtures/fw/axi4_lite/axi4_lite_regs_test_strict_latency.c`, the
  reference driver test plus one named check,
  `read32_and_write32_take_the_conforming_rtls_cycles`. It reads the
  simulation time through `Verilated::s_lastContextp`, as the reach probe
  does, times one `read32` and one `write32`, and passes only at the
  conforming RTL's counts. It passes on that RTL, and check 7 fails it on the
  reference RTL by that one check: the test asserts the run built, finished
  with the harness's summary, reported no harness error, and failed no other
  check, and that its bus transfers equal those of the run on the conforming
  RTL.
- `driver-strict-latency-driver`: `axi4_lite_regs_drv_strict_latency.c`, the
  reference driver except that it times every transfer the same way and
  reports one that took other than the conforming RTL's count as a bus error,
  with the reference driver test. It builds alone (check 4), passes check 5
  on the conforming RTL and fails check 6.
- `driver-strict-soc-cycles` and `driver-strict-soc-address`: the same
  strict test on the other route, the SoC run's `NIRMAAN_SOC_CYCLES`
  register, once named through `nirmaan_soc.h` and once by its address
  copied into the test. The case's checks run on host co-simulation
  (`fw.test`); its request names no RISC-V, so no `fw.soc_test` check runs.
  The first is refused when the seat's own `fw.test` check builds it (the
  header is not on the include path); the second kills the co-simulation
  with signal 11 before any harness record is written out, which `fw.test`
  reports as "build failed before co-simulation: 0 errors (exit status -11)"
  although the build was clean. Neither reaches review.

Each strict fixture prints what it timed on a line of its own
(`STRICT-FIXTURE ...`). The `FLOW-CONTROL` line carries those lines per
check, a control that never reaches review carries its gate runs, and the
record keeps both; the counts are in the manifest as expected values, and
every later run is held to them. The fixture files stay when a route is
closed; their expected result then changes to the refusal, in a recorded run.
These are judge controls written by the platform. No model-written driver
test has used either route.

## The document check record (M87, follow-up)

A fixed requirements document is a contract, so a session other than its
writer checks it, and the check is kept next to it as
`evals/flow/<block>/requirements_check.json` (format
`nirmaan.flow-document-check`): the case, the document's path and sha256, the
writer and the checker, when it was checked, the sources read, the evidence
for each tag (`path:line`, a test id, or `unjudged`) and the result. The
tags marked `unjudged` must be the case's `not_judged`, and the result must be
`holds`. Any edit to the document makes the record stale, and a flow
requirements document with no record fails, so every edit gets a new check.
An author never writes the record for its own document.

`tests/test_whole_flow_cases.py` holds every `evals/flow/*/requirements.md`
to this. Until a document's first record lands it is listed, with the reason,
in `evals/flow/requirements_check_pending.json` (a data file); its test still
runs and checks that it has no record yet, so the entry must go when the
record lands, and a document neither listed nor recorded fails. No test
skips. Both documents are listed now: independent checks failed both, each more than once,
with mutants that pass the reference testbenches, and each was fixed by
stronger checks in the case's own reference testbench and by splitting what
stays unjudged into its own tags; neither has passed a fresh check yet. Another test
shows the rule refuses a stale record, a record whose checker is its writer,
a missing tag, a tag marked unjudged that a check cites, unreadable
evidence, and a result that does not hold.

## The runner option, part 4a: the dispatch

`evals/runner.py`'s `evaluate` sends a whole-flow case to
`nirmaan.evals.flow.evaluate` with every argument as given (the case, the
seat runtime with its recorder, the repository, the sandbox, the clock, the
attempts, the knowledge setting and the variant) and returns its result and
engine, so the flow module needs no second edit to `runner.py`. While the
module is absent the dispatch refuses the case with a plain message. The
fingerprint's `run` section says `flow: whole` and its `flow` section digests
`harness.FLOW_CODE`, for a whole-flow run only (`docs/HARNESS.md`). This is
the one edit that changes every fingerprint; it merges only after the H3
batch's last trial is recorded and before the pull request that names the
default harness (WF1, WF6).

## The runner option, part 4b: the flow module

`src/nirmaan/evals/flow.py` (`harness.FLOW_CODE`, digested only in a
whole-flow run's fingerprint) seats every work stage in dependency order with
one seat runtime and one recorder, through the unchanged `run_task`, so each
stage's own before-review checks run for real.

- **Inputs.** A stage gets the case's fixed inputs as task inputs and as
  customer documents (`document.<name>`), so the requirements seat reads them
  as text and its trials are seated at every stage.
- **Pass-through.** Review and approval of every stage but the last are done
  by the harness as `eval-flow-passthrough`, never the fixture, with the note
  "Whole-flow evaluation: not reviewed. Before-review checks passed: <runs>."
  or "... This stage has no before-review check: submitted, not checked." The
  words "reviewed in the repository" are never used.
- **A stage that does not reach review** stops the flow. Later stages are
  recorded "not run", every held-out check is not run, and the trial is a
  failed trial of its group. There is no fallback to a reference document.
- **The judge.** Only the final block is judged. Each check runs under the
  stage that produced the first kind it takes from the seat (so its tool runs
  under a role that may run it) and sees every seated stage's files. A check
  that takes its `top` from `seat_entries` reads it from the producing stage's
  own runs, so check 5 runs on the flow's RTL with the RTL stage's top. The
  held-out-run scorer now honours `seat_entries` (only the whole-flow case
  uses them there).
- **The record.** The record's name ends in `-whole-flow`, and the manifest
  and every trial carry `flow: whole`, all from the case: no option sets or
  clears it. A run never mixes whole-flow and single-seat cases. Each trial
  keeps one `EvalStage` per stage (task, role, the actors that reviewed and
  approved it, status, attempts, gate runs, the skills given with their
  digests, model, calls and tokens, the note), the sums over all stages, the
  attestations of any stage, and the flow digest. The flow digest is sha256
  over the sorted (stage, skill, skill digest) of every skill each seated
  stage was given, in the trial's arm.
- **A test stricter than the contract.** When the clean run of a must-fail
  check fails (the flow's own test on the reference block), or a check with no
  mutants fails on a case file while the same tool on the flow's own file
  passes (check 6 against check 5), the trial's detail names the candidate
  cause "a flow test stricter than the contract", as an inference, not a fact.
  A must-fail check whose mutants survive is a weak test and is never called
  stricter.
- **The stop rule (WF8).** A live whole-flow run stops right after a trial
  whose last recorded answer has no text and an error (`flow_stopped`). The
  single-seat rule (`no_model_answer`) is unchanged.
- **Replay.** A replay answers each stage with the case's reference files of
  the kinds it outputs (`FlowReplayLLM`). `eval run` runs a whole-flow case
  only when it is named, and `eval rejudge` finds it.

Tests (`tests/test_whole_flow_runner.py`):
- the reference flow of both cases passes every check and re-judges clean;
- a flow ending in a mutant RTL fails, and a flow with the wrong map fails
  checks 5 and 6;
- a flow on the conforming RTL passes, with check 5 on the RTL stage's top;
- a flow whose second stage never answers is a failed trial with the later
  stages and every check not run;
- the requirements seat's prompt carries the fixed document;
- a testbench written to the conforming RTL's one choice is named "stricter
  than the contract" as an inference, and a plain fault never is;
- the stop rule fires on (text, text, no text and an error) and not on three
  answers;
- the whole-flow fingerprint digests this module.

## Gate status

The council record's gates are its own
(`council/records/2026-11-17-g3-whole-flow-cases.md`, WF1 to WF13); this
section only records, with dates, what the repository can show about them.

- WF1 (no `CODE` change before the H3 batch's last trial is recorded),
  2026-11-18. The H3 runner recorded its last slot, slot 69 of 69, at
  2026-11-18T07:12:47Z; its ledger's last line reads "ALL DONE
  2026-11-18T07:12:47Z: 69 slots, 66 done, 2 interrupted (slot 1 SIGKILL, slot
  44 Mac reboot), 1 stopped (slot 35 plan limit)". That ledger and the
  frontier-case records, slot 69's among them, are private (the record's fact
  15); this rests on the orchestrator's account. The batch's pilot-case
  records reach `main` by pull request in six parts (ip#332 and ip#333 are
  open at this date); none is merged yet, so `main` holds no H3 record today.
  The `CODE` changes made after it: the dispatch edit, ip#330, merged at
  13:28Z (merge commit 91cb482), and the customer-document change, the second
  half of the same window (decision 4).

## The CI path (step 5 of the build; WF9, WF13, WF17)

Both cases run in the live evaluation's own jobs,
`.github/workflows/live-eval.yml` (`docs/LIVE_EVAL_EVIDENCE.md`, section 6):
one CLI pin, one tool set, the seat account and its reach test, the tree hash
around the trials and the counting re-judge in a job of its own on a fresh
checkout. No new workflow and no new action.

- **Named, one trial per dispatch.** `scripts/live_eval_ci.py` knows a
  whole-flow case only by its ID (`flow/axil-timer`,
  `flow/axi4-lite-regs-driver`). It refuses `trials` other than 1 and a
  harness other than `default` for one, so each dispatch is one slot of the
  batch plan and the arms can be interleaved by dispatch order.
- **The fingerprint** it checks is the whole-flow one
  (`harness_sha256(flow="whole")`, digesting `harness.FLOW_CODE`), and every
  record must carry `flow: whole` as well as the purpose, knowledge label,
  variant, fingerprint and CLI asked for. The single-seat fingerprints are
  unchanged.
- **One tool set.** For a `flow/` case, `.github/actions/live-eval-setup`
  also installs the RISC-V cross compiler that `ci.yml` installs (RV32I
  multilib checked) and fails if any of `verilator`, `iverilog`, `vvp`,
  `yosys`, `sby`, `yices-smt2`, `cc`, `make`, `riscv64-unknown-elf-gcc` or
  `cocotb-config` is missing. Single-seat cases get the tool set they had.
- **The credential test for seat C** (decision 4; second addendum,
  decision 2, item 1). Every job that runs a `flow/` case runs
  `scripts/live_eval_fw_reach.py` after the cocotb reach test and before the
  checkout is hashed. It compiles a driver test in C for this run and runs it
  through `fw.test`'s co-simulation backend on the reference register block,
  under a parent process that holds two canaries in its real environment
  (one under `CLAUDE_CODE_OAUTH_TOKEN`). Its tests try to run as the runner,
  run `sudo -n`, create a file in the checkout, the installed package and the
  records folder, find a canary in any `/proc/<pid>/environ`, read its
  parent's environment at all, read a runner-only file and signal the
  harness; a control writes its own run directory. The result is uploaded as
  `live-eval-fw-reach-<job>-<run id>`. It is recorded, not a gate:
  `fw.test` runs seat C by path, as the runner. `--require-denied` makes it
  a gate.
- **The recorded result** (`evals/flow/credential_test_record.json`, run
  44401041085, job `replay`, head feda503): every probe not denied. The C ran
  as the runner (uid 1001), `sudo -n true` exited 0, it created a file in the
  checkout, `src/nirmaan`, `scripts`, `evals`, `site-packages` and the records
  folder, it read its parent's `/proc/<pid>/environ` holding both canaries
  (the credential-named one included), its own environment held the plain
  one, and it read the runner-only file and could signal the harness. So the
  register block flow waits, as below.
- **The register block flow stays refused.** Its firmware stage and its
  held-out checks run seat C, so `check --require-expected` and `trials`
  refuse it with exit 6 before any trial, as M89 refuses the single-seat
  firmware case. It runs live only once `fw.test` builds and runs seat C as
  the seat account (a harness change, after wave 2's first live batch is
  read), the credential test then shows every probe denied and is switched to
  a gate, and gates WF15 to WF19 are met. A replay of it still runs: its code
  is the reference answer.
- **The timer flow** links no seat C (its checks and stages run HDL, and its
  testbenches run in `vvp` as the seat account), so it runs live now.

## Not yet

The committed batch plan (WF10) and the trials, after wave 2's first live
batch is read.
