# Milestone 86 - Failures feed the curriculum

Item G5 of the capability build-out. Design: `docs/CAPABILITY_LEVELS.md`
("Failures feed the curriculum"). Tests: `tests/test_failure_curriculum.py`.

**The gap.** Knowledge notes came from sources only. A live trial the model
failed taught the curriculum nothing.

**The rule.** Every failed live evidence trial that the failure labeller (H2)
marks "model" is answered in the PR of its batch by a knowledge note, a
must-fail case or a written reason.

**The checker.** `scripts/failure_curriculum.py` reads every `causes.md` under
`evals/results/`, lists the model-labelled failures of a batch and the answers
in the PR body, and exits 1 when one is unanswered. It lists failed trials no
`causes.md` labels. It touches nothing in `harness.CODE`, so no harness
fingerprint changes.

**The first backlog.** The six model-labelled failures on main when the rule
merged were answered in one PR (the "Failure curriculum" section of its body).
One became a new case, `rtl/apb-gpio-reset` (DATA_IN unknown after reset, seen
twice), with one mutant; no existing case changed, so no trial went stale and no
harness fingerprint moved. Two failures the seat's own simulation gate had
already refused, and the knowledge-off ones where the knowledge-on arm passed,
are answered with a reason.
