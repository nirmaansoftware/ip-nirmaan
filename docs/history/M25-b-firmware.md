# Milestone 25 (firmware part) - A driver run on the approved RTL (roadmap Stage 6)

The firmware part of Stage 6, built in parallel with the physical-design and
DFT parts and the Stage 5 graph. A firmware seat writes a C driver and its
tests; they reach review only after a strict build and a co-simulation against
a Verilator model of the approved RTL passed. Version bump left to the
coordinator.

**Two tools, through the M21 registry.** `src/nirmaan/integrations/firmware.py`
registers `fw.build` (backends `host-cc`, and `riscv-gcc`, which is refused
unless `riscv64-unknown-elf-gcc` is on PATH) and `fw.test` (backend
`verilator-cosim`, needs `cc`, `verilator`, `make`). Both are `AVAILABLE` in
`company/tools.py`; `compiler.run` stays `CONTRACT_ONLY`. `fw.build` compiles
every `.c` under `-std=c11 -Wall -Wextra -Werror -pedantic` and checks each
`.h` alone (through a generated one-line file, since a macro-only header is an
empty translation unit under `-pedantic`). `fw.test` compiles the driver and
tests the same way, builds the RTL with Verilator (`--prefix Vdut`) around
`integrations/firmware_harness/axil_manager.cpp`, and runs it. Parsers
`parse_c_build` (GCC and Clang, `-Werror=` and `-Werror,-W` mapped to the
warning code) and `parse_fw_test` (the harness's `FWTEST` lines) are pure.

**The HAL.** `firmware_harness/nirmaan_hal.h`: a struct of `read32`/`write32`
function pointers plus a context, each returning the AXI response code; tests
define `nirmaan_fw_test(const nirmaan_hal *)` and report through
`nirmaan_test_result`. The harness is a generic AXI4-Lite manager over the
`s_axil_*` port convention (32-bit data): real VALID/READY handshakes, one
`FWTEST BUS` line per transfer, a 1000-cycle handshake timeout that fails the
run, and exit 0 only when at least one check passed and none failed.

**The seat, as data.** Capability `fw.driver` (`approved_inputs=True`,
produces `driver`, `driver_test`), provided by the existing `device_drivers`
skill (now with tools `fw.build` and `fw.test` and the HAL contract in its
procedures; extended rather than a new skill so the landing page's skill count
stays true), held by the existing Driver Engineer practice; review is
`sw.review` (HAL, BSP, and boot engineers). Stage `firmware` in `block-design`,
when the requirement mentions firmware or a driver, depending on
`interface-spec` and `rtl-implementation`. `driver_test` joins `driver` in the
`08_documentation` export folder.

**One generic addition: `FileInput.upstream`.** A tool parameter can be filled
from the task's approved upstream artifacts of given kinds, not only its own
files. The runtime passes only files that are APPROVED and still match their
digest; the `evidence-before-review` policy additionally requires a passing run
to have named an approved upstream file in that parameter (so a co-simulation
against some other copy of the RTL does not open review); the prompt says
"with the approved rtl_source". None of the three names a seat, kind, or tool.
`runtime/tools.py` now imports every `nirmaan.integrations` module to register
bindings, instead of naming `eda` and `veritriage`, so the runtime names no
integration (a test checks it names no firmware).

Key design points worth not re-deriving:
- Verilator's `--build` runs make, which breaks on a space in a path, and this
  repo lives under `~/Documents/IP Nirmaan`. `fw.test` copies the harness and
  the RTL into the working directory first; the run records the given paths.
  A working directory with a space in it fails as a recorded run.
- The wrong-driver fixture (`axi4_lite_regs_map_wrong.h`, REG2 at REG1's
  offset) builds clean; only the co-simulation catches it, because the tests
  write all four registers before reading any back.
- An approved RTL that changed on disk is not co-simulated: the check does not
  run and the submission is refused (as M23 treats a missing file), not
  blocked.

18 new tests in `tests/test_nirmaan_firmware.py`, including the end-to-end
`test_the_firmware_seat_runs_its_driver_on_the_approved_rtl` (the M23 flow,
then the firmware seat on the `tests/fixtures/fw/axi4_lite/` answer, real
build and co-simulation, agent review, human approval) and the crown jewel
`test_a_new_firmware_backend_needs_no_core_changes` (an `arm-cc` backend whose
compiler is a script the test writes). CI adds `cc make` to
`NIRMAAN_REQUIRE_EDA`. Design doc: `docs/FIRMWARE.md`. Deferred: a RISC-V
cross compile in CI and an instruction-set simulator in the loop, a repair
loop, APB and AXI4 harnesses, static analysis, generated register headers.
