# Design for Test, advanced (Milestone 27)

Status: design for the owner's review, implemented on branch `m27/dft-plus`.
It extends `docs/DFT.md` (M25: mux-D scan, one chain, the rule registry, and
chain simulation) with the three items M25 deferred: multiple scan chains,
stuck-at ATPG with fault coverage measured by real fault simulation, and
March C- memory BIST. Prose here is free of em and en dashes per the standing
style law.

Every run here is real: Yosys synthesizes, Icarus simulates, and the steps in
between are standard-library Python (`dft_scan.py`, `dft_atpg.py`,
`dft_mbist.py`) that read only what the tools wrote. It works on Yosys 0.33,
Icarus 12, and Verilator 5.020 (CI) as well as current releases.

---

## 1. The laws

M21, M23, and M25's laws hold unchanged:

1. **Never fake work.** A missing executable is a refusal with the reason; a
   design that fails is a recorded run with `succeeded=False`. Fault coverage
   is what the fault simulation measured, never what the pattern generator
   says about its own patterns (section 3.4).
2. **Data over code.** The new tools, skills, and evidence are records in
   `company/`. The runtime names none of them.
3. **Registries.** Each new tool is a `register_backend(Backend(...))`; the
   crown-jewel test shows a new backend for a DFT tool needs no core change.

---

## 2. Multiple scan chains

### 2.1 Parameters

`dft.scan_insert` takes two optional parameters:

| Parameter | Meaning |
|---|---|
| `chains` | the number of chains (default 1) |
| `max_chain_length` | the longest a chain may be; enough chains are added to meet it |

With both, the larger resulting chain count wins. `max_chain_length` is also an
ordinary M21 `max_` limit on the run's `chain_length` metric (the longest
chain), so the result is checked, not only requested. More chains than flops,
or a value that is not a positive integer, is a recorded failed run.

### 2.2 Ports

One chain keeps M25's scalar ports `scan_en`, `scan_in`, `scan_out`, so every
M25 netlist and test is unchanged. With N > 1 chains, `scan_in` and `scan_out`
are N-bit vector ports: chain k runs from `scan_in[k]` to `scan_out[k]`.
`scan_en` stays one bit and drives every chain.

### 2.3 Clock domains

A chain is a shift register, so every flop on it must share one clock and
edge. M25 refused a second clock; M27 groups instead:

1. Flops are partitioned into domains by (clock net, edge). Every clock must
   still be a module input (the `clock-from-input` rule).
2. Each domain gets at least one chain. With `max_chain_length`, a domain of n
   flops gets at least ceil(n / max) chains.
3. Any further chains (up to `chains`) go, one at a time, to the domain whose
   longest chain is currently longest.
4. Within a domain, flops keep M25's natural net-name order and are cut into
   contiguous pieces whose lengths differ by at most one.

So chains are balanced within a domain, and across domains as far as whole
chains allow. No chain crosses a domain, so no lockup latch is needed.

`dft.check`'s `one-clock-domain` rule is retired: several domains are now
scannable. `scan-chain-complete` instead reports a chain whose flops do not
share one clock and edge.

### 2.4 Tracing and simulating N chains

The functional tracer (M25 section 3) starts a chain at each bit of `scan_in`,
and requires `scan_out[k]` to be the last flop of chain k. The chain report
(`chain.json`) lists every chain with its length, clock, edge, and order.

`dft.scan_sim` shifts all chains at once for L cycles (L the longest chain);
a shorter chain's `scan_out` is checked only for the cycles its length allows.
With several clocks, all are pulsed together. Each clock idles low if any flop
uses its rising edge, else high, so each pulse has two edges: flops whose
active edge comes first capture first. The expected capture is evaluated in
that order: first-edge flops from the loaded state, then second-edge flops
from the state the first edge left. For one clock and one edge this is M25's
single evaluation.

---

## 3. ATPG: `dft.atpg`

### 3.1 Search first

There is no open-source ATPG in Homebrew or Ubuntu 24.04's apt. Atalanta
builds from source, but it reads ISCAS `.bench`, so it needs a netlist
converter and a CI build step, and its own coverage figure would still have to
be checked by simulation. Fault (the ASIC flow tool) needs its own Swift and
Yosys stack. M27 implements a small, standard ATPG itself and keeps the
measurement independent of it.

### 3.2 The model

`dft.atpg` works on a scan netlist (what `dft.scan_insert` wrote, or any
design with the scan ports). Yosys synthesizes it flat, exactly as `dft.check`
does, and the chains are traced functionally. The **capture model** is the
combinational logic between scan flops with `scan_en` low:

| Kind | Nets |
|---|---|
| Controllable | primary inputs (not clocks, asynchronous resets, `scan_en`, `scan_in`); every flop output (loaded by shifting) |
| Observable | primary outputs (not `scan_out`); every flop input (captured, then shifted out) |
| Constant | `scan_en` and `scan_in` low, asynchronous resets inactive |

The **fault universe** is stuck-at-0 and stuck-at-1 on every net of the
capture model that is a controllable input or a gate output: the stem faults
of the Yosys gate netlist, uncollapsed. Clock, reset, and scan-control nets are
outside it; the chain test (`dft.scan_sim`) covers them. All flops must
capture on the same clock phase; a design whose domains capture on different
edges is refused (deferred).

### 3.3 Generation (`dft_atpg.py generate`)

1. **Random patterns**, 64 at a time, fault simulated bit-parallel over each
   fault's fanout cone. A pattern is kept only if it is the first to detect a
   fault. Batches stop when one detects nothing new.
2. **PODEM** for every fault left: decisions only on controllable inputs,
   three-valued simulation of the good and the faulty machine, the D-frontier
   and an X-path check to prune, and full backtracking. A fault whose search
   space is exhausted is **proven undetectable** in the capture model; one that
   hits the backtrack limit (default 200) is **aborted**. Each new pattern's
   unassigned inputs are filled at random and it is fault simulated against the
   faults still open.
3. The final pattern list is fault simulated once more, in order, and each
   detected fault is **claimed** by the first pattern that detects it.

The output, `patterns.json`, holds per pattern the primary inputs, the load of
each chain, and the expected primary outputs and unload of each chain; plus the
claims, the proven undetectable faults, and the aborted ones.

### 3.4 Measurement (`dft_atpg.py inject`, Yosys, Icarus)

The coverage is measured by a separate fault simulation, through the scan
protocol, in Icarus:

1. **The fault netlist.** The grader enumerates the fault universe itself,
   from the netlist, not from the pattern file. Each fault site gets a `$_MUX_`
   between the net and its loads, selected by bit s of a new port
   `nirmaan_fault_en` to the constant on bit s of `nirmaan_fault_val`.
   Yosys writes it as Verilog (`read_json`, `check -assert`,
   `write_verilog`). With every enable low it is the original netlist.
2. **Two machines.** A generated testbench instantiates the scan netlist as
   given (`sources`) as the good machine and the fault netlist beside it, with
   the same inputs.
3. **Checking the pattern file.** With no fault enabled, every pattern is
   applied: the good machine's primary outputs and unloaded chains must equal
   the file's expected values bit for bit, and the fault netlist must equal the
   good machine. Any mismatch fails the run: the pattern set is wrong, or the
   injection changed the design.
4. **Each fault.** Enable it, flush the chains, then apply the patterns through
   the real protocol: shift the load in with `scan_en` high (unloading the
   previous capture), apply the primary inputs, compare the primary outputs,
   pulse once with `scan_en` low, and so on, then a final unload. The fault is
   detected at the first pattern where any output or unloaded bit of the fault
   netlist differs from the good machine. Fault dropping stops it there.

The parser then classifies every fault in the universe:

| Class | Meaning |
|---|---|
| detected | the fault simulation saw it |
| undetectable | not detected, and PODEM proved no capture pattern exists (unobservable or redundant logic) |
| undetected | not detected and not proven: aborted, or never targeted |

and reports `faults_total`, `faults_detected`, `faults_undetectable`,
`faults_undetected`, `fault_coverage` (detected over total, percent), and
`test_coverage` (detected over total less undetectable).

**A claim is a checkable statement.** Every fault the pattern file claims must
be detected by the fault simulation; one that is not fails the run and is
named. So a pattern generator bug, or a hand-edited pattern set, cannot inflate
coverage. The reverse, a fault the simulation detects that the file did not
claim, is fine: shifting can reveal faults the capture model cannot (for
example on a net used only in shift mode), and the measurement is what counts.

### 3.5 Parameters

| Parameter | Meaning |
|---|---|
| `patterns` | grade this pattern file instead of generating one |
| `min_fault_coverage`, `min_test_coverage` | the run fails below this percent |
| `max_<metric>` | the ordinary M21 limit, for example `max_faults_undetected` |
| `fault_sample` | simulate a seeded random sample of this many faults; the summary says so |
| `seed` | the generator's seed (default 1) |

---

## 4. MBIST: `dft.mbist`

### 4.1 The memory

A single-port synchronous RAM with ports `clk`, `we`, `addr`, `wdata`, and a
registered `rdata` (one cycle of read latency), over the full address space.
The widths come from the module's ports, read by Yosys. The fixture is
`tests/fixtures/rtl/mbist/sync_ram.v` (16 words of 8 bits).

### 4.2 March C-

`{⇕(w0); ⇑(r0,w1); ⇑(r1,w0); ⇓(r0,w1); ⇓(r1,w0); ⇕(r0)}`, 10N operations,
with solid backgrounds (all zeros, all ones). It detects stuck-at, transition,
address decoder, and inversion and idempotent coupling faults between words.

### 4.3 The run

1. Yosys reads the memory and writes its ports.
2. `dft_mbist.py` writes `mbist.v`, a synthesizable controller
   (`nirmaan_mbist`: a state machine over element, address, and operation,
   with `start`, `done`, `fail`, and the first failing element and address),
   and a testbench that connects it to the memory.
3. Icarus runs it. The testbench counts every read and write the controller
   makes and requires exactly 5N of each, and exactly 15N cycles (a read takes
   two: issue, then compare), so a controller that skips work fails too.

The run passes when the controller reports no failure and the counts hold.
`tests/fixtures/rtl/mbist/faulty_rams.v` holds the same RAM with one injected
fault each: a bit stuck at 0, a bit stuck at 1, a transition fault, an
inversion coupling fault, an idempotent coupling fault, and an address decoder
fault. Every one must fail.

The controller is lint clean under `verilator --lint-only -Wall`, checked by a
test through `lint.run`.

---

## 5. The seat, as data

| Record | Change |
|---|---|
| Tools | `dft.atpg` and `dft.mbist`, `AVAILABLE`. `dft.run` stays `CONTRACT_ONLY` for commercial flows. |
| Skills | `atpg` and `fault_modeling` gain `dft.atpg`; `mbist` gains `dft.mbist`; `scan_design` gains `dft.atpg` |
| Workflow | `block-design`'s `dft` stage gains a third before-review check: `dft.atpg` over the scan netlist with `min_test_coverage` 90 |

A memory seat is not added: `block-design` has no memory stage, and MBIST is a
tool a DFT engineer can run (deferred: a memory-compiler stage).

---

## 6. Extension points

| To add | Do this | Core changes |
|---|---|---|
| Another ATPG (Atalanta, a commercial tool) | `register_backend(Backend(..., "dft.atpg", ...))` | none |
| Another memory test algorithm | a backend for `dft.mbist` | none |
| A coverage gate elsewhere | a `checked(...)` requirement naming `dft.atpg` with `min_test_coverage` | none |

Crown jewel `test_a_new_atpg_backend_needs_no_core_changes`: a backend the core
has never seen is registered for `dft.atpg` in the test, selected by name, runs
for real, and is removed.

---

## 7. Laws, each pinned by a test (`tests/test_nirmaan_dft_advanced.py`)

1. Multi-chain insertion, check, and simulation run for real on `counter.v`,
   `axi4_lite_regs.v`, and the M26 blocks; chains are balanced.
2. Two clock domains get separate chains, and they shift and capture.
3. ATPG coverage on `counter.v` and a multi-chain block is measured by the
   Icarus fault simulation and meets its threshold.
4. A pattern set with a false claim, or a wrong expected response, is refused.
5. An undetectable fault is classified as such, with a proof, on a fixture.
6. MBIST passes on the clean RAM and fails on each injected fault kind; the
   controller is lint clean.
7. Without the tools, `dft.atpg` and `dft.mbist` are refused with the reason.
8. Crown jewel, and the import laws.

---

## 8. Deferred

* Transition (at-speed) faults, and pin (branch) faults beyond net stems.
* ATPG across domains that capture on different edges.
* Lockup latches and chains that cross clock domains; compression.
* MBIST for multi-port memories, other read latencies, and partial address
  spaces; a memory stage in a workflow; LBIST and JTAG.
