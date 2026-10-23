# Example: synchronous FIFO

What a design seat's work on a small RTL block looks like when real tools judge
it. The files are the M26 fixture set in `tests/fixtures/rtl/sync_fifo/`, reused
as they are; `example.json` lists the runs:

1. Verilator lint of the RTL: passes.
2. The self-checking testbench on Icarus: passes on its own verdict line.
3. A deliberately wrong testbench: the run fails, and the failure is recorded.
4. The same passing testbench on the overflow mutant (a write accepted while
   full): the run fails, so the testbench checks the full boundary.
5. The SymbiYosys proof at DEPTH 8: passes.

Each step runs through the tool bindings in `src/nirmaan/integrations/eda.py`
via the broker, and its outcome is the run's own result (`succeeded`), never a
match on printed text. `tests/test_examples_budget.py` runs it inside the
existing `test` job and fails if it takes longer than `budget_seconds`.
