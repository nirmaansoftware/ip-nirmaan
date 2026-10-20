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
