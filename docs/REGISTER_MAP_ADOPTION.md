# The register map in `block-design`, bit fields, and an APB harness (M41)

Status: implemented on branch `m41/regmap-adoption`. This document was written
before the code and records the decisions the code follows. Prose here is free
of em and en dashes per the standing style law.

M30 (`docs/REGISTER_MAP.md`) made a register map a validated intermediate
representation with lowerings and a generated co-simulation test, and
deferred three things this milestone closes:

1. **Adoption in a workflow.** The map was used only by the evaluation case.
2. **Bit fields.** Every register was one 32-bit word.
3. **An APB harness.** The host co-simulation (`fw.test`, M25) drives
   AXI4-Lite only, so an APB map was a recorded failed run.

What already exists and is not redone: M29 put an APB bridge in the RISC-V
SoC (`fw.soc_test`), so APB RTL is already reachable from firmware through a
core. What it does not give is an APB manager in the host co-simulation, which
is the harness `fw.test` and `regmap.verify` use. That is what "an APB
harness" means here.

---

## 1. Adoption in `block-design`

### Decision: the map is the output of its own stage, and an approved input downstream

A register map is design intent. It must be reviewed and approved before it
judges anything, exactly as the interface spec is, so it is the **output** of
a stage, and an approved **upstream input** to the stages it judges:

| Stage | Change |
|---|---|
| `register-map` (new) | Capability `arch.interface`, depends on `interface-spec`, planned only when the request asks for a register map (feature `register_map`). Output `register_map`. Before review: `regmap.check` over the file. Reviewed by `arch.review`. |
| `rtl-implementation` | Also depends on `register-map`. When the feature is present, before review: `regmap.verify` with the approved map (`map`, upstream) on the submitted RTL (`rtl`, `top` from its entry). |
| `firmware` | Also depends on `register-map`. `fw.build` and `fw.test` (and the RISC-V pair) take the approved map as an optional upstream input (section 1.2). |

Why not an output of `interface-spec`: an added expected output is reported as
a missing deliverable by the export whenever it is absent, and a FIFO or an
arbiter has no registers. A separate conditional stage plans the map only when
it is asked for. Why opt in (feature `register_map`, from "register map" or
"regmap" in the request) rather than on every request that mentions
registers: an existing register-block request keeps its plan, and the
evaluation cases keep their upstream; the M29 verification plan took the same
route. A depends-on edge to a stage that is not planned is dropped, as
elsewhere.

### 1.2 The conditional-upstream rule

M30 noted that adoption needs "a conditional-upstream rule". It is one new
field on `FileInput`: `optional`. An optional upstream binding is filled from
the approved upstream artifacts of its kinds when there are any, and left out
when there are none. The policy (`evidence-before-review`) follows the same
rule: when an approved upstream file of that kind exists, a passing run must
have used it, so a seat cannot dodge the map by leaving the parameter out;
when none exists, the binding asks for nothing. That keeps one requirement per
check on the firmware stage instead of a copy per combination of features.

### 1.3 The header generated from the approved map

`fw.build`, `fw.test`, `fw.cross_build`, and `fw.soc_test` take an optional
`map` parameter. With it:

* The map's `c-header` lowering is written as `<block>_map.h` into an include
  directory searched after the driver's own directories. A driver that writes
  no register header includes this one: the header is generated, never
  hand-copied.
* An agreement unit is compiled with the sources. It includes `<block>_map.h`
  exactly as the driver does (so it sees the driver's own header if the driver
  wrote one) and fails the build with `#error` when any register's `_OFFSET`
  macro is missing, or when any numeric macro the generated header defines
  (offsets, resets, the count, field shifts, masks, and resets) is defined
  with another value. The `#error` names the macro and the map's value.

So "the driver agrees with the map" is a compile-time fact checked by a real
compiler run, and the driver's behaviour is still judged by its own tests on
the RTL.

### 1.4 The RTL against the map

`regmap.verify` (M30) is the before-review check: a C test generated from the
map, run through the co-simulation harness of the map's bus, reading every
register's reset value over real bus transfers and comparing it with the map,
then the write, read-only, write-1-to-clear, strobe, and unmapped checks
(section 2.4).

---

## 2. Bit fields

### 2.1 The format

A register gains `fields`, each:

```json
{"name": "MODE", "msb": 3, "lsb": 1, "access": "rw", "reset": 2, "description": "..."}
```

* `lsb` is required; `msb` defaults to `lsb` (a one-bit field).
* `access`: `rw`, `ro`, `wo`, or the new `w1c` (reads the bit; writing 1
  clears it, writing 0 leaves it). `w1c` is also allowed on a whole register.
* `reset` is the field's value, not shifted.
* Bits no field holds are reserved: they read zero and ignore writes.
* A register with fields keeps its `reset`, which must equal its fields'
  resets put in place (the specification's table states it, so the two are
  checked against each other), and its `access` must be `rw` (the default):
  its fields' accesses govern its bits.

A register without fields is exactly the M30 register.

### 2.2 Validation

New problems `validate` lists: a field name that is not a C identifier or
appears twice in its register; `msb` below `lsb`; a field beyond the register
width; two fields that overlap (naming the first shared bit); a field reset
wider than the field; a register reset that disagrees with its fields; a
register with fields whose access is not `rw`.

### 2.3 Header

For each field, the `c-header` lowering adds `<BLOCK>_<REG>_<FIELD>_SHIFT`,
`_MASK` (in place), `_RESET` (the field value), and two accessors:
`_GET(reg)` and `_SET(reg, value)` (the register value with the field
replaced). They are macros, so the header stays free of functions and
compiles alone under the strict flags. The `markdown` lowering adds a field
table after the register table when any register has fields; a map with no
fields lowers exactly as before.

### 2.4 The generated test

Each register lowers to four masks: `rw`, `ro`, `w1c`, `wo` (a register
without fields puts all 32 bits in the mask of its access). Every check is
written over the masks, so field registers and plain registers share it:

| Check | What it does |
|---|---|
| `reset_values` | Reads every register; the readable bits (all but `wo`) must equal the reset, reserved bits zero. A mismatch names the field (`CTRL.MODE`) or "reserved bits". |
| `write_then_read_every_register` | Writes a pattern to every register with `rw` or `wo` bits, with `w1c` bits written 0, before reading any back; then each register with `rw` bits must read the pattern in its `rw` bits and its reset in `ro` and `w1c` bits. |
| `write_one_to_clear` | For each register with `w1c` bits: writing 0 to them leaves them; writing 1 clears them. |
| `read_only_ignores_writes` | For each register with `ro` bits: writes the inverse of the reset into them (`rw` bits as read, `w1c` bits 0) and reads back the same value. |
| `byte_strobes` | As in M30, on the first register whose 32 bits are all `rw`. |
| `unmapped_response` | As in M30. |

Checks run in that order, and the first failure names its check. A `w1c` bit
whose reset is 1 is fully distinguished: it would read 0 after a 0 write if it
were `rw`, and 1 after a 1 write if it were `ro`.

### 2.5 The fixture

Neither existing register block has fields, read-only bits, or
write-1-to-clear bits, and their RTL is covered by proofs and evaluation cases
that should not move. So a new APB fixture, `tests/fixtures/rtl/apb_csr/`, has
them: `CTRL` (fields `ENABLE` [0] rw, `MODE` [3:1] rw reset 2), `SCRATCH`
(plain rw), `STATUS` (`RESET_DONE` [0] w1c reset 1, `VERSION` [15:8] ro reset
0x12), and `ID` (a plain read-only register). It is lint-clean under
`verilator --lint-only -Wall`. Its driver, in `tests/fixtures/fw/apb_csr/`,
writes no register header: it uses the generated one, field accessors
included.

---

## 3. The APB harness

`firmware_harness/apb_manager.cpp` implements `nirmaan_hal` as an APB4
manager on the Verilator model: a setup cycle (`psel`, address, direction,
data, and `pstrb`, zero for reads), then an access phase held until `pready`
(at most 1000 cycles, then a recorded bus timeout). `pslverr` is reported as
`NIRMAAN_BUS_SLVERR`, so a driver sees the same response codes on either bus.
It prints the same `FWTEST` lines, so the parser is unchanged.

**The protocol is selected as data.** The host harness keeps a registry of
bus managers by bus name (`register_cosim_bus`), with `axi4-lite` and `apb`
shipped. `fw.test` picks the manager from its `bus` parameter, else from the
bus its `map` names, else `axi4-lite` (so every M25 call is unchanged). A bus
parameter that contradicts the map, or a bus with no manager, is a recorded
failed run that says so. `regmap.verify` uses the map's bus, so an APB map is
now simulated instead of refused.

---

## 4. Tests (`tests/test_nirmaan_regmap_adoption.py`)

* Field validation names each problem; the fixture maps are clean.
* The header has the field macros, compiles strict, and its accessors are
  right (a compiled program checks them).
* APB host co-simulation: the M26 APB driver passes on `apb_regs.v` with the
  RTL's own PSLVERR in the log; a driver with a wrong offset fails, by its
  tests without a map and at compile time with one.
* `regmap.verify` on APB: passes on both APB fixtures, fails a map whose reset
  disagrees with the RTL, and fails field mutants (a reset, a write-1-to-clear
  bit built as read/write, a read-only field that takes writes), naming the
  check and the field.
* The fixture driver builds and passes using only the generated header.
* `block-design` end to end: a request for a register map plans the stage;
  the map, the RTL (with `regmap.verify` over APB), and the driver (with the
  map) each go through their seat, real runs, review, and approval; a seat
  whose RTL disagrees with the approved map cannot reach review; a driver run
  that leaves the approved map out is refused by the policy.
* Crown jewel: a new co-simulation bus, registered in the test with its own
  manager file, runs `fw.test` with no core change.
* The import laws hold for the changed modules.

## 5. Deferred

* Fields in `fw.soc_test` beyond the header: the SoC run takes the map for the
  header and the agreement unit, but its bus still comes from the RTL ports.
* Other field accesses (`w1s`, `rc`, `w0c`) and hardware-set events in the
  generated test: the test checks only what a bus manager can observe from
  reset.
* Adopting the map on `new-ip`'s interface and RTL stages.
* Interrupts in the host co-simulation (still SoC only).
