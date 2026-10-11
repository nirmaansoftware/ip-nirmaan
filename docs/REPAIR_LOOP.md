# The repair loop (Milestone 26)

Status: design for the owner's review, implemented on branch
`m26/repair-loop`. This is post-roadmap work (see `docs/ROADMAP.md`, "After
Stage 6"). Prose here is free of em and en dashes per the standing style law.

M23 made a design seat's files reach review only after real checks passed on
them: lint and simulation for RTL, and M25 added a strict build and a
co-simulation for a driver, and testability rules and a scan simulation for a
DFT netlist. When a check fails, the submission is refused and the failed runs
stay on the task as evidence. Until now that was the end of it: the next
attempt was a fresh `nirmaan run`, and the model never saw why it was refused.

M26 closes that loop, bounded: when a submission is refused, the runtime may
ask the same seat again, handing it the failed runs as citable evidence with an
excerpt of each run's log. The attempt limit is data, and it defaults to one,
so nothing changes unless an organization or an operator asks for repair.

```
nirmaan run <project> rtl-implementation --runtime anthropic --attempts 3 --input workspace=work/
```

---

## 1. The laws

Every earlier law holds. In particular, the engine decides whether work may go
to review, never the runtime, and a failed run is a fact worth keeping. M26
adds:

1. **Repair is bounded, and the bound is data.** A capability's `max_attempts`
   (default 1: no repair) caps the attempts one `run_task` makes. The CLI's
   `--attempts N` overrides it for one run.
2. **A refused attempt never counts.** Its files are recorded, with their
   digests, as artifacts of an `Attempt` record, not as the task's artifacts.
   Nothing that reviews, verifies, approves, exports, or links artifacts ever
   sees them. The M23 `evidence-before-review` check still requires passing
   runs over the exact files submitted, so a run over an earlier attempt's
   files cannot open review for a later one.
3. **Only a refusal is repaired.** The constitution refusing the submission
   (a failed before-review check, or an answer with no file to check) starts
   another attempt. A tool the broker refuses (`blocked`), an
   answer that is not JSON (`declined`), an escalation, and a run the model
   invented (P5, raised) end the loop exactly as before. A missing tool is not
   something a model can fix.
4. **Every attempt is audited.** Each refused attempt is a `task.attempt` audit
   entry naming its files, runs, evidence, and the engine's reason; the one
   that passes is the ordinary `task.submit` entry.
5. **The runtime names nothing.** The loop, the packet, and the prompt name no
   seat, tool, skill, or artifact kind. RTL, firmware, and DFT seats get repair
   purely from their evidence requirements.

---

## 2. Where the limit lives

```python
Capability(id="rtl.implement", ..., max_attempts=3)
```

`Capability.max_attempts` is an integer, at least 1, default 1. It sits on the
capability because the capability is what a task requires, and a checked
design capability is where repair is useful. No shipped capability sets it:
the owner turns repair on per capability, or per run with `--attempts`.

`run_task(engine, task, runtime, attempts=None)` takes the override; `None`
means the task's capability decides.

---

## 3. The loop

```
run_task
  engine.start                               once
  for attempt in 1 .. limit:
    assemble the packet                      includes earlier refused attempts
    runtime.execute                          writes to <workspace>/<task>/<n>/
    record evidence for every run            failed runs unsubstantiated
    escalation, blocked, declined            stop, exactly as before
    engine.submit                            P9 evidence-before-review
      accepted                               stop: submitted
      refused, limit > 1                     engine.record_attempt, then repeat
  all refused                                refused, every attempt listed
```

With a limit of 1 the loop runs once and records no `Attempt`: the result, the
state, and the audit trail are identical to M23's.

M23 already gives every execution its own directory
(`<workspace>/<task>/<attempt>/`), so a later attempt never overwrites the
files an earlier run checked.

---

## 4. The Attempt record

```python
class Attempt(BaseModel):
    id: str                       # "<task>#t<n>"
    task: str
    number: int                   # counts every refused attempt on the task
    actor: str
    refusal: str                  # the engine's reason
    tool_runs: tuple[str, ...]
    evidence: tuple[str, ...]
    artifacts: tuple[Artifact, ...]   # EXECUTED, digests kept, never in state.artifacts
```

It lives in `ProjectState.attempts` (new, default empty, so saved projects
load unchanged). `TaskEngine.record_attempt` is the only writer: the owner
records it, only while the task is in progress, through the same policy check
and hash-chained audit as every other change.

Why not put the files in `state.artifacts`? Everything that iterates artifacts
(the deliverable export, the engineering links, the trace graph, the status
counts) would then have to learn to skip them, and the first thing to forget
would ship refused RTL. Keeping them inside the attempt makes "never counts"
structural rather than a filter.

---

## 5. What the seat sees on a repair

The packet gains `task["attempts"]`: the task's refused attempts, each with
its reason, its failed runs, and its files. The work prompt renders them in the
Task section (a review prompt never does): every attempt's reason, then the
latest attempt's failed runs, log excerpts, and files. Captured from the
counter test:

```
- Repair: your previous attempt 1 was refused and nothing from it counts. Fix what failed
  and answer again in full; files from a refused attempt are never reviewed.
- Attempt 1 was refused: Refused by the constitution: [P9] ...:rtl-implementation cannot go
  to review: 'Lint-clean under the RTL lint rules' is not met
- Failed run [run:run-0001] lint.run, evidence [evidence:....rtl-implementation.e1]:
  verilator-lint: lint failed: 0 errors, 1 warning; first: .../1/counter.v:20: [WIDTHTRUNC] ...
- Log excerpt of [run:run-0001] (first 3 of 3 notable lines):
| %Warning-WIDTHTRUNC: .../1/counter.v:20:19: Operator ASSIGNDLY expects 4 bits ...
|                      ... For warning description see https://verilator.org/warn/WIDTHTRUNC
| %Error: Exiting due to 1 warning(s)
- Content of refused file counter.v (sha256:4f6b...):
=== FILE: counter.v ===
...
=== END FILE ===
```

* **Citable.** The failed runs were recorded as evidence by `run_task`, so the
  run and evidence tokens are already on the prompt's citation list. The model
  can cite why it changed what it changed.
* **Bounded.** The excerpt is read from the run's first reference (the log, by
  the M21 backend convention) and keeps at most 20 lines of at most 240
  characters: the lines that mention an error, a warning, a failure, a fatal,
  an assertion, or a mismatch, in order; with none, the log's last lines. A
  reference that is not a readable file gives no excerpt, and says so.
* **Verified.** A refused file's content is shown only while its digest still
  matches, through the same `read_verified` M23 uses for approved inputs.

---

## 6. Outcomes

| Situation | Result | Task |
|---|---|---|
| Limit 1, checks fail | `refused`, as in M23 | `in_progress`; no `Attempt` recorded |
| Attempt n fails, n < limit | the loop continues | `in_progress`; `Attempt` n recorded and audited |
| A later attempt passes | `submitted`; report lists every attempt | `in_review`, with only that attempt's files |
| Every attempt fails | `refused`; the detail names every attempt | `in_progress`; every `Attempt` recorded |
| The broker refuses a before-review tool | `blocked`, no retry | `blocked` |
| The model invents a run | P5 raises, as in M20 | `in_progress` |

`RunReport.attempts` lists each attempt: its number, its result, its detail,
its runs and evidence, and (for a refused one) its `Attempt` ID. `nirmaan run`
prints one line per attempt when there was more than one.

---

## 7. Extension points

| To add | Do this | Core changes |
|---|---|---|
| Repair for any checked seat | `max_attempts` on its capability, or `--attempts` | none |
| A new check that repair uses | An `EvidenceRequirement` with `files` and `before_review`, naming any AVAILABLE tool whose first reference is its log | none |

The crown jewel `test_a_new_check_gets_repair_with_no_core_changes` adds a
capability with `max_attempts=2`, a stage checked by a `units.check` tool bound
in the test, and a scripted seat whose first file fails the check and whose
second passes: it reaches review with only the second file.

---

## 8. Laws, each pinned by a test (`tests/test_nirmaan_repair.py`)

1. An RTL seat whose first answer fails real lint and whose second passes ends
   `submitted`; the first attempt's files are recorded in an `Attempt`, never
   among the task's artifacts, and the reviewer never sees their content
   (it does see the failed run, which is the task's evidence).
2. Attempt 2's prompt carries the failed run's evidence and run tokens and a
   bounded excerpt of its log.
3. With a limit of 1 the result, state, and audit are as in M23: one model
   call, no `Attempt`, no `task.attempt` entry.
4. Exhausting the limit leaves `refused`, every attempt listed and audited;
   an attempt's files, submitted by hand, are still refused by P9.
5. A tool the broker refuses is `blocked`, with one model call and no retry.
6. The same loop repairs a firmware seat: the wrong register map first, then
   the fixture driver, against the approved RTL.
7. Crown jewel: a new check gets repair with no core changes.
8. The runtime names no seat or tool, and keeps the import laws; no test
   reaches a model API.

---

## 9. Deferred

* Repair after a review's `request_changes`: handing the reviewer's comments
  back to the seat. Today the next `nirmaan run` starts fresh from
  `changes_requested`.
* A per-workflow or per-stage limit. The capability is enough for every seat
  that exists; a stage field is a small data change if one is needed.
* A shared attempt budget across separate `nirmaan run` invocations. Each run
  has its own limit; attempt numbers keep counting across runs.
* Summarizing long logs with a model. Today the excerpt is a plain filter.
* File-level signoff. As in M23, the evidence check at approval is per tool,
  not per file, so a passing run from a refused attempt stays on the task as
  evidence. Review opens only with passing runs over the submitted files, so
  this lets nothing through today; binding signoff to files is a policy change
  for its own milestone.
