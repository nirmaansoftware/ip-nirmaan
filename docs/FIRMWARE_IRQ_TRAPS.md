# Interrupts in host co-simulation, and precise bus-error traps (Milestone 35)

Status: design for the owner's review, implemented on branch `m35/host-irq`.
It continues `docs/FIRMWARE.md` (M25, the host co-simulation `fw.test`) and
`docs/RISCV_NEXT.md` (M29, interrupts on the SoC), and closes two items M29
deferred: interrupts in `fw.test`, and precise bus-error traps. Prose here is
free of em and en dashes per the standing style law.

After M29 an interrupt-driven driver could be tested only on the SoC: its
tests used `nirmaan_irq.h`, which the host harness did not implement, so they
did not even link under `fw.test`. And a bus error reached firmware only as a
status code read after the access: M29 found no way to trap on it precisely
and explained why. This milestone:

1. implements `nirmaan_irq.h` in the host harness, from the design's own
   `irq` output, so the same timer tests run under `fw.test` and on both cores;
2. adds a bus-fault API to the platform, delivered precisely in host
   co-simulation and on PicoRV32, and refused, with the reason, on SERV;
3. makes "the interrupt was taken" and "a bus error trapped" gate data:
   `require_irq` and `require_bus_error_trap`.

---

## 1. The laws

M25's, M27's, and M29's laws hold unchanged: a tool either ran, with its log
and parsed result on disk, or the broker refused it and said why; the driver
runs against the approved RTL, never a model of it. M35 adds:

1. **The interrupt is still the design's own wire.** The host harness reads
   the model's `irq` output and nothing else; it never raises an interrupt the
   RTL did not. A design whose `irq` is stuck, or ignores its enable, fails the
   same tests under `fw.test` that it fails on the SoC.
2. **"Precise" is a stated guarantee, per platform, and tested.** Section 4
   says exactly what a handler is promised on each platform. A platform that
   cannot keep the promise says so when asked (`nirmaan_bus_fault_attach`
   returns 0) rather than delivering something weaker under the same name.
3. **A required interrupt or trap is counted from the run, not claimed.** The
   gate parameters fail a run whose log shows no interrupt taken, or no trap
   delivered, by the platform's own code.

---

## 2. The platform API

`nirmaan_irq.h` (the platform's header, beside `nirmaan_hal.h`) keeps M29's
interrupt calls and gains the bus-fault calls:

```c
/* M29: the design's interrupt line. */
void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx);  /* NULL detaches */
unsigned nirmaan_irq_count(void);
unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles);

/* M35: a bus error, delivered as a trap. */
typedef struct nirmaan_bus_fault {
    uint32_t offset;    /* the bus offset of the faulting access, as the driver passed it */
    unsigned write;     /* 1 for a write, 0 for a read */
    unsigned response;  /* NIRMAAN_BUS_SLVERR or NIRMAAN_BUS_DECERR */
    uint32_t pc;        /* on a RISC-V core: the faulting load or store; in host co-simulation: 0 */
} nirmaan_bus_fault;
typedef void (*nirmaan_bus_fault_handler)(const nirmaan_bus_fault *fault, void *ctx);
int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx);  /* 1: attached; 0: not supported */
unsigned nirmaan_bus_fault_count(void);
```

`read32` and `write32` keep returning the response code, whether or not a
fault handler is attached: the trap is a second, earlier report of the same
access, never a replacement for the return value.

---

## 3. Interrupts in host co-simulation

### Wiring

The `fw.test` backend reads the top module's ports with the same function the
SoC backend uses (`design_ports`, now in `integrations/firmware.py` and
re-exported from `firmware_riscv.py`). A design with an `irq` output is built
with `-CFLAGS -DNIRMAAN_DUT_IRQ`, which compiles the harness's reads of
`irq`. A design without one is built as before; `nirmaan_irq_attach` still
links, and the handler simply never runs.

### When the handler runs

On a core, an interrupt is taken between any two instructions. A host program
is not a core: the driver's C runs natively, and the model advances only when
the harness clocks it. The harness therefore delivers an interrupt at the
points where the model can have changed, which are the points where a core
would have been able to take it:

* at the end of every `read32` and `write32`, after the response is recorded
  and before the call returns (on the SoC, the HAL's critical section ends
  at the same place);
* on every clock cycle of `nirmaan_irq_wait`;
* when a handler is attached while the line is already high.

Delivery is level sensitive, as on both cores: while the line is high and a
handler is attached, the harness counts the interrupt, prints
`FWTEST IRQ taken`, and calls the handler. The handler is not re-entered
(as on both cores, which do not nest), and after it returns the harness
clocks the model one cycle, the cost of a return from interrupt. A handler
that never acknowledges is called again and again, each time a cycle later, so
an interrupt storm ends at the harness's new cycle limit (5,000,000, the SoC's)
as a recorded failed run instead of hanging the job.

### The tests

The M29 timer tests (`tests/fixtures/fw/axil_timer/axil_timer_test.c`) run
unchanged under `fw.test`: the interrupt fires and is handled, the
acknowledgement is a real W1C write from the handler, it stays quiet after the
acknowledgement, a masked expiry does not fire, and unmasking a pending one
does. The two broken copies (`irq` stuck low; `irq` ignoring `IE`) fail the
same checks in host co-simulation as on both cores.

---

## 4. Precise bus errors

### What "precise" means here

A bus error is reported **precisely** when its handler runs before any later
access or instruction of the interrupted program, and is told which access
failed. Concretely, per platform:

| Platform | When the handler runs | What it is told | Not promised |
|---|---|---|---|
| Host co-simulation (`fw.test`) | inside the `read32` or `write32` that failed, after the response and before the call returns | offset, read or write, response; `pc` 0 | nothing further: the driver's C is not instructions on a model |
| PicoRV32 (`fw.soc_test`, default core) | at the instruction boundary right after the faulting load or store: no later instruction executes first | offset, read or write, response, and the faulting instruction's address (`pc`) | restartability: the load has already written its destination (with the bus's data, zero here), so the handler reports, it does not retry; inside another interrupt handler the trap waits for `retirq` |
| SERV (`fw.soc_test`, `core=serv`) | never: `nirmaan_bus_fault_attach` returns 0 | (the access still returns its response code) | anything: see below |

The response code returned by `read32` and `write32` stays the per-access
report on every platform, and the tests assert it per access: a sequence of
OKAY, SLVERR, OKAY, SLVERR accesses must return exactly those codes in that
order (`bus_errors_are_reported_per_access`).

### How PicoRV32 does it

M29 rejected "map SLVERR to an external interrupt line" because an interrupt
is taken at the next instruction boundary, after the access has retired, and
can be masked. Both objections are about timing, and both can be closed for
PicoRV32, because of how it takes interrupts:

* PicoRV32 checks for a pending interrupt in its fetch state, when the next
  instruction has been decoded and before it executes
  (`decoder_trigger && !irq_active && !irq_delay && |(irq_pending & ~irq_mask)`).
  After a load or store completes, the very next state is that check.
* `irq_pending` samples the `irq` inputs every cycle. The SoC raises the
  bus-error line on the same clock edge as `mem_ready` for the faulting
  access, so the line is already pending when the core reaches that check.
* So the trap is taken at the boundary immediately after the faulting
  instruction. The core writes the address of the next, unexecuted
  instruction into `q0`; with RV32I (no compressed instructions here) the
  faulting instruction is at `q0 - 4`.

The line is a dedicated one, `irq[4]` (0 to 2 are the core's own, 3 is the
design's), level sensitive (`LATCHED_IRQ` bit 4 clear), and it is never masked
by the HAL: the HAL's critical sections now mask `irq[3]` only, so an access
inside one still traps at once. The one case left is nesting: PicoRV32 does
not take an interrupt while it is in a handler, so a bus error raised inside
the design's interrupt handler is delivered after `retirq`. That trap still
names the right offset, but its `pc` is not the faulting instruction; the
table above says so.

**The SoC side** (`nirmaan_soc.v`) adds three control registers:

| Address | Name | Access | What |
|---|---|---|---|
| `0x2000_0010` | `BERR_CTRL` | RW | bit 0 `TRAP`: latch errors and raise the line; bit 1 `WIRED` (read only): the core has a bus-error input |
| `0x2000_0014` | `BERR_INFO` | R, W1C | bit 0 `PENDING` (write 1 to clear), bit 1 `WRITE`, bits 3:2 the response |
| `0x2000_0018` | `BERR_ADDR` | R | the bus offset of the faulting access |

While `TRAP` is set, a device transfer whose response is not OKAY latches
`BERR_INFO` and `BERR_ADDR` and sets `PENDING`, which is the core's bus-error
line. The first error wins until it is cleared. With `TRAP` clear (the default,
and the state of every M27 and M29 run) nothing changes: `STATUS` is the only
report, as before.

**The core side.** `Core` gains `bus_error: bool`; `picorv32` sets it, which
adds `+define+NIRMAAN_CORE_BUS_ERR` so the SoC connects its `bus_err` port and
`WIRED` reads 1. A core without it (SERV, or the crown-jewel third core of
M29) is built exactly as before. Each core's runtime file defines one more
function, `nirmaan_core_bus_error_set`, which unmasks `irq[4]` on PicoRV32 and
returns 0 (unsupported) on SERV.

**The runtime.** PicoRV32's trap entry reads the pending mask (`q1`, with
`getq`) and the return address (`q0`), and dispatches the bus error first,
then the design's interrupt, either or both. The bus-fault dispatch reads
`BERR_INFO` and `BERR_ADDR`, prints

```
FWTEST TRAP bus-error read 0x5 SLVERR at pc 0x000004c4
```

calls the handler, and clears `PENDING` before returning. The handler must not
access the device: it would overwrite `STATUS` for the interrupted HAL access
(the same rule M29 set for interrupt handlers).

**How the tests prove it.** The fault tests check the offset, the direction,
and the response the handler saw, and that the handler had already run when
the failing `read32` or `write32` returned. The Python test then takes the
`pc` from the log and disassembles the image the run built: the instruction
at that address must be the HAL's own device load (`lw` in `soc_read32`) or
store (in `store`). A trap taken one instruction late would point elsewhere.

### Why not SERV

SERV's data bus is Wishbone without `err`, and it has one interrupt input,
`i_timer_irq`, which already carries the design's `irq`. Sharing that input
would give an interrupt taken on the rising edge of a combined line, so a bus
error that arrives while the design's line is high would never be seen.
Adding an `err` path would mean modifying the vendored core, which
the M29 law forbids (it is pinned byte for byte). So on SERV,
`nirmaan_bus_fault_attach` returns 0 and the fault test reports
`unmapped_read_traps_precisely` as failed with "this platform has no precise
bus-error trap". The response code from `read32` and `write32` is unaffected.

---

## 5. The gate, as data

Two new tool parameters, declared on the M28 contracts of `fw.test` and
`fw.soc_test`:

| Parameter | Values | A run fails when |
|---|---|---|
| `require_irq` | `auto`, `yes`, `no` (default) | required and no `FWTEST IRQ taken` line was printed by the platform. `auto` requires it when the top module has an `irq` output; `yes` also fails, before anything runs, on a design without one |
| `require_bus_error_trap` | `yes`, `no` (default) | required and no `FWTEST TRAP` line was printed by the platform |

The steps write the resolved requirement into `fw_require.json` in the run's
working directory, and the parser reads it back, the pattern `dft.atpg` uses
for its limits; so the limit is part of the recorded run. The counts are
metrics, `irq_taken` and `bus_error_traps`.

The `block-design` firmware stage carries them:

* the `fw.test` requirement, and the `fw.soc_test` requirement when the
  request names RISC-V, now carry `require_irq=auto`: a design with an `irq`
  output must have its interrupt taken by its driver's tests before review;
* when the request asks for interrupts (a new feature, `interrupts`:
  "interrupt", "IRQ"), they carry `require_irq=yes` instead;
* when the request names RISC-V and asks for bus-error traps (a new feature,
  `bus_errors`: "bus error", "precise trap"), a further `fw.soc_test`
  requirement carries `require_bus_error_trap=yes` on the default core.

M28's policy matches a run's parameters to the requirement's exactly, so a
run without the parameter does not count.

---

## 6. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A core with a precise bus-error path | `register_core(Core(..., bus_error=True))`, whose wrapper has a `bus_err` input and whose runtime file implements `nirmaan_core_bus_error_set` | none |
| A platform that reports traps another way | print `FWTEST TRAP ...` from its trap path | none |

The crown jewel `test_a_new_bus_error_core_needs_no_core_changes` registers
a third core from a temporary directory (PicoRV32 with a barrel shifter and
a two-cycle ALU, with a `bus_err` input) with `bus_error=True`, and the fault
tests pass on it with precise traps, the `pc` checked against the image.

---

## 7. Tests (`tests/test_nirmaan_firmware_irq.py`)

1. The parser counts `FWTEST IRQ` and `FWTEST TRAP` lines, and a required one
   that is missing fails the run.
2. The parameters are declared; the gate carries them, by feature.
3. Host co-simulation: the timer's five interrupt checks pass, with the W1C
   acknowledgement on the bus; the two broken IRQs fail the expected checks;
   a timer driver with the wrong register map fails; `require_irq=yes` on a
   design without `irq` is a recorded failed run; `require_irq=auto` fails
   tests that never take the design's interrupt, and passes a design
   without one.
4. Bus errors: per-access response codes, and precise traps, pass in host
   co-simulation and on PicoRV32 (the `pc` disassembled from the run's own
   image); on SERV the trap check fails, saying why; a design that answers
   unmapped offsets with OKAY fails the trap checks.
5. Crown jewel, import laws, and the contract scan.

---

## 8. Deferred

* Precise traps on SERV: needs an `err` input on its data bus, which means a
  modified core, or a different core (Ibex's `data_err_i`).
* Restartable bus errors (the faulting load not writing its destination):
  PicoRV32 has no way to cancel a completed load.
* Bus errors on CPU addresses outside the device window (they still read
  zero), and on instruction fetches.
* An APB manager in the host harness, and more than one interrupt line.
