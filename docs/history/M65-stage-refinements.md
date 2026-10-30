# Milestone 65 - Stage refinements: a feature adds skills to a stage's one task, with no fan-out

Part of item P1-14 of the capability build-out council record
(`council/records/2026-10-18-capability-buildout.md`, section 9.3): the
`arbitration` skill must reach the RTL seat that the `rtl/rr-arbiter` eval case
judges. Design: `docs/STAGE_REFINEMENTS.md`. Tests:
`tests/test_stage_refinements.py`.

**The gap.** The arbiter request plans `block-design`, whose RTL stage put no
skill on its task, so `arbitration` neither routed the task nor entered its
packet. A variant would fan the stage out and rename the RTL task of every
block-design plan.

**Refinements.** `StageTemplate.refinements`: a plan-time condition and the
skills it adds to the stage's task when it holds. They route and enter the
packet like a variant's skills; nothing fans out and no task ID changes.
Validation checks their skills and conditions as it does a variant's.

**Block design.** The RTL stage adds `arbitration` when the `arbitration`
feature holds. The arbiter's RTL task now routes to an RTL interconnect
designer, as `new-ip`'s arbitration variant does; every other block plans as
before.
