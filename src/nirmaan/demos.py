"""Demonstration requirements: the organizational simulation's test inputs.

Each is a synthetic request the company can receive. Planning one exercises
analysis, workflow selection, routing, review, gates, and escalation paths
without executing anything, which is exactly the Phase 3 claim: the
organization generates and connects the right work.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Demo:
    key: str
    title: str
    requirement: str
    expects_intent: str
    expects_phases: tuple[str, ...]


DEMOS: tuple[Demo, ...] = (
    Demo("1", "New IP: AXI-to-NoC bridge",
         "Create a 4-port AXI-to-NoC bridge.",
         "new_ip", ("Requirements", "Architecture", "RTL", "Verification", "Formal", "CDC/RDC",
                    "Implementation", "Documentation", "Integration", "Signoff")),
    Demo("2", "Feature addition: QoS arbitration",
         "Add QoS arbitration to an existing NoC router.",
         "feature_addition", ("Requirements", "Architecture", "RTL", "Verification", "Formal", "Integration")),
    Demo("3", "Parameter change: AXI data width",
         "Change AXI data width from 256-bit to 512-bit.",
         "parameter_change", ("Architecture", "RTL", "Verification", "Implementation", "Integration")),
    Demo("4", "Regression investigation",
         "Investigate a regression failure introduced by a recent RTL commit.",
         "regression_investigation", ("Debug", "Fix", "Verification")),
    Demo("5", "Verification signoff preparation",
         "Prepare an IP for verification signoff.",
         "signoff_preparation", ("Signoff", "Verification", "Formal")),
    Demo("6", "Organizational simulation (full spec)",
         "Design a configurable 4-port AXI-to-NoC bridge supporting 256-bit data, 40-bit address and QoS arbitration.",
         "new_ip", ("Requirements", "Architecture", "RTL", "Verification", "Formal", "CDC/RDC", "Signoff")),
    Demo("7", "Timing closure",
         "Fix the setup timing violation on the NoC router.",
         "timing_closure", ("Implementation", "Fix")),
    Demo("8", "Block design: AXI4-Lite register block",
         "Create an AXI4-Lite register block.",
         "block_design", ("Requirements", "Architecture", "RTL")),
)


def demo(key: str) -> Demo:
    for d in DEMOS:
        if d.key == key:
            return d
    raise KeyError(f"Unknown demo {key!r}; choose from {', '.join(d.key for d in DEMOS)}")
