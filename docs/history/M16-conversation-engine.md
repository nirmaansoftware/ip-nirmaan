# Milestone 16 (v1.12.0) - Conversation Engine

The milestone that turns a static report into something an engineer can
interrogate. New top-level package `conversation/`, above every intelligence
layer, below `workspace/`. It is the only layer that owns no intelligence at
all.

**The critical evaluation that reframed the milestone.** The spec read as "add
a way to ask questions", but VeriTriage *already had* a question-answering
layer: 51 MCP tools, ~40 WorkspaceServices methods, `workspace/navigation.py`
(address one object by ID) and `workspace/search.py` (substring match). Each
answers exactly one question completely, then forgets everything. Four things
were actually missing: **composition** (follow-ups require restating
everything), **navigation state** (no current hypothesis/module/filter),
**cross-layer joins** (evidence -> hypothesis -> agent -> plan step is four
calls and a manual correlation the report performs, renders, and discards), and
**a uniform answer contract**. M16 supplies those four and reimplements no
existing query.

Two further corrections adopted before coding:
- **Honest parsing.** The non-goal says "do not create natural language" while
  the examples are English sentences. Resolved by making the canonical question
  a structured object and the parser a *declared, finite vocabulary* matcher
  (keyword/regex, in the spirit of the M5 clause matcher). Out-of-vocabulary
  input returns an honest miss listing what *can* be asked, never a nearest
  guess. This is exactly what makes a future LLM a **translator** producing
  `Question` objects, never an owner of answers.
- **No new store.** `ConversationSession` is serializable and handed back to
  the caller. Navigation state is not intelligence; a sixth SQLite file for
  "which hypothesis am I looking at" would be storage for nothing.

**The load-bearing decision:** conversation navigates, it never concludes.
Enforced rather than trusted: `ConversationEngine._verify` strips any citation
that does not resolve to a real artifact and records the omission, so a handler
that invents a node ID cannot reach a client.

Structure: `context.py` (`ConversationContext` + the *only* sanctioned reference
builders, each returning None when the artifact is absent), `registry.py`
(`@register_handler`, one per intent), `parse.py` (declared vocabulary),
`handlers/` (explain/why/why_not, show_evidence/filter,
navigate/summarize/help, trace/compare), `engine.py`.

Ten intents. `Answer.followups` is what makes navigation possible without
prose: each answer names the questions it has made available.

Additive edits only: two WorkspaceServices methods, 8 MCP tools (51 -> 59), a
CLI `ask` command. **No report schema bump**: conversation is live interaction
over a finished report, not a new report field, which is itself the clearest
statement of what this layer is.

34 new tests (609 total). Design doc: `docs/CONVERSATION_ENGINE.md` (approved
before implementation). Crown jewel `test_new_intent_needs_only_registration`.
Caught during implementation: `summarize design` lost its target because no
pattern captured the noun after an intent verb, fixed by adding a verb-plus-noun
extractor.

Deferred to M16.x: an LLM translator producing `Question` objects; a VS Code
conversation panel; Slack threading over serialized `ConversationSession`s.
