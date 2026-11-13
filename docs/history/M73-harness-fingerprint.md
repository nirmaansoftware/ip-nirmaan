# Milestone 73 - The harness in one place, and its fingerprint on every trial

Item H1 of the harness track of the capability build-out. Design:
`docs/HARNESS.md`. Tests: `tests/test_harness.py` and
`tests/test_capability_levels.py`.

**The gap.** A skill level is earned by a model and a harness together, but
the evidence levels (M63) grouped trials by skill, model and skill digest
only. The harness settings were spread over seven modules (the domain cap in
`org/knowledge.py`, `MAX_CONTENT` in `runtime/context.py`, the default limits
in `models/limits.py`, the prompts and repair text in `runtime/prompt.py`,
the excerpt bounds in `runtime/files.py`, the Claude Code flags and timeout in
`runtime/claude_code.py`, the anthropic settings in
`integrations/veritriage.py`), and a change to any of them, or to the code
that words the prompt (M68 was one), would have mixed trials from two
harnesses into one level.

**One place.** `src/nirmaan/runtime/harness.py` holds every setting; the code
reads each from there when it runs. `harness.CODE` names the files whose code
shapes a seat's run.

**The fingerprint.** `harness_sha256` covers every setting, the sha256 of
each code file, and the run's options (`--attempts`, knowledge on or off).
`EvalResult.harness` and `RecordedAnswer.harness` record it on every trial.

**Levels.** Trials group by skill, model, skill digest and harness. A group
whose harness is not the current default is stale; a trial with no harness,
or whose answers disagree with its result, is "harness not recorded" and never
counts. No live record exists, so `capability/levels.json` is unchanged and
the Knowledge levels from check records are untouched.

No model was called and no tool was added.
