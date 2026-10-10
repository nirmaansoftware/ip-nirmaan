"""The deliverable tree: how a finished IP is laid out when it leaves the company.

Each folder names the artifact kinds it collects, the capabilities it collects
as a fallback (for an artifact whose kind no folder names), and the evidence
sections it holds. ``nirmaan export`` reads this table and names no folder
itself, so adding a folder or moving a kind is an edit here (or a
``register_folder`` overlay), never a code change.

Implementation views (netlist, timing, power, layout) travel with the RTL they
were built from until physical design gets a folder of its own.
"""

from __future__ import annotations

from nirmaan.models import DeliverableFolder, ExportSection

X = ExportSection

DELIVERABLE_FOLDERS: list[DeliverableFolder] = [
    DeliverableFolder(
        id="01_requirement", title="Requirement",
        description="What was asked for, as the organization understood and baselined it.",
        artifact_kinds=("requirements_spec", "product_brief", "competitive_analysis"),
        capabilities=("req.analyze", "product.define", "product.competitive"),
    ),
    DeliverableFolder(
        id="02_architecture", title="Architecture",
        description="Interfaces, IP architecture, and the architecture views the requirement called for.",
        artifact_kinds=("architecture_spec", "ip_architecture_spec", "interface_spec", "register_map",
                        "interconnect_architecture",
                        "qos_architecture", "memory_architecture", "security_architecture", "power_architecture",
                        "performance_model", "software_architecture", "threat_model", "impact_analysis"),
        capabilities=("arch.system", "arch.ip", "arch.interface", "arch.interconnect", "arch.memory",
                      "arch.security", "arch.power", "arch.performance", "arch.software", "rtl.impact"),
    ),
    DeliverableFolder(
        id="03_microarchitecture", title="Microarchitecture",
        description="Pipelines, buffers, arbitration, and datapaths at cycle level.",
        artifact_kinds=("microarchitecture_spec",),
        capabilities=("arch.microarchitecture",),
    ),
    DeliverableFolder(
        id="04_rtl", title="RTL",
        description="RTL, power intent, quality, and the implementation views built from the RTL.",
        artifact_kinds=("rtl_source", "power_intent", "quality_report", "constraints", "netlist", "synthesis_report",
                        "timing_report", "power_report", "dft_netlist", "mbist_configuration", "floorplan",
                        "power_grid", "layout", "physical_verification_report", "ip_package", "merge_record"),
        capabilities=("rtl.implement", "rtl.cdc_design", "rtl.power_intent", "rtl.quality", "rtl.integrate",
                      "scm.merge", "synth.run", "sta.analyze", "sta.constraints", "power.analyze", "dft.insert",
                      "dft.mbist", "pd.floorplan", "pd.power_plan", "pd.place_route", "pd.signoff_checks"),
    ),
    DeliverableFolder(
        id="05_verification", title="Verification",
        description="Plan, environment, tests, assertions, coverage, regression, debug, CDC, and closure.",
        artifact_kinds=("verification_architecture", "verification_plan", "testbench", "vip_configuration", "tests",
                        "assertions", "coverage_report", "regression_report", "triage_report", "root_cause_analysis",
                        "cdc_report", "security_verification_report", "verification_closure_report",
                        "regression_infrastructure"),
        capabilities=("dv.architecture", "dv.plan", "dv.testbench", "dv.vip", "dv.directed_tests",
                      "dv.random_tests", "dv.assertions", "dv.coverage", "dv.regression", "dv.closure",
                      "debug.triage", "debug.root_cause", "cdc.verify", "secver.verify", "infra.regression"),
    ),
    DeliverableFolder(
        id="06_formal", title="Formal",
        description="Property proofs and equivalence results.",
        artifact_kinds=("formal_report", "equivalence_report"),
        capabilities=("formal.prove", "formal.equivalence"),
    ),
    DeliverableFolder(
        id="07_lint", title="Lint",
        description="Lint and coding-standard results with dispositioned waivers.",
        artifact_kinds=("lint_report",),
        capabilities=("rtl.lint",),
    ),
    DeliverableFolder(
        id="08_documentation", title="Documentation",
        description="Integration guide, user manual, register reference, and reference software.",
        artifact_kinds=("document", "register_doc", "programming_guide", "driver", "driver_test"),
        capabilities=("doc.write", "doc.registers", "sw.register_programming", "sw.driver", "fw.driver"),
    ),
    DeliverableFolder(
        id="09_evidence", title="Evidence",
        description="Requirement traceability, tool runs, reviews, and the verified audit chain.",
        artifact_kinds=("traceability_matrix", "audit_report"),
        capabilities=("quality.traceability", "quality.audit"),
        sections=(X.TRACE, X.TOOL_RUNS, X.REVIEWS, X.AUDIT_CHAIN, X.ENGINEERING_GRAPH, X.FAILURES),
    ),
    DeliverableFolder(
        id="10_signoff", title="Signoff",
        description="What is and is not signed off, from gate approvals the engine recorded, and the decisions behind it.",
        artifact_kinds=("release_record",),
        capabilities=("release.manage",),
        sections=(X.SIGNOFF, X.DECISIONS),
    ),
]
