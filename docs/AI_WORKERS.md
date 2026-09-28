# AI Workers in Verification Seats (Milestone 20)

Status: design for the owner's review, implemented on branch `m20/ai-workers`.
This is Stage 1 of `docs/ROADMAP.md`. Prose here is free of em and en dashes
per the standing style law.

Until now every seat in IP Nirmaan ran `NullRuntime`: the organization planned
and enforced, but nobody worked. M20 seats the first language-model workers,
in the department where their output can be checked rather than trusted:
verification debug. VeriTriage already produces real, engine-substantiated
evidence there, so an agent's report can be held to it.

```
nirmaan run <project> triage --runtime mock-llm --input paths=failing.log
nirmaan run <project> root-cause --runtime anthropic --dry-run
nirmaan run <project> root-cause --runtime anthropic --review
nirmaan task approve <project> root-cause --as verification.debug.tech_lead
```

---

## 1. The laws (unchanged, and now tested against a model)

1. **Agents propose; the engine decides.** A model-backed runtime returns a
   `WorkResult` like any other runtime. `run_task` applies it through the
   state machine, the authority matrix, and the constitution. Its artifacts
   become `EXECUTED`, never more.
2. **Evidence is a record, not a sentence.** Only tool runs the broker
   recorded can become evidence. A model that names a run which never happened
   is refused by P5, and the whole result is rejected.
3. **Cite or be stripped.** Every citation in generated prose is checked
   against the set the prompt declared. Anything outside it is removed and the
   removal is reported. An artifact left with no valid citation is dropped.
4. **Independence is structural.** The reviewer is a different seat and a
   different model call, and P6 is enforced before that call is made.
5. **Off by default.** The default seat stays `unbound`. Nothing calls a model
   unless a person names a model runtime on the command line.

---

## 2. The open decision: how the runtime reaches a model

The roadmap left one decision open. Only the bridge module
(`nirmaan/integrations/veritriage.py`) may import VeriTriage, and the M17
provider registry lives in `veritriage.ai`. Two shapes were possible:

| Option | What it means | Verdict |
|---|---|---|
| A. Expose the M17 registry through the bridge | The bridge gains `generate`, `ground`, and `render_prompt`, which wrap `veritriage.ai` providers, the frozen `Prompt`, and `grounding.enforce`. The runtime calls those. | **Chosen** |
| B. A thin adapter owned by the runtime | `nirmaan/runtime/` calls a vendor SDK itself and reimplements citation stripping. | Rejected |

**Why A.** It keeps the roadmap's promise that one vendor registry serves the
whole platform: any provider registered with `@register_llm_provider` is
immediately usable by an agent seat, and a vendor is never registered twice.
It reuses M17's grounding enforcement as code, not just as an idea, so
"strip what the prompt did not authorize" has one implementation. And it
keeps the import law intact with no exceptions: the runtime talks to the
bridge, the bridge talks to VeriTriage. Option B would have created a second
vendor seam and a second grounding implementation that could drift apart.

**Where the vendor lives.** The M17 guard `test_no_vendor_sdk_in_ai` forbids
a vendor SDK import inside `veritriage/ai/`, and VeriTriage is not being
changed for a Nirmaan milestone. So the Anthropic provider is registered into
the M17 registry by the bridge, which is the one Nirmaan module allowed to
touch it. It is an ordinary `LLMProvider` (a `BaseProvider` subclass) that
imports the `anthropic` SDK lazily, inside `generate`. Without the optional
`ai` extra, or without credentials, it returns a failed generation rather than
raising, which is the M17 failure contract. Moving it into VeriTriage later,
if VeriTriage wants it for its own renderers, is a file move and nothing else.

The provider calls `claude-opus-5` (the current default in the `claude-api`
skill) through `client.beta.messages.create` with adaptive thinking, effort
`high`, `max_tokens` 16000, and the server-side refusal fallback
(`fallbacks: "default"` under beta `server-side-fallback-2026-07-01`). It
branches on `stop_reason` before reading content: a refusal or a truncated
response is a failed generation, never partial work.

---

## 3. Seats and seat behaviour

Three roles are seated, all from the regression-investigation workflow that
Demo 4 plans:

| Seat | Task | What the runtime does |
|---|---|---|
| Failure triage | `triage` | Runs `veritriage.investigate` through the broker, then asks the model to write the triage report citing that run. |
| Root cause | `root-cause` (a decision) | Reads the triage evidence in its packet and concludes one of the declared outcomes (`rtl_bug`, `testbench_bug`, `infrastructure`, `spec_ambiguity`). |
| Debug review | review of `root-cause` | A separate seat (the task's reviewer) and a separate model call, which returns a verdict that cites evidence. |

The runtime does not name any of these. Its behaviour is derived from the
packet, so the same class works for any seat:

* **Pre-flight tools.** For each evidence requirement that accepts a tool run,
  the runtime invokes the named tools the role is granted, before the model is
  called. Parameters come from the task's inputs (task-scoped memory entries
  keyed `input.<param>`, which `nirmaan run --input` records). A tool that is
  `CONTRACT_ONLY`, unbound, or not granted is not run; the refusal is shown to
  the model and reported in the run's notes. A tool that fails is a recorded,
  failed run, exactly as for a human.
* **Decisions.** When the task declares outcomes, the model must choose one.
  An outcome outside the declared set is refused by the engine on submit.
* **Reviews.** `review_task` seats the task's reviewer, checks independence
  (P6) and then asks the model. The runtime never picks the reviewer.

Humans stay where the organization puts them: `root-cause` is approved by its
approver, and in the demo that approval is given by a human.

---

## 4. Work packets become prompts

A prompt is rendered from exactly four scopes of the M19 work packet, as four
sections in fixed order: **Company**, **Domain**, **Project**, **Task**.
Nothing else is rendered: packet memory (including the task's inputs) is
never shown to the model. The role card appears only as the seat line in the
Task section.

The packet's task scope gains three things the seats need:

* `evidence`: the evidence records on the task and on its upstream tasks
  (ID, kind, description, whether substantiated, the tool run it cites);
* `artifacts`: the task's own artifacts, so a reviewer can read what it is
  reviewing;
* a `summary` on every artifact (a new optional field on `Artifact`), which is
  where an agent's written work is stored.

`assemble(engine, task_id, role=...)` can now build the packet for a seat
other than the owner, which is how the reviewer gets its own card and tools.

**Citations.** The prompt declares a citation set:

| Token | Cites |
|---|---|
| `[evidence:<id>]` | an evidence record in the packet |
| `[run:<run-id>]` | a brokered tool run: upstream, or made in this execution |

Nirmaan IDs contain `:` and `#`, which M17's token grammar does not allow, so
an evidence token uses the ID with those two characters replaced by `.`
(`prj-1f0f5cb2a9:triage#e1` becomes `[evidence:prj-1f0f5cb2a9.triage.e1]`).
The prompt carries the mapping back to the real ID.

The prompt is a `WorkPrompt`: system rules and the output schema, a one-line
task, the four sections, and the citation set. `render()` produces the exact
text a provider receives, through the same M17 `Prompt.render` the provider
is handed. `nirmaan run ... --dry-run` prints it without calling a model,
running a tool, or changing state. Tool results made during execution are
appended to the Task section, so the dry run shows the prompt as it stands
before pre-flight tools run.

---

## 5. What the model returns, and what happens to it

The model must return one JSON object. For work:

```json
{
  "uncertainty": 0.2,
  "outcome": "rtl_bug",
  "artifacts": [{"kind": "root_cause_analysis", "title": "...", "summary": "... [run:run-0001] ..."}],
  "tool_runs": ["run-0001"],
  "claims": ["..."],
  "escalation": null,
  "notes": "..."
}
```

For a review: `{"verdict": "approve" | "request_changes", "comments": "...", "uncertainty": 0.1}`.

| What the model did | What the platform does |
|---|---|
| Cited a token the prompt declared | Kept. |
| Cited anything else | Stripped from the prose; listed in the run's notes. |
| Wrote an artifact with no surviving citation | Artifact dropped. If none remain, P4 refuses the completion. |
| Listed a tool run in `tool_runs` | Passed to the engine unfiltered. A real run becomes evidence; a run that never happened is refused by P5. |
| Made a claim | Recorded as `CLAIM` evidence, which satisfies nothing. |
| Omitted `uncertainty` | Refused by P3. |
| Asked to escalate | Routed up the owner's real escalation chain. |
| Returned something that is not JSON, or the call failed | The run is reported as declined, with the reason. Nothing is recorded as work. |
| Reviewed without citing evidence | The review is not recorded. |

Prose citations and evidence claims are handled differently on purpose.
Prose is presentation, so an invented reference is cut and the rest survives.
`tool_runs` is a claim about what happened, so the engine judges it and a
false one rejects the result.

---

## 6. Runtimes

```
LLM (protocol: complete(prompt) -> Completion)
  RegistryLLM(provider)   any M17 provider, through the bridge
  MockLLM                 deterministic, scriptable, no network

ModelRuntime(llm)         one class for every seat: accepts, execute, review
```

Registered runtimes:

| ID | What it is |
|---|---|
| `unbound` | The default. Declines honestly (unchanged). |
| `mock-llm` | `ModelRuntime(MockLLM())`. Deterministic: it answers from the prompt's own citation set and declared outcomes. Every test uses it or a scripted variant; the suite never calls an API. |
| `anthropic` | `ModelRuntime(RegistryLLM("anthropic"))`. Off unless named. |

A new runtime is one `@register_runtime` call. A new vendor is one
`@register_llm_provider` class plus a `ModelRuntime(RegistryLLM(name))`
registration. Neither touches the engine, the policy engine, the broker, the
prompt renderer, or the CLI.

---

## 7. What does not change

* Users who never name a model runtime see no difference. `nirmaan run` with
  no `--runtime` uses `unbound`, which declines and changes nothing.
* No test calls a model API. The Anthropic provider is tested against a fake
  `anthropic` module that records the request.
* VeriTriage is not modified. The M17 laws (`test_no_vendor_sdk_in_ai`
  included) still hold.
* The orchestrator still names no unit, skill, role, or protocol.

---

## 8. Laws, each pinned by a test (`tests/test_nirmaan_ai_workers.py`)

1. An agent citing a tool run that never happened is refused by P5.
2. An agent cannot review its own output (P6), and no model call is made.
3. Demo 4 runs triage, root cause, and review with agents on fixture logs,
   ending at a human approval.
4. Only the four scopes are rendered; memory never reaches the prompt.
5. Uncited and unknown citations are stripped; an uncited artifact is dropped.
6. A failed or unreadable model call declines and records nothing.
7. Nothing changes without a model runtime.
8. Crown jewel: a new runtime registers and runs from the CLI with zero core
   changes, and any M17 provider serves a seat through the one registry.

---

## 9. Deferred

* Seats beyond verification debug (design seats wait for Stage 2's real tools
  and Stage 4).
* Automatic seating from `AgentProfile.runtime` in the company definition;
  M20 seats are chosen per command.
* Multi-turn tool use by the model. Tools are run by the runtime from the
  task's declared evidence requirements, not chosen by the model.
* Token and cost accounting per run.
