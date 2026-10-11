# Milestone 35 - Interrupts in host co-simulation, and precise bus-error traps (after Stage 6)

Closes two of M29's deferred firmware items. Built in parallel with M34 and
M36 to M38; no version bump. Design doc: `docs/FIRMWARE_IRQ_TRAPS.md`.

Key design points worth not re-deriving:
- **Host interrupts.** `fw.test` reads the top's ports (`top_module`,
  `design_ports`, `rtl_files`, `IRQ_PORT` moved to `integrations/firmware.py`,
  re-exported by `firmware_riscv.py`); an `irq` output adds `-CFLAGS
  -DNIRMAAN_DUT_IRQ`. `axil_manager.cpp` implements `nirmaan_irq.h`: an
  attached handler runs while `irq` is high, at the end of each `read32` and
  `write32`, on each cycle of `nirmaan_irq_wait`, and on attach; never nested;
  one cycle after each handler, and a 5,000,000-cycle limit, so a storm is a
  failed run. It prints `FWTEST IRQ taken`. The M29 timer tests run unchanged.
- **Bus-fault API** in `nirmaan_irq.h`: `nirmaan_bus_fault_attach` (returns 0
  when the platform has no precise trap), `nirmaan_bus_fault_count`, and a
  `nirmaan_bus_fault` record (offset, write, response, pc). Host: called
  before the failing access returns, `pc` 0. Both print `FWTEST TRAP ...`.
- **PicoRV32 is precise**: the SoC (`BERR_CTRL`/`BERR_INFO`/`BERR_ADDR` at
  0x2000_0010 to 0x18) raises a bus-error line on the same edge as `mem_ready`;
  it is `irq[4]` (`LATCHED_IRQ` 0xffff_ffe7), which PicoRV32 checks in fetch
  before the next instruction runs. The trap entry reads `q1` and `q0` with
  `getq`; the faulting pc is `q0 - 4`. Verified: the pc is the HAL's device
  `lw`, and the following `STATUS` load had not run. HAL critical sections now
  mask `irq[3]` only (`set_line` in `irq_picorv32.S`). Not restartable (the
  load wrote its register); inside another handler the trap waits for
  `retirq`. `Core.bus_error` (picorv32 True) adds
  `+define+NIRMAAN_CORE_BUS_ERR`, connecting the wrapper's `bus_err`.
- **SERV has none**: no Wishbone `err`, one interrupt input already taken by
  `irq`, and the vendored core may not change. `nirmaan_core_bus_error_set`
  returns 0 there; the fault test's trap checks fail saying why.
- **Gate as data.** `require_irq` (`auto`/`yes`/`no`) and
  `require_bus_error_trap` (`yes`/`no`) are declared on `fw.test` and
  `fw.soc_test`; steps write `fw_require.json`, the parser counts
  `irq_taken` and `bus_error_traps` (as `dft.atpg` does its limits). The
  `block-design` firmware stage's `fw.test` and `fw.soc_test` requirements
  carry `require_irq=auto`, or `yes` with the new `interrupts` feature; the
  new `bus_errors` feature with `riscv` adds a `fw.soc_test` requirement with
  `require_bus_error_trap=yes`.

Fixture: `tests/fixtures/fw/axil_timer/axil_timer_fault_test.c` (per-access
response codes; precise read and write traps; OKAY does not trap; detached).
Tests: `tests/test_nirmaan_firmware_irq.py` (17), crown jewel
`test_a_new_bus_error_core_needs_no_core_changes`. Two older assertions
changed for the gate: M25's other-RTL policy test now passes
`require_irq=auto`, and M29's soc requirement params are
`{"require_irq": "auto"}`.

Deferred: SERV traps, restartable bus errors, errors outside the device
window, APB in the host harness, more than one interrupt line.
