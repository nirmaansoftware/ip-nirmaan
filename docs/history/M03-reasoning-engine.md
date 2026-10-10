# Milestone 3 (v0.3.0) - `47b1f57`
The **Verification Reasoning Engine**: a 7-stage pipeline (Evidence Graph
→ Evidence Selection → Rule Evaluation → Hypothesis Generation →
Hypothesis Ranking → Recommendation Generation → Final Report), every
stage independently testable and injectable. `EvidenceSelector` produces a
bounded `WorkingSet`; `ReasoningRule` subclasses emit evidence-cited
`ReasoningSignal`s that only shift ranking, never conclude; a
`HypothesisGenerator` registry produces competing `Hypothesis` objects that
must abstain without evidence; `rank_hypotheses` computes
`final = clamp01(base + Σ signal_contributions) * evidence_factor` with a
full `ConfidenceTrace` recorded per hypothesis; `RecommendationEngine`
produces categorized next steps. Optional `AIReasoner` runs strictly after,
receiving only `build_ai_payload()` (selected evidence + signals +
hypotheses + recommendations), never raw files - pinned by
`tests/test_ai_boundary.py`. `docs/REASONING_ENGINE.md` written.
