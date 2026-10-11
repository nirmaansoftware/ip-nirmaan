"""The requirement vocabulary: how IP Nirmaan reads a request.

Declared, not learned. Every intent, feature, and parameter the organization
recognizes is a pattern here, so an analysis can always say exactly which
phrase produced which conclusion, and a request nobody declared is reported as
unrecognized rather than guessed at. A language model can later propose
analyses; it will be checked against this vocabulary, not replace it.
"""

from __future__ import annotations

from nirmaan.models import AssumptionRule, Condition, FeatureRule, IntentRule, ParameterRule

INTENTS: list[IntentRule] = [
    IntentRule(intent="regression_investigation", priority=10,
               description="Something that passed now fails.",
               patterns=(r"\bregression\b.*\b(fail\w*|broke\w*|break\w*)",
                         r"\b(investigate|debug|triage)\b.*\bfail\w*",
                         r"\btest\w* (started )?failing\b")),
    IntentRule(intent="timing_closure", priority=15, description="Timing is not met.",
               patterns=(r"\btiming violation", r"\b(setup|hold) (violation|slack)",
                         r"\bnegative slack\b", r"\bclose timing\b", r"\btiming closure\b")),
    IntentRule(intent="signoff_preparation", priority=20, description="Get an IP ready for signoff.",
               patterns=(r"\bsign-?off\b",)),
    IntentRule(intent="parameter_change", priority=30, description="Change a parameter of an existing design.",
               patterns=(r"\bchange\b.*\bfrom\b.*\bto\b",
                         r"\b(widen|narrow|increase|decrease|resize|double|halve)\b.*\b(width|depth|size|ports?)\b")),
    IntentRule(intent="feature_addition", priority=40, description="Add a capability to an existing design.",
               patterns=(r"\badd\b.*\b(to|into)\b.*\b(existing|current)\b",
                         r"\b(add|extend|enhance)\b.*\bto (an? |the )?(existing )?\w+ (router|bridge|controller|ip|block|fabric|interconnect)\b")),
    IntentRule(intent="rtl_change", priority=45, description="Change RTL.",
               patterns=(r"\b(rtl|design) (change|fix|update|modification)\b", r"\bmodify\b.*\brtl\b",
                         r"\bfix\b.*\b(bug|rtl)\b")),
    IntentRule(intent="physical_implementation", priority=50, description="Take a netlist to layout.",
               patterns=(r"\bplace[- ]and[- ]route\b", r"\bp&r\b", r"\bpnr\b",
                         r"\bphysical (design|implementation)\b")),
    IntentRule(intent="block_design", priority=55, description="Build a small, self-contained block.",
               patterns=(r"\b(create|build|design|develop|implement|write)\b.*"
                         r"\b(register (block|file|bank)|fifo|arbiter|counter)\b",
                         r"\b(create|build|design|develop|implement|write)\b.*"
                         r"\b(apb[34]?|axi4?[- ]?lite) (subordinate|slave|peripheral)\b")),
    IntentRule(intent="new_ip", priority=60, description="Build something new.",
               patterns=(r"\b(create|build|design|develop|implement|architect)\b.*\b(ip|bridge|controller|router|block|"
                         r"interconnect|fabric|core|engine|phy|interface|subsystem|accelerator)\b",)),
]

FEATURES: list[FeatureRule] = [
    FeatureRule(feature="axi", skills=("axi",), patterns=(r"\baxi\s*[345]?\b(?![- ]?stream)",), description="AMBA AXI"),
    FeatureRule(feature="axi_stream", skills=("axi_stream",), patterns=(r"\baxi[- ]?stream\b",)),
    FeatureRule(feature="ace", skills=("ace",), patterns=(r"\bace(-lite)?\b",)),
    FeatureRule(feature="chi", skills=("chi",), patterns=(r"\bchi\b",)),
    FeatureRule(feature="apb", skills=("apb",), patterns=(r"\bapb[34]?\b",)),
    FeatureRule(feature="ahb", skills=("ahb",), patterns=(r"\bahb\b",)),
    FeatureRule(feature="pcie", skills=("pcie",), patterns=(r"\bpci[- ]?e(xpress)?\b",)),
    FeatureRule(feature="cxl", skills=("cxl",), patterns=(r"\bcxl\b",)),
    FeatureRule(feature="ddr", skills=("ddr", "memory_controller_microarchitecture"), patterns=(r"\bl?pddr\d*\b|\bddr\d*\b",), implies=("memory_controller",)),
    FeatureRule(feature="memory_controller", skills=("memory_controller_microarchitecture",), patterns=(r"\bmemory controller\b",)),
    FeatureRule(feature="noc", skills=("noc_architecture", "noc_protocol", "interconnect_design"), patterns=(r"\bnoc\b", r"\bnetwork[- ]on[- ]chip\b"), description="Network-on-chip"),
    FeatureRule(feature="qos", skills=("qos_architecture", "arbitration"), patterns=(r"\bqos\b", r"\bquality[- ]of[- ]service\b"), implies=("arbitration",)),
    FeatureRule(feature="arbitration", skills=("arbitration",), patterns=(r"\barbitrat\w*", r"\barbiter\b")),
    FeatureRule(feature="multi_port", skills=("buffering_flow_control", "arbitration"), patterns=(r"\b\d+[- ]port\b", r"\bmulti[- ]?port\b")),
    FeatureRule(feature="configurable", patterns=(r"\bconfigurable\b", r"\bparameteri[sz]\w*")),
    FeatureRule(feature="cdc", skills=("cdc_design", "cdc_verification"), patterns=(r"\bcdc\b", r"\bclock[- ]domains?\b", r"\basync\w*\b",
                                         r"\b(multi|dual)[- ]clock\b")),
    FeatureRule(feature="single_clock", patterns=(r"\bsingle[- ]clock\b", r"\bone clock\b", r"\bfully synchronous\b")),
    FeatureRule(feature="low_power", skills=("low_power_design", "power_architecture"), patterns=(r"\blow[- ]power\b", r"\bpower[- ]gat\w*", r"\bretention\b", r"\bupf\b")),
    FeatureRule(feature="security", skills=("security_architecture", "security_verification"), patterns=(r"\bsecur\w*", r"\btrustzone\b", r"\bencrypt\w*", r"\bcrypto\w*")),
    FeatureRule(feature="registers", skills=("register_programming", "register_documentation"), patterns=(r"\bcsrs?\b", r"\bregisters?\b", r"\bregister map\b")),
    FeatureRule(feature="dft", skills=("dft_architecture",), patterns=(r"\bdft\b", r"\bscan chains?\b", r"\bmbist\b", r"\batpg\b")),
    # M29: at-speed test asks for transition-fault coverage; a memory in the block asks for memory BIST.
    FeatureRule(feature="at_speed", skills=("atpg",), implies=("dft",),
                patterns=(r"\bat[- ]speed\b", r"\btransition faults?\b", r"\bdelay (test|faults?)\b")),
    FeatureRule(feature="memory", skills=("mbist",),
                patterns=(r"\bs?rams?\b", r"\bmemory (arrays?|macros?|blocks?)\b", r"\bembedded memor(y|ies)\b",
                          r"\bmbist\b")),
    FeatureRule(feature="firmware", skills=("embedded_firmware", "device_drivers"), patterns=(r"\bfirmware\b", r"\bdrivers?\b")),
    FeatureRule(feature="riscv", patterns=(r"\brisc[- ]?v\b", r"\brv32\w*")),
    FeatureRule(feature="register_map", patterns=(r"\bregister maps?\b", r"\bregmaps?\b"),
                description="A register map as data, approved, then judging the RTL and the driver (M41)"),
    # M35: a request that asks for interrupts, or for bus errors to trap, makes the firmware gate require them.
    FeatureRule(feature="interrupts", patterns=(r"\binterrupts?\b", r"\birqs?\b")),
    FeatureRule(feature="bus_errors", patterns=(r"\bbus[- ]errors?\b", r"\bprecise traps?\b")),
    # M44: a request for a layout takes the block's approved RTL through physical design in the same project.
    FeatureRule(feature="layout", patterns=(r"(?<!register )(?<!memory )\blayouts?\b", r"\bgds(ii)?\b"),
                description="A layout of the block, from its approved RTL, in the same project (M44)"),
    FeatureRule(feature="verification_plan", patterns=(r"\bverification plan\b", r"\bv-?plan\b", r"\btest plan\b"),
                description="A verification plan, written and checked before the testbench (M29)"),
    FeatureRule(feature="performance", skills=("performance_modeling",), patterns=(r"\bbandwidth\b", r"\blatency\b", r"\bthroughput\b")),
    FeatureRule(feature="existing_design", patterns=(r"\bexisting\b", r"\bcurrent\b")),
    FeatureRule(feature="recent_change", skills=("change_impact_analysis", "regression_intelligence"), patterns=(r"\b(recent|latest|last)\b.*\b(commit|change|merge)\b",
                                                   r"\bintroduced by\b")),
    FeatureRule(feature="width_change", patterns=(r"\b(data|bus|address) width\b",)),
]

PARAMETERS: list[ParameterRule] = [
    ParameterRule(name="ports", patterns=(r"\b(\d+)[- ]port\b",)),
    ParameterRule(name="data_width", unit="bits",
                  patterns=(r"\b(\d+)[- ]bit data\b", r"\bdata width (?:of )?(\d+)\b", r"\b(\d+)[- ]bit datapath\b")),
    ParameterRule(name="address_width", unit="bits", patterns=(r"\b(\d+)[- ]bit address\b",)),
    ParameterRule(name="from_width", unit="bits", patterns=(r"\bfrom (\d+)[- ]?bits?\b",)),
    ParameterRule(name="to_width", unit="bits", patterns=(r"\bto (\d+)[- ]?bits?\b",)),
]

ASSUMPTIONS: list[AssumptionRule] = [
    AssumptionRule(
        id="clocking-unstated",
        applies_to_intents=("new_ip", "parameter_change", "feature_addition", "signoff_preparation"),
        when=Condition(none_of=("cdc", "single_clock")),
        assume_features=("cdc",),
        note="Clocking was not stated, so CDC/RDC work is planned conservatively: IP with "
             "multiple interfaces frequently crosses clock domains.",
        question="Do all interfaces share one clock? If so, CDC/RDC stages can be cancelled.",
    ),
    AssumptionRule(
        id="registers-unstated",
        applies_to_intents=("new_ip",),
        when=Condition(any_of=("configurable", "qos", "noc"), none_of=("registers",)),
        assume_features=("registers",),
        note="A configurable IP normally exposes control and status registers, so register "
             "documentation and a reference driver are planned.",
        question="Does the IP expose software-visible registers?",
    ),
    AssumptionRule(
        id="existing-design",
        applies_to_intents=("feature_addition", "parameter_change", "rtl_change"),
        when=Condition(none_of=("existing_design",)),
        assume_features=("existing_design",),
        note="The request modifies a design that already exists and is under regression.",
        question="Which design baseline (branch or tag) does this change start from?",
    ),
]
