# Milestone 10 (v1.0.0) - Collaborative Investigation Platform
The capstone, and the version freeze. Makes investigations portable,
reviewable, reproducible engineering artifacts, and declares the public API
stable. New `collab/` package: `model.py` (frozen `InvestigationBundle` =
session + reviews + annotations + `BundleMetadata`; content-derived `bundle_id`;
sha256 integrity `fingerprint`; `seal_bundle` recomputes both on any amend;
`extra="allow"` for forward compatibility), `exchange.py` (deterministic
canonical JSON + gzip mtime=0 -> `.vtb`; lossless round-trip; auto-detects
compression on import; no raw waveform/log files embedded, only the normalized
session incl. per-node raw_line provenance), `validation.py` (deterministic
`ValidationResult`: schema-major compat, fingerprint recompute, bundle_id/
session_id consistency, dangling-annotation + dangling-edge + dangling-
hypothesis detection, unknown-extension warnings), `review.py` (5 verdicts:
approved/needs_investigation/incorrect_diagnosis/incomplete_evidence/
false_positive; `add_review` returns a new sealed bundle), `annotation.py`
(`@register_annotation_target` registry + 6 built-in kinds: evidence,
knowledge-pattern, waveform-observation, engineering-commit, recommendation,
execution-step; `add_annotation` rejects unknown kinds and dangling targets),
`comparison.py` (explanatory diff across classification/evidence/knowledge/
waveform/engineering/recommendations/trace/metadata with a human summary
sentence). **Reviews and annotations layer on top; the session is never
mutated and reasoning is never affected** (deep-compare tests). Additive
integration only: WorkspaceServices gains bundle methods (export/import/
validate/review/annotate/compare/collaboration_view) that reach collab via
LAZY imports so services stays the boundary with no import-time coupling; an
optional report Collaboration section (`render(collaboration=...)`, plain data,
byte-identical without it); CLI `bundle` sub-app (export/import/validate/
compare) + `review`/`annotate` commands; 7 MCP tools (export/import/validate/
compare_bundles/get_bundle_metadata/list_reviews/list_annotations). No core
engine changed; NO report schema change (collab lives in the bundle, not the
report). collab imports only workspace + models (AST-verified); nothing below
imports collab. Crown jewel `test_new_annotation_target_needs_only_registration`
(a throwaway target kind validates and round-trips with zero core changes). 22
new tests (278 total). Version freeze: pyproject Development Status -> 5 -
Production/Stable; the public API (WorkspaceServices, MCP tool table,
orchestrator step/profile registries, .vtb format) is declared stable. Review
decisions (user-confirmed): ship AS v1.0.0, include raw_line in bundles, one
collab/ package. Design doc: `docs/COLLABORATION_PLATFORM.md` (approved before
implementation).

**As of v1.0.0 the core is complete and stable.** Future milestones are
integrations and ecosystem adoption over existing seams (section 5.8), never
core expansion.
