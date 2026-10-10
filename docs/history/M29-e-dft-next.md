# Milestone 29 (DFT) - Transition ATPG, lockup latches, and an MBIST stage (after Stage 6)

One new tool, `AVAILABLE`: `dft.atpg_transition` (backend
`icarus-atpg-transition`, in `nirmaan/integrations/dft.py`); `dft.scan_insert`
gains `cross_domains=lockup` and `dft.mbist` makes `top` optional. Design doc:
`docs/DFT_NEXT.md`.

Key design points worth not re-deriving:
- **Transition faults are two-frame stuck-at faults.** `build_model` in
  `dft_atpg.py` copies the capture model into a second frame
  (`CaptureModel.copy_frame`); `net/STR` is the frame-2 copy stuck at 0 with a
  need (`Fault.need`) that the net is 0 in frame 1. PODEM treats needs as goals
  and contradictions as dead ends, so "untestable" is still a proof. Primary
  inputs are held through launch and capture (launch on capture only; LOS is
  deferred), so their transitions are proven undetectable.
- **The grader's delay model.** In the fault netlist each site gets a flop on
  `nirmaan_fault_clk` holding the previous value and becomes `net & prev`
  (STR) or `net | prev` (STF), only while `nirmaan_fault_en[s]` and
  `nirmaan_fault_atspeed` are high; the testbench raises at-speed 1 ns after
  the launch edge and drops it 1 ns after the capture edge. Pattern files carry
  `fault_model` (absent means stuck-at) and a mismatch is refused.
- **Stuck-at across capture edges is now modelled, not refused**: second-edge
  flops capture from a copy of the logic whose first-edge flops hold their new
  state; a fault sits on both copies (`Fault.extra`). Transition ATPG over two
  edges is still refused with the reason.
- **Lockups.** With `cross_domains=lockup`, flops are ordered second-edge
  domains first, then by clock port and edge, cut into balanced chains, and a
  `$_DLATCH_N_` (after a rising-edge flop) or `$_DLATCH_P_` goes on each clock
  crossing. `Design.lockups` are latches whose D is a flop Q and enable a
  module input; `no-latches` skips them unless they reach capture logic
  (`lockup_leaks`). The tracer reports `hazards` (an unlatched crossing, a
  wrong latch, a second-edge flop loading a first-edge one), which make a chain
  incomplete. `dft.scan_sim` with several clocks runs the shift three times:
  together, skewed 1 ns per clock, and skewed in reverse.
- **MBIST.** With no memory as top, every module with the single-port
  interface in the hierarchy is a memory, each with its own controller in one
  testbench. `(* read_latency = N *)` sets the latency (default 1); the
  testbench measures it first (word 0 zeros, word 1 ones, switch the address)
  and a mismatch fails the run. Cycles are (10 + 5L)N.
- **Data.** Features `memory` (RAM, SRAM, memory array, MBIST) and `at_speed`
  (implies `dft`); `block-design` gains an `mbist` stage (`dft.mbist` over the
  approved upstream `rtl_source`, no top) and the `dft` stage a fourth check,
  `dft.atpg_transition` with `min_test_coverage` 80, `when=when("at_speed")`.
  Skills `atpg`, `fault_modeling`, `scan_design` gain the new tool. Under the
  M28 contracts, `dft.atpg_transition` declares `dft.atpg`'s parameters,
  `dft.scan_insert` declares `cross_domains`, and `dft.mbist`'s `top` is no
  longer required.

Measured transition coverage (launch on capture): counter 53/70 (17 proven
undetectable), `atpg_demo` 87/132 (45), rr_arbiter 92/116 (24): 100% test
coverage each. The lockup `two_clocks` chain shifts clean in all three passes;
with the latch made a wire, `dft.check` reports the crossing and the skewed
shift loses 8 bits. MBIST passes `sync_ram_2cycle` (32x16, latency 2) in 640
cycles.

Fixtures: `mbist/sync_ram_2cycle.v`, `mbist/ram_block.v`, `mbist/block_ram.v`,
`mbist/ram_block_tb.v`. Tests: `tests/test_nirmaan_dft_next.py`; crown jewel
`test_a_new_transition_backend_needs_no_core_changes`. Deferred: launch on
shift, transition ATPG over two capture edges, pin and path delay faults,
parameterized memory instances, multi-port memories, a memory collar.
