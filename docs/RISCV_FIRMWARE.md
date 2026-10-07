# The driver on a RISC-V core, against the real RTL (Milestone 27)

Status: design for the owner's review, implemented on branch
`m27/riscv-firmware`. It continues the firmware part of Stage 6
(`docs/FIRMWARE.md`, M25) and closes the first item that document deferred: a
RISC-V cross compile in CI, and the driver run on a processor against the RTL.
Prose here is free of em and en dashes per the standing style law.

M25 ran a driver's tests against a Verilator model of the approved RTL, with a
C++ harness playing the bus manager. That proves the driver programs the
registers correctly, but not that it survives a real target: a compiler for a
32-bit bare-metal ISA, a C library that is not the host's, a startup file and a
linker script, and a CPU whose loads and stores are the only way to reach the
hardware. This milestone adds both halves:

```
fw.cross_build    driver + tests + SoC runtime  ->  RV32I ELF, code size
fw.soc_test       that ELF on PicoRV32, in one Verilator model with the approved RTL
```

---

## 1. The laws

M25's laws hold unchanged: a tool either ran, with its log and parsed result on
disk, or the broker refused it and said why; the driver is tested on the
approved RTL, never on a model of it; strict C or no review. M27 adds:

1. **The CPU is real, and so is the bus.** The tests run as RV32I machine code
   on PicoRV32, an open-source RISC-V core, simulated at RTL level in the same
   Verilator model as the design. There is no instruction-set simulator and
   no transaction-level shortcut: a register access is a `lw`, `sw`, `sh`, or
   `sb` that the core puts on its memory bus, and a bridge turns into an
   AXI4-Lite transfer on the design's own ports.
2. **The same driver and the same tests.** `fw.soc_test` takes exactly the
   files `fw.test` takes. The driver source does not change between the host
   model and the target; only the HAL behind `nirmaan_hal.h` does, and that is
   the platform's, not the seat's.
3. **The core is vendored unmodified.** `firmware_soc/picorv32.v` is
   byte for byte the upstream file (a test pins its SHA-256), with its ISC
   license header. Everything the SoC needs beyond the core is in files we
   wrote.

---

## 2. The tools

| Tool ID | Backend | Executables | Status |
|---|---|---|---|
| `fw.cross_build` | `rv32-gcc` | a RISC-V GCC, with its `objcopy` and `size` | `AVAILABLE` |
| `fw.soc_test` | `picorv32-verilator` | the same, plus `verilator`, `make` | `AVAILABLE` |

Both register through M21's `register_backend` in
`src/nirmaan/integrations/firmware_riscv.py`; the broker, the engine, and the
policy are unchanged by them. `compiler.run` stays `CONTRACT_ONLY`.

**Two names for one compiler.** Ubuntu's package `gcc-riscv64-unknown-elf`
installs `riscv64-unknown-elf-gcc`; Homebrew's `riscv64-elf-gcc` installs
`riscv64-elf-gcc`. Both are multilib builds that include `rv32i/ilp32`. The
backends accept either: the M21 `environment` hook finds the first prefix
whose `gcc`, `objcopy`, and `size` are all on PATH, and otherwise refuses with
"no RISC-V GCC on PATH (riscv64-unknown-elf-gcc or riscv64-elf-gcc, with its
objcopy and size)". The run's log shows which one ran.

### `fw.cross_build`

Parameters: `sources` (the driver and its tests, `.c` and `.h`, required),
`workdir`, `backend`, `timeout`, and any `max_<metric>` limit (section 6).

Steps, one process each, never through a shell:

1. Each C file, the driver's and the tests', and the runtime's
   `soc_runtime.c` and `libc/nirmaan_libc.c`:
   `<gcc> -std=c11 -Wall -Wextra -Werror -pedantic -march=rv32i -mabi=ilp32
   -ffreestanding -Os -fno-tree-loop-distribute-patterns -I... -c`.
   The strict flags are M25's `STRICT_FLAGS`; a warning is a failed build on
   the target exactly as on the host. The last flag stops GCC from turning
   the libc's own copy loops into calls to `memcpy`, which would recurse.
2. `crt0.S`, assembled for the same ISA.
3. The link: `-nostdlib -nostartfiles -T link.ld`, the objects, then `-lgcc`
   (RV32I has no divide instruction; `libgcc` supplies it).
4. `<prefix>size firmware.elf`.

`parse_cross_build` reads GCC diagnostics (M25's parser), link errors
(`undefined reference`, `collect2`), and linker warnings, and passes only when
every step exited 0, nothing warned, and `size` measured the ELF. The metrics
are `text`, `data`, `bss`, `image_bytes` (text plus data: what the image
occupies), and `compiled`. The summary reads, for the AXI4-Lite fixture:

```
cross-built clean for RV32I: 5 compiler runs, 0 errors, 0 warnings; firmware.elf text 9332, data 0, bss 168 bytes
```

About 9 KiB of that is the runtime (`snprintf` without a multiplier is not
small); the driver itself is a few hundred bytes.

### `fw.soc_test`

Parameters: `sources` and `rtl` (required), `top` (the design's module;
optional when the RTL has exactly one module that nothing else instantiates),
`workdir`, `backend`, `timeout`.

Steps:

1. Copy `firmware_soc/` and the RTL into the working directory, byte for byte
   (Verilator's `--build` runs make, which cannot take the space in
   `~/Documents/IP Nirmaan`; M25 does the same). The run records the paths it
   was given.
2. The `fw.cross_build` steps, then `<prefix>objcopy -O verilog` to the RAM
   image.
3. `verilator --cc --exe --build -j 0 -Wno-fatal --prefix Vsoc --top-module
   nirmaan_soc +define+NIRMAAN_DUT=<top> nirmaan_soc.v picorv32.v <rtl>
   soc_main.cpp`. The design is instantiated through the `NIRMAAN_DUT` macro,
   so no SoC file names a design (a test checks it).
4. `soc/Vsoc +firmware=rv32/firmware.hex`.

The run's output is in M25's format, so `parse_soc_test` is M25's
`parse_fw_test` (with the run named "SoC run") plus the code size:

```
FWTEST BUS read 0x5 -> 0x00000000 SLVERR
FWTEST PASS unmapped_read_reports_slverr
FWTEST BUS write 0x4 = 0xabababab strobe 0x4 -> OKAY
FWTEST SUMMARY 6 passed, 0 failed, 59734 cycles
```

Every outcome is a recorded run: a compile or link error, a Verilator error, a
failed check, a CPU trap (illegal instruction, misaligned access, `ebreak`), a
bus handshake that never completes (1000 cycles, as in M25), and firmware that
never writes `EXIT` (5,000,000 cycles).

---

## 3. The SoC

`src/nirmaan/integrations/firmware_soc/nirmaan_soc.v`:

```
             +-----------+   native mem bus   +-------------------+
  clk, rst ->| PicoRV32  |------------------->| decode            |
             |  RV32I    |<-------------------|  RAM 64 KiB       |  code, data, stack
             +-----------+                    |  device window ---+--> AXI4-Lite bridge --> the design (s_axil_*)
                                              |  control regs     |  STATUS, CONSOLE, EXIT, CYCLES
                                              +-------------------+
```

| Address | What |
|---|---|
| `0x0000_0000` | RAM, 64 KiB, loaded from the image before reset ends |
| `0x1000_0000` | The design, with a register shift of 2 (below) |
| `0x2000_0000` | `STATUS` (read): the response code of the latest device transfer |
| `0x2000_0004` | `CONSOLE` (write): one character to the log |
| `0x2000_0008` | `EXIT` (write): end the run with this exit code |
| `0x2000_000C` | `CYCLES` (read): clock cycles since reset |

PicoRV32 is built with its defaults (RV32I, misaligned accesses and illegal
instructions trap) except that its cycle counters are off, since `CYCLES`
serves.

### The device window, and why a register shift of 2

A 32-bit CPU never puts an unaligned address on its bus: a word load is
word-aligned or it traps, and a byte store shows up as a word address with one
strobe bit. The AXI4-Lite block, though, answers SLVERR for an unaligned
offset, and the M25 tests check exactly that (`0x5` read, `0xE` write). Mapped
one to one, those checks could not be expressed as CPU accesses at all.

So the SoC attaches the design the way many SoCs attach narrow peripherals
(Linux calls it `reg-shift = <2>` for 8250 UARTs): AXI byte offset `N` is the
32-bit word at `0x1000_0000 + 4 * N`. Every AXI offset, aligned or not, is one
aligned CPU word; byte lanes are the CPU's byte and halfword stores within
that word, and their strobes pass straight to `WSTRB`. The design sees the
offset the driver asked for, and its own decode decides the response. The
window is 4 KiB (offsets up to `0x3FF`); the bridge drives the design's
address port from those bits, and a design with a narrower port sees the low
bits, as it would on any bus.

### How a bus error reaches the driver: a status register

PicoRV32 has no bus-error input, so a trap is not available; and the HAL
contract (`nirmaan_hal.h`) returns the response code rather than raising
anything. The bridge therefore latches `BRESP` or `RRESP` into `STATUS` at the
end of every device transfer, and the target HAL reads `STATUS` right after
each access. The code the driver receives is the one the RTL returned, as in
M25. A CPU with precise bus-error exceptions could use a trap handler that
returns the same code; the driver would not change.

### The target HAL (`soc_runtime.c`)

* `read32`: a `volatile` word load from the window, then `STATUS`.
* `write32`: the store a CPU would use for the strobe: `sw` for `0xF`, `sh`
  for `0x3` or `0xC`, `sb` for one lane. Any other pattern is one `sb` per
  lane, returning the first response that is not OKAY. A zero strobe issues
  nothing and returns SLVERR: the HAL cannot make that request, and says so.
* `nirmaan_test_result`: formats the M25 `FWTEST PASS` or `FWTEST FAIL` line
  and writes it to `CONSOLE`.
* `nirmaan_soc_main` (called by `crt0.S`): runs `nirmaan_fw_test`, prints the
  summary with `CYCLES`, and writes `EXIT` 0 only when at least one check
  passed and none failed.

A byte store replicates its byte across the data bus, so the byte-lane check
shows as `write 0x4 = 0xabababab strobe 0x4`: the design must take only the
strobed lane, and the check proves it did.

### The C library

No libc ships with every RISC-V GCC (Homebrew's has none; Ubuntu's is a
separate picolibc package), and the driver tests use `snprintf`. The runtime
carries its own: `libc/stdio.h` (`snprintf`, `vsnprintf`) and
`libc/string.h` (`memcpy`, `memmove`, `memset`, `memcmp`, `strlen`, which GCC
may call on its own). It is compiled under the same strict flags. A test that
calls anything else fails to link, a recorded failed run naming the symbol;
nothing is stubbed. Carrying it also makes the image identical on every
machine with a RISC-V GCC, whichever C library that machine has.

### Startup and link

`crt0.S` sets `gp` and `sp`, clears `.bss`, and calls `nirmaan_soc_main`.
`link.ld` places everything in RAM at 0: the SoC loads the whole image into
RAM, so nothing is copied at startup.

---

## 4. The gate, as data: conditional on the request

The `block-design` firmware stage gains two `checked(...)` requirements:

```python
checked("Driver and tests cross-build for bare-metal RV32I", "fw.cross_build",
        FileInput(param="sources", kinds=("driver", "driver_test")), when=when("riscv")),
checked("Driver tests pass on a RISC-V core against the approved RTL", "fw.soc_test",
        FileInput(param="sources", kinds=("driver", "driver_test")),
        FileInput(param="rtl", kinds=("rtl_source",), upstream=True), when=when("riscv")),
```

The vocabulary gains the feature `riscv` (`RISC-V`, `RISC V`, `riscv`,
`rv32...`). "Create an AXI4-Lite register block and its driver for a RISC-V
core." plans a firmware seat gated on all four checks; "Create an AXI4-Lite
register block and its driver." plans M25's two, unchanged.

**Why conditional, and why on the request.** Required everywhere, the checks
would make every firmware task on every machine need a RISC-V GCC (about
380 MB from Homebrew) and a second Verilator build; a machine without them
would block drivers that target an ARM part or the host. Opt-in by the seat
(M26's `when_produced`, as for formal) would let the seat decide whether its
driver is tested on the target, which is the requester's call, not the
seat's. The target is a property of the request, so the condition is on the
request's features.

**One generic addition: `EvidenceRequirement.when`.** A `Condition` over the
request's features, like `StageTemplate.when`, default unconditional. The
planner keeps a stage's requirement on a task only when it holds; the runtime,
the policy, and `unsatisfied_requirements` read the task's requirements, so
nothing else changes. Nothing in it names RISC-V, a tool, or a seat (a test
checks the planner does not).

The seat's skill `device_drivers` gains the two tools. Its procedures are
unchanged: the driver is written against `nirmaan_hal.h` exactly as before,
which is the point.

The `evidence-before-review` policy's M25 upstream rule applies to `fw.soc_test`
as it does to `fw.test`: a passing SoC run counts only if its `rtl` named the
approved RTL.

---

## 5. Tests (`tests/test_nirmaan_riscv_firmware.py`)

1. The catalog lists both tools `AVAILABLE`, held by `device_drivers`.
2. A RISC-V request gates the firmware seat on four checks, with the approved
   RTL upstream for `fw.soc_test`; a request without RISC-V gates it on M25's
   two.
3. Parsers, on captured text: code size, a link error, a warning, no image; the
   SoC run's verdict and a CPU trap; the top-module rule.
4. With nothing on PATH, both tools are refused with the reason, and nothing is
   recorded.
5. A real cross build: a 32-bit RISC-V ELF (`e_machine` 243), linked with
   `link.ld` and `crt0.S`, strict and target flags in the log, code size
   reported. A strict warning is a recorded failed run.
6. A real SoC run: all six M25 checks pass on PicoRV32 against
   `axi4_lite_regs.v`, and the log shows the RTL's own SLVERRs and the byte
   store's strobe.
7. The wrong driver (REG2 at REG1's offset) is a recorded failed run naming
   `write_then_read_every_register`.
8. End to end: the M23 flow designs the block on a RISC-V request, the
   firmware seat's answer is built and run four ways (host build, host
   co-simulation, cross build, SoC run), all against the approved RTL, then
   reviewed by another seat and approved by a human.
9. Crown jewel `test_a_new_soc_backend_needs_no_core_changes`: another core or
   simulator for `fw.soc_test` is one `register_backend` call, refused while
   absent and run once on PATH.
10. The vendored core matches its upstream SHA-256 and keeps its license; the
    SoC files name no design; `firmware_riscv.py` never imports VeriTriage; the
    runtime names no target; the planner names no feature.

---

## 6. Extension points

| To add | Do this | Core changes |
|---|---|---|
| Another core (VexRiscv, Ibex, SERV) | A SoC file and a `fw.soc_test` backend whose steps build it | none |
| An ISA simulator instead (Spike, QEMU) | A `fw.soc_test` backend whose steps run it with a bus model | none |
| Another target ISA (Cortex-M) | A `fw.cross_build` backend with its flags, crt0, and linker script | none |
| A code-size budget | `params=(("max_text", "16384"),)` on the requirement: M26's generic limits | none |
| The SoC checks for another request word | Another pattern on the `riscv` feature, or another `when=` | none |

---

## 7. Tools installed

* **Here (macOS):** `brew install riscv64-elf-gcc` (GCC 16.2.0, with
  `riscv64-elf-binutils` 2.47). No libc, no simulator: the SoC runs in the
  Verilator already installed.
* **CI (ubuntu-24.04):** `apt-get install gcc-riscv64-unknown-elf` (with its
  binutils). `NIRMAAN_REQUIRE_EDA` gains `riscv64-unknown-elf-gcc`, so the
  RISC-V tests fail in CI rather than skip.

Neither picolibc, QEMU, nor Spike is needed.

---

## 8. Deferred

* Interrupts: a driver that waits on an IRQ from the design. PicoRV32 has an
  IRQ input and the SoC ties it off; a block with an interrupt line and a
  harness that routes it are the next step.
* Precise bus-error traps, on a core that has them.
* Other cores and ISAs (section 6), and running the image on an FPGA board.
* A code-size budget in the gate: the metric is reported; no limit is set yet.
* APB and AXI4 bridges in the SoC; the bridge assumes the `s_axil_*`
  convention and 32-bit data, as M25's harness does.
