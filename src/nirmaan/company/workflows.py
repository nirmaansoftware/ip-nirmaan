"""The workflow registry: IP Nirmaan's reusable engineering processes.

Each workflow names capabilities, never teams or people; the router decides
who. Conditions select stages from requirement features, variants fan a stage
out per feature, and decision stages branch (root-cause classification picks
the RTL, testbench, infrastructure, or specification path, and the untaken
paths are cancelled, visibly, when the decision is recorded).
"""

from __future__ import annotations

from nirmaan.models import (
    Condition,
    Criticality,
    EvidenceKind,
    EvidenceRequirement,
    FileInput,
    Level,
    OnFailure,
    ReviewRequirement,
    StageTemplate,
    Variant,
    WorkflowTemplate,
)

L, M, H, C = Criticality.LOW, Criticality.MEDIUM, Criticality.HIGH, Criticality.CRITICAL
K = EvidenceKind


def rv(capability: str, level: Level = Level.SENIOR) -> ReviewRequirement:
    return ReviewRequirement(capability=capability, min_level=level)


def when(*any_of: str, all_of: tuple[str, ...] = (), none_of: tuple[str, ...] = ()) -> Condition:
    return Condition(any_of=any_of, all_of=all_of, none_of=none_of)


def var(key: str, title: str, *skills: str, cond: Condition | None = None) -> Variant:
    return Variant(key=key, title=title, when=cond or Condition(), skills=skills)


REVIEWED = EvidenceRequirement(description="Independent review recorded", accepts=(K.REVIEW_RECORD,))


def ran(description: str, *tools: str, **kw) -> EvidenceRequirement:
    """A run of one of these tools, or a named human attesting to a run made elsewhere."""
    return EvidenceRequirement(description=description, accepts=(K.TOOL_RUN, K.HUMAN_ATTESTATION), tools=tools,
                               **kw)


def dv_ran(description: str, *tools: str) -> EvidenceRequirement:
    """Verification evidence: a named tool run, a VeriTriage session, or a human attestation."""
    return EvidenceRequirement(
        description=description, accepts=(K.TOOL_RUN, K.VERITRIAGE_SESSION, K.HUMAN_ATTESTATION),
        tools=(*tools, "veritriage.investigate"),
    )


def checked(description: str, tool: str, *files: FileInput, **kw) -> EvidenceRequirement:
    """A real run of ``tool`` over the task's own produced files, met before the work goes to review."""
    return EvidenceRequirement(description=description, accepts=(K.TOOL_RUN,), tools=(tool,), files=files,
                               before_review=True, **kw)


def documented(description: str) -> EvidenceRequirement:
    return EvidenceRequirement(description=description, accepts=(K.DOCUMENT, K.REVIEW_RECORD))


def st(id: str, title: str, phase: str, capability: str, **kw) -> StageTemplate:
    return StageTemplate(id=id, title=title, phase=phase, capability=capability, **kw)


#: M27: a proof counts only if every cover in it is reached under its assumptions (docs/GATES_EVERYWHERE.md).
NOT_VACUOUS = checked("The proof is not vacuous: every cover is reached", "formal.cover",
                      FileInput(param="sby", kinds=("formal_spec",)),
                      FileInput(param="sources", kinds=("rtl_source",)),
                      when_produced=("formal_spec",))

#: M27: the checks produced RTL passes before review on the new-ip, feature-addition, and rtl-change RTL
#: stages, the same ones block-design's RTL stage carries: real lint and simulation, synthesis with no
#: latches, and, when the seat writes a proof setup, a proof that passes and is not vacuous. M29: also on
#: every other stage that produces RTL (docs/GATES_REST.md); the cover run also covers each assertion's
#: antecedent.
RTL_GATES = (
    checked("Lint-clean under the RTL lint rules", "lint.run",
            FileInput(param="sources", kinds=("rtl_source",))),
    checked("Self-checking simulation passes", "simulator.run",
            FileInput(param="sources", kinds=("rtl_source", "testbench")),
            FileInput(param="top", kinds=("testbench",), entry=True)),
    checked("Synthesizes with Yosys, with no latches", "synth.run",
            FileInput(param="sources", kinds=("rtl_source",)),
            FileInput(param="top", kinds=("rtl_source",), entry=True),
            params=(("max_latches", "0"),)),
    checked("Formal properties are proven", "formal.run",
            FileInput(param="sby", kinds=("formal_spec",)),
            FileInput(param="sources", kinds=("rtl_source",)),
            when_produced=("formal_spec",)),
    NOT_VACUOUS,
)


_PROTOCOL_VARIANTS = (
    var("axi", "AXI interface", "axi", cond=when("axi")),
    var("ace", "ACE interface", "ace", cond=when("ace")),
    var("chi", "CHI interface", "chi", cond=when("chi")),
    var("apb", "APB interface", "apb", cond=when("apb")),
    var("ahb", "AHB interface", "ahb", cond=when("ahb")),
    var("pcie", "PCIe interface", "pcie", cond=when("pcie")),
    var("noc", "NoC network interface", "noc_protocol", cond=when("noc")),
)

# --- 1. New IP development --------------------------------------------------------

NEW_IP = WorkflowTemplate(
    id="new-ip",
    name="New IP development",
    description="Requirement to signed-off, packaged IP: the full lifecycle.",
    intents=("new_ip",),
    stages=(
        st("requirements", "Requirements specification", "Requirements", "req.analyze",
           criticality=H, review=rv("req.review"), gate="gate.requirements",
           outputs=("requirements_spec",), evidence=(REVIEWED,)),
        st("interface-spec", "Interface specification", "Architecture", "arch.interface",
           depends_on=("requirements",), variants=_PROTOCOL_VARIANTS, criticality=H,
           review=rv("arch.review"), outputs=("interface_spec",), evidence=(REVIEWED,)),
        st("noc-integration", "NoC integration architecture", "Architecture", "arch.interconnect",
           depends_on=("requirements",), when=when("noc"), skills=("noc_architecture",), criticality=H,
           review=rv("arch.review"), outputs=("interconnect_architecture",), evidence=(REVIEWED,)),
        st("qos-architecture", "QoS architecture", "Architecture", "arch.interconnect",
           depends_on=("requirements",), when=when("qos"), skills=("qos_architecture",), criticality=H,
           review=rv("arch.review"), outputs=("qos_architecture",), evidence=(REVIEWED,)),
        st("power-architecture", "Power architecture", "Architecture", "arch.power",
           depends_on=("requirements",), when=when("low_power"), criticality=H,
           review=rv("arch.review"), outputs=("power_architecture",), evidence=(REVIEWED,)),
        st("security-architecture", "Security architecture and threat model", "Architecture", "arch.security",
           depends_on=("requirements",), when=when("security"), criticality=H,
           review=rv("security.review"), outputs=("security_architecture",), evidence=(REVIEWED,)),
        st("ip-architecture", "IP architecture", "Architecture", "arch.ip",
           depends_on=("interface-spec", "noc-integration", "qos-architecture", "power-architecture",
                       "security-architecture"),
           criticality=H, review=rv("arch.review", Level.STAFF), outputs=("ip_architecture_spec",),
           evidence=(REVIEWED,)),
        st("microarchitecture", "Microarchitecture", "Architecture", "arch.microarchitecture",
           depends_on=("ip-architecture",), criticality=C, review=rv("arch.review", Level.STAFF),
           gate="gate.architecture", outputs=("microarchitecture_spec",), evidence=(REVIEWED,)),
        st("rtl-implementation", "RTL implementation", "RTL", "rtl.implement",
           depends_on=("microarchitecture",), criticality=H, review=rv("rtl.review"),
           variants=(
               var("axi", "AXI slave interface", "axi", cond=when("axi")),
               var("chi", "CHI interface", "chi", cond=when("chi")),
               var("pcie", "PCIe interface", "pcie", cond=when("pcie")),
               var("noc", "NoC network interface", "interconnect_design", "noc_protocol", cond=when("noc")),
               var("arbitration", "Arbitration", "arbitration", cond=when("arbitration", "qos", "multi_port")),
               var("buffers", "Buffers and flow control", "buffering_flow_control", cond=when("multi_port", "noc")),
               var("control", "Control and CSRs", "control_logic_design"),
           ),
           outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),
        st("cdc-design", "CDC-safe crossings", "RTL", "rtl.cdc_design",
           depends_on=("microarchitecture",), when=when("cdc"), criticality=H, review=rv("rtl.review"),
           outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),  # M29
        st("power-intent", "Power intent (UPF)", "RTL", "rtl.power_intent",
           depends_on=("microarchitecture",), when=when("low_power"), criticality=H,
           review=rv("rtl.review"), outputs=("power_intent",), evidence=(REVIEWED,)),
        st("rtl-lint", "Lint and coding standards", "RTL", "rtl.lint",
           depends_on=("rtl-implementation", "cdc-design", "power-intent"), criticality=M,
           outputs=("lint_report",), evidence=(ran("Lint run with waivers dispositioned", "lint.run"),)),
        st("rtl-quality", "RTL quality and synthesis awareness", "RTL", "rtl.quality",
           depends_on=("rtl-lint",), skills=("coding_standards",), criticality=H, review=rv("rtl.review", Level.TECH_LEAD),
           gate="gate.rtl", outputs=("quality_report",), evidence=(REVIEWED,)),
        st("dv-plan", "Verification plan", "Verification", "dv.plan",
           depends_on=("requirements", "microarchitecture"), criticality=H, review=rv("dv.review"),
           outputs=("verification_plan",), evidence=(REVIEWED,)),
        st("dv-environment", "UVM environment", "Verification", "dv.testbench",
           depends_on=("dv-plan",), skills=("uvm",), criticality=H, review=rv("dv.review"),
           outputs=("testbench",), evidence=(REVIEWED, dv_ran("Environment smoke test runs", "simulator.run", "test.run"))),
        st("vip", "Verification IP integration", "Verification", "dv.vip",
           depends_on=("dv-plan",), when=when("axi", "chi", "pcie"),
           variants=(
               var("axi", "AXI VIP", "axi", cond=when("axi")),
               var("chi", "CHI VIP", "chi", cond=when("chi")),
               var("pcie", "PCIe VIP", "pcie", cond=when("pcie")),
           ),
           criticality=M, review=rv("dv.review"), outputs=("vip_configuration",), evidence=(REVIEWED,)),
        st("directed-tests", "Directed tests", "Verification", "dv.directed_tests",
           depends_on=("dv-environment", "vip", "rtl-implementation"), criticality=M, review=rv("dv.review"),
           outputs=("tests",), evidence=(REVIEWED, dv_ran("Directed tests executed", "test.run"))),
        st("random-tests", "Constrained-random tests", "Verification", "dv.random_tests",
           depends_on=("dv-environment", "vip", "rtl-implementation"), criticality=M, review=rv("dv.review"),
           outputs=("tests",), evidence=(REVIEWED, dv_ran("Random tests executed", "test.run", "regression.run"))),
        st("assertions", "Assertions", "Verification", "dv.assertions",
           depends_on=("dv-plan", "microarchitecture"), criticality=H, review=rv("dv.review"),
           variants=(
               var("axi", "AXI protocol assertions", "axi", "sva", cond=when("axi")),
               var("noc", "NoC protocol assertions", "noc_protocol", "sva", cond=when("noc")),
               var("intent", "Design-intent assertions", "sva"),
           ),
           outputs=("assertions",), evidence=(REVIEWED,)),
        st("coverage", "Coverage closure", "Verification", "dv.coverage",
           depends_on=("directed-tests", "random-tests", "assertions"), skills=("functional_coverage",), criticality=H, review=rv("dv.review"),
           outputs=("coverage_report",), evidence=(REVIEWED, dv_ran("Merged coverage report", "coverage.read"))),
        st("regression", "Regression", "Verification", "dv.regression",
           depends_on=("directed-tests", "random-tests", "assertions"), criticality=H, review=rv("dv.review"),
           outputs=("regression_report",),
           evidence=(dv_ran("Regression results, failures triaged through VeriTriage", "regression.run"),)),
        st("formal", "Formal property verification", "Formal", "formal.prove",
           depends_on=("assertions", "rtl-implementation"), skills=("formal_verification",), criticality=H, review=rv("formal.review"),
           outputs=("formal_report",), evidence=(REVIEWED, ran("Proof results with vacuity and bounds", "formal.run"))),
        st("cdc-verification", "CDC / RDC verification", "CDC/RDC", "cdc.verify",
           depends_on=("rtl-lint",), when=when("cdc"), criticality=H, review=rv("cdc.review"),
           outputs=("cdc_report",), evidence=(REVIEWED, ran("CDC/RDC analysis with waivers reviewed", "cdc.run"))),
        st("security-verification", "Security verification", "Verification", "secver.verify",
           depends_on=("rtl-implementation", "security-architecture"), when=when("security"), criticality=H,
           review=rv("security.review"), outputs=("security_verification_report",), evidence=(REVIEWED,)),
        st("timing-constraints", "Timing constraints", "Implementation", "sta.constraints",
           depends_on=("microarchitecture",), criticality=M, review=rv("sta.review"),
           outputs=("constraints",), evidence=(REVIEWED,)),
        st("synthesis", "Synthesis", "Implementation", "synth.run",
           depends_on=("rtl-quality", "timing-constraints"), criticality=M,
           outputs=("netlist", "synthesis_report"), evidence=(ran("Synthesis QoR report", "synth.run"),)),
        st("sta", "Static timing analysis", "Implementation", "sta.analyze",
           depends_on=("synthesis",), criticality=H, review=rv("sta.review"), gate="gate.implementation",
           outputs=("timing_report",), evidence=(REVIEWED, ran("Timing report across corners", "sta.run"))),
        st("power-analysis", "Power analysis", "Implementation", "power.analyze",
           depends_on=("synthesis",), when=when("low_power"), criticality=M,
           outputs=("power_report",), evidence=(ran("Power report with stated activity", "power.run"),)),
        st("dft", "DFT insertion", "Implementation", "dft.insert",
           depends_on=("rtl-quality",), when=when("dft"), criticality=M, review=rv("dft.review"),
           outputs=("dft_netlist",), evidence=(REVIEWED,)),
        st("documentation", "IP documentation", "Documentation", "doc.write",
           depends_on=("microarchitecture", "rtl-quality"), criticality=M, review=rv("doc.review"),
           variants=(
               var("integration", "Integration guide", "user_documentation"),
               var("user", "User manual", "user_documentation"),
           ),
           outputs=("document",), evidence=(REVIEWED,)),
        st("register-docs", "Register reference", "Documentation", "doc.registers",
           depends_on=("rtl-quality",), when=when("registers"), criticality=M, review=rv("doc.review"),
           outputs=("register_doc",), evidence=(REVIEWED,)),
        st("driver", "Reference driver", "Software", "sw.driver",
           depends_on=("rtl-quality",), when=when("registers", "firmware"), criticality=M,
           review=rv("sw.review"), outputs=("driver",), evidence=(REVIEWED,)),
        st("verification-signoff", "Verification closure", "Signoff", "dv.closure",
           depends_on=("coverage", "regression", "formal", "cdc-verification", "security-verification"),
           skills=("verification_signoff",), criticality=C, review=rv("dv.review", Level.STAFF), gate="gate.verification",
           outputs=("verification_closure_report",),
           evidence=(REVIEWED, dv_ran("Coverage, regression, and formal evidence", "coverage.read", "regression.run", "formal.run"))),
        st("integration", "IP integration and packaging", "Integration", "rtl.integrate",
           depends_on=("rtl-quality", "documentation", "register-docs"), criticality=M,
           review=rv("rtl.review"), outputs=("ip_package",), evidence=(REVIEWED,)),
        st("traceability", "Traceability audit", "Signoff", "quality.traceability",
           depends_on=("verification-signoff", "sta", "integration"), criticality=H,
           review=rv("quality.design_review"),
           outputs=("traceability_matrix",), evidence=(documented("Requirement-to-evidence matrix"),)),
        st("release", "Release", "Signoff", "release.manage",
           depends_on=("traceability", "driver", "power-analysis", "dft"), criticality=C,
           review=rv("req.review"), gate="gate.release", outputs=("release_record",),
           evidence=(REVIEWED,)),
    ),
)

# --- 2. Feature addition to an existing design --------------------------------------

FEATURE_ADDITION = WorkflowTemplate(
    id="feature-addition",
    name="Feature addition",
    description="Add a feature to an existing design without regressing it.",
    intents=("feature_addition",),
    stages=(
        st("requirements-delta", "Feature requirements", "Requirements", "req.analyze", criticality=H,
           review=rv("req.review"), outputs=("requirements_spec",), evidence=(REVIEWED,)),
        st("impact", "Change impact analysis", "Architecture", "rtl.impact", depends_on=("requirements-delta",),
           criticality=H, review=rv("arch.review"), outputs=("impact_analysis",), evidence=(REVIEWED,)),
        st("qos-architecture", "QoS architecture", "Architecture", "arch.interconnect",
           depends_on=("impact",), when=when("qos"), skills=("qos_architecture",), criticality=H,
           review=rv("arch.review"), outputs=("qos_architecture",), evidence=(REVIEWED,)),
        st("performance-model", "Performance model", "Architecture", "arch.performance",
           depends_on=("impact",), when=when("qos", "performance"), criticality=M,
           review=rv("arch.review"), outputs=("performance_model",), evidence=(REVIEWED,)),
        st("microarchitecture", "Microarchitecture update", "Architecture", "arch.microarchitecture",
           depends_on=("impact", "qos-architecture", "performance-model"), criticality=C,
           review=rv("arch.review", Level.STAFF), gate="gate.architecture",
           outputs=("microarchitecture_spec",), evidence=(REVIEWED,)),
        st("rtl-change", "RTL change", "RTL", "rtl.implement", depends_on=("microarchitecture",), criticality=H,
           review=rv("rtl.review"),
           variants=(
               var("arbitration", "Arbitration", "arbitration", cond=when("arbitration", "qos")),
               var("noc", "Router datapath and flow control", "interconnect_design", cond=when("noc")),
               var("control", "Control and CSRs", "control_logic_design"),
           ),
           outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),
        st("rtl-lint", "Lint", "RTL", "rtl.lint", depends_on=("rtl-change",),
           outputs=("lint_report",), evidence=(ran("Lint run", "lint.run"),)),
        st("dv-plan", "Verification plan update", "Verification", "dv.plan", depends_on=("microarchitecture",),
           criticality=H, review=rv("dv.review"), outputs=("verification_plan",), evidence=(REVIEWED,)),
        st("tests", "New feature tests", "Verification", "dv.random_tests", depends_on=("dv-plan", "rtl-change"),
           skills=("uvm",), criticality=M, review=rv("dv.review"), outputs=("tests",),
           evidence=(REVIEWED, dv_ran("Feature tests executed", "test.run", "regression.run"))),
        st("assertions", "Feature assertions", "Verification", "dv.assertions",
           depends_on=("dv-plan",), skills=("sva",), criticality=H, review=rv("dv.review"),
           outputs=("assertions",), evidence=(REVIEWED,)),
        st("formal", "Formal proof of fairness and liveness", "Formal", "formal.prove",
           depends_on=("assertions", "rtl-change"), when=when("arbitration", "qos"), criticality=H,
           review=rv("formal.review"), outputs=("formal_report",), evidence=(REVIEWED, ran("Proof results", "formal.run"))),
        st("regression", "Full regression (no regressions allowed)", "Verification", "dv.regression",
           depends_on=("tests", "rtl-lint"), criticality=H, review=rv("dv.review"), outputs=("regression_report",),
           evidence=(dv_ran("Regression results with failures triaged", "regression.run"),)),
        st("coverage", "Coverage closure", "Verification", "dv.coverage", depends_on=("regression", "assertions"),
           criticality=H, review=rv("dv.review"), gate="gate.verification", outputs=("coverage_report",),
           evidence=(REVIEWED, dv_ran("Merged coverage", "coverage.read"))),
        st("timing", "Timing impact check", "Implementation", "sta.analyze", depends_on=("rtl-lint",),
           criticality=M, review=rv("sta.review"), outputs=("timing_report",), evidence=(REVIEWED, ran("Timing report", "sta.run"))),
        st("docs", "Documentation update", "Documentation", "doc.write", depends_on=("microarchitecture",),
           criticality=L, review=rv("doc.review"), outputs=("document",), evidence=(REVIEWED,)),
        st("merge", "Merge to mainline", "Integration", "scm.merge",
           depends_on=("coverage", "formal", "timing", "docs"), owner_from="rtl-change", criticality=H,
           review=rv("rtl.review", Level.TECH_LEAD),
           gate="gate.rtl", outputs=("merge_record",), evidence=(REVIEWED,)),
    ),
)

# --- 3. Parameter change ------------------------------------------------------------

PARAMETER_CHANGE = WorkflowTemplate(
    id="parameter-change",
    name="Parameter change",
    description="Change a design parameter (width, depth, ports) and re-establish correctness.",
    intents=("parameter_change",),
    stages=(
        st("impact", "Change impact analysis", "Architecture", "rtl.impact", criticality=H,
           review=rv("arch.review"), outputs=("impact_analysis",), evidence=(REVIEWED,)),
        st("interface-update", "Interface specification update", "Architecture", "arch.interface",
           depends_on=("impact",), variants=_PROTOCOL_VARIANTS, criticality=H, review=rv("arch.review"),
           outputs=("interface_spec",), evidence=(REVIEWED,)),
        st("microarchitecture", "Microarchitecture update", "Architecture", "arch.microarchitecture",
           depends_on=("interface-update",), criticality=H, review=rv("arch.review", Level.STAFF),
           gate="gate.architecture", outputs=("microarchitecture_spec",), evidence=(REVIEWED,)),
        st("rtl-change", "RTL change", "RTL", "rtl.implement", depends_on=("microarchitecture",), criticality=H,
           review=rv("rtl.review"),
           variants=(
               var("datapath", "Datapath width", "datapath_design"),
               var("buffers", "Buffers and storage", "buffering_flow_control"),
               var("axi", "AXI interface", "axi", cond=when("axi")),
           ),
           outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),  # M29
        st("rtl-lint", "Lint", "RTL", "rtl.lint", depends_on=("rtl-change",), outputs=("lint_report",),
           evidence=(ran("Lint run", "lint.run"),)),
        st("cdc-recheck", "CDC re-check", "CDC/RDC", "cdc.verify", depends_on=("rtl-lint",), when=when("cdc"),
           criticality=H, review=rv("cdc.review"), outputs=("cdc_report",), evidence=(REVIEWED, ran("CDC run", "cdc.run"))),
        st("tb-update", "Testbench and VIP reconfiguration", "Verification", "dv.testbench",
           depends_on=("interface-update",), skills=("uvm",), criticality=M, review=rv("dv.review"),
           outputs=("testbench",), evidence=(REVIEWED,)),
        st("regression", "Full regression", "Verification", "dv.regression", depends_on=("tb-update", "rtl-lint"),
           criticality=H, review=rv("dv.review"), outputs=("regression_report",), evidence=(dv_ran("Regression results", "regression.run"),)),
        st("coverage", "Coverage at new width", "Verification", "dv.coverage", depends_on=("regression",),
           criticality=H, review=rv("dv.review"), gate="gate.verification", outputs=("coverage_report",),
           evidence=(REVIEWED, dv_ran("Merged coverage", "coverage.read"))),
        st("timing", "Timing and area re-check", "Implementation", "sta.analyze", depends_on=("rtl-lint",),
           criticality=H, review=rv("sta.review"), outputs=("timing_report",), evidence=(REVIEWED, ran("Timing report", "sta.run"))),
        st("docs", "Documentation update", "Documentation", "doc.write", depends_on=("microarchitecture",),
           criticality=L, review=rv("doc.review"), outputs=("document",), evidence=(REVIEWED,)),
        st("merge", "Merge to mainline", "Integration", "scm.merge",
           depends_on=("coverage", "cdc-recheck", "timing", "docs"), owner_from="rtl-change", criticality=H,
           review=rv("rtl.review", Level.TECH_LEAD), gate="gate.rtl", outputs=("merge_record",),
           evidence=(REVIEWED,)),
    ),
)

# --- 4. RTL change ------------------------------------------------------------------

RTL_CHANGE = WorkflowTemplate(
    id="rtl-change",
    name="RTL change",
    description="Impact analysis, targeted verification, regression, review, merge.",
    intents=("rtl_change",),
    stages=(
        st("impact", "Change impact analysis", "RTL", "rtl.impact", criticality=M, review=rv("rtl.review"),
           outputs=("impact_analysis",), evidence=(REVIEWED,)),
        st("change", "RTL change", "RTL", "rtl.implement", depends_on=("impact",), criticality=H,
           review=rv("rtl.review"), outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),
        st("targeted", "Targeted verification", "Verification", "dv.directed_tests", depends_on=("change",),
           criticality=M, review=rv("dv.review"), outputs=("tests",), evidence=(REVIEWED, dv_ran("Targeted tests", "test.run"))),
        st("regression", "Regression", "Verification", "dv.regression", depends_on=("targeted",), criticality=H,
           review=rv("dv.review"), outputs=("regression_report",), evidence=(dv_ran("Regression results", "regression.run"),)),
        st("merge", "Review and merge", "Integration", "scm.merge", depends_on=("regression",), owner_from="change",
           criticality=H,
           review=rv("rtl.review", Level.TECH_LEAD), gate="gate.rtl", outputs=("merge_record",),
           evidence=(REVIEWED,)),
    ),
)

# --- 5. Regression investigation ----------------------------------------------------

REGRESSION_INVESTIGATION = WorkflowTemplate(
    id="regression-investigation",
    name="Regression investigation",
    description="Triage with VeriTriage, establish a root cause, branch to the right fix, prove it.",
    intents=("regression_investigation",),
    stages=(
        st("triage", "Failure triage (VeriTriage)", "Debug", "debug.triage", criticality=M,
           outputs=("triage_report",),
           evidence=(EvidenceRequirement(description="VeriTriage investigation of the failing artifacts",
                                         accepts=(K.VERITRIAGE_SESSION,), tools=("veritriage.investigate",)),)),
        st("change-correlation", "Correlate with recent RTL commits", "Debug", "rtl.impact",
           depends_on=("triage",), when=when("recent_change"), criticality=M, outputs=("impact_analysis",),
           evidence=(documented("Commit range and touched modules"),)),
        st("root-cause", "Root-cause analysis", "Debug", "debug.root_cause",
           depends_on=("triage", "change-correlation"), skills=("root_cause_analysis",), criticality=H, review=rv("debug.review"),
           outcomes=("rtl_bug", "testbench_bug", "infrastructure", "spec_ambiguity"),
           outputs=("root_cause_analysis",), evidence=(REVIEWED,)),
        st("rtl-fix", "RTL fix", "Fix", "rtl.implement", depends_on=("root-cause",),
           branch=("root-cause", "rtl_bug"), criticality=H, review=rv("rtl.review"),
           outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),  # M29
        st("tb-fix", "Testbench fix", "Fix", "dv.testbench", depends_on=("root-cause",),
           branch=("root-cause", "testbench_bug"), criticality=M, review=rv("dv.review"),
           outputs=("testbench",), evidence=(REVIEWED,)),
        st("infra-fix", "Infrastructure fix", "Fix", "infra.regression", depends_on=("root-cause",),
           branch=("root-cause", "infrastructure"), criticality=M, outputs=("regression_infrastructure",),
           evidence=(ran("Infrastructure change verified", "farm.submit", "ci.configure"),)),
        st("spec-clarification", "Specification clarification", "Fix", "req.analyze", depends_on=("root-cause",),
           branch=("root-cause", "spec_ambiguity"), criticality=H, review=rv("req.review"),
           outputs=("requirements_spec",), evidence=(REVIEWED,)),
        st("verify-fix", "Re-run and confirm the fix", "Verification", "dv.regression",
           depends_on=("rtl-fix", "tb-fix", "infra-fix", "spec-clarification"), criticality=H,
           review=rv("dv.review"), outputs=("regression_report",),
           evidence=(dv_ran("Failing test passes; no new failures in regression", "regression.run", "test.run"),),
           on_failure=OnFailure.RETRY_THEN_ESCALATE, max_retries=2),
    ),
)

# --- 6. Verification signoff preparation --------------------------------------------

SIGNOFF_PREPARATION = WorkflowTemplate(
    id="signoff-preparation",
    name="Verification signoff preparation",
    description="Assemble and audit the evidence that verification is complete.",
    intents=("signoff_preparation",),
    stages=(
        st("plan-audit", "Plan-to-requirement audit", "Signoff", "quality.traceability", criticality=H,
           review=rv("dv.review"), outputs=("traceability_matrix",), evidence=(documented("Requirement-to-plan matrix"),)),
        st("regression-health", "Regression health (VeriTriage)", "Verification", "debug.triage", criticality=H,
           review=rv("debug.review"), outputs=("triage_report",),
           evidence=(EvidenceRequirement(description="Every open failure investigated",
                                         accepts=(K.VERITRIAGE_SESSION, K.HUMAN_ATTESTATION),
                                         tools=("veritriage.investigate",)),)),
        st("coverage-closure", "Coverage closure and exclusions", "Verification", "dv.coverage",
           depends_on=("plan-audit",), skills=("functional_coverage",), criticality=H, review=rv("dv.review"), outputs=("coverage_report",),
           evidence=(REVIEWED, dv_ran("Merged coverage with reviewed exclusions", "coverage.read"))),
        st("formal-closure", "Formal closure", "Formal", "formal.prove", criticality=H, review=rv("formal.review"),
           outputs=("formal_report",), evidence=(REVIEWED, ran("Proof status with bounds", "formal.run"))),
        st("cdc-closure", "CDC / RDC closure", "CDC/RDC", "cdc.verify", when=when("cdc"), criticality=H,
           review=rv("cdc.review"), outputs=("cdc_report",), evidence=(REVIEWED, ran("Clean or waived CDC", "cdc.run"))),
        st("waiver-audit", "Waiver audit", "Signoff", "quality.audit",
           depends_on=("coverage-closure", "formal-closure", "cdc-closure"), criticality=H,
           review=rv("quality.design_review"), outputs=("audit_report",), evidence=(documented("Every waiver has an approved rationale"),)),
        st("closure-report", "Verification closure report", "Signoff", "dv.closure",
           depends_on=("regression-health", "waiver-audit"), skills=("verification_signoff",), criticality=C, review=rv("dv.review", Level.STAFF),
           gate="gate.verification", outputs=("verification_closure_report",),
           evidence=(REVIEWED, dv_ran("Regression, coverage, and formal evidence", "coverage.read", "regression.run", "formal.run"))),
    ),
)

# --- 7. Timing closure --------------------------------------------------------------

TIMING_CLOSURE = WorkflowTemplate(
    id="timing-closure",
    name="Timing closure",
    description="STA analysis, root-cause classification, the right fix, re-analysis.",
    intents=("timing_closure",),
    stages=(
        st("sta-analysis", "STA analysis", "Implementation", "sta.analyze", criticality=H,
           review=rv("sta.review"), outputs=("timing_report",), evidence=(ran("Timing report with failing paths", "sta.run"),)),
        st("classify", "Root cause: RTL, constraint, or physical", "Implementation", "sta.analyze",
           depends_on=("sta-analysis",), criticality=H, review=rv("sta.review"),
           outcomes=("rtl_path", "constraint_issue", "physical_implementation"),
           outputs=("root_cause_analysis",), evidence=(REVIEWED,)),
        st("rtl-fix", "RTL restructuring", "Fix", "rtl.implement", depends_on=("classify",),
           branch=("classify", "rtl_path"), criticality=H, review=rv("rtl.review"),
           skills=("pipeline_design",), outputs=("rtl_source", "testbench"), evidence=(REVIEWED, *RTL_GATES)),  # M29
        st("constraint-fix", "Constraint correction", "Fix", "sta.constraints", depends_on=("classify",),
           branch=("classify", "constraint_issue"), criticality=H, review=rv("sta.review"),
           outputs=("constraints",), evidence=(REVIEWED,)),
        st("pd-fix", "Physical implementation fix", "Fix", "pd.place_route", depends_on=("classify",),
           branch=("classify", "physical_implementation"), criticality=H, review=rv("pd.review"),
           outputs=("layout",), evidence=(REVIEWED,)),
        st("reanalysis", "Re-analysis", "Implementation", "sta.analyze",
           depends_on=("rtl-fix", "constraint-fix", "pd-fix"), criticality=H, review=rv("sta.review"),
           gate="gate.implementation", outputs=("timing_report",),
           evidence=(REVIEWED, ran("Clean timing report", "sta.run"))),
    ),
)

# --- 8. Small, self-contained block design (M23) -------------------------------------

BLOCK_DESIGN = WorkflowTemplate(
    id="block-design",
    name="Block design",
    description="A small, self-contained block (register block, FIFO, arbiter): specified, "
                "microarchitected, and implemented from approved inputs, with RTL lint-clean, "
                "simulated, synthesized, and (when the seat writes a proof setup) formally proven "
                "before review.",
    intents=("block_design",),
    stages=(
        st("requirements", "Requirements specification", "Requirements", "req.analyze", criticality=M,
           review=rv("req.review"), outputs=("requirements_spec",), evidence=(REVIEWED,)),
        st("interface-spec", "Interface specification", "Architecture", "arch.interface",
           depends_on=("requirements",), criticality=H, review=rv("arch.review"),
           outputs=("interface_spec",), evidence=(REVIEWED,)),
        st("microarchitecture", "Microarchitecture", "Architecture", "arch.microarchitecture",
           depends_on=("interface-spec",), criticality=H, review=rv("arch.review"),
           outputs=("microarchitecture_spec",), evidence=(REVIEWED,)),
        # M29: when the request asks for a verification plan, it is written from the approved spec,
        # checked against it before review, and recorded on approval. Nothing waits on it: its items
        # bind to the testbench whenever that file is recorded.
        st("dv-plan", "Verification plan", "Verification", "dv.plan",
           depends_on=("interface-spec",), when=when("verification_plan"), criticality=M, review=rv("dv.review"),
           outputs=("verification_plan",),
           evidence=(REVIEWED,
                     checked("The plan covers every requirement of the approved interface spec", "vplan.check",
                             FileInput(param="plan", kinds=("verification_plan",)),
                             FileInput(param="spec", kinds=("interface_spec",), upstream=True)))),
        st("rtl-implementation", "RTL implementation and testbench", "RTL", "rtl.implement",
           depends_on=("microarchitecture",), criticality=H, review=rv("rtl.review"),
           outputs=("rtl_source", "testbench"),
           evidence=(REVIEWED,
                     checked("Lint-clean under the RTL lint rules", "lint.run",
                             FileInput(param="sources", kinds=("rtl_source",))),
                     checked("Self-checking simulation passes", "simulator.run",
                             FileInput(param="sources", kinds=("rtl_source", "testbench")),
                             FileInput(param="top", kinds=("testbench",), entry=True)),
                     # M26: every block synthesizes with no latches; formal runs when the seat writes a .sby.
                     checked("Synthesizes with Yosys, with no latches", "synth.run",
                             FileInput(param="sources", kinds=("rtl_source",)),
                             FileInput(param="top", kinds=("rtl_source",), entry=True),
                             params=(("max_latches", "0"),)),
                     checked("Formal properties are proven", "formal.run",
                             FileInput(param="sby", kinds=("formal_spec",)),
                             FileInput(param="sources", kinds=("rtl_source",)),
                             when_produced=("formal_spec",)),
                     NOT_VACUOUS)),  # M27
        # M25: when the request asks for test (DFT, scan chains), the scan netlist goes to review
        # only after real rule checks and a real chain simulation over it.
        st("dft", "Scan insertion", "Implementation", "dft.insert",
           depends_on=("rtl-implementation",), when=when("dft"), skills=("scan_design",), criticality=M,
           review=rv("dft.review"),
           outputs=("dft_netlist",),
           evidence=(REVIEWED,
                     checked("Testability rules hold and every flop is on the chain", "dft.check",
                             FileInput(param="sources", kinds=("dft_netlist",)),
                             FileInput(param="top", kinds=("dft_netlist",), entry=True)),
                     checked("The scan chain shifts and captures in simulation", "dft.scan_sim",
                             FileInput(param="sources", kinds=("dft_netlist",)),
                             FileInput(param="top", kinds=("dft_netlist",), entry=True)),
                     # M27: stuck-at test coverage, measured by fault simulation, before review.
                     checked("ATPG reaches 90% stuck-at test coverage in fault simulation", "dft.atpg",
                             FileInput(param="sources", kinds=("dft_netlist",)),
                             FileInput(param="top", kinds=("dft_netlist",), entry=True),
                             params=(("min_test_coverage", "90"),)),
                     # M29: at-speed test asks for transition coverage too (launch on capture).
                     checked("Transition ATPG reaches 80% test coverage in fault simulation", "dft.atpg_transition",
                             FileInput(param="sources", kinds=("dft_netlist",)),
                             FileInput(param="top", kinds=("dft_netlist",), entry=True),
                             params=(("min_test_coverage", "80"),), when=when("at_speed")))),
        # M29: a block with memory gets March C- on every memory of the approved RTL before review.
        st("mbist", "Memory BIST", "Implementation", "dft.mbist",
           depends_on=("rtl-implementation",), when=when("memory"), skills=("mbist",), criticality=M,
           review=rv("dft.review"), outputs=("mbist_configuration",),
           evidence=(REVIEWED,
                     checked("March C- passes on every memory in the approved RTL", "dft.mbist",
                             FileInput(param="sources", kinds=("rtl_source",), upstream=True)))),
        st("firmware", "Driver and driver tests", "Software", "fw.driver",
           depends_on=("interface-spec", "rtl-implementation"), when=when("firmware"), criticality=M,
           review=rv("sw.review"), outputs=("driver", "driver_test"),
           evidence=(REVIEWED,
                     checked("Driver builds clean under strict C flags", "fw.build",
                             FileInput(param="sources", kinds=("driver",))),
                     checked("Driver tests pass against the approved RTL", "fw.test",
                             FileInput(param="sources", kinds=("driver", "driver_test")),
                             FileInput(param="rtl", kinds=("rtl_source",), upstream=True)),
                     # M27: when the request names RISC-V, the same tests also run as a bare-metal
                     # RV32I image on a RISC-V core whose loads and stores reach the approved RTL.
                     # M29: the image's code (text) must fit a budget: a quarter of the SoC's RAM.
                     checked("Driver and tests cross-build for bare-metal RV32I", "fw.cross_build",
                             FileInput(param="sources", kinds=("driver", "driver_test")), when=when("riscv"),
                             params=(("max_text_bytes", "16384"),)),
                     checked("Driver tests pass on a RISC-V core against the approved RTL", "fw.soc_test",
                             FileInput(param="sources", kinds=("driver", "driver_test")),
                             FileInput(param="rtl", kinds=("rtl_source",), upstream=True), when=when("riscv")))),
    ),
)

# --- 9. Physical implementation (M25) ---------------------------------------------------

PHYSICAL_IMPLEMENTATION = WorkflowTemplate(
    id="physical-implementation",
    name="Physical implementation",
    description="Constraints, Liberty-mapped synthesis, floorplan, power grid, place, clock tree, route, and "
                "metal fill, then DRC and LVS, and STA signoff on extracted parasitics across corners. "
                "The PDK is a task input; a machine without the tools refuses the runs.",
    intents=("physical_implementation",),
    stages=(
        st("timing-constraints", "Timing constraints (SDC)", "Implementation", "sta.constraints", criticality=M,
           review=rv("sta.review"), outputs=("constraints",), evidence=(REVIEWED,)),
        st("synthesis", "Synthesis to the target library", "Implementation", "synth.run",
           depends_on=("timing-constraints",), criticality=M, outputs=("netlist", "synthesis_report"),
           evidence=(ran("Netlist mapped to the target library", "synth.run"),)),
        st("floorplan", "Floorplan", "Implementation", "pd.floorplan", depends_on=("synthesis",), criticality=M,
           review=rv("pd.review"), outputs=("floorplan",),
           evidence=(REVIEWED, ran("Floorplan run with utilization reported", "pnr.run"))),
        # M29: the power grid, a clock tree, and extracted parasitics (docs/PD_SIGNOFF.md). A run counts
        # only if made with these limits, and a limit on a metric the run never reported fails it.
        st("power-grid", "Power grid", "Implementation", "pd.power_plan", depends_on=("floorplan",), criticality=M,
           review=rv("pd.review"), outputs=("power_grid",),
           evidence=(REVIEWED, ran("Power grid built, with every cell supply pin connected", "pnr.run",
                                   params=(("max_unconnected_supply_pins", "0"),)))),
        st("place-route", "Placement, clock tree, and routing", "Implementation", "pd.place_route",
           depends_on=("floorplan", "power-grid"), criticality=H, review=rv("pd.review"), outputs=("layout",),
           evidence=(REVIEWED, ran("Placed, clock tree built, and routed, with clock skew, DRC count, and "
                                   "wirelength reported", "pnr.run",
                                   params=(("max_drc_violations", "0"), ("max_unconnected_supply_pins", "0"))))),
        # M34: DRC and LVS with the PDK's decks on the filled layout, and timing on at least three corners
        # (docs/PD_FINAL.md). As in M29, a run counts only if made with these limits.
        st("physical-verification", "DRC and LVS", "Signoff", "pd.signoff_checks", depends_on=("place-route",),
           criticality=H, review=rv("pd.review"), outputs=("physical_verification_report",),
           evidence=(REVIEWED, ran("DRC and LVS clean on the filled layout, with the PDK's decks", "pv.run",
                                   params=(("max_drc_violations", "0"), ("max_lvs_mismatches", "0"),
                                           ("min_fill_shapes", "1"))))),
        st("sta-signoff", "STA signoff", "Signoff", "sta.analyze", depends_on=("place-route", "physical-verification"),
           criticality=H, review=rv("sta.review"), gate="gate.implementation", outputs=("timing_report",),
           evidence=(REVIEWED, ran("Signoff timing on the routed netlist with extracted parasitics (SPEF), "
                                   "across slow, typical, and fast corners", "sta.run",
                                   params=(("max_unannotated_nets", "0"), ("min_timing_corners", "3"))))),
    ),
)

WORKFLOWS: list[WorkflowTemplate] = [
    NEW_IP,
    FEATURE_ADDITION,
    PARAMETER_CHANGE,
    RTL_CHANGE,
    REGRESSION_INVESTIGATION,
    SIGNOFF_PREPARATION,
    TIMING_CLOSURE,
    BLOCK_DESIGN,
    PHYSICAL_IMPLEMENTATION,
]
