# Design for Test, next steps (Milestone 29)

Status: design for the owner's review, implemented on branch `m29/dft-next`.
It extends `docs/DFT.md` (M25) and `docs/DFT_ADVANCED.md` (M27) with three
items M27 deferred: transition (at-speed) fault ATPG, lockup latches on chains
that cross clock domains (and ATPG across capture edges), and an MBIST stage
in a workflow. Prose here is free of em and en dashes per the standing style
law.

As before, every run is real: Yosys synthesizes, Icarus simulates, and the
steps in between are standard-library Python (`dft_scan.py`, `dft_atpg.py`,
`dft_mbist.py`) that read only what the tools wrote. It works on Yosys 0.33 and
Icarus 12 (CI) as well as current releases.

---

## 1. The laws

M21, M23, M25, and M27's laws hold unchanged:

1. **Never fake work.** A missing executable is a refusal with the reason; a
   design that fails is a recorded run with `succeeded=False`. Transition
   coverage, like stuck-at coverage, is what an Icarus fault simulation
   measured. A shift across clock domains is correct because a simulation
   with skewed clocks shifted through it, not because a latch was inserted.
2. **Data over code.** The new tool, the two new request features, the MBIST
   stage, and the new evidence are records in `company/`. The runtime names
   none of them.
3. **Registries.** The new tool is a `register_backend(Backend(...))`; the
   crown-jewel test shows a new transition-fault generator needs no core
   change.

---

## 2. Transition faults: `dft.atpg_transition`

### 2.1 The fault model

A **slow-to-rise** (STR) fault on a net delays its rising transitions by one
clock cycle; **slow-to-fall** (STF) delays its falling ones. The universe is
STR and STF on every site of the M27 stuck-at universe (every controllable
input and gate output of the capture model, uncollapsed), named `net/STR` and
`net/STF`.

### 2.2 The protocol: launch on capture

Launch on capture (LOC, also called broadside):

1. Shift the load in with `scan_en` high (slow), and apply the primary inputs.
2. `scan_en` low. **Launch** pulse: the flops take their next state; the
   transitions start.
3. **Capture** pulse, one cycle later (at speed): the flops capture the second
   next state. The primary outputs are compared just before it.
4. Shift the capture out while the next load shifts in.

Primary inputs are held through launch and capture (a tester cannot change
them at speed), so a transition on a primary input cannot be launched: those
faults are proven undetectable, not counted as missed. Launch on shift (LOS)
is deferred (section 7).

### 2.3 Generation: two time frames

`dft_atpg.py generate --model transition` unrolls the capture model into two
frames. Frame 1 is the capture model on the loaded state; frame 2 is a copy of
it whose flop outputs are frame 1's next state and whose primary inputs are
frame 1's (held). A transition fault on net n is then a stuck-at fault on n's
frame-2 copy (STR: stuck at 0) with a condition on frame 1 (STR: n is 0 there).
The M27 generator runs unchanged over that model: random patterns with the
condition as a mask in the bit-parallel fault simulation, then PODEM, which
gains conditions (a goal before activation, a dead end when violated), so an
exhausted search is still a proof.

### 2.4 Measurement: a delay in the faulty copy

`dft_atpg.py inject --model transition` writes the fault netlist with, at each
site, a one-cycle delay: a flop (on a new clock input `nirmaan_fault_clk`,
pulsed with the design's clocks) holds the net's previous value, and the site
becomes `net & prev` (STR) or `net | prev` (STF), selected by
`nirmaan_fault_val[s]`. It applies only while `nirmaan_fault_en[s]` and a new
input `nirmaan_fault_atspeed` are high. The testbench raises
`nirmaan_fault_atspeed` just after the launch edge and lowers it just after
the capture edge, so the delay acts in the one at-speed cycle and never during
the slow shift. Everything else is M27's grader: the design as given is the
good machine, the expected responses and the injection are checked first, a
claim the simulation does not bear out fails the run, and the coverage is the
simulation's.

### 2.5 Capture edges

Transition ATPG needs every flop to capture on one edge of the pulse (M27's
restriction); a design with both is refused with the reason (section 3.4
lifts it for stuck-at only).

### 2.6 Measured coverage

Generated pattern pairs, graded by the Icarus fault simulation (Yosys 0.69,
Icarus 13; the full universe, no sampling). Every fault not detected was
proven undetectable under launch on capture (the primary inputs, which are
held, and logic whose transitions the second frame cannot observe), so test
coverage is 100% on each:

| Block | Chains | Transition faults | Detected | Proven undetectable | Fault coverage | Test coverage |
|---|---|---|---|---|---|---|
| `counter` | 1 | 70 | 53 | 17 | 75.7% | 100% |
| `atpg_demo` | 2 | 132 | 87 | 45 | 65.9% | 100% |
| `rr_arbiter` | 2 | 116 | 92 | 24 | 79.3% | 100% |

Each takes under a second of Icarus. The `block-design` gate (section 5) asks
for 80% test coverage.

### 2.7 Parameters

As `dft.atpg`: `patterns`, `min_<metric>` (for example `min_test_coverage`),
`max_<metric>`, `fault_sample`, `seed`.

---

## 3. Chains across clock domains

### 3.1 Why a lockup latch

M27 never let a chain cross a clock domain, so shift was always within one
clock. A chain that crosses from a flop on `clk_a` to a flop on `clk_b` is a
hold race: if `clk_b`'s edge arrives after `clk_a`'s, the receiving flop takes
the new value and a bit is lost. A **lockup latch** between them, clocked by
the launching flop's clock and transparent at the level before its active edge
(a negative-level latch after a rising-edge flop), holds the old value for
half a cycle, which covers any skew below half a cycle.

Mixed edges of one clock need ordering, not a latch: in a pulse the first
edge's flops capture first, so a second-edge flop must not load a first-edge
flop (the bit would race through two flops in one pulse). Chains put
second-edge flops first.

### 3.2 Insertion: `cross_domains=lockup`

`dft.scan_insert` gains `cross_domains`. Absent, chains are per domain as in
M27. With `lockup`:

1. Flops are ordered by capture phase (second-edge domains first), then
   domain, then M27's natural name order.
2. That one sequence is cut into `chains` (or `max_chain_length`) balanced
   pieces, so chains may cross domains.
3. At each place a chain passes from one clock to another, the stitcher adds a
   lockup latch (`$_DLATCH_N_` after a rising-edge flop, `$_DLATCH_P_` after a
   falling-edge one) between the launching flop's Q and the next flop's scan
   input.

The chain report lists each lockup (chain, from, to, cell, clock).

### 3.3 Checking and proving the shift

`Design` recognizes a lockup latch: a latch whose D is a flop's Q and whose
enable is a module input. It is not a design latch for `no-latches` (unless it
reaches capture-mode logic, which a lockup never does), and the chain tracer
follows it. `scan-chain-complete` now reports, per chain:

* a transfer between flops on different clocks with no lockup latch, or a
  lockup latch on the wrong clock or with the wrong polarity;
* a second-edge flop that loads a first-edge flop.

`dft.scan_sim` proves the shift. With more than one clock, the shift test runs
three times: clocks together (as M27), then **skewed** with each clock's
edges 1 ns after the previous clock's, then skewed in the reverse order. Every
crossing so sees its receiving clock both late and early. Without a lockup
the late case loses a bit, which the testbench reports as shift mismatches;
with one, all three pass. The capture check keeps the clocks together.

### 3.4 ATPG across capture edges

M27 refused ATPG when flops capture on both edges of the pulse. Stuck-at ATPG
now models the pulse as two phases, as `dft.scan_sim` already does: the
second-edge flops' next state is computed from a copy of the logic whose
first-edge flop outputs are their new values. A stuck-at fault is then a fault
on both copies of its net (PODEM and the bit-parallel simulation take several
sites). Chains that cross domains shift through their lockups in the fault
simulation. The refusal stays, with the reason, for a chain the tracer does
not accept (no lockup, wrong order, broken) and for transition ATPG over two
capture edges.

---

## 4. MBIST in a workflow

### 4.1 `dft.mbist` finds the memories

`top` becomes optional. Yosys reads the design (with `top`, or
`hierarchy -auto-top`), and every module in the elaborated hierarchy with the
single-port interface (`clk`, `we`, `addr`, `wdata`, registered `rdata`) is a
memory. If the top itself has the interface, it alone is tested (as M27).
Each memory gets its own generated March C- controller, and one testbench runs
them all; the run passes only if every memory does. No memory found is a
recorded failed run.

### 4.2 A second variant: read latency

A memory may declare its read latency with a module attribute,
`(* read_latency = 2 *)` (default 1). The controller then waits that many
cycles before comparing, so a read takes 1 + L cycles and the run takes
(10 + 5L)N cycles, which the testbench counts. The latency is not taken on
trust: before March C-, the testbench drives the memory directly, writes 0 to
word 0 and all ones to word 1, switches the address, and counts cycles until
the new word appears. A declared latency that differs from the measured one
fails the run. The new fixture `sync_ram_2cycle.v` is 32 words of 16 bits
with a two-stage read pipeline (March C- passes in (10 + 10) x 32 = 640
cycles); `ram_2cycle_stuck_at_1` in the same file must fail.

### 4.3 The stage, as data

A new request feature `memory` (`RAM`, `SRAM`, `memory array`, `MBIST`) plans
a `mbist` stage in `block-design`:

```python
st("mbist", "Memory BIST", "Implementation", "dft.mbist",
   depends_on=("rtl-implementation",), when=when("memory"), skills=("mbist",),
   review=rv("dft.review"), outputs=("mbist_configuration",),
   evidence=(REVIEWED,
             checked("March C- passes on every memory in the approved RTL", "dft.mbist",
                     FileInput(param="sources", kinds=("rtl_source",), upstream=True))))
```

The check runs over the approved RTL, with no top named, so the memories are
found in what the RTL seat produced. A faulty memory fails the run, and the
M23 `evidence-before-review` check refuses the submission. The fixtures are
`mbist/ram_block.v` (a register file whose ports are not a memory interface),
`mbist/block_ram.v` (the RAM inside it), and `mbist/ram_block_tb.v`; the test
injects a stuck-at bit into `block_ram` that the block's own testbench does not
see, and the MBIST stage refuses it.

---

## 5. The seat, as data

| Record | Change |
|---|---|
| Tools | `dft.atpg_transition`, `AVAILABLE` |
| Skills | `atpg`, `fault_modeling`, `scan_design` gain `dft.atpg_transition` |
| Vocabulary | features `memory` and `at_speed` (`at-speed`, `transition fault`, `delay test`; implies `dft`) |
| Workflow | `block-design` gains the `mbist` stage; its `dft` stage gains a fourth before-review check, `dft.atpg_transition` with `min_test_coverage`, planned only for `at_speed` |

---

## 6. Laws, each pinned by a test (`tests/test_nirmaan_dft_next.py`)

1. Transition coverage on the fixtures is measured by the Icarus fault
   simulation, with primary-input transitions proven undetectable.
2. A pattern set with a false transition claim, or a broken pattern pair
   (a wrong launch or capture response), is refused.
3. A chain crossing clock domains with lockups passes `dft.check` and shifts
   correctly with skewed clocks; the same chain with the lockup removed is
   caught by both `dft.check` and `dft.scan_sim`.
4. Stuck-at ATPG over two capture edges runs and is graded.
5. MBIST finds the memory in a hierarchy and passes the 2-cycle RAM; a wrong
   declared latency fails; a faulty 2-cycle RAM fails.
6. The MBIST stage is planned for a memory block, and a faulty memory keeps
   it from review.
7. Crown jewel: a new transition-fault backend needs no core change.
8. The import laws (`test_nirmaan_architecture.py`).

---

## 7. Deferred

* Launch on shift, and transition ATPG over two capture edges.
* Pin (branch) faults, path delay faults, and small-delay defects.
* MBIST memories instantiated with overridden parameters (Yosys renames them);
  multi-port memories; a memory collar inserted into the design.
* Compression, LBIST, JTAG.
