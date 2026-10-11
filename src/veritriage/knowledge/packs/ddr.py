"""DDR / LPDDR SDRAM (with DFI) Knowledge Pack.

DRAM timing parameters, refresh discipline, and the DFI PHY interface. These
are the controller-side failures that corrupt data or hang a rank: a timing
constraint violated between commands, or a refresh that slips past its
interval.

Note: threshold-margin analysis (how close a number is to a limit) is not
expressible with today's presence-based clauses; these patterns fire on a
checker/monitor already reporting the violation. Numeric-comparison clauses
are a future matcher upgrade (docs/history/context-before-M43.md, section 5.1).
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
    Reference,
)
from veritriage.knowledge.registry import register_pack

_SPEC = "JEDEC DDR/LPDDR SDRAM Standard"


@register_pack
def ddr_pack() -> KnowledgePack:
    return KnowledgePack(
        id="ddr",
        name="DDR / LPDDR SDRAM",
        version="1.0.0",
        domain="memory",
        summary="DRAM command timing, refresh discipline, and DFI PHY handoff.",
        concepts=[
            Concept(
                id="ddr.timing",
                name="DRAM command timing",
                summary=(
                    "DRAM commands must respect timing parameters: tRCD (activate to "
                    "read/write), tRP (precharge), tRAS (active window), tWR (write "
                    "recovery). Issuing a command before its predecessor's timing "
                    "closes corrupts the access or the array."
                ),
                markers=[r"\bt(?:rcd|rp|ras|rc|rfc|wr|faw)\b", r"dram timing|command timing", r"activate|precharge|refresh"],
                references=[Reference(source=_SPEC, section="Timing", note="Core DRAM timing parameters.")],
            ),
            Concept(
                id="ddr.refresh",
                name="Refresh discipline",
                summary=(
                    "DRAM cells leak and must be refreshed within tREFI on average, "
                    "each refresh taking tRFC. A controller that skips or delays "
                    "refresh past the retention window loses data; one that refreshes "
                    "into an open bank violates command ordering."
                ),
                markers=[r"\brefresh\b", r"\btrefi\b|\btrfc\b", r"retention|auto[- ]?refresh"],
                references=[Reference(source=_SPEC, section="Refresh", note="tREFI/tRFC refresh requirements.")],
            ),
        ],
        signals=[
            ProtocolSignal(name="dram_cmd", role="issued DRAM command", channel="DFI"),
            ProtocolSignal(name="bank_state", role="per-bank active/idle state", channel="DFI"),
            ProtocolSignal(name="refresh_pending", role="refresh owed to a rank", channel="DFI"),
        ],
        patterns=[
            FailurePattern(
                id="ddr.timing-violation",
                name="DRAM timing parameter violated",
                summary=(
                    "A DRAM command was issued before the required timing between it "
                    "and a prior command elapsed (for example activate-to-read before "
                    "tRCD), risking corruption."
                ),
                required=[
                    EvidenceClause(
                        name="timing constraint violated",
                        pattern=r"\bt(?:rcd|rp|ras|rc|rfc|wr|faw)\b.*(?:violat|not met)|dram timing.*violat|(?:activate|precharge).*too (?:soon|early)|timing parameter.*violat",
                        must_fail=True,
                    ),
                ],
                optional_=[
                    EvidenceClause(name="ddr context", pattern=r"\bdram\b|\bddr\b|\bdfi\b|activate|precharge"),
                ],
                typical_causes=[
                    "Timing counter for the parameter initialized or decremented incorrectly",
                    "Command scheduler reorders around an open constraint",
                    "Per-rank/per-bank timing tracked with a shared counter",
                ],
                ownership="design",
                suggested_signals=["dram_cmd", "bank_state", "timing counter"],
                playbook_id="ddr.timing-debug",
                confidence_modifiers={"rtl_bug": 0.12},
                references=[Reference(source=_SPEC, section="Timing", note="Command spacing constraints.")],
            ),
            FailurePattern(
                id="ddr.refresh-missed",
                name="Refresh missed or delayed",
                summary=(
                    "An auto-refresh was not issued within tREFI, so cells risk "
                    "losing retention, or a required refresh was skipped entirely."
                ),
                required=[
                    EvidenceClause(
                        name="refresh not issued in time",
                        pattern=r"refresh (?:missed|not issued|skipped|interval violat)|trefi.*(?:violat|exceed)|missed (?:auto[- ]?)?refresh",
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Refresh interval counter paused during a long burst and never caught up",
                    "Refresh de-prioritized indefinitely under heavy traffic",
                    "Per-rank refresh owed-counter not incremented",
                ],
                ownership="design",
                suggested_signals=["refresh_pending", "refresh interval counter"],
                playbook_id="ddr.refresh-debug",
                confidence_modifiers={"rtl_bug": 0.12},
                references=[Reference(source=_SPEC, section="Refresh", note="Average tREFI must be met.")],
            ),
        ],
        playbooks=[
            DebugPlaybook(
                id="ddr.timing-debug",
                name="DRAM timing debug",
                steps=[
                    PlaybookStep(action="Identify the two commands and the timing parameter between them", signals=["dram_cmd"]),
                    PlaybookStep(action="Check the corresponding timing counter's init and decrement", signals=["timing counter"]),
                    PlaybookStep(action="Confirm the scheduler cannot reorder around an open constraint"),
                    PlaybookStep(action="Verify per-rank/per-bank timing is tracked independently", signals=["bank_state"]),
                ],
            ),
            DebugPlaybook(
                id="ddr.refresh-debug",
                name="DRAM refresh debug",
                steps=[
                    PlaybookStep(action="Trace the refresh interval counter across the failing window", signals=["refresh interval counter"]),
                    PlaybookStep(action="Confirm refresh is not indefinitely de-prioritized under load"),
                    PlaybookStep(action="Check the per-rank refresh owed-counter increments correctly", signals=["refresh_pending"]),
                    PlaybookStep(action="Verify refresh is not issued into an open bank"),
                ],
            ),
        ],
        references=[Reference(source=_SPEC, note="Primary reference for DDR/LPDDR.")],
    )
