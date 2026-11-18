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

**Both testbench copies strengthened again (follow-up).** Another independent
check passed mutants through both copies: a write decode ignoring `addr[1]`,
offsets with bit 5 or bit 7 set aliasing at `ADDR_WIDTH` 8, an `irq` that
drops after 20 cycles, `CTRL` bits above 2 that read back, and a read decode
ignoring `addr[0]` on the register block. Each copy now drives every unmapped
address, holds `irq` high for 100000 cycles, writes every bit and every strobe
alone, runs long counts, stops and gaps, and leaves a write's address and data
unknown while they are not offered; the timer's stop value is now judged
(`TMR-STOP-EDGE`). The author swept every judged tag of both documents with
its own scratch mutants before asking for review. The documents are unchanged,
and both still wait for a fresh check. The register block testbench's check
that `AWREADY` is high in reset is not stated by the single-seat interface
specification, and is left for a decision.

**Not here.** The runner option (its `runner.py` dispatch waits for the H3
batch, gate WF1).
