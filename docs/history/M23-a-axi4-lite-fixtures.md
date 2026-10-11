# Milestone 23 fixtures - AXI4-Lite reference design (roadmap Stage 4)

`tests/fixtures/rtl/axi4_lite/` is the reference output of the design seats,
and the contract their end-to-end test scripts a model to produce:
`interface_spec.md`, `microarchitecture.md`, `axi4_lite_regs.v` (module
`axi4_lite_regs`, `ADDR_WIDTH` 4, `DATA_WIDTH` 32, `s_axil_*` ports, four
registers at 0x0 to 0xC), `axi4_lite_regs_tb.v` (self-checking, top
`axi4_lite_regs_tb`), `axi4_lite_regs_tb_fail.v` (one deliberately wrong
`wstrb` expectation, top `axi4_lite_regs_tb_fail`), and `axi4_lite_regs.sby`.
Choices: unmapped (misaligned) addresses get SLVERR, write latency and read
latency are 1 cycle (bound 2), reset values are zero, no skid buffer (READY
depends only on state). `tests/test_axi4_lite_fixture.py` proves it through
the broker with real tools: Verilator lint clean under `-Wall` with no
waivers, simulation passing under Icarus and Verilator, the wrong testbench a
recorded failed run, Yosys synthesis with no latches, and a SymbiYosys proof
of the handshake rules (formal skips in CI, which has no `sby`).
