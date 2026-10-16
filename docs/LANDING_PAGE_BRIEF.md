# Landing page brief: ip.nirmaan.online

A brief for building the IP Nirmaan landing page. It says what the page must
communicate and what it must never claim. Layout, visual design, and stack are
up to the builder.

## 1. Basics

| | |
|---|---|
| **URL** | `ip.nirmaan.online`, a subdomain of the owner's existing software-services company site (`nirmaan.online`). |
| **Brand** | **IP Nirmaan**, always written that way. The command-line tool is `nirmaan`; the verification engine is **VeriTriage**. |
| **Source** | https://github.com/nirmaansoftware/ip-nirmaan (public, Apache-2.0) |
| **Stage** | Early and open source: a working foundation, not a commercial product. A small number of design partners may work with it under written terms. The page must read that way. |
| **Owner** | Om Patel. Contact details are for the owner to supply; do not invent an email address or a form endpoint. |

## 2. Who the page is for

1. **Semiconductor engineers and verification leads** who want to see what an AI-native engineering organization looks like.
2. **Technical recruiters and hiring managers**, evaluating the owner's systems and DV skills.
3. **Potential collaborators and customers**, who should be able to reach us within one click.

All three are technical. Write for engineers: concrete, specific, and without hype.

## 3. The one-sentence pitch

> IP Nirmaan is an AI-native semiconductor IP company modeled as software: you
> give it a requirement, and a machine-readable organization plans, routes,
> reviews, and gates the work, with evidence behind every claim.

A shorter tagline for the hero: **"A semiconductor IP company, as software."**

On the page (2026-09-28) the hero headline reads **"Chip IP, built as software."**, with "Semiconductor IP" in the label above it. Each line then fits nirmaan.online's headline rule, so both sites' headlines are the same size; any line containing "semiconductor" is too wide for it.

## 4. Sections, in order

### Hero
- Tagline, the one-sentence pitch, and two buttons: **Talk to us** (the nirmaan.online contact page) and **See how it works** (scrolls down).
- The page links to the source once, in the footer ("Open source under Apache-2.0. Source on GitHub."), never from the hero, the navigation or a call to action (founder decision, 2026-10-16, replacing the 2026-09-28 decision not to link it).
- One visual: an excerpt of a real plan tree (sample in section 6), styled as a terminal.

### The idea
Three short points:
- **An organization, not a chatbot.** Divisions, teams, and roles from intern to CEO, each with skills, authority, and an escalation path.
- **Planned is not done.** Work moves through planned, executed, verified, and approved, and nothing skips a step.
- **Evidence or it did not happen.** A tool run, a review, or a named person's sign-off backs every claim. An AI cannot mark its own work approved.

### How it works
A four-step flow diagram:

```
Requirement -> Analyze -> Route to roles -> Review and gate -> Deliverable
```

One or two sentences per step. Example requirement: "Create a 4-port AXI-to-NoC bridge."

### What the organization looks like
Stat tiles, using these exact numbers (from `site/stats.json`, v1.25.0):

| Number | Label |
|---|---|
| 207 | organizational units |
| 685 | roles, from intern to CEO |
| 140 | engineering skills |
| 9 | engineering workflows |
| 12 | constitution principles |
| 44 | verification knowledge packs |
| 1987 | automated tests |

A simplified org chart helps here: Product, Architecture, Design Engineering, Verification, Silicon Implementation, Software, Security, Infrastructure, Documentation, Quality.

### The company constitution
List the 12 principles as short cards: traceability, evidence for decisions, explicit uncertainty, no fabricated work, no fabricated tool runs, independent review, conflicts escalate, provenance, evidence for signoff, no hidden state changes, auditability, human approval at gates.

### Built on VeriTriage
One short section. VeriTriage is the verification-intelligence engine inside IP Nirmaan. It turns simulation logs, coverage, and waveforms into an evidence graph and a ranked, evidence-backed root cause. When IP Nirmaan triages a regression, VeriTriage does the investigation, and its results become evidence in the task.

### Status and roadmap
Be honest and specific:
- **Working today:** the organization model, planning, routing, reviews, gates, the audit trail, and real VeriTriage investigations. AI workers can take design, RTL, and verification seats. They are off by default. Open-source tools check every RTL submission (lint, simulation, synthesis, and formal proofs when the work includes them) before a person reviews it. On a small block, place and route, three-corner timing, DRC, and LVS run for real in CI. In the tests, the AI workers' answers are scripted; one early live run of Claude Opus 5.5 passed all four RTL cases, judged by held-out checks, but was not recorded as data.
- **Next:** recorded, repeated live evaluations that anyone can re-judge, formal proofs written by the AI workers, and physical design beyond small blocks.
- **Not yet:** no customer has received IP from the system and nothing has been taped out. The reference blocks that run through the whole flow (a register block, a FIFO, an arbiter) prove the flow and its checks, not yet a model designing them unaided.

### Design partners
After Status. Follows `council/records/2026-10-16-commercial-model-and-design-partners.md`, which holds the exact copy. No price. No partner is named without their written consent. One call to action, "Talk to us". Status says "We have no design partners yet." until one has signed.

### Footer
"Talk to us", a link back to `nirmaan.online`, privacy and terms, and "Built by Om Patel".

## 5. Rules the copy must follow

- **Never claim what isn't true.** No "designs chips", "verified RTL", "customers", "production-ready", or performance numbers. The project's whole premise is not faking work, and the page must hold to that.
- **No em dashes or en dashes** anywhere in the copy. This is the owner's standing rule. Use a colon, a comma, or a new sentence.
- Keep it plain and specific: no "revolutionary", "unleash", "supercharge", or "10x".
- Use "AI agents" or "AI workers", not "AI employees".

## 6. Sample content for visuals

Plan tree excerpt, real output of `nirmaan plan "Create a 4-port AXI-to-NoC bridge."`, trimmed:

```
PROJECT: Create a 4-port AXI-to-NoC bridge
Intent: new_ip   Features: axi, cdc, multi_port, noc, registers
Assumption: Clocking was not stated, so CDC/RDC work is planned conservatively.

PROGRAM MANAGER  Senior Technical Program Manager
├── Architecture  (lead: Chief Architect)
│   ├── Interface specification: AXI interface   owner: Senior AXI Interface Architect
│   ├── Microarchitecture                        owner: Staff NoC Microarchitect
│   └── GATE Architecture approval                owner: Chief Architect (human approval)
├── RTL  (lead: Director, RTL Engineering)
│   ├── RTL implementation: AXI slave interface  owner: Senior Interface Design Engineer
│   └── RTL implementation: Arbitration          owner: Senior Interconnect Design Engineer
├── Verification  (lead: VP, Verification)
│   ├── Verification plan                         owner: Senior Verification Planning Engineer
│   └── Coverage closure                          owner: Senior Functional Coverage Engineer
└── Signoff
    └── GATE Verification signoff                 owner: VP, Verification (human approval)
```

The assurance ladder, as a visual: `planned -> executed -> verified -> approved`.

## 7. Technical requirements

- Static site: fast, no tracking, no cookie banner.
- Works on phones, with no horizontal scrolling.
- Light and dark mode.
- Accessible: sufficient contrast, keyboard navigable, and animations off under `prefers-reduced-motion`.
- DNS: a CNAME record for `ip` on `nirmaan.online`, pointing at the host.
