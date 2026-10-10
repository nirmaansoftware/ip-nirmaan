# Milestone 27 (RISC-V firmware) - the driver on a core against the RTL (after Stage 6)

Closes M25's first deferred firmware item. The firmware seat's driver and
tests, unchanged, are cross-compiled for bare-metal RV32I and run on PicoRV32
in one Verilator model with the approved RTL. Built in parallel with other
post-Stage-6 work; no version bump. Design doc: `docs/RISCV_FIRMWARE.md`.

**Two tools, through the M21 registry.** `src/nirmaan/integrations/firmware_riscv.py`
registers `fw.cross_build` (backend `rv32-gcc`) and `fw.soc_test` (backend
`picorv32-verilator`, also needs `verilator`, `make`), both `AVAILABLE`. The
compiler is `riscv64-unknown-elf-gcc` (Ubuntu) or `riscv64-elf-gcc`
(Homebrew): the backends' `environment` hook takes the first prefix with
`gcc`, `objcopy`, and `size` on PATH, else refuses naming both.
`fw.cross_build` compiles the driver, the tests, and the runtime under M25's
strict flags plus `-march=rv32i -mabi=ilp32 -ffreestanding -Os`, assembles
`crt0.S`, links with `link.ld` and `-lgcc`, and runs `size`: metrics `text`,
`data`, `bss`, `image_bytes`. `fw.soc_test` builds that image, converts it
with `objcopy -O verilog`, builds `nirmaan_soc.v`, `picorv32.v`, and the RTL
with Verilator (`--prefix Vsoc`, the design as `+define+NIRMAAN_DUT=<top>`;
`top` defaults to the one module nothing instantiates), and runs it. Output is
M25's `FWTEST` format, so `parse_soc_test` is `parse_fw_test(...,
what="SoC run")` plus code size. `firmware.py` changed only by that `what`
argument, link errors in `parse_fw_test`, and a shared `copy_rtl`.

**The SoC** (`integrations/firmware_soc/`): PicoRV32 (vendored unmodified,
ISC, SHA-256 pinned by a test; upstream YosysHQ/picorv32 at `ef203c2`), 64 KiB
RAM at 0, the design at `0x1000_0000` behind a native-to-AXI4-Lite bridge, and
control registers at `0x2000_0000` (`STATUS`, `CONSOLE`, `EXIT`, `CYCLES`).
The target HAL is `soc_runtime.c`; `libc/` is a small strict-C libc
(`snprintf`, `mem*`, `strlen`), since Homebrew's GCC ships none.

Key design points worth not re-deriving:
- **Register shift 2.** A CPU never issues an unaligned bus address, but the
  M25 tests check SLVERR for offsets `0x5` and `0xE`. AXI offset N is the CPU
  word at `0x1000_0000 + 4*N` (like `reg-shift = <2>` for 8250 UARTs), so
  every offset is one aligned access and the RTL's own decode answers.
- **Bus errors reach the driver through `STATUS`**, latched from `BRESP` or
  `RRESP` per transfer and read by the HAL after each access; PicoRV32 has no
  bus-error input to trap on. A zero strobe is refused by the HAL with SLVERR.
- **Byte stores replicate the byte** (`write 0x4 = 0xabababab strobe 0x4`); the
  byte-lane check proves the RTL takes only the strobed lane.
- **`-fno-tree-loop-distribute-patterns`**, or GCC may turn the libc's
  `memset` loop into a call to `memset`.
- **The gate is conditional on the request, as data.** New feature `riscv`
  (`RISC-V`, `riscv`, `rv32...`); the firmware stage gains two `checked(...)`
  requirements with `when=when("riscv")`. One generic field,
  `EvidenceRequirement.when: Condition` (default unconditional), read only by
  the planner, which drops a requirement whose condition the request does not
  meet. Required everywhere would make every firmware task need a RISC-V GCC;
  opt-in by the seat (`when_produced`) would let the seat choose its own test.
  `device_drivers` gains both tools.

Tests: `tests/test_nirmaan_riscv_firmware.py` (14): the catalog; a RISC-V
request gates the seat on four checks and a plain one on two; parsers on
captured text; refusal with nothing on PATH; a real cross build (a 32-bit
RISC-V ELF) and a strict warning failing it; a real SoC run passing all six
M25 checks with the RTL's SLVERRs in the log; the wrong driver failing as a
recorded run; the end-to-end seat
(`test_the_firmware_seat_runs_its_driver_on_a_riscv_core`: four real runs
against the approved RTL, review, approval); the crown jewel
`test_a_new_soc_backend_needs_no_core_changes`; the pinned core; import laws.
CI installs `gcc-riscv64-unknown-elf` and adds `riscv64-unknown-elf-gcc` to
`NIRMAAN_REQUIRE_EDA`. The standard run, with M27 review repair merged, is
1140 tests with 2 skipped.

Deferred: interrupts from the design, precise bus-error traps, other cores and
ISAs, a code-size budget in the gate, APB and AXI4 bridges.
