# Whole-flow cases (G3, M87)

Source: `council/records/2026-11-17-g3-whole-flow-cases.md` (gates WF1 to
WF13), which applies decision 6 of the pilot retrospective
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
a copy of `evals/spec/axi4_lite/requirements.md` with tags on section 1 and a
section 4. Both state the rule that binds the flow's own tests: a test accepts
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
not judged: readiness (`TMR-READY`), the read value at the accepting edge
(`TMR-READ-VALUE`), `COUNT` while a count runs (`TMR-COUNT-READ`), a periodic
`LOAD` of 0, the value the stop edge gives `COUNT`, a `CTRL` write on a count
end (`TMR-CTRL-WINS`), the edge `irq` changes on after a write, what a
synchronous reset does to a pending response or a held half write
(`TMR-RESET-EDGE`), and the testbench checking every requirement
(`TMR-TB-ALL`; the must-fail check holds it only to the four mutants). A test
checks both ways: each cited tag or heading exists, and each tag is cited or
listed.

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
`axil_timer_tb.v` lines 380 to 383), so the timer has no conforming variant
and no strict testbench. No strict driver test exists either: the HAL a driver
test calls (`nirmaan_hal.h`) has no clock or cycle count, so a driver test
cannot see latency; the judge controls record this by a run.

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
path reaches the requirements seat. Putting the document into the request
text is no way out: the planner then reads other features from it
(`existing_design`, `width_change`, `performance`), which changes what each
seat is given. So the document is given another way: `runtime/context.py` carries task
memory `document.<name>` (`<digest> <path>`) into that task's packet as an
approved upstream file of kind `customer_document`, whole, citable (as a
`document`, never an artifact, so the provenance check never refuses a draft
that cites it) and withheld once its bytes change. Only the platform writes it (no seat answer
writes memory, and the CLI writes only `input.` keys), only the task it is
given to sees it, and no single-seat case gives one, so their prompts are byte
for byte as before (`tests/test_flow_requirements_document.py`). The
whole-flow runner gives the fixed documents to the requirements stage this
way, so its trials are seated at every stage, never "seated from
interface-spec". `runtime/context.py` is a `harness.CODE` file, so this change
merges in the window with the dispatch edit.

## The judge controls (M87, third pull request)

Gates WF4 and WF5 need each case's judge proven by replays with no model call,
run in CI, before the first trial. `evals/flow/controls.json` lists 20
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
  the flow's RTL (1 and 2; check 5 waits for the runner), and the held-out
  test passes on it;
- the range-accepting reference tests pass on both RTLs, and the testbench
  written to the variant's one choice fails check 3 on the reference RTL;
- `fw.test` works under the must-fail scorer (check 7: the clean run passes
  and `wstrb_ignored` and `okay_unmapped` are caught);
- `b_before_w` is not visible through the HAL: under the must-fail scorer
  with that mutant alone, the reference driver test passes on it. The ruling
  assumed so and left it out of check 7; this run records it;
- no driver test can see latency: the reference driver test passes on both
  RTLs with the same bus transfers, and the HAL has no clock or cycle count.
  So no strict driver test exists, and checks 6 and 7 cannot fail for being
  stricter than the latency bound.

Each control prints one `FLOW-CONTROL` line with its verdicts and run
summaries. `evals/flow/controls_record.json` keeps those lines from a named
CI run (the check record, not an eval record), and the test holds every later
run to the verdicts it records.

Left for the whole-flow runner: the reference flow replayed through every
seated stage, a flow with a planted upstream fault, and check 5, which takes
the RTL from another stage.

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
skips. Both documents are listed now: the timer document was rewritten after
an independent check found tags its checks do not reach and rules it left
ambiguous, and the register block copy has never been checked. Another test
shows the rule refuses a stale record, a record whose checker is its writer,
a missing tag, a tag marked unjudged that a check cites, unreadable
evidence, and a result that does not hold.

## Not yet

The runner option (its
dispatch edit to `runner.py` waits for the H3 batch, gate WF1), the record
name suffix, the flow digest and the stop rule are later pull requests of the
same record.
