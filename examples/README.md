# Worked examples

Each folder holds one example: an `example.json` and a `README.md` saying what
it shows. An example reuses committed fixtures; it adds no RTL of its own.

`example.json`:

- `title`: one line.
- `fixture`: the folder, from the repository root, that step paths are
  relative to.
- `budget_seconds`: the most the example may take in CI. All examples together
  add at most 300 seconds to one job.
- `steps`: each with `tool` (a tool id in the catalog), `params` (file
  parameters relative to `fixture`), `needs` (executables) and `expect`
  (`pass` or `fail`).

`tests/test_examples_budget.py` checks the format and the budgets everywhere,
and runs every example where its tools are installed. CI's `test` job installs
them and requires them (`NIRMAAN_REQUIRE_EDA`), so the examples run there on
every pull request, with no new check and no path filter. Design:
`docs/WORKED_EXAMPLES.md`.
