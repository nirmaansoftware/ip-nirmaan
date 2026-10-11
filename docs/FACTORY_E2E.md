# One end-to-end factory project (Milestone 44)

Until M44 the factory was two factories. `block-design` took a request through
specification, register map, microarchitecture, RTL, scan, and firmware, and
stopped. `physical-implementation` took a netlist to a signed-off layout, but
CI ran it on the fixture RTL, with every design input a path someone typed. No
project carried one IP's approved RTL into layout, and nothing tested the
hand-off between the two (the principal-engineer review, sections 1 and 5.1
item 7, risk 3, recommendation 2).

M44 makes it one line. One request:

```
Create an AXI4-Lite register block with a register map, a driver, scan chains,
and a layout on sky130hd.
```

plans one `block-design` project whose stages run from the requirements
specification to signoff timing on the routed, extracted layout, and whose
export fills all ten numbered folders from that project's own records. The
project runs for real in CI's `physical-design` job.

---

## 1. Decision: a `layout` variant of `block-design`, not a project hand-off

Two ways to connect the workflows were on the table.

**A project-level hand-off.** A finished `block-design` project's approved RTL
becomes the input of a second, `physical-implementation` project. Rejected:

* The engine's guarantees are per project. P8 (work starts only from approved
  inputs), P9 (checks before review over the very files submitted), the
  hash-chained audit trail, and the export all read one `ProjectState`. A
  hand-off needs an artifact in one project to stand for an approved artifact
  in another: a cross-project reference, a way to verify the other project's
  chain, and an export that spans two trees. That is new trust machinery, and
  the integration it would test is mostly itself.
* Two projects give two exports, so "all ten folders filled from one project"
  would not be true of either.

**A `layout` variant of `block-design` (chosen).** When the request asks for a
layout, `block-design` plans six more stages after the RTL, as data in
`company/workflows.py`, conditioned on a new `layout` feature
(`company/vocabulary.py`: "layout", "GDS"). They reuse everything the engine
already enforces: the stages build only on approved upstream artifacts (the
dependency edges are the hand-off), each stage's checks run over those
artifacts before review, and the export, trace, and audit trail stay one.
No engine, policy check, or orchestrator code names a stage, a kind, or a tool.

`physical-implementation` stays as it was, for a netlist that comes from
outside (a customer's RTL): its design inputs are task inputs. The six layout
stages share its limits (one constant per limit set, so the two can never
drift) but bind their design inputs to approved artifacts instead.

## 2. The stages

All six are planned only when the request has the `layout` feature, and each
check is `before_review`: it must pass, over approved inputs, before the work
reaches a reviewer.

| Stage | Depends on | Check (tool, over which approved inputs) | Fixed parameters | Artifacts it yields |
|---|---|---|---|---|
| `timing-constraints` | `rtl-implementation` | `sta.run`: the seat's SDC, with the approved RTL synthesized to the PDK's Liberty | | `constraints` (written by the seat) |
| `synthesis` | `rtl-implementation` | `synth.run` over the approved RTL | `backend=yosys-liberty` | `netlist`, `synthesis_report` |
| `floorplan` | `synthesis`, `timing-constraints` | `pnr.run` over the approved netlist and SDC | `stop_after=floorplan` | `floorplan` |
| `place-route` | `synthesis`, `timing-constraints`, `floorplan` | `pnr.run` over the approved netlist and SDC: power grid, placement, CTS, routing, fill, extraction | `stop_after=extract`, no DRC violations, every supply pin connected | `layout`, `routed_netlist`, `power_netlist`, `parasitics` |
| `physical-verification` | `place-route` | `pv.run`: KLayout DRC and LVS of the approved layout against the approved power netlist | no DRC violations, no LVS mismatches, at least one fill shape | `gds`, `physical_verification_report` |
| `sta-signoff` | `place-route`, `physical-verification`, `timing-constraints` | `sta.run` on the approved routed netlist, its parasitics, and the approved SDC | every net annotated, at least three corners | `timing_report`; closes `gate.implementation` |

A separate `power-grid` stage, as `physical-implementation` has, would repeat
the whole flow: the supply-pin count is only measured after routing, so a
power-grid run with that limit is a routed run. In the layout variant the grid
is built and checked inside `place-route`, whose limits include it.

The layout is of the functional RTL, not the scan-inserted netlist; laying out
the scan netlist is deferred (section 7).

**The PDK is a task input** (`docs/PHYSICAL_DESIGN.md` section 3): the Liberty
files, LEFs, site, layers, tie and buffer cells, and decks are set on each
layout task by the person who runs the line (`nirmaan run --input`, or
`engine.remember` in a test), and each tool is handed only the inputs its
contract declares (M28). The top module is a task input too. The **design**
inputs never are: they come from approved artifacts only, and a run that used
any other file does not open review.

## 3. Tool outputs as artifacts (`yields`)

The layout stages need something the platform did not have: a file a tool
wrote becoming the stage's artifact. A seat writes RTL; nobody writes a
netlist or a DEF by hand. Before M44 the DFT stage's scan netlist was handed in
by its owner as a path, and nothing tied it to the run that wrote it, or that
run to the approved RTL.

Three generic pieces close this:

1. **A run records what it wrote.** `ToolOutcome.outputs` and
   `ToolRun.outputs` (name to path). Every EDA run records its `log`; a
   backend adds the files it reports under `outputs` in its metrics:
   `synth.run` (`yosys-liberty`) its `netlist`, `pnr.run` its `def`,
   `netlist`, `pg_netlist`, and `spef`, `pv.run` its `gds`, `drc_report`, and
   `lvs_report`, and `dft.scan_insert` its `scan_netlist` and `chain_report`.
2. **A requirement names what it yields.** `EvidenceRequirement.yields` pairs
   an artifact kind with an output name, for example
   `(("netlist", "netlist"), ("synthesis_report", "log"))`.
3. **The engine holds the claim to the run** (policy check
   `evidence-before-review`). A submitted artifact of a yielded kind must be
   at the very path a passing run of that requirement wrote under that name,
   and that same run must have used the approved upstream files the
   requirement binds. Anything else does not open review.

The model runtime produces them: after the answer, it runs each requirement in
order, and a passing run's yielded files become drafts of the task, written by
the run (with a digest, a summary naming the run, and the approved upstream
artifacts it used as `derived_from`). They join the task's produced files, so
a later requirement on the same stage checks them: the DFT stage now first
inserts scan into the approved RTL (`dft.scan_insert`, yielding the
`dft_netlist`), then runs its rule check, chain simulation, and ATPG over that
netlist. A yielded file's entry (for a `top` binding) is the entry the run that
wrote it was given. A seat on such a stage writes nothing; its answer only
declares its uncertainty.

## 4. Lint and formal in the export

`06_formal` and `07_lint` collected only `formal_report` and `lint_report`
artifacts, and no workflow that writes RTL produces those: the reports are the
logs of the runs that gate the RTL. So these two folders were empty for every
project. A folder can now name tools (`DeliverableFolder.tool_runs`): the
export lists each recorded run of them in that folder, pass or fail, with its
log and result copied, exactly as `09_evidence/tool_runs/` copies every run.
`06_formal` lists `formal.run` and `formal.cover`, `07_lint` lists `lint.run`.
This is a table edit; `export.py` names no folder and no tool.

## 5. The project, end to end

`tests/test_nirmaan_factory_e2e.py::test_one_request_runs_from_requirements_to_a_signed_off_layout`
plans the request above and drives every stage the way people and seats
would:

* the requirements specification is submitted by its owner (a person: there
  is nothing upstream for a seat to cite), reviewed, and approved;
* the interface spec, register map, microarchitecture, RTL (with testbench and
  proof setup), driver, and SDC are written by MockLLM seats whose scripted
  answers are the AXI4-Lite fixtures, and the scan, synthesis, floorplan,
  place-and-route, verification, and signoff seats write nothing: the platform
  runs their checks over the approved artifacts;
* every check is real: lint, simulation, synthesis, formal and its cover run,
  the register map's co-simulation, scan insertion, rules, chain simulation,
  ATPG, the strict driver build and its co-simulation against the approved
  RTL, Liberty-mapped synthesis, the timer, OpenROAD, and KLayout;
* each stage is reviewed by an independent MockLLM reviewer and approved by a
  person; the implementation gate is approved by a person;
* `nirmaan export` writes the tree.

It asserts that every folder from `01_requirement` to `10_signoff` holds this
project's own records (the AXI4-Lite files, the netlist, the routed layout, the
GDS, the lint and formal runs, the trace, the signoff), that each layout stage
ran on the artifact the stage before it approved, never on a fixture path, and
that every run the export lists is recorded in the project's state and passed.

Locally the project runs to the RTL, scan, and driver and then stops: the
layout stages need OpenROAD and KLayout, which run only in CI. The test skips
without them; CI's `physical-design` job requires them (`NIRMAAN_REQUIRE_EDA`),
so there it fails instead. `test_without_the_pd_tools_the_layout_stages_block`
checks the local side: the timer is refused, the stage is BLOCKED, and no run
is recorded.

## 6. Integration bugs found

The line surfaced these; each fix is generic (section 3 and 4):

1. **A tool's output could not become an artifact.** The physical stages had
   no way to pass a netlist, DEF, or SPEF to the next stage except as a typed
   path. Fixed by `yields`.
2. **The scan netlist was not tied to the approved RTL.** Any file could be
   submitted as the `dft_netlist`. The DFT stage now yields it from a scan
   insertion over the approved RTL.
3. **`06_formal` and `07_lint` were always empty**, because no RTL workflow
   produces a report artifact for them. Fixed by folder `tool_runs`.
4. **Upstream artifacts are only a stage's direct dependencies'**
   (`upstream_artifacts`), so a stage that needs the SDC and the routed netlist
   must depend on both stages. The layout stages declare every stage whose
   artifacts they bind; the rule stands and is documented here.
5. **The AXI4-Lite reference driver had never met its register map.** M41
   adopted register maps on APB only; the AXI driver's map header named its
   offsets `AXIL_REGS_*`, so with the approved map the strict build failed
   ("does not define AXI4_LITE_REGS_REG0_OFFSET"). The fixture header now also
   defines the offsets under the names the map generates.
6. **ATPG on one 206-flop chain takes over ten minutes** in fault simulation
   (800 s measured locally), past the runner's 300 s default. The line asks for
   eight chains as a DFT task input (127 s, 100% stuck-at coverage, 2476 of
   2476 faults); that is a design choice of the person running the line, not a
   change to the stage's data.
7. **A run that wrote nothing would have changed every saved project**: a new
   `outputs` field serialized as `{}` broke the byte-for-byte round trip of a
   project saved before it (M39's test). An empty `outputs` is now left out
   when saving.
8. **`synth.run`'s `flip_flops` metric reads 0 on a Liberty-mapped netlist**
   (it counts Yosys's generic flop cells, and the mapped netlist has library
   flops). Reported here, not changed: nothing gates on it.

## 7. Deferred

* Laying out the scan-inserted netlist (the scan netlist is Yosys gate cells,
  not Liberty-mapped; mapping it is a synthesis step of its own).
* PDK profiles as data, so a request that names a PDK sets its inputs once per
  project rather than once per task.
* Running the line unattended with `nirmaan drive` on live models: the test
  drives each stage, as the seat tests do.
* A separate `power-grid` stage with a metric measured before routing.
