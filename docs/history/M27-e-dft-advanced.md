# Milestone 27 (DFT) - ATPG, multiple scan chains, and MBIST (after Stage 6)

Two new tools, both `AVAILABLE` and backed by M21 backends in
`nirmaan/integrations/dft.py`: `dft.atpg` (backend `icarus-atpg`) and
`dft.mbist` (`icarus-mbist`); `dft.scan_insert` gains multiple chains. The
step helpers are standard library only: `dft_scan.py` (as in M25),
`dft_atpg.py`, and `dft_mbist.py`. `dft.run` stays `CONTRACT_ONLY`.

Key design points worth not re-deriving:
- **Chains.** `chains` and `max_chain_length` params; flops are grouped by
  (clock, edge), each domain gets at least one chain, spare chains go to the
  domain with the longest chain, and within a domain natural-order runs differ
  in length by at most one. One chain keeps scalar `scan_in`/`scan_out`; N
  chains make them N-bit vectors. The tracer starts a chain at each `scan_in`
  bit and checks `scan_out[k]` and one domain per chain. The M25 rule
  `one-clock-domain` is retired. `dft.scan_sim` pulses all clocks together;
  each clock idles low if any flop uses its rising edge, and the expected
  capture is evaluated in edge order (first-toggle flops, then the rest).
- **ATPG is our own, not an external tool.** Nothing is packaged in Homebrew
  or apt; Atalanta would need a `.bench` converter and a CI build. `dft_atpg.py
  generate`: random 64-pattern batches with bit-parallel cone fault
  simulation, then PODEM (three-valued good and faulty machines, D-frontier,
  X-path, full backtracking, limit 200) on the capture model (scan_en low,
  resets inactive). Fault universe: stuck-at 0/1 on every controllable input
  and gate output of the Yosys gate netlist (stems, uncollapsed).
- **Coverage is measured, not claimed.** `dft_atpg.py inject` enumerates the
  universe again from the netlist, adds a `$_MUX_` per fault site (select
  `nirmaan_fault_en[s]`, value `nirmaan_fault_val[s]`), and Yosys writes it.
  The testbench runs the design as given (good machine) beside the fault
  netlist, through the real scan protocol. It first checks the pattern file's
  expected responses and that the fault netlist equals the design with no
  fault; then, per fault, detection at the first differing output or
  unloaded bit. A claim the simulation does not bear out, a wrong expected
  response, or an injection mismatch fails the run. `min_<metric>` params
  (for example `min_test_coverage`) are checked in `parse_atpg` from
  `atpg_config.json`; `max_` limits work as in M21. `patterns` grades a given
  file; `fault_sample` samples, and says so.
- **A capture-untestable fault can still be detected** by shifting (for
  example a NAND with `scan_en` stuck at 1): the class is from the
  simulation, so `undetectable` means proven by PODEM and not detected.
- **MBIST.** `dft_mbist.py` writes a March C- controller (10N operations,
  solid backgrounds, a read is issue then compare) for a single-port sync RAM
  (`clk`, `we`, `addr`, `wdata`, registered `rdata`) whose widths Yosys reads.
  The testbench counts reads, writes, and cycles independently (5N, 5N, 15N)
  and flags X reads. The controller is `verilator -Wall` lint clean (a test).
- **Seat data.** Skills `atpg`, `fault_modeling`, `scan_design` gain
  `dft.atpg`; `mbist` gains `dft.mbist`. The `block-design` `dft` stage's third
  `checked(...)` requirement is `dft.atpg` with `min_test_coverage` 90.

Measured (8 chains for the register blocks): counter 70/70 faults (100%),
`atpg_demo` 130/132 (2 proven undetectable, 100% test coverage), rr_arbiter
116/116, sync_fifo 754/754, apb_regs 1800/1800, axi4_lite_regs 2476/2476.
The last two take about 2 and 3 minutes of Icarus, so the tests grade only
the smaller blocks. MBIST passes the clean `sync_ram` in 240 cycles and fails
each of six faulty RAMs (stuck-at 0 and 1, transition, inversion and
idempotent coupling, address decoder).

Fixtures: `tests/fixtures/rtl/dft/two_clocks.v`, `dft/atpg_demo.v`,
`mbist/sync_ram.v`, `mbist/faulty_rams.v`. Tests:
`tests/test_nirmaan_dft_advanced.py`; crown jewel
`test_a_new_atpg_backend_needs_no_core_changes`. Design doc:
`docs/DFT_ADVANCED.md`. Deferred: transition faults, pin faults, ATPG across
capture edges, lockup latches, compression, other memory types, a memory stage.
