# Milestone 52 - Runtime and loop fixes

Two audits of v1.24.0 found that `nirmaan drive` and the runtime under it could
spin, abort, or let one submission's evidence back another. This milestone
fixes them in the engine and the runtime, so the CLI, the MCP server, and the
loop behave the same. Design: `docs/RUNTIME_LOOP_FIXES.md`. Tests:
`tests/test_nirmaan_runtime_loop_fixes.py`, one per finding, written first and
failing on main.

**A runtime's submission is final (audit A C1).** `TaskEngine.submit` takes
`final`; the model runtime always passes it. For a task with no review a final
submission must meet every requirement (P9), or it is refused and becomes an
M26 attempt that escalates when the limit is spent. The probe that made 20
calls now makes one and escalates. A person may still submit first and record
evidence after.

**Every refusal is an attempt.** With a limit of 1 the refusal is recorded too,
so the limit is spent and the next owner step escalates with no call. M26 law 3
changed accordingly.

**A bad answer is a refused attempt (audit A H2).** No uncertainty, nothing left
after grounding, or a run that never happened is refused with the
constitution's reason instead of raising out of the loop. `drive` and `run`
save before they report an error. Every prompt declares the project
requirement as a citation, so the first stage can ground its answer.

**The mock drives a fresh project (audit C H3).** `MockLLM` cites the
requirement when nothing else is citable: `drive --runtime mock-llm` on a fresh
project goes owner, reviewer, then stops for a person's approval, as its dry
run says.

**Evidence is bound to its submission (M50 deferral).** A refused attempt
takes its evidence with it, and a run of an earlier submission backs nothing.
The repair prompt cites the attempt's failed runs from the attempt.

**A person's resolution grants a fresh budget (audit A M5).** Read from the
audit trail; an agent's resolution grants nothing.

**Smaller fixes.** M6: only a schema "1" file reads `max_`/`min_` parameters as
bounds. M4: `inputs` clauses are honored by every requirement reader. L1:
registry `items()` and `values()` snapshot under the lock. L4: preflight runs
once per distinct tool and parameters. L5: upstream evidence is seen through
gates. `--auto-gate` and MCP `auto_gates` are removed.

**Flows updated.** Tests that retried a refused run by hand at a limit of 1 now
pass `attempts=2` on the retry; tests that expected a P3, P4, or P5 error now
assert the refusal; the golden prompts gained the requirement citation, and
the repair prompt shows the refused attempt's runs from the attempt.
