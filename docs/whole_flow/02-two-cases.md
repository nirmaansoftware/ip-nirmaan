# The two cases (M87, second pull request)

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
(`TMR-PORTS-ONLY`, `AXIL-PORTS-ONLY`, `AXIL-NO-PROT`: a simulation sees no
port it does not connect), and, for the timer, the read value at the
accepting edge (`TMR-READ-VALUE`), `COUNT` while a count runs
(`TMR-COUNT-READ`), a `CTRL` write on a count end (`TMR-CTRL-WINS`), what a
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
waited on `READY`, and no response valid after the first reset edge. A third
round (decision #37), after a third independent check, closes classes instead
of single findings: each copy ends with a coverage matrix. Writes run in every
ordering (address and data together, address first, data first) at every
address class (each register, every unaligned offset, and for the timer at
`ADDR_WIDTH` 8 offsets from `0x10` up with each high bit) with every `wstrb`
value; reads run at every address class with `READY` late by 0 to 2 cycles;
writes and reads alternate `OKAY` and `SLVERR` back to back; and a write and a
read overlap, either first, each response waiting while the other completes.
For the timer, a protocol monitor judges `READY` and the response edges on
every edge of the run (so `TMR-READY` is now judged), one-shot and periodic
counts with `LOAD` 0, 1, 2, 37 and `0x0001_0005` are checked edge by edge
against `STATUS` clears landed on every phase (so `TMR-LOAD-ZERO-PERIODIC` is
judged), restarts, stops and `LOAD` writes land in the middle of a count in
both modes, `CTRL` is written with every strobe and with `EN` 0 and 1 while
running and stopped, and `irq` is checked after the very edge of an `IE`
write or a clear (`TMR-IRQ-EDGE`). For the register block, the overlap holds
the latency bound for both directions, which the reference meets. "No other
ports" is split out of `AXIL-PORTS` as `AXIL-PORTS-ONLY`, not judged. A rule
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
must not fail it. The original keeps it. A block that holds `AWREADY` low in
reset (`tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_awready_low_in_reset.v`)
passes the copy and fails the original on that check
(`tests/test_whole_flow_cases.py::test_a_block_holding_awready_low_in_reset_passes_the_flow_copy_and_fails_the_original`).
A test holds both, and fails on any other dropped or altered check.

**The mutant sweep record.** `evals/flow/<block>/mutant_sweep.json` (format
`nirmaan.flow-mutant-sweep`, a data file) records the sweep run on each
testbench copy: every mutant `tests/flow_mutants.py` builds from the reference
RTL (99 for the timer, 40 for the register block), the tag each violates, its
sha256, and its result, all failing; the reference and the conforming RTLs
(`axi4_lite_regs_lat2.v` and the `AWREADY`-low block) pass.
`test_each_sweep_record_matches_its_builders_and_fails_every_tag_the_testbench_check_cites`
rebuilds each mutant and compares its sha256, holds the record to the
testbench copy and reference RTL by sha256 (an edit to either makes it stale),
and requires a failing mutant for every tag check 1 cites;
`test_one_mutant_per_tag_fails_the_testbench_copy_and_the_conforming_rtl_passes`
runs one mutant per tag, and the conforming RTLs, with the simulator.

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
