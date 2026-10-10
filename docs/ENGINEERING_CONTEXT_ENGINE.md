# Engineering Context Engine (Milestone 7)

Status: IMPLEMENTED in v0.7.0. This began as the design contract for M7
(reviewed and approved before any Python was written) and is now the
milestone's permanent architecture doc, mirroring `WAVEFORM_ENGINE.md`,
`KNOWLEDGE_ENGINE.md`, and `REGRESSION_INTELLIGENCE.md`. The design below
matches what shipped.

---

## 1. The one-sentence thesis

VeriTriage should answer "what changed?" before it answers "what broke?":
engineering change (commits, changed files, CI runs, ownership) becomes one
more normalized evidence source in the Evidence Graph, gathered by pluggable
providers, so the platform grows from a verification intelligence platform
into an engineering investigation platform - while the Verification
Intelligence Core never learns that Git, GitHub, Perforce, or any CI system
exists.

## 2. Why engineering context is evidence

A senior engineer debugging a regression does not start from the waveform.
They start from "what merged since the last green run?". That question is
answerable deterministically, before any log is read, and its answer changes
which hypotheses deserve weight: a watchdog timeout in a module whose
arbitration logic changed yesterday is a different investigation than the
same timeout in code untouched for a year.

That makes engineering change *evidence* in exactly the platform's sense: a
verifiable observation with a source, a location, a confidence, and
relationships to other observations. It therefore belongs in the Evidence
Graph, not in a side channel, and it reaches reasoning the same way knowledge
(M5) and waveform observations (M6) do: as ordinary evidence cited by
ordinary signals. It never concludes; it only shifts ranking.

## 3. Why this fits without new architecture

Every M7 need maps to an existing, test-enforced extension category:

| M7 need | Existing seam it uses |
| --- | --- |
| Ingest a context artifact (CI-exported JSON) | `Parser` ABC + `@register` (parser registry) |
| Gather live context (git) without breaking pipeline purity | the CLI-layer composition seam history already uses |
| Enter the Evidence Graph | `emit_evidence()`-shaped projection -> `GraphFragment` |
| Link changes to failures | new correlation pass in `GraphBuilder.build()` |
| Influence hypothesis ranking | `ReasoningRule` subclasses, composed in `pipeline` |
| Add ownership recommendations without touching reasoning | the additive augment seam (`HistoryEngine.augment` precedent) |
| Appear in the report | additive `Optional` field on `AnalysisReport` (schema v6 -> v7) |
| Support a new tool later (GitHub, Perforce, Jenkins, Jira) | new `ContextProvider` subclass only |

M5 proved the reasoning bridge shape, M6 proved the adapter split. M7 is the
same two ideas applied to engineering systems.

## 4. The provider split (mirrors the M6 adapter split)

```
  engineering system (git repo, CI export, review system, tracker)
          |
          v
  [ ContextProvider ]      <- the ONLY tool-aware code. One per system.
          |                    May shell out to git or read tool exports;
          |                    emits ONLY normalized EngineeringContext.
          v
  EngineeringContext       <- immutable, tool-independent normalized model.
          |
          v
  [ EngineeringContextEngine ]  <- tool-AGNOSTIC. Projects context into
          |                        evidence nodes, computes impact, builds
          |                        the timeline and investigation views.
          |                        Never imports a provider, never runs a
          |                        subprocess, never sees the string "git".
          v
  EvidenceNode[] (artifact_type = ENGINEERING_CHANGE)
          |
          v
     Evidence Graph  (correlation, reasoning, report, AI all follow)
```

**Two permanent laws** (the M7 analogues of M6's, written into
`ARCHITECTURE.md` and pinned by tests):

1. **Core-tool isolation.** No component beyond a `ContextProvider` may
   reference Git, a hosting platform, a CI system, or any engineering-tool
   API, binary, or file format. The Verification Intelligence Core operates
   exclusively on normalized context and evidence. (This law is retroactive:
   M4's `capture_execution_metadata` in `history/record.py` predates it and
   shells to git directly; M7 migrates that call to delegate to the Git
   provider, preserving its exact behavior and public API, so the law is
   enforceable repo-wide with no grandfather clause.)

2. **Evidence, never conclusions.** Engineering context may only enter the
   platform as evidence nodes and evidence-cited signals. No provider, no
   correlation pass, and no impact computation may produce a conclusion,
   modify a hypothesis, or veto reasoning. Ownership in particular may
   inform recommendations only, never ranking.

## 5. Normalized model (`engineering/model.py`)

All models are immutable (frozen Pydantic) and tool-independent. Every model
carries the milestone's required spine: `id` (deterministic content hash),
`timestamp`, `source` (provider name), `confidence`, `metadata`.
Relationships are expressed in the Evidence Graph (edges), not as object
references, so the models stay flat and serializable.

```python
class ChangeCategory(str, Enum):    # where a changed file lives
    RTL, TESTBENCH, CONSTRAINT, ASSERTION, BUILD, DOCS, OTHER

class ChangedFile(BaseModel):       # one file touched by a commit
    path: str
    category: ChangeCategory        # from path heuristics or manifest
    lines_added: int; lines_deleted: int
    modules: list[str]              # design/tb modules this path maps to

class Commit(BaseModel):
    id: str                         # deterministic (source, revision)
    revision: str                   # sha / changelist / review id
    timestamp: datetime | None
    author: str | None
    title: str
    files: list[ChangedFile]
    source: str; confidence: float; metadata: dict

class CIRun(BaseModel):
    id: str
    pipeline: str | None; build_number: str | None
    timestamp: datetime | None
    simulator: str | None; compiler: str | None
    configuration: dict[str, str]   # tool versions, defines, env markers
    environment_changes: list[str]  # declared drift vs the previous run
    source: str; confidence: float; metadata: dict

class Ownership(BaseModel):
    scope: str                      # module/path/protocol the owner covers
    role: str                       # "rtl", "verification", "protocol", ...
    owner: str
    source: str; confidence: float; metadata: dict

class IssueRef(BaseModel):          # a linked ticket, normalized thinly
    id: str; tracker_id: str; title: str; status: str | None
    source: str; confidence: float; metadata: dict

class EngineeringContext(BaseModel):
    sources: list[str]              # provider names that contributed
    capabilities: frozenset[ContextCapability]
    commits: list[Commit]           # bounded: recent-N, newest first
    ci_run: CIRun | None
    ownership: list[Ownership]
    issues: list[IssueRef]
```

Deliberately absent: diffs, patch text, file contents. Providers may read
them to compute categories and module mappings, but only summaries survive
normalization - the same lossy-by-design rule as waveform adapters, and for
the same reason (VeriTriage must not drift into being a code browser, and
the graph must stay small).

## 6. Providers (`engineering/providers/`)

```python
class ContextCapability(str, Enum):
    COMMITS, CHANGED_FILES, CI_RUNS, OWNERSHIP, ISSUES, REVIEWS

class ContextProvider(ABC):
    name: ClassVar[str]
    source: ClassVar[str]                 # provenance tag, e.g. "git"
    capabilities: ClassVar[frozenset[ContextCapability]]
    @classmethod
    def available(cls, root: Path) -> bool: ...   # can this provider run here?
    @abstractmethod
    def collect(self, root: Path, max_commits: int = 10) -> EngineeringContext: ...
```

Registered via `@register_provider` (`engineering/providers/registry.py`),
the same registry shape as parsers, packs, and waveform adapters. Capability
declaration gives the same honest degradation as M6: an analysis that needs
`CI_RUNS` when only git contributed is reported unavailable, never silently
skipped.

**v1 ships two providers:**

1. `manifest.py` (`source="manifest"`): reads a canonical, tool-independent
   JSON context manifest (`*.engctx.json`). This is the reference contract
   any CI system or internal tool can export, it can declare everything
   (commits, CI run, ownership, issues), and it doubles as the artifact-file
   entry path: a thin `EngineeringContextParser` (registered `Parser`)
   claims `*.engctx.json`, so `veritriage analyze sim.log run.engctx.json`
   works with zero pipeline changes - exactly how the waveform manifest
   enters.

2. `git.py` (`source="git"`): local repository, no network. The only place
   in the platform allowed to run the `git` binary. Collects the last N
   commits with per-file stats (`git log --numstat`), maps paths to
   categories via deterministic heuristics (`/rtl/`, `.sv` outside tb ->
   RTL; `/tb/`, `_test`, `_seq` -> TESTBENCH; `.sdc`/`.xdc` -> CONSTRAINT;
   Makefile/filelists -> BUILD), and degrades to an empty context outside a
   repo. Declares COMMITS + CHANGED_FILES only - honestly no CI_RUNS, no
   OWNERSHIP.

Future providers (GitHub, GitLab, Perforce, Gerrit, Jenkins, GitHub Actions,
Jira, DOORS, internal tools) are each one registered class; the crown-jewel
architecture test proves nothing else has to change.

## 7. Evidence emission and correlation

`EngineeringContextEngine.emit_evidence(context) -> GraphFragment` projects
the context into a bounded set of nodes tagged with the **one new enum
member** M7 adds to the graph model: `ArtifactType.ENGINEERING_CHANGE`
(additive, exactly like `WAVEFORM_METADATA` was). No new `RelationType` is
needed - `PART_OF` (file summary belongs to commit), `PRECEDES` (commit
order), and `CORRELATES_WITH` (change relates to failure) already express
everything.

Nodes emitted (each with full provenance in `attributes`: source provider,
revision, category, mapped modules):

* one node per recent commit ("Commit a1b2c3d by <author>: <title>
  (3 RTL files, 1 testbench file)"), severity None;
* one node per CI run descriptor, severity None - unless it declares
  `environment_changes`, which makes it WARNING evidence;
* ownership and issues stay in the report context, **not** in the graph:
  ownership must never sit in the evidence path that feeds ranking (law 2),
  and issues are reference material, not observations.

**Correlation pass** (`_link_engineering_changes_to_failures` in
`graph/builder.py`, the documented extension point): a commit node whose
changed files' modules or path tokens match a failing node's module/source
file gets a `CORRELATES_WITH` edge to that failure, rationale naming the
overlapping token, confidence 0.6 - identical shape and conservatism to the
coverage-hole and waveform passes.

## 8. Reasoning bridge (`engineering/inference.py`)

Mirrors `knowledge/inference.py` and `waveform/inference.py` exactly:
`engineering_reasoning_rules()` returns standard `ReasoningRule`s composed
in `pipeline.py`; the reasoning engine keeps zero engineering dependency.

v1 rules (all evidence-cited, all only shift ranking):

| Rule | Fires when | Weights toward |
| --- | --- | --- |
| `recent-change-in-failing-scope` | a commit node CORRELATES_WITH a failing node and touched RTL | RTL_BUG +0.15 |
| `recent-testbench-change-in-failing-scope` | same, but the overlapping files are TESTBENCH | TESTBENCH_ISSUE +0.15 |
| `environment-drift` | the CI-run node declares environment_changes | INFRASTRUCTURE_ISSUE +0.20 |
| `build-flow-change` | a correlated commit touched BUILD files and a compile failure exists | BUILD_ISSUE +0.15 |

Weights are modest by design: change proximity is suggestive, not probative,
and the deterministic log/waveform/knowledge evidence should keep dominating.
This is also how the platform separates verification failures from
infrastructure/environment/configuration failures: not by a new classifier,
but by letting CI-context evidence weight the existing INFRASTRUCTURE and
BUILD hypothesis categories.

## 9. Test impact analysis (`engineering/impact.py`)

Deterministic, two tiers, both pure functions of their inputs:

* **In-pipeline** (no storage access, preserving pipeline purity): changed
  modules x the current graph's test metadata and knowledge matches ->
  `ImpactedTest` entries ("this run's test touches a changed module") in
  the report's engineering section.
* **Historical** (`veritriage impact`, CLI layer, uses `RegressionStore`
  like the other history commands): changed modules x recorded regressions
  -> tests that historically failed in those modules, ranked by a
  deterministic score (failure count x recency bucket), each citing the
  regression IDs it derived from. Same inputs, same output, byte for byte.

Impact output is evidence-shaped (citations, confidence), never a verdict.

## 10. Ownership (`engineering/ownership.py`)

`OwnershipMap` built from provider-declared ownership (v1: the manifest;
future: CODEOWNERS/Perforce protections providers). Used in exactly one
place: `EngineeringContextEngine.augment(outcome)` appends one
`EngineeringRecommendation` ("loop in <owner>, verification owner of
<module>") after reasoning completes - the same additive-augment seam
`HistoryEngine.augment` established, appended after existing steps, never
replacing anything. An architecture test asserts the reasoning and rules
packages never import ownership and that no ownership-derived
`ReasoningSignal` exists: ownership informs people-routing, never ranking.

## 11. Timeline (`engineering/timeline.py`) and Investigation view (`engineering/investigation.py`)

Both are **pure projections of the Evidence Graph** - deliberately not new
graphs, because the Evidence Graph is the single source of truth and a
second graph would fork it.

* `build_timeline(graph, report)` orders evidence along the engineering
  axis: commits -> CI run -> compile events -> simulation events ->
  waveform observations -> knowledge matches, using timestamps where
  present and sim-time/artifact order otherwise, into a `TimelineView`
  (report section + `veritriage investigate` output).
* `build_investigation(graph, report)` groups the working set plus every
  node cited by signals/hypotheses into layers (engineering / artifacts /
  waveform / knowledge / hypotheses) with the cross-layer edges between
  them: an `InvestigationView` that summarizes "how the conclusion hangs
  together" and is the substrate a future interactive visualization renders.
  Projections never mutate the graph; a test deep-compares the graph before
  and after.

## 12. Pipeline, report, and CLI integration (all additive)

* `pipeline.analyze()` gains one optional keyword:
  `engineering: EngineeringContext | None = None`. When provided, the
  engine's fragment is added alongside parser fragments before correlation,
  and `engineering_reasoning_rules()` join the rule list beside knowledge
  and waveform rules. The pipeline stays a pure function of its inputs: it
  receives an already-normalized object and never calls a provider. Context
  manifests passed as artifact files need no parameter at all (they enter
  through the parser).
* **CLI gathers, pipeline consumes** (the history precedent): `analyze`
  gains `--context/--no-context` (default on, mirroring `--history`) plus
  `--context-root PATH`; with context on, the CLI asks the provider
  registry for available providers at the root, merges their contexts, and
  passes the result to `analyze()`. Outside a git repo with no manifest,
  this degrades to nothing, silently and safely.
* Report schema bumps `"6" -> "7"` with an optional `engineering` field
  (`EngineeringContextView`: recent changes, changed modules, correlated
  failures, impacted tests, ownership, CI info, capability gaps, timeline,
  investigation summary). New "Engineering Context" report section; every
  statement cites node IDs. `test_cli.py`'s schema assertion updates - the
  test exists to force exactly this acknowledgement.
* New CLI commands, none invoking AI:
  * `veritriage context` - show the normalized context the registered
    providers produce for a root (what the platform would see);
  * `veritriage investigate <artifacts...>` - analyze with context and
    print the investigation view and timeline to the terminal;
  * `veritriage impact` - historical test-impact for the current changes
    (needs the regression DB).

Report schema lineage: v1 Logs, v2 Evidence, v3 Reasoning, v4 History,
v5 Knowledge, v6 Waveform Intelligence, **v7 Engineering Context**.

## 13. Package layout

```
engineering/
  __init__.py        public surface; importing registers built-in providers
  model.py           frozen normalized models (section 5)
  providers/
    __init__.py      built-in provider imports (registration side effect)
    base.py          ContextProvider ABC + ContextCapability
    registry.py      @register_provider, available_providers, collect_all
    git.py           local git provider (the only git-aware module)
    manifest.py      canonical JSON manifest provider
  parser.py          EngineeringContextParser (registered Parser for *.engctx.json)
  context.py         EngineeringContextEngine: emit_evidence + augment + report view
  inference.py       engineering_reasoning_rules (ReasoningRule adapters)
  impact.py          deterministic in-pipeline + historical impact analysis
  ownership.py       OwnershipMap + the augment recommendation
  timeline.py        build_timeline projection
  investigation.py   build_investigation projection
models/engineering.py  report-facing views (plain data, imports no engine)
```

## 14. Tests

Unit: each provider (git against a throwaway repo fixture built in tmp_path;
manifest against a JSON fixture); path-category heuristics; evidence
emission (bounded, provenanced, deterministic IDs); correlation pass;
each reasoning rule fires and abstains correctly; in-pipeline and
historical impact; ownership augment appends exactly one recommendation;
timeline ordering; investigation layering.

Architecture guards (the milestone's actual deliverable):

* `test_engineering_core_is_tool_agnostic` - `model/context/inference/
  impact/ownership/timeline/investigation` contain no subprocess use, no
  provider import, no file reads;
* `test_no_git_outside_providers` - `subprocess` and the string `"git"`
  appear in no `src/` module except `engineering/providers/` (this is what
  forces and then protects the M4 migration);
* `test_reasoning_has_no_engineering_dependency` - extends the existing
  reasoning/rules import guard;
* `test_ownership_never_reaches_ranking` - no ownership import in
  reasoning, and no signal named `engineering:ownership*` exists;
* `test_projections_do_not_mutate` - graph serialized before/after
  timeline + investigation builds compares equal;
* `test_impact_is_deterministic` - repeated runs, identical output;
* `test_engineering_never_depends_on_ai`;
* **crown jewel: `test_new_provider_needs_only_a_provider`** - a throwaway
  `_FakePerforceProvider` defined inside the test, registered, collected,
  passed to `analyze()`; its commits reach evidence, correlate to a
  failure, appear in a reasoning signal and the report - with no core
  module imported or edited. The success criterion, machine-checked.

Fixtures: `tests/fixtures/change_context.engctx.json` (commits touching an
AXI RTL module + a CI run with an environment change + ownership entries),
plus a scripted tmp git repo builder for the git provider tests.

## 15. Out of scope for M7 (deliberately)

* Network providers (GitHub/GitLab/Gerrit APIs) - the provider seam is
  proven locally first; network providers are each one future class.
* Diff/patch content analysis beyond path-level categories - lossy by
  design; a future `ChangedInterface`/`ChangedAssertion` extractor can
  deepen `ChangedFile.modules` without touching anything downstream.
* Interactive investigation visualization - the `InvestigationView`
  projection is the substrate; rendering interactivity is front-end work
  (`docs/history/context-before-M43.md` section 5.8).
* Requirement databases (DOORS) and review systems - future providers.
* Any learning or reweighting from context - deterministic only.

## 16. Success criteria (from the milestone spec, as tests)

Given a regression plus engineering context, VeriTriage automatically:
identifies recently changed modules (evidence nodes), correlates failures
with changes (correlation pass), determines likely impacted tests (impact),
separates code from infrastructure/environment failures (CI-context
weighted hypotheses), generates engineering evidence (never conclusions),
and integrates it all into the existing Evidence Graph - with zero
dependency between the Verification Intelligence Core and external
engineering systems, proven by the crown-jewel provider test and the
no-git-outside-providers guard.
