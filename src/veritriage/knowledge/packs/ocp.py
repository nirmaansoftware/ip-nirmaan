"""Open Core Protocol (OCP) Knowledge Pack.

OCP is a configurable point-to-point core interface: a request phase the
slave accepts with SCmdAccept, an optional datahandshake phase, and a
response phase the master accepts with MRespAccept. Almost everything else
is a configuration option, which is exactly why its failures cluster around
the parts that are never optional: the handshakes, the response code, the
declared burst length, and in-order delivery within a thread.
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

_SPEC = "Open Core Protocol Specification 3.0 (Accellera/OCP-IP)"


@register_pack
def ocp_pack() -> KnowledgePack:
    return KnowledgePack(
        id="ocp",
        name="Open Core Protocol",
        version="1.0.0",
        domain="protocol",
        summary=(
            "OCP request/response handshakes, SResp error codes, burst-length "
            "agreement, and in-order delivery within a thread."
        ),
        concepts=[
            Concept(
                id="ocp.handshake",
                name="Request and response handshakes",
                summary=(
                    "A request is presented on MCmd and is only transferred on a "
                    "cycle where SCmdAccept is high; MCmd must hold stable until "
                    "then. A response is presented on SResp and, when "
                    "respaccept is configured, is only transferred when "
                    "MRespAccept is high. Either side holding its accept low "
                    "forever stalls the interface with no error anywhere."
                ),
                markers=[
                    r"\bocp\b",
                    r"\bmcmd\b",
                    r"\bscmdaccept\b",
                    r"\bmrespaccept\b",
                ],
                references=[
                    Reference(source=_SPEC, section="4.1", note="Request and response phases.")
                ],
            ),
            Concept(
                id="ocp.sresp",
                name="SResp response codes",
                summary=(
                    "SResp carries NULL (no response), DVA (data valid or "
                    "accepted), FAIL (request refused) or ERR (request failed). "
                    "FAIL and ERR are real failures: a master or scoreboard that "
                    "treats them as DVA converts an addressing or permission bug "
                    "into silent data corruption."
                ),
                markers=[r"\bsresp\b", r"\bocp\b.*(?:err|fail)\b", r"response code"],
                references=[Reference(source=_SPEC, section="4.5", note="Response field encoding.")],
            ),
            Concept(
                id="ocp.threads",
                name="Threads and ordering",
                summary=(
                    "Transfers carrying the same MThreadID must complete in "
                    "order. Reordering is legal only between different threads. "
                    "An out-of-order response inside one thread is a protocol "
                    "violation even when every individual transfer looks correct."
                ),
                markers=[r"\bmthreadid\b", r"\bsthreadid\b", r"\bthread\b.*\bocp\b", r"out.of.order"],
                references=[Reference(source=_SPEC, section="4.9", note="Threads and concurrency.")],
            ),
            Concept(
                id="ocp.bursts",
                name="Burst framing",
                summary=(
                    "MBurstLength declares how many transfers a burst contains "
                    "and MBurstSeq declares the address sequence (INCR, WRAP, "
                    "STRM, XOR, BLCK). A precise burst that delivers a different "
                    "number of data phases than it declared desynchronizes every "
                    "downstream counter."
                ),
                markers=[r"\bmburstlength\b", r"\bmburstseq\b", r"\bburst\b.*\bocp\b"],
                references=[Reference(source=_SPEC, section="4.7", note="Burst extensions.")],
            ),
        ],
        signals=[
            ProtocolSignal(name="MCmd", role="request command"),
            ProtocolSignal(name="SCmdAccept", role="slave accepts the request"),
            ProtocolSignal(name="SResp", role="response code"),
            ProtocolSignal(name="MRespAccept", role="master accepts the response"),
            ProtocolSignal(name="MThreadID", role="request thread identifier"),
            ProtocolSignal(name="SThreadID", role="response thread identifier"),
            ProtocolSignal(name="MBurstLength", role="declared burst length"),
        ],
        state_machines=[
            StateMachine(
                id="ocp.transfer",
                name="OCP transfer",
                states=[
                    ProtocolState(
                        name="Idle",
                        description="MCmd is IDLE; no request presented.",
                        markers=[r"ocp idle", r"mcmd.*idle"],
                    ),
                    ProtocolState(
                        name="RequestPresented",
                        description="MCmd driven, waiting for SCmdAccept.",
                        markers=[r"mcmd.*(?:assert|driven|present)", r"request.*present"],
                    ),
                    ProtocolState(
                        name="RequestAccepted",
                        description="SCmdAccept high; the request phase completed.",
                        markers=[r"scmdaccept.*(?:high|assert|seen)", r"request accepted"],
                    ),
                    ProtocolState(
                        name="ResponsePresented",
                        description="SResp driven, waiting for MRespAccept.",
                        markers=[r"sresp.*(?:driven|present|assert)", r"response.*present"],
                    ),
                    ProtocolState(
                        name="Complete",
                        description="Response transferred; the transaction is done.",
                        markers=[r"mrespaccept.*(?:high|assert)", r"ocp.*complete"],
                    ),
                ],
            ),
        ],
        patterns=[
            FailurePattern(
                id="ocp.request-not-accepted",
                name="Request never accepted",
                summary=(
                    "A command was presented on MCmd and the slave never raised "
                    "SCmdAccept, so the request phase never completed and the "
                    "interface stalled until a timeout fired."
                ),
                required=[
                    EvidenceClause(
                        name="timeout or hang observed",
                        pattern=r"time[- ]?out|watchdog|hung|stuck|no progress",
                        must_fail=True,
                    ),
                    EvidenceClause(
                        name="OCP request pending",
                        pattern=(
                            r"\bocp\b.*(?:request|mcmd|pending|stall)"
                            r"|scmdaccept.*(?:low|never|not)"
                            r"|\bmcmd\b.*(?:held|stable|pending)"
                        ),
                    ),
                ],
                typical_causes=[
                    "Slave clock gated or in reset while a request is presented",
                    "Slave FSM waiting on an internal event that never occurs",
                    "MAddr decodes into an unmapped region the slave silently ignores",
                    "Thread-busy backpressure applied to a thread that never drains",
                ],
                ownership="design",
                suggested_signals=["MCmd", "SCmdAccept", "MAddr", "MThreadID"],
                playbook_id="ocp.request-hang",
                confidence_modifiers={"rtl_bug": 0.10},
                references=[
                    Reference(source=_SPEC, section="4.1.1", note="Request phase handshake.")
                ],
            ),
            FailurePattern(
                id="ocp.response-error",
                name="Error response accepted as data",
                summary=(
                    "A transfer completed with SResp of ERR or FAIL, but the "
                    "returned data was consumed as valid. Later mismatches are "
                    "symptoms of this earlier ignored error, not independent bugs."
                ),
                required=[
                    EvidenceClause(
                        name="OCP error response observed",
                        pattern=(
                            r"\bsresp\b.*(?:err|fail)"
                            r"|\bocp\b.*(?:error|fail) response"
                            r"|response code.*(?:err|fail)"
                        ),
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Access to an unmapped or permission-protected address",
                    "Slave legally refusing the request in its current state",
                    "Testbench address map out of sync with the RTL decode",
                    "Scoreboard comparing payloads without checking SResp first",
                ],
                ownership="testbench",
                suggested_signals=["SResp", "MAddr", "MCmd"],
                playbook_id="ocp.response-error",
                confidence_modifiers={"testbench_issue": 0.08, "rtl_bug": 0.05},
                references=[Reference(source=_SPEC, section="4.5", note="SResp encoding.")],
            ),
            FailurePattern(
                id="ocp.burst-length-mismatch",
                name="Burst delivered a different length than declared",
                summary=(
                    "A precise burst declared one length on MBurstLength and "
                    "delivered a different number of data phases. Every counter "
                    "downstream of the burst is now offset."
                ),
                required=[
                    EvidenceClause(
                        name="burst length disagreement",
                        pattern=(
                            r"burst length.*(?:mismatch|expected|differs|wrong)"
                            r"|mburstlength.*(?:mismatch|violat)"
                            r"|(?:expected|declared) \d+ (?:transfers|beats).*(?:got|saw|received)"
                        ),
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Burst terminated early on an error without unwinding counters",
                    "Precise burst driven from a length register updated mid-burst",
                    "Master and slave disagreeing on whether the burst is precise",
                    "Testbench generator emitting a length the DUT configuration forbids",
                ],
                ownership="design",
                suggested_signals=["MBurstLength", "MBurstSeq", "MCmd", "MData"],
                playbook_id="ocp.burst",
                confidence_modifiers={"rtl_bug": 0.10, "testbench_issue": 0.05},
                references=[Reference(source=_SPEC, section="4.7", note="Precise burst framing.")],
            ),
            FailurePattern(
                id="ocp.thread-ordering-violation",
                name="Out-of-order response within one thread",
                summary=(
                    "Two responses carrying the same SThreadID were returned in "
                    "the wrong order. OCP permits reordering only between "
                    "threads, so this is a protocol violation regardless of "
                    "whether the data itself is correct."
                ),
                required=[
                    EvidenceClause(
                        name="ordering violation observed",
                        pattern=(
                            r"out.of.order.*(?:thread|response)"
                            r"|thread.*(?:ordering|order).*(?:violat|error|wrong)"
                            r"|response.*out of order"
                        ),
                        must_fail=True,
                    ),
                    EvidenceClause(
                        name="thread context present",
                        pattern=r"\bthread\b|\bmthreadid\b|\bsthreadid\b|\bocp\b",
                    ),
                ],
                typical_causes=[
                    "Response reorder buffer keyed on tag rather than thread",
                    "Multiple slaves sharing a thread id through an interconnect",
                    "Thread id dropped or remapped by a bridge",
                    "Scoreboard assuming global ordering across all threads",
                ],
                ownership="design",
                suggested_signals=["SThreadID", "MThreadID", "SResp"],
                playbook_id="ocp.thread-ordering",
                confidence_modifiers={"rtl_bug": 0.12},
                references=[
                    Reference(source=_SPEC, section="4.9", note="In-order delivery within a thread.")
                ],
            ),
        ],
        playbooks=[
            DebugPlaybook(
                id="ocp.request-hang",
                name="OCP request phase hang",
                steps=[
                    PlaybookStep(
                        action="Capture MCmd and SCmdAccept around the stall",
                        detail="Confirm MCmd was held stable and never withdrawn.",
                        signals=["MCmd", "SCmdAccept"],
                    ),
                    PlaybookStep(
                        action="Check the slave clock and reset during the request",
                        detail="A gated clock or a late reset release is the most common cause.",
                        signals=["clk", "SReset_n"],
                    ),
                    PlaybookStep(
                        action="Decode MAddr against the slave address map",
                        detail="An unmapped address that no slave claims looks exactly like a hang.",
                        signals=["MAddr"],
                    ),
                    PlaybookStep(
                        action="Check thread-busy backpressure for the stalled thread",
                        signals=["SThreadBusy", "MThreadID"],
                    ),
                ],
            ),
            DebugPlaybook(
                id="ocp.response-error",
                name="OCP error response investigation",
                steps=[
                    PlaybookStep(
                        action="List every transfer whose SResp was ERR or FAIL",
                        signals=["SResp", "MAddr"],
                    ),
                    PlaybookStep(
                        action="Classify each as unmapped, permission, or state-dependent refusal"
                    ),
                    PlaybookStep(
                        action="Reconcile the testbench address map with the RTL decode",
                        detail="A stale map produces error storms that look like a DUT bug.",
                    ),
                    PlaybookStep(
                        action="Make the scoreboard check SResp before comparing any payload"
                    ),
                ],
            ),
            DebugPlaybook(
                id="ocp.burst",
                name="OCP burst framing mismatch",
                steps=[
                    PlaybookStep(
                        action="Count the delivered data phases against MBurstLength",
                        signals=["MBurstLength", "MData", "SData"],
                    ),
                    PlaybookStep(
                        action="Confirm whether the burst was configured precise or imprecise",
                        detail="Imprecise bursts may legally deliver a different count.",
                        signals=["MBurstPrecise"],
                    ),
                    PlaybookStep(
                        action="Check for an early termination caused by an error response",
                        signals=["SResp"],
                    ),
                    PlaybookStep(action="Verify the length register is stable for the whole burst"),
                ],
            ),
            DebugPlaybook(
                id="ocp.thread-ordering",
                name="OCP thread ordering violation",
                steps=[
                    PlaybookStep(
                        action="Group the responses by SThreadID and re-check order within each group",
                        signals=["SThreadID", "SResp"],
                    ),
                    PlaybookStep(
                        action="Confirm the scoreboard enforces per-thread, not global, ordering",
                        detail="A global-order checker reports false violations on legal traffic.",
                    ),
                    PlaybookStep(
                        action="Trace the thread id through every bridge on the path",
                        detail="Remapping or truncation merges two threads into one.",
                        signals=["MThreadID", "SThreadID"],
                    ),
                    PlaybookStep(action="Inspect the response reorder buffer's keying and eviction"),
                ],
            ),
        ],
        references=[Reference(source=_SPEC, note="Primary protocol reference for this pack.")],
    )
