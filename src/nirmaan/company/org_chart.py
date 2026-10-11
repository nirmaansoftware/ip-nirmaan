"""The IP Nirmaan org chart, level profiles, and executive roles.

Only the structure is written here. Roles for every division, department,
team, and practice are derived by the builder from the unit kinds: a VP per
division, a director per department, a manager and tech lead per team, and the
senior/engineer/junior/intern ladder on every leaf.
"""

from __future__ import annotations

from typing import Any

from nirmaan.models import (
    Function,
    Level,
    LevelProfile,
    OrgUnit,
    Role,
    UnitKind,
    UnitStatus,
)

COMPANY_NAME = "IP Nirmaan"
ROOT = "nirmaan"

ARCH_LADDER = (Level.STAFF, Level.SENIOR, Level.ENGINEER)
KNOWLEDGE_LADDER = (Level.SENIOR, Level.ENGINEER, Level.JUNIOR)

_ENGINEERING_SKILLS = ("git", "linux", "debugging")
_ENGINEERING_TOOLS = ("git.read", "code.search")


def _u(kind: UnitKind, slug: str, name: str, *children: dict, **kw: Any) -> dict:
    return {"kind": kind, "slug": slug, "name": name, "children": list(children), **kw}


def div(slug, name, *children, **kw):
    return _u(UnitKind.DIVISION, slug, name, *children, **kw)


def dept(slug, name, *children, **kw):
    return _u(UnitKind.DEPARTMENT, slug, name, *children, **kw)


def team(slug, name, *children, **kw):
    return _u(UnitKind.TEAM, slug, name, *children, **kw)


def prac(slug, name, noun, *skills, **kw):
    return _u(UnitKind.PRACTICE, slug, name, noun=noun, skills=skills, **kw)


# --- Structure -----------------------------------------------------------------

_PRODUCT = div(
    "product", "Product and Programs",
    team("management", "Product Management",
         prac("strategy", "Product Strategy", "Product Strategist", "product_strategy"),
         prac("requirements", "Requirements Management", "Requirements Engineer", "requirements_engineering"),
         prac("features", "Feature Management", "Feature Manager", "product_strategy"),
         prac("roadmap", "Roadmap", "Roadmap Planner", "product_strategy"),
         prac("competitive", "Competitive Analysis", "Competitive Analyst", "competitive_analysis"),
         prac("customer", "Customer Requirements", "Customer Requirements Engineer", "requirements_engineering"),
         skills=("requirements_engineering",), ladder=KNOWLEDGE_LADDER),
    team("programs", "Program Management",
         prac("tpm", "Technical Program Management", "Technical Program Manager", "program_management"),
         prac("schedule", "Schedule", "Schedule Planner", "project_management"),
         prac("milestones", "Milestones", "Milestone Planner", "project_management"),
         prac("dependencies", "Dependencies", "Dependency Manager", "project_management", "risk_management"),
         prac("risks", "Risks", "Risk Manager", "risk_management"),
         prac("resources", "Resources", "Resource Planner", "project_management"),
         prac("release", "Release Management", "Release Manager", "release_management"),
         ladder=KNOWLEDGE_LADDER),
    team("projects", "Project Management",
         prac("planning", "Project Planning", "Project Planner", "project_management"),
         prac("tasks", "Task Management", "Task Coordinator", "project_management"),
         prac("status", "Status", "Status Coordinator", "project_management"),
         prac("reporting", "Reporting", "Reporting Analyst", "project_management"),
         ladder=KNOWLEDGE_LADDER),
    function=Function.PRODUCT, head_role="exec.cpo",
    mission="Decide what to build, plan how it gets built, and ship it.",
)

_ARCHITECTURE = div(
    "architecture", "Architecture",
    dept("system", "System Architecture",
         prac("soc", "SoC Architecture", "SoC Architect", "system_architecture"),
         prac("ip", "IP Architecture", "IP Architect", "ip_architecture"),
         prac("memory", "Memory Architecture", "Memory Architect", "memory_architecture"),
         prac("interconnect", "Interconnect Architecture", "Interconnect Architect", "noc_architecture", "qos_architecture"),
         prac("security", "Security Architecture", "Security Architect", "security_architecture"),
         prac("power", "Power Architecture", "Power Architect", "power_architecture"),
         prac("performance", "Performance Architecture", "Performance Architect", "performance_modeling"),
         prac("software", "Software Architecture", "Software Architect", "software_architecture"),
         skills=("system_architecture",), ladder=ARCH_LADDER),
    dept("micro", "Microarchitecture",
         prac("cpu", "CPU", "CPU Microarchitect", "cpu_microarchitecture"),
         prac("gpu", "GPU", "GPU Microarchitect", "gpu_microarchitecture"),
         prac("npu", "NPU", "NPU Microarchitect", "npu_microarchitecture"),
         prac("dsp", "DSP", "DSP Microarchitect", "dsp_microarchitecture"),
         prac("noc", "NoC", "NoC Microarchitect", "noc_architecture", "qos_architecture"),
         prac("cache", "Cache", "Cache Microarchitect", "cache_microarchitecture"),
         prac("memctrl", "Memory Controller", "Memory Controller Microarchitect", "memory_controller_microarchitecture"),
         prac("peripheral", "Peripheral IP", "Peripheral IP Microarchitect", "peripheral_microarchitecture"),
         skills=("rtl_microarchitecture",), ladder=ARCH_LADDER),
    dept("interface", "Interface Architecture",
         prac("axi", "AXI", "AXI Interface Architect", "axi"),
         prac("ace", "ACE", "ACE Interface Architect", "ace"),
         prac("chi", "CHI", "CHI Interface Architect", "chi"),
         prac("apb", "APB", "APB Interface Architect", "apb"),
         prac("ahb", "AHB", "AHB Interface Architect", "ahb"),
         prac("pcie", "PCIe", "PCIe Interface Architect", "pcie"),
         prac("cxl", "CXL", "CXL Interface Architect", "cxl"),
         prac("ddr", "DDR", "DDR Interface Architect", "ddr"),
         prac("usb", "USB", "USB Interface Architect", "usb"),
         prac("ethernet", "Ethernet", "Ethernet Interface Architect", "ethernet"),
         prac("noc", "NoC Interfaces", "NoC Interface Architect", "noc_protocol"),
         prac("custom", "Custom Interfaces", "Custom Interface Architect", "custom_interfaces"),
         skills=("interface_specification",), ladder=ARCH_LADDER),
    function=Function.ENGINEERING, head_role="exec.chief_architect",
    skills=_ENGINEERING_SKILLS, tools=_ENGINEERING_TOOLS,
    mission="Own what every product is, structurally, before anyone builds it.",
)

_DESIGN = div(
    "design", "Design Engineering",
    dept("rtl", "RTL Engineering",
         team("architecture", "RTL Architecture", noun="RTL Architect",
              skills=("rtl_microarchitecture", "synthesis_awareness", "change_impact_analysis"), ladder=ARCH_LADDER),
         team("design", "Design Engineering",
              prac("datapath", "Datapath", "Datapath Design Engineer", "datapath_design"),
              prac("control", "Control Logic", "Control Logic Design Engineer", "control_logic_design"),
              prac("fsm", "FSM", "FSM Design Engineer", "fsm_design"),
              prac("pipeline", "Pipeline", "Pipeline Design Engineer", "pipeline_design"),
              prac("memory", "Memory", "Memory Design Engineer", "memory_design"),
              prac("arithmetic", "Arithmetic", "Arithmetic Design Engineer", "arithmetic_design"),
              prac("interconnect", "Interconnect", "Interconnect Design Engineer", "interconnect_design")),
         team("interface", "Interface Engineering", noun="Interface Design Engineer",
              skills=("axi", "chi", "apb", "ahb", "axi_stream", "pcie")),
         team("cdc", "CDC / RDC Design", noun="CDC Design Engineer", skills=("cdc_design", "reset_design")),
         team("low_power", "Low Power", noun="Low Power Design Engineer", skills=("low_power_design",)),
         team("quality", "RTL Quality",
              prac("lint", "Lint", "Lint Engineer", "rtl_lint"),
              prac("standards", "Coding Standards", "Coding Standards Engineer", "coding_standards", "rtl_lint"),
              prac("synthesis", "Synthesis Awareness", "RTL Quality Engineer", "synthesis_awareness"),
              prac("review", "Code Review", "RTL Review Engineer", "code_review_practice", "change_impact_analysis"),
              skills=("rtl_lint", "coding_standards")),
         team("automation", "Design Automation", noun="Design Automation Engineer", skills=("design_automation",)),
         skills=("rtl_design", "change_integration")),
    dept("integration", "IP Integration and Delivery",
         team("packaging", "IP Integration", noun="IP Integration Engineer", skills=("ip_integration",))),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=_ENGINEERING_SKILLS, tools=_ENGINEERING_TOOLS,
    mission="Turn microarchitecture into clean, reviewed, synthesizable RTL.",
)

_VERIFICATION = div(
    "verification", "Verification",
    team("architecture", "Verification Architecture", noun="Verification Architect",
         skills=("verification_architecture",), ladder=ARCH_LADDER),
    team("planning", "Verification Planning", noun="Verification Planning Engineer",
         skills=("verification_planning",)),
    team("simulation", "Simulation",
         prac("systemverilog", "SystemVerilog", "SystemVerilog Verification Engineer", "directed_testing"),
         prac("uvm", "UVM", "UVM Verification Engineer", "uvm", "constrained_random"),
         prac("testbench", "Testbench", "Testbench Engineer", "uvm", "constrained_random", "directed_testing"),
         prac("vip", "VIP", "VIP Engineer", "vip_integration", "axi", "chi", "pcie"),
         prac("regression", "Regression", "Regression Engineer", "regression_management"),
         skills=("uvm", "sva")),
    team("formal", "Formal Verification",
         prac("property", "Property Verification", "Formal Verification Engineer", "formal_verification"),
         prac("model_checking", "Model Checking", "Model Checking Engineer", "model_checking"),
         prac("equivalence", "Equivalence", "Equivalence Engineer", "equivalence_checking"),
         prac("coverage", "Formal Coverage", "Formal Coverage Engineer", "formal_coverage")),
    team("coverage", "Coverage",
         prac("code", "Code Coverage", "Code Coverage Engineer", "code_coverage"),
         prac("functional", "Functional Coverage", "Functional Coverage Engineer", "functional_coverage"),
         prac("assertion", "Assertion Coverage", "Assertion Coverage Engineer", "assertion_coverage", "sva")),
    team("debug", "Debug",
         prac("logs", "Log Analysis", "Log Analysis Engineer", "log_analysis"),
         prac("waveforms", "Waveform Analysis", "Waveform Debug Engineer", "waveform_debug"),
         prac("triage", "Failure Triage", "Failure Triage Engineer", "failure_triage"),
         prac("root_cause", "Root Cause", "Root Cause Engineer", "root_cause_analysis"),
         prac("intelligence", "Regression Intelligence", "Regression Intelligence Engineer", "regression_intelligence"),
         skills=("debugging", "root_cause_analysis"), tools=("veritriage.investigate", "veritriage.explain_log")),
    team("cdc", "CDC / RDC Verification", noun="CDC Verification Engineer", skills=("cdc_verification",)),
    team("security", "Security Verification", noun="Security Verification Engineer", skills=("security_verification",)),
    team("signoff", "Verification Signoff", noun="Verification Signoff Engineer",
         skills=("verification_signoff", "functional_coverage"), ladder=(Level.STAFF, Level.SENIOR)),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=(*_ENGINEERING_SKILLS, "systemverilog", "verification_signoff"),
    tools=(*_ENGINEERING_TOOLS, "veritriage.investigate"),
    mission="Prove, with evidence, that the design does what the requirements say.",
)

_IMPLEMENTATION = div(
    "implementation", "Silicon Implementation",
    dept("pd", "Physical Design",
         team("synthesis", "Synthesis", noun="Synthesis Engineer", skills=("synthesis",)),
         team("floorplan", "Floorplanning", noun="Floorplan Engineer", skills=("floorplanning",)),
         team("power_plan", "Power Planning", noun="Power Planning Engineer", skills=("power_planning",)),
         team("placement", "Placement", noun="Placement Engineer", skills=("place_and_route",)),
         team("cts", "Clock Tree Synthesis", noun="CTS Engineer", skills=("place_and_route",)),
         team("routing", "Routing", noun="Routing Engineer", skills=("place_and_route",)),
         team("sta", "Static Timing Analysis",
              prac("setup", "Setup", "Setup Timing Engineer", "sta"),
              prac("hold", "Hold", "Hold Timing Engineer", "sta"),
              prac("mcmm", "MCMM", "MCMM Timing Engineer", "sta"),
              prac("constraints", "Constraints", "Timing Constraints Engineer", "timing_constraints"),
              skills=("sta",)),
         team("power", "Power Analysis",
              prac("dynamic", "Dynamic Power", "Dynamic Power Engineer", "power_analysis"),
              prac("leakage", "Leakage", "Leakage Power Engineer", "power_analysis"),
              prac("ir", "IR Drop", "IR Drop Engineer", "power_analysis"),
              prac("em", "Electromigration", "EM Engineer", "power_analysis")),
         team("signoff", "Physical Signoff",
              prac("drc", "DRC", "DRC Engineer", "physical_verification"),
              prac("lvs", "LVS", "LVS Engineer", "physical_verification"),
              prac("erc", "ERC", "ERC Engineer", "physical_verification"),
              prac("antenna", "Antenna", "Antenna Engineer", "physical_verification"),
              prac("density", "Density", "Density Engineer", "physical_verification"),
              skills=("implementation_signoff",))),
    dept("dft", "Design for Test",
         team("engineering", "DFT Engineering",
              prac("scan", "Scan", "Scan Engineer", "scan_design"),
              prac("atpg", "ATPG", "ATPG Engineer", "atpg"),
              prac("mbist", "MBIST", "MBIST Engineer", "mbist"),
              prac("lbist", "LBIST", "LBIST Engineer", "lbist"),
              prac("jtag", "JTAG", "JTAG Engineer", "jtag"),
              prac("compression", "Compression", "Test Compression Engineer", "test_compression"),
              prac("memory_test", "Memory Test", "Memory Test Engineer", "mbist"),
              prac("faults", "Fault Modeling", "Fault Modeling Engineer", "fault_modeling"),
              prac("verification", "DFT Verification", "DFT Verification Engineer", "dft_verification"),
              skills=("dft_architecture",))),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=(*_ENGINEERING_SKILLS, "implementation_signoff"), tools=_ENGINEERING_TOOLS,
    mission="Take RTL to signoff-clean silicon: timing, power, test, and physical.",
)

_SOFTWARE = div(
    "software", "Software",
    team("firmware", "Firmware",
         prac("boot", "Boot", "Boot Firmware Engineer", "embedded_firmware", "secure_boot"),
         prac("hal", "HAL", "HAL Engineer", "embedded_firmware"),
         prac("bsp", "BSP", "BSP Engineer", "embedded_firmware"),
         prac("drivers", "Drivers", "Driver Engineer", "device_drivers")),
    team("registers", "Register Programming", noun="Register Programming Engineer", skills=("register_programming",)),
    team("diagnostics", "Diagnostics", noun="Diagnostics Engineer", skills=("diagnostics_software",)),
    team("validation", "Validation Software", noun="Validation Software Engineer", skills=("diagnostics_software", "embedded_firmware")),
    team("performance", "Performance Software", noun="Performance Software Engineer", skills=("performance_modeling", "embedded_firmware")),
    team("tools", "Developer Tools",
         prac("sdk", "SDK", "SDK Engineer", "developer_tools"),
         prac("compiler", "Compiler", "Compiler Engineer", "developer_tools"),
         prac("debugger", "Debugger", "Debugger Engineer", "developer_tools"),
         prac("utilities", "Utilities", "Utilities Engineer", "developer_tools")),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=(*_ENGINEERING_SKILLS, "c_programming"), tools=(*_ENGINEERING_TOOLS, "compiler.run"),
    mission="Make the hardware usable: firmware, drivers, diagnostics, and tools.",
)

_SECURITY = div(
    "security", "Security",
    team("hardware", "Hardware Security", noun="Hardware Security Engineer", skills=("hardware_security",)),
    team("secure_boot", "Secure Boot", noun="Secure Boot Engineer", skills=("secure_boot",)),
    team("crypto", "Cryptography", noun="Cryptography Engineer", skills=("cryptography",)),
    team("threats", "Threat Modeling", noun="Threat Modeling Engineer", skills=("threat_modeling",)),
    team("architecture", "Security Architecture", noun="Security Architect", skills=("security_architecture",), ladder=ARCH_LADDER),
    team("verification", "Security Verification", noun="Security Verification Engineer", skills=("security_verification",)),
    team("vulnerabilities", "Vulnerability Management", noun="Vulnerability Engineer", skills=("vulnerability_management",)),
    function=Function.ENGINEERING, sponsor_role="exec.cto",
    skills=_ENGINEERING_SKILLS, tools=_ENGINEERING_TOOLS,
    mission="Make security a property the company can prove, not assert.",
)

_INFRASTRUCTURE = div(
    "infrastructure", "Engineering Infrastructure",
    team("build", "Build and CI",
         prac("ci", "CI/CD", "CI Engineer", "ci_cd"),
         prac("build_systems", "Build Systems", "Build Engineer", "build_systems"),
         prac("artifacts", "Artifact Management", "Artifact Engineer", "artifact_management"),
         prac("repositories", "Repository Management", "Repository Engineer", "change_integration", "configuration_management"),
         ladder=KNOWLEDGE_LADDER),
    team("compute", "Compute Platform",
         prac("compute", "Compute", "Compute Engineer", "compute_cloud"),
         prac("cloud", "Cloud", "Cloud Engineer", "compute_cloud"),
         prac("containers", "Containers", "Container Engineer", "compute_cloud"),
         prac("monitoring", "Monitoring", "Monitoring Engineer", "monitoring"),
         ladder=KNOWLEDGE_LADDER),
    team("eda", "EDA and Regression",
         prac("regression", "Regression Infrastructure", "Regression Infrastructure Engineer", "regression_infrastructure"),
         prac("environment", "EDA Environment", "EDA Environment Engineer", "eda_environment"),
         prac("tooling", "Developer Tooling", "Developer Tooling Engineer", "developer_tools", "design_automation"),
         ladder=KNOWLEDGE_LADDER),
    function=Function.INFRASTRUCTURE, sponsor_role="exec.coo",
    skills=_ENGINEERING_SKILLS, tools=_ENGINEERING_TOOLS,
    mission="Keep engineering fast, reproducible, and observable.",
)

_DOCUMENTATION = dept(
    "documentation", "Technical Documentation",
    team("writing", "Technical Writing",
         prac("specifications", "Specifications", "Specification Writer", "specification_writing"),
         prac("architecture", "Architecture Documents", "Architecture Writer", "specification_writing"),
         prac("design", "Design Documents", "Design Documentation Writer"),
         prac("verification", "Verification Plans", "Verification Documentation Writer"),
         prac("api", "API Documentation", "API Writer"),
         prac("registers", "Register Documentation", "Register Documentation Writer", "register_documentation"),
         prac("release_notes", "Release Notes", "Release Notes Writer"),
         prac("manuals", "User Manuals", "User Manual Writer", "user_documentation"),
         prac("knowledge_base", "Knowledge Base", "Knowledge Base Curator"),
         ladder=KNOWLEDGE_LADDER),
    function=Function.PRODUCT, sponsor_role="exec.cpo", skills=("technical_writing",), tools=("doc.publish",),
    mission="Make every product understandable, accurately, from one source of truth.",
)

_QUALITY = div(
    "quality", "Quality and Process",
    team("engineering", "Quality Engineering",
         prac("design_reviews", "Design Reviews", "Design Review Facilitator", "design_review_facilitation"),
         prac("verification_signoff", "Verification Signoff Oversight", "Signoff Quality Engineer", "verification_signoff"),
         prac("release", "Release Quality", "Release Quality Engineer", "release_quality"),
         prac("process", "Process QA", "Process QA Engineer", "engineering_audit"),
         prac("configuration", "Configuration Management", "Configuration Manager", "configuration_management"),
         prac("traceability", "Traceability", "Traceability Engineer", "traceability"),
         prac("compliance", "Compliance", "Compliance Engineer", "compliance"),
         prac("audits", "Engineering Audits", "Engineering Auditor", "engineering_audit"),
         ladder=KNOWLEDGE_LADDER),
    function=Function.QUALITY, sponsor_role="exec.coo", skills=("release_quality", "traceability"),
    tools=("git.read",),
    mission="Make sure what the company says is done is actually done.",
)

_BUSINESS = [
    div(slug, name, function=Function.BUSINESS, sponsor_role=sponsor, status=UnitStatus.PLACEHOLDER,
        skills=("business_operations",), mission=f"{name}: declared so the company is whole; not yet staffed.")
    for slug, name, sponsor in (
        ("finance", "Finance", "exec.coo"),
        ("legal", "Legal", "exec.coo"),
        ("hr", "Human Resources", "exec.coo"),
        ("procurement", "Procurement", "exec.coo"),
        ("operations", "Operations", "exec.coo"),
        ("sales", "Sales", "exec.ceo"),
        ("marketing", "Marketing", "exec.ceo"),
        ("customer_success", "Customer Success", "exec.ceo"),
        ("partnerships", "Partnerships", "exec.ceo"),
    )
]

STRUCTURE = [
    _PRODUCT,
    _ARCHITECTURE,
    _DESIGN,
    _VERIFICATION,
    _IMPLEMENTATION,
    _SOFTWARE,
    _SECURITY,
    _INFRASTRUCTURE,
    _DOCUMENTATION,
    _QUALITY,
    *_BUSINESS,
]


def _flatten(spec: dict, parent: str) -> list[OrgUnit]:
    uid = spec["slug"] if parent == ROOT else f"{parent}.{spec['slug']}"
    fields = {k: v for k, v in spec.items() if k not in ("slug", "children", "kind")}
    fields.setdefault("function", _function_of(parent))
    unit = OrgUnit(id=uid, kind=spec["kind"], parent=parent, **fields)
    units = [unit]
    for child in spec["children"]:
        child.setdefault("function", unit.function)
        units += _flatten(child, uid)
    return units


def _function_of(parent: str) -> Function:
    return Function.ENGINEERING


def units() -> list[OrgUnit]:
    found = [
        OrgUnit(
            id=ROOT,
            name=COMPANY_NAME,
            kind=UnitKind.COMPANY,
            function=Function.EXECUTIVE,
            head_role="exec.ceo",
            mission="An AI-native semiconductor IP company: requirement in, evidence-backed deliverable out.",
            skills=("company_methodology",),
            tools=("project.read", "status.read", "artifact.read", "trace.read", "escalation.raise",
                   "spec.read", "knowledge.search"),
        ),
        OrgUnit(
            id="executive",
            name="Executive Office",
            kind=UnitKind.OFFICE,
            function=Function.EXECUTIVE,
            parent=ROOT,
            head_role="exec.ceo",
            mission="Set direction, allocate resources, resolve what nobody else can.",
        ),
    ]
    for spec in STRUCTURE:
        found += _flatten(dict(spec, children=[dict(c) for c in spec["children"]]), ROOT)
    return found


# --- Executive roles (explicit: they are not derived from a unit kind) -----------

_EXEC_TOOLS = ("approval.grant", "task.create", "task.assign", "task.cancel", "review.create")


def _exec(id: str, title: str, level: Level, reports_to: str | None, skills: tuple[str, ...],
          responsibilities: tuple[str, ...]) -> Role:
    return Role(
        id=id,
        title=title,
        unit="executive",
        level=level,
        reports_to=reports_to,
        escalates_to=reports_to,
        skills=("company_methodology", "executive_leadership", "engineering_management", *skills),
        tools=("project.read", "status.read", "artifact.read", "trace.read", "escalation.raise",
               "spec.read", "knowledge.search", *_EXEC_TOOLS),
        responsibilities=responsibilities,
        generated=False,
    )


EXECUTIVES: list[Role] = [
    _exec("exec.board", "Board / Owner", Level.BOARD, None, ("corporate_governance",),
          ("Own the company charter and constitution.", "Approve changes to engineering policy.")),
    _exec("exec.ceo", "Chief Executive Officer", Level.CEO, "exec.board", (),
          ("Set company strategy.", "Resolve strategic conflicts between functions.")),
    _exec("exec.cto", "Chief Technology Officer", Level.EXECUTIVE, "exec.ceo",
          ("system_architecture", "verification_signoff", "implementation_signoff"),
          ("Own technology strategy and engineering execution.", "Final technical escalation point.")),
    _exec("exec.coo", "Chief Operating Officer", Level.EXECUTIVE, "exec.ceo",
          ("release_quality", "program_management"),
          ("Own operations, infrastructure, and quality.",)),
    _exec("exec.cpo", "Chief Product Officer", Level.EXECUTIVE, "exec.ceo",
          ("product_strategy", "requirements_engineering", "program_management", "release_management"),
          ("Own what the company builds and ships.", "Approve requirement baselines and releases.")),
    _exec("exec.chief_architect", "Chief Architect", Level.EXECUTIVE, "exec.ceo",
          ("system_architecture", "ip_architecture", "noc_architecture", "rtl_microarchitecture"),
          ("Own architectural integrity across products.", "Resolve major architectural conflicts.")),
    _exec("exec.chief_of_staff", "Chief of Staff", Level.EXECUTIVE, "exec.ceo", ("program_management",),
          ("Run the executive operating cadence.", "Track cross-functional commitments.")),
]


# --- Level profiles -----------------------------------------------------------------

_MANAGER_TOOLS = ("task.create", "task.assign", "task.cancel", "approval.grant", "review.create")

LEVEL_PROFILES: list[LevelProfile] = [
    LevelProfile(level=Level.INTERN, responsibilities=(
        "Complete well-scoped {unit} tasks under close supervision.",
        "Escalate uncertainty early rather than guess.",
    )),
    LevelProfile(level=Level.JUNIOR, responsibilities=(
        "Deliver defined {unit} tasks with review.",
        "Record evidence for every claim.",
    )),
    LevelProfile(level=Level.ENGINEER, responsibilities=(
        "Own {unit} tasks end to end.",
        "Submit work with evidence for independent review.",
    )),
    LevelProfile(level=Level.SENIOR, skills=("code_review_practice",), tools=("review.create",), responsibilities=(
        "Own complex {unit} work.",
        "Review peers' work independently.",
        "Mentor junior engineers and interns.",
    )),
    LevelProfile(level=Level.TECH_LEAD, skills=("technical_leadership", "code_review_practice"),
                 tools=("review.create", "approval.grant", "task.create", "task.assign"), responsibilities=(
        "Decompose {unit} work into reviewable tasks.",
        "Review and approve {unit} work within authority.",
        "Resolve technical escalations or raise them.",
    )),
    LevelProfile(level=Level.STAFF, skills=("technical_leadership", "code_review_practice"),
                 tools=("review.create", "approval.grant"), responsibilities=(
        "Set technical direction for {unit}.",
        "Review critical designs and decisions.",
    )),
    LevelProfile(level=Level.MANAGER, skills=("engineering_management",), tools=_MANAGER_TOOLS, responsibilities=(
        "Plan and staff {unit} work.",
        "Delegate, track, and unblock; never silently absorb subordinates' work.",
        "Report status and escalate cross-team issues.",
    )),
    LevelProfile(level=Level.SENIOR_MANAGER, skills=("engineering_management",), tools=_MANAGER_TOOLS,
                 responsibilities=("Coordinate {unit} teams and their dependencies.",)),
    LevelProfile(level=Level.DIRECTOR, skills=("engineering_management",), tools=_MANAGER_TOOLS, responsibilities=(
        "Own {unit} delivery and quality.",
        "Approve gates within authority.",
        "Resolve cross-team conflicts.",
    )),
    LevelProfile(level=Level.VP, skills=("engineering_management", "executive_leadership"), tools=_MANAGER_TOOLS,
                 responsibilities=(
        "Own {unit} strategy, staffing, and signoff.",
        "Resolve strategic conflicts or take them to the executive team.",
    )),
    LevelProfile(level=Level.EXECUTIVE, skills=("executive_leadership", "engineering_management")),
    LevelProfile(level=Level.CEO, skills=("executive_leadership", "engineering_management")),
    LevelProfile(level=Level.BOARD, skills=("corporate_governance",)),
]
