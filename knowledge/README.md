# Knowledge documents

One document per skill, at `knowledge/<division>/<skill_id>.md`, cited from the
skill in `src/nirmaan/company/skills.py`. The rules come from the 2026-10-18
capability build-out council record (section 9); the checks are
`nirmaan.org.knowledge_files`, run over every file here by
`tests/test_knowledge_files.py`. No document exists yet.

A document is knowledge, not evidence. It never raises a skill's evidence
level by itself, and nothing here is counted as a "verification knowledge
pack" (those are VeriTriage's packs).

## Front matter

Between two `---` lines, one `key: value` per line:

| Field | Value |
|---|---|
| `id` | `<division>/<skill_id>`, the file's own path |
| `skill` | the skill ID, the file's name |
| `as_of` | the date the content was true, `YYYY-MM-DD` |
| `review_by` | the date it must be read again; once passed, the test warns |
| `sources` | one source per indented line: `- <access> \| <title> \| <where>` |
| `licence_check` | how the text respects its sources' licences (summarised and cited, no copied text) |
| `export_screen` | `clear`, or `flagged` for a flagged area (section 9.10) |
| `writer` | the session or seat that wrote it |
| `checker` | a different session or seat, which read the sources |

`<access>` is `open` (free to read) or `purchasable` (a published standard
anyone can buy). Member-only specifications are never sources, and neither is
NDA or vendor EDA documentation.

```text
---
id: software/c_programming
skill: c_programming
as_of: 2026-10-19
review_by: 2027-04-19
sources:
  - open | SEI CERT C Coding Standard | https://wiki.sei.cmu.edu/confluence/display/c
licence_check: summarised and cited; no text, table or figure copied
export_screen: clear
writer: session a
checker: session b
---
Knowledge only: no tool run backs this.
```

## Body

1. **The first line states the tier,** computed from the skill's tools:
   `Practising:` when one of them is `AVAILABLE`, else `Knowledge only:`
   (for example "Knowledge only: no tool run backs this."). A `CONTRACT_ONLY`
   tool gives knowledge only.
2. Then the content, in sections such as: what the skill covers, how the work
   is done, common failure modes, how a result is checked, and sources. Every
   claim cites a source from the front matter.

## Rules a test checks

- every front matter field above, with a date where a date is due;
- only `open` or `purchasable` sources; the checker is not the writer;
- at most 12,000 characters (split a larger topic); the skill card (its catalog
  entry as sorted JSON) at most 2,000;
- no em or en dash; no level word ("expert", "industry level", "robust") and no
  readiness claim (signoff clean, timing closed, tapeout ready, foundry ready);
- the first body line states the computed tier;
- no line of a held-out eval input or a reference answer appears in a document.

## Rules a reviewer checks

Licence (section 9.11): summarise and cite, never reproduce specification text,
tables, register maps or figures; no benchmark results from licensed tools;
examples only under permissive licences with a NOTICE entry, no GPL code and no
CC-BY-SA text. Export control (section 9.10): a flagged area stays knowledge
only, from published sources, until counsel sets the scope. An eval case and the
content it grades never change in one pull request.
