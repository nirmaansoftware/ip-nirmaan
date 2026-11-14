# Example: interrupt controller, directed testbench

What the testbench seat's work on an approved block looks like when real tools
judge it. The files are the W2-E1 fixture set in `tests/fixtures/dv/irq_ctrl/`
(the eval case `dv/directed-irq-ctrl`), reused as they are; `example.json`
lists the runs:

1. Verilator lint of the approved RTL: passes.
2. The directed, self-checking SystemVerilog testbench (two lanes, 8 and 5
   sources) on Icarus: passes on its own verdict line.
3. The same testbench on each of the five RTL mutants the case's must-fail
   control lists (priority inverted, acknowledge ignored, level mask ignored,
   a clear that beats a detection, a write that clears every bit): each run
   fails, so the testbench catches each one.

Each step runs through the tool bindings in `src/nirmaan/integrations/eda.py`
via the broker, and its outcome is the run's own result (`succeeded`), never a
match on printed text. `tests/test_examples_budget.py` runs it inside the
existing `test` job and fails if it takes longer than `budget_seconds`. The
proof half of the wave 2 example is `examples/dv_formal/`.
