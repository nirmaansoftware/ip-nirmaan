# Council record: commercial model and design partners (2026-10-16)

The founder delegated this decision to the council. The chair decided it in
round 2 after reading all 12 positions. Facts were checked on origin/main
(commit e59dc2f). What stays with the founder is listed under "Founder to
confirm". Internal minutes and the positions are kept outside the repository.

## Decisions

### 1. What we sell

We sell engineer-led work and its evidence. We do not sell the code, which is
public under Apache-2.0. We do not sell AI capability.

**Note, 2026-10-30.** Founder decision, 2026-10-30 (recorded in
`council/records/2026-10-18-capability-buildout.md`): the
repository is all rights reserved from then on and no longer offered under
Apache-2.0 (see `LICENSE` and `NOTICE`); versions published before were offered
under Apache-2.0, and that does not change. This note corrects the licence
fact only. It does not decide what we sell: that is for the council or the
founder to revisit.

1. **First: a custom small block with its evidence pack.** One small,
   single-clock digital block, built to the customer's spec. In scope: register
   blocks from a register map (with a C header), simple peripherals such as a
   timer or GPIO, single-clock FIFOs and arbiters, and bus glue on APB or
   AXI4-Lite. The pack holds the interface spec, the microarchitecture,
   lint-clean Verilog, a self-checking testbench, formal results, a synthesis
   report with no latches, the `nirmaan export` tree, the tools and versions
   that ran, and a list of known limits. Bounded formal checks are reported as
   "no counterexample within N steps", never as proofs.
2. **Second: VeriTriage regression triage.** It is not sold yet. First it is
   measured: one partner's labelled regression, on the partner's machines,
   scored against the partner's own triage. It becomes a paid offer only if
   it matches or beats their manual baseline.
3. **On request only, not marketed:** support for self-hosted use, and
   training.
4. **Not now:** a hosted instance, dual licensing, and catalogue IP.

Units: one block; one regression study; support by the month; training by the
day. Prices are set internally and quoted per engagement. **No price is
published now.** Prices are published only after two paid engagements have
closed and market-research has at least five buyer interviews or real quotes
behind them.

AI is an internal accelerator. Model seats are used on partner work only after
gate 9, and only if the partner opts in in writing.

**Who wanted what.** Product Lead wanted the VeriTriage pilot as the first
offer. Verification Lead and QA found no accuracy evidence on real logs: the
fixtures are synthetic and there is no benchmark. Design Architect, EDA
Tooling, Finance, QA and Market Research favoured custom blocks with evidence.
**Chosen:** blocks first, because each delivery makes its own tool-judged
evidence that the customer can check. Triage comes second, behind a measured
study, because charging for triage with no recorded hit rate would break
"never fake work".

### 2. Design partners

Start looking now. Partner work starts only after the gates below. Three
partners, India only in this round.

| Slot | Profile | Work | Terms | Length |
|---|---|---|---|---|
| A | Indian fabless startup (DLI-backed preferred) or design-services firm | One small single-clock block with its evidence pack | Paid, at a partner discount | 90 days |
| B | Same as A | Same as A | Paid, at a partner discount | 90 days |
| C | Verification team with a running UVM regression on Questa, VCS or Xcelium, and its own triage labels | VeriTriage accuracy study on their machines, offline, model seats off | Unpaid | 8 weeks |

An academic lab can fill slot C only if it has a labelled regression on a
commercial simulator.

**Who wanted what.** Finance wanted three paid partners. Product Lead wanted
two or three unpaid triage partners. Market Research wanted two paid startups
and one free academic lab. Verification Lead wanted one or two labelled
regressions. Security wanted the first partner to start on open or synthetic
RTL. **Chosen:** two paid block partners, because they can pay and payment
tests the offer, and one unpaid triage study with Verification Lead's profile.
Security's concern is met by design: a block partner gives us a spec, not
RTL, and the triage study runs on the partner's machines. The spec is still
confidential and falls under every data gate.

**The partner gives:** a real spec or a labelled regression, one engineer for
a short weekly review, a right or wrong verdict on each triage (slot C), and a
sign-off by their own engineer. Slots A and B pay.

**The partner gets:** the block and its evidence pack, or a scored report of
VeriTriage against their labels. Their fixes go first in our backlog. They own
deliverables built from their inputs.

**We get:** recorded results per engagement, and failure data under NDA that
never enters this repository. A partner is named, or a case study published,
only with their written consent at the end.

**Selection:** the work fits the single-clock class; the partner accepts the
open-source tool boundary in writing; the export screen passes; acceptance
criteria are agreed before work; data stays on their machines or in an
isolated workspace they approve; no CONTRACT_ONLY capability is needed
(coverage, CDC, power, regression, equivalence).

**Exit:** the term ends; either side gives two weeks' notice; three weeks pass
with no response or no logs; scope grows past one block; a CONTRACT_ONLY
capability is needed; the partner asks for exclusivity or for the platform;
slot C ends if accuracy is below their manual baseline. Any data-handling
breach ends it at once.

**How to find them:** the founder's network; companies in the DLI scheme;
institutions in the C2S programme; design-services firms in Bengaluru and
Hyderabad; the new section on ip.nirmaan.online. The buyer interviews double
as the search.

### 3. Readiness

Gates 1 to 4 can be done now in the repository and ship with the page change.
Gates 5 to 19 must pass before the first partner's work starts. Each gate has
an owner seat, which verifies it. See the table below.

### 4. The public page

- **Stage:** the hero keeps "Early stage". The Status section keeps its "Not
  yet" box, and adds "We have no design partners yet." When a partner signs,
  that line becomes "We are working with a small number of design partners."
- **New section:** one static design-partner section between Status and the
  closing call to action. Exact copy is below. No new JavaScript, motion, form
  or schema.org Offer.
- **Call to action:** one label, "Talk to us". The partner section's button
  sends an email with a subject line, so enquiries can be told apart.
- **Price:** not shown.
- **Overclaim:** "AI workers fill ... seats" is corrected, on the page and in
  the landing brief.
- **GitHub link:** not decided here. See "Founder to confirm".
- **Order:** the page change ships in the same change as LICENSE and NOTICE.
  Legal asked that no commercial offer appear before them.

Product Lead wanted no page change until a partner signs. Overruled: the
section asks for a conversation, says work starts only under written terms,
and says what is out of scope. It promises nothing the gates do not cover.

## Changes to make now

Each change below goes in one branch. The founder merges it, because it
publishes. QA checks every public claim before merge. Run
`python scripts/check_dashes.py` and `pytest tests/test_landing_site.py`.

### 1. `LICENSE` (new, top level)

The full, unmodified text of the Apache License, Version 2.0, from
https://www.apache.org/licenses/LICENSE-2.0.txt.

### 2. `NOTICE` (new, top level)

```
IP Nirmaan
Copyright 2026 Om Patel

Licensed under the Apache License, Version 2.0. See LICENSE.

This product includes third-party files under their own licences:
- SERV, Copyright 2019 Olof Kindgren, ISC licence:
  src/nirmaan/integrations/firmware_soc/serv/ (see LICENSE there).
- PicoRV32, Copyright (C) 2015 Claire Xenia Wolf, ISC-style licence:
  src/nirmaan/integrations/firmware_soc/picorv32.v (notice in the file header).
- Fonts under the SIL Open Font License: site/assets/fonts/
  (see the OFL-*.txt files there).
```

### 3. `pyproject.toml`

Replace `"Development Status :: 5 - Production/Stable",` with:

```
  "Development Status :: 3 - Alpha",
```

### 4. `site/index.html`, Working today

Replace:

> AI workers fill design, RTL, and verification seats, and open-source tools
> check every submission (lint, simulation, synthesis, formal proofs) before a
> person reviews it.

With:

> AI workers can take design, RTL, and verification seats. They are off by
> default. Open-source tools check every RTL submission (lint, simulation,
> synthesis, and formal proofs when the work includes them) before a person
> reviews it.

### 5. `site/index.html`, Not yet

Append to the end of the "Not yet" paragraph:

> We have no design partners yet.

### 6. `site/index.html`, new section between `#status` and the `cta-band`

```html
<section class="section" id="partners" aria-labelledby="partners-title">
  <div class="wrap">
    <div class="section__head section__head--split" data-reveal>
      <div>
        <p class="eyebrow">Design partners</p>
        <h2 class="section__title display" id="partners-title">Looking for a few design&nbsp;partners.</h2>
      </div>
      <p class="section__text">IP Nirmaan is early. We are looking for a small number of teams to try it on real work, under written terms.</p>
    </div>
    <div class="status">
      <section class="status__col" data-reveal style="--d:0">
        <h3>A small block, with its evidence</h3>
        <p>Bring the spec for a small, single-clock digital block: a register block, a FIFO, an arbiter, or bus glue on APB or AXI4-Lite. We build it and give you the evidence from open-source tools (lint, simulation, synthesis, and formal), with every log, including what failed. Your engineer signs it off.</p>
      </section>
      <section class="status__col" data-reveal style="--d:1">
        <h3>A regression, measured</h3>
        <p>Bring a regression from your simulator, with your own triage labels. We run VeriTriage on your machines, offline, and compare its top diagnosis with your labels, one regression at a time. You see how often it was right.</p>
      </section>
      <section class="status__col" data-reveal style="--d:2">
        <h3>What we ask</h3>
        <p>A real requirement, an engineer for a short weekly review, and honest feedback. Work starts only after we agree in writing how your data is handled. Not covered: multi-clock designs, signoff, tapeout, or commercial EDA tools.</p>
      </section>
    </div>
    <div class="actions">
      <a class="btn" href="mailto:nirmaansoftware@gmail.com?subject=IP%20Nirmaan%20design%20partner">Talk to us</a>
    </div>
  </div>
</section>
```

Site Engineer may swap `status__col` for the cards component in nirmaan.css.
The words must not change without a new council record.

### 7. `site/index.html`, navigation

After each `<li><a href="#status">Status</a></li>` (primary nav, menu, and
footer), add:

```html
<li><a href="#partners">Partners</a></li>
```

### 8. `tests/test_landing_site.py`, new test

```python
def test_partner_offer_stays_early_and_unpriced() -> None:
    # Council record 2026-10-16: the design-partner offer shows no price and
    # claims no partner until one has signed.
    section = HTML.split('id="partners"', 1)[1].split('class="cta-band"', 1)[0]
    assert "early" in section.lower()
    for mark in ("\u20b9", "$", "usd", "lakh"):
        assert mark not in section.lower(), mark
    assert "We have no design partners yet." in HTML
```

When a partner signs, the last line changes in the same commit as the page.

### 9. `docs/LANDING_PAGE_BRIEF.md`

- Stage row, replace the text with: "Early and open source: a working
  foundation, not a commercial product. A small number of design partners may
  work with it under written terms. The page must read that way."
- Working today line: the same replacement as change 4.
- Stat table: take the numbers from `site/stats.json` (207 units, 685 roles,
  140 skills, 9 workflows, 12 principles, 44 knowledge packs, 1987 tests).
- Add a "Design partners" entry after Status that points to this record and
  repeats its rules: no price, no partner named without consent, one call to
  action.

### 10. `site/sitemap.xml`

Set `<lastmod>` to the deploy date.

### 11. `council/records/`

- Add this record as `council/records/2026-10-16-commercial-model-and-design-partners.md`.
- In `council/records/README.md`, replace "No meeting has been held yet."
  with:

```
- [2026-10-16: commercial model and design partners](2026-10-16-commercial-model-and-design-partners.md)
```

## Before the first design partner

Gates 1 to 4: now, in the repository. Gates 5 to 19: before the first
partner's work starts. The owner seat verifies each one.

| # | Gate | Owner seat |
|---|---|---|
| 1 | LICENSE and NOTICE at the top level (changes 1 and 2) | legal-compliance |
| 2 | Classifier set to "3 - Alpha" (change 3) | qa-evidence |
| 3 | "AI workers fill" overclaim fixed on the page and in the brief (changes 4 and 9) | brand-content |
| 4 | Landing brief matches the page: stage, stats, partner section (change 9) | brand-content |
| 5 | No partner spec, RTL or logs in this repository's public CI or artifacts. A private runner or the partner's machine only | eda-tooling |
| 6 | Mutual NDA and IP agreement, reviewed by counsel and signed: confidentiality, ownership of deliverables, our platform stays ours, AS-IS warranty, liability capped at the fee | legal-compliance |
| 7 | No personal Claude plan for partner work. A commercial API account with stated retention and no training, and a spend limit per partner, or the partner's own account, or model seats off | ai-engineer |
| 8 | Partner data lives outside this repository and outside iCloud or any cloud-synced folder, and is deleted at the end. EDA runs and partner testbenches run in a container with no network | security |
| 9 | A live evaluation record committed under `evals/results/`: at least 5 trials per case, Wilson intervals, `nirmaan eval rejudge` clean, and one run on a commercial API account with a recorded cost | ai-engineer |
| 10 | Export screen for each partner: country, end use, SCOMET and US EAR | legal-compliance |
| 11 | Written acceptance criteria per engagement: held-out testbench passes, proofs proven and covers reached, lint clean and no latches, the export tree with audit and tool versions, the partner's engineer signs the gate, and a known limits list | qa-evidence |
| 12 | A scope statement per engagement: the block is single-clock, the open-source tool boundary is stated, and the tools and configurations that ran are named. No "signoff", "tapeout-ready" or "verified" without that scope | design-architect |
| 13 | Tool versions pinned per engagement, and run records hold tool versions, not only paths | eda-tooling |
| 14 | A written data-handling agreement per partner: where the data lives, which provider and model see it, retention, deletion, and who has access | security |
| 15 | The open gate-integrity items (the token readable by same-user processes, the in-process firmware tests) are closed or disclosed in the engagement terms | qa-evidence |
| 16 | Results and model call costs recorded per engagement | finance-licensing |
| 17 | Slot C only: VeriTriage's parser checked on an anonymised sample log from the partner's simulator | verification-lead |
| 18 | The MCP server stays on local stdio and is never exposed over a network | security |
| 19 | A privacy notice for contact data under DPDP, and terms that cover IP work rather than only the studio's | legal-compliance |

## Founder to confirm

1. **GitHub link (FOUNDER TO CONFIRM).** Brand proposed one quiet line in
   Status or the footer: "Open source under Apache-2.0. Source on GitHub."
   Legal had no objection. This reverses the owner decision of 2026-09-28
   ("the repository is the factory, not the storefront"), so the council does
   not decide it. If confirmed, `test_the_site_does_not_send_visitors_to_github`
   and line 39 of the landing brief change in the same commit.
2. Merging the changes above, because they publish.
3. Spending: counsel for gate 6, a commercial API account for gates 7 and 9,
   and a private runner if gate 5 needs one.
4. Signing each partner agreement.
5. The copyright holder named in NOTICE: Om Patel, as in pyproject.toml, or a
   company entity.

## Open questions

| Question | Owner seat |
|---|---|
| Do the consumer Claude plan's terms differ from the commercial API's on retention and training? Does the API's server-side fallback stay within Anthropic models? | legal-compliance, with ai-engineer |
| Is the owner's ~/Documents folder synced to iCloud? | security |
| Do ARM's AMBA terms affect blocks we deliver with AMBA interfaces? Do the knowledge packs need spec issue numbers? | legal-compliance (for counsel) |
| Can the nirmaan.online contact page read a topic parameter? If so, the main CTAs could carry it | site-engineer |
| Do the internal prices hold up in at least five buyer interviews? | market-research |
| Does a slot C partner need Questa multi-line assertion parsing or real coverage databases (UCDB, VDB, UCD)? | verification-lead |
| When do we take partners outside India, and on what export terms? | legal-compliance, with finance-licensing |

## Dissent

- **Product Lead:** wanted the VeriTriage pilot as the first offer, two or
  three unpaid partners, and no page change until a partner signs. Overruled
  on all three, for the reasons above. Kept: the triage study runs on the
  partner's machines with model seats off.
- **Finance:** wanted three paid partners. Two are paid. The third slot is an
  unpaid accuracy study, because triage has no evidence yet to charge for.
- **Market Research:** wanted a free academic lab in the third slot. A lab
  qualifies only if it has a labelled regression on a commercial simulator.
- **Security:** wanted the first partner on open or synthetic RTL only. The
  chair took a spec-only block engagement instead, under every data gate.
  Security may hold that a spec is as sensitive as RTL; gates 8 and 14 apply
  to it in full.
- **Brand:** wanted a second CTA line, "Ask about design partnership", and a
  topic parameter on the contact link. The chair kept one label, "Talk to us",
  with an email subject, because the topic parameter is not verified.
- **QA:** asked that the evaluation batch come before any partner work. Gate 9
  does this. QA asked for the gate-integrity items to be closed or disclosed;
  the chair accepted disclosure.
- **Design Architect and EDA Tooling:** no dissent. Their limits (single-clock
  only, the open-source tool boundary, no signoff claims) are gates 12 and 13.

## Amendment (2026-10-16, before merge)

qa-evidence checked the new public copy against the code, as this record
requires. Two claims overstated it and were corrected above, in changes 4 and 6:

- VeriTriage has no scorer that reads a label file. An engineer marks each top
  diagnosis correct or incorrect (`FeedbackRecord`), so the copy now says we
  compare its top diagnosis with the partner's labels, one regression at a time.
- The tools gate RTL submissions only, and formal runs only when the work
  includes proofs. Spec submissions have no tool gate.

Every other new claim was checked and is true: every recorded run's files are
exported, pass or fail; VeriTriage runs without a model; its parsers read VCS,
Questa, Xcelium and UVM logs.

## Founder decisions (2026-10-16, after the meeting)

- Merged the changes above.
- **GitHub link:** confirmed. One line in the footer of the page and the 404:
  "Open source under Apache-2.0. Source on GitHub." A test keeps it to that one
  footer link.
- **Copyright holder:** the company, Nirmaan, in NOTICE and in pyproject.toml.
- **Spending:** none for now. Gates that need money (counsel for gate 6, a
  commercial AI account for gates 7 and 9, a private runner for gate 5) stay
  open, so no partner work starts until they pass. Development continues.
