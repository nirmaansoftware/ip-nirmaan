# Council record: market learnings (2026-10-18)

The founder asked for the market to be studied, the companies that work most
like IP Nirmaan to be researched, and the learnings and possible improvements
to be documented after a council meeting. The founder delegated the judgement
to the council. The chair decided it in round 2 after reading all 18
positions. Facts were checked on origin/main (commit 5e80dd2, v1.25.0). The
research report, the positions and the internal minutes are kept outside the
repository. What stays with the founder is listed under "Founder to confirm".

This record decides what to learn. It changes no code, no gate semantics and
no site copy. Every improvement below is a backlog item with an owner seat, a
gate and a check; none of them is done by this record.

## Decisions

### 1. How "adopt" is used here

- **ADOPT NOW:** doable in this repository with no new spending and no outside
  gate. It goes into the backlog (section 5) in the order given there.
- **ADOPT LATER:** waits for a named gate, owned by a named seat.
- **REJECT:** not taken.

### 2. The 15 learnings

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

No learning was rejected. One practice was: a membership model as our
business (see section 3).

**Who wanted what, and why the chair chose.**

- **Learning 2.** Product Lead wanted the re-run promise added to "The partner
  gets" now, behind a gate. Legal Compliance, Legal Counsel and Brand wanted no
  promise before code and counsel. **Chosen:** build first, promise later. Run
  records hold executable paths, not versions (correction C1), so a promise
  today would be fake work.
- **Learning 3.** Security wanted the note public now, with every sentence
  citing a control. Legal Compliance and Legal Counsel wanted an internal
  draft now and a public note only after gates 7, 8 and 14. **Chosen:**
  Security's format, which states what the software does today and marks
  everything else "not yet, gate N". It makes no commitment, which meets
  Legal's concern. Commitments go in the written data agreement (gate 14). The
  site links to it only after those gates pass.
- **Learning 4.** QA wanted it later, until `FeedbackRecord` stores a rank and
  a time. **Chosen:** the protocol now. Top-3 is reported only after the record
  stores a rank; time to root cause only if the partner times its own triage.
- **Learning 5.** Product Lead, Design Architect, Firmware, Brand and
  Partnerships wanted it now. Market Research wanted to wait for three of five
  buyer interviews, because the premise rests on one vendor's own claims.
  **Chosen:** now, as an order change only. It is cheap to reverse, and our
  reason rests on our own code: the register map does not generate RTL; it
  lowers to a C header and Markdown and checks RTL against the map by
  co-simulation (`src/nirmaan/regmap.py`). Our value on a register block is
  independent checking, not generation. The timer is a firmware fixture only
  (`tests/fixtures/rtl/axil_timer/`), so the copy does not lead with it. If
  the interviews say otherwise, the order changes back.
- **Learning 6.** Design Architect, DFT and QA wanted it now with our own
  criteria. Verification Lead wanted it later, because coverage-based stages
  need coverage we do not measure. **Chosen:** now, with these rules: our own
  stage names, not another project's labels; each stage computed by code from
  recorded runs, never set by hand; a test per stage; no coverage criterion
  until `coverage.read` is AVAILABLE; DFT criteria as given by the DFT seat
  (scan inserted, `dft.check` and `dft.scan_sim` pass, stuck-at test coverage
  of at least 90% on the full fault universe, transition coverage only when
  at-speed was asked, March C- on every memory); and no stage that reads as
  ready for silicon. Stages are per block. They do not map onto the per-record
  assurance levels (correction C8).
- **Learning 7.** Site Engineer wanted it now, rescoped. DFT, Firmware, EDA
  Tooling and Product Lead wanted it later. **Chosen:** later, with Site
  Engineer's scope: data from CI reports for a named run, not the export
  tree; results as words; place and route rows only where it ran, "not run"
  elsewhere; a new data file, not `site/stats.json`.
- **Learning 9.** Design Architect wanted a CSV importer now; Firmware wanted
  SystemRDL now and spreadsheets later. **Chosen:** later, behind a buyer
  naming the format. The two seats disagree on which format comes first, which
  shows we do not yet know what buyers send. Their shared rule is adopted now
  as a design rule: an importer refuses, by name, every construct the map
  model cannot hold (hardware-updated fields, read-to-clear, write-one-to-set,
  arrays, register files, registers that are not 32 bits). It never
  approximates, because an approximated map would let `regmap.verify` pass
  RTL against the wrong spec. An imported map is a draft for review in the
  `register-map` stage.
- **Learning 10.** QA wanted it later only. **Chosen:** hand-written fixtures
  now, labelled as written by us. They prove our reading of each format, not
  compatibility with the real tools; gate 17 still checks a real log.
- **Learning 14.** Partnerships wanted a support target in the record now.
  **Chosen:** the founder sets it, because it is the founder's time and a
  contract term. It is not stated here.

### 3. What we will not copy

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

### 4. Corrections

The seats found these errors in the research and in our own documents, site
and code. Each is either fixed by a backlog item or noted here so that no doc
repeats it.

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

### 5. Improvements backlog

Each item has an owner seat that verifies it, a gate, the files it changes and
the check that closes it. None is done by this record. Items that change
`site/**`, `.github/**`, `NOTICE` or a public claim wait for the founder's
merge. A milestone item reserves its number in `docs/ROADMAP.md` first. The
live copy of this table, with status, is `docs/MARKET_LEARNINGS.md`.

| # | Improvement | Owner seat | Gate | Files | Verified by |
|---|---|---|---|---|---|
| B1 | Site "whole flow" line: name the four reference blocks and the stages they run through, and say place and route ran on the AXI4-Lite block only | brand-content; qa-evidence checks the claim | Founder merges (public claim) | `site/index.html`, `docs/LANDING_PAGE_BRIEF.md` | qa-evidence reads each claim against `docs/IP_BLOCKS.md` and `tests/test_nirmaan_physical.py`; `pytest tests/test_landing_site.py`; `python scripts/check_dashes.py` |
| B2 | Partner section: list a FIFO, an arbiter and bus glue before the register block (learning 5) | product-lead, with brand-content | Founder merges (partner section) | `site/index.html#partners`, `docs/LANDING_PAGE_BRIEF.md` | Same as B1; the words change only as this record allows |
| B3 | Record each tool's `--version` output and the executable's sha256 in every run record | eda-tooling; dft-engineer checks `dft.atpg` | None | `src/nirmaan/integrations/eda.py`, `docs/EDA_TOOLS.md` | A test asserts both fields for every executable in a lint, sim and `dft.atpg` record |
| B4 | Pin the `test` job's tools (the pinned OSS CAD Suite instead of apt) and the RISC-V GCC | eda-tooling | Founder approves (`.github/**` is a founder class) | `.github/workflows/ci.yml` | The "Tool versions" step matches the manifest |
| B5 | Each export writes `reproduce.sh` and `TOOLS.json` (download URLs with sha256, image digests); the script refuses on a version mismatch. DFT packs carry `patterns.json` and the seed; place and route packs name the image digest and each Liberty file's sha256 | qa-evidence, with eda-tooling, dft-engineer, physical-design-engineer | B3, B4 | `src/nirmaan/export.py`, `docs/DELIVERABLE_EXPORT.md` | A CI test runs `reproduce.sh` from the exported tree alone, in a clean directory, and matches every `result.json` verdict |
| B6 | Put the generated C header in the pack | firmware-engineer | None | `src/nirmaan/integrations/firmware.py`, `src/nirmaan/company/deliverables.py`, `docs/DELIVERABLE_EXPORT.md` | An export test: the header is byte-equal to `nirmaan regmap lower --to c-header` and compiles under the strict flags |
| B7 | Add `mbist_configuration` to the export doc | dft-engineer | None | `docs/DELIVERABLE_EXPORT.md` | Reviewer compares with `deliverables.py` |
| B8 | Formal wording: a bounded pass reads "no counterexample within N steps"; "proven" only for an unbounded result, with the parameter points | verification-lead | Verification reviews (gate wording) | `src/veritriage/parsers/formal_result.py`, `docs/FORMAL_GATE.md` | A test on a pass-with-depth input; a test on a prove-mode input |
| B9 | Parse Verilator `%Error` lines | verification-lead | None | `src/veritriage/parsers/simulation_log.py` | The existing Verilator fixture parses to at least one failure |
| B10 | Hand-written fixtures for an Xcelium `*E,` line and a Questa multi-line assertion, labelled as written by us; a test that each simulator has a failing fixture | eda-tooling, with verification-lead | None (real logs: gate 17) | `tests/fixtures/`, `tests/test_parsers.py`, `docs/EDA_TOOLS.md` | The new tests pass and fail on a broken regex |
| B11 | Pre-registered triage study protocol: unit, label written before the run, top-1 primary, unparsed logs count as misses, Wilson intervals, minimum N, frozen SHA and knowledge packs, the partner's manual baseline. Add `correct_rank` to `FeedbackRecord` | verification-lead | Committed before any slot C regression is scored | new `docs/VERITRIAGE_STUDY.md`, `src/veritriage/feedback/__init__.py` | Doc merged; a scorer test on `correct_rank` |
| B12 | The first recorded live evaluation batch, failures included; a failure class per failed trial (gate, judge, timeout, usage limit); a "public since" date per case, with results called an upper bound. The site's "not recorded" line changes to per-case results only after the record merges | ai-engineer | The founder runs the batch on the existing plan; the founder merges the site line | `evals/results/`, `src/nirmaan/evals/records.py`, `docs/LIVE_EVAL_EVIDENCE.md`, `evals/README.md`, later `site/index.html` | `nirmaan eval rejudge` clean on the record; `scripts/live_eval_gate.py`; a test with a fake usage-limit error |
| B13 | A facts-only data-handling document: a table of claim, control, file:line and test; a data-path table (which runtime and MCP tool sends what, where); the warning that VeriTriage's MCP `investigate` reads any path the user can read; "not yet, gate N" for everything unbuilt; "no egress" only as "while model seats are off" | security; legal-compliance reviews | Doc: none. Site link: gates 7, 8, 14 and the founder | new `docs/DATA_HANDLING.md` | A test fails when a cited path is missing; qa-evidence checks every claim |
| B14 | Block maturity stages, computed from recorded runs, printed in the export's `INDEX.md`, with the rules in section 2 | qa-evidence, with design-architect and dft-engineer | Milestone number reserved | `docs/IP_BLOCKS.md`, `docs/DELIVERABLE_EXPORT.md`, `src/nirmaan/export.py` | A test per stage; no stage without its records |
| B15 | A DFT section in the pack (fault model, universe size, `sampled`, undetectable and aborted counts, pattern count, seed), and a scan-ready check for RTL-only deliveries | dft-engineer | None | `docs/DELIVERABLE_EXPORT.md`, `src/nirmaan/integrations/dft.py` | An export test; `two_clocks.v` and `untestable.v` fail the scan-ready check |
| B16 | A static status page for the reference blocks, from CI reports of a named run: results as words, commit, run ID and date per row, "not run" where nothing ran; a `<caption>`, `th scope`, and a labelled, keyboard-focusable scroll region at 390 px | site-engineer; qa-evidence checks values; physical-design-engineer checks its rows | B3 and B17; the founder merges | new page under `site/`, new `site/blocks.json`, a new generator script, `site/sitemap.xml` | Page matches `blocks.json`; CSP hash test; the launch list passes on a preview |
| B17 | Site tests cover every page, not a hand-written list | site-engineer | None | `tests/test_landing_site.py` | A deliberately broken third page fails |
| B18 | Re-run launch-list items 12 to 14 and record the results | site-engineer | None | `site/README.md` | The recorded scores, with date and preview URL |
| B19 | Place and route on the FIFO and the arbiter; report the tightest clock that still meets timing at the slow corner beside the chosen one; a "what the open-PDK flow is not" box | physical-design-engineer | None | `tests/test_nirmaan_physical.py`, `tests/fixtures/pd/`, `docs/PD_FINAL.md` | The `physical-design` job on the head SHA |
| B20 | A register spec importer for the format a buyer names, through an importer registry, refusing unsupported constructs by name | design-architect, with firmware-engineer | A buyer names the format; for SystemRDL, legal-compliance checks the library licence | `src/nirmaan/regmap.py`, `docs/REGISTER_MAP_ADOPTION.md`, new `tests/test_nirmaan_regmap_import.py` | The APB register fixture round-trips to its JSON and passes `regmap.verify`; one refusal fixture per unsupported construct; a new format needs no core change |
| B21 | A small public benchmark slice through the seat evaluator, judged by our open tools | ai-engineer | legal-compliance licence check per subset; a "datasets" heading in `NOTICE` (founder class); B12 done | `evals/`, `docs/SEAT_EVALUATION.md`, `NOTICE` | A committed record under `evals/results/`; rejudge clean |
| B22 | An injected-bug triage corpus on open cores, named "injected bugs", never "real regressions" | verification-lead; partnerships for any lab | B9; a label-file scorer; a hashed held-out split. A lab: written terms and the founder | proposed `evals/triage/` | Results committed under `evals/results/` |
| B23 | A write-up template per engagement: what was asked, what was built, results including failures, tool versions, known limits. Published only with the partner's written consent and the founder's merge | brand-content, with legal-counsel | None for the template | new `docs/case-studies/README.md` | qa-evidence reads it against this record |
| B24 | Landing brief: add Indian fabless startups and design-services firms to the audience; "open evidence" wording; no "re-run" claim until B5, enforced by a test | brand-content | Founder merges any site copy | `docs/LANDING_PAGE_BRIEF.md`, `tests/test_landing_site.py` | The test fails if "re-run" appears in `site/` before the export writes tool versions |
| B25 | Verilator code coverage as a recorded run, so coverage criteria can later have a number | design-architect, with eda-tooling | Milestone number reserved | `src/nirmaan/integrations/eda.py`, `docs/EDA_TOOLS.md` | Recorded on `sync_fifo` at both parameter points |
| B26 | Audit chain wording: say what it detects (partial edits) and never "tamper-proof"; check the site's "append-only and hash-chained" line against the code | qa-evidence | Founder merges any site copy | `site/index.html`, `docs/` where the chain is described | qa-evidence cites `src/nirmaan/work/audit.py` for each sentence |
| B27 | Make gate 16 checkable: it fails if the project's cost report shows any unpriced model call; zero calls passes | finance-licensing | None | Internal records only | The check run per engagement |
| B28 | A list of fixes sent upstream to the open tools, started with the first real fix, never with placeholders | eda-tooling | Filing under the organization's name: the founder | `docs/EDA_TOOLS.md` | Each entry links the upstream issue or change |

### 6. Changes to the 2026-10-16 gates

- **Gate 9 is split.** 9a: a live evaluation record on the existing plan
  (B12). 9b: one run on a commercial API account with a recorded cost, needed
  only before partner work with model seats on. Partner work with seats off
  needs 9a only. (ai-engineer proposed it; no seat objected.)
- **Gate 13** is unchanged and is now known to be open in code (C1). B3 and B4
  close it.
- **Gate 16** gains the check in B27.
- **The pack definition** in the 2026-10-16 record ("the tools and versions
  that ran") stays the target. Until B5 lands, a pack states that versions are
  not yet recorded, in its known-limits list.

### 7. Billing principle

Payments follow written acceptance points (gate 11), never a third party's
schedule. Nothing that depends on a shuttle, a hosted service or one model
vendor's plan is paid in advance. No delivery depends on IP Nirmaan's own
services. Figures, splits and discounts stay internal.

### 8. Where it is recorded, and naming

- This record, in `council/records/`.
- A public doc, `docs/MARKET_LEARNINGS.md`: the learnings in our own terms,
  what we will not copy, the corrections, and the live backlog table.
- The research report, the positions and the internal minutes stay outside
  the repository.
- **No company is named in the public repository**: no competitor, prospect
  or reference customer. Open-source projects, public standards and public
  datasets that we use or take a method from may be named, with a source, as
  may the commercial tools whose log formats our parsers read (as the
  repository already does).
  Market Research would have named a closed platform as a cited fact; QA would
  have allowed names as cited company claims. **Chosen:** Legal Compliance's
  rule, because another company's claims on our pages go stale and carry
  trade mark and disparagement risk with no gain for a buyer. The founder
  decides any public name.

## Changes to make now (one documentation PR)

One branch, `docs/market-learnings`. Documentation only: no code, no site, no
gate change. It touches `council/**`, so the founder merges it. Run
`python scripts/check_dashes.py` and `python scripts/status.py --check`.

1. **`council/records/2026-10-18-market-learnings.md`** (new): this record.
2. **`council/records/README.md`**: add the line
   `- [2026-10-18: market learnings](2026-10-18-market-learnings.md)`.
3. **`docs/MARKET_LEARNINGS.md`** (new), outline:
   1. Purpose: what was studied and why, the date, and that this doc carries
      the live backlog. Link to this record.
   2. How sources are used: a company's claim about itself is its claim, not a
      fact; no company named; open projects and datasets named with sources.
   3. What we studied, by kind, not by name: AI agent firms for RTL design,
      verification and debug; large EDA vendors' agent products; register
      tooling vendors; an open-source EDA services firm; an open-source silicon
      root-of-trust project (OpenTitan, named as an open project); an
      open-silicon shuttle platform that closed in 2025; an Indian core and SoC
      generator firm; the Indian incentive and EDA-access schemes.
   4. What the market shows, in six short points, each tied to a learning:
      proof is self-reported almost everywhere; buyers ask where their data
      goes before they ask for certificates; human oversight and gates are now
      common language, so what stays different is evidence that is open and
      re-checkable; a supplier's closure can strand its customers' work;
      register generation is a mature tooled market; nobody in this set
      publishes prices.
   5. The 15 learnings and their decisions (the table in section 2 above,
      without the dissent).
   6. What we will not copy (section 3 above).
   7. Corrections (section 4 above), so no later doc repeats them.
   8. The improvements backlog (section 5 above) with a Status column, all
      "open" at merge. An item moves to "done" only when its owner seat cites
      the check that closed it (test ID, CI run or record path).
4. **`docs/ROADMAP.md`**, "Next milestones": add one bullet:
   "**Market learnings backlog** (council record 2026-10-18): items B1 to B28
   in `docs/MARKET_LEARNINGS.md`, starting with tool versions in run records
   and the reproduce script (B3 to B5). Design-partner readiness still needs
   gates 5 to 19 of the 2026-10-16 record."

No other file changes in this PR. Site copy (B1, B2) goes in its own PR, which
the founder merges.

**Order after this PR (recommended):** B1 and B2 (one founder-merge PR); B7,
B8, B9, B10; B3, then B4, then B5 and B6; B11 before any slot C contact; B12
when the founder chooses to run it; B13; B17 before B16; the rest as gates
open.

## Founder to confirm

1. Merging the documentation PR (it touches `council/**`).
2. Merging the site copy PR (B1, B2), and later B12's site line, B16, B24 and
   B26.
3. Running the first live evaluation batch on the existing plan (B12).
4. The support response target for the partner terms (learning 14).
5. The payment split and the partner discount (internal).
6. Sending every outreach and interview message.
7. Any lab agreement or co-authorship, any membership (only if its fee is
   confirmed zero in writing), and anything filed upstream under the
   organization's name.
8. Spending, which stays at none: counsel (gate 6), a commercial API account
   (gates 7 and 9b), a private runner (gate 5), and any silicon run.
9. Any public company name.

## Open questions

| Question | Owner seat |
|---|---|
| What register spec format do buyers send? | market-research (interviews) |
| Do buyers generate register RTL themselves? (tests learning 5) | market-research |
| Is outsourced block work an eligible cost under the Indian incentive scheme, and what invoice does it need? | tax-accounts, with market-research (for a chartered accountant) |
| What is the licence of the SystemRDL parser library? | legal-compliance |
| Which public benchmark subsets are licensed for commercial use, and does their harness run on our open tools? | legal-compliance, with ai-engineer |
| Does a slot C partner need Questa multi-line assertions or real coverage databases? (carried from 2026-10-16) | verification-lead |
| Is an open-source silicon project's tools tier, or a benchmarking coalition, free to join? | partnerships (asks); finance-licensing (checks) |

## Dissent

- **Security:** wanted the data note public and linked now. It is written now,
  facts only; the site link waits for gates 7, 8 and 14.
- **Legal Compliance and Legal Counsel:** wanted the data note internal until
  those gates. Overruled for the doc, because it states only what the code
  does and makes no commitment. Kept: no commitment and no site link before
  the gates.
- **Product Lead:** wanted the re-run promise in "The partner gets" now, behind
  a gate. Overruled: no promise before B5 passes and counsel reviews it.
- **Market Research:** wanted the register-block reorder to wait for
  interviews, and named facts about one closed platform in public. The reorder
  goes ahead as reversible; names stay out.
- **Verification Lead:** wanted maturity stages later. Taken now with no
  coverage criteria, which was the concern.
- **QA:** wanted the triage protocol and the simulator fixtures later. Both
  taken now, with top-3 deferred and fixtures labelled as ours. QA's
  corrections are all in section 4.
- **Site Engineer:** wanted the status page now. It waits for recorded tool
  versions and the test change in B17.
- **Design Architect and Firmware:** wanted a register importer now, in
  different formats. It waits for a buyer to name the format; their refusal
  rule is adopted now.
- **Partnerships:** wanted the support target in this record. The founder sets
  it.
- **Finance, Tax, DFT, Physical Design, EDA Tooling, AI Engineer, Brand:** no
  dissent on the decisions; their limits are rules in sections 2, 3 and 6.
