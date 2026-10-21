# Council record: capability build-out and hierarchy (P0, 2026-10-18)

Chair: council chair (agent apex). Round 1: all 18 seats gave written positions
(product-lead, verification-lead, design-architect, dft-engineer,
physical-design-engineer, firmware-engineer, eda-tooling, ai-engineer,
market-research, finance-licensing, legal-compliance, security, qa-evidence,
brand-content, site-engineer, legal-counsel, tax-accounts, partnerships).
Code read on ip-nirmaan main at 5e80dd2. The chair rebuilt the organization
read only (`build_organization()`, repository venv) to check every count below;
the command and its output are in the appendix, so any reader can reproduce them.

This is a council record, not a decision in the product's sense. A key is an
agent review, never a person's decision. The founder can overrule any item, and
the founder items in section 12 wait for the founder (see the note of
2026-10-20 in section 12 for who reviews them now).

Wording note (legal-counsel, tax-accounts): this record says "organisation" and
"shared services". It does not call IP Nirmaan a separate company or describe a
corporate group; no entity fact is recorded (section 7).

**The plan and what this record decides.** The meeting's brief was the
capability build-out plan (version 3), an internal planning document. It, the
round-1 positions and the internal minutes are kept outside this public
repository, as for every council record (council/README.md, "Records"). A plan
section number below only names where a statement came from: section 1 quotes
each plan statement it corrects, and every rule this record adopts or replaces
is written out here in full, so no reader needs the plan. What the council
decided is in this record's own sections 2 to 14; where the plan and this
record differ, the record states the decision (the founder can overrule it, as
any item). Nothing in the repository reads or depends on the plan.

## 1. Facts corrected before deciding

The plan's statements in the left column do not match the code. The record
cites the code, not the plan (qa-evidence must-have).

Note, 2026-10-20: the right column is the code at 5e80dd2, when the meeting
read it. Milestones since (M56 seniority band, M57 hierarchy fixes) changed
some of it, as this record decided; for example Commercial is now one
placeholder division.

| Plan says | Code says (FACT) |
|---|---|
| "19 seats and a chair" | 18 seats plus the chair (council/README.md) |
| CEO spans 5 | CEO has 9 direct reports: CTO, COO, CPO, Chief Architect, Chief of Staff, and the placeholder VPs of Sales, Marketing, Customer Success and Partnerships (the nine placeholder business divisions are declared at org_chart.py:333-347; the four sponsored by the CEO at :342-345) |
| Documentation under the COO | Technical Documentation is a department sponsored by the CPO (org_chart.py:312) |
| Add CPU, GPU, AI accelerator, memory, perf modelling to Architecture | They exist: architecture.micro.cpu, gpu, npu, dsp, cache, memctrl and architecture.system.memory, performance (org_chart.py:85-104) |
| Add hardware security to Security | It exists: security.hardware (org_chart.py:263) |
| (not mentioned) | Security architecture is held twice (org_chart.py:91 and :267); security verification is held twice (:187 and :268) |
| EDA tooling under Software | Team infrastructure.eda sits under the COO (org_chart.py:289) |
| Span limits are an addition | 26 of the 69 roles that have reports exceed 8, because every IC ladder reports to its team or department head (max 37, the DFT Engineering manager). Counted on units, 11 units are outside 3 to 8 (section 3) |
| Depth has room for a VP group | Depth is already 6 below the Board (Board, CEO, C-level, VP, Director, Manager, IC) |
| Chair and CEO drawn as two apexes | One apex: the chair speaks for exec.ceo (section 6) |
| Practised processor skills from PicoRV32 and SERV runs | Those are vendored, unmodified cores used as firmware hosts (`fw.soc_test`, category software); no tool models architecture, and microarchitecture stages accept only a review record (workflows.py:194-196) |
| A site count change is a founder merge (plan section 8) | site/stats.json is a ledger file when it equals `scripts/status.py --release`; the founder class on site/** covers names, claims, meta and title tags and the partners section (review-teams.yml) |

## 2. Decisions by agenda item

### Item 1. Hierarchy: CHANGE plan 2.7

The product's org (`src/nirmaan/company/org_chart.py`) stays the one hierarchy
for engineering work. Plan section 2.7 (the plan's hierarchy) is replaced by
the tree in section 4, which is the built org plus the changes decided here.
Every change is listed with the PR stage that lands it.

Decided changes:
1. **CEO within span.** The four CEO-level placeholder divisions become one
   placeholder Commercial division sponsored by the CPO, with departments
   Sales and Partnerships (the two placeholders merged), Marketing, Customer
   Success and Applications Engineering. CEO span becomes 5.
2. **No duplicates.** Security architecture and security verification are owned
   by Security only: architecture.system.security and verification.security
   are removed (their roles move to the Security teams). Placement, CTS and
   Routing (three teams holding one skill) become one Place and Route team with
   three practices.
3. **Deepen, do not re-add.** CPU, GPU, NPU, DSP, cache, memory controller,
   memory and performance practices stay where they are and are deepened in
   their wave. Computer arithmetic enters as a skill held by the
   microarchitecture and RTL arithmetic practices, not as a new practice
   (architecture.micro is at 8). architecture.micro.noc stays: it owns the NoC
   microarchitecture task shown on the public hero.
4. **Splits for span.** Interface Architecture (12 practices) splits into
   on-chip (AXI, ACE, CHI, APB, AHB, NoC interfaces, custom) and a new External
   Interface Architecture department (PCIe, CXL, DDR, USB, Ethernet). DFT (one
   team of 9 practices) becomes three teams: Scan and ATPG, Memory Test and
   BIST, Test Access. Technical Documentation and Quality and Process (one team
   each) become three teams each. IP Integration and Delivery gains IP
   Qualification and Deliverable Kits teams.
5. **New areas as placeholders.** FPGA Design (Design) and Foundation IP
   (standard cells, memory compilers and SRAM, I/O and ESD; Implementation)
   enter in P1. Domain IP (Design), Architecture Research (emerging compute,
   knowledge only), and three CTO divisions (Analog, RF and Photonics;
   Technology and Packaging; Silicon Lifecycle) enter with the P2 coverage map.
   The CTO is then at 8, the maximum: a ninth area joins an existing division
   or goes to a council meeting. The plan's "Mixed-signal and Technology" VP
   group is rejected because it adds a seventh layer.
6. **New active teams for seats with no unit.** AI Platform under Engineering
   Infrastructure (model seats, providers, evaluation, usage) and Platform and
   Product Security under Security (customer design confidentiality, MCP and
   CLI surfaces, supply chain).
7. **Documentation stays under the CPO.** Specs, register documents and manuals
   are part of the evidence pack (product-lead). Datasheets and integration
   guides join Documentation; technical marketing goes to Marketing.
8. **EDA tooling has one home:** infrastructure.eda under the COO, including
   CAD and flow engineering. Software keeps developer tools for firmware (SDK,
   compiler, debugger) and gains an accelerator compilers practice, knowledge
   only.
9. **DFT and Silicon Lifecycle boundary.** Implementation DFT owns on-chip test
   structures and pattern generation and grading (scan, ATPG, MBIST, LBIST,
   JTAG, compression, fault models). Silicon Lifecycle owns applying patterns to
   silicon: the ATE program, burn-in, scan diagnosis on silicon, yield, failure
   analysis. Lifecycle's "test" is named "Production Test". Hardware security
   stays in Security (the chart wins over the plan's Appendix A).
10. **Activation rule.** A unit added after this record enters as PLACEHOLDER.
    It becomes ACTIVE only in a PR that shows one of its skills uses an
    AVAILABLE tool and has an eval case judged by that tool. A unit in the
    chart is never an offer.
11. **Sibling practices with identical skill sets** (for example the STA,
    signoff, power and project-management practices) get distinct skills or
    merge during their department's wave. This is a wave exit criterion, not a
    P1 change.
12. **Product lines** (processor, interface, foundation, security, subsystems)
    are tags on skills in the P2 coverage map, not units, so there is one line
    of management.

Dissent: market-research wanted product lines as "staffs" units under the CPO.
partnerships wanted Commercial under the CEO; the chair placed it under the CPO
because it keeps the CEO at 5, puts every customer-facing answer (product,
documentation, applications, marketing) under one executive, and matches the
Product and Site review team. eda-tooling wanted CAD and flow engineering in
Software; the chair kept one home where the code, the seat and CI already are,
since a split recreates two owners of the flow wrappers. dft-engineer preferred
mapping physical-design-engineer to Director, Physical Design (see item 4).

### Item 2. Review keys: DERIVE AS DATA, CHAIR STAYS KEY 2 TODAY

The derivation is adopted as data checked by a test; it is not read by the
review script. Full rule in section 5. Outcome today: key 2 is the chair on
every PR, because no CTO, COO, CPO, Chief Architect or VP-level key-2 seat
exists. Switching any team's key 2 off the chair is a later founder-class PR.

Dissent: ai-engineer and firmware-engineer wanted derived keys live now (with a
fallback). design-architect, dft-engineer and qa-evidence wanted the chair kept
until real holders exist; the outcome matches theirs while the data is built.
security's bypass finding decided where the values live.

### Item 3. Shared services: SHARED FUNCTION, PER-REPOSITORY SEATS

Section 7. No seat argued for fully separate functions.

### Item 4. One seat, one org role; practice leads: ACCEPT, WITH A SEAT MAP OUTSIDE THE PRODUCT CATALOGUE

Section 6. The seat map lives in `council/seat-map.yml` (founder class), never
in `src/nirmaan/`. org_chart.py remains the product's modelled company shown on
the public site; no seat name, deputy or vote is written into it. The org gains
units only where the modelled company needs the function (AI Platform,
Platform and Product Security, the Commercial placeholders), so an assignment
of a seat never changes a public tile.

Practice leads: a practice lead is a seat file `council/<slug>.md` (founder
class) with an "In a review" key-1 checklist, mapped in the seat map with
`vote: false`. It holds key 1 on its unit's paths, is asked for owner facts
(council step 4), and gives no round-1 position. Practice leads are added or
promoted in the founder-class hiring PR at the start of their wave.

Dissent: none on the principle. brand-content's condition (keep the seat map
outside the catalogue) is adopted.

### Item 5. Capability model: ACCEPT WITH THE FIXES IN SECTION 9

### Item 6. Pilot and waves: CHANGE. Pilot is RTL small-block design

Section 10.

Dissent: design-architect (Processor architecture scoped to architecture.micro),
eda-tooling and market-research (Processor first: processor IP is the largest
design-IP category), firmware-engineer (firmware and drivers), verification-lead
(Verification), physical-design-engineer (Implementation earlier).

### Item 7. Delivery: ACCEPT SESSION-DRIVEN AUTHORING, WITH THE ORDERING IN SECTION 11

### Item 8. Coverage: ACCEPT every addition below as P2 input

Section 13.

## 3. The span rule

1. **What is counted.** The span of a manager position is the number of child
   units directly below it plus explicit roles reporting to it. For an
   executive it is the units it heads or sponsors plus the executives reporting
   to it. Generated IC ladder roles are not counted: a leaf unit's ladder (at
   most four rungs and a tech lead) is that leaf's staffing.
2. **Range: 3 to 8.** The minimum is 3 (plan 2.3.5). Plan section 10's
   "manager only at 4 or more ICs" is withdrawn for IP Nirmaan because it
   counts roles, not units.
3. **Placeholders count.** A head is accountable for a placeholder's capability
   map, so excluding them would hide areas a head owns. A placeholder must
   declare a mission and the coverage-map area it holds; an empty box is not a
   unit.
4. **Exempt by definition:** leaf units (no child units) and staff roles (an
   explicit executive role that heads or sponsors no unit; today only the Chief
   of Staff).
5. **Depth:** at most 6 layers below the Board. The Board is the founder.
6. **Exceptions are data.** A unit outside 3 to 8 carries `span_exception` with
   a reason and a review date in org_chart.py. A test fails on an exception
   that is no longer needed. After the P1 changes the org passes with **zero
   exceptions**.
7. **Layers mapped to the code:** L0 Board (founder); L1 CEO (chair seat); L2
   C-level (CTO, COO, CPO, Chief Architect, Chief of Staff); L3 VP (division);
   L4 Director (department); L5 Manager and Tech Lead (team); L6 ICs (ladder).
   A division with no departments has teams directly under the VP.

Units outside 3 to 8 today (FACT, chair's run): architecture.interface 12,
design 2, design.integration 1, documentation 1, documentation.writing 9,
implementation 2, implementation.dft 1, implementation.dft.engineering 9,
implementation.pd 9, quality 1, verification 9; and the CEO at 9. Each is fixed
by a decided change in item 1.

Dissent: firmware-engineer wanted the builder changed so each practice's
senior becomes an L5 lead over its ladder; rejected because it adds a seventh
layer below the Board. eda-tooling wanted placeholders excluded from the count.

## 4. The IP hierarchy (code plus decided changes)

Marks: [P1] lands in P1; [P2] with the coverage map; [W2] in wave 2;
(placeholder) not routable, no ladder. Seats in the right column of section 6.

```text
Board / Owner (founder) L0
└─ CEO  [seat: chair]                                            span 5
   ├─ Chief Architect: heads Architecture                         span 4, 5 at P2
   │  ├─ System Architecture: soc, ip, memory, interconnect, power,
   │  │    performance, software  [P1: security practice moves to Security]
   │  ├─ Microarchitecture: cpu, gpu, npu, dsp, noc, cache, memctrl, peripheral
   │  ├─ Interface Architecture (on-chip): axi, ace, chi, apb, ahb, noc, custom  [P1 split]
   │  ├─ External Interface Architecture: pcie, cxl, ddr, usb, ethernet  [P1 new]
   │  └─ Architecture Research (placeholder): emerging compute, knowledge only  [P2]
   ├─ CTO                                                          span 5, 8 at P2
   │  ├─ VP Design Engineering  [seat: design-architect]           span 3, 4 at P2
   │  │  ├─ RTL Engineering: architecture, design, interface, cdc, low_power,
   │  │  │    quality, automation  (pilot)
   │  │  ├─ IP Integration and Delivery: IP Integration, IP Qualification,
   │  │  │    Deliverable Kits  [P1: two teams new]
   │  │  ├─ FPGA Design (placeholder): open flow, vendor flows, FPGA mapping  [P1]
   │  │  └─ Domain IP (placeholder): codecs and ISP, wireless baseband,
   │  │       networking silicon  [P2]
   │  ├─ VP Verification  [seat: verification-lead]
   │  │    [P1: 8 teams, security verification moves to Security]
   │  │    [W2: five departments]
   │  │  ├─ Methodology and Signoff: architecture, planning, signoff
   │  │  ├─ Simulation: simulation, coverage, gate-level and power-aware,
   │  │  │    emulation and prototyping (knowledge only)
   │  │  ├─ Formal and Static: formal, equivalence, cdc
   │  │  ├─ Debug and Regression: debug, triage (VeriTriage), regression
   │  │  └─ Processor and Accelerator: ISA compliance, reference models and
   │  │       scoreboards, accelerator verification (knowledge only)
   │  ├─ VP Silicon Implementation  [seat: physical-design-engineer]   span 3
   │  │  ├─ Physical Design: synthesis, floorplan, power_plan, place_and_route,
   │  │  │    sta, power, signoff  [P1: placement, CTS, routing merged]
   │  │  ├─ Design for Test  [seat: dft-engineer]: Scan and ATPG, Memory Test
   │  │  │    and BIST, Test Access  [P1 split]
   │  │  └─ Foundation IP (placeholder): standard cells, memory compilers and
   │  │       SRAM, I/O and ESD  [P1]
   │  ├─ VP Software  [seat: firmware-engineer]: firmware, registers,
   │  │    diagnostics, validation, performance, developer tools
   │  │    (+ accelerator compilers practice, knowledge only)
   │  ├─ VP Security: hardware, secure boot, cryptography, threat modelling,
   │  │    security architecture, security verification, vulnerability
   │  │    management, Platform and Product Security [seat: security]  [P1 new team]
   │  ├─ Analog, RF and Photonics (placeholder)  [P2]
   │  ├─ Technology and Packaging (placeholder): Process and PDK use,
   │  │    Packaging, Board and Systems  [P2]
   │  └─ Silicon Lifecycle (placeholder): Post-silicon Validation, Production
   │       Test, Yield and Reliability, Functional Safety  [P2]
   ├─ COO                                                          span 7
   │  ├─ VP Engineering Infrastructure  [seat: eda-tooling]: Build and CI,
   │  │    Compute Platform, EDA and Regression (one home for EDA, CAD and
   │  │    flow), AI Platform [seat: ai-engineer]  [P1 new team]
   │  ├─ VP Quality and Process  [seat: qa-evidence]: three teams  [P1 split]
   │  └─ Finance [seat: finance-licensing], Legal, Human Resources,
   │       Procurement, Operations (placeholders)
   ├─ CPO  [seat: product-lead]: heads Product and Programs          span 5
   │  ├─ Product Management, Program Management, Project Management
   │  ├─ Technical Documentation: three teams  [P1 split]
   │  └─ VP Commercial (placeholder)  [P1, replaces four CEO-level placeholders]
   │     ├─ Sales and Partnerships  [seat: partnerships]
   │     ├─ Marketing: Brand and Content [seat: brand-content], Web
   │     │    [seat: site-engineer], Market Research [seat: market-research]
   │     ├─ Customer Success
   │     └─ Applications Engineering
   └─ Chief of Staff (staff role, no reports)

Shared services (outside the product org; council/seat-map.yml):
   Legal [seats: legal-compliance, legal-counsel], Tax and Accounts
   [seat: tax-accounts]; each reports to the founder until a shared-services
   head is defined with the Nirmaan studio.
```

Exact slugs and the team-level cut inside a department are set by the PR that
lands it; the span and depth tests are the check. A PR that renames a role
shown in the public hero (`nirmaan plan "Create a 4-port AXI-to-NoC bridge."`)
must update the hero or keep the title.

## 5. The key rule

1. **One source of reviewers.** The review script reads only
   `.github/review-teams.yml` on main (founder class). It never reads
   org_chart.py, which is not founder class. Deriving reviewers from the chart
   would let one PR change the chart and auto-merge, and a second PR be
   reviewed by the reviewers the first chose (security).
2. **Derived values are stored, then checked.** Each team in review-teams.yml
   gains `unit:` (the lowest common unit of its lead seats' org roles and their
   interim `covers`, or `shared` for a shared-services role) and `key2:`. A test
   recomputes both from `build_organization()` and the seat map. A chart change
   that alters a derived value fails CI until review-teams.yml is changed,
   which waits for the founder. `scripts/review_map.py` stays standard library
   only.
3. **The tests are founder class.** `tests/test_review_teams.py` and the new
   seat-map test join the control-plane class (CODEOWNERS and
   `founder_classes`). (Note, 2026-10-19: the same day, the Founder Proxy
   change removed `.github/CODEOWNERS`, and `tests/test_review_teams.py` now
   fails if one is added back, so the class is `founder_classes` in
   `.github/review-teams.yml` alone.)
4. **Derivation.** Key 2 for a PR is the nearest role above the lowest common
   unit of all owning teams that is held by a seat with a key-2 checklist and a
   passing seeded-defect review set, and that is not a key-1 holder on that PR.
   If none, the chair. Key 2 is always at least one rung above every key 1.
5. **Floor.** Key 2 is the chair, on the strongest model, for: every founder
   class (control plane, gate semantics, licence and third-party, commercial,
   public names and claims, export control); `evals/**`,
   `src/nirmaan/evals/**`, the levels generator and its records;
   `src/nirmaan/mcp/**`; `src/nirmaan/runtime/**`; and paths that handle
   customer design data (listed by security in P1-05).
6. **Today.** No CTO, COO, CPO, Chief Architect or VP key-2 seat exists, so every
   derived `key2` is `chair`, and the script's constant stays. The first
   non-chair key 2 needs a council decision after the pilot retrospective, a
   seeded-defect review set passed by that seat (ai-engineer), and a
   founder-class PR.
7. **Content keys are kept.** Derivation never removes: Verification key 1 on
   gates, evals, scorers and the levels generator; Product and Site key 1 on
   site/**, README.md and the roadmap scope markers; Business key 1 on licence,
   third-party and commercial content.
8. **Deputies.** Named as data in the seat map. A deputy runs only for key 1 and
   only after an infrastructure failure: the reviewer call failed after its
   retry. Never after invalid output, a failed validation or a fail: those
   stop for the founder, as today, because a diff can cause invalid output on
   purpose. A deferred key 2 moves up one rung; above the chair is the founder.
   The script change waits until the loop's records show a deferral a deputy
   would have resolved (gate G14). Plan rule 2.3.6 is replaced by this.

## 6. The seat map

`council/seat-map.yml`: each seat maps to exactly one org role or one shared
role; no role has two seats.

| Seat | Org role | Interim covers | Deputy | Vote |
|---|---|---|---|---|
| chair | exec.ceo | | (founder) | chairs |
| product-lead | exec.cpo | | brand-content | yes |
| design-architect | design.vp | architecture, implementation, software paths, until a seat holds key 1 inside each | physical-design-engineer | yes |
| verification-lead | verification.vp | | qa-evidence | yes |
| dft-engineer | implementation.dft.director | | | yes |
| physical-design-engineer | implementation.vp | | dft-engineer | yes |
| firmware-engineer | software.vp | | | yes |
| eda-tooling | infrastructure.vp | | ai-engineer | yes |
| ai-engineer | infrastructure.ai (AI Platform manager) | | | yes |
| security | security.platform (Platform and Product Security manager) | | | yes |
| qa-evidence | quality.vp | | | yes |
| market-research | Commercial, Marketing, Market Research manager | | | yes |
| brand-content | Commercial, Marketing, Brand and Content manager | | | yes |
| site-engineer | Commercial, Marketing, Web manager | | | yes |
| partnerships | Commercial, Sales and Partnerships director | | | yes |
| finance-licensing | finance.vp | | tax-accounts | yes |
| legal-compliance | shared.legal (IP supplement: export control, specification terms, IP licensing) | | legal-counsel | yes |
| legal-counsel | shared.legal.counsel | | | yes |
| tax-accounts | shared.tax (IP supplement: licences, royalties, export of services) | | | yes |

Rules:
- legal-compliance never maps to the Quality "Compliance" practice (functional
  safety standards, not legal).
- A key-1 lead maps to a head role; a member may map to any role.
- A seat's key-1 scope is its unit's paths plus its `covers`. Each cover ends
  when a seat inside that unit holds key 1 there (Processor wave for
  Architecture; Implementation wave for physical-design-engineer and
  dft-engineer; Firmware wave for firmware-engineer).
- Review-team membership is a review relation, not line management (plan
  2.3.3); members need not sit under their team's unit.
- The test checks: every file in council/ except README.md and records maps
  once; every role exists in the built org or is a declared shared role; no
  duplicates; every deputy is a seat in the same review team.

## 7. Shared services

- **Shared:** one legal policy (copyright, licences, DPDP, claims) and one master
  template set with a schedule per organisation; one tax and accounts question
  list for the chartered accountant with one answer per question; the brand
  and site platform (components, mark, privacy and terms), owned in the
  Nirmaan repository; the review platform design; one private plan-usage
  ledger with one cap.
- **Per organisation:** prices and the commercial model (finance-licensing for
  IP); positioning and copy; the sales pipeline (contact intake and tooling
  shared, with a written routing rule: one owner per lead, handoff recorded);
  IP keeps the export-control, specification-terms and IP-licensing
  specialisms in its legal seat.
- **Seats stay per repository,** because key 1 must be a seat file in that
  repository. Shared services are shared records and rules, not new seats.
- **Books, invoices and returns follow the legal entity,** whatever the chart
  says.
- **Open founder question: one legal entity or two.** Nothing here depends on the
  answer until an agreement is drafted for signature, an invoice is raised, or
  costs are shared across entities. Until then every draft carries the
  contracting party as `[FOR COUNSEL / FOUNDER]`.
- No public page uses "group" in a way that implies a corporate group, and none
  calls IP Nirmaan a separate company until an entity exists.

## 8. Where our build-out lives

- **org_chart.py and skills.py** hold the product's modelled company. The
  capability build-out adds skills and units there, because they are what the
  product's agents use on customer work.
- **council/seat-map.yml, council/*.md and review-teams.yml** hold who runs this
  repository. None of it is imported by `src/nirmaan/`.
- **Public tiles.** Unit and role tiles describe the model and move with it at
  release. The skills tile ("140 engineering skills") is relabelled by a
  founder decision before any skill from this programme is counted, so
  knowledge-only skills never read as capability (gate G8). No level tile.
  Knowledge documents are never counted as "verification knowledge packs".
- Plan section 8's sentence on site counts is corrected to match the code
  (section 1), not made true by a new path rule.

## 9. Capability model

1. **Names.** The existing level-derived scale (`Proficiency`: awareness,
   working, proficient, expert; models/org.py:128, derived from the ladder
   rung in organization.py:490) is renamed to a seniority band, and the word
   "expert" leaves the code and its output. The record-based scale is the
   **evidence level**: Knowledge, Practised, Proven. Neither appears on a public
   page without records. The checker's output is called a **check record**.
2. **Skill card and knowledge document.** The skill card is the skills.py entry,
   rendered at most 2,000 characters. Long-form knowledge is one document per
   skill at `knowledge/<division>/<skill_id>.md`, at most 12,000 characters,
   cited from the skill by a new knowledge source kind. Larger topics split.
3. **How knowledge reaches a seat.** Today only source names reach the prompt
   (runtime/context.py:229). Before any knowledge document is written, P1 adds
   the loading path: a cited document's text enters the packet; the domain
   scope is capped at 40,000 characters; the packet must fit the seat's
   context limit; a seat over budget declines with a recorded reason, never a
   silent cut. A test runs over every workflow seat. The pilot runs an
   ablation (the same cases with and without knowledge) to show the content
   changes outputs.
4. **Tier is computed:** practising when the skill uses an AVAILABLE tool,
   otherwise knowledge only. CONTRACT_ONLY tools give knowledge only.
5. **Knowledge level:** the files exist and a check record (a different session,
   sources read) is committed.
6. **Practised level:** only from committed, tool-judged eval result records in
   `evals/results/`. Each record names model id, skill digest (card plus
   document), case, judge tool, head SHA and outcome. A case lists the skills it
   judges (`EvalCase.skills`), and only those skills get credit; one stage pass
   never raises every skill of the stage. Threshold: at least 5 trials, a 95
   percent Wilson lower bound of at least 0.5, and a clean rejudge. A level is
   stale when the model or the skill digest changes. Replays, human
   attestations (`dv_ran`), and rubric judging never raise a level; rubric
   results are shown separately, labelled, with n.
7. **Must-fail scorers.** Before a verification or RTL skill can be Practised,
   its case set includes negative controls: mutant RTL must fail the agent's
   testbench or assertions, clean RTL must pass, covers must be reached; for
   RTL, a failing testbench control and formal proofs at each parameter point.
   DFT is graded by a recorded fault simulation; physical design by the
   physical-design CI job on the head SHA, naming the PDK ("Practised
   (sky130hd)").
8. **Proven level:** only from the product's own seat run records on delivered
   work that passed review. Authoring-session PRs never count. Today nothing is
   Proven, and nothing is Practised (no file under evals/results/ has been
   committed).
9. **Eval cases come first,** in their own PR, written by a different session
   from the knowledge they grade. Held-out inputs never appear in a knowledge
   document (a test checks). An eval and the content it grades never change in
   one PR.
10. **Export-control screening.** Every knowledge document carries
    `export_screen`. Flagged areas by default: radiation hardening, cryptographic
    and post-quantum hardware, side-channel and fault-injection attack
    techniques, advanced AI accelerators, advanced process and fab, high-speed
    data converters, RF and phased arrays, quantum. A path rule on those
    knowledge directories plus a content rule on `export_screen: flagged` adds
    legal-compliance as key 1 and raises the export-control founder class.
    Flagged areas stay knowledge only, from published sources, until counsel
    sets the scope. Classifications are questions for counsel.
11. **Licence rules for knowledge files** (the repository is Apache-2.0, so
    anything merged is offered under it): summarise and cite, never reproduce
    specification text, tables, register maps or figures; member-only
    specifications are never sources; no NDA or vendor EDA documentation; no
    benchmark results from licensed tools or SPEC; examples use permissive
    licences with a NOTICE entry, no GPL code and no CC-BY-SA text. Front
    matter: `sources` with an access type (open, purchasable; member-only
    fails), `licence_check`, `export_screen`, `as_of`, `review_by`, writer and
    checker.
12. **Writing checks** extend to skill cards and knowledge documents: no em or en
    dashes; no level words ("expert", "industry level", "robust"); no readiness
    claims ("signoff clean", "timing closed", "tapeout ready", "foundry ready");
    the first body line states the tier ("Knowledge only: no tool run backs
    this" where true); every claim cites a source.
13. **Worked examples** run inside the existing required CI jobs, with no new
    required check and no path filter; each declares a time budget, and a test
    caps the total at 5 added minutes per job. The first is the sync FIFO
    already in tests/fixtures/rtl.

## 10. Pilot and wave order

**Pilot: RTL small-block design (unit design.rtl), scoped to the first offer:**
register blocks, timer and GPIO, single-clock FIFOs and arbiters, APB and
AXI4-Lite glue.

Why: it is the only department whose skills already have tool-judged eval cases
(evals/rtl: sync_fifo, rr_arbiter, apb_regs, axi4_lite_regs), it needs no new
tool (a new tool is founder class), it serves the first offer, and its sources
are our own designs. Processor architecture cannot reach Practised by the
rule in section 9: no tool judges architecture, and its supporters' tools
(riscv-arch-test, riscv-formal, cycle counts on a core we change) are not yet
wrapped or checked.

Pilot exit (owner design-architect): all pilot skills at Knowledge; at least
half Practised under section 9; the ablation run; throughput and usage measured
privately; a retrospective that decides format and process changes.

Wave order (each wave names unit ids):
1. Pilot: design.rtl.
2. Verification (verification.*): the five-department cut, must-fail scorers.
3. Firmware and drivers (software.*): `fw.*` tools and an eval exist.
4. Implementation (implementation.pd, implementation.dft): the flow runs in CI;
   eval cases needed first.
5. Processor (architecture.micro with Verification's Processor and Accelerator
   department). Moves up to the next free slot as soon as an architecture judge
   is runnable (gate G12).
6. Design remainder (design.rtl.interface, design.integration): interface IP,
   IP qualification, deliverable kits.
7. Product, Documentation and Commercial (product.*, documentation.*,
   commercial.*): knowledge only, rubric results labelled.
8. FPGA (design.fpga), if an open FPGA flow is wrapped.
9. AI accelerator and GPU architecture (architecture.micro.npu, gpu).
10. Security and Silicon Lifecycle, after the export rule (gate G6).
11. Knowledge-only areas (P5): Foundation IP, Analog, RF and Photonics,
    Technology and Packaging, Architecture Research, Domain IP.

Rule behind the order: a wave goes first when its skills can reach Practised
with tool-judged evals now and it serves the first offer; market size orders
the rest.

Dissent: listed under item 6. partnerships also wanted the commercial wave
right after Verification; the chair placed it seventh because no customer
exists yet and no tool judges those skills.

## 11. Delivery

- Session-driven authoring first. The author loop needs its own council meeting
  after the pilot (control plane, founder class).
- Order inside a department: eval cases PR; one skills.py batch PR (so the
  roadmap count block changes once per department); knowledge document PRs of 3
  to 8 skills; examples.
- Founder-class changes for a wave (seat files, review-teams.yml rules,
  CODEOWNERS, CI) are batched into one hiring PR per wave. (Note, 2026-10-19:
  CODEOWNERS no longer exists; see section 5, rule 3.)
- Knowledge PRs auto-merge only when no founder class is detected, including
  licence and export-control content.
- Live eval runs are paced and logged privately; the founder sets each
  organisation's share. The owner's first recorded batch runs before any level
  is computed.

## 12. Founder items

1. One legal entity or two (registration facts). Needed before agreements for
   signature, invoices or cross-charges.
2. A licence for the Nirmaan repository or an intra-group grant: it is public
   with no LICENSE file (no commit of nirmaansoftware/Nirmaan has added one, as
   read on its main at 645933d), and this repository vendors three of its site
   files with no NOTICE entry (site/README.md, file table; NOTICE). Needed
   before shared components or cross-organisation skills grow.
3. The skills tile label (G8) before any programme skill is counted.
4. Approval of the founder-class P1 PRs (record, seat map and tests, programme
   review rules and checklists, CI examples).
5. Each organisation's share of plan usage, and the first recorded live eval
   batch.
6. Later: switching any key 2 off the chair; the author loop.

**Note, 2026-10-20.** The Founder Proxy's seat file on `main`
(`council/founder-proxy.md`, as changed by the founder's commit 30b5825)
returns needs-founder only for new spending, contracts or legal counsel,
export control, and turning on sending, and fails a change that weakens a
review gate. The founder's record of 2026-10-18
(`council/records/2026-10-18-founder-proxy.md`) also keeps public names,
prices and licence terms for the founder. This record does not say which of
the two governs an item; each item above still names what it needs, and an
item that touches contracts, counsel or export control (items 1 and 2, and
the export screen in section 9 item 10) waits for the founder under both. No
item above is recorded as decided by the founder.

The founder can overrule any decision in this record.

## 13. Coverage additions (P2 input)

- Product: design-partner programme management; IP release and errata;
  deliverable handoff; tapeout programme (knowledge only).
- Verification: debug and triage; reference models and scoreboards; testbench
  mutation qualification; Portable Stimulus; mixed-signal real-number models;
  performance verification; hardware fuzzing; cocotb, EQY, riscv-formal,
  riscv-arch-test.
- Design: AMBA (AXI, AHB, APB, CHI); TileLink and Wishbone; RISC-V extensions
  (vector); debug and trace; interrupt controllers and DMA; IOMMU; IP
  qualification.
- DFT: IEEE 1149.1, 1149.6, 1500, 1687, 1838, 1149.4; on-chip clock control;
  test point insertion; cell-aware, small-delay and path-delay tests; IDDQ;
  memory repair (BISR, eFuse); STIL (IEEE 1450); scan diagnosis; in-field test.
- Implementation: ECO; parasitic extraction; crosstalk and SI noise; OCV, AOCV,
  POCV; netlist-to-RTL equivalence; multi-voltage implementation; custom
  layout; chip finishing and tapeout data preparation (knowledge only).
- Firmware: RISC-V debug (JTAG, OpenOCD, GDB); RTOS porting to our SoC. Boundary
  with the Nirmaan studio: IP owns software whose correctness is defined by our
  RTL or register map; the studio owns embedded applications on commodity
  boards and ML on commodity GPUs; skills cross-link, never duplicate.
- EDA: flow reproducibility (version pinning). AI: ML for EDA; eval
  engineering.
- Market: IP productisation and integration; SoC integration; custom circuit
  design and mask layout; interface IP as controller plus PHY; die-to-die PHY;
  embedded NVM, OTP and eFuse; verification IP as a product; memory device
  design and wide-bandgap power (knowledge only); automotive qualification
  (AEC-Q100); product and test engineering at volume; commercial and field.
- Business: royalty reporting and audit rights; compute and AI cost accounting;
  intercompany allocation if entities separate; export screening;
  specification-terms register; open-source licence compliance (SPDX, SBOM);
  entity records; contract register; GST and withholding on licences and
  royalties; customs on imported boards and tools (knowledge only); IP product
  documentation; technical marketing; partner programmes and government
  channels; bid and proposal writing; contract and licence administration.

## 14. Gates

| Gate | Condition | Owner seat |
|---|---|---|
| G1 | Hierarchy fixes merged; the org passes the span and depth test with zero exceptions | eda-tooling (qa-evidence recomputes) |
| G2 | Seat-map test green; every derived key2 is chair; both tests founder class | security |
| G3 | Knowledge loading path and budget test merged before any knowledge document | ai-engineer |
| G4 | `EvalCase.skills` and must-fail scorers merged before any skill is credited Practised | verification-lead |
| G5 | Levels generator test: no level without a committed record path | verification-lead |
| G6 | Export-control path and content rule merged before any knowledge file in a flagged area | legal-compliance |
| G7 | Licence front matter and the Knowledge PR checklist merged before the first knowledge PR | legal-compliance |
| G8 | Skills tile relabelled by founder decision before any programme skill is counted | brand-content (site-engineer implements) |
| G9 | Release check of the hero role titles and the org figure's division names | site-engineer |
| G10 | Contracting party stated before any agreement is drafted for signature | legal-counsel (tax-accounts for books) |
| G11 | Pilot exit criteria in section 10 | design-architect |
| G12 | Processor wave moves up only when an architecture judge is wrapped (CONTRACT_ONLY first) and runnable at no cost | eda-tooling |
| G13 | New units enter as placeholders and activate only by the activation rule | product-lead |
| G14 | Deputy code only after the loop's records show a deferral it would have resolved | eda-tooling (security reviews) |
| G15 | Any non-chair key 2 only after the pilot retrospective and a passed seeded-defect review set | ai-engineer, then the chair |
| G16 | DFT and Silicon Lifecycle boundary written into the chart before P2 | dft-engineer |
| G17 | First recorded live eval batch committed before any level is computed | ai-engineer |
| G18 | Examples stay within their CI budget | eda-tooling |
| G19 | The plan's next version (v4, internal) carries the corrections in section 1 and the minimum span of 3; until it does, this record is the reference | chair |

## Appendix: how the counts were computed

Run from the repository root on main at 5e80dd2:

```text
PYTHONPATH=src .venv/bin/python - <<'PY'
from collections import Counter
from nirmaan.company import build_organization
o = build_organization()
roles = list(o.roles.values()) if isinstance(o.roles, dict) else list(o.roles)
units = list(o.units.values()) if isinstance(o.units, dict) else list(o.units)
reports = Counter(r.reports_to for r in roles if r.reports_to)
print("roles with reports", len(reports), "over 8", sum(v > 8 for v in reports.values()),
      "max", max(reports.items(), key=lambda kv: kv[1]))
print("roles reporting to exec.ceo", reports["exec.ceo"])
children = Counter(u.parent for u in units if u.parent)
print("units outside 3 to 8", sorted((k, v) for k, v in children.items() if not 3 <= v <= 8))
PY
```

Output:

```text
roles with reports 69 over 8 26 max ('implementation.dft.engineering.manager', 37)
roles reporting to exec.ceo 9
units outside 3 to 8 [('architecture.interface', 12), ('design', 2), ('design.integration', 1), ('documentation', 1), ('documentation.writing', 9), ('implementation', 2), ('implementation.dft', 1), ('implementation.dft.engineering', 9), ('implementation.pd', 9), ('nirmaan', 20), ('quality', 1), ('verification', 9)]
```

The root unit (`nirmaan`, 20 children) is the company itself; its span is
counted at the CEO (section 3). `ls evals/` at the same commit shows `firmware`,
`rtl` (apb_regs, axi4_lite_regs, rr_arbiter, sync_fifo) and `spec`, and no
`results` directory. P1-04 turns the span count into a committed test.

