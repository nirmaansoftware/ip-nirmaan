# Hierarchy fixes (M57)

The council record of 2026-10-18 (capability build-out, sections 1 to 4) sets
the target tree for the product's modelled company and the rule it must meet.
This milestone changes `src/nirmaan/company/org_chart.py` so the built
organization matches that tree for every change marked P1. Tests:
`tests/test_nirmaan_hierarchy.py` (new), plus the unit ids that moved in
`tests/test_nirmaan_org.py` and `tests/test_nirmaan_dft.py`.

## 1. The rule

The span of a unit is the number of child units directly below it, counted
from `build_organization()`. Generated ladder roles are not counted: a leaf's
ladder is that leaf's staffing. For an executive, the span is the units it
heads or sponsors plus the executives reporting to it.

- Every unit with child units has 3 to 8 of them. Placeholders count.
- The CEO spans 5: CTO, COO, CPO, Chief Architect, Chief of Staff.
- Leaf units and staff roles (the Chief of Staff) are exempt.
- Depth does not grow: every new unit sits at a layer that already exists.

The general validator (span exceptions as data, depth, the activation rule) is
a separate work item; this milestone makes the org pass it with no exceptions.

## 2. The changes

| Change | Before | After |
|---|---|---|
| Commercial placeholder division, sponsored by the CPO | `sales`, `marketing`, `customer_success`, `partnerships`: four placeholder divisions sponsored by the CEO | `commercial` with `sales` (Sales and Partnerships), `marketing` (teams `brand`, `web`, `research`), `customer_success`, `applications` (Applications Engineering) |
| One home for security architecture | `architecture.system.security` and `security.architecture` | `security.architecture` only |
| One home for security verification | `verification.security` and `security.verification` | `security.verification` only |
| Interface Architecture split | `architecture.interface`: 12 practices | `architecture.interface` (on-chip: axi, ace, chi, apb, ahb, noc, custom) and `architecture.io` (External Interface Architecture: pcie, cxl, ddr, usb, ethernet) |
| One Place and Route team | teams `placement`, `cts`, `routing`, each holding `place_and_route` | team `place_and_route` (holding `place_and_route`, so its tech lead reviews as the three teams' leads did) with practices `placement`, `cts`, `routing` |
| DFT in three teams | team `engineering`: 9 practices | `scan_atpg` (scan, atpg, faults), `memory_bist` (mbist, memory_test, lbist), `test_access` (jtag, compression, verification); each team keeps `dft_architecture` |
| Technical Documentation in three teams | team `writing`: 9 practices | `specifications` (specifications, architecture, registers), `engineering` (design, verification, api), `product` (manuals, release_notes, knowledge_base) |
| Quality and Process in three teams | team `engineering`: 8 practices | `reviews` (design reviews, verification signoff oversight, release quality, traceability), `process` (process QA, compliance, audits), `configuration` (a leaf team) |
| IP Integration and Delivery | one team, `packaging` | adds `qualification` (IP Qualification) and `kits` (Deliverable Kits), both placeholders |
| FPGA Design | none | `design.fpga`, placeholder |
| Foundation IP | none | `implementation.foundation`, placeholder (standard cells, memory compilers and SRAM, I/O and ESD) |
| AI Platform | none | `infrastructure.ai`, active leaf team (`python`, `monitoring`) |
| Platform and Product Security | none | `security.platform`, active leaf team (`threat_modeling`, `vulnerability_management`) |

`architecture.micro.noc` stays: it owns the NoC microarchitecture task shown in
the public hero.

## 3. Decisions inside the record's latitude

The record leaves exact slugs and the team-level cut inside a department to
this PR (section 4); the span test is the check.

- **Quality's 8 practices.** Three teams of practices would leave one team with
  2 children, which fails the minimum. Configuration Management becomes a leaf
  team (its practice's skill moves to the team), and traceability joins the
  review and release team, where requirements meet their evidence.
- **DFT verification** sits with Test Access so that each DFT team has 3
  practices; the boundary with Silicon Lifecycle (record item 9) is unchanged.
- **Placeholders.** FPGA Design, Foundation IP, IP Qualification, Deliverable
  Kits, and the whole Commercial tree enter as placeholders (record items 5 and
  10): each declares a mission, gets its head role, and has no ladder, so
  nothing routes to it. AI Platform and Platform and Product Security are
  active, as record item 6 decides; they hold existing skills only.
- **The on-chip department keeps its id and name** (`architecture.interface`,
  "Interface Architecture"), so the role titles in the public hero do not move.
- **The external department's id is `architecture.io`.** The router breaks
  ties on role id. An id that sorts before `architecture.interface` (such as
  `architecture.external`) would hand a generic interface specification, for
  example the one for a 4-bit counter, to a CXL architect instead of an on-chip
  one. `io` sorts after it, so routing is unchanged.

Routing was compared before and after on the requirements the tests plan (the
counter, the AXI-to-NoC bridge, PCIe and CXL controllers, DFT and physical
implementation requests): every owner and reviewer is the same role, under its
new id where its unit moved. One owner changes on purpose: on a request with
the `security` feature, the security-architecture stage goes to
`security.architecture.senior` instead of `architecture.system.security.senior`,
and it now gets an independent reviewer (`security.hardware.tech_lead`), where
on main it planned with none.

## 4. What does not change

- No skill entry is added: the catalogue stays at 140 skills.
- `src/nirmaan/company/workflows.py` is unchanged: no stage names a unit, and
  every stage is still owned by an active role.
- `nirmaan plan "Create a 4-port AXI-to-NoC bridge."` prints every role title
  in the site hero. Only role ids under Documentation and Quality move (for
  example `documentation.writing.manuals.engineer` becomes
  `documentation.product.manuals.engineer`), and the Documentation workstream
  is now led by the director of Technical Documentation, the narrowest unit
  that contains all three of its tasks.
- The site is not touched; its counts move at the next release
  (`scripts/status.py --release`).

## 5. Wave 2: Verification in five departments

The record's section 4 draws Verification as five departments for wave 2.
Verification had eight teams directly under its VP; it now has:

| Department (director role) | Teams |
|---|---|
| Methodology and Signoff (`verification.methodology.director`) | architecture, planning, signoff |
| Simulation (`verification.dynamic.director`) | testbench (systemverilog, uvm, testing, vip), coverage (code, functional, assertion), gate_level_power (placeholder), emulation (placeholder, knowledge only) |
| Formal and Static (`verification.formal.director`) | proof (property, model_checking, coverage), equivalence, cdc |
| Debug and Regression (`verification.debug.director`) | analysis (logs, waveforms, root_cause, intelligence), triage, regression |
| Processor and Accelerator (placeholder, `verification.processor.director`) | isa, models, accelerator (all placeholders) |

Spans: the VP 5, the departments 3, 4, 3, 3 and 3; depth is unchanged (six
layers below the Board). Every existing unit moved with its skills, tools,
noun and ladder; the equivalence and triage practices and the regression
practice became teams, so each has a manager and a tech lead of its own. The
regression team no longer inherits the Simulation team's `uvm` and `sva`.
Wave 2's skill batches set the departments' skills; this change adds none.

Slugs. The Simulation department's slug is `dynamic`, and the old
`testbench` practice is now `testing`. The router breaks score ties on role
id, so a slug that sorts differently moves work: with `simulation`, the
coverage-closure task would go to the signoff team instead of the functional
coverage practice, and with `directed`, the plain testbench task would leave
the SystemVerilog practice.

`tests/test_verification_departments.py` plans every representative request
on the chart before the cut and after it, maps old ids to new, and allows only
these changes: regression and verify-fix work is reviewed and approved by the
regression team's tech lead; the verification work stream of a regression
investigation is led by the regression manager (or the VP, when it spans
other verification teams); proof plus equivalence work is led by the Formal
and Static director, and equivalence work is approved by its own tech lead;
on a regression investigation asked for a reproduction (M71), the debug work
stream spans the Debug Analysis and Triage teams, so the Debug and Regression
director leads it; and a department director joins each verification escalation path below the
VP. The site hero's role titles do not change.

Activation (M77). Four of the departments (Methodology and Signoff,
Simulation, Formal and Static, Debug and Regression) have no skills, tools,
ladder or explicit roles of their own and group units that were ACTIVE at
M60, so they are ACTIVE as grouping units under record item 10 (b), as
amended by the council record `council/records/2026-11-14-g13-grouping-units.md`;
Processor and Accelerator stays a placeholder. Every ACTIVE child of the four
is in the frozen list, and each director holds nothing the VP does not. The
frozen list changes by renames only (205 ids, through `MOVES`): the
departments are not added, and `verification.formal` and `verification.debug`,
reused for departments, left it, their M60 units now listed as
`verification.formal.proof` and `verification.debug.analysis`
(`docs/ORG_SPAN_RULE.md` section 4). The cut first moved the coverage gate
from the VP to the Simulation director, pinned in `INTENDED`; M78 (section 6)
routes it back to the VP, so that move is no longer in `INTENDED`.

## 6. Signoff gates independent of the producing department (M78)

Council record `council/records/2026-11-14-g13-grouping-units.md`, decision
2c, gate owner verification-lead: the approver of a `gate.verification` task
is never the head of the department whose unit produced the evidence. After
the cut, five of the twelve `gate.verification` tasks in the representative
requests (the coverage gates of `parameter-change` and `feature-addition`)
went to the Simulation director, whose department's coverage team produced
the coverage.

**The approver: the VP, not Methodology and Signoff.** Verification-lead's
choice, which the record leaves to this pull request. The reasons, from the
plans of every representative request:

1. On the other seven `gate.verification` tasks (the `verification-signoff`
   gate of `new-ip` and the `closure-report` gate of `signoff-preparation`)
   the evidence is produced by
   Methodology and Signoff itself: the stage owner is
   `verification.methodology.signoff.staff`. Routing the gate to the
   Methodology and Signoff director would break the record's constraint on
   those seven to fix it on the other five.
2. Those seven are critical, and approving a critical gate needs VP level in
   the authority matrix (`APPROVE_GATE`, `src/nirmaan/company/governance.py`).
   The Methodology and Signoff director, a director, could not approve them
   anyway.
3. The VP heads the division, not a department, and was the approver of all
   twelve before the cut, so the coverage gate returns to the routing the plan
   had. The rule names no unit: the router excludes the producing roles and
   their heads and takes the next holder up the producer's chain, which is the
   VP for every Verification department.

**The rule, as data.** `INDEPENDENT_GATES` in
`src/nirmaan/company/governance.py` lists the gates it covers, carried by the
company definition (`CompanyDefinition.independent_gates`; validation reports
an unknown gate id). On those gates `Router.gate_approver` drops every
candidate in `Organization.own_heads` of a producer: the producer itself and
the head of each unit below the division that holds it (its team's manager
and its department's director; the division's VP is not one). Teams are
included because a team manager approving their own team's evidence is the
same conflict one level lower; no plan routes a gate to a team manager today,
so including them moves nothing. When only dependent holders remain, the gate
is planned blocked with the staffing reason, never routed back to them. The
`GateSpec` of every gate is unchanged: `gate.verification` still needs a
DIRECTOR or above holding `signoff.verification`, with `human_required`.

**Which gates.** Only `gate.verification`. `gate.implementation` is not
listed: its timing signoff tasks still go to the Physical Design director, and
making that gate independent is left to a later pull request. `gate.rtl` is
not listed either: only the RTL department's own director holds `signoff.rtl` at the
authority its high-criticality gates need, so under the rule every RTL gate
would be planned blocked (a test pins that). Giving it an independent approver
is a change to the Design organization, left to a later pull request. The
architecture, requirements and release gates are approved by executives
outside the producing departments already.

**What moves.** `tests/test_independent_gates.py` plans every representative
request with the rule and without it and allows only these changes, each of
the gate task's owner, approver and unit: the coverage gate (5 tasks) from
the Simulation director to the Verification VP. Every other task plans as
before. The must-fail tests: planned without the rule, the check finds the
Simulation director approving coverage evidence; and with `gate.rtl` added, the RTL gate is blocked, not self-approved.
