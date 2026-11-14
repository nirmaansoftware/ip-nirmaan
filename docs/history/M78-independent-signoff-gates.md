# Milestone 78 - Signoff gates independent of the producing department

Wave 2 of the capability build-out, the routing pull request of council record
`council/records/2026-11-14-g13-grouping-units.md`, decision 2c (gate owner
verification-lead). Design: `docs/HIERARCHY_FIXES.md` section 6. Tests:
`tests/test_independent_gates.py`, and the `INTENDED` set of
`tests/test_verification_departments.py`.

**The gap.** The five-department cut of Verification (M77) moved five
`gate.verification` tasks from the VP to the Simulation director, whose own
department produced the coverage they sign off. The gate spec was unchanged,
so the record allowed the move in M77 and asked for this fix.

**The rule.** `INDEPENDENT_GATES` in `src/nirmaan/company/governance.py`
(`gate.verification` and `gate.implementation`), carried by
`CompanyDefinition.independent_gates`. On those gates the router drops the
producers of the gated work and the heads of the units below the division
that hold them (`Organization.own_heads`); the approver is the next holder up
the chain, the division's VP. With no other holder the gate is planned
blocked. `gate.rtl` is left out: only the RTL director holds `signoff.rtl` at
the authority its gates need.

**The approver.** The VP, not Methodology and Signoff: Methodology and
Signoff's own signoff team produces the evidence on the other seven
`gate.verification` tasks, which are critical and need VP authority.

**What moves.** The coverage gate (5 tasks) goes back to the Verification VP;
the `sta`, `sta-signoff` and `reanalysis` gates (8 tasks) go from the Physical
Design director to the Implementation VP. Every other task plans as before.
No `GateSpec` changed.
