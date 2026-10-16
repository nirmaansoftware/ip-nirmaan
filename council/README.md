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

Add a seat by adding a file in the same format and a row here.

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
always wait for the founder: merging anything that publishes, signing a
contract, spending money (including legal counsel), and changing a public name.

To run a meeting in a Claude Code session, ask for one; the `council-meeting`
skill (`.claude/skills/council-meeting/`) follows this page.
