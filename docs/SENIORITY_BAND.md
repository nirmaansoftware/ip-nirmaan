# Seniority band (M56)

The organization held every skill at a `Proficiency`: awareness, working,
proficient, or expert. Nothing measured it. It was derived from the role's
level alone, so every senior, tech lead, and staff seat, and every level's own
core skills, read "expert" with no record behind the word. The capability
build-out council (record section 9, item 1) decided the scale keeps its job
and loses the claim: it is renamed to a seniority band, and "expert" leaves the
code and its output. A record-based scale (evidence levels: Knowledge,
Practised, Proven) comes later and must not share a name with this one.

## 1. The band

`models/org.py::SeniorityBand`, in rank order:

| Was | Is | Held by (inherited skills) |
|---|---|---|
| `AWARENESS` | `FOUNDATION` (`foundation`) | Intern |
| `WORKING` | `WORKING` (`working`) | Junior |
| `PROFICIENT` | `ADVANCED` (`advanced`) | Engineer; every manager-track role |
| `EXPERT` | `LEAD` (`lead`) | Senior, Tech Lead, Staff; any role in the skills its level profile grants |

The band says how senior the seat is, not how well the skill is done. It stays
derived from level, never hand-set.

## 2. What was renamed

| Was | Is |
|---|---|
| `Proficiency` | `SeniorityBand` |
| `Capability.min_proficiency` | `Capability.min_band` (default `ADVANCED`, as before) |
| `Organization.proficiency(role, skill)` | `Organization.band(role, skill)` |
| `_IC_PROFICIENCY` | `_IC_BAND` |
| `AW, WK, PR, EX` in `company/capabilities.py` | `FD, WK, AD, LD`; `_cap(..., band=...)` |

The agent card's `skills` map (and so `nirmaan org role`, `--json`, and the
work packet's role card) prints the band: `failure_triage (lead)` where it
printed `failure_triage (expert)`.

## 3. Behaviour is unchanged

Only names changed. The rank order is the same, so `capabilities_of` and
`tools_of` compare the same ranks: a capability needs the same band it needed,
and write, execute, and approve tools still need at least `WORKING`. Checked by
building the organization on main and on this branch and comparing every
role's capabilities, tools, and skill map (old values mapped to new): all 685
roles identical. Prompts in `tests/fixtures/prompts/` do not render the band
and are unchanged.

Tests: `tests/test_nirmaan_org.py::test_band_is_derived_from_level` (the
derivation, renamed) and `test_band_claims_no_expertise` (no band value says
"expert"; a senior's card prints `lead`).
