# Milestone 5 follow-up (v0.5.1) - `6d59aad` - knowledge base breadth
Direct response to the user's "very less effort" feedback. Expanded from 4
packs / 9 patterns to **13 packs / 29 patterns / 29 playbooks / 31
concepts / 9 state machines**, with zero changes to the matcher, the
reasoning engine, or the report layer (proof that the M5 architecture
genuinely supports this - the whole diff was pack content plus tests).
New packs: `apb`, `ahb` (AMBA low/high-speed bus), `chi`, `tilelink`
(coherent interconnects), `pcie` (LTSSM/credits/completions), `sva`
(assertion-failure-shape semantics, protocol-agnostic), `cdc` (clock
domain crossing, distinct from reset sequencing), `coherency` (MESI/MOESI
legality, protocol-agnostic), `riscv-privilege` (trap delegation, CSR
access faults). AXI deepened with a write-channel lifecycle FSM plus
write-response and exclusive-access patterns. Two Milestone-5-era patterns
were found to be missing spec references during validation-test
development and were fixed. Added `test_pack_schema_is_well_formed`
(parametrized over every registered pack: regexes compile, confidence
modifiers name real `HypothesisCategory` values, every pattern cites a
reference, every playbook step has a real action, IDs unique within/across
packs) and one fixture + match test per new pattern (11 new fixture logs
under `tests/fixtures/`), proving each pattern fires on realistic evidence
and reaches the reasoning engine as a cited signal, not just loads without
error. 166 tests passing (up from 134).
