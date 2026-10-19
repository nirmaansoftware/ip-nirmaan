# Milestone 62 - Knowledge file schema and checks: every knowledge document and skill card is checked before the first is written

The capability build-out council record sets the rules for knowledge
documents and skill cards (sections 9.2, 9.4, 9.11, 9.12; item P1-07, gate
G7). Design: `docs/KNOWLEDGE_FILES.md`. Tests: `tests/test_knowledge_files.py`.

**The schema.** `knowledge/README.md`: front matter (`id`, `skill`, `as_of`,
`review_by`, `sources` with an access type, `licence_check`, `export_screen`,
`writer`, `checker`) and a body whose first line states the tier.

**The checks.** `nirmaan.org.knowledge_files` runs over every document under
`knowledge/` (none yet) and every skill card: required fields, only open or
purchasable sources, a checker other than the writer, at most 12,000
characters per document and 2,000 per card, no dash, level word or readiness
claim, the computed tier on the first body line, and no held-out eval input. A
passed `review_by` warns. Each rule has a failing fixture.

**The tier is computed.** Practising when one of a skill's tools is
available; a contract-only tool gives knowledge only, so `c_programming`
computes as knowledge only.
