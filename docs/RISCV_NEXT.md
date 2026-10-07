# Interrupts, a second core, a code-size gate, and APB in the RISC-V loop (Milestone 29)

Status: design for the owner's review, implemented on branch
`m29/riscv-next`. It continues `docs/RISCV_FIRMWARE.md` (M27) and closes four
of the items that document deferred: interrupts from the design to the core,
another core, a code-size budget in the gate, and an APB bridge. Prose here is
free of em and en dashes per the standing style law.

M27 ran a driver's tests as an RV32I image on PicoRV32, in one Verilator model
with the approved RTL. Three things about that loop were narrower than real
firmware work: a driver could not wait for an interrupt (the SoC tied the
core's IRQ input off), the harness had exactly one core (so "core-agnostic"
was a claim, not a tested fact), and only AXI4-Lite designs could sit behind
the bridge. The code size was measured but not limited.

```
fw.cross_build   driver + tests + SoC runtime for one core  ->  RV32I ELF, code size, max_text_bytes
fw.soc_test      that ELF on the chosen core (picorv32 | serv), the design behind its bus (axi4-lite | apb),
                 the design's irq line routed to the core
```

---

## 1. The laws

M25's and M27's laws hold unchanged: a tool either ran, with its log and
parsed result on disk, or the broker refused it and said why; the driver is
tested on the approved RTL, never on a model of it; strict C or no review; the
CPU is real and so is the bus; the vendored cores are byte for byte upstream.
M29 adds:

1. **An interrupt is the design's own wire.** The design's `irq` output goes
   to the core's interrupt input, and the core takes a real trap into the
   runtime's vector. Nothing polls on the driver's behalf and nothing
   synthesizes an interrupt: a design whose `irq` is stuck, or ignores its
   enable, fails the same tests that pass on the correct design.
2. **The SoC is core-agnostic, and that is tested.** The same driver, the same
   tests, and the same SoC run on two unrelated cores (PicoRV32 and SERV); a
   core is data (`core=`), and a third one is one `register_core` call.
3. **The SoC is bus-agnostic in the same way.** The bus a design speaks is
   read from its ports, and the bridge for it is data (`register_bus`).

---

## 2. Interrupts

### The convention

A design that interrupts has a one-bit output port named `irq`, active high
and level sensitive: high while the design wants service, low once the
firmware has acknowledged it through a register write. This is the common
convention for simple peripherals, and the one the fixture follows. The SoC
backend reads the top module's ports; when `irq` is there it builds the model
with `+define+NIRMAAN_DUT_IRQ`, and the bridge connects it. A design without
`irq` (the AXI4-Lite and APB register blocks) is built exactly as before, with
the core's line tied low.

### The fixture: an AXI4-Lite one-shot timer

`tests/fixtures/rtl/axil_timer/axil_timer.v`, with the AXI4-Lite channel logic
of `axi4_lite_regs.v` and four registers:

| Offset | Name | Access | What |
|---|---|---|---|
| `0x0` | `CTRL` | RW | bit 0 `EN` (writing 1 loads `COUNT` from `LOAD` and starts), bit 1 `IE` |
| `0x4` | `LOAD` | RW | the count, in clock cycles |
| `0x8` | `COUNT` | RO | the cycles left; a write is SLVERR |
| `0xC` | `STATUS` | W1C | bit 0 `EXPIRED`: set when `COUNT` reaches zero; writing 1 clears it |

`irq = EXPIRED && IE`. Unaligned or unmapped offsets are SLVERR, as on the
register block. Its driver (`tests/fixtures/fw/axil_timer/`) has an interrupt
API: `axil_timer_start(dev, cycles, irq_enable)`, `axil_timer_irq_enable`,
`axil_timer_expired`, and `axil_timer_ack` (the W1C write).

### The core side

| | PicoRV32 | SERV |
|---|---|---|
| Parameters | `ENABLE_IRQ=1`, `ENABLE_IRQ_QREGS=1`, `ENABLE_IRQ_TIMER=0`, `PROGADDR_IRQ=0x10`, `LATCHED_IRQ` with bit 3 clear | `WITH_CSR=1` |
| Where the design's `irq` goes | `irq[3]` (0 to 2 are the core's own: timer, ebreak, misalignment) | `i_timer_irq`, SERV's only interrupt input (`mcause` 0x80000007) |
| Entry | the core jumps to `0x10` | `mtvec` is set to `0x10` at startup |
| Enable, disable | `maskirq` (a PicoRV32 instruction, emitted with `.insn`) | `csrs`/`csrc mstatus.MIE`, with `mie.MTIE` set once |
| Return | `retirq` | `mret` |

Both cores enter at the same vector: `crt0.S` puts a jump at `0x10` to
`nirmaan_core_trap`, which each core's runtime file (`irq_picorv32.S`,
`irq_serv.S`) defines. It saves the caller-saved registers on the
interrupted stack, calls `nirmaan_irq_dispatch` in C, restores, and returns
the core's way. On SERV the same entry also receives exceptions (a misaligned
access, `ecall`, `ebreak`): the runtime prints `FWTEST ERROR the CPU trapped`
with `mcause` and `mepc` and ends the run, so a trap is a failed run on both
cores (PicoRV32 still traps through its `trap` output, since its exception
lines stay masked).

PicoRV32's line is level sensitive (`LATCHED_IRQ` bit 3 clear), so an
interrupt that is not acknowledged is taken again on return; SERV's is taken
on the rising edge of `mtip && mstatus.MIE && mie.MTIE`, so after `mret` a
line that is still high fires again too. Both give the same observable
behavior for the tests.

### The platform API: `nirmaan_irq.h`

```c
typedef void (*nirmaan_irq_handler)(void *ctx);
void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx);  /* NULL detaches */
unsigned nirmaan_irq_count(void);                                  /* handler runs so far */
unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles);         /* until count > seen, or cycles pass */
```

Attaching enables the core's interrupt; detaching disables it. The handler
runs in interrupt context and acknowledges the device through its driver, so
the acknowledgement is a real bus write. The header sits next to
`nirmaan_hal.h`, as the platform's, not the seat's.

One consequence for the HAL: each `read32` and `write32` is a device access
followed by a read of `STATUS`. An interrupt between the two, whose handler
also touches the device, would overwrite `STATUS` before the HAL reads it. The
target HAL therefore makes each access and its `STATUS` read a critical
section (interrupts off, then restored), which is what a real HAL with a
side-band status register must do.

### The tests (on both cores)

The timer's tests (`axil_timer_test.c`) check:

1. `registers_reset_and_read_back`: reset values, `LOAD` written and read back,
   a write to `COUNT` is SLVERR.
2. `interrupt_fires_and_is_handled`: start with `IE`; the handler runs once,
   and in it `STATUS.EXPIRED` reads 1.
3. `interrupt_is_acknowledged_by_a_register_write`: after the handler's W1C
   write, `EXPIRED` reads 0 and no further interrupt arrives over a long wait.
4. `masked_interrupt_does_not_fire`: start without `IE`; `EXPIRED` becomes 1 (the
   event happened) and the handler never runs.
5. `unmasking_a_pending_interrupt_fires_it`: setting `IE` with `EXPIRED` still
   set raises the line, and the handler runs and acknowledges it.

The Python tests run them against `axil_timer.v` (all pass) and against two
broken copies made at test time from the same file: `irq` stuck low (2, 3 and
5 fail) and `irq` ignoring `IE` (4 fails). Each is a recorded failed run that
names the failing check.

---

## 3. Precise bus-error traps: not done, and why STATUS stays

The request was to map SLVERR to a precise trap if feasible. It is not, on
either core here, and a trap that is not precise would be worse than the
status register:

* **PicoRV32 has no bus-error input.** Its `irq[2]` ("bus error") is raised
  only by the core itself, for a misaligned access; `mem_ready` has no error
  companion.
* **Mapping SLVERR to an external IRQ line is an interrupt, not an
  exception.** The core takes it at the next instruction boundary: by then
  the faulting load has written its destination register and retired, the
  return address is the next instruction, and the line can be masked (it is,
  inside any handler and inside the HAL's own critical sections). That is the
  definition of an imprecise exception, and code cannot use it to fail the
  access that caused it.
* **SERV has no bus error at all.** Its Wishbone ports have no `err`, and its
  single interrupt input is already the design's `irq`.

So the bridge keeps latching `BRESP`, `RRESP`, or `PSLVERR` into `STATUS`, and
the HAL returns it, exactly as in M27. The driver contract (`nirmaan_hal.h`
returns the response code) does not change either way. The path to precise
traps is a core whose data bus has an error input that raises a synchronous
access fault (Ibex's `data_err_i`, or a VexRiscv built with
`catchAccessFault`), registered as a third core: its runtime file would turn
`mcause` 5 or 7 into the same response code. That stays deferred.

---

## 4. The second core: SERV

**Chosen:** SERV 1.4.0 (`olofk/serv`, tag `1.4.0`, commit
`7d9cde4e6ca4f4c84d7512a752a4c187537dd373`), ISC license, in
`firmware_soc/serv/`: the seventeen files of its `rtl/` that `serv_rf_top`
uses, byte for byte, plus its `LICENSE`. A test pins every file's SHA-256 and
license header. One of them, `serv_compdec.v` (the compressed decoder, unused
here since `COMPRESSED=0` but instantiated in a generate branch Verilator
still resolves), is adapted from lowRISC's Ibex and keeps Ibex's Apache-2.0
header, the license of this repository.

**Why SERV, and not VexRiscv.** Both licenses are fine (ISC, MIT). SERV is
Verilog source: what is vendored is what its author wrote and releases, about
3,500 lines. VexRiscv is SpinalHDL (Scala); its Verilog is generated, so
vendoring it means pinning a build artifact of a configuration someone else
chose, and regenerating it needs a Scala toolchain. SERV is also as unlike
PicoRV32 as two RV32I cores get (bit-serial, Wishbone, standard CSRs and
`mret` against PicoRV32's custom IRQ instructions), which makes the
core-agnostic claim worth testing.

**Its cost:** SERV is bit-serial (32 or more cycles per instruction), so the
same tests take roughly ten times the cycles they take on PicoRV32: 682,218
against 63,642 for the register block, 640,145 against 96,154 for the timer,
and at most about 1,950,000 for a failing timer run. All are well within the
5,000,000-cycle limit, and seconds of wall time in Verilator.

**The wrapper.** `core_serv.v` adapts SERV to the SoC's memory interface,
which is PicoRV32's (`mem_valid`, `mem_ready`, word-aligned `mem_addr`,
`mem_wstrb`). SERV never has its instruction and data buses active together,
so the wrapper muxes them (as SERV's own `servile_arbiter` does), aligns the
address (SERV puts the byte address of a byte store on the bus; the SoC wants
the word and the strobe), and has no `trap` output: SERV's traps go through
`mtvec`. `core_picorv32.v` is the same interface around PicoRV32. The SoC
instantiates `` `NIRMAAN_CORE ``, a macro the build defines, so
`nirmaan_soc.v` names no core, as it names no design.

**As data.** `firmware_riscv.py` holds the cores in a registry:

```python
Core(name="serv", module="nirmaan_core_serv",
     verilog=(SOC / "core_serv.v", *(SOC / "serv" / f for f in SERV_FILES)),
     runtime=SOC / "irq_serv.S", march="rv32i_zicsr")
```

`fw.cross_build` and `fw.soc_test` take `core=` (default `picorv32`, so every
M27 run and requirement is unchanged); an unknown core is a recorded failed
run naming the known ones. `core` is declared on both tools' contracts
(`company/tools.py`, M28), the only new parameter M29 adds. The `fw.soc_test` backend keeps its M27 name,
`picorv32-verilator`, so recorded runs and refusals read as before; the core
that ran is in the log's `+define+NIRMAAN_CORE=`. A new core is one `register_core` call: its
wrapper Verilog and its runtime file, no change to the SoC, the backends, the
broker, or the gate (the crown-jewel test registers a third core, a PicoRV32
built with a barrel shifter and two-cycle ALU, from files in a temporary
directory, and runs the tests on it).

---

## 5. The code-size gate: `max_text_bytes`

`fw.cross_build` (and `fw.soc_test`) report a new metric, `text_bytes`, the
`text` column of `size` (code plus read-only data). M26's generic limit
applies: `max_text_bytes` fails a run whose image is larger, or whose size was
not measured. The `block-design` firmware stage's cross-build requirement
carries it, as data:

```python
checked("Driver and tests cross-build for bare-metal RV32I", "fw.cross_build",
        FileInput(param="sources", kinds=("driver", "driver_test")), when=when("riscv"),
        params=(("max_text_bytes", "16384"),)),
```

16 KiB is a quarter of the SoC's RAM, and about 1.6 times the fixture images
(10,012 to 10,180 bytes of text, mostly the runtime's `snprintf`). A run without the
parameter has no limit, as before; a seat's run gets it from the requirement,
and the policy counts only a run that carried it.

---

## 6. APB

**The bridge.** `bridge_apb.v` is an APB4 manager: a setup phase, then an
access phase held until `PREADY`, with `PSTRB` from the CPU's store and
`PSLVERR` mapped to SLVERR (`2`) in `STATUS`. `bridge_axil.v` is M27's
AXI4-Lite bridge moved into its own module behind the same interface. Both
instantiate the design through `` `NIRMAAN_DUT `` and connect `irq` when it
exists.

**Which bridge.** The backend reads the top module's ports: `s_axil_awaddr`
and `s_axil_araddr` mean AXI4-Lite; `psel`, `penable`, and `paddr` mean APB.
A design with neither is a recorded failed run naming both conventions. The
buses are data too (`register_bus`).

**The driver fixture.** `tests/fixtures/fw/apb_regs/` drives
`tests/fixtures/rtl/apb_regs/apb_regs.v` (the M26 block, unchanged): reset
values, every register written and read back, byte lanes through `PSTRB`, and
PSLVERR for a misaligned (`0x5`) and an out-of-range (`0x10`) offset, with an
unmapped write changing nothing. It passes on both cores.

The host co-simulation (`fw.test`) stays AXI4-Lite only, and does not route
interrupts; section 8.

---

## 7. Tests (`tests/test_nirmaan_riscv_next.py`)

1. The firmware stage's cross-build requirement carries `max_text_bytes`.
2. Parsers: `text_bytes` from `size`; an over-limit run fails with the limit
   named.
3. The SoC files name no design and no core; the cores and buses are data.
4. Real runs, each on both cores where it applies:
   * the M27 register-block driver passes on SERV as on PicoRV32;
   * the timer's interrupt tests pass on `axil_timer.v`;
   * they fail on the `irq`-stuck and `irq`-ignores-`IE` copies, naming the
     checks;
   * the APB driver passes against `apb_regs.v`, with the RTL's own PSLVERR in
     the log, and the same driver with a wrong register map fails, naming
     the check;
   * an image over `max_text_bytes` is a recorded failed run;
   * an unknown core, and a design with no bus the SoC knows, are recorded
     failed runs that say why.
5. Crown jewel `test_a_new_core_needs_no_core_changes`: a third core from a
   temporary directory, one `register_core` call, runs the tests.
6. SERV is unmodified (every file's SHA-256) and keeps its license; the
   import laws hold.

---

## 8. Deferred

* Precise bus-error traps (section 3): needs a core with a data-bus error
  input.
* Interrupts in the host co-simulation (`fw.test`): its harness drives
  AXI4-Lite only, and an interrupt-driven driver's tests link only on the SoC.
  The same `nirmaan_irq.h` could be implemented there by ticking the model
  until `irq`.
* An APB manager in the host harness, for the same reason.
* More than one interrupt line, and an interrupt controller (PLIC or CLIC).
* Running the gate on both cores: the requirement runs the default core;
  running SERV too is one more requirement with `params=(("core", "serv"),)`.
