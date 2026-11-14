# Example: formal proofs of two approved blocks

What the proof seat's work looks like when real tools judge it. The files are
the W2-E2 fixture sets in `tests/fixtures/dv/` (the eval cases
`dv/formal-credit-counter` and `dv/prove-deep-counter`), reused as they are;
`example.json` lists the runs:

1. The SymbiYosys proof of the credit counter at `MAX` 4 and 5
   (`credit_counter/credit_counter_check.sby`): passes.
2. The cover run of the same setup: passes, with every cover reached.
3. The prove-mode (k-induction) proof of the deep counter
   (`deep_counter/deep_counter_check.sby`): passes, unbounded.

The mutants of these two cases are caught by the cases' must-fail controls,
which swap the RTL under a proof in a sandbox (`tests/test_dv_formal_evals.py`);
a step here runs a committed `.sby` as it is, so this example shows the passing
proofs only. Each step runs through the tool bindings in
`src/nirmaan/integrations/eda.py` via the broker, and its outcome is the run's
own result (`succeeded`), never a match on printed text.
`tests/test_examples_budget.py` runs it inside the existing `test` job and
fails if it takes longer than `budget_seconds`. The testbench half of the
wave 2 example is `examples/dv_irq_ctrl/`.
