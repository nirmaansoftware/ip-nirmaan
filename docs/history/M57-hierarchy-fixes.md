# Milestone 57 - Hierarchy fixes: the org matches the capability build-out council record

The council record of 2026-10-18 (capability build-out, section 4) set the
target tree and a span rule: every unit with child units has 3 to 8 of them,
placeholders count, and the CEO spans 5. On main, 11 units and the CEO (9)
were outside it. Design: `docs/HIERARCHY_FIXES.md`. Tests:
`tests/test_nirmaan_hierarchy.py`.

**Commercial.** The four CEO-level placeholder divisions (Sales, Marketing,
Customer Success, Partnerships) become one placeholder Commercial division
sponsored by the CPO: Sales and Partnerships; Marketing with Brand and
Content, Web, and Market Research; Customer Success; Applications Engineering.

**One home per capability.** `architecture.system.security` and
`verification.security` are removed; Security owns both. Placement, CTS, and
Routing become one Place and Route team with three practices.

**Splits.** Interface Architecture keeps the on-chip protocols and External
Interface Architecture takes PCIe, CXL, DDR, USB, and Ethernet. DFT, Technical
Documentation, and Quality and Process become three teams each. IP Integration
and Delivery gains IP Qualification and Deliverable Kits.

**New areas.** FPGA Design and Foundation IP enter as placeholders. AI
Platform (Engineering Infrastructure) and Platform and Product Security
(Security) enter as active teams holding existing skills.

No skill entry was added (140), `workflows.py` is unchanged, and
`nirmaan plan "Create a 4-port AXI-to-NoC bridge."` still prints every role
title in the site hero.
