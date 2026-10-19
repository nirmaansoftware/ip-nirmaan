# Knowledge documents in the work packet (M61)

Item P1-06 of the 2026-10-18 council record on the capability build-out
(section 9.3, gate G3): before any knowledge document is written, the path
that brings its text to a seat exists, with a budget and a test over every
workflow seat. The record is proposed in pull request #118, which waits for
the founder, so it is not yet in `council/records/`; every rule this
milestone takes from it is stated here in full, and the 40,000 character cap
is this milestone's own limit.

## The gap

A skill's `knowledge_sources` reached the prompt only as names
(`runtime/context.py`, the `knowledge` lines of the Domain section). A
long-form document written for a skill would never be read by the seat that
holds the skill.

## The source kind

`KnowledgeSourceKind.KNOWLEDGE_DOCUMENT` (`knowledge_document`). Its `ref` is
`<division>/<skill_id>`, and the document is the file
`knowledge/<division>/<skill_id>.md` at the repository root
(`nirmaan.org.knowledge.KNOWLEDGE_ROOT`). One document per skill: organization
validation fails a ref that is not two plain segments (`[a-z0-9_]+`) or whose
last segment is not the citing skill's id, so a ref cannot leave the
directory. The file schema (front matter, size, sources, tier line) is M62's,
not this milestone's.

## What enters the packet

`assemble` reads every document cited by a skill in the packet's domain scope
(the task's skills, plus the seat's skills that provide the task's
capability), once per ref, in skill order. `DomainScope.documents` carries each
whole: ref, citing skill, `sha256:` digest of the bytes read at assembly,
and the text, so the digest is always that of the text the seat was given. The
renderer puts each document after its skill's lines in the Domain section:

```text
Knowledge document <ref> (sha256:<hex>):
<the whole text>
=== END KNOWLEDGE ===
```

A packet whose skills cite no document renders exactly as before, so every
existing prompt and its `prompt_sha256` are unchanged (no skill cites one
today).

## Two budgets, and no silent cut

1. **Domain cap: 40,000 characters** (`DOMAIN_CAP`), the sum of the documents'
   text in one packet. At the cap the documents are carried whole; one
   character over, none is carried and `DomainScope.declines` says why.
2. **The seat's model context.** `ModelRuntime` checks the rendered prompt
   against `context_limit(llm)` twice: before the pre-flight tool runs (the
   prompt without tool notes), so a seat that cannot fit runs no tool, and
   again before it calls, with the tool notes in: the LLM's own
   `context_chars` if it states one, else the profile of its model, else the
   smallest profile of its provider. Over it, the seat declines with the
   reason and no model is called or counted. The `auto` runtime already
   refuses a prompt no profile holds (M31), so it has no limit of its own here.

A cited document that is missing, unreadable or not UTF-8 also sets
`declines`. `run_task` and `review_task` check `declines` before asking the
runtime anything, so the task is not started and the decline names the seat,
the task and the reason. The automated loop records that reason in the audit
trail with the step (`loop.step`, M29). Nothing is truncated anywhere: a seat
reads a document whole or declines.

## The test over every workflow seat

`tests/test_knowledge_packet.py` plans the representative requests that reach
every workflow (the applicability golden's list) and, for every task's owner
and reviewer, assembles and renders the packet and checks that the prompt plus
a domain scope at the full cap fits the default seat model's context
(400,000 characters, the smallest non-testing profile). Fixture tests show a
document in the prompt only when a skill on the task cites it, a missing or
oversized document making the seat decline before any work, a prompt over a
small model's context declining with no call, and bad refs failing validation.

## Not in this milestone

The knowledge file schema and its checks (M62), evidence levels (M63), any
knowledge document, and the pilot's ablation run (record section 9.3).
`runtime/tools.py` is untouched.
