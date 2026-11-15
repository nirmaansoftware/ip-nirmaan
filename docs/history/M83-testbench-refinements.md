# Milestone 83 - Block verification's testbench refinements for a scoreboard and for cocotb, and the cocotb testbench gate

Wave 2 (Verification) of the capability build-out, item W2-R3, for the eval
cases `dv/scoreboard-mac` and `dv/cocotb-crc` (W2-E6). Design:
`docs/BLOCK_VERIFICATION.md`, section "Scoreboard and cocotb (M83)". Tests:
`tests/test_dv_testbench_refinements.py`.

**The gap.** M68 planned refinements for a scoreboard and for cocotb but left
them until their skills landed. With `reference_modelling` and
`python_verification` in the catalog, neither reached the testbench seat's
packet, and the testbench's before-review gate ran `simulator.run` with the
default backend, which Python tests cannot pass; no gate named the M72 cocotb
backend.

**Refinements.** `scoreboard` ("scoreboard", "reference model") adds
`reference_modelling` to block verification's testbench task; `cocotb`
("cocotb", "Python tests") adds `python_verification`.

**Gate.** Asked for cocotb, the testbench is gated by `simulator.run` with
`backend: cocotb` over the approved RTL, the seat's Python test modules and
the top its testbench declares; the HDL testbench gate gains the plan-time
clause "not cocotb", which holds for every earlier request.

**Unchanged.** Every earlier request plans and renders its prompts as before
(tested against the organization without this change); eval case digests,
prompt fixtures and the harness fingerprint are identical. No count changes.
