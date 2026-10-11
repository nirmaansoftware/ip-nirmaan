# Milestone 13 (v1.9.0) - Learning Engine

The milestone that makes VeriTriage adaptive rather than stateless. New
top-level package `learning/`, a peer of `knowledge/`/`agents/`/`project/`,
positioned above all of them.

**The finding that shaped it:** the regression database was write-rich and
read-poor. It stored complete reports and complete Evidence Graphs and ran
exactly two queries against them (`count_signature`, `find_similar`), whose
total influence on the next run was capped at one appended recommendation.
Stored-but-never-read included: every agent outcome (v1.8.0 records what eight
specialists concluded and nothing asked whether any was right), the
`useful_recommendations`/`false_recommendations` votes M4 designed and left
unbuilt, `diagnosis == "incorrect"`, per-pack utility across 42 packs, project
continuity, and evidence co-occurrence.

**The load-bearing decision:** *learning is a pure function of recorded
history*. Same records plus same feedback yields byte-identical artifacts,
independent of arrival order and of the wall clock. Two mechanical details make
that hold rather than merely be claimed: `Corpus.as_of` supplies artifact
timestamps from the newest recorded run instead of `now()`, and artifact IDs use
content digests rather than builtin `hash()` (which is salted per process and
was caught doing exactly that during implementation).

Structure: `corpus.py` (indexed read-only view; the only thing a learner sees),
`registry.py` (`@register_learner`, batch not incremental, so rebuilds are
idempotent), `learners/` (seven families), `persistence.py` (`LearningStore`, a
**separate** SQLite file so deleting it restores exact pre-M13 behavior),
`calibration.py`, `engine.py` (`observe` / `recall` / `augment`, mirroring
`HistoryEngine.record`/`augment`).

Three guards on calibration: a floor on evidence (`MIN_OBSERVATIONS = 3` judged
runs), a clamp to [0.80, 1.20], and a default of nothing. Applied by the
**Coordinator at merge time, never by an agent**, so an agent still computes the
same position from the same evidence and only its influence moves. Agents gain
memory without gaining a dependency: hints arrive as plain data on
`AgentContext.learning`, and `agents/` never imports `learning/`.

Additive edits only: `AnalysisReport.learning` (schema `9` -> `10`),
`analyze(learning=...)`, `AgentCoordinator(calibration=...)`,
`WorkspaceServices(learning_db=...)` plus six methods,
`investigate(learn=True)`, 6 MCP tools (31 -> 37), CLI `learn` command and
`--learn/--no-learn`, and a report "What Prior Investigations Suggest" section.
No LLM, no embeddings, no vector DB, no ArtifactType, no reasoning change, no
agent rewritten, Regression Intelligence untouched and still authoritative.

44 new tests (487 total). Design doc: `docs/LEARNING_ENGINE.md` (approved before
implementation). Crown jewel `test_new_learner_needs_only_registration`: a
throwaway flakiness learner defined in the test reaches the store, the
statistics, and the recall path with zero core changes. Notable: an agent-memory
test caught that recurring patterns only arrived in `augment()` (after agents
ran), defeating the intended "agents receive historical context before
execution" flow; fixed by recalling all investigation patterns up front, with
`augment` promoting the signature-specific match.

Deferred to M13.x: learned embeddings behind the existing `EmbeddingProvider`
seam; a learning-aware dashboard section; recommendation reranking from
`RecommendationOutcome` (the artifacts exist, the reranker does not).
