# Worked examples and the programme review rules (M64)

Items P1-10 and P1-11 of the 2026-10-18 council record on the capability
build-out (section 9; gate G7). The record is proposed in pull request #118, so
it is not yet in `council/records/`; every rule this milestone takes from it is
stated here in full.

## Worked examples (P1-11)

An example shows, on committed fixtures, what a seat's work looks like when real
tools judge it. `examples/<name>/example.json` lists tool runs, each with the
outcome it must have (`pass` or `fail`), and declares `budget_seconds`. The
format is in `examples/README.md`. The first example, `examples/rtl_sync_fifo/`,
reuses the M26 FIFO fixtures: lint, the self-checking testbench, a wrong
testbench that must fail, the overflow mutant (M58) that the testbench must
catch, and the DEPTH 8 proof.

Rules, checked by `tests/test_examples_budget.py`:

1. **Inside the existing jobs.** The examples are a test file, so they run in
   the required `test` job (whichever shard `scripts/shards.py` gives the file),
   with every tool required there by `NIRMAAN_REQUIRE_EDA`. No new required
   check, no new workflow step and no path filter. In the `no-tools` job they
   skip, like every real-tool test.
2. **The run's own result.** Each step goes through the tool bindings
   (`src/nirmaan/integrations/eda.py`) via the broker, is recorded as a tool run,
   and passes or fails on `run.succeeded`, which for a simulation comes from the
   testbench's own verdict line (M53). No step matches printed text.
3. **A budget.** Each example declares `budget_seconds` and fails if it takes
   longer. All examples together declare at most 300 seconds, the most they may
   add to one job; a set over the limit fails the check.

## Review rules for programme files (P1-10)

`.github/review-teams.yml` maps the programme's files to the teams whose
checklists cover them:

| Path | Owning team (key 1) | Co-owner |
|---|---|---|
| `knowledge/**` | Business, led by legal-compliance (licence and sources) | Verification (qa-evidence's claims and levels checks run inside verification-lead's key 1) |
| `capability/**` | Verification | |
| `examples/**`, `tests/test_examples_budget.py` | EDA and Platform | Verification |

Each seat's "In a review" section gains a Knowledge PR list:
`council/qa-evidence.md` (a source per claim, no level without records,
`as_of`, the tier line, size), `council/legal-compliance.md` (no copied text,
access type, `licence_check`, licensed benchmarks, example licences) and
`council/verification-lead.md` (held-out inputs absent, an eval and its graded
content never in one pull request, levels only from records, examples on the
run's result within budget).

Not in this milestone:

- **Division rules** such as `knowledge/design/**` to Silicon Design: the map's
  test fails a glob that wins no tracked file, so each lands with its
  division's first document.
- **The export screen** (a path rule on flagged knowledge areas, and a content
  rule on `export_screen: flagged` that raises the export-control class): it
  waits for the founder's decision on the record's export-control item. Until
  then legal-compliance's existing line on export-control sensitive content
  applies.
