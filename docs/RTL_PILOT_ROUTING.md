# RTL pilot routing: the pilot's skills on the block-design RTL seat (M66)

Part of the RTL small-block pilot (design.rtl, council record
`council/records/2026-10-18-capability-buildout.md`, section 10: register
blocks, timer and GPIO, single-clock FIFOs and arbiters, APB and AXI4-Lite
glue). Each pilot skill is judged at the `rtl-implementation` seat of an eval
case, so its card and, later, its knowledge document must reach that seat's
work packet. M65 built the mechanism (`docs/STAGE_REFINEMENTS.md`) and used it
for `arbitration`; this milestone uses it for the rest of the pilot.

## The gaps

- The packet rule (`runtime/context.py`, `assemble`) gives the RTL seat the
  task's skills plus the seat's providers of `rtl.implement` (`rtl_design`).
  On `block-design` the RTL task carried no skill except `arbitration` on an
  arbiter, so the APB and AXI4-Lite register blocks and the FIFO reached the
  seat with `rtl_design` only: no `apb`, no `axi`, nothing about buffering.
- There was no `fifo`, `timer`, `gpio` or skid-buffer feature, and
  "Create an AXI4-Lite timer peripheral with an interrupt.", "Create an APB
  GPIO peripheral with interrupts." and "Create a skid buffer ..." matched no
  intent: they failed to plan.

## The change

**Features** (`company/vocabulary.py`): `fifo` ("FIFO"), `timer` ("timer"),
`gpio` ("GPIO", "general-purpose I/O") and `register_slice` ("skid buffer",
"register slice"). They carry no skills of their own. A feature's skills are
routing context for every stage of every workflow the request plans; these
features exist so block-design's RTL stage can refine its one task, and no
other stage, and no request outside block-design, should move because a
request names a timer or a FIFO.

**Intent** (`block_design`): a third pattern takes a timer, GPIO, skid buffer
or register slice as the block when it is the thing built: a build verb, an
optional article, at most three words, none of them "with", "and", "for",
"of", "to", "in" or "on", then the noun. "Create an AXI4-Lite timer
peripheral" is a block; "Design a controller with a timer" stays `new_ip`.
The two existing patterns are unchanged.

**Refinements** (`company/workflows.py`, block-design `rtl-implementation`),
after M65's `arbitration`:

| Feature | Skills added to the RTL task |
|---|---|
| `apb` | `apb` |
| `axi` | `axi` |
| `fifo` | `buffering_flow_control` |
| `register_slice` | `pipeline_design`, `buffering_flow_control` |
| `timer` | `fsm_design` |
| `gpio` | `control_logic_design` |

Every skill is in the catalog and held by a `design.rtl` role: `apb` and
`axi` by RTL interface design, `buffering_flow_control` through
`interconnect_design`'s includes, `pipeline_design`, `fsm_design` and
`control_logic_design` by their own RTL design practices.

## Who gets the task

The task's skills route it (`router.py`, `_fit`), so a refinement can move the
owner, as M65 moved the arbiter to an RTL interconnect designer.

| Request | RTL task skills | Owner | Reviewer |
|---|---|---|---|
| rr_arbiter: round-robin arbiter | `arbitration` | interconnect senior (unchanged since M65) | RTL design tech lead |
| sync_fifo: synchronous FIFO | `buffering_flow_control` | **interconnect senior** (was RTL architecture senior) | **RTL design tech lead** (was RTL architecture staff) |
| apb_regs: APB register block | `apb` | interface senior (unchanged) | interface tech lead (unchanged) |
| axi4_lite_regs: AXI4-Lite register block | `axi` | interface senior (unchanged) | interface tech lead (unchanged) |
| AXI4-Lite timer peripheral (new) | `axi`, `fsm_design` | interface senior | interface tech lead |
| APB GPIO peripheral (new) | `apb`, `control_logic_design` | interface senior | interface tech lead |
| skid buffer or register slice (new) | `pipeline_design`, `buffering_flow_control` | pipeline senior | RTL design tech lead |

One change of owner: the FIFO's RTL task moves from RTL architecture to RTL
interconnect design, the role family that holds `buffering_flow_control`; its
approver follows the reviewer, and the RTL phase's workstream follows its one
task (now led by the RTL design manager). The timer and GPIO go to RTL
interface design, not to the FSM or control practices: no role holds both
the bus skill and the block skill, and the interface unit's own `axi` and
`apb` decide the tie. The block skill still reaches the seat, since the
packet carries every task skill whether or not the seat holds it.

No gate, check, evidence requirement, review requirement or stage changes:
a refinement adds skills to a task and nothing else.

## What does not change

Every request that is not one of these blocks plans exactly as before, task
for task. The test builds the organization without M66's data (no new
features, the old intent patterns, M65's refinement only) and compares every
task of every representative request in the golden suite, plus three that
name a timer, GPIO, FIFOs or a skid buffer inside a larger IP. On a pilot
block only the RTL task changes, and the RTL workstream when that task
changes unit.

The applicability golden file (`tests/fixtures/applicability/plans.txt`)
gains the timer, GPIO and skid-buffer requests as representative requests,
and otherwise changes only in its analysis lines: the FIFO request now lists
`fifo`, and the three requests about "the timer" (a parameter change, a
sign-off and a timing closure) list `timer`. Their tasks and evidence are
unchanged.

## Tests

`tests/test_pilot_refinements.py`: for each existing RTL eval case's request
(rr_arbiter, sync_fifo, apb_regs, axi4_lite_regs), the RTL task's skills,
owner and reviewer, and every skill the case is judged on in the seat's
packet; timer, GPIO, skid-buffer and register-slice requests plan block-design
with their skills; a block with several features carries them all and no seat
declines; and the before-and-after comparison above.

## Known, not changed

"Register slice" also matches the existing `registers` feature (`\bregisters?\b`),
which adds register skills to routing context. No stage depends on it on
block-design (the register map stage needs `register_map`), and the RTL task
routes the same; narrowing that pattern would change other plans, so it stays.

## Not in this milestone

Skill cards and knowledge documents for these skills (P3-K1, P3-K2), the new
eval cases (P3-E2, P3-E3) and their must-fail controls (P3-E1). No count in
`scripts/status.py` changes: no new skill, workflow, tool, unit or principle.
