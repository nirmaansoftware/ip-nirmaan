# Milestone 61 - Knowledge documents in the work packet: a cited document's text reaches the seat, within a budget, or the seat declines

A skill's knowledge sources reached the prompt only as names, so a document
written for a skill would never be read by the seat holding it (capability
build-out council record, item P1-06, gate G3; pull request #118, waiting
for the founder). Design:
`docs/KNOWLEDGE_PACKET.md`. Tests: `tests/test_knowledge_packet.py`.

**A new source kind.** `KnowledgeSourceKind.KNOWLEDGE_DOCUMENT`, ref
`<division>/<skill_id>`, file `knowledge/<division>/<skill_id>.md`.
Validation fails a ref that is not two plain segments ending in the citing
skill's id.

**The packet carries the text.** `DomainScope.documents` holds every cited
document whole, with its digest, and the Domain section renders each after
its skill. A packet that cites none renders exactly as before.

**No silent cut.** Over 40,000 characters of documents in one domain scope, or
with a cited document missing, the packet carries none and the seat declines
before any work, with the reason. A rendered prompt over the seat's model
context declines with no model call.

**Every workflow seat fits.** A test over every task's owner and reviewer, on
requests reaching every workflow, shows each prompt plus a full domain scope
fits the default model's context. No skill cites a document yet.
