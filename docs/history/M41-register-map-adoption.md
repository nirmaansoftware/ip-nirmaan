# Milestone 41 - The register map in `block-design`, bit fields, and an APB host harness (after Stage 6)

Closes what M30 deferred. Design doc: `docs/REGISTER_MAP_ADOPTION.md`. No
version bump.

Key points worth not re-deriving:
- **Adoption is opt-in, as data.** Feature `register_map` ("register map",
  "regmap") plans a `register-map` stage on `block-design` (`arch.interface`,
  after `interface-spec`, output `register_map`, `regmap.check` before
  review). `rtl-implementation` and `firmware` depend on it. The RTL stage
  adds `regmap.verify` (approved map, the submitted RTL, its entry as `top`)
  with `when=register_map`, after the shared `RTL_GATES`; the gate tests now
  allow checks after the shared ones. Not on every "registers" request, so
  existing plans and evaluation cases are unchanged.
- **The conditional-upstream rule is `FileInput.optional`.** An optional
  upstream binding is filled when an approved upstream file of its kinds
  exists and left out when none does; the `evidence-before-review` policy
  still demands that a passing run used it when it exists. Every firmware
  check (`fw.build`, `fw.test` both M35 variants, `fw.cross_build`, the
  `fw.soc_test` variants) carries `APPROVED_MAP`; the test helper
  `gated_submit` honours `optional`.
- **The header is generated, not copied.** With `map`, the firmware tools
  write the `c-header` lowering as `<block>_map.h` into an include directory
  searched after the driver's own (`_compile(include=...)`), and compile an
  agreement unit that includes `<block>_map.h` as the driver does and
  `#error`s when an `_OFFSET` is missing or any numeric macro differs. A
  driver may write no register header at all (`tests/fixtures/fw/apb_csr/`).
- **Bit fields**: `BitField` (`name`, `lsb`, optional `msb`, `access`,
  `reset` unshifted); new access `w1c`. A register with fields must keep
  access `rw` and a `reset` equal to its fields' composed resets. Header:
  `_SHIFT`, `_MASK`, `_RESET`, `_GET(reg)`, `_SET(reg, value)` macros;
  markdown gains a field table only when fields exist.
- **The generated test works over four masks per register** (`rw`, `ro`,
  `w1c`, `wo`); reserved bits read zero. Order: `reset_values` (a mismatch
  names `REG.FIELD` or reserved bits), `write_then_read_every_register`,
  `write_one_to_clear` (before the read-only check, whose writes put 0 in
  `w1c` bits, so a w1c bit built as rw is named by the right check),
  `read_only_ignores_writes`, `byte_strobes`, `unmapped_response`.
- **APB host harness**: `firmware_harness/apb_manager.cpp`, the M35
  `axil_manager.cpp` with the bus functions replaced (setup, access until
  `pready`, PSLVERR as SLVERR), so interrupts and bus-fault handlers work the
  same. A registry `register_cosim_bus(bus, manager)`; `fw.test` takes `bus`,
  else the map's bus, else `axi4-lite`; a contradiction or an unknown bus is a
  recorded failed run. `regmap.verify` uses the map's bus, so an APB map is
  simulated (`integrations/regmap.HARNESSED_BUSES` is gone).
- **Fixtures**: `tests/fixtures/rtl/apb_regs/register_map.json`, and a new
  lint-clean APB block `tests/fixtures/rtl/apb_csr/` (CTRL fields, SCRATCH,
  STATUS with a w1c `RESET_DONE` that resets to 1 and a ro `VERSION`, ro ID)
  with its map and a driver that uses only the generated header.

`tests/test_nirmaan_regmap_adoption.py` (31): field validation, the header
and its accessors compiled and run, the APB driver on `apb_regs.v` over the
host harness (and a wrong offset caught by its tests and, with the map, at
compile time), `regmap.verify` on both APB fixtures and on field mutants, the
generated header on the RISC-V SoC too, `block-design` end to end (map, RTL
judged by the map over APB, driver with the map), RTL that disagrees with the
approved map refused although its testbench passes, a driver run without the
approved map refused by the policy; crown jewel
`test_a_new_cosimulation_bus_needs_no_core_changes`.
