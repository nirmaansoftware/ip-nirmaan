# Knowledge check records

One JSON file per skill, `<skill_id>.json`: the record that a session other
than the writer read the skill's knowledge document and its sources. It is
what raises a skill to the Knowledge level (`scripts/capability_levels.py`,
`docs/CAPABILITY_LEVELS.md`). No record exists yet.

```json
{
  "format": "nirmaan.knowledge-check",
  "skill": "c_programming",
  "knowledge_document": "knowledge/software/c_programming.md",
  "document_sha256": "sha256:<the document's bytes>",
  "writer": "the session or seat that wrote the document",
  "checker": "a different session or seat",
  "sources_read": ["SEI CERT C Coding Standard"],
  "checked_at": "2026-10-19"
}
```

A document changed after its check makes the record stale: the skill drops
back until a new check record names the new sha256.
