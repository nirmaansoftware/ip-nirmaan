# Milestone 68 - Block verification: verify an existing block's RTL, with the testbench and the proof gated over the approved RTL

Wave 2 (Verification) of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10). Design:
`docs/BLOCK_VERIFICATION.md`. Tests: `tests/test_block_verification.py`.

**The gap.** No workflow fit a verification eval seat: no DV stage checked
the seat's own testbench or proof before review, and "Verify the existing
... RTL" matched no intent.

**Workflow.** `block-verification` (intent `block_verification`): the block's
specification and RTL handed over and approved, then a verification plan
checked by `vplan.check`, a testbench that must pass `simulator.run` on the
approved RTL, and a proof over the approved RTL that `formal.run` proves and
`formal.cover` finds not vacuous, each before review. Coverage and
equivalence stages are planned when asked for; their tools are contracts, so
their evidence is recorded, not run.

**Runtime.** Two bindings of one tool parameter add up (approved RTL plus the
seat's testbench in `sources`); no earlier workflow had one. `FileInput.beside`
links an approved upstream file beside the seat's own files under its own
name, so a .sby that names it reads the approved file; a seat file of that
name is never replaced, and the proof is then refused.

**Refinements.** `systemverilog`, `random_stimulus` and `unbounded_proof`
add `systemverilog`, `constrained_random` and `model_checking` to the
testbench or proof task; `coverage` and `equivalence` plan their stages.
Every other request plans exactly as before, which a test proves against the
organization without M68's data.

**Counts.** Workflows 9 to 10 (`scripts/status.py --write`).
