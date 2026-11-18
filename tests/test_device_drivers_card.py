"""The device_drivers card and decision 6 agree on where a register map header comes from (G3).

The council record 2026-11-17 (whole-flow cases, fact 8 and decision 2) found the card saying the header is written
"from the approved interface specification, never from the RTL" beside decision 6 of the pilot retrospective, which
has the driver's map come from the RTL stage's output, and left the card change to its own pull request. The card
now keeps the specification as the source and adds the check against the approved RTL, so a seat given both reads
one rule: write from the specification, check against the RTL, never copy the RTL, escalate a disagreement.
"""

from __future__ import annotations

from nirmaan.company import build_organization


def test_the_map_header_comes_from_the_specification_and_is_checked_against_the_rtl():
    card = build_organization().skills["device_drivers"]
    [rule] = [p for p in card.procedures if "register map header" in p]
    assert "from the approved interface specification" in rule
    assert "check it against the approved RTL" in rule
    assert "never copy it from the RTL" in rule and "escalate a disagreement" in rule
    assert "never from the RTL." not in rule  # the old wording, which read as "ignore the RTL"
