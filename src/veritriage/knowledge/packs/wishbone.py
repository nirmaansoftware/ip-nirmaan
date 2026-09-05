"""Wishbone B4 Knowledge Pack.

Wishbone is deliberately small: a master raises CYC for the bus cycle and
STB for each phase, and the slave ends each phase with exactly one of ACK,
ERR or RTY. That single rule, plus the pipelined mode's STALL backpressure
and the CTI/BTE burst tags, accounts for nearly every Wishbone failure worth
a knowledge pack.
"""

from __future__ import annotations

from veritriage.knowledge.model import (
    Concept,
    DebugPlaybook,
    EvidenceClause,
    FailurePattern,
    KnowledgePack,
    PlaybookStep,
    ProtocolSignal,
    ProtocolState,
    Reference,
    StateMachine,
)
from veritriage.knowledge.registry import register_pack

_SPEC = "Wishbone B4 System-on-Chip Interconnect Specification (OpenCores)"


@register_pack
def wishbone_pack() -> KnowledgePack:
    return KnowledgePack(
        id="wishbone",
        name="Wishbone B4",
        version="1.0.0",
        domain="protocol",
        summary=(
            "Wishbone cycle framing, the exclusive ACK/ERR/RTY termination rule, "
            "pipelined STALL backpressure, and CTI/BTE burst tags."
        ),
        concepts=[
            Concept(
                id="wishbone.cycle",
                name="CYC and STB framing",
                summary=(
                    "CYC_O marks the whole bus cycle and must stay asserted for "
                    "its duration; STB_O marks each individual phase within it. "
                    "STB without CYC is meaningless, and dropping CYC before a "
                    "phase terminates abandons a transfer the slave still thinks "
                    "is live."
                ),
                markers=[r"\bwishbone\b", r"\bcyc\b", r"\bstb\b", r"bus cycle"],
                references=[
                    Reference(source=_SPEC, section="3.1.3", note="Cycle and strobe framing.")
                ],
            ),
            Concept(
                id="wishbone.termination",
                name="Exclusive cycle termination",
                summary=(
                    "A slave ends each phase with exactly one of ACK_I, ERR_I or "
                    "RTY_I. Asserting none hangs the master; asserting more than "
                    "one is a protocol violation that different masters resolve "
                    "differently, which makes it a portability bug as well."
                ),
                markers=[r"\back\b", r"\berr\b.*wishbone", r"\brty\b", r"terminat"],
                references=[
                    Reference(source=_SPEC, section="3.1.4", note="Termination signals are mutually exclusive.")
                ],
            ),
            Concept(
                id="wishbone.pipelined",
                name="Pipelined mode and STALL",
                summary=(
                    "In pipelined mode the slave throttles with STALL_I while the "
                    "master keeps issuing phases. Acknowledgements arrive later "
                    "and independently, so the count of ACKs must eventually equal "
                    "the count of accepted STBs; any drift is a lost or duplicated "
                    "transfer."
                ),
                markers=[r"\bstall\b", r"pipelined", r"outstanding"],
                references=[
                    Reference(source=_SPEC, section="3.1.5", note="Pipelined cycle behaviour.")
                ],
            ),
            Concept(
                id="wishbone.burst-tags",
                name="CTI and BTE burst tags",
                summary=(
                    "CTI_O declares the cycle type (classic, constant address, "
                    "incrementing, end-of-burst) and BTE_O the wrap size for "
                    "incrementing bursts. A burst that never emits the end-of-burst "
                    "tag leaves the slave's prefetch running."
                ),
                markers=[r"\bcti\b", r"\bbte\b", r"burst.*wishbone", r"end.of.burst"],
                references=[
                    Reference(source=_SPEC, section="4.2", note="Registered feedback bus cycles.")
                ],
            ),
        ],
        signals=[
            ProtocolSignal(name="CYC_O", role="bus cycle in progress"),
            ProtocolSignal(name="STB_O", role="phase strobe"),
            ProtocolSignal(name="ACK_I", role="normal termination"),
            ProtocolSignal(name="ERR_I", role="error termination"),
            ProtocolSignal(name="RTY_I", role="retry termination"),
            ProtocolSignal(name="STALL_I", role="pipelined backpressure"),
            ProtocolSignal(name="CTI_O", role="cycle type identifier"),
        ],
        state_machines=[
            StateMachine(
                id="wishbone.cycle",
                name="Wishbone bus cycle",
                states=[
                    ProtocolState(
                        name="Idle",
                        description="CYC low; no bus cycle in progress.",
                        markers=[r"wishbone idle", r"\bcyc\b.*(?:low|deassert)"],
                    ),
                    ProtocolState(
                        name="CycleOpen",
                        description="CYC asserted, the master owns the bus.",
                        markers=[r"\bcyc\b.*(?:assert|high)", r"bus cycle.*(?:start|open)"],
                    ),
                    ProtocolState(
                        name="PhaseActive",
                        description="STB asserted, waiting for a termination signal.",
                        markers=[r"\bstb\b.*(?:assert|high)", r"phase.*(?:active|pending)"],
                    ),
                    ProtocolState(
                        name="Stalled",
                        description="Pipelined slave asserting STALL; the phase is not yet accepted.",
                        markers=[r"\bstall\b.*(?:assert|high)", r"back.?pressure"],
                    ),
                    ProtocolState(
                        name="Terminated",
                        description="ACK, ERR or RTY ended the phase.",
                        markers=[r"\back\b.*(?:assert|seen|high)", r"terminat"],
                    ),
                ],
            ),
        ],
        patterns=[
            FailurePattern(
                id="wishbone.no-termination",
                name="Cycle never terminated",
                summary=(
                    "A Wishbone phase was strobed and the slave asserted none of "
                    "ACK, ERR or RTY, so the master waited on a termination that "
                    "never came until a timeout fired."
                ),
                required=[
                    EvidenceClause(
                        name="timeout or hang observed",
                        pattern=r"time[- ]?out|watchdog|hung|stuck|no progress",
                        must_fail=True,
                    ),
                    EvidenceClause(
                        name="Wishbone phase pending",
                        pattern=(
                            r"\bwishbone\b.*(?:pending|stall|wait|stuck|cycle)"
                            r"|\back\b.*(?:never|low|not asserted)"
                            r"|\bstb\b.*(?:pending|held|asserted)"
                        ),
                    ),
                ],
                typical_causes=[
                    "Address decodes into a hole no slave claims",
                    "Slave clock gated or held in reset during the cycle",
                    "Slave FSM waiting on an internal condition that never occurs",
                    "Master dropped CYC early, so the slave abandoned the response",
                ],
                ownership="design",
                suggested_signals=["CYC_O", "STB_O", "ACK_I", "ADR_O"],
                playbook_id="wishbone.hang",
                confidence_modifiers={"rtl_bug": 0.10},
                references=[
                    Reference(source=_SPEC, section="3.1.4", note="Every phase must be terminated.")
                ],
            ),
            FailurePattern(
                id="wishbone.err-ignored",
                name="ERR termination accepted as data",
                summary=(
                    "A phase terminated with ERR_I but the master or scoreboard "
                    "consumed the data bus as if it were a normal ACK. The real "
                    "defect is upstream of whatever mismatch is reported later."
                ),
                required=[
                    EvidenceClause(
                        name="Wishbone error termination observed",
                        pattern=(
                            r"\berr_i\b|\berr\b.*(?:terminat|assert).*wishbone"
                            r"|wishbone.*error (?:terminat|response)"
                            r"|bus error.*wishbone"
                        ),
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Access to an unmapped or protected region",
                    "Slave rejecting an access that is illegal in its current state",
                    "Testbench memory map out of sync with the interconnect decode",
                    "Master treating ERR and ACK through a shared termination path",
                ],
                ownership="testbench",
                suggested_signals=["ERR_I", "ADR_O", "DAT_I"],
                playbook_id="wishbone.err",
                confidence_modifiers={"testbench_issue": 0.08, "rtl_bug": 0.05},
                references=[Reference(source=_SPEC, section="3.1.4", note="ERR_I semantics.")],
            ),
            FailurePattern(
                id="wishbone.rty-livelock",
                name="Retry livelock",
                summary=(
                    "A slave asserted RTY repeatedly and the master kept "
                    "re-issuing the same phase, so the bus stayed busy while "
                    "making no forward progress. The simulation is not hung; it "
                    "is looping."
                ),
                required=[
                    EvidenceClause(
                        name="repeated retry observed",
                        pattern=(
                            r"\brty\b.*(?:repeat|again|loop|storm)"
                            r"|retry.*(?:loop|livelock|repeated|exceeded)"
                            r"|max(?:imum)? retr(?:y|ies)"
                        ),
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Slave resource that is never freed because the freeing agent is blocked",
                    "Arbiter starving the retrying master under a fixed priority scheme",
                    "Two masters retrying against each other over a shared resource",
                    "Master lacking any retry backoff or attempt limit",
                ],
                ownership="design",
                suggested_signals=["RTY_I", "CYC_O", "STB_O"],
                playbook_id="wishbone.rty",
                confidence_modifiers={"rtl_bug": 0.10, "infrastructure_issue": 0.04},
                references=[Reference(source=_SPEC, section="3.1.4", note="RTY_I semantics.")],
            ),
            FailurePattern(
                id="wishbone.cyc-stb-violation",
                name="CYC and STB framing violation",
                summary=(
                    "STB was asserted outside an open CYC, or CYC was withdrawn "
                    "while a phase was still awaiting termination. The two sides "
                    "now disagree about whether a transfer is in flight."
                ),
                required=[
                    EvidenceClause(
                        name="framing violation observed",
                        pattern=(
                            r"\bstb\b.*without.*\bcyc\b"
                            r"|\bcyc\b.*(?:deassert|dropped|withdrawn).*(?:before|during|mid)"
                            r"|(?:cyc|stb).*(?:protocol )?violation"
                        ),
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Master aborting a cycle on an internal error without unwinding the bus",
                    "Reset asserted mid-cycle on one side of the interface only",
                    "Bridge forwarding STB while gating CYC",
                    "Arbiter revoking the grant before the current phase terminated",
                ],
                ownership="design",
                suggested_signals=["CYC_O", "STB_O", "ACK_I"],
                playbook_id="wishbone.framing",
                confidence_modifiers={"rtl_bug": 0.12},
                references=[
                    Reference(source=_SPEC, section="3.1.3", note="CYC must frame every phase.")
                ],
            ),
        ],
        playbooks=[
            DebugPlaybook(
                id="wishbone.hang",
                name="Wishbone cycle hang",
                steps=[
                    PlaybookStep(
                        action="Capture CYC, STB and all three termination signals at the stall",
                        signals=["CYC_O", "STB_O", "ACK_I", "ERR_I", "RTY_I"],
                    ),
                    PlaybookStep(
                        action="Decode ADR_O against the interconnect address map",
                        detail="An unclaimed address produces a hang with no error anywhere.",
                        signals=["ADR_O"],
                    ),
                    PlaybookStep(
                        action="Check the slave clock and reset for the duration of the cycle",
                        signals=["clk", "rst"],
                    ),
                    PlaybookStep(
                        action="Confirm the master held CYC until termination",
                        detail="An early CYC drop makes a slave-side hang look like a master-side one.",
                        signals=["CYC_O"],
                    ),
                ],
            ),
            DebugPlaybook(
                id="wishbone.err",
                name="Wishbone ERR investigation",
                steps=[
                    PlaybookStep(
                        action="List every phase terminated by ERR_I with its address",
                        signals=["ERR_I", "ADR_O"],
                    ),
                    PlaybookStep(action="Classify each as unmapped, protected, or state-dependent"),
                    PlaybookStep(
                        action="Reconcile the testbench memory map with the interconnect decode"
                    ),
                    PlaybookStep(
                        action="Make the master and scoreboard treat ERR as an error, never as data",
                        detail="A shared ACK/ERR path in the master is a common root cause.",
                    ),
                ],
            ),
            DebugPlaybook(
                id="wishbone.rty",
                name="Wishbone retry livelock",
                steps=[
                    PlaybookStep(
                        action="Count RTY terminations per address and per master",
                        signals=["RTY_I", "ADR_O"],
                    ),
                    PlaybookStep(
                        action="Identify the resource the slave is waiting to free",
                        detail="Find who owns it and why that owner is not making progress.",
                    ),
                    PlaybookStep(
                        action="Check the arbiter for fixed-priority starvation",
                        signals=["CYC_O"],
                    ),
                    PlaybookStep(action="Add a retry limit or backoff so livelock fails loudly"),
                ],
            ),
            DebugPlaybook(
                id="wishbone.framing",
                name="Wishbone framing violation",
                steps=[
                    PlaybookStep(
                        action="Find the first cycle where STB was high and CYC was not",
                        signals=["CYC_O", "STB_O"],
                    ),
                    PlaybookStep(
                        action="Check for a reset asserted on only one side of the interface",
                        signals=["rst"],
                    ),
                    PlaybookStep(
                        action="Inspect any bridge on the path for independent CYC and STB gating"
                    ),
                    PlaybookStep(
                        action="Confirm the arbiter holds the grant until the phase terminates"
                    ),
                ],
            ),
        ],
        references=[Reference(source=_SPEC, note="Primary protocol reference for this pack.")],
    )
