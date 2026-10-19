"""Capabilities: the units of work IP Nirmaan can perform.

A task requires a capability; a skill provides it; a role holds the skill at
some seniority band. Routing is nothing more than that join, which is why a new
engineering domain needs new capability records, not new routing code.
"""

from __future__ import annotations

from nirmaan.models import Capability, CapabilityKind, Level, SeniorityBand

E, A, R, M, S = (
    CapabilityKind.EXECUTION,
    CapabilityKind.ANALYSIS,
    CapabilityKind.REVIEW,
    CapabilityKind.MANAGEMENT,
    CapabilityKind.SIGNOFF,
)
FD, WK, AD, LD = SeniorityBand.FOUNDATION, SeniorityBand.WORKING, SeniorityBand.ADVANCED, SeniorityBand.LEAD


def _cap(
    id: str,
    name: str,
    kind: CapabilityKind,
    description: str,
    band: SeniorityBand = AD,
    produces: tuple[str, ...] = (),
    min_level: Level | None = None,
    approved_inputs: bool = False,
) -> Capability:
    return Capability(
        id=id,
        name=name,
        kind=kind,
        description=description,
        min_band=band,
        produces=produces,
        min_level=min_level,
        approved_inputs=approved_inputs,
    )


CAPABILITIES: list[Capability] = [
    # --- Product, program, project ------------------------------------------
    _cap("req.analyze", "Requirement analysis", A, "Turn a request into traceable, testable requirements.", AD, ("requirements_spec",)),
    _cap("req.review", "Requirements review", R, "Independently review requirements for completeness and testability.", LD),
    _cap("product.define", "Product definition", E, "Define product scope, configurations, and success criteria.", AD, ("product_brief",)),
    _cap("product.competitive", "Competitive analysis", A, "Position a product against alternatives.", AD, ("competitive_analysis",)),
    _cap("program.plan", "Program planning", M, "Plan milestones, dependencies, and resources across teams.", AD, ("program_plan",)),
    _cap("program.risk", "Risk management", A, "Identify, rate, and track program risks.", AD, ("risk_register",)),
    _cap("release.manage", "Release management", M, "Assemble, baseline, and ship a release.", AD, ("release_record",)),
    _cap("project.plan", "Project planning", M, "Plan and track one project's tasks.", AD, ("project_plan",)),
    _cap("signoff.requirements", "Requirements signoff", S, "Approve a requirement baseline.", AD, (), Level.DIRECTOR),
    _cap("signoff.release", "Release signoff", S, "Authorize a deliverable to leave the company.", AD, (), Level.VP),
    # --- Architecture --------------------------------------------------------
    _cap("arch.system", "System architecture", E, "Partition a system and define its top-level structure.", LD, ("architecture_spec",)),
    _cap("arch.ip", "IP architecture", E, "Define an IP block's architecture, configuration space, and interfaces.", LD, ("ip_architecture_spec",)),
    _cap("arch.interconnect", "Interconnect architecture", E, "Topology, routing, ordering, and QoS for on-chip fabrics.", LD, ("interconnect_architecture",)),
    _cap("arch.memory", "Memory architecture", E, "Memory hierarchy, maps, and controllers.", LD, ("memory_architecture",)),
    _cap("arch.security", "Security architecture", E, "Isolation, roots of trust, and protection domains.", LD, ("security_architecture",)),
    _cap("arch.power", "Power architecture", E, "Power domains, states, and intent.", LD, ("power_architecture",)),
    _cap("arch.performance", "Performance architecture", A, "Bandwidth, latency, and throughput modeling.", LD, ("performance_model",)),
    _cap("arch.software", "Software architecture", E, "Hardware/software interface and programming model.", LD, ("software_architecture",)),
    _cap("arch.interface", "Interface specification", E, "Specify a protocol interface: signals, channels, ordering, parameters.", AD, ("interface_spec", "register_map"),
         approved_inputs=True),
    _cap("arch.microarchitecture", "Microarchitecture", E, "Pipelines, buffers, arbitration, and datapaths at cycle level.", LD, ("microarchitecture_spec",),
         approved_inputs=True),
    _cap("arch.review", "Architecture review", R, "Independently review an architecture or microarchitecture.", LD),
    _cap("signoff.architecture", "Architecture signoff", S, "Approve an architecture baseline.", AD, (), Level.DIRECTOR),
    # --- RTL -----------------------------------------------------------------
    _cap("rtl.implement", "RTL implementation", E, "Write synthesizable RTL for a specified block.", AD, ("rtl_source",),
         approved_inputs=True),
    _cap("rtl.review", "RTL review", R, "Independently review RTL for correctness, quality, and intent.", LD),
    _cap("rtl.lint", "Lint and coding-standard checks", E, "Run and disposition lint against coding standards.", WK, ("lint_report",)),
    _cap("rtl.quality", "RTL quality analysis", A, "Synthesis-awareness, area/timing risk, and quality metrics.", AD, ("quality_report",)),
    _cap("rtl.impact", "Change impact analysis", A, "Determine what a design change affects.", AD, ("impact_analysis",)),
    _cap("rtl.cdc_design", "CDC-safe design", E, "Implement synchronizers and safe crossings.", AD, ("rtl_source",),
         approved_inputs=True),
    _cap("rtl.power_intent", "Power intent", E, "Write and maintain power intent (UPF).", AD, ("power_intent",)),
    _cap("rtl.integrate", "IP integration", E, "Integrate blocks, package IP, and deliver configured views.", AD, ("ip_package",)),
    _cap("scm.merge", "Change integration", E, "Merge an approved change to the mainline.", AD, ("merge_record",)),
    _cap("automation.develop", "Design automation", E, "Build flows and scripts that automate engineering work.", AD, ("automation_script",)),
    _cap("signoff.rtl", "RTL signoff", S, "Approve an RTL baseline for downstream consumption.", AD, (), Level.MANAGER),
    # --- Verification --------------------------------------------------------
    _cap("dv.architecture", "Verification architecture", E, "Define the verification strategy and environment architecture.", LD, ("verification_architecture",)),
    _cap("dv.plan", "Verification planning", E, "Write a traceable verification plan.", AD, ("verification_plan",)),
    _cap("dv.testbench", "Testbench development", E, "Build the UVM environment: agents, scoreboards, models.", AD, ("testbench",)),
    _cap("dv.vip", "VIP integration", E, "Integrate and configure verification IP.", AD, ("vip_configuration",)),
    _cap("dv.directed_tests", "Directed tests", E, "Write directed tests for specified scenarios.", WK, ("tests",)),
    _cap("dv.random_tests", "Constrained-random stimulus", E, "Write constrained-random sequences and tests.", AD, ("tests",)),
    _cap("dv.assertions", "Assertions", E, "Write SystemVerilog assertions for interface and design intent.", AD, ("assertions",)),
    _cap("dv.coverage", "Coverage closure", E, "Define coverage models and close coverage.", AD, ("coverage_report",)),
    _cap("dv.regression", "Regression execution", E, "Run, monitor, and report regressions.", WK, ("regression_report",)),
    _cap("dv.review", "Verification review", R, "Independently review plans, environments, and results.", LD),
    _cap("debug.triage", "Failure triage", A, "Classify failures and gather evidence.", WK, ("triage_report",)),
    _cap("debug.root_cause", "Root-cause analysis", A, "Establish a root cause backed by evidence.", AD, ("root_cause_analysis",)),
    _cap("debug.review", "Debug review", R, "Independently review a root-cause conclusion.", LD),
    _cap("formal.prove", "Formal property verification", E, "Prove or falsify properties with formal tools.", AD, ("formal_report",)),
    _cap("formal.equivalence", "Equivalence checking", E, "Prove two design representations equivalent.", AD, ("equivalence_report",)),
    _cap("formal.review", "Formal review", R, "Review formal setups, constraints, and results.", LD),
    _cap("cdc.verify", "CDC/RDC verification", E, "Run and disposition clock- and reset-domain crossing analysis.", AD, ("cdc_report",)),
    _cap("cdc.review", "CDC/RDC review", R, "Independently review crossing analysis and waivers.", LD),
    _cap("secver.verify", "Security verification", E, "Verify security properties and access control.", AD, ("security_verification_report",)),
    _cap("dv.closure", "Verification closure", E, "Assemble the evidence that verification is complete.", LD, ("verification_closure_report",)),
    _cap("signoff.verification", "Verification signoff", S, "Approve verification completeness.", AD, (), Level.DIRECTOR),
    # --- Implementation ------------------------------------------------------
    _cap("synth.run", "Synthesis", E, "Synthesize RTL to a netlist under constraints.", AD, ("netlist", "synthesis_report")),
    _cap("sta.analyze", "Static timing analysis", A, "Analyze timing across modes and corners.", AD, ("timing_report",)),
    _cap("sta.constraints", "Timing constraints", E, "Write and validate timing constraints (SDC).", AD, ("constraints",)),
    _cap("sta.review", "Timing review", R, "Independently review timing results and exceptions.", LD),
    _cap("pd.floorplan", "Floorplanning", E, "Floorplan and partition a block.", AD, ("floorplan",)),
    _cap("pd.power_plan", "Power planning", E, "Design the power grid.", AD, ("power_grid",)),
    _cap("pd.place_route", "Place and route", E, "Place, clock-tree, and route a block.", AD,
         ("layout", "routed_netlist", "power_netlist", "parasitics")),
    _cap("power.analyze", "Power analysis", A, "Dynamic, leakage, IR-drop, and EM analysis.", AD, ("power_report",)),
    _cap("pd.review", "Physical design review", R, "Independently review physical implementation.", LD),
    _cap("pd.signoff_checks", "Physical verification", E, "DRC, LVS, ERC, antenna, and density.", AD,
         ("physical_verification_report", "gds")),
    _cap("signoff.implementation", "Implementation signoff", S, "Approve timing, power, and physical signoff.", AD, (), Level.DIRECTOR),
    # --- DFT -----------------------------------------------------------------
    _cap("dft.insert", "DFT insertion", E, "Insert scan, compression, and test access.", AD, ("dft_netlist",)),
    _cap("dft.atpg", "ATPG", E, "Generate and grade test patterns.", AD, ("test_patterns",)),
    _cap("dft.mbist", "Memory BIST", E, "Insert and verify memory built-in self-test.", AD, ("mbist_configuration",)),
    _cap("dft.verify", "DFT verification", E, "Verify test logic and pattern simulation.", AD, ("dft_verification_report",)),
    _cap("dft.review", "DFT review", R, "Independently review test architecture and coverage.", LD),
    # --- Software ------------------------------------------------------------
    _cap("fw.develop", "Firmware development", E, "Boot, HAL, and BSP code.", AD, ("firmware",)),
    _cap("sw.driver", "Driver development", E, "Device drivers for an IP.", AD, ("driver",)),
    _cap("fw.driver", "Driver against approved RTL", E, "A driver and its tests, run on the approved RTL.", AD,
         ("driver", "driver_test"), approved_inputs=True),
    _cap("sw.register_programming", "Register programming", E, "Programming sequences and register models.", AD, ("programming_guide",)),
    _cap("sw.diagnostics", "Diagnostics", E, "Diagnostics and validation software.", AD, ("diagnostics",)),
    _cap("sw.tools", "Developer tools", E, "SDKs, compilers, debuggers, and utilities.", AD, ("developer_tool",)),
    _cap("sw.review", "Software review", R, "Independently review software.", LD),
    # --- Security ------------------------------------------------------------
    _cap("security.threat_model", "Threat modeling", A, "Enumerate assets, adversaries, and mitigations.", LD, ("threat_model",)),
    _cap("security.crypto", "Cryptography engineering", E, "Specify and review cryptographic blocks.", LD, ("crypto_spec",)),
    _cap("security.vulnerability", "Vulnerability management", A, "Track and remediate vulnerabilities.", AD, ("vulnerability_report",)),
    _cap("security.review", "Security review", R, "Independently review security posture.", LD),
    # --- Infrastructure ------------------------------------------------------
    _cap("infra.ci", "CI/CD", E, "Build and maintain CI pipelines.", AD, ("pipeline_config",)),
    _cap("infra.regression", "Regression infrastructure", E, "Maintain regression farms and scheduling.", AD, ("regression_infrastructure",)),
    _cap("infra.eda_environment", "EDA environment", E, "Tool installation, licensing, and environment.", AD, ("environment_config",)),
    _cap("infra.compute", "Compute and cloud", E, "Compute, storage, and container platforms.", AD, ("compute_config",)),
    # --- Documentation -------------------------------------------------------
    _cap("doc.write", "Technical writing", E, "Write specifications, guides, and release notes.", WK, ("document",)),
    _cap("doc.registers", "Register documentation", E, "Document register maps and fields.", AD, ("register_doc",)),
    _cap("doc.review", "Documentation review", R, "Review documents for accuracy and completeness.", LD),
    # --- Quality -------------------------------------------------------------
    _cap("quality.traceability", "Traceability", A, "Maintain requirement-to-evidence traceability.", AD, ("traceability_matrix",)),
    _cap("quality.design_review", "Design review facilitation", R, "Run formal design reviews and record outcomes.", LD),
    _cap("quality.audit", "Engineering audit", A, "Audit process adherence and evidence.", AD, ("audit_report",)),
    _cap("quality.configuration", "Configuration management", E, "Baseline and control configurations.", AD, ("baseline",)),
    _cap("signoff.quality", "Release quality signoff", S, "Approve release quality.", AD, (), Level.DIRECTOR),
    # --- Management ----------------------------------------------------------
    _cap("mgmt.plan", "Workstream planning", M, "Plan and decompose a workstream.", AD, ("workstream_plan",)),
    _cap("mgmt.delegate", "Delegation", M, "Assign work to the right people.", AD),
    _cap("mgmt.track", "Tracking and reporting", M, "Track status, detect blockers, report.", AD, ("status_report",)),
    _cap("mgmt.decompose", "Technical decomposition", M, "Break technical work into reviewable tasks.", LD),
    _cap("exec.strategy", "Strategy", M, "Set company direction and resolve strategic conflicts.", AD),
]
