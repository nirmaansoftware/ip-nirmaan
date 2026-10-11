# Milestone 44 - One end-to-end factory project

The principal-engineer review found that the factory was two factories:
`block-design` stopped at firmware, and `physical-implementation` ran in CI
on the fixture RTL with typed design paths, so no project carried one IP's
approved RTL into layout (sections 1 and 5.1 item 7, risk 3, recommendation
2). Design: `docs/FACTORY_E2E.md`.

**The connection is data.** A new `layout` feature ("layout", "GDS") plans
six stages in `block-design` after the RTL: `timing-constraints`,
`synthesis` (Liberty-mapped), `floorplan`, `place-route` (power grid,
placement, CTS, routing, fill, extraction), `physical-verification` (KLayout
DRC and LVS), and `sta-signoff` (three corners, closes `gate.implementation`).
Every design input is bound to an approved upstream artifact and checked
before review; the PDK and the top module are task inputs. A project-level
hand-off was rejected: P8, P9, the audit chain, and the export are per
project. `physical-implementation` is unchanged for outside netlists and
shares its limits with the layout stages through one constant per set.

**Tool outputs as artifacts.** `ToolOutcome.outputs` and `ToolRun.outputs`
record the files a run wrote (every EDA run its `log`; synthesis its netlist,
OpenROAD its DEF, netlists, and SPEF, KLayout its GDS, scan insertion its
scan netlist). `EvidenceRequirement.yields` makes such a file the task's
artifact: the model runtime records it (digest, `derived_from`, a summary
naming the run), feeds it to the stage's later checks, and the engine refuses
an artifact of a yielded kind that is not the very file a passing run over the
approved inputs wrote. The DFT stage now inserts scan into the approved RTL
this way before its checks.

**Folders of tool runs.** `DeliverableFolder.tool_runs` lists a tool's
recorded runs in a folder: `06_formal` (`formal.run`, `formal.cover`) and
`07_lint` (`lint.run`) were empty for every project before.

**The project.** "Create an AXI4-Lite register block with a register map, a
driver, scan chains, and a layout on sky130hd." MockLLM seats answer with the
AXI4-Lite fixtures; people approve each stage and the gate; `nirmaan export`
fills all ten folders. First green run in CI's `physical-design` job (run
38110473925): 19 recorded tool runs, all passing, 23 artifacts all APPROVED,
371 audit entries; 1185 sky130hd cells (11,669 um2); 34% utilization,
30,550 um of wire, 17 clock buffers, 12,947 fill shapes, 0 DRC violations, 0
unconnected supply pins; KLayout 0 DRC, 0 LVS mismatches; signoff on the SPEF
at three corners, worst setup slack 1.276 ns (ss), worst hold 0.399 ns (ff),
TNS 0, every net annotated. Front end locally: 13 runs in about 130 s,
including ATPG at 100% stuck-at coverage over 8 chains.

**Integration bugs found:** no way to pass a tool's output to the next stage;
the scan netlist not tied to the approved RTL; the formal and lint folders
always empty; the AXI4-Lite driver's map header never checked against its
register map; ATPG on one long chain past the default timeout; an `outputs`
field that would have changed old saved projects; a `flip_flops` metric of 0
on mapped netlists (reported only). Details in `docs/FACTORY_E2E.md` section 6.

**Deferred:** laying out the scan netlist, PDK profiles as project data, the
line run unattended on live models, and a separate power-grid stage.

Tests: `tests/test_nirmaan_factory_e2e.py` (the connection as data, shared
limits, yields in the policy and the runtime, the local blocked path, the end
to end project required in `physical-design`, a crown jewel for a new yielded
output and a folder of its runs, import laws); the DFT stage tests now name
scan insertion.
