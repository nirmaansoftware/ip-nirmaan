# Milestone 47 - Small cleanups found by the principal-engineer review

The review of v1.16.1 to v1.23.0 listed a handful of small faults (its
section 5.1 items 3 and 5, section 5.4, and recommendation 10). This milestone
fixes them without redesigning anything: M48 will move metric bounds into a
structured field, so the `max_`/`min_` convention is left as it is. Tests:
`tests/test_review_cleanups.py`, written first and failing.

**One model ID.** `claude-opus-5-5` was written in three Nirmaan files
(`company/model_profiles.py`, `integrations/veritriage.py`,
`runtime/claude_code.py`), and VeriTriage still defaulted to
`claude-opus-4-8` in `reasoning/ai.py` and its `--ai-model` CLI option.
Now `nirmaan.company.model_profiles.DEFAULT_MODEL` is the one Nirmaan source:
the profile, the `anthropic` provider, and the `claude-code` runtime all read
it, so the two runtimes cannot drift apart. VeriTriage may not import Nirmaan,
and Nirmaan never calls VeriTriage's `AIReasoner`, so nothing needs to be
passed in: VeriTriage's own default is a plain public constant,
`veritriage.reasoning.ai.DEFAULT_MODEL`, now `claude-opus-5-5`, which the CLI
option also uses. A test keeps it equal to the profiles' value, and another
fails if the literal appears in any other source file.

**`max_chain_length=0`.** The `dft.scan_insert` contract said "0 for no limit
(default)", but the engine refuses 0 ("must be a positive integer").
`docs/DFT_ADVANCED.md` section 2.1 is the specification: a value that is not a
positive integer is a recorded failed run, and `max_chain_length` is also an
ordinary `max_` bound on the `chain_length` metric, which 0 could never meet.
So the behavior was right and the contract text was wrong. It now reads
"Longest chain allowed, a positive integer; omit it for no limit (the
default)."

**`min_` bounds in one place.** M27 gave `dft.atpg` its own `min_` check
(written to `atpg_config.json` and read back in `parse_atpg`) because the
runner then checked only `max_`. M34 added `min_` to `eda._within_limits`,
which runs on every passing result, so the ATPG copy had become a duplicate
with the same messages. It is removed, along with the `atpg_config.json` file
and a pre-run "is not a number" check that the broker's typed contracts (M28,
M39) already make before any run. Failures read exactly as before
(`<metric> <measured> is below min_<metric> <bound>`).

**Stale `context.md` references.** M43 moved the old `context.md` sections
into `docs/history/`. `docs/ENGINEERING_CONTEXT_ENGINE.md` (5.8) and
`docs/WAVEFORM_ENGINE.md` (5.1) now point to
`docs/history/context-before-M43.md`; the M6, M23, and M27 entries cited in
`docs/WAVEFORM_ENGINE.md` and `docs/architecture/REVIEW_PLAN.md` point to
their history files; `docs/STATUS_DOCS.md` no longer says these were left as
written. A test fails if a tracked doc outside `docs/history/` cites a
`context.md` section number that is not a heading of `context.md`, or a
`context.md` milestone entry.

**The review's other drift (section 5.4).** M43 had already fixed the
roadmap's test count, the resume checklist, the Stage 2 `sta.run` line, the
false CI claim about `test_missing_sdk_raises_clean_error`, the order of the
history entries, and the landing page's hand-kept test count. One item is not
in a tracked file: the description of PR #68 says "Test count 1424 to 1484",
while the merged diff kept 1424 (the site now reads its count from
`site/stats.json`). GitHub PR descriptions were left unedited. `docs/PD_FINAL.md`
gains one line noting that the runner's `min_` check is now the only one.

**Not done.** No version bump. The `max_`/`min_` prefix overloading itself is
M48's.
