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
graded by fault simulation, and March C- memory BIST (M27).
"""

from __future__ import annotations

from nirmaan.models import ToolRisk, ToolSpec, ToolStatus

RD, WR, EXE, APP = ToolRisk.READ, ToolRisk.WRITE, ToolRisk.EXECUTE, ToolRisk.APPROVE
AV, CO = ToolStatus.AVAILABLE, ToolStatus.CONTRACT_ONLY


def _tool(id: str, name: str, category: str, risk: ToolRisk, status: ToolStatus, description: str) -> ToolSpec:
    return ToolSpec(id=id, name=name, category=category, risk=risk, status=status, description=description)


TOOLS: list[ToolSpec] = [
    # Platform operations, implemented by Nirmaan itself.
    _tool("project.read", "Read project", "platform", RD, AV, "Read project, task, and artifact state."),
    _tool("status.read", "Read status", "platform", RD, AV, "Read status reports and blockers."),
    _tool("artifact.read", "Read artifacts", "platform", RD, AV, "Read recorded artifacts and their provenance."),
    _tool("trace.read", "Read traceability", "platform", RD, AV, "Read the requirement-to-evidence trace graph."),
    _tool("escalation.raise", "Raise escalation", "platform", WR, AV, "Raise a structured escalation."),
    _tool("task.create", "Create tasks", "platform", WR, AV, "Create tasks in a project."),
    _tool("task.assign", "Assign tasks", "platform", WR, AV, "Assign or reassign task owners and reviewers."),
    _tool("task.cancel", "Cancel tasks", "platform", WR, AV, "Cancel planned or branched-away work."),
    _tool("review.create", "Record reviews", "platform", WR, AV, "Record an independent review verdict."),
    _tool("approval.grant", "Grant approvals", "platform", APP, AV, "Approve work or a gate within authority."),
    # VeriTriage: the verification-intelligence subsystem, really executable.
    _tool("veritriage.investigate", "VeriTriage investigation", "verification-intelligence", EXE, AV,
          "Run the deterministic VeriTriage pipeline over verification artifacts."),
    _tool("veritriage.explain_log", "VeriTriage log explanation", "verification-intelligence", RD, AV,
          "Explain what a log is, which parser claims it, and what it contains."),
    _tool("knowledge.search", "Knowledge search", "verification-intelligence", RD, AV,
          "Search the VeriTriage Knowledge Packs."),
    # Source control and specs (organization plans around these).
    _tool("spec.read", "Read specifications", "documents", RD, CO, "Read specifications and standards."),
    _tool("git.read", "Git read", "scm", RD, CO, "Read repositories."),
    _tool("git.write", "Git write", "scm", WR, CO, "Commit to working branches."),
    _tool("git.merge", "Git merge", "scm", WR, CO, "Merge to protected branches."),
    _tool("code.search", "Code search", "scm", RD, CO, "Search source code."),
    # RTL and verification EDA.
    _tool("lint.run", "Lint", "eda", EXE, AV, "RTL lint against coding standards."),
    _tool("simulator.run", "Simulator", "eda", EXE, AV, "Compile and simulate RTL and testbenches."),
    _tool("test.run", "Run tests", "eda", EXE, AV, "Run individual tests."),
    _tool("regression.run", "Run regressions", "eda", EXE, CO, "Launch and monitor regressions."),
    _tool("waveform.inspect", "Waveform viewer", "eda", RD, CO, "Inspect waveforms."),
    _tool("coverage.read", "Coverage database", "eda", RD, CO, "Read and merge coverage."),
    _tool("formal.run", "Formal engine", "eda", EXE, AV, "Model checking and property proofs."),
    _tool("formal.cover", "Formal cover check", "eda", EXE, AV,
          "Non-vacuity: every cover in a proof setup is reached under its assumptions (M27)."),
    _tool("vplan.check", "Verification plan check", "verification", RD, AV,
          "A verification plan is valid and covers exactly the requirements its approved spec tags (M29)."),
    _tool("equivalence.run", "Equivalence checker", "eda", EXE, CO, "Logic equivalence checking."),
    _tool("cdc.run", "CDC/RDC analyzer", "eda", EXE, CO, "Structural and functional crossing analysis."),
    # Implementation EDA.
    _tool("synth.run", "Synthesis", "eda", EXE, AV, "Logic synthesis."),
    _tool("sta.run", "Static timing", "eda", EXE, AV, "Static timing of a netlist under an SDC (OpenSTA)."),
    _tool("pnr.run", "Place and route", "eda", EXE, AV,
          "Floorplan, placement, and routing in one staged run, with timing (OpenROAD)."),
    _tool("power.run", "Power analysis", "eda", EXE, CO, "Power, IR-drop, and EM."),
    _tool("pv.run", "Physical verification", "eda", EXE, CO, "DRC, LVS, ERC, antenna, density."),
    _tool("dft.run", "DFT tools", "eda", EXE, CO, "ATPG, MBIST, and commercial scan flows."),
    _tool("dft.scan_insert", "Scan insertion", "eda", EXE, AV, "Mux-D scan flops stitched into one chain."),
    _tool("dft.check", "DFT rule check", "eda", EXE, AV, "Testability rules over the synthesized netlist."),
    _tool("dft.scan_sim", "Scan chain simulation", "eda", EXE, AV, "Shift and capture through the chain in simulation."),
    _tool("dft.atpg", "ATPG", "eda", EXE, AV, "Stuck-at patterns, with coverage measured by fault simulation."),
    _tool("dft.mbist", "Memory BIST", "eda", EXE, AV, "A March C- controller run against the memory in simulation."),
    # Software and infrastructure.
    _tool("compiler.run", "Compiler toolchain", "software", EXE, CO, "Build firmware and software."),
    _tool("fw.build", "Firmware build", "software", EXE, AV, "Compile C firmware under strict warning flags."),
    _tool("fw.test", "Firmware co-simulation", "software", EXE, AV,
          "Run a driver's tests against a Verilator model of the RTL, over real bus transactions."),
    _tool("fw.cross_build", "Firmware cross build", "software", EXE, AV,
          "Cross-compile a driver and its tests for bare-metal RV32I into a linked ELF, with its code size."),
    _tool("fw.soc_test", "Firmware on a RISC-V core", "software", EXE, AV,
          "Run a driver's tests on a RISC-V core (PicoRV32) whose loads and stores reach the RTL over its bus."),
    _tool("debugger.attach", "Debugger", "software", EXE, CO, "Attach to targets and models."),
    _tool("ci.configure", "CI configuration", "infrastructure", WR, CO, "Change CI pipelines."),
    _tool("farm.submit", "Compute farm", "infrastructure", EXE, CO, "Submit jobs to the compute farm."),
    _tool("doc.publish", "Publish documents", "documents", WR, CO, "Publish documents to the knowledge base."),
]
