# Physical-design signoff, the rest (Milestone 34)

M29 (`docs/PD_SIGNOFF.md`) took the AXI4-Lite block through a power grid,
clock-tree synthesis, routing, and OpenRCX extraction on Nangate45 and
sky130hd, and left four items open (its section 11): multi-corner timing,
physical verification with a signoff deck, metal fill, and a local OpenROAD on
the Mac. This milestone closes them, on sky130hd, in the same `physical-design`
CI job.

Read `docs/PHYSICAL_DESIGN.md` (M25, M27) and `docs/PD_SIGNOFF.md` (M29)
first. Everything there still holds unless this document says otherwise.

Status: done. The numbers are from CI run 37913292574 (head `8e91b21`), whose four jobs passed.

---

## 1. What the image has (probed in CI)

The `openroad/orfs:26Q3-687-gc63a606f9` image was probed before any code was
written:

| Item | In the image |
|---|---|
| KLayout | `/usr/bin/klayout`, 0.30.12 |
| Magic, Netgen | not installed |
| sky130hd DRC deck | `flow/platforms/sky130hd/drc/sky130hd.lydrc` (KLayout) |
| sky130hd LVS deck | `flow/platforms/sky130hd/lvs/sky130hd.lylvs` (KLayout) |
| Cell GDS, cell CDL | `gds/sky130_fd_sc_hd.gds`, `cdl/sky130hd.cdl` |
| KLayout technology | `sky130hd.lyt` (a template: the LEF list is filled in per run) |
| Fill rules | `fill.json` (met1 to met5) |
| Liberty corners | `tt_025C_1v80` only |
| OpenRCX rules | one model (`DensityModel 0`): one RC corner |

So DRC and LVS run on KLayout with the decks ORFS ships, and nothing is
skipped for lack of a deck. Magic and Netgen are not needed.

---

## 2. Decisions

1. **Corners are an `sta.run` input, not a new tool.** Each `liberty_<name>`
   parameter defines a timing corner `<name>` read from that Liberty; the base
   `liberty` is the corner named by `corner` (default `typical`). The script
   defines the corners, reads each Liberty into its corner, reads the SPEF
   into every corner, and reports setup and hold per corner, then the worst
   over all of them. Without `liberty_<name>` the run is single-corner, as
   before.
2. **The slow and fast libraries are fetched, pinned, and cached, never
   bundled.** They come from the open SkyWater sources as the open_pdks build
   publishes them (section 3).
3. **`pv.run` becomes AVAILABLE**, backed by KLayout (`klayout` backend): the
   routed DEF streamed to GDS with the cell GDS merged, the PDK's DRC deck, and
   the PDK's LVS deck against a CDL written from the routed Verilog netlist.
   Nirmaan counts the results itself (section 5).
4. **Metal fill is a `pnr.run` step** (`fill_rules`), at the end of `route`,
   so the DEF that `pv.run` streams and checks is the filled one.
5. **Limits are data.** `max_` limits already fail a run (M21); this milestone
   adds `min_` the same way, so the workflow can say "at least three timing
   corners".

---

## 3. Corner libraries

Pinned in `.github/workflows/ci.yml`:

* Source: `fossi-foundation/ciel-releases`, release
  `sky130-ff08c23db8359afce3f134c454e7930586d0641c` (the open_pdks commit),
  asset `sky130_fd_sc_hd.tar.zst`, sha256
  `69500f75f639989fb2c01b5fa7347aa5972e80238abb4460a7304fa8de405977`.
  The Liberty files are generated from `google/skywater-pdk-libs-sky130_fd_sc_hd`
  (Apache-2.0); that repository holds per-cell JSON, not assembled `.lib`
  files, so the open_pdks build is the assembled form.
* `sky130_fd_sc_hd__ss_100C_1v60.lib`, sha256
  `9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361`
* `sky130_fd_sc_hd__ff_n40C_1v95.lib`, sha256
  `fb61d91c55a7f85b1989e8149d040b13ba5e7f5478f5bf0c3c16c5da30720139`

The job checks both hashes after extraction and caches the two files by hash.
The typical corner stays the image's `tt_025C_1v80`, the one the flow used.

**RC corners: one.** The platform's OpenRCX rules have one model, so there is
one SPEF, and every corner times on it. The corners vary cell delay (process,
voltage, temperature), not wire RC. A real signoff would add Cmax and Cmin
extraction; no rules for them ship here, and inventing a scale factor would
report a corner that does not exist.

---

## 4. Timing corners (`sta.run`)

| Parameter | Kind | Meaning |
|---|---|---|
| `liberty_<corner>` | PDK files (prefix) | One corner's Liberty files; any one of them makes the run multi-corner |
| `corner` | text | The name of the corner the base `liberty` files time (default `typical`) |
| `min_<metric>` | number (prefix) | A limit from below, e.g. `min_timing_corners=3` (section 7) |

The script (both backends, `opensta` and `openroad-sta`):

```
define_corners tt ss ff
read_liberty -corner tt <tt.lib>     ... one line per corner and file
read_verilog, link_design, read_sdc
read_spef -corner tt route.spef      ... the one SPEF, into every corner
set_propagated_clock [all_clocks]
puts "nirmaan-corner: ss"
report_checks -path_delay max -scenes ss -format end -digits 3
report_checks -path_delay min -scenes ss -format end -digits 3
puts "nirmaan-corner-done: ss"       ... per corner
report_worst_slack -max / -min, report_tns ...   the worst over every corner
```

The image's OpenSTA (`e983e15b`) has the newer scene API (`define_scene`,
`-scenes`). Both forms were tried in the probe run: `define_corners` with
`read_liberty -corner` gave the typical corner exactly the single-corner
figures (4.419 / 0.629 ns on the M29 layout), while the `define_scene` form
gave 4.413 / 0.628. The older form is documented as supported for scripts that
define corners before reading Liberty, so it is the one used; moving to scenes
is a one-function change in `_sta_script` once the two agree. `report_tns` and
`report_worst_slack` take no `-scenes`, so per-corner figures come from the
`report_checks -format end` tables.

Parsed: `slack_by_corner` (worst setup and hold per corner) and
`timing_corners`, the number of corners that reported both; a single-corner
run reports 1. A corner that reports no path fails the run, by name. The
overall `worst_slack` and `worst_hold_slack` are over every corner, so pass
still means "met everywhere".

---

## 5. Physical verification (`pv.run`, backend `klayout`)

`pv.run` was `CONTRACT_ONLY`. It is now AVAILABLE, with these inputs (all
declared in `company/tools.py`):

| Parameter | Meaning |
|---|---|
| `def` | The routed, filled DEF (`pnr.run`'s `def` output) |
| `netlist` | The routed netlist with supply pins (`pnr.run`'s new `pg_netlist` output, `final_pg.v`) |
| `top`, `tech_lef`, `lef` | As for `pnr.run` |
| `gds` | The cells' GDS |
| `klayout_tech` | The PDK's KLayout technology; Nirmaan fills in this run's LEF files, as ORFS does |
| `drc_deck` | The PDK's KLayout DRC deck; enables DRC |
| `lvs_deck`, `cdl` | The PDK's KLayout LVS deck and the cells' CDL; together they enable LVS |

At least one check must be possible, or the probe refuses the run with the
reason. The steps:

1. `openroad`: read the LEFs and the netlist, `write_cdl -masters <cell CDL>`;
   a `reference.cdl` includes the cells' CDL, then this one.
2. `klayout -zz -r stream.py`: Nirmaan's own stream script, the same method as
   ORFS's `def2stream.py` (read the DEF with the technology's LEF/DEF options,
   empty every non-top cell except DEF vias and fill, read the cell GDS over
   them, copy the top tree). It prints how many cells stayed empty (no GDS) and
   how many fill shapes the DEF holds.
3. `klayout -zz -r <drc_deck>`, then `klayout -r drc_count.py`: the report
   database's item count, in total and per rule.
4. `klayout -b -r <lvs_deck>`, then `klayout -r lvs_count.py`: the LVS
   database's cross-reference, counting circuit, net, device, pin, and
   subcircuit pairs that do not match.

Nirmaan counts both results itself from the databases, so a different deck
(whatever it prints) is read the same way, and the deck's own "ERROR : Netlists
don't match" text is not mistaken for a tool error. Metrics: `gds_empty_cells`,
`fill_shapes`, `drc_violations`, `drc_by_rule`, `lvs_mismatches` (the sum),
`lvs_mismatched` (per kind), `lvs_unmatched_circuits`. Pass: exit 0, no error,
no empty cell, and every check run clean; a check that ran and printed no
count fails.

**LVS needs supply connections in the netlist.** The first LVS against
`final.v` did not match: OpenROAD's `write_verilog` leaves supply pins out, so
the CDL from it had every tap and cell supply pin on `_unconnected_` nets.
`pnr.run` now also writes `final_pg.v` with `write_verilog -include_pwr_gnd`
(output `pg_netlist`), and LVS against it matches. A CDL written from the DEF
matched too, but that would compare the layout with its own database rather
than with the netlist.

**What the deck checks.** The sky130hd deck in ORFS runs the back-end-of-line
rules (li1, met1 to met5, vias) and the manufacturing grid and angle checks;
its front-end-of-line group is off (`FEOL = false`). That is the deck as
shipped and is not changed here; the front-end rules come from the cell
library's own signoff, since the block adds no devices of its own.

---

## 6. Metal fill (`pnr.run` `fill_rules`)

With `fill_rules` (the PDK's `fill.json`), the `route` stage runs
`density_fill -rules <file>` after the fillers and before the checks, and
prints `nirmaan-fill-shapes` from the block's fill count. The DEF written is
the filled one, so `pv.run` checks the layout with its fill, and extraction
runs after fill, as in ORFS. On the AXI4-Lite block: 12947 fill shapes on met2
to met5 (met1 has no room), and DRC is clean with and without them.

---

## 7. The workflow, and `min_` limits

`physical-implementation` gains a stage and a limit, all in
`company/workflows.py`:

```
place-route
  -> physical-verification (pd.signoff_checks)  evidence: a pv.run with max_drc_violations=0,
                                                max_lvs_mismatches=0, min_fill_shapes=1, reviewed
  -> sta-signoff (sta.analyze)                  evidence: an sta.run with max_unannotated_nets=0
                                                and min_timing_corners=3, reviewed; gate.implementation
                                                (now after physical-verification too)
```

`min_<metric>` is new in the runner (`eda._within_limits`), the mirror of M21's
`max_<metric>`: a run below the bound, or one that never reported the metric,
fails. `dft.atpg` already checked its own `min_` limits; the runner's check
agrees with it and runs only on a passing result, so nothing there changes.
`physical_verification_report` joins the `04_rtl` deliverable folder.

---

## 8. Real numbers (CI, AXI4-Lite block on sky130hd, 100 MHz)

Signoff STA on the extracted SPEF, through standalone OpenSTA and OpenROAD's
OpenSTA (the same figures from both):

| Corner | Liberty | Setup slack (ns) | Hold slack (ns) |
|---|---|---|---|
| ss | `ss_100C_1v60` | 1.276 | 1.283 |
| tt | `tt_025C_1v80` (the platform's) | 4.428 | 0.629 |
| ff | `ff_n40C_1v95` | 5.606 | 0.399 |

Setup is worst on ss and hold on ff, as expected; the typical corner equals
the flow's own extracted timing (4.428 / 0.629). The run reports 0 unannotated
nets on every corner.

Physical verification on the filled layout:

| Run | Result |
|---|---|
| Clean | DRC 0 (BEOL and grid rules), LVS match (0 mismatched circuits, nets, devices, pins, subcircuits), 0 cells without GDS, 12947 fill shapes |
| One `dfxtp` moved 1 nm (off the 5 nm grid) | 782 DRC violations: `licon_OFFGRID` 200, `li_OFFGRID` 172, `poly_OFFGRID` 138, `ct_OFFGRID` 88, `ct.1` 64, and more; a recorded failed run |
| One flip-flop's `D` rewired in the netlist | LVS: the top circuit unmatched, 2 nets and 1 subcircuit mismatched; DRC still 0; a recorded failed run |

**Routing on met1 to met3.** With signals allowed up to met4 (M29's
setting), the KLayout deck found 3 `m3.6` violations (met3 area under
0.24 um^2) that the detailed router's own count (0) missed: each a met3 island
where a via2 and a via3 meet, about 0.19 um^2. With signals on met1 to met3 the
deck finds none, timing is the same (4.428 against M29's 4.419 ns extracted
setup slack), and the wire is 30550 um. The sky130hd test now routes on met1 to
met3; the router's miss is recorded here rather than worked around in the
deck.

---

## 9. OpenROAD on the development Mac: not supported

Time-boxed and closed. The development machine is macOS 27 on arm64
(Apple silicon). What was checked:

* **Packages.** No Homebrew formula or tap for OpenROAD. The litex-hub conda
  channel builds `linux-64` and `osx-64` only, and its last `osx-64` build is
  from 2023-11 (OpenROAD 2.0-10927), which predates the OpenSTA scene API the
  image's OpenROAD has and the commands this flow uses as they are now.
* **Rosetta.** Not installed (`Bad CPU type in executable` for an x86_64
  binary), so an `osx-64` build cannot run without a system-level install.
* **Source build.** Feasible in principle, but it needs eight more Homebrew
  formulae (or-tools, swig, spdlog, cmake, bison 3, yaml-cpp, googletest, and
  LEMON graph, which Homebrew's `lemon` is not) plus CUDD built from source,
  a long compile, and several GB of a disk with 18 GB free. It would change the
  shared Homebrew prefix other work uses, and the result would still be a
  different build from the one CI pins.

So the real OpenROAD, OpenSTA, and KLayout tests run in the `physical-design`
CI job only, and skip locally with the reason (they fail instead of skipping
wherever `NIRMAAN_REQUIRE_EDA` names the tools). The way to run them on a Mac
is the CI image under Docker or another Linux VM, which needs no change here.
KLayout alone is available for macOS, but `pv.run` also needs OpenROAD (for
the CDL), so it refuses on this machine too.

---

## 10. CI

| | M29 | M34 |
|---|---|---|
| `physical-design` job | 3 min 34 s (OpenSTA cached) | 6 min 21 s (OpenSTA cached; the corner libraries fetched, 4 s) |
| of which the tests | 3 min 26 s | 5 min 1 s |

The extra time is three `pv.run`s (about 30 s each: DRC about 26 s, LVS about
3 s), two three-corner STA runs, and the parser and stand-in tests. The job
still runs in parallel with the main test jobs and finishes before them (7 to
18 minutes in this run), so CI's wall time does not grow.

`NIRMAAN_REQUIRE_EDA` in the job is now `yosys openroad sta klayout`.

Warnings left in the logs, recorded and not failing: `ORD-2011` in `pv.run`'s
CDL step (it reads no Liberty, and needs none to write a CDL), `FIN-0010`
(fill skips the layers `fill.json` does not name), and the M29 warnings.

---

## 11. Fixtures

Captured from the run in section 10, each with a `# CAPTURED:` line and the log
unedited below it: `opensta_corners.log` (standalone OpenSTA, three corners),
`openroad_sky130_fill.log` (the sky130hd flow with fill), and
`klayout_pv.log`, `klayout_pv_drc.log`, `klayout_pv_lvs.log` (the clean, broken
layout, and broken netlist `pv.run`s).

---

## 12. Not in this milestone

* RC corners (Cmax, Cmin): the platform ships one OpenRCX model (section 3).
* Front-end DRC rules (off in the shipped deck), ERC, and antenna checks in
  KLayout (OpenROAD's `check_antennas` still runs in `pnr.run`).
* Multi-corner timing inside `pnr.run` (repair and CTS still see one corner);
  signoff timing is where the corners are checked.
* An IR-drop limit as workflow data (still reported, not limited).
