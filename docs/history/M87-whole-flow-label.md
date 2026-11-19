# Milestone 87 - Whole-flow cases: the label and the list

Item G3 of the capability build-out, first pull request of the council record
`council/records/2026-11-17-g3-whole-flow-cases.md` (decision 1, decision 3
"The label and the list", gate WF2). Design: `docs/WHOLE_FLOW.md`. Tests:
`tests/test_whole_flow.py` and the whole-flow section of
`tests/test_capability_levels.py`.

**The gap.** The levels credited every skill a case names. Only three labels
took a trial out (knowledge off, a calibration purpose, a harness variant), so
a whole-flow record that named skills would have been credited.

**The label.** `flow: whole` on the case, the run manifest and the trial.
Either the manifest's label or the trial's alone takes a trial out of the
levels, checked before every other label. The record's name is never read.

**The list.** `whole_flow` in `capability/levels.json`, by group (case digest,
model, harness, CLI, flow digest, purpose), every trial listed; the
whole-flow pass count is written only from 10 trials. A mixed record is
refused. A whole-flow case names no skill and lists what it exercises
apart, the second lock.

**No change for a run without the label.** Single-seat cases, manifests and
trials dump as before, so no case digest changes; no file in `harness.CODE`
is touched, so the default, attempts-3 and tools-in-loop fingerprints are
unchanged. A whole-flow case is in no default case set, and `record_run`
refuses one until the whole-flow runner exists.

**The cases (second pull request).** `flow/axil-timer` and
`flow/axi4-lite-regs-driver` under `evals/flow/`, a new tagged timer
requirements document, the register block's own copies of its requirements,
driver interface and held-out test, a citation file per case, and the
fixtures for the controls. A test settles fact 10: a document given through a
case's `inputs` never reaches the requirements seat as text.

**The judge controls (third pull request).** `evals/flow/controls.json`, 20
replays through the real gates and scorers with no model call, run in CI
(`tests/test_whole_flow_controls.py`), and their recorded CI run in
`evals/flow/controls_record.json`. They confirm by a run that `b_before_w` is
not visible through the HAL and that the reference driver test makes the
same bus transfers on both RTLs. (Their text first said that no driver test
can see latency; the council record's addendum of 2026-11-18 narrowed that to
`read32` and `write32` on this block, shown by the harness's construction and
the run together.)

**What a driver test can reach (gate WF14, follow-up).** The reach guard
(`tests/test_nirmaan_firmware_reach.py`) pins the HAL, the two harness
headers, each host manager's exports and includes, and the Verilator options;
the wait probe (`driver-wait-probe`) is the 21st control, recorded passing on
both RTLs with the same bus transfers; `docs/WHOLE_FLOW.md` and the
`driver-reference` text are corrected. The addendum's open question is
answered by a CI test: a driver test's C reaches Verilator's runtime by a
mangled symbol and can read the simulation time.

**The object screen (gate WF16, follow-up).** The council record's second
addendum asks for a tripwire on seat-written C before the first register block
trial. Two scorers, `screened-held-out-run` and `screened-must-fail`, compile
a check's C as `fw.test` does and refuse it, as a failed check with nothing
run, on an undefined symbol off the allow list, a definition of a harness or C
library name, code outside the tests (constructors, destructors, indirect
functions) or asm in the seat's own lines; otherwise they run the unchanged
scorers. The allow list, one refused fixture per construct, the clock probe
and the address-arithmetic probe are recorded from CI. No tool definition,
harness code or fingerprint changed. It stops names, not address arithmetic:
the recorded probe, starting from `hal->read32`, read the harness's cycle
count, its pass counter and the run's nonce. The register block case's checks
4 to 7 then took the screen in a second pull request, and the control follows
the channel: the strict fixtures of WF15 on the simulator's clock are refused
by the screen (files kept, expected results changed, recorded), and two strict
fixtures on the address-arithmetic route, which stays open, are the live
controls (27 controls).

**The timer document fixed, and the check record rule (follow-up).** An
independent check found that `evals/flow/axil_timer/requirements.md` claimed
tags its checks do not reach and left rules open (readiness one way only, the
response edge, the read value, `COUNT` after a stop and on a `CTRL` write at a
count end). The document now states each rule exactly as the reference RTL
does, splits every partly reached rule, and lists the unreached parts as not
judged. Each flow requirements document gets a check record by another
session (`requirements_check.json`), held by a test; both documents wait for
theirs.

**Both documents fixed again (follow-up).** A second independent check, with
mutants that pass the reference testbenches, found tags still claimed beyond
what is judged in both documents. Each case's check 1 now runs its own copy of
the single-seat reference testbench (`evals/flow/axil_timer/axil_timer_tb.v`,
`evals/flow/axi4_lite/axi4_lite_regs_tb.v`), which keeps every check of the
original and adds the missing ones: RDATA held still while a running `COUNT`
is read, a clear on the edge a one-shot count ends, a reset with `EXPIRED`
set, a new request accepted in the cycle after a response is taken, and reset
while a response waits or half a write is held. The single-seat cases keep the
originals, so their digests and recorded trials stay as they are. The
parameter defaults, the timer's widths 5 to 7 and the "no other ports" rules
have their own tags, listed as not judged. Both documents wait for a fresh
check.

**The strict fixtures (gate WF15, follow-up).** The record's second addendum
of 2026-11-18 found the fixture driver test owed again: a driver test's C
reads the simulation time through Verilator's runtime. Four controls add a
strict fixture driver test (fails check 7 on the reference RTL by its one
timing check only), a strict fixture driver (passes check 5 on the conforming
RTL, fails check 6), and the SoC's cycle counter refused before review, each
on a flow whose RTL stage ended in the conforming RTL. The record keeps the
cycle counts.

**Both testbench copies strengthened again (follow-up).** Another independent
check passed mutants through both copies: a write decode ignoring `addr[1]`,
offsets with bit 5 or bit 7 set aliasing at `ADDR_WIDTH` 8, an `irq` that
drops after 20 cycles, `CTRL` bits above 2 that read back, and a read decode
ignoring `addr[0]` on the register block. Each copy now drives every unmapped
address, holds `irq` high for 100000 cycles, writes every bit and every strobe
alone, runs long counts, stops and gaps, and leaves a write's address and data
unknown while they are not offered; the timer's stop value is now judged
(`TMR-STOP-EDGE`). The author's mutant sweep is a committed check record,
`evals/flow/<block>/mutant_sweep.json`: every mutant `tests/flow_mutants.py`
builds (74 for the timer, 29 for the register block, one tag each, every tag
check 1 cites covered) fails the copy, and the conforming RTLs pass;
`tests/test_whole_flow_cases.py` holds the record to the builders and reruns
one mutant per tag. The fresh check the documents wait for is still owed. The documents are unchanged,
and both still wait for a fresh check. The register block copy drops the original's
check that `AWREADY` is high in reset: only the single-seat microarchitecture
states it, and `AXIL-TEST-RANGE` holds a testbench to what the document states,
so a conforming flow block must not fail it. The
copy test now allows only named exemptions, each with its reason.

**The runner option.** Part 4a, the dispatch edit to `runner.py` and the
fingerprint entries, merged in the window after the H3 batch. With it, a
`runtime/context.py` and `runtime/prompt.py` change gives a customer document
to its task's seat as text, citable as a document. Part 4b is
`evals/flow.py`: every stage seated, the pass-through with a true note, a
failed stage stops the flow, the per-stage record, the flow digest, the label
from the case, and the whole-flow stop rule.

**The CI path (step 5).** Whole-flow cases run in the live evaluation's own
jobs (`.github/workflows/live-eval.yml`, M89's seat account, reach test, tree
hashes and separate re-judge job), named by ID, one trial per dispatch, on
the default harness, in the whole-flow fingerprint, each record checked for
`flow: whole`. A `flow/` case adds the RISC-V cross compiler and fails if any
tool is missing. Every such job also runs the credential test for seat C
under `fw.test` (`scripts/live_eval_fw_reach.py`) and uploads its result; it
is recorded, not a gate, because `fw.test` still runs seat C as the runner.
So the register block flow stays refused live (exit 6) and only the timer
flow runs. Design: `docs/WHOLE_FLOW.md`, "The CI path".

**Not here.** The batch plan and the trials, after wave 2's first live
batch is read.
