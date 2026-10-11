# Milestone 25 (part) - Physical design through OpenSTA and OpenROAD (roadmap Stage 6)

`sta.run` (backend `opensta`, executable `sta`) and `pnr.run` (backend
`openroad`) moved from `CONTRACT_ONLY` to `AVAILABLE`, in
`nirmaan/integrations/physical.py` (bindings) and `pd_parsers.py` (pure
parsers), on the M21 `register_backend` registry. `synth.run` gained a second
backend, `yosys-liberty` (chosen with `backend=yosys-liberty`), that maps to a
Liberty library and writes `netlist.v`, the input STA and PnR need. **Neither
OpenSTA nor OpenROAD has run in this repository**: they are not installed
locally or in CI, and Homebrew has no formula. Version bump left to the
coordinator.

Key design points worth not re-deriving:
- **One staged `pnr.run`**, not four tools: OpenROAD is one process and one
  database, so one run does floorplan, place, route (ending at `stop_after`),
  then timing, and prints `nirmaan-stage:` / `nirmaan-stage-done:` markers the
  parser reads. The existing skills already named `pnr.run`.
- **The PDK is an input, never bundled.** `liberty`, `tech_lef`, `lef`, `site`,
  `hor_layers`, `ver_layers` are task parameters; relative files resolve under
  `pdk_root` or `NIRMAAN_PDK_ROOT`. A missing PDK input is a *refusal* (the
  probe; no run recorded), like a missing executable; a missing netlist or SDC
  is a recorded failed run, like a missing source.
- `Backend` gained two optional generic fields in `eda.py`: `environment`
  (asked by the probe after the executables; its reason joins the refusal) and
  `files` (parameters whose paths must exist). `select_backend`'s refusal text
  now reads `<backend> needs <exe> on PATH, not found; <backend>: <reason>`.
- `nirmaan.runtime.unavailable_reason(tool, params)` exposes the broker's probe;
  `nirmaan org tools` shows it in a new **Here** column.
- STA passes only with a worst setup slack reported and non-negative, hold
  non-negative, and no violating endpoint; `worst slack INF` (unconstrained)
  fails. PnR passes only when every requested stage and timing finished, DRC
  count is 0 after routing, and timing is met.
- New workflow `physical-implementation` (intent `physical_implementation`,
  priority 50: "place and route", "PnR", "physical design/implementation"):
  timing-constraints -> synthesis -> floorplan -> place-route -> sta-signoff
  (gate.implementation). Existing capabilities and skills only. `floorplan`
  artifacts and `pd.floorplan` file into `04_rtl` in the export. The landing
  page's workflow tile is now 9.

Fixtures `tests/fixtures/pd/`: `axi4_lite_regs.sdc` (100 MHz), `tiny_cells.lib`
(a toy Liberty library, no timing, so `yosys-liberty` runs for real in CI), and
four **synthetic** logs (`synthetic_*.log`, first line `# SYNTHETIC:`) written to
the documented report formats. `tests/test_nirmaan_physical.py` (22 tests, 2
skip without `sta`/`openroad` and sky130 under `NIRMAAN_PDK_ROOT`; CI does not
require them). Test stand-in executables exercise the runner (script written,
argv, parse, timeout, failures). Crown jewel
`test_a_new_pd_backend_needs_no_core_changes`. The `test_nirmaan_eda` catalog
test no longer lists `sta.run` and `pnr.run` as contracts. Design doc:
`docs/PHYSICAL_DESIGN.md`. Deferred: CTS, power grid, tap/filler cells, repair,
parasitic extraction, MCMM, captured logs, a physical deliverable folder.
