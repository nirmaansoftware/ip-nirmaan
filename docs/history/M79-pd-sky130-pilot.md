# Milestone 79 - The SKY130 physical design pilot in CI: Magic DRC and Netgen LVS

Resources item R3 of the capability build-out, under the founder's approval
in session, 2026-11-14, of OpenROAD-flow-scripts, KLayout, Magic, Netgen and
the open PDKs SKY130, GF180MCU and IHP SG13G2, on CI runners only. Design:
`docs/PD_SKY130_PILOT.md`. Tests: `tests/test_pv_magic.py`,
`tests/test_pd_sky130_pilot.py`.

**The gap.** `pv.run` judged a layout only with the sky130hd platform's
KLayout decks (M34), and no block of the product's own went from RTL to DRC
and LVS in a job of its own.

**Backend.** `pv.run` gains `magic-netgen` (`integrations/pv_magic.py`, one
`register_backend` call, no EDA core change), by name only: the M34 stream to
GDS, Magic DRC with the PDK's `.tech`, Magic extraction, Netgen LVS against
the routed netlist with supply pins over the cells' SPICE, and Nirmaan's own
count of Netgen's JSON. Its lines are the KLayout scripts' lines, so
`parse_klayout` judges it and the physical-verification bounds read it.
New PDK parameters: `magic_tech`, `netgen_setup`, `spice`.

**Pilot.** The M26 synchronous FIFO at 100 MHz on sky130hd: synthesis, place
and route, then DRC and LVS with KLayout and with Magic and Netgen; a cell
moved off grid and a rewired flip-flop input must fail. Workflow
`pd-sky130.yml`: the ci.yml ORFS image by digest, Magic and Netgen built from
tags checked against their commits, the SKY130A files from the pinned ciel
release by sha256; `workflow_dispatch` plus a paths filter; not required.
The pilot test is collected only under `NIRMAAN_PD_PILOT`.

**Counts.** None change: `pv.run` was already `AVAILABLE`.
