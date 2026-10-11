# Milestone 7 (v0.7.0) - Engineering Context Engine
Answers "what changed?" before "what broke?": engineering change becomes one
more normalized evidence source, and VeriTriage grows from a verification
intelligence platform into an engineering investigation platform. New
`engineering/` package with the M6 split applied to tools: **providers** are
the only tool-aware code (`providers/base.py` `ContextProvider` ABC +
`ContextCapability`, `providers/registry.py` `@register_provider` +
`collect_context`, `providers/git.py` local git via subprocess, the platform's
ONLY git call site, `providers/manifest.py` canonical `*.engctx.json` any CI
can export), and everything downstream is tool-agnostic: `model.py` (frozen
`EngineeringContext`: bounded commits with categorized `ChangedFile`s, `CIRun`
with declared `environment_changes`, `Ownership`, `IssueRef`; lossy by design,
no diffs or patch text survive), `context.py` (evidence emission + report view
+ ownership augment), `inference.py` (4 modest-weight `ReasoningRule`s:
RTL/testbench change in failing scope, build-flow change, environment drift
toward INFRASTRUCTURE), `impact.py` (deterministic two-tier test impact:
in-run pure, historical via CLI-mapped `HistoricalRegression` slices; no
storage import), `ownership.py` (routing recommendation only, appended via the
M4 additive-augment seam; never ranking, test-enforced), `timeline.py` +
`investigation.py` (pure projections of the Evidence Graph, never new graphs,
mutation-tested). One new enum member (`ArtifactType.ENGINEERING_CHANGE`),
zero new relation types. Additive edits: correlation pass
`_link_engineering_changes_to_failures`, `analyze(engineering=...)` optional
keyword (CLI gathers via providers with `--context/--no-context`, default on,
degrades silently outside a repo; pipeline stays pure), report schema `6` ->
`7` (`engineering` field), report section, CLI commands `context`,
`investigate`, `impact`. **M4 migration:** `capture_execution_metadata` now
delegates (lazily) to `providers/git.py::execution_snapshot`, so the "no git
outside providers" law holds repo-wide with no grandfather clause. Ownership
and issues deliberately never become graph nodes. Two permanent laws in
`docs/ARCHITECTURE.md` (core-tool isolation; evidence never conclusions),
each test-pinned. Crown-jewel test `test_new_system_needs_only_a_provider`:
a fake Perforce provider defined inside the test reaches evidence,
correlation, reasoning, and the report with zero core changes. 24 new tests
(213 total). CLI tests pin `--no-context` for determinism (they run inside
the real repo). Design doc: `docs/ENGINEERING_CONTEXT_ENGINE.md` (approved
before implementation; scope, git-law migration, and default-on context all
user-confirmed).
