"""Evidence rules that name parts of the company, as data (M63).

The levels generator (`nirmaan.evals.levels`) may not name a unit, skill or
domain itself (tests/test_nirmaan_evals.py), so the domains whose skills need
a must-fail control before they can be Practised live here: RTL design and
verification (capability build-out council record, 2026-10-18, section 9.7;
pull request #118, waiting for the founder).
"""

from __future__ import annotations

#: Skill domains whose Practised level needs a must-fail control in every case it rests on.
MUST_FAIL_DOMAINS: tuple[str, ...] = ("design", "verification")
