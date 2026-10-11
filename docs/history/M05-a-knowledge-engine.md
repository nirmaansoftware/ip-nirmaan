# Milestone 5 (v0.5.0) - `8df1652` - architecture, initially thin content
The **Verification Knowledge Engine**: structured, versioned, LLM-independent
domain knowledge as a first-class component. `knowledge/model.py` defines
the normalized schema (`Concept`, `ProtocolSignal`, `StateMachine`,
`EvidenceClause`, `FailurePattern`, `DebugPlaybook`, `Reference`,
`KnowledgePack`, all versioned/serializable/metadata-carrying).
`knowledge/registry.py` is the `@register_pack` plugin mechanism.
`knowledge/graph.py` normalizes packs into a **frozen, queryable**
Verification Knowledge Graph (`contains`/`suggests_playbook`/`follows`
edges; `fingerprint()` for immutability proofs). `knowledge/matcher.py` is
pure deterministic clause matching (required/optional/forbidden clauses
against evidence node descriptions) plus state-machine projection ("where
did progress stop?"). `knowledge/inference.py` bridges knowledge into
reasoning: every `FailurePattern` becomes a `KnowledgePatternRule` - a
standard `ReasoningRule` - so matched knowledge contributes evidence-cited
ranking weight through **the exact same interface every built-in rule
uses**; the reasoning engine has zero knowledge dependency (architecture
test enforced). Report schema bumped to v5 (`knowledge` field); report.html
gained a Verification Knowledge section (pattern cards, protocol-sequence
stepper, playbooks, references). Shipped with only 4 packs (axi, uvm,
reset-clocking, coverage; 9 patterns total) - **the user flagged this as
too shallow given the milestone spec explicitly said "every protocol,
every architecture."**
