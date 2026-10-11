# Milestone 4 (v0.4.0) - `675c8d0`
**Regression Intelligence**: turns every analysis into historical memory.
New packages, all downstream of reasoning and never imported by it
(architecture test enforces this): `signatures/` (deterministic
`FailureSignature`, stable fingerprint excluding anything volatile),
`storage/` (`RegressionStore`, one SQLite file, full records as JSON blobs
with indexed query columns), `similarity/` (deterministic sparse feature
embeddings + cosine ranking behind an `EmbeddingProvider` seam; signature
matches always score 1.0), `history/` (`HistoryEngine` records runs,
answers "seen before?", and *additively* augments the report - one extra
precedent recommendation, confidence discounted 0.85x from similarity -
never rewriting what reasoning produced), `analytics/` (hotspots, failure
mix, signal frequency, confidence histogram, daily trend, deterministic
signature+embedding clustering via union-find), `feedback/` (interfaces
and storage only - `FeedbackRecord`, no learning implemented, designed so
confirmed root causes immediately improve similarity results and so future
work can reweight recommendations from labeled data), `dashboard/`
(self-contained `dashboard.html`, no JS). CLI gained `--history/--db` on
`analyze` (recording on by default) plus `history`, `dashboard`, `feedback`
commands. Report schema bumped to v4 (`history` field). `docs/
REGRESSION_INTELLIGENCE.md` written.
