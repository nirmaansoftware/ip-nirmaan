# Milestone 82 - The IHP SG13G2 physical design pilot in CI

The M79 pilot on a third open PDK, in CI only. Design: `docs/PD_IHP_PILOT.md`.
Tests: `tests/test_pd_ihp_pilot.py` (in `pd-ihp` only), and the `test_ihp_*`
tests in `tests/test_pv_magic.py`, which read the committed records in the
required jobs. No code change under `src/`, no version bump, no count changes.

**Pilot.** The M26 synchronous FIFO at 100 MHz on the ORFS `ihp-sg13g2`
platform (typical corner, 1.2 V): synthesis, place and route with power grid,
CTS, metal fill and extraction, then Magic DRC and Netgen LVS over the IHP Open
PDK's own Magic technology, Netgen setup and cell SPICE (ciel release
`ihp-sg13g2-5e6d592e`, by sha256). Must fail: a flip-flop half a site over
another (DRC) and a rewired D input (LVS). Workflow `pd-ihp.yml`, a sibling of
`pd-sky130.yml` and `pd-gf180.yml`; not required. Once its records are
committed, the pilot test requires every run to reproduce their result lines.

**Result** (run 43639949127, head 1465f3e; the records in `tests/fixtures/pd/ihp/`):
0 router DRC, 3616 fill shapes, setup slack 6.052 ns, hold 0.431 ns; Magic DRC
0 with every fill shape on a mapped fill layer, Netgen unique match; the
overlapping cell fails with 1524 DRC violations, the rewired input with 1
mismatched net.

**Fill.** The first pilot to fill: the platform's layer map file sends fill to
datatype 22, the M80 guard's targets with `layer_map`, and Magic reads those
layers, so the guard did not trip and no mapping fix was needed.

**Gaps, stated.** The platform's KLayout DRC and LVS decks, metal density and
IR drop were not run.
