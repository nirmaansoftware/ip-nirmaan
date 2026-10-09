"""The tool catalog: capability-based permissions over honest implementations.

``AVAILABLE`` means a real binding exists in this repository and an
invocation executes. ``CONTRACT_ONLY`` means the organization plans around the
tool but nothing here can run it, and the broker refuses rather than pretends:
no agent can ever claim a CDC or equivalence run happened.

Lint, simulation, tests, synthesis, and formal are AVAILABLE through
open-source EDA (``nirmaan/integrations/eda.py``, M21); static timing and
place and route through OpenSTA and OpenROAD (``integrations/physical.py``,
M25). Their bindings still refuse, with a reason, on a machine whose PATH
lacks the executable or that has no PDK input for the run. Firmware build and
co-simulation are AVAILABLE the same way (``nirmaan/integrations/firmware.py``,
M25), and so are the RV32I cross build and the run on a RISC-V core
(``nirmaan/integrations/firmware_riscv.py``, M27).

Scan insertion, DFT rule checks, and scan chain simulation are AVAILABLE through
Yosys and Icarus (``nirmaan/integrations/dft.py``, M25); so are stuck-at ATPG,
graded by fault simulation, and March C- memory BIST (M27), and transition
ATPG (M29).

Every tool with a binding declares its parameters (M28): the broker refuses an
undeclared or ill-typed one before anything runs. The lists below are what the
bindings and backends actually read.
"""

from __future__ import annotations

from nirmaan.models import ParamKind, ParamSpec, ToolRisk, ToolSpec, ToolStatus

RD, WR, EXE, APP = ToolRisk.READ, ToolRisk.WRITE, ToolRisk.EXECUTE, ToolRisk.APPROVE
AV, CO = ToolStatus.AVAILABLE, ToolStatus.CONTRACT_ONLY
TEXT, PATH, PATHS, INT, NUM = ParamKind.TEXT, ParamKind.PATH, ParamKind.PATHS, ParamKind.INTEGER, ParamKind.NUMBER


def _p(name: str, kind: ParamKind = TEXT, description: str = "", required: bool = False,
       prefix: bool = False) -> ParamSpec:
    return ParamSpec(name=name, kind=kind, description=description, required=required, prefix=prefix)


def _tool(id: str, name: str, category: str, risk: ToolRisk, status: ToolStatus, description: str,
          params: tuple[ParamSpec, ...] | None = None) -> ToolSpec:
    return ToolSpec(id=id, name=name, category=category, risk=risk, status=status, description=description,
                    params=params)


SOURCES = _p("sources", PATHS, "HDL source files.", required=True)
TOP = _p("top", TEXT, "The top module.")
TOP_REQUIRED = _p("top", TEXT, "The top module.", required=True)
#: What the EDA runner itself reads, for every tool it runs (integrations/eda.py).
RUNNER = (
    _p("backend", TEXT, "Which backend to use, when the tool has several."),
    _p("workdir", PATH, "The run's working directory; a new temporary one by default."),
    _p("timeout", INT, "Seconds before the run is stopped (default 300)."),
    _p("max_", NUM, "Fail a passing run whose parsed metric of that name exceeds this, or was not reported.",
       prefix=True),
)
PDK = (
    _p("liberty", PATHS, "Liberty files, absolute or under pdk_root / NIRMAAN_PDK_ROOT (backend yosys-liberty)."),
    _p("pdk_root", PATH, "Where relative PDK paths resolve."),
)
#: For timing and place and route, where the library is not optional (their probes refuse without it).
PDK_REQUIRED = (_p("liberty", PATHS, "Liberty files, absolute or under pdk_root / NIRMAAN_PDK_ROOT.", required=True),
                _p("pdk_root", PATH, "Where relative PDK paths resolve."))
#: The RISC-V core a firmware image is built for and run on (M29; integrations/firmware_riscv.py CORES).
CORE = _p("core", TEXT, "The RISC-V core: picorv32 (default), serv, or another registered core.")
#: What a firmware run must show (M35; docs/FIRMWARE_IRQ_TRAPS.md, section 5).
REQUIRE = (_p("require_irq", TEXT, "auto, yes, or no (default): fail unless the design's interrupt was taken; "
                                   "auto asks it only of a design with an irq output."),
           _p("require_bus_error_trap", TEXT, "yes or no (default): fail unless a bus error was delivered as a "
                                              "precise trap."))
NETLIST = (_p("netlist", PATH, "The gate-level netlist.", required=True),
           _p("sdc", PATH, "Timing constraints.", required=True))


TOOLS: list[ToolSpec] = [
    # Platform operations, implemented by Nirmaan itself.
    _tool("project.read", "Read project", "platform", RD, AV, "Read project, task, and artifact state.",
          (_p("task", TEXT, "A task ID; the project itself when omitted."),)),
    _tool("status.read", "Read status", "platform", RD, AV, "Read status reports and blockers.", ()),
    _tool("artifact.read", "Read artifacts", "platform", RD, AV, "Read recorded artifacts and their provenance.",
          (_p("artifact", TEXT, "The artifact ID.", required=True),)),
    _tool("trace.read", "Read traceability", "platform", RD, AV, "Read the requirement-to-evidence trace graph.", ()),
    _tool("escalation.raise", "Raise escalation", "platform", WR, AV, "Raise a structured escalation."),
    _tool("task.create", "Create tasks", "platform", WR, AV, "Create tasks in a project."),
    _tool("task.assign", "Assign tasks", "platform", WR, AV, "Assign or reassign task owners and reviewers."),
    _tool("task.cancel", "Cancel tasks", "platform", WR, AV, "Cancel planned or branched-away work."),
    _tool("review.create", "Record reviews", "platform", WR, AV, "Record an independent review verdict."),
    _tool("approval.grant", "Grant approvals", "platform", APP, AV, "Approve work or a gate within authority."),
    # VeriTriage: the verification-intelligence subsystem, really executable.
    _tool("veritriage.investigate", "VeriTriage investigation", "verification-intelligence", EXE, AV,
          "Run the deterministic VeriTriage pipeline over verification artifacts.",
          (_p("paths", PATHS, "Logs and other verification artifacts.", required=True),
           _p("workspace", PATH, "Where the session is saved."))),
    _tool("veritriage.explain_log", "VeriTriage log explanation", "verification-intelligence", RD, AV,
          "Explain what a log is, which parser claims it, and what it contains.",
          (_p("path", PATH, "The log.", required=True),)),
    _tool("knowledge.search", "Knowledge search", "verification-intelligence", RD, AV,
          "Search the VeriTriage Knowledge Packs.",
          (_p("query", TEXT, "What to search for.", required=True),)),
    # Source control and specs (organization plans around these).
    _tool("spec.read", "Read specifications", "documents", RD, CO, "Read specifications and standards."),
    _tool("git.read", "Git read", "scm", RD, CO, "Read repositories."),
    _tool("git.write", "Git write", "scm", WR, CO, "Commit to working branches."),
    _tool("git.merge", "Git merge", "scm", WR, CO, "Merge to protected branches."),
    _tool("code.search", "Code search", "scm", RD, CO, "Search source code."),
    # RTL and verification EDA.
    _tool("lint.run", "Lint", "eda", EXE, AV, "RTL lint against coding standards.",
          (SOURCES, TOP, *RUNNER)),
    _tool("simulator.run", "Simulator", "eda", EXE, AV, "Compile and simulate RTL and testbenches.",
          (SOURCES, TOP_REQUIRED, *RUNNER)),
    _tool("test.run", "Run tests", "eda", EXE, AV, "Run individual tests.",
          (SOURCES, TOP_REQUIRED, *RUNNER)),
    _tool("regression.run", "Run regressions", "eda", EXE, CO, "Launch and monitor regressions."),
    _tool("waveform.inspect", "Waveform viewer", "eda", RD, CO, "Inspect waveforms."),
    _tool("coverage.read", "Coverage database", "eda", RD, CO, "Read and merge coverage."),
    _tool("formal.run", "Formal engine", "eda", EXE, AV, "Model checking and property proofs.",
          (_p("sby", PATH, "The SymbiYosys job file.", required=True),
           _p("sources", PATHS, "RTL the proof must read; the job file must list each one."), *RUNNER)),
    _tool("formal.cover", "Formal cover check", "eda", EXE, AV,
          "Non-vacuity: every cover in a proof setup (M27), and a cover derived for every assertion "
          "antecedent (M29), is reached under its assumptions.",
          (_p("sby", PATH, "The proof's SymbiYosys job file, run in cover mode.", required=True),
           _p("sources", PATHS, "RTL the setup reads."), *RUNNER)),
    _tool("regmap.check", "Register map check", "eda", RD, AV,
          "Validate a register map: alignment, overlaps, names, reset widths (M30).",
          (_p("map", PATH, "The register map (JSON).", required=True),)),
    _tool("regmap.verify", "Register map against RTL", "eda", EXE, AV,
          "Run a test generated from the register map on the RTL, over the AXI4-Lite co-simulation harness (M30).",
          (_p("map", PATH, "The register map (JSON).", required=True),
           _p("rtl", PATHS, "The RTL to check.", required=True), TOP, *RUNNER)),
    _tool("vplan.check", "Verification plan check", "verification", RD, AV,
          "A verification plan is valid and covers exactly the requirements its approved spec tags (M29).",
          (_p("plan", PATHS, "The verification plan file or files to check.", required=True),
           _p("spec", PATHS, "The approved spec file or files the plan must cover.", required=True))),
    _tool("equivalence.run", "Equivalence checker", "eda", EXE, CO, "Logic equivalence checking."),
    _tool("cdc.run", "CDC/RDC analyzer", "eda", EXE, CO, "Structural and functional crossing analysis."),
    # Implementation EDA.
    _tool("synth.run", "Synthesis", "eda", EXE, AV, "Logic synthesis.",
          (SOURCES, TOP_REQUIRED, *PDK,
           _p("tie_high", TEXT, "Tie-high cell as CELL/PORT (backend yosys-liberty)."),
           _p("tie_low", TEXT, "Tie-low cell as CELL/PORT (backend yosys-liberty)."),
           _p("buffer_cell", TEXT, "Buffer as CELL/IN/OUT, inserted where one port drives another "
                                   "(backend yosys-liberty)."), *RUNNER)),
    _tool("sta.run", "Static timing", "eda", EXE, AV, "Static timing of a netlist under an SDC (OpenSTA).",
          (*NETLIST, _p("spef", PATH, "Parasitics (SPEF), as pnr.run extracts them."), TOP_REQUIRED, *PDK_REQUIRED,
           _p("tech_lef", PATHS, "Technology LEF (backend openroad-sta)."),
           _p("lef", PATHS, "Cell LEF files (backend openroad-sta)."), *RUNNER)),
    _tool("pnr.run", "Place and route", "eda", EXE, AV,
          "Floorplan, power grid, placement, clock tree, routing, and extraction in one staged run, with timing "
          "(OpenROAD).",
          (*NETLIST, TOP_REQUIRED, *PDK_REQUIRED,
           _p("tech_lef", PATHS, "Technology LEF.", required=True),
           _p("lef", PATHS, "Cell LEF files.", required=True),
           _p("site", TEXT, "The placement site.", required=True),
           _p("hor_layers", TEXT, "Horizontal pin layers, comma separated.", required=True),
           _p("ver_layers", TEXT, "Vertical pin layers, comma separated.", required=True),
           _p("utilization", NUM, "Core utilization percent (default 40)."),
           _p("aspect_ratio", NUM, "Core aspect ratio (default 1)."),
           _p("core_space", NUM, "Core to die spacing (default 2)."),
           _p("stop_after", TEXT, "floorplan, place, cts, route, or extract (default: extract with rcx_rules, "
                                  "else route)."),
           # M29: the signoff steps, each enabled by the PDK input it needs (docs/PD_SIGNOFF.md).
           _p("rc_tcl", PATH, "The PDK's layer RC script (set_layer_rc, set_wire_rc); needed from cts on."),
           _p("tap_cell", TEXT, "Well-tap cell master."),
           _p("endcap_cell", TEXT, "Endcap cell master."),
           _p("tap_distance", NUM, "Microns between tap columns; needed with tap_cell."),
           _p("pdn_tcl", PATH, "The PDK's power-grid script, sourced before pdngen."),
           _p("place_density", NUM, "Global placement target density."),
           _p("dont_use", TEXT, "Cells (names or * patterns, comma separated) repair and CTS must not insert."),
           _p("cts_buffers", TEXT, "Clock buffer masters, comma separated (default: the tool picks)."),
           _p("routing_layers", TEXT, "Lowest and highest signal routing layers, as LOWEST,HIGHEST."),
           _p("filler_cells", TEXT, "Filler cell masters, comma separated."),
           _p("supply_voltage", NUM, "Volts on each power net, for IR-drop analysis."),
           _p("rcx_rules", PATH, "The PDK's OpenRCX rules; enables the extract stage."), *RUNNER)),
    _tool("power.run", "Power analysis", "eda", EXE, CO, "Power, IR-drop, and EM."),
    _tool("pv.run", "Physical verification", "eda", EXE, CO, "DRC, LVS, ERC, antenna, density."),
    _tool("dft.run", "DFT tools", "eda", EXE, CO, "ATPG, MBIST, and commercial scan flows."),
    _tool("dft.scan_insert", "Scan insertion", "eda", EXE, AV, "Mux-D scan flops stitched into one chain.",
          (SOURCES, TOP_REQUIRED, _p("chains", INT, "Number of scan chains (default 1)."),
           _p("max_chain_length", INT, "Longest chain allowed; 0 for no limit (default)."),
           _p("cross_domains", TEXT, "'lockup': chains may cross clock domains, with a lockup latch at each crossing "
              "(M29)."), *RUNNER)),
    _tool("dft.check", "DFT rule check", "eda", EXE, AV, "Testability rules over the synthesized netlist.",
          (SOURCES, TOP_REQUIRED, *RUNNER)),
    _tool("dft.scan_sim", "Scan chain simulation", "eda", EXE, AV, "Shift and capture through the chain in simulation.",
          (SOURCES, TOP_REQUIRED, *RUNNER)),
    _tool("dft.atpg", "ATPG", "eda", EXE, AV, "Stuck-at patterns, with coverage measured by fault simulation.",
          (SOURCES, TOP_REQUIRED, _p("patterns", PATH, "Patterns to grade instead of generating them."),
           _p("fault_sample", INT, "Grade a sample of this many faults; 0 for all (default)."),
           _p("seed", INT, "Random seed (default 1)."),
           _p("min_", NUM, "Fail unless the graded metric of that name reaches this, e.g. min_test_coverage.",
              prefix=True), *RUNNER)),
    _tool("dft.atpg_transition", "Transition ATPG", "eda", EXE, AV,
          "Slow-to-rise and slow-to-fall pattern pairs (launch on capture), with coverage measured by fault "
          "simulation.",
          (SOURCES, TOP_REQUIRED, _p("patterns", PATH, "Patterns to grade instead of generating them."),
           _p("fault_sample", INT, "Grade a sample of this many faults; 0 for all (default)."),
           _p("seed", INT, "Random seed (default 1)."),
           _p("min_", NUM, "Fail unless the graded metric of that name reaches this, e.g. min_test_coverage.",
              prefix=True), *RUNNER)),
    _tool("dft.mbist", "Memory BIST", "eda", EXE, AV, "A March C- controller run against the memory in simulation.",
          (SOURCES, TOP, *RUNNER)),
    # Software and infrastructure.
    _tool("compiler.run", "Compiler toolchain", "software", EXE, CO, "Build firmware and software."),
    _tool("fw.build", "Firmware build", "software", EXE, AV, "Compile C firmware under strict warning flags.",
          (_p("sources", PATHS, "C sources and headers.", required=True), *RUNNER)),
    _tool("fw.test", "Firmware co-simulation", "software", EXE, AV,
          "Run a driver's tests against a Verilator model of the RTL, over real bus transactions.",
          (_p("sources", PATHS, "The driver and its tests.", required=True),
           _p("rtl", PATHS, "The RTL to build the model from.", required=True), TOP, *REQUIRE, *RUNNER)),
    _tool("fw.cross_build", "Firmware cross build", "software", EXE, AV,
          "Cross-compile a driver and its tests for bare-metal RV32I into a linked ELF, with its code size.",
          (_p("sources", PATHS, "C sources and headers.", required=True), CORE, *RUNNER)),
    _tool("fw.soc_test", "Firmware on a RISC-V core", "software", EXE, AV,
          "Run a driver's tests on a RISC-V core (PicoRV32 or SERV) whose loads and stores reach the RTL over its bus.",
          (_p("sources", PATHS, "The driver and its tests.", required=True),
           _p("rtl", PATHS, "The RTL the core's bus reaches.", required=True), TOP, CORE, *REQUIRE, *RUNNER)),
    _tool("debugger.attach", "Debugger", "software", EXE, CO, "Attach to targets and models."),
    _tool("ci.configure", "CI configuration", "infrastructure", WR, CO, "Change CI pipelines."),
    _tool("farm.submit", "Compute farm", "infrastructure", EXE, CO, "Submit jobs to the compute farm."),
    _tool("doc.publish", "Publish documents", "documents", WR, CO, "Publish documents to the knowledge base."),
]
