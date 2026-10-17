# Council record: teams and the PR review mechanism (2026-10-17)

Status: decided by the chair; the founder answered on 2026-10-17 (see
"Founder decisions" at the end). The mechanism itself is PLANNED, not live:
see `docs/REVIEW_MECHANISM.md`.

The founder asked for one PR review mechanism for Nirmaan and IP Nirmaan: a
review by a higher authority in the PR's team (key 1), then by the top level
(key 2), then automatic merge. The Nirmaan meeting decides the shared mechanism.
This council decides IP Nirmaan's teams and states what the mechanism must do
to fit hardware work. The chair decided in round 2 after reading all 15
positions. Paths were checked against the tracked tree (`git ls-files`).
Internal minutes and positions are kept outside the repository.

Corrected fact used throughout: agent sessions use the GitHub login
`patel-om`, a write collaborator. `nirmaansoftware` (the founder) is the only
admin. Agents cannot change or bypass rulesets, but can post any commit status
and add or remove labels. GitHub merge queues are for organizations only.

Agent keys are reviews, nothing more. In any status, comment or page they never
stand for a person's decision, a release, or a claim that a design is ready to
be made in silicon.

## 1. Teams

| Team | Key 1 | Members | Role |
|---|---|---|---|
| Council | chair holds key 2 for every PR. Key 1 on Council paths: security (control files), qa-evidence (records, seat files) | | Rules, seats, records |
| Silicon Design | design-architect | proposed: dft-engineer, physical-design-engineer, firmware-engineer | RTL, DFT, physical design, firmware |
| Verification | verification-lead | qa-evidence | Gates, formal, evals, VeriTriage |
| EDA and Platform | eda-tooling | security, ai-engineer | CI, tools, runtime, MCP, catch-all |
| Product and Site | product-lead | site-engineer, brand-content, market-research | Site, README, scope |
| Business | legal-compliance (licences, notices, third-party code and text); finance-licensing (prices, commercial terms, spend) | legal-counsel, tax-accounts, partnerships | Licences and commercial terms |

- One key-1 verdict per owning team. Members' checklists run inside the lead's
  review and are cited in it. legal-counsel, tax-accounts, partnerships and
  market-research hold no key and own no paths.
- The three new seats are proposals. Their names wait for the founder. No
  separate RTL seat: RTL review is design-architect's own expertise.
- The top seat stays "chair"; the team is "Council", not "Executive".

### Path ownership map

`.github/review-teams.yml`. Rules are read from `main`, never from the PR head.
A PR's owning teams are every team whose rule matches a changed file.

| Path | Owner (key 1) | Co-owner |
|---|---|---|
| `council/**`, `CLAUDE.md`, `.claude/**`, `.github/review-teams.yml` | Council | |
| `tests/fixtures/rtl/**` | Silicon Design | Verification |
| `tests/fixtures/fw/**`, `tests/fixtures/pd/**` | Silicon Design | |
| `src/nirmaan/integrations/dft*.py`, `firmware*.py`, `regmap.py`, `spec_check.py` | Silicon Design | |
| `src/nirmaan/integrations/physical.py`, `pd_parsers.py` | Silicon Design | EDA and Platform |
| `src/nirmaan/integrations/firmware_soc/**`, `firmware_harness/**` | Silicon Design | |
| `src/nirmaan/integrations/firmware_soc/serv/**`, `firmware_soc/picorv32.v` | Silicon Design | Business |
| `src/nirmaan/regmap.py` | Silicon Design | |
| `evals/rtl/**`, `evals/firmware/**`, `evals/spec/**` | Verification | Silicon Design |
| `docs/IP_BLOCKS.md`, `DESIGN_AGENTS.md`, `DESIGN_INTELLIGENCE.md`, `DFT*.md`, `PHYSICAL_DESIGN.md`, `*FIRMWARE*.md`, `REGISTER_MAP*.md` | Silicon Design | |
| `tests/test_nirmaan_{dft*,firmware*,riscv_*,physical,regmap*,sta_antecedents,design_agents,more_blocks}.py`, `tests/test_{apb_regs,axi4_lite,rr_arbiter,sync_fifo}_fixture.py` | Silicon Design | |
| `src/veritriage/**`, `src/nirmaan/evals/**`, `src/nirmaan/vplan.py`, `src/nirmaan/integrations/vplan.py`, `src/nirmaan/integrations/veritriage.py`, `src/nirmaan/eval_proposals.py` | Verification | |
| `src/veritriage/design/**` | Verification | Silicon Design |
| `evals/**` (rest), `tests/fixtures/gate_integrity/**`, `tests/fixtures/vplan/**`, `tests/fixtures/eval_results_synthetic/**` | Verification | |
| `tests/test_nirmaan_{gate_integrity,formal_gate,gates_*,evals,eval_proposals,live_eval,verification_plan*}.py`, `tests/test_veritriage_*.py` | Verification | |
| `docs/VERIFICATION_PLAN*.md`, `FORMAL_GATE.md`, `GATE_INTEGRITY.md`, `LIVE_EVAL_EVIDENCE.md` | Verification | |
| Gate files: `src/nirmaan/integrations/eda.py`, `src/nirmaan/work/policy.py`, `src/nirmaan/work/engine.py`, `src/nirmaan/runtime/tools.py`, `src/nirmaan/company/workflows.py`, `scripts/check_*.py`, `scripts/live_eval_gate.py` | EDA and Platform (eda.py, scripts) or catch-all | Verification |
| `.github/**`, `scripts/**`, `pyproject.toml`, `src/nirmaan/integrations/eda*.py`, `tests/fixtures/eda/**`, `tests/test_ci.py`, `tests/test_status_docs.py`, `docs/TEST_CI_HARDENING.md` | EDA and Platform | |
| `src/nirmaan/runtime/**`, `src/nirmaan/mcp/**`, `docs/CLAUDE_CODE_RUNTIME.md`, `docs/NIRMAAN_MCP.md` | EDA and Platform | |
| `site/**`, `README.md`, `docs/LANDING_PAGE_BRIEF.md`, `tests/test_landing_site.py` | Product and Site | |
| `scripts/status.py` | EDA and Platform | Product and Site |
| `LICENSE`, `NOTICE`, `**/LICENSE*`, `site/assets/fonts/OFL-*.txt`, `council/records/*commercial*` | Business | |
| `site/index.html` partner section (between marker comments) | Product and Site | Business |
| `docs/ROADMAP.md` scope and ordering sections (between marker comments) | Product and Site | |
| `**` (every file no rule above matches) | EDA and Platform (catch-all) | |

Ledger files add no owning team when the PR also touches other paths:
`context.md`, `docs/history/**`, the "Milestone numbers" table and the
`status:begin` to `status:end` block in `docs/ROADMAP.md`, and `site/stats.json`
when it equals the output of `scripts/status.py --release`. CI
(`tests/test_status_docs.py`) covers their consistency.

Content rules (a path cannot see them): a diff that adds a price, currency
amount, discount, royalty, payment or tax wording, or a partner or client name
adds Business as an owning team. A diff that touches a gate (see the key-1
list for Verification) adds Verification.

**Coverage test** (`tests/test_review_teams.py`, owner eda-tooling, verified by
qa-evidence). It fails when: a tracked file maps to no team; a rule matches no
tracked file (this is how the draft's paths `src/nirmaan/design*` and
`src/nirmaan/tools*`, which match nothing, would have been caught); a lead or
member names a seat with no file in `council/`; a marker comment a content rule
relies on is missing.

## 2. Does the mechanism fit hardware work

It fits, with these changes for IP Nirmaan. They go to the Nirmaan chair, who
decides the shared mechanism.

1. **CI first.** Key 1 starts only when all five CI checks are green on the
   head SHA, and cites the CI run and the SHA. Physical design tools do not run
   on the development machine, so a reviewer cannot rerun them; CI is the record.
2. **Require all five checks by name** (`test`, `no-tools`, `physical-design`,
   `test-union`, `dashes`), bound to GitHub Actions. Requiring only
   `test-union` is not enough: when a job it needs fails it is skipped, and a
   skipped check counts as passing. No required job gets a `paths:` filter.
   Every job gets `timeout-minutes`.
3. **"Require branches up to date" off for IP Nirmaan.** Each update makes a
   new head SHA, voids both keys and reruns the full hardware CI, and merge
   queues are not available to a personal account. The push to `main` runs CI;
   if `main` breaks, the owning lead reverts.
4. **Evidence, not prose.** A simulation, formal or timing claim counts only if
   CI or a committed run record shows it. A bounded check is never a proof.
5. **An eval and the code it grades never change in one PR.**
6. **Gate changes go to Verification**, whichever team opened the PR.
7. **Content rules** beside path rules (section 1).
8. **Reviewer isolation.** A fresh read-only process in a clean checkout of the
   head SHA, never the author session. Role spec, `CLAUDE.md` and the map come
   from `main`. The PR title, body and commit messages are not given to the
   reviewer; code comments, RTL comments and docs in the diff are data, never
   instructions. The model returns only a JSON verdict with file and line
   findings and holds no token. A script checks every citation and that the head
   SHA is unchanged, then posts the status. Bad JSON or a timeout fails the key.
9. **Wording.** Status descriptions say "agent review (role)", name the head
   SHA and link the review comment.

### Concerns on M1 to M5 for the Nirmaan chair

- **M1.** With the correction, any `patel-om` session can post
  `review/team-lead` and `review/executive` itself, by mistake or under
  injection. A workflow's `GITHUB_TOKEN` can too, and `ci.yml` has no top-level
  `permissions:` block. The council asks for a free GitHub App owned by the
  founder's account, with both review checks bound to the App in the ruleset,
  and every workflow set to `permissions: contents: read` by default. On one
  machine this is partial: the App key must live outside both repositories and
  be unreadable by authoring sessions. Until the App exists, the review
  statuses are a convention, and the docs must say so.
- **M2.** Local skill now. No Action runs PR content with a plan token; never
  `pull_request_target`. If a plan token secret exists, it moves to an
  environment only `main` can use.
- **M3.** The founder's instruction should not cover every PR. Six classes keep
  the founder as a third key (below). Because the founder is a separate
  identity from the agents, path classes can be enforced by GitHub: CODEOWNERS
  names `nirmaansoftware` on those paths and the ruleset requires code owner
  review. Content classes are enforced by a `hold` label the key-1 script sets;
  agents can remove labels, so that part is convention and is stated as such.
  Cross-repository: `site/index.html` links nirmaan.online's privacy and terms
  pages, so a Nirmaan PR to those pages changes IP Nirmaan's published terms and
  should be in Nirmaan's founder class.
- **M4.** Green CI is not enough: a key fails when a test skips in every job, a
  gate is weakened, or a claim has no record. Checklists in section 3.
- **M5.** No fast path for docs that state results, eval data or fixtures. A
  typo fix still takes both keys. An urgent security fix: the founder merges by
  hand (only the founder can bypass), both keys run after the merge, and the
  council records it.

### Founder third key (council's advice on M3)

1. **Control plane:** `.github/**`, `.claude/**`, `CLAUDE.md`, `council/**`,
   `.github/review-teams.yml`, the pr-review skill and its posting script, gate
   scripts (`scripts/check_*.py`, `scripts/live_eval_gate.py`).
2. **Gate semantics:** the gate files in section 1, and any change to required
   check names or `NIRMAAN_REQUIRE_EDA`.
3. **Licence and third-party:** `LICENSE`, `NOTICE`, any vendored licence file,
   new third-party code or specification text, the licence field, classifiers
   or dependencies in `pyproject.toml`.
4. **Commercial:** any price, discount, rate, payment, invoice or tax wording;
   commercial terms on a public page; anything that adds spend.
5. **Public names and claims:** on `site/**` or `README.md`, a new or changed
   public name, a named client, partner or person, the partner section, launch
   status lines, or a new capability, performance or compliance claim in the
   hero or meta tags. Ordinary copy edits are not in this class.
6. **Export-control sensitive content**, as flagged by legal-compliance (scope
   to be confirmed by counsel).

Partner deliverables never go through this mechanism; a named person signs
them.

## 3. Checklists

### Every key 1 (base)

Reads the diff, the code and the CI logs for the head SHA; never the PR text.
Fails when:
- a claim in a commit, doc or comment has no record behind it (test ID, CI job
  on this SHA, tool log, or committed eval record path);
- a "fixes X" change has no test that fails on the base and passes on the head
  (the reviewer runs it on both);
- any CI job is not green on the head SHA, or a test skips in every job;
- a gate is weakened without saying so;
- a bounded check is reported as a proof, or a simulation passes without the
  nonce verdict line;
- counts are typed by hand where `scripts/status.py --write` makes them, or a
  milestone ships without its history file;
- any text uses the words "sign-off", "silicon-ready", "timing closure" or
  "tape-out".

The review comment holds: the role and a statement that this was a fresh
session; base and head SHAs; every claim with a verdict and a citation; the
commands run with exit codes; what was not checked, listed as `not_run`. A
comment whose SHA differs from the head is void.

### Silicon Design (design-architect)

Fails when: a pass claim has no tool run or CI log; a real-tool test is skipped
(`-rs` output); a `_tb_fail.v` negative control, an assertion, a `.sby` (prove
mode, both parameter points) or an `.sdc` is weakened; interface spec,
microarchitecture, register map and firmware headers disagree; RTL changes with
no testbench and `.sby` run in `test` or `physical-design`. Member checklists:
DFT (scan, ATPG, MBIST results from a run), physical design (STA and DRC from
CI on Nangate45), firmware (driver built strict and run against the RTL).

### Verification (verification-lead)

Fails when: a gate is loosened (a `max_<metric>` limit, required parameters,
`when_produced`, the testbench pass contract in `docs/GATE_INTEGRITY.md`
section 1); a `*_fail.v` fixture is removed or stops failing; a coverage or
eval number has no committed `evals/results/<run>/` record; a new tool is not
`CONTRACT_ONLY`; an eval and the code it grades change together.

### EDA and Platform (eda-tooling, with security and ai-engineer)

Fails when: a required check is renamed, removed, path-filtered or made to
skip; a required tool becomes a skip; a workflow lacks top-level
`permissions:`; an action is not pinned by SHA, an image not by digest, or a
download not checked by sha256; `pull_request_target` appears; `${{ github.event.* }}`
appears in `run:`; a new third-party action or a paid tool or runner is added.
On `src/nirmaan/runtime/**` and `src/nirmaan/mcp/**`, security's checklist
(customer data, tool surfaces) runs and is cited; ai-engineer's covers prompts
and model seats.

### Product and Site (product-lead, with site-engineer and brand-content)

Fails when: a capability claim is not backed by the code (a planned or
`CONTRACT_ONLY` tool), and qa-evidence has not checked each such claim; the
diff's launch-list items (1 to 20, `site/README.md`) are not named;
Lighthouse items are marked PASS without a measured run (they say "not
measured"); `nirmaan.css`, `site.js` or `hero.js` differ from a named Nirmaan
commit; copy breaks voice rules (no hype, no invented customers or numbers).

### Business (legal-compliance or finance-licensing by subject)

Fails when: licence or notice text changes, or third-party code or spec text
is added, without a matching NOTICE entry; a price, discount or commercial term
appears (none is published now, per the 2026-10-16 record); what a partner
gives, gets or pays changes; anything adds spend; real registration, turnover,
bank or invoice figures appear. A Business pass is an agent review, never legal
advice or a legal clearance, and always leads to the founder (classes 3, 4).

### Key 2 (chair)

- Key 1 ran for every owning team, computed from `main`'s map, on this head SHA.
- Every key-1 finding is fixed or answered; the teams' verdicts agree with each
  other.
- The scope fits `docs/ROADMAP.md` and `CLAUDE.md` (number reserved, design doc,
  history file, `status.py --write`).
- Founder classes detected: `hold` set or code owner review pending; key 2
  never passes a founder-class PR on its own.
- Nothing a public repository must not hold.
- Agent wording only: no "approved by", "sign-off" or "tape-out".

## 4. Rollout

| Step | What | Owner seat | Files |
|---|---|---|---|
| R0 | Founder decides seat names, M3 classes, and creates the App | founder | none |
| R1 | Path map and coverage test | eda-tooling (file), each lead (its rows), qa-evidence (verifies) | `.github/review-teams.yml`, `tests/test_review_teams.py`, markers in `site/index.html` and `docs/ROADMAP.md` |
| R2 | CI hardening: top-level permissions, timeouts, supply-chain test | security, eda-tooling | `.github/workflows/ci.yml`, `.github/workflows/live-eval.yml`, a CI test |
| R3 | Vendored-file hash test with source commit, and the current drift reconciled in Nirmaan first | site-engineer | `tests/test_landing_site.py`, `site/nirmaan.css`, `site/site.js` |
| R4 | Seats and checklists: new member seats, key-1 checklists in lead files, teams in the council README, mechanism doc saying keys are agent reviews | chair, design-architect (new seats), each lead | `council/*.md`, `council/README.md`, `docs/REVIEW_MECHANISM.md`, `CLAUDE.md` |
| R5 | pr-review skill and posting script | ai-engineer (skill, prompts), security (script) | `.claude/skills/pr-review/`, `scripts/` |
| R6 | Dry run on real PRs, keys not yet required: seeded bugs, planted false claims, prompt injection; every one caught, results recorded | qa-evidence, ai-engineer | review records |
| R7 | Founder sets the ruleset: five CI checks, two review checks bound to the App, code owner review for founder classes, admin-only bypass, strict off; CODEOWNERS; auto-merge on | founder; eda-tooling prepares, security checks | `.github/CODEOWNERS`, repository settings |

Team order inside R7: EDA and Platform, then Verification, then Silicon
Design, then Product and Site (only after R3), then Business (founder class in
practice). Every R step is a PR under today's rule (the founder merges) until R7.

## Dissent

- **Chair vs CTO.** The draft proposed a CTO. brand-content: the product's
  simulated organization already has a CTO and an executive tier
  (`src/nirmaan/company/org_chart.py`), and the site sells it. No seat argued
  for CTO. Chosen: "chair", team "Council", to keep the company and the
  product apart.
- **Business lead.** The draft had finance-licensing alone. finance-licensing
  and legal-counsel asked for a split. Chosen: split by subject, because
  legal-compliance already owns the legal gates in the 2026-10-16 record.
- **Founder third key.** The founder's instruction covers every PR merge.
  ai-engineer, security, qa-evidence, legal-compliance, legal-counsel,
  finance-licensing, brand-content, product-lead, partnerships and tax-accounts
  asked for a third key on some classes. Chosen: six classes, detectable by path
  or content. security's wider list (all of `scripts/**` and `pyproject.toml`)
  was narrowed to gate scripts and licence or dependency changes, so routine
  work still merges on two keys. The founder decides.
- **Branches up to date.** The shared draft turns it on; eda-tooling asked for
  off. Chosen: off for IP Nirmaan, reasons in section 2.
- **Bypass actors.** eda-tooling asked for none, on the premise that agents
  share the founder's identity. The corrected fact removes that premise.
  Chosen: the founder alone, as admin, for emergencies, provided the founder's
  login is not reachable from agent sessions (security verifies).
- **Roadmap ownership.** The draft gave all of `docs/ROADMAP.md` to Product and
  Site. product-lead asked to own only scope and ordering. Chosen: product-lead's
  split.
- **Seat count.** market-research would add an RTL seat; design-architect would
  not. Chosen: no RTL seat.
- **Security as its own key.** security asked to be a required reviewer on
  control paths; design-architect asked for one verdict per team. Chosen: one
  verdict, with security's checklist required and cited inside it.

## Gates

| Gate | Owner seat |
|---|---|
| Coverage test passes on `main` with no unmapped file and no dead rule | eda-tooling |
| Every workflow has top-level `permissions:` | security |
| Vendored site files match a named Nirmaan commit | site-engineer |
| Dry run catches every planted claim, bug and injection | qa-evidence |
| Code owner review blocks a founder-class test PR | eda-tooling |
| Agent sessions cannot reach the App key or the founder's login | security |

## Open questions

- Is there a plan token secret in this repository? (security)
- Does Vercel deploy `site/` on every merge to `main`? (site-engineer)
- Export-control scope and Arm specification terms. (legal-compliance, for
  counsel; counsel is a founder decision)
- What buyers expect to see in public PR history. (market-research, in the
  buyer interviews)

## Founder decisions (2026-10-17, after the meeting)

- **Third-key classes:** all six classes in section 2 are kept as written.
  Nirmaan's own six classes (A to F) are kept too; they are decided in
  Nirmaan's record, not here.
- **New seats:** dft-engineer, physical-design-engineer and firmware-engineer
  are confirmed as Silicon Design members. Their seat files are added in a
  later PR, with the key-1 checklists (rollout step R4).
- **Build:** the rollout starts. R2 (CI hardening) and this record go first, each
  as its own PR that the founder merges.

Still with the founder: creating the GitHub App; the ruleset and turning on
auto-merge (R7); replacing "the founder merges anything that publishes" for PR
merges in `CLAUDE.md`. Until the App and the ruleset are live, a review status
on a PR is a convention, not an enforced check.

The shared mechanism (both repositories) is decided in Nirmaan's meeting and
described in `docs/operations/pr-review.md` in `nirmaansoftware/Nirmaan`.
