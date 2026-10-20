# Milestone 56 - Seniority band

The level-derived skill scale said every senior seat was "expert" with no
record behind it. The capability build-out council (record section 9, item 1)
renamed it. Design: `docs/SENIORITY_BAND.md`. Tests:
`tests/test_nirmaan_org.py::test_band_is_derived_from_level` and
`test_band_claims_no_expertise`.

**The rename.** `Proficiency` (awareness, working, proficient, expert) is now
`SeniorityBand` (foundation, working, advanced, lead).
`Capability.min_proficiency` is `min_band`, `Organization.proficiency()` is
`band()`, and the agent card, `nirmaan org role`, and the work packet print the
band.

**No behaviour change.** Same rank order, same derivation, same tool gating:
every role's capabilities, tools, and skill map compared equal between main and
the branch.
