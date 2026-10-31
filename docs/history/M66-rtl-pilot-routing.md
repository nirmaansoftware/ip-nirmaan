# Milestone 66 - RTL pilot routing: the pilot's block and bus skills reach the block-design RTL seat

Part of the RTL small-block pilot (council record
`council/records/2026-10-18-capability-buildout.md`, section 10). Design:
`docs/RTL_PILOT_ROUTING.md`. Tests: `tests/test_pilot_refinements.py`.

**The gap.** On `block-design` the RTL seat's packet held `rtl_design` only,
except `arbitration` on an arbiter (M65): the APB and AXI4-Lite register
blocks reached it without `apb` or `axi`, and the FIFO without
`buffering_flow_control`. Timer, GPIO and skid-buffer requests matched no
intent and did not plan.

**Vocabulary.** Features `fifo`, `timer`, `gpio` and `register_slice`, with
no routing context of their own, and a `block_design` pattern that takes a
timer, GPIO, skid buffer or register slice as the block when it is the thing
built.

**Refinements.** Block-design's RTL task adds `apb`, `axi`,
`buffering_flow_control` (FIFO), `pipeline_design` and
`buffering_flow_control` (skid buffer or register slice), `fsm_design`
(timer) and `control_logic_design` (GPIO) when the feature holds. The FIFO's
RTL task now routes to an RTL interconnect designer instead of RTL
architecture; the register blocks, the arbiter and every other request plan
as before, which a test proves against the organization without M66's data.
