# Milestone 74 - The harness bundle

Decision 4 of the council record `council/records/2026-11-14-pilot-retrospective.md`
("the bundle"), item H3 of the harness track. Design: `docs/HARNESS.md`
("The tool definitions", "Named variants", "Changes to the harness since
M73"). Tests: `tests/test_harness.py`, `tests/test_capability_levels.py`,
`tests/test_gate_contracts.py`, `tests/test_nirmaan_claude_code.py`,
`tests/test_claude_code_canary.py`; the canary script
`scripts/claude_code_canary.py`.

**The gap.** The retrospective found four things around the model that the
pilot's trials either missed or could not see: the formal tools' definitions
never said that a `[tasks]` setup is refused (fact 3); those definitions reach
the prompt but were not in the fingerprint (fact 5); a seat call through
Claude Code loaded the user-level `~/.claude/CLAUDE.md`; and there was no way
to name a second harness to compare with the default.

**One fingerprint change.** The four go in together so every group goes stale
once:

- the `sby` parameter of `formal.run` and `formal.cover` states the
  single-task rule, so the seat's input contract carries it;
- the fingerprint carries a digest of every tool definition in the catalog
  (format version 2);
- `CLAUDE_CODE_FLAGS` gains `--safe-mode`, checked on Claude Code 2.1.325:
  without it a probe call quoted the user-level file, with it nothing; the
  canary `scripts/claude_code_canary.py` (run by hand, since it calls a
  model) repeats the check with a control call that must see the file;
- `nirmaan eval run --harness <name>` runs on a named variant: `default`, or
  `attempts-3` (three attempts, a refused one answered again with the repair
  text). The variant's name is a run option of the fingerprint; its records
  and trials carry `harness_variant`; the levels generator lists them under
  `variants` and they never count; M42 learning does not read them.

**Levels.** `capability/levels.json` is regenerated: every Practised group
recorded before this milestone is now "stale: the harness changed after these
trials". The totals are unchanged (no group counted before), and Knowledge
levels come from check records and are untouched.

**Order.** The record's decision 1e holds this change off `main` until the
one read of the pilot's levels; it merges only after that read, and opens the
quiet window in which the other harness changes land and no evidence trial
runs. Tools in the loop, the other variant, is its own milestone.

No eval trial ran. The only model calls were the flag probe and the canary,
on a small model.
