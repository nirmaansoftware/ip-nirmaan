# Stage refinements: a feature's skills on a stage's one task (M65)

Part of item P1-14 of the 2026-10-18 council record on the capability
build-out (`council/records/2026-10-18-capability-buildout.md`, sections 9.3
and 9.9): the first RTL small-block skill, `arbitration`, is judged by the
`rtl/rr-arbiter` eval case at the `rtl-implementation` seat, and its knowledge
document must reach that seat's work packet.

## The gap

A work packet's domain scope is the task's skills plus the seat's skills that
provide the task's capability (`runtime/context.py`, `assemble`). A task's
skills come from its stage (`StageTemplate.skills`, always) and its variant
(`Variant.skills`, when the variant's condition holds). The arbiter request
plans `block-design`, whose `rtl-implementation` stage has neither, so its
task carries no skill. The RTL seat it routes to holds `rtl_design` but not
`arbitration`, so nothing about arbitration reaches the prompt.

The requirement's features already know it is an arbiter (the `arbitration`
feature rule matches "arbiter"), and the router uses the feature rules' skills
as context when it scores owners. But context only nudges routing; it never
enters a task or a packet.

## Why not a variant

`new-ip` has an `arbitration` variant on its RTL stage. A variant fans the
stage out: one task per variant whose condition holds, with the variant's key
in the task ID (`rtl-implementation.arbitration`), and a stage whose variants
all fail to hold is not planned at all. `block-design` builds one small block
as one task. A variant there would need a default variant for every block that
is not an arbiter, renaming the RTL task of every block-design plan
(`rtl-implementation` becomes `rtl-implementation.<key>`), which every caller,
test and document that names the task would have to follow.

## The change

`StageTemplate.refinements: tuple[Refinement, ...]`, default empty.
A `Refinement` is a plan-time `Condition` (`when`) and the `skills` it adds.
When the planner instantiates a stage, the skills of every refinement whose
condition holds over the request's features (observed and assumed, as stage
and variant selection use) join the task's skills, after the stage's and the
variant's, without duplicates. Nothing fans out and no task ID changes.

The added skills do what a variant's skills do: they refine routing (the
router scores owners and reviewers on the task's skills) and they enter the
seat's work packet. On the arbiter, the RTL task now routes to an RTL
interconnect designer, the role family that holds `arbitration`, as the
`new-ip` arbitration variant already does.

`block-design`'s `rtl-implementation` stage gains one refinement:
`arbitration` when the `arbitration` feature holds. A block that is not an
arbiter plans exactly as before: same tasks, same skills, same owners.

Organization validation reads refinements as it reads variants: every skill
must be in the catalog, and the condition must be a plan-time condition over
known features (a run-time condition such as `produced` is refused, since the
task's skills are fixed when it is planned).

## Tests

`tests/test_stage_refinements.py`: the arbiter's single RTL task carries
`arbitration`, routes to a seat holding it, and has it in its packet; the
FIFO's RTL task does not; a refinement added as data alone reaches its task
(the crown-jewel extension test); and a refinement with an unknown skill, an
unknown feature or a run-time condition fails validation.

## Not in this milestone

The `arbitration` skill card and its knowledge document (P1-14 part b, a
separate pull request), and the check record (part c). No eval case changes.

M66 adds the RTL pilot's refinements (APB, AXI, FIFO, skid buffer, timer,
GPIO) on the same stage: `docs/RTL_PILOT_ROUTING.md`.
