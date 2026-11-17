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
