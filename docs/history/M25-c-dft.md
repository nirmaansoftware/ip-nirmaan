# Milestone 25 (DFT part) - Design for test through Yosys and Icarus (roadmap Stage 6)

Three new tools, all `AVAILABLE` and backed by M21 backends in
`nirmaan/integrations/dft.py` (the broker imports every integrations module): `dft.scan_insert`
(backend `yosys-scan`), `dft.check` (`yosys-dft`), and `dft.scan_sim`
(`icarus-scan`). `dft.run` (ATPG, MBIST) stays `CONTRACT_ONLY`. Physical design
and firmware are the M25 entries above; M24, the engineering graph, sits between.

Key design points worth not re-deriving:
- **Architecture: mux-D, one chain.** Yosys `synth -flatten` then `dffunmap`
  leaves only `$_DFF_[PN]_` and `$_DFF_[PN][PN][01]_` flops.
  `dft_scan.py stitch` renames each to a `$__NIRMAAN_SCAN_DFF_*` cell with `SE`
  and `SI` pins in the Yosys JSON, chaining flops in natural net-name order;
  Yosys then `techmap`s each into a `$_MUX_` plus the original flop and writes
  `scan.v` with ports `scan_en`, `scan_in`, `scan_out`, plus `chain.json`.
  Latches, a second clock or edge, a non-input clock, or taken port names are
  refused as a failed run.
- **`dft_scan.py` is standard library only.** The backends run it as a step
  (`sys.executable dft_scan.py ...`) between Yosys and Icarus, so it never
  depends on how Nirmaan is installed; `dft.py` imports the same functions.
- **Rules are a registry** (`register_rule(DftRule(...))`), evaluated over the
  Yosys netlist in the parser: `no-latches`, `no-combinational-loops`,
  `scannable-flops`, `clock-from-input`, `reset-from-input`,
  `one-clock-domain`, `recognized-cells`, and `scan-chain-complete` (only when
  the top has the scan ports). Each violation's diagnostic code is its rule ID.
- **The chain is traced functionally**, not by finding muxes (synthesis may
  restructure them): random 64-bit words on inputs and flop outputs, `scan_en`
  high, each flop's D evaluated by a small gate evaluator over the netlist.
- **`dft.scan_sim`** generates a testbench: shift 2L known bits (scan_out must
  replay them after L cycles), then load a state, capture once with `scan_en`
  low, and unload. The expected capture is the gate evaluator's next state over
  Yosys's netlist, so Icarus and Yosys cross-check each other. A broken chain
  fails before simulating, with the chain problems.
- **The seat is data.** `scan_design` and `dft_verification` skills gain the
  tools; `block-design` gains a `dft` stage ("Scan insertion", `dft.insert`,
  output `dft_netlist`, review `dft.review`) only when the request asks for
  test (the existing `dft` feature). Its two `checked(...)` requirements make
  `dft.check` and `dft.scan_sim` before-review checks over the netlist file.
- Verified on Yosys 0.33 (CI's apt version, via `yowasp-yosys`) and current
  Yosys: both fixtures insert, check, and simulate cleanly (4 and 206 flops).

Fixtures: `tests/fixtures/rtl/dft/` (`untestable.v`: latch, gated and divided
clocks, a combinational loop; `broken_chain.v`: a flop with no scan mux).
`tests/test_nirmaan_dft.py` (16 tests): pure stitcher, tracer, and rule tests; real
insertion, rules, and chain simulation on `counter.v` and `axi4_lite_regs.v`;
a broken chain and a mis-shifting chain as recorded failed runs; refusal
without Yosys; the DFT stage gated before review end to end; crown jewel
`test_a_new_dft_rule_needs_no_core_changes`. Design doc: `docs/DFT.md`.

Deferred: ATPG and fault grading, multiple chains and clock domains, MBIST,
a Verilator backend for `dft.scan_sim`, a seat that records a tool-written file
(the runtime records only model-written files today), and the before-review
checks on `new-ip`'s `dft` stage.

v1.19.0 is the one version bump for Stage 5 (M24, #29) and the three Stage 6
parts (physical design #28, firmware #30, DFT #31), built in parallel. The
standard run is 1055 tests with 2 skipped: the real OpenSTA and OpenROAD tests,
whose tools are not installed anywhere yet.
