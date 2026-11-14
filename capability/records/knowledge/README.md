# Knowledge check records

One JSON file per skill, `<skill_id>.json`: the record that a session other
than the writer read the skill's knowledge document and its sources. It is
what raises a skill to the Knowledge level (`scripts/capability_levels.py`,
`docs/CAPABILITY_LEVELS.md`). The first is `arbitration.json`.

```json
{
  "format": "nirmaan.knowledge-check",
  "skill": "c_programming",
  "knowledge_document": "knowledge/software/c_programming.md",
  "document_sha256": "sha256:<the document's bytes>",
  "writer": "the session or seat that wrote the document",
  "checker": "a different session or seat",
  "sources_read": ["SEI CERT C Coding Standard"],
  "checked_at": "2026-11-15",
  "gate_claims": [
    {"claim": "formal runs in mode prove only", "evidence": "src/nirmaan/runtime/model.py:120"},
    {"claim": "the cover check reruns the same .sby", "evidence": "tests/test_x.py::test_cover"},
    {"claim": "the lint tool is named", "evidence": "unverified"}
  ]
}
```

## `gate_claims`

Council record 2026-11-14 (pilot retrospective), decision 3. List every sentence
of the document that names a tool, gate, mode, option, section or file rule,
each with what confirms it:

- `claim`: the sentence, or a short paraphrase of it;
- `evidence`: `path:line` of the gate code that confirms it, a test id
  (`path::test_name`), or `unverified` for a sentence about a tool with no gate
  behind it.

A sentence about an option the gate restricts must say that it is restricted,
and the entry cites the gate line that restricts it. The list is not empty.

The field is required in a record whose `checked_at` is on or after
2026-11-15. A record checked before then may leave it out: it counts as not
checked for gate claims, and still raises the Knowledge level. One that carries
the field is held to the same shape. A record with no valid `checked_at` needs
the field. The check is `_gate_claim_problems` in `src/nirmaan/evals/levels.py`.

A document changed after its check makes the record stale: the skill drops
back until a new check record names the new sha256.
