# Milestone 27 (physical design) - OpenROAD and OpenSTA run for real in CI (after Stage 6)

M25's `sta.run` and `pnr.run` bindings had never run. A new CI job,
`physical-design`, runs them for real, and the first runs' breakages are
fixed. Design doc: `docs/PHYSICAL_DESIGN.md` (sections 8 and 10). No version
bump.

Key points worth not re-deriving:
- **Where it runs.** Only in CI: the job runs inside
  `openroad/orfs:26Q3-687-gc63a606f9` (pinned by digest; ORFS `c63a606f9`,
  OpenROAD `c487fc70`, Yosys 0.68+post, Nangate45 under `flow/platforms`),
  Python 3.12 from `setup-uv`, `NIRMAAN_PDK_ROOT` at the platforms directory,
  `NIRMAAN_REQUIRE_EDA="yosys openroad"`, and only
  `tests/test_nirmaan_physical.py`. Every run's working directory is uploaded as
  the `pd-logs` artifact. The main test jobs are unchanged. macOS: no Homebrew
  formula and no Docker, so the real tests skip locally.
- **No standalone `sta` exists in packaged OpenROAD**, and `openroad` has no
  OpenSTA-only mode. `sta.run` gained a second backend, `openroad-sta`: the same
  script under `openroad`, plus `read_lef` (OpenROAD links into its database;
  `ORD-2010` without LEFs), so it also needs `tech_lef` and `lef`. `opensta`
  stays first when `sta` is on PATH.
- **Fixes from the real output:** `yosys-liberty` takes optional
  `tie_high`/`tie_low` (`CELL/PORT`, via `hilomap`), since the detailed router
  rejects a constant net (`DRT-0305`); the area line is `um^2`, not `u^2`;
  `report_worst_slack` prints `worst slack max <n>` and `report_tns` `tns max
  <n>` (parsed by label, unlabelled still read in order); `-group_count` and
  `-endpoint_count` became `-group_path_count` and `-endpoint_path_count`; a
  violator count at the report cap (`VIOLATOR_REPORT_LIMIT`, 100) is "at least".
- **Real numbers** (AXI4-Lite block, Nangate45, ideal clock, no CTS or power
  grid): STA at 100 MHz met, setup slack 7.264, hold 0.101; at 5 GHz
  (`axi4_lite_regs_fast.sdc`) violated, setup -0.905, TNS -157.481; place and
  route to route, 41% utilization, 0 DRC (the signal routing only; power pins
  are unconnected), wirelength 10783 um, setup slack 7.120; at 300% utilization
  it fails in placement (`GPL-0301`).

Fixtures: the four `synthetic_*.log` are deleted; `opensta_met.log`,
`opensta_violated.log`, `openroad_route.log`, and `openroad_error.log` are
captured from CI run 36600440325, each with a `# CAPTURED:` first line and the
log unedited below it. The real-tool tests moved from sky130 to Nangate45 and
gained the violated-timing and failed place-and-route cases; new unit tests
cover the `openroad-sta` fallback and tie cells. The standard local run is 1128
tests with 3 skipped (the three real OpenROAD tests); in CI the
`physical-design` job runs them. Deferred: standalone OpenSTA in CI, sky130,
a local OpenROAD, and CTS, power grid, and parasitic extraction as before.
