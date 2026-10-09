# The register map as data (M30)

The fourth structural-review milestone (`docs/architecture/target-state.md`
section 5). The review's compiler principle,
applied where it pays first: design intent that is only prose cannot be checked
or lowered. Today a register map lives as a Markdown table in an interface
specification, and the C header a driver includes is written by hand from it
(`tests/fixtures/fw/axi4_lite/axi4_lite_regs_map.h`). M30 makes the map a
structured intermediate representation that is validated, lowered, and used to
judge RTL.

## The representation

`RegisterMap` (`models/regmap.py`), loaded from JSON:

```json
{"block": "axi4_lite_regs", "bus": "axi4-lite", "addr_width": 4, "data_width": 32,
 "unmapped": "slverr",
 "registers": [{"name": "REG0", "offset": 0, "access": "rw", "reset": 0}, ...]}
```

- `access`: `rw` (every bit writable), `ro` (writes ignored, reads the reset
  value), `wo` (writes accepted, reads not defined, so never checked).
- `unmapped`: the response to an address no register holds (`slverr`,
  `decerr`, or `okay`); such a write changes no register.
- Bit fields are out of scope for M30: every register is one `data_width` word.

## Validation (pure)

`nirmaan.regmap.validate(map)` lists every problem: a data width other than 32
(the harness and the lowerings assume it), a misaligned offset, an offset
outside the address space, two registers at one offset, a name that is not a C
identifier or appears twice, a reset value wider than the register, no
registers.

## Lowerings (a registry)

`register_lowering(name, fn)`; two ship:

- `c-header`: `#define <BLOCK>_COUNT`, `<BLOCK>_<NAME>_OFFSET`,
  `<BLOCK>_<NAME>_RESET` for each register, with the bus and access in comments.
  It compiles under the firmware build's strict flags.
- `markdown`: the register table an interface specification carries.

`nirmaan regmap check MAP` and `nirmaan regmap lower MAP --to NAME` expose them.

## Judging RTL with the map

Two tools, through the broker, with contracts:

- `regmap.check` (`map`): validation as a recorded run, so a map can be a
  before-review check like any other.
- `regmap.verify` (`map`, `rtl`, `top`): generates a C test from the map and
  runs it on the RTL with the existing AXI4-Lite co-simulation harness (M25's
  `fw.test` machinery: real VALID/READY handshakes on a Verilator model). The
  generated test checks every register's reset value; writes every writable
  register before reading any back, so aliasing shows; checks that read-only
  registers ignore writes; checks byte strobes on the first read/write
  register; and checks that unmapped and misaligned addresses answer with the
  declared response and change nothing. A map for a bus with no harness (APB
  today) is a recorded failed run that says so; nothing is simulated.

## Where it is used in M30

- The AXI4-Lite fixture gains `register_map.json`, transcribed from its
  interface specification's section 3.
- The `rtl/axi4-lite-regs` evaluation case (M27) gains a second held-out
  check: `regmap.verify` with the reference map on the seat's RTL.
- **Not yet in a workflow.** Making the interface-spec seat produce a
  `register_map` would add an expected output, which the export reports as a
  missing deliverable when absent. Adopting it in `block-design` (and running
  `regmap.verify` before RTL review whenever an approved upstream map exists)
  is the next step, with the conditional-upstream rule it needs.

## Tests (`tests/test_nirmaan_regmap.py`)

- Validation catches each problem above; the fixture map is clean.
- The `c-header` lowering compiles under `fw.build`; its offsets and resets
  match the hand-written fixture header.
- `regmap.verify` passes on the fixture RTL, and fails, with the failing check
  named, on RTL whose `reg3` resets to all ones, on RTL where writing REG2
  lands in REG1, and on a map that declares `okay` for unmapped addresses.
- An APB map is a recorded failed run naming the missing harness.
- The evaluation case's new held-out check passes on replay.
- Crown jewel `test_a_new_lowering_needs_no_core_changes`: a lowering
  registered in the test is listed and used by `nirmaan regmap lower`.
