# Physical-design signoff, the rest (Milestone 34)

M29 (`docs/PD_SIGNOFF.md`) took the AXI4-Lite block through a power grid,
clock-tree synthesis, routing, and OpenRCX extraction on Nangate45 and
sky130hd, and left four items open (its section 11): multi-corner timing,
physical verification with a signoff deck, metal fill, and a local OpenROAD on
the Mac. This milestone closes them, on sky130hd, in the same `physical-design`
CI job.

Read `docs/PHYSICAL_DESIGN.md` (M25, M27) and `docs/PD_SIGNOFF.md` (M29)
first. Everything there still holds unless this document says otherwise.

Status: design. Numbers are filled in from the CI run that proves them.

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
