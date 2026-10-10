# Milestone 29 (RISC-V) - interrupts, a second core, a code-size gate, and APB (after Stage 6)

Closes four of M27's deferred RISC-V items. Built in parallel with other
post-Stage-6 work; no version bump. Design doc: `docs/RISCV_NEXT.md`.

**Cores and buses are data** in `src/nirmaan/integrations/firmware_riscv.py`:
`CORES` (`Core(name, module, verilog, runtime, march)`, `register_core`) holds
`picorv32` (default) and `serv`; `BUSES` (`Bus(name, module, verilog, ports)`,
`register_bus`) holds `axi4-lite` and `apb`. `fw.cross_build` and
`fw.soc_test` take `core=`; the bus is read from the top module's ports
(`design_ports`, `bus_of`). The SoC instantiates `` `NIRMAAN_CORE `` (a
wrapper, `core_<name>.v`, with PicoRV32's memory interface, `trap`, and `irq`)
and `` `NIRMAAN_BRIDGE `` (`bridge_axil.v` or `bridge_apb.v`, each of which
instantiates `` `NIRMAAN_DUT ``), so `nirmaan_soc.v` names no core, bus, or
design. The `fw.soc_test` backend keeps its M27 name `picorv32-verilator`.
The one new parameter, `core`, is declared (M28 contracts) on both tools in
`company/tools.py`; the IRQ and the bus need none, being read from the RTL.

Key design points worth not re-deriving:
- **SERV 1.4.0** (olofk/serv, commit `7d9cde4`), seventeen `rtl/` files
  unmodified in `firmware_soc/serv/` with its ISC `LICENSE`, every SHA-256
  pinned. `serv_compdec.v` keeps Ibex's Apache-2.0 header (unused with
  `COMPRESSED=0`, but Verilator resolves the generate branch). Chosen over
  VexRiscv because VexRiscv's Verilog is generated from SpinalHDL. SERV is
  bit-serial: about ten times PicoRV32's cycles (682,218 against 63,642 for
  the register block).
- **The wrapper aligns SERV's address** (it puts a byte store's byte address
  on the bus) and shares one port between its I and D buses, which are never
  active together.
- **Interrupts.** A design output named `irq` adds `+define+NIRMAAN_DUT_IRQ`;
  the bridge wires it to the core. PicoRV32: `ENABLE_IRQ`, QREGS, `irq[3]`,
  level sensitive (`LATCHED_IRQ` bit 3 clear), `PROGADDR_IRQ` 0x10, `maskirq`
  and `retirq` emitted with `.insn`. SERV: `WITH_CSR=1`, the line on
  `i_timer_irq` (its only one), `mtvec` = 0x10, `mstatus.MIE`, `mret`; its
  exceptions also arrive at 0x10 and end the run as `FWTEST ERROR the CPU
  trapped`. `crt0.S` puts the vector at 0x10; `irq_<core>.S` defines
  `nirmaan_core_init`, `nirmaan_core_irq_set`, `nirmaan_core_trap`.
- **`nirmaan_irq.h`** (in `firmware_harness/`, the platform's): `attach`,
  `count`, `wait`. Each HAL access plus its `STATUS` read is a critical
  section, or a handler touching the device could overwrite `STATUS`.
- **No precise bus-error traps.** Neither core has a bus-error input, and
  SLVERR on an external IRQ line would be an imprecise interrupt; `STATUS`
  stays. A core with `data_err_i` (Ibex) would be the path.
- **`max_text_bytes`.** `_size` adds `text_bytes`; the `block-design`
  firmware stage's `fw.cross_build` requirement carries
  `params=(("max_text_bytes", "16384"),)` (images are about 10 KiB).

Fixtures: `tests/fixtures/rtl/axil_timer/axil_timer.v` (AXI4-Lite one-shot
timer: `CTRL` EN and IE, `LOAD`, read-only `COUNT`, W1C `STATUS`,
`irq = EXPIRED && IE`), its driver and interrupt tests in
`tests/fixtures/fw/axil_timer/`, and an APB driver in
`tests/fixtures/fw/apb_regs/` for the M26 `apb_regs.v`.

Tests: `tests/test_nirmaan_riscv_next.py` (20): the gate's limit; `text_bytes`;
cores and buses as data; the SoC naming nothing; an unknown core and an
unknown bus as recorded failed runs; an oversized image refused; on both
cores, the register driver, the timer's five interrupt checks, the two broken
IRQs (stuck low, ignoring IE) each failing the expected checks, and the APB
driver; a wrong APB map failing; crown jewel
`test_a_new_core_needs_no_core_changes` (a third core from a temporary
directory); SERV pinned; import laws. One M27 assertion changed: a cross build
now compiles six files (the core's interrupt runtime). CI is unchanged.

Deferred: precise bus-error traps, interrupts and APB in the host
co-simulation (`fw.test`), more than one interrupt line, and running the gate
on both cores.
