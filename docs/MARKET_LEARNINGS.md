# Market learnings

What IP Nirmaan learned from studying the companies that work most like it,
what it decided to do about it, and the live backlog of improvements. Studied
and decided on 2026-10-18; the decisions, who disagreed and why, are in the
council record
[council/records/2026-10-18-market-learnings.md](../council/records/2026-10-18-market-learnings.md).
This doc carries the live status of the backlog; the record does not change.

## 1. How sources are used

- A company's claim about itself is its own claim, not a fact. Nothing here
  repeats one as fact.
- No company is named in this repository: no competitor, prospect or reference
  customer. Open-source projects, public standards and public datasets that we
  use or take a method from are named, with a source.
- The research report, the council's positions and the internal minutes are
  kept outside the repository.

## 2. What was studied, by kind

- Startups building AI agents for RTL design, verification and failure debug.
- The large EDA vendors' agent products.
- Register tooling vendors (register RTL, models and headers from a spec).
- A services firm that has run on open-source EDA for many years.
- An open-source silicon root-of-trust project (OpenTitan), for its public
  design and verification stages.
- An open-silicon shuttle platform that closed in 2025 and stranded its
  customers' projects.
- An Indian core and SoC generator firm.
- India's chip design incentive scheme and its EDA access programme.

## 3. What the market shows

1. **Proof is self-reported almost everywhere.** Hit rates without a
   denominator, benchmark scores on public sets, customer counts. No AI triage
   or verification product in the set has an independent accuracy result.
   Learnings 1, 4 and 11.
2. **Buyers ask where their design data goes before they ask for
   certificates.** Learning 3.
3. **Human oversight and gates are now common language.** What stays
   different is evidence that is open and can be checked again by the buyer.
   Learnings 2, 6, 7 and 8.
4. **A supplier's closure can strand its customers' work.** Deliveries must
   not depend on us to be re-checked. Learnings 2 and 15.
5. **Register generation is a mature, tooled market.** Our value on a register
   block is checking RTL against the map, not generating it. Learnings 5 and 9.
6. **Nobody in this set publishes prices.** The 2026-10-16 rule (no published
   price until two paid engagements and five buyer interviews) stands.

## 4. The 15 learnings

| # | Learning | Decision | Gate (for LATER) | Owner seat | Backlog |
|---|---|---|---|---|---|
| 1 | Record the first live evaluation batch, and publish failures with passes | ADOPT NOW | The founder runs it on the existing plan | ai-engineer | B12 |
| 2 | Every evidence pack re-runs without IP Nirmaan | ADOPT NOW for the engineering. ADOPT LATER for any promise | A CI test re-runs an exported pack from a clean directory and matches every verdict; then gate 6 (counsel) for any clause in terms | qa-evidence, with eda-tooling; legal-counsel for the clause | B3, B4, B5 |
| 3 | A data-handling note | ADOPT NOW as a facts-only document. ADOPT LATER for a link from the site | Gates 7, 8 and 14 pass, and the founder merges | security | B13 |
| 4 | Fix the triage study's metrics before the study | ADOPT NOW | None | verification-lead | B11 |
| 5 | Do not lead the partner offer with register blocks | ADOPT NOW, as a change of order, not of scope | None (the founder merges the copy) | product-lead, with brand-content | B2 |
| 6 | Named maturity stages per block | ADOPT NOW, changed (see below) | None | qa-evidence, with design-architect and dft-engineer | B14 |
| 7 | A public status page for the reference blocks | ADOPT LATER | Run records hold tool versions (B3); every value comes from a named CI run; the founder merges | site-engineer | B16 |
| 8 | Position on open evidence that anyone can re-run | ADOPT NOW for "open". ADOPT LATER for "re-run" | B5 is done | brand-content | B24 |
| 9 | Import register specs from standard formats | ADOPT LATER | A buyer interview or a partner names the format they send; for SystemRDL, legal-compliance checks the parser library's licence | design-architect, with firmware-engineer | B20 |
| 10 | Fixtures for the three commercial simulators' logs | ADOPT NOW for hand-written format fixtures. ADOPT LATER for real logs | Gate 17 of the 2026-10-16 record | eda-tooling, with verification-lead | B9, B10 |
| 11 | Run a public benchmark slice through the seat evaluator | ADOPT LATER | legal-compliance confirms the licence of each subset used (commercial subsets only, with attribution); B12 is done first | ai-engineer | B21 |
| 12 | Change the India pitch away from licence savings | ADOPT NOW, in the internal buyer-interview guide only | None | market-research | Internal |
| 13 | A labelled triage corpus with an academic lab | ADOPT LATER, in two parts | Part 1 (injected bugs on open cores): B9 done, a scorer that reads label files, a hashed held-out split. Part 2 (a lab): written data and licence terms, and the founder approves any co-authorship | verification-lead; partnerships for part 2 | B22 |
| 14 | A support promise, and a write-up per engagement | Write-up template: ADOPT NOW. Support promise: ADOPT LATER | Support: the founder sets the response target, inside counsel-reviewed terms (gate 6) | brand-content (template); partnerships (support) | B23 |
| 15 | Milestone billing; no dependence on one supplier | ADOPT NOW, as a principle | None | finance-licensing, with eda-tooling | B5, B28 |


## 5. What we will not copy

- A headline accuracy with no denominator, no labelling method, or a top-3 hit
  reported as success.
- Comparing our hand-made evaluation cases with other parties' benchmark
  numbers. Our rule stays: per case and per seat, n always shown.
- Borrowing another benchmark's "met PPA" as our yardstick. Our timing result
  is against a clock we chose; we have no power figure (`power.run` is
  CONTRACT_ONLY), so we claim area and timing only, never PPA.
- Deployment counts, investor-customers counted as customers, or unnamed
  "top ten" claims.
- Certificate badges we do not hold, "air-gapped", an unqualified "no
  egress", "never trains", or "your IP stays where it belongs" without saying
  where.
- "Silicon proven", "met PPA" or readiness-for-silicon wording for runs on open
  PDKs in CI. Coverage figures we do not measure.
- Another project's maturity labels without its coverage criteria.
- A seat or headcount licence, a free hosted tier, or a membership model as
  our business. Finance rejected membership: it needs a member base and a
  catalogue, which the 2026-10-16 record put "not now".
- Prepayment for anything that depends on a third party's schedule.
- Sponsored articles, booths or paid listings (spending).
- An LLM that changes VeriTriage's ranking.

## 6. Corrections

Errors the council found in the research and in our own docs, site and code.
No later doc should repeat them.

| # | What is wrong | Fact | Fixed by |
|---|---|---|---|
| C1 | The 2026-10-16 record lists "the tools and versions that ran" in every evidence pack, and the research proposes promising a re-run. Neither is backed | Run records hold each executable's resolved path, not its version (`src/nirmaan/integrations/eda.py:261`; `RunRecord` has no version field). The `test` job takes Verilator, Icarus and Yosys from apt, unpinned, and the RISC-V GCC is unpinned (`.github/workflows/ci.yml:41-42`). Only formal (OSS CAD Suite, sha256-checked) and place and route (image by digest) are pinned. Until B3 and B5 land, a pack names the tools that ran but not their versions | B3, B4, B5 |
| C2 | The research's data-handling list says "no egress" | False whenever a model seat is on: work packets carry up to 60,000 characters of each recorded file to the model provider (`src/nirmaan/runtime/context.py:30-31`), and VeriTriage `--ai` calls the API. True only with seats off: the default runtime is `unbound` and calls nothing. "Deletion at exit" is not true either: runs with no `workdir` leave directories in TMPDIR (`docs/GATE_INTEGRITY.md`, sections 5 and 6), and no network isolation for tool runs is built. "No training" is a provider term, not ours to promise | B13 |
| C3 | The research says the council keeps model seats off for partners | The rule is opt-in in writing, after gate 9; only slot C runs with seats off (2026-10-16 record) | Noted |
| C4 | Formal wording: VeriTriage can print "proven" for a bounded pass | `src/veritriage/parsers/formal_result.py:49` maps "pass" and "passed" to "proven", and line 104 prints "proven" without a depth. The rule (2026-10-16 record) is: a bounded check reads "no counterexample within N steps", never a proof. An unbounded result (`mode prove`, as for the reference blocks, `docs/IP_BLOCKS.md:54`) reads "proved for parameter points X and Y", because only those configurations ran | B8 |
| C5 | Place and route ran on one block, not on "the three reference blocks" (research), and the site's "whole flow" line can be read as including it | Place and route runs on the AXI4-Lite register block only (`tests/test_nirmaan_physical.py:49-51`; `docs/PD_FINAL.md`). There are four reference blocks: two register blocks (AXI4-Lite and APB), a FIFO and an arbiter (`docs/IP_BLOCKS.md:7-10`). `site/index.html` (Status, "Not yet") says the reference blocks "run through the whole flow" | B1 (founder merges), B19 |
| C6 | The research gives the register map's path as `src/nirmaan/integrations/regmap` | There is no such directory. The loader and model are `src/nirmaan/regmap.py` and `src/nirmaan/models/regmap.py`; `src/nirmaan/integrations/regmap.py` is the tool binding. The claim that the map reads only JSON is true (`src/nirmaan/regmap.py:35-36`). The research missed further limits: 32-bit registers only, four access types, no arrays or hardware-updated fields | Noted; B20 |
| C7 | The research implies fixtures exist for all three commercial simulators. The 2026-10-16 amendment says the parsers read Xcelium logs | Questa and VCS fixtures are tested. One fixture has an Xcelium header but no `*E,` line, so the Xcelium regex (`src/veritriage/parsers/simulation_log.py:37-41`) is never exercised. Every fixture is written by us. Verilator `%Error` lines are not parsed at all: the Verilator fixture yields zero events | B9, B10 |
| C8 | The research says block stages "map cleanly" onto PLANNED, EXECUTED, VERIFIED, APPROVED | Those are per-record assurance levels (`src/nirmaan/models/work.py`), not block maturity. Coverage is CONTRACT_ONLY | B14 |
| C9 | The research calls our gates "hash-chained and inspectable" as a selling point | The audit chain is unkeyed SHA-256 from a fixed start (`src/nirmaan/work/audit.py`). It detects a partial edit, not a full rewrite by someone with write access. Do not describe it as tamper-proof | B26 |
| C10 | The research proposes a new status generator in `scripts/status.py`, run nightly | `scripts/status.py` exists and generates the roadmap counts. CI runs on push and pull request, not nightly. A status page needs its own script fed by CI reports | B16 |
| C11 | `docs/DELIVERABLE_EXPORT.md` omits the `mbist_configuration` kind | `src/nirmaan/company/deliverables.py:49` routes it | B7 |
| C12 | The register block's C header is not in the evidence pack | `<block>_map.h` is written only into the job's work directory (`src/nirmaan/integrations/firmware.py:346-349`); no deliverable kind holds it | B6 |


Also weak in the research, and not to be repeated as fact: the register-tool
market size (one vendor's 2018 claim); the India incentive's 50% figure (a
secondary summary; whether outsourced block work is an eligible cost is not
established); a leading benchmark's pass rates (from a sponsored article); one
public benchmark's problem and category counts (its dataset card shows
different numbers).

## 7. Improvements backlog

Every item is open at merge. An item moves to "done" only when its owner seat
cites the check that closed it (a test ID, a CI run or a record path) in this
table. Items that change `site/**`, `.github/**`, `NOTICE` or a public claim
wait for the founder's merge. A milestone item reserves its number in
`docs/ROADMAP.md` first.

| # | Improvement | Owner seat | Gate | Files | Verified by | Status |
|---|---|---|---|---|---|---|
| B1 | Site "whole flow" line: name the four reference blocks and the stages they run through, and say place and route ran on the AXI4-Lite block only | brand-content; qa-evidence checks the claim | Founder merges (public claim) | `site/index.html`, `docs/LANDING_PAGE_BRIEF.md` | qa-evidence reads each claim against `docs/IP_BLOCKS.md` and `tests/test_nirmaan_physical.py`; `pytest tests/test_landing_site.py`; `python scripts/check_dashes.py` | open |
| B2 | Partner section: list a FIFO, an arbiter and bus glue before the register block (learning 5) | product-lead, with brand-content | Founder merges (partner section) | `site/index.html#partners`, `docs/LANDING_PAGE_BRIEF.md` | Same as B1; the words change only as this record allows | open |
| B3 | Record each tool's `--version` output and the executable's sha256 in every run record | eda-tooling; dft-engineer checks `dft.atpg` | None | `src/nirmaan/integrations/eda.py`, `docs/EDA_TOOLS.md` | A test asserts both fields for every executable in a lint, sim and `dft.atpg` record | open |
| B4 | Pin the `test` job's tools (the pinned OSS CAD Suite instead of apt) and the RISC-V GCC | eda-tooling | Founder approves (`.github/**` is a founder class) | `.github/workflows/ci.yml` | The "Tool versions" step matches the manifest | open |
| B5 | Each export writes `reproduce.sh` and `TOOLS.json` (download URLs with sha256, image digests); the script refuses on a version mismatch. DFT packs carry `patterns.json` and the seed; place and route packs name the image digest and each Liberty file's sha256 | qa-evidence, with eda-tooling, dft-engineer, physical-design-engineer | B3, B4 | `src/nirmaan/export.py`, `docs/DELIVERABLE_EXPORT.md` | A CI test runs `reproduce.sh` from the exported tree alone, in a clean directory, and matches every `result.json` verdict | open |
| B6 | Put the generated C header in the pack | firmware-engineer | None | `src/nirmaan/integrations/firmware.py`, `src/nirmaan/company/deliverables.py`, `docs/DELIVERABLE_EXPORT.md` | An export test: the header is byte-equal to `nirmaan regmap lower --to c-header` and compiles under the strict flags | open |
| B7 | Add `mbist_configuration` to the export doc | dft-engineer | None | `docs/DELIVERABLE_EXPORT.md` | Reviewer compares with `deliverables.py` | open |
| B8 | Formal wording: a bounded pass reads "no counterexample within N steps"; "proven" only for an unbounded result, with the parameter points | verification-lead | Verification reviews (gate wording) | `src/veritriage/parsers/formal_result.py`, `docs/FORMAL_GATE.md` | A test on a pass-with-depth input; a test on a prove-mode input | open |
| B9 | Parse Verilator `%Error` lines | verification-lead | None | `src/veritriage/parsers/simulation_log.py` | The existing Verilator fixture parses to at least one failure | open |
| B10 | Hand-written fixtures for an Xcelium `*E,` line and a Questa multi-line assertion, labelled as written by us; a test that each simulator has a failing fixture | eda-tooling, with verification-lead | None (real logs: gate 17) | `tests/fixtures/`, `tests/test_parsers.py`, `docs/EDA_TOOLS.md` | The new tests pass and fail on a broken regex | open |
| B11 | Pre-registered triage study protocol: unit, label written before the run, top-1 primary, unparsed logs count as misses, Wilson intervals, minimum N, frozen SHA and knowledge packs, the partner's manual baseline. Add `correct_rank` to `FeedbackRecord` | verification-lead | Committed before any slot C regression is scored | new `docs/VERITRIAGE_STUDY.md`, `src/veritriage/feedback/__init__.py` | Doc merged; a scorer test on `correct_rank` | open |
| B12 | The first recorded live evaluation batch, failures included; a failure class per failed trial (gate, judge, timeout, usage limit); a "public since" date per case, with results called an upper bound. The site's "not recorded" line changes to per-case results only after the record merges | ai-engineer | The founder runs the batch on the existing plan; the founder merges the site line | `evals/results/`, `src/nirmaan/evals/records.py`, `docs/LIVE_EVAL_EVIDENCE.md`, `evals/README.md`, later `site/index.html` | `nirmaan eval rejudge` clean on the record; `scripts/live_eval_gate.py`; a test with a fake usage-limit error | open |
| B13 | A facts-only data-handling document: a table of claim, control, file:line and test; a data-path table (which runtime and MCP tool sends what, where); the warning that VeriTriage's MCP `investigate` reads any path the user can read; "not yet, gate N" for everything unbuilt; "no egress" only as "while model seats are off" | security; legal-compliance reviews | Doc: none. Site link: gates 7, 8, 14 and the founder | new `docs/DATA_HANDLING.md` | A test fails when a cited path is missing; qa-evidence checks every claim | open |
| B14 | Block maturity stages, computed from recorded runs, printed in the export's `INDEX.md`, with the rules in section 2 | qa-evidence, with design-architect and dft-engineer | Milestone number reserved | `docs/IP_BLOCKS.md`, `docs/DELIVERABLE_EXPORT.md`, `src/nirmaan/export.py` | A test per stage; no stage without its records | open |
| B15 | A DFT section in the pack (fault model, universe size, `sampled`, undetectable and aborted counts, pattern count, seed), and a scan-ready check for RTL-only deliveries | dft-engineer | None | `docs/DELIVERABLE_EXPORT.md`, `src/nirmaan/integrations/dft.py` | An export test; `two_clocks.v` and `untestable.v` fail the scan-ready check | open |
| B16 | A static status page for the reference blocks, from CI reports of a named run: results as words, commit, run ID and date per row, "not run" where nothing ran; a `<caption>`, `th scope`, and a labelled, keyboard-focusable scroll region at 390 px | site-engineer; qa-evidence checks values; physical-design-engineer checks its rows | B3 and B17; the founder merges | new page under `site/`, new `site/blocks.json`, a new generator script, `site/sitemap.xml` | Page matches `blocks.json`; CSP hash test; the launch list passes on a preview | open |
| B17 | Site tests cover every page, not a hand-written list | site-engineer | None | `tests/test_landing_site.py` | A deliberately broken third page fails | open |
| B18 | Re-run launch-list items 12 to 14 and record the results | site-engineer | None | `site/README.md` | The recorded scores, with date and preview URL | open |
| B19 | Place and route on the FIFO and the arbiter; report the tightest clock that still meets timing at the slow corner beside the chosen one; a "what the open-PDK flow is not" box | physical-design-engineer | None | `tests/test_nirmaan_physical.py`, `tests/fixtures/pd/`, `docs/PD_FINAL.md` | The `physical-design` job on the head SHA | open |
| B20 | A register spec importer for the format a buyer names, through an importer registry, refusing unsupported constructs by name | design-architect, with firmware-engineer | A buyer names the format; for SystemRDL, legal-compliance checks the library licence | `src/nirmaan/regmap.py`, `docs/REGISTER_MAP_ADOPTION.md`, new `tests/test_nirmaan_regmap_import.py` | The APB register fixture round-trips to its JSON and passes `regmap.verify`; one refusal fixture per unsupported construct; a new format needs no core change | open |
| B21 | A small public benchmark slice through the seat evaluator, judged by our open tools | ai-engineer | legal-compliance licence check per subset; a "datasets" heading in `NOTICE` (founder class); B12 done | `evals/`, `docs/SEAT_EVALUATION.md`, `NOTICE` | A committed record under `evals/results/`; rejudge clean | open |
| B22 | An injected-bug triage corpus on open cores, named "injected bugs", never "real regressions" | verification-lead; partnerships for any lab | B9; a label-file scorer; a hashed held-out split. A lab: written terms and the founder | proposed `evals/triage/` | Results committed under `evals/results/` | open |
| B23 | A write-up template per engagement: what was asked, what was built, results including failures, tool versions, known limits. Published only with the partner's written consent and the founder's merge | brand-content, with legal-counsel | None for the template | new `docs/case-studies/README.md` | qa-evidence reads it against this record | open |
| B24 | Landing brief: add Indian fabless startups and design-services firms to the audience; "open evidence" wording; no "re-run" claim until B5, enforced by a test | brand-content | Founder merges any site copy | `docs/LANDING_PAGE_BRIEF.md`, `tests/test_landing_site.py` | The test fails if "re-run" appears in `site/` before the export writes tool versions | open |
| B25 | Verilator code coverage as a recorded run, so coverage criteria can later have a number | design-architect, with eda-tooling | Milestone number reserved | `src/nirmaan/integrations/eda.py`, `docs/EDA_TOOLS.md` | Recorded on `sync_fifo` at both parameter points | open |
| B26 | Audit chain wording: say what it detects (partial edits) and never "tamper-proof"; check the site's "append-only and hash-chained" line against the code | qa-evidence | Founder merges any site copy | `site/index.html`, `docs/` where the chain is described | qa-evidence cites `src/nirmaan/work/audit.py` for each sentence | open |
| B27 | Make gate 16 checkable: it fails if the project's cost report shows any unpriced model call; zero calls passes | finance-licensing | None | Internal records only | The check run per engagement | open |
| B28 | A list of fixes sent upstream to the open tools, started with the first real fix, never with placeholders | eda-tooling | Filing under the organization's name: the founder | `docs/EDA_TOOLS.md` | Each entry links the upstream issue or change | open |
