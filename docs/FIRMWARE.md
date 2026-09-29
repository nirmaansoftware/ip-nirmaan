# Firmware against the real RTL (Milestone 25, firmware part)

Status: design for the owner's review, implemented on branch `m25/firmware`.
This is the firmware part of Stage 6 of `docs/ROADMAP.md`; physical design
and DFT are separate parts of the same stage. Prose here is free of em and en
dashes per the standing style law.

M23 seated models in design and let RTL reach review only after real lint and
simulation. The natural next seat downstream is the driver: software that
programs the registers the RTL implements. A driver is as easy to check as RTL
is, provided it runs against the hardware it claims to drive. Before this
milestone nothing could run it: `compiler.run` was `CONTRACT_ONLY`, and there
was no hardware model to run on.

This milestone adds two tools, a firmware seat, and a harness that runs a C
driver against a Verilator model of the approved RTL, over real AXI4-Lite bus
transactions.

```
nirmaan plan "Create an AXI4-Lite register block and its driver."
...                                   # spec, microarchitecture, RTL, as in M23
nirmaan run <project> firmware --runtime anthropic --input workspace=work/
nirmaan run <project> firmware --runtime anthropic --review
nirmaan task approve <project> firmware --as <approver>
```

---

## 1. The laws

M20's, M21's, and M23's laws hold unchanged. In particular: a tool either
ran, and its log and parsed result are on disk, or the broker refused it and
said why. Nothing is simulated, stubbed, or replayed. M25 adds:

1. **A driver is tested on the approved RTL, not on a model of it.** The
   co-simulation runs the driver's own tests against a Verilator build of the
   exact RTL file that was approved upstream, digest checked. There is no
   hand-written register model anywhere in the loop that could agree with a
   wrong driver.
2. **Strict C, or no review.** The driver compiles under
   `-std=c11 -Wall -Wextra -Werror -pedantic`. A warning is a failed build.
3. **The bus is an interface, not an address.** A driver talks to hardware only
   through a HAL of function pointers (section 4). That is what lets the same
   source run on a target and on the model, and what lets the harness report
   the response code the RTL actually returned.

---

## 2. The tools

| Tool ID | Backends, in preference order | Executables | Status |
|---|---|---|---|
| `fw.build` | `host-cc`, then `riscv-gcc` | `cc`; or `riscv64-unknown-elf-gcc` | `AVAILABLE` |
| `fw.test` | `verilator-cosim` | `cc`, `verilator`, `make` | `AVAILABLE` |

Both register through M21's `register_backend` in
`src/nirmaan/integrations/firmware.py`, so the broker, the engine, and the
policy are unchanged by them. Availability follows M21 exactly: the catalog
says `AVAILABLE` because a real binding exists in this repository; the probe
decides, at every invocation, whether this machine can run it, and refuses with
the missing executables named when it cannot.

`compiler.run` stays `CONTRACT_ONLY`. It stands for a general software build;
`fw.build` is the narrower, checkable thing: a driver compiled under the strict
flags.

### `fw.build`

Parameters: `sources` (comma-separated `.c` and `.h` files, required),
`workdir`, `backend`, `timeout`.

Steps, one process each, never through a shell:

* each header: `cc <strict> -I<dirs> -fsyntax-only obj/header_<n>_<stem>.c`,
  where that file includes only the header (plus one `typedef`, because a
  macro-only header is an empty translation unit, which `-pedantic` rejects).
  A header that does not compile on its own fails, not only the file that
  includes it;
* each C file: `cc <strict> -I<dirs> -c <file> -o obj/<n>_<stem>.o`.

`<strict>` is `-std=c11 -Wall -Wextra -Werror -pedantic`. `<dirs>` are the
directories of the sources, then the harness directory that holds
`nirmaan_hal.h`.

The `riscv-gcc` backend runs the same steps with
`riscv64-unknown-elf-gcc -march=rv32imac_zicsr -mabi=ilp32 -ffreestanding`.
It is refused with its reason unless a machine has that compiler; it is
registered to show that a cross target is one registry entry, and it is never
chosen unless asked for by `backend=riscv-gcc` or the host compiler is absent.
M27 adds a full RV32I image build and a run on a RISC-V core
(`docs/RISCV_FIRMWARE.md`).

### `fw.test`

Parameters: `sources` (the driver and its tests, `.c` and `.h`, required),
`rtl` (comma-separated Verilog files of the design, required), `top` (the
design's top module; optional when the RTL has one), `workdir`, `backend`,
`timeout`.

Steps:

1. Copy the harness (`axil_manager.cpp`, `nirmaan_hal.h`) and the RTL into the
   working directory. `make`, which Verilator's `--build` drives, cannot handle
   a path with a space in it, and this repository lives under
   `~/Documents/IP Nirmaan`. The copies are byte for byte; the run records the
   original paths it was given.
2. Compile each C file under the strict flags, as `fw.build` does.
3. `verilator --cc --exe --build -j 0 -Wno-fatal --prefix Vdut -Mdir cosim
   [--top-module <top>] <rtl> harness/axil_manager.cpp <objects>`. The prefix
   is fixed, so the harness names no design. RTL lint is `lint.run`'s job, so
   Verilator warnings do not fail the build here.
4. Run `cosim/Vdut`.

A failing step stops the job, and every outcome is a recorded run: a compile
error, a Verilator error, a failed check, a bus timeout.

---

## 3. The harness: an AXI4-Lite manager

`src/nirmaan/integrations/firmware_harness/axil_manager.cpp` is a small,
generic C++ program. It needs only the AXI4-Lite subordinate port convention
of the M23 interface specification: `aclk`, `aresetn`, and the `s_axil_*`
channels, with 32-bit data. It:

* holds reset low for four cycles, then releases it;
* implements `write32` as AW and W presented together, each dropped on the
  edge that accepts it, then B taken with BREADY high; and `read32` as AR then
  R. Every handshake follows the VALID/READY rule: a transfer happens on a
  rising edge where both are high;
* gives up after 1000 cycles without a handshake, with `FWTEST ERROR bus
  timeout`, a failed run rather than a hang;
* prints one line per bus transfer and one per check, then a summary.

```
FWTEST BUS write 0x8 = 0x0123abcd strobe 0xf -> OKAY
FWTEST BUS read 0x5 -> 0x00000000 SLVERR
FWTEST PASS unmapped_read_reports_slverr
FWTEST FAIL write_then_read_every_register: REG1 read 0x0123abcd (status 0), wrote 0x5a5a5a5a
FWTEST SUMMARY 5 passed, 1 failed, 41 cycles
```

The exit status is 0 only when at least one check passed and none failed, so
tests that report nothing fail.

A block with a different bus (APB, a custom port list) gets a different
harness and a different `fw.test` backend; nothing else changes (section 7).

---

## 4. The HAL

`nirmaan_hal.h` is the contract between a driver, its tests, and whatever
runs them:

```c
typedef struct nirmaan_hal {
    void *ctx;
    unsigned (*read32)(void *ctx, uint32_t offset, uint32_t *value);
    unsigned (*write32)(void *ctx, uint32_t offset, uint32_t value, uint8_t strobe);
} nirmaan_hal;

void nirmaan_fw_test(const nirmaan_hal *hal);                          /* the driver's tests */
void nirmaan_test_result(const char *name, int passed, const char *detail);  /* the harness */
```

* Both accessors return the AXI response code (`NIRMAAN_BUS_OKAY`,
  `NIRMAAN_BUS_SLVERR`, ...) that the bus returned. Under `fw.test` it is the
  RTL's `bresp` or `rresp`, so a driver's error path is exercised by the
  hardware's own error, not by a stub that returns one.
* `strobe` is the AXI `wstrb`: a driver that offers byte writes passes a
  one-hot strobe and the RTL decides which bytes change.
* On a target, the HAL is a pair of `volatile` accesses plus a status read; the
  driver source is the same.
* The tests are C too, written against the driver's public API. They report
  each check through `nirmaan_test_result`, which the harness implements.

Why function pointers rather than link-time symbols: a single driver object can
be linked into the harness, a target image, and a unit test at once, and the
harness can carry state (`ctx`) without globals in the driver.

---

## 5. The firmware seat

All data, in `company/`:

| Record | Value |
|---|---|
| Capability | `fw.driver`, "Driver against approved RTL", produces `driver`, `driver_test`, `approved_inputs=True` |
| Skill | the existing `device_drivers` now also provides `fw.driver`, uses `fw.build` and `fw.test`, and carries the HAL contract in its procedures (extending it, rather than adding a skill, keeps the published skill count on the landing page unchanged) |
| Seat | the existing Driver Engineer practice (`software.firmware.drivers`) holds the skill |
| Review | `sw.review`, held by the firmware team's HAL, BSP, and boot engineers: an independent seat |
| Stage | `firmware` in the `block-design` workflow, when the requirement mentions firmware or a driver |
| Export | `driver_test` joins `driver` in `08_documentation` |

The stage:

```python
st("firmware", "Driver and driver tests", "Software", "fw.driver",
   depends_on=("interface-spec", "rtl-implementation"), when=when("firmware"),
   review=rv("sw.review"), outputs=("driver", "driver_test"),
   evidence=(REVIEWED,
             checked("Driver builds clean under strict C flags", "fw.build",
                     FileInput(param="sources", kinds=("driver",))),
             checked("Driver tests pass against the approved RTL", "fw.test",
                     FileInput(param="sources", kinds=("driver", "driver_test")),
                     FileInput(param="rtl", kinds=("rtl_source",), upstream=True))))
```

It depends on the interface specification (the register map a driver is
written from) and on the RTL (what it runs against). `approved_inputs` makes
M23's `approved-inputs` check refuse the seat until both are `APPROVED`, before
any model is asked.

### One generic addition: files from upstream

M23's `FileInput` fills a tool parameter from the files the task itself
produced. A driver test also needs a file the task did not produce: the
approved RTL. `FileInput` gains one optional field, `upstream: bool`:

* **The runtime** fills such a parameter from the task's upstream artifacts of
  those kinds that are `APPROVED` and whose bytes still match their recorded
  digest. An unapproved, missing, or tampered file is never passed; with none
  left, the check does not run ("no approved upstream rtl_source file"), and
  the submission is refused, exactly as M23 treats an answer with no RTL file.
* **The policy** (`evidence-before-review`) additionally requires, at
  submission, that a passing run for the requirement named an approved
  upstream file of those kinds in that parameter. A person submitting through
  the CLI meets the same check, so no one can take a co-simulation against
  other RTL to review.
* **The prompt** tells the seat which of its files the platform will run and
  with which approved upstream file.

None of the three names a seat, a kind, or a tool. It is the M23
approved-inputs pattern carried into tool parameters.

### The sequence

```
run_task
  engine.start                        P8 approved-inputs: interface spec and RTL approved
  ModelRuntime.execute
    prompt -> model -> JSON + file blocks (header, driver, tests)
    ground summaries, write kept files, digest them
    post-flight tools                 fw.build over driver files
                                      fw.test over driver and test files, rtl = approved RTL
  record evidence for every run       failed runs are recorded, unsubstantiated
  engine.submit                       P9 evidence-before-review, over these files and that RTL
```

Outcomes, as in M23:

| Outcome of the runs | Result | Task |
|---|---|---|
| Build and co-simulation pass | `submitted` | `in_review`, with the file artifacts |
| A strict warning, or a failed check on the RTL | `refused`, with the engine's reason | stays `in_progress`; the failed runs are on it as evidence |
| `cc` or `verilator` absent | `blocked`, with the broker's reason | `blocked`; nothing was run |
| The approved RTL changed on disk since approval | `refused`: `fw.test` is not run | stays `in_progress`; nothing was co-simulated |

---

## 6. The fixture

`tests/fixtures/fw/axi4_lite/` is the scripted firmware seat's answer for the
M23 AXI4-Lite register block:

| File | Kind | What |
|---|---|---|
| `axi4_lite_regs_map.h` | `driver` | Register offsets from the interface spec |
| `axi4_lite_regs_drv.h`, `axi4_lite_regs_drv.c` | `driver` | Indexed and raw access, byte-lane writes, every bus error returned to the caller |
| `axi4_lite_regs_test.c` | `driver_test` | Reset values; write all four registers then read all four back; byte-lane writes; an unmapped read (`0x5`) and an unmapped write (`0xE`) report SLVERR and the write changes nothing; bad indices refused |
| `axi4_lite_regs_map_wrong.h` | (none) | The deliberate failure: REG2 at REG1's offset. It compiles cleanly; only the co-simulation shows REG1 overwritten |

Writing all four registers before reading any back is what catches an aliasing
offset; a write-read pair per register would not.

---

## 7. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A cross-compiler target | `register_backend(Backend("<name>", "fw.build", ("<compiler>",), steps, parse_c_build))` | none |
| A different bus harness | A harness source, and a `fw.test` backend whose steps build it | none |
| A new firmware check | An `EvidenceRequirement` with `files`, `before_review`, and any AVAILABLE tool | none |

The crown jewel `test_a_new_firmware_backend_needs_no_core_changes` registers
an `arm-cc` `fw.build` backend whose compiler is a script the test writes: it
is refused while absent, runs once on `PATH`, and its run substantiates the
build requirement.

---

## 8. Laws, each pinned by a test (`tests/test_nirmaan_firmware.py`)

1. The C diagnostic parser reads GCC and Clang formats, with `-Werror` flags
   mapped to their warning code, and ignores notes.
2. A strict warning (an unused variable) is a failed `fw.build` run, recorded.
3. The fixture driver builds clean, and passes every check in a real
   co-simulation against `axi4_lite_regs.v`.
4. The wrong driver is a recorded failed `fw.test` run naming the failed
   check, not an exception.
5. With `cc` or `verilator` absent, both tools are refused with the missing
   executables named; the RISC-V backend is refused unless its compiler is
   present.
6. The end-to-end seat flow: the AXI4-Lite block designed by agents as in M23,
   then the firmware seat on the fixture answer, real build and co-simulation,
   review by a different seat, human approval.
7. The wrong driver cannot reach review. A passing co-simulation against a
   copy of the RTL instead of the approved file does not open review (the
   policy, not only the runtime). An RTL that changed after approval is not
   co-simulated.
8. Crown jewel: a new firmware backend needs zero core changes.
9. The import laws still hold: `integrations/firmware.py` never imports
   VeriTriage.

---

## 9. Deferred

* A RISC-V cross compile in CI, and running the driver on a processor against
  the RTL: done in M27, on PicoRV32 in the same Verilator model as the RTL
  (`docs/RISCV_FIRMWARE.md`).
* A repair loop that hands the seat its compiler or co-simulation log: done in
  M26 (`docs/REPAIR_LOOP.md`); a firmware capability opts in with
  `max_attempts`.
* Harnesses for APB, AXI4 (bursts), and interrupts; the AXI4-Lite harness
  assumes 32-bit data and the `s_axil_*` port names.
* Static analysis (`clang-tidy`, `cppcheck`, MISRA) as another before-review
  check. It is one more backend and one more requirement.
* A register description (IP-XACT, SystemRDL) from which both the RTL decode
  and the driver header are generated and checked against each other.
* Coverage of the driver (`gcov`) as evidence.
