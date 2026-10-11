# Milestone 30 - The register map as data

The fourth structural-review milestone: a
register map that was only a table in an interface spec becomes an
intermediate representation that is validated, lowered, and judges RTL.
Design doc: `docs/REGISTER_MAP.md`. No version bump.

Key design points worth not re-deriving:
- `RegisterMap` (`models/regmap.py`): block, bus, `addr_width`, 32-bit
  registers with `rw`/`ro`/`wo` access and reset values, and the `unmapped`
  response (`slverr`, `decerr`, `okay`). No bit fields yet.
- `nirmaan/regmap.py`: `validate` (width, alignment, address space, overlaps,
  C identifiers, duplicates, reset width), a lowering registry
  (`register_lowering`; `c-header` compiles under strict flags and agrees with
  the hand-written firmware header; `markdown` reproduces the AXI4-Lite spec's
  section 3 table line for line), and `c_test`, a `nirmaan_fw_test` whose
  checks run in order (reset values, write-then-read with every register
  written first, read-only, strobes, unmapped) because the co-sim parser names
  only the first failing check.
- Tools with contracts: `regmap.check` (validation as a recorded run) and
  `regmap.verify`, a backend that writes the generated test and reuses
  `fw.test`'s co-simulation steps and parser unchanged. A bus with no harness
  (APB: the host harness drives AXI4-Lite only; M29's `fw.soc_test` reaches APB
  through a RISC-V core) is a recorded failed run, never a simulation. Granted to `rtl_design`
  (both) and `interface_specification` (check).
- The `rtl/axi4-lite-regs` evaluation case holds the map out as a second judge;
  the gates-miss eval test now expects both judges to fail the `reg3` mutant.
- Not adopted in a workflow yet: an added expected output would show as a
  missing deliverable in the export; a conditional-on-upstream rule is needed.
- The M23 crown jewel's hypothetical `regmap.check` collided with the core
  tool and was renamed `regmap.overlaps`.

`tests/test_nirmaan_regmap.py` (19): real co-simulation passes on the fixture
RTL and fails on a `reg3` reset mutant, a REG2-into-REG1 alias, and a map that
misstates the unmapped response; crown jewel
`test_a_new_lowering_needs_no_core_changes`. With the M29 parts merged, the
standard local run is 1387 passed, 3 skipped.
