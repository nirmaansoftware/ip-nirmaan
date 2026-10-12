"""UVM methodology Knowledge Pack.

Testbench-side knowledge: phase/objection timeouts, scoreboard architecture,
and the failure modes that live in the verification environment rather than
the design.
"""

from __future__ import annotations

from veritriage.knowledge.model import (
    Concept,
    DebugPlaybook,
    EvidenceClause,
    FailurePattern,
    KnowledgePack,
    PlaybookStep,
    Reference,
)
from veritriage.knowledge.registry import register_pack

_UVM_REF = "IEEE 1800.2 (UVM)"


@register_pack
def uvm_pack() -> KnowledgePack:
    return KnowledgePack(
        id="uvm",
        name="UVM methodology",
        version="1.0.1",  # M55: a playbook or concept id no longer repeats a pattern id
        domain="methodology",
        summary="UVM phasing, objections, and scoreboard failure modes.",
        concepts=[
            Concept(
                id="uvm.phasing",
                name="UVM phasing and objections",
                summary=(
                    "UVM run-time phases end when every raised objection drops. A phase "
                    "timeout means someone held an objection past the limit: either the "
                    "stimulus genuinely never finished (DUT hang) or a component forgot "
                    "to drop its objection (testbench hang)."
                ),
                markers=[r"PH_TIMEOUT", r"phase timeout", r"objection", r"uvm_phase"],
                references=[Reference(source=_UVM_REF, section="9.3", note="Phasing and objection mechanism.")],
            ),
            Concept(
                id="uvm.scoreboard",
                name="Scoreboard and reference model",
                summary=(
                    "A scoreboard compares DUT observations against a predicted stream "
                    "from a reference model. A mismatch means the DUT and the model "
                    "disagree; which one is wrong is exactly the RTL-vs-testbench "
                    "question the evidence must settle."
                ),
                markers=[r"scoreboard", r"\bSCBD\b", r"reference model", r"predictor"],
                references=[Reference(source=_UVM_REF, section="13.5", note="Analysis components and comparators.")],
            ),
        ],
        patterns=[
            FailurePattern(
                id="uvm.scoreboard-mismatch-after-protocol-success",
                name="Scoreboard mismatch after protocol success",
                summary=(
                    "The interface followed the protocol (no assertion fired) yet the "
                    "scoreboard disagreed on data: the transport was right and the "
                    "prediction or the datapath was wrong."
                ),
                required=[
                    EvidenceClause(
                        name="scoreboard mismatch",
                        pattern=r"scoreboard|mismatch|miscompare|expected\b.*\b(?:got|actual)",
                        must_fail=True,
                    ),
                ],
                optional=[
                    EvidenceClause(name="protocol reported clean", pattern=r"follows .* protocol|protocol (?:ok|clean|pass)"),
                    EvidenceClause(name="multiple mismatches", pattern=r"mismatch.*0x[0-9a-f]+"),
                ],
                forbidden=[
                    EvidenceClause(
                        name="no protocol assertion fired",
                        pattern=r".",
                        artifact_types=["assertion"],
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Reference model predicts stale data (missed update ordering)",
                    "Scoreboard compares out-of-order streams as in-order",
                    "DUT datapath corrupts data while keeping the protocol legal",
                    "Byte-enable or endianness handling differs between model and DUT",
                ],
                ownership="testbench",
                suggested_signals=["scoreboard exp/act FIFOs", "monitor transaction stream"],
                playbook_id="uvm.scoreboard-mismatch",
                confidence_modifiers={"testbench_issue": 0.12, "rtl_bug": 0.04},
                references=[
                    Reference(source=_UVM_REF, section="13.5", note="Comparator semantics."),
                ],
            ),
            FailurePattern(
                id="uvm.phase-timeout",
                name="Phase timeout with stimulus incomplete",
                summary=(
                    "The UVM phase watchdog expired: an objection never dropped because "
                    "either the DUT stalled a completion or a component hung."
                ),
                required=[
                    EvidenceClause(
                        name="phase timeout",
                        pattern=r"PH_TIMEOUT|phase timeout|default timeout .* hit",
                        must_fail=True,
                    ),
                ],
                optional=[
                    EvidenceClause(name="activity pending", pattern=r"await|pending|outstanding|issued"),
                ],
                typical_causes=[
                    "DUT never returns a response the sequence is blocked on",
                    "A sequence forgot to drop its objection",
                    "Monitor missed the completing transaction, so the scoreboard never drained",
                ],
                ownership="testbench",
                suggested_signals=["uvm objection trace", "sequencer/driver handshake"],
                playbook_id="uvm.phase-timeout-debug",
                confidence_modifiers={"rtl_bug": 0.06, "testbench_issue": 0.06},
                references=[
                    Reference(source=_UVM_REF, section="9.3.1", note="Phase timeout semantics."),
                ],
            ),
        ],
        playbooks=[
            DebugPlaybook(
                id="uvm.scoreboard-mismatch",
                name="Scoreboard mismatch",
                steps=[
                    PlaybookStep(action="Dump the first mismatching transaction pair", detail="Expected vs actual, with timestamps and IDs."),
                    PlaybookStep(action="Replay the prediction for that transaction by hand", detail="Walk the reference model with the same inputs."),
                    PlaybookStep(action="Check stream ordering assumptions", detail="Out-of-order completion compared in-order is the classic false mismatch."),
                    PlaybookStep(action="Diff against the specification", detail="If the model and DUT disagree, the spec is the referee."),
                    PlaybookStep(action="Pull the datapath waveform for the failing address", detail="Only after the model is proven right.", signals=["write data path", "byte enables"]),
                ],
            ),
            DebugPlaybook(
                id="uvm.phase-timeout-debug",
                name="UVM phase timeout",
                steps=[
                    PlaybookStep(action="Print the objection trace at timeout", detail="+UVM_OBJECTION_TRACE names the component that never dropped."),
                    PlaybookStep(action="Find the blocked sequence/driver call", detail="The stack that never returned points at the stalled interface."),
                    PlaybookStep(action="Check the DUT side of that interface for progress", detail="Distinguish DUT-never-responded from testbench-never-completed.", signals=["interface handshake signals"]),
                    PlaybookStep(action="Inspect completion counters in the env", detail="Issued vs completed tells whether the hang is systematic."),
                ],
            ),
        ],
        references=[Reference(source=_UVM_REF, note="Methodology reference for this pack.")],
    )
