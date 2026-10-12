"""Reset sequencing and clocking Knowledge Pack.

Reset/clock-domain failures produce some of the most confusing evidence
(X propagation, simulator iteration limits, failures at time zero); this
pack encodes the deterministic signatures that identify them.
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

_CDC_REF = "Clifford Cummings, CDC design and verification papers (SNUG)"


@register_pack
def reset_pack() -> KnowledgePack:
    return KnowledgePack(
        id="reset-clocking",
        name="Reset sequencing and clocking",
        version="1.0.1",  # M55: a playbook or concept id no longer repeats a pattern id
        domain="clocking",
        summary="Reset ordering, X propagation, and oscillation/iteration-limit signatures.",
        concepts=[
            Concept(
                id="reset.sequencing",
                name="Reset sequencing",
                summary=(
                    "Reset must be asserted long enough, released synchronously to a "
                    "stable clock, and ordered across domains. Releasing reset before "
                    "the clock (or a dependent domain) is stable leaves state elements "
                    "metastable or X."
                ),
                markers=[r"reset (?:released|deassert)", r"clock .*(?:stable|lock)", r"\bpor\b|power[- ]on reset"],
                references=[Reference(source=_CDC_REF, note="Asynchronous reset synchronization.")],
            ),
            Concept(
                id="reset.x-propagation-after-reset",
                name="X propagation",
                summary=(
                    "Uninitialized or reset-skipped state drives X into downstream "
                    "logic; comparisons against X poison checkers and can silently "
                    "mask real behavior in 2-state simulation."
                ),
                markers=[r"\bx\b propagat", r"unknown value", r"=\s*[xX]\b", r"is [xX]\b"],
            ),
        ],
        patterns=[
            FailurePattern(
                id="reset.released-before-clock-stable",
                name="Reset released before clock stable",
                summary=(
                    "Reset deasserted while the clock or PLL was not yet stable; "
                    "downstream state is unreliable from that point."
                ),
                required=[
                    EvidenceClause(
                        name="reset/clock ordering message",
                        pattern=r"reset .*(?:before|while).*(?:clock|pll)|clock not stable|pll (?:not )?lock",
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Reset counter shorter than PLL lock time",
                    "Missing reset synchronizer on the released domain",
                    "Testbench drives reset on a different timescale than the clock model",
                ],
                ownership="design",
                suggested_signals=["rst_n per domain", "pll_lock", "clock enables"],
                playbook_id="reset.sequence-audit",
                confidence_modifiers={"rtl_bug": 0.12},
                references=[Reference(source=_CDC_REF, note="Reset release ordering.")],
            ),
            FailurePattern(
                id="reset.x-propagation",
                name="Unexpected X propagation",
                summary="Unknown values reached checked logic; state was never initialized or reset was bypassed.",
                required=[
                    EvidenceClause(
                        name="X observed",
                        pattern=r"\bx\b propagat|unknown value|(?:=|is)\s*[xX]\b",
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Flop not covered by any reset term",
                    "Reset-domain crossing without synchronization",
                    "Memory read-before-write in the model",
                ],
                ownership="design",
                suggested_signals=["first X-valued net (trace backward)"],
                playbook_id="reset.x-trace",
                confidence_modifiers={"rtl_bug": 0.10},
                references=[Reference(source=_CDC_REF, note="Uninitialized state and reset coverage.")],
            ),
            FailurePattern(
                id="clock.oscillation-iteration-limit",
                name="Repeated evaluation loop (iteration limit)",
                summary=(
                    "The simulator hit its delta-cycle/iteration limit: combinational "
                    "feedback or a zero-delay loop kept re-evaluating without time "
                    "advancing."
                ),
                required=[
                    EvidenceClause(
                        name="iteration limit reached",
                        pattern=r"iteration limit|delta (?:cycle )?limit|infinite loop|retry loop",
                        must_fail=True,
                    ),
                ],
                typical_causes=[
                    "Combinational loop through a multiplexer or latch",
                    "Zero-delay clock generator feeding back into itself",
                    "always_comb reading and writing the same signal",
                ],
                ownership="design",
                suggested_signals=["nets in the reported instance (loop trace)"],
                playbook_id="clock.loop-trace",
                confidence_modifiers={"rtl_bug": 0.12, "infrastructure_issue": -0.05},
                references=[Reference(source=_CDC_REF, note="Combinational loop and delta-cycle hazards.")],
            ),
        ],
        playbooks=[
            DebugPlaybook(
                id="reset.sequence-audit",
                name="Reset sequence audit",
                steps=[
                    PlaybookStep(action="Plot reset and clock/PLL-lock together", signals=["rst_n", "pll_lock", "clk"]),
                    PlaybookStep(action="Measure reset assertion length in clock cycles", detail="Compare against the documented minimum."),
                    PlaybookStep(action="Check every domain's reset synchronizer", detail="Async assert, sync release, per domain."),
                    PlaybookStep(action="Audit the testbench reset driver", detail="Confirm the stimulus honors the bring-up ordering the design assumes."),
                ],
            ),
            DebugPlaybook(
                id="reset.x-trace",
                name="X origin trace",
                steps=[
                    PlaybookStep(action="Find the first time any checked signal went X", detail="Everything after the first X is a symptom."),
                    PlaybookStep(action="Trace the X fan-in to its origin flop or memory"),
                    PlaybookStep(action="Check that flop's reset term", detail="Most X origins are simply un-reset state."),
                    PlaybookStep(action="Re-run with X-propagation checks enabled", detail="Catch siblings of the same origin."),
                ],
            ),
            DebugPlaybook(
                id="clock.loop-trace",
                name="Combinational loop trace",
                steps=[
                    PlaybookStep(action="Read the simulator's reported instance and time", detail="The loop is inside or feeds this scope."),
                    PlaybookStep(action="List combinational paths that close on themselves in that scope"),
                    PlaybookStep(action="Check latch inference warnings from compilation", detail="Unintended latches create feedback."),
                    PlaybookStep(action="Break the loop with a register and re-run"),
                ],
            ),
        ],
    )
