# Milestone 64 - Worked examples inside the existing CI jobs, and review rules for programme files

Items P1-10 and P1-11 of the capability build-out council record (section 9;
gate G7; pull request #118, not yet on main). Design:
`docs/WORKED_EXAMPLES.md`. Tests: `tests/test_examples_budget.py`,
`tests/test_review_teams.py`.

**Examples.** `examples/rtl_sync_fifo/` reuses the M26 FIFO fixtures: lint, a
passing testbench, a wrong testbench and the overflow mutant that must fail, and
a formal proof. Every step runs through the broker and is judged by the run's
own result. The examples run in the required `test` job with no new check, and
fail past their declared budget; all examples together may add at most 300
seconds to a job.

**Review rules.** `knowledge/**` goes to Business (legal-compliance) with
Verification, `capability/**` to Verification, and `examples/**` to EDA and
Platform with Verification. qa-evidence, legal-compliance and verification-lead
gain a Knowledge PR list in "In a review". Division rules land with each
division's first document; the export screen waits for the founder.
