# The IP Nirmaan council

The council decides questions about IP Nirmaan as a business and a product:
pricing and licensing, launches and design partners, naming and public pages,
legal and data questions, and architecture choices that are expensive to undo.
It is the same structure the Nirmaan studio uses (see
`docs/operations/decision-meetings.md` in `nirmaansoftware/Nirmaan`), with seats
for chip IP.

**Not the product's decisions.** IP Nirmaan the software records engineering
decisions inside a project (`Decision` in `models/work.py`, `nirmaan decide`,
docs/DECISIONS_CLI_MCP.md), checked by its authority matrix and constitution.
The council is outside the software: it is how the people building IP Nirmaan
decide. Its records are called council records, never decisions in the product
sense.

## Seats

| Seat | Judges |
|---|---|
| [chair](chair.md) | Chairs round 2 and decides |
| [product-lead](product-lead.md) | Scope, launch status, design partners, roadmap |
| [verification-lead](verification-lead.md) | VeriTriage, regression debug, coverage, formal |
| [design-architect](design-architect.md) | RTL, microarchitecture, protocols, IP blocks |
| [dft-engineer](dft-engineer.md) | Scan, ATPG, MBIST, and what a test coverage number rests on |
| [physical-design-engineer](physical-design-engineer.md) | Synthesis to a library, place and route, STA, DRC and LVS on open PDKs |
| [firmware-engineer](firmware-engineer.md) | Drivers, the register map as firmware sees it, RISC-V SoC runs |
| [eda-tooling](eda-tooling.md) | The open-source EDA flow and CI, and what each run proves |
| [ai-engineer](ai-engineer.md) | Model seats, providers, evaluation, AI cost |
| [market-research](market-research.md) | Who buys, what they pay today, competitors |
| [finance-licensing](finance-licensing.md) | Prices and the commercial model |
| [legal-compliance](legal-compliance.md) | Licences, specifications, export control, customer data (flags for counsel) |
| [security](security.md) | Customer design confidentiality, MCP and CLI surfaces, supply chain |
| [qa-evidence](qa-evidence.md) | Every claim against the code and recorded evidence |
| [brand-content](brand-content.md) | Positioning, naming, public copy |
| [site-engineer](site-engineer.md) | ip.nirmaan.online: performance, accessibility, SEO |
| [legal-counsel](legal-counsel.md) | Drafts agreements for a qualified lawyer to review (legal-compliance flags, counsel drafts) |
| [tax-accounts](tax-accounts.md) | GST, export of services, TDS and invoices, for a chartered accountant |
| [partnerships](partnerships.md) | Finding and recruiting design partners and first customers |
| [founder-proxy](founder-proxy.md) | Agent, not a meeting seat: the third reviewer of founder-class pull requests, under the founder's delegation of 2026-10-18 |

Add a seat by adding a file in the same format and a row here.

## Teams (pull request review)

The same seats review pull requests in teams. Decided in
[the 2026-10-17 council record](records/2026-10-17-teams-and-pr-review.md); how
the review runs is in `docs/REVIEW_MECHANISM.md` (IMPLEMENTED: the ruleset on
`main` requires both review checks from the review App). Each lead's seat file holds its key-1 checklist
under "In a review".

| Team | Key 1 (lead) | Members (no key) |
|---|---|---|
| Council | chair holds key 2 for every PR; key 1 on Council paths: security (control files), qa-evidence (records, seat files) | |
| Silicon Design | design-architect | dft-engineer, physical-design-engineer, firmware-engineer |
| Verification | verification-lead | qa-evidence |
| EDA and Platform | eda-tooling (also the catch-all owner) | security, ai-engineer |
| Product and Site | product-lead | site-engineer, brand-content, market-research |
| Business | legal-compliance (licences, notices, third-party code and text); finance-licensing (prices, commercial terms, spend) | legal-counsel, tax-accounts, partnerships |

One key-1 verdict per owning team; members' checklists run inside the lead's
review and are cited in it. A key is an agent review: never a person's
decision, a release, or a claim that a design is ready to be made in silicon.
Six founder classes (council record, section 2) also get the Founder Proxy
(agent, [founder-proxy.md](founder-proxy.md)) after key 2, under the founder's
delegation of 2026-10-18. It is not the founder: what only the founder decides
(spending, contracts and legal counsel, public names, prices published to
clients, any sending, and the review system's own gates) it sends to the
founder as `needs-founder`.

## Seat map

[`seat-map.yml`](seat-map.yml) maps each seat to one role in the product's
modelled company (`src/nirmaan/company/org_chart.py`) or to a shared role
(legal, legal counsel, tax and accounts, which serve both organisations and
report to the founder). Decided in the capability build-out council record of
2026-10-18 (sections 5 and 6) and corrected by the review-loop record of
2026-10-18 (work item R12). The chart itself names no seat, deputy or vote.

- One seat, one role; no role holds two seats. `legal-compliance` is the shared
  legal role, never the Quality "Compliance" practice.
- A key-1 lead holds a role that heads a unit. `covers` lists units a seat
  reviews until a seat inside each holds key 1 there.
- A deputy runs only for key 1, only after an infrastructure failure, and
  shares a review team with its seat; the chair's deputy is the founder.
- The Founder Proxy is unplaced: where the chart records it is the founder's
  decision.
- Each team in `.github/review-teams.yml` stores `unit:` and `key2:`, derived
  from this map and the chart and checked by `tests/test_seat_map.py`. A derived
  key 2 that would be the founder or report to the founder is the chair, and
  today every `key2` is `chair`. Nothing that picks a reviewer reads this map or
  the chart: the review script reads only `.github/review-teams.yml` on `main`.

### Practice leads (key 1, no vote)

A practice lead holds key 1 on its unit's paths and is asked for owner facts in
a meeting; it gives no round-1 position. None is seated yet: practice leads are
added in the founder-class hiring pull request at the start of their wave.

| Seat | Role | Key-1 paths |
|---|---|---|
| (none yet) | | |

A practice lead's seat file has the same shape as the other seat files:

```
---
slug: <seat>
role: <title>
reviewed_by: chair
permissions: read only (a seat never changes the repository)
---

# <Title>

## Mission
## Expertise
## Reads first
## In a review (key 1, <team>, practice lead)
<its unit's paths; the base checklist first; then "Fails when:" items>
## Never claims
## In a meeting
<owner facts only, when the chair asks; no round-1 position and no vote>
```

Its row goes in the table above and its entry in `seat-map.yml` (`vote: no`).

## When to call a meeting

Pricing, launching or naming, anything that goes on ip.nirmaan.online, a legal
or data question, or an architecture choice that is expensive to undo. Not
routine code: milestones follow CLAUDE.md and docs/ROADMAP.md.

## How it runs

1. **Brief.** One file states the decision, the facts (with numbers and file
   paths, read from the repository), the rules that apply (CLAUDE.md, including
   "never fake work" and no em or en dashes), the agenda as numbered
   questions, and the answer format. Every seat reads the same brief.
2. **Round 1: independent positions.** Every seat except the chair answers at
   once, from its own file, without seeing anyone else's answer. Read only.
   Format: ROLE / POSITION / MUST-HAVE / CONFIDENCE, about 250 words. Facts,
   inferences and assumptions are labelled, and sources are cited.
3. **Round 2: the chair decides.** The chair reads every position, decides each
   agenda item, names who disagreed and why it chose as it did, records dissent,
   and sets gates with an owner seat for each.
4. **Follow-up questions go to the owner.** A decision that rests on a number or
   fact goes back to the seat that owns it; nobody guesses.
5. **Implement, then verify by the owner.** The owning seat checks the result
   before it ships (qa-evidence checks every public claim against the code).

## Records

| Record | Where | Contains |
|---|---|---|
| Council record | `council/records/YYYY-MM-DD-<topic>.md` | Decisions, changes, gates with owner seats, open questions, dissent |
| Internal minutes and every position | `~/Nirmaan-internal/<date>-ip-<topic>/`, outside the repository | Margins, costs, effort estimates, anything a public repository must not hold |

This repository is public. A council record never contains margins, internal
costs or effort estimates.

## What stays with the founder

The council decides; the founder can overrule, and the record says so. These
always wait for the founder: signing a contract, spending money (including
legal counsel), and changing a public name.

Merging follows the two-key review (Teams, above; `docs/REVIEW_MECHANISM.md`):
a pull request merges by itself once CI and both keys pass, unless it is in
one of the six founder classes (control plane, gate semantics, licence and
third-party, commercial, public names and claims, export-control sensitive
content; council record 2026-10-17, section 2). Those also wait for the
founder's own approval on GitHub. Publishing is not a class of
its own: a change to ip.nirmaan.online waits for the founder when it is in one
of the six, for example a new public claim or name.

To run a meeting in a Claude Code session, ask for one; the `council-meeting`
skill (`.claude/skills/council-meeting/`) follows this page.
