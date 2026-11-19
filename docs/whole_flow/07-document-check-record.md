# The document check record (M87, follow-up)

A fixed requirements document is a contract, so a session other than its
writer checks it, and the check is kept next to it as
`evals/flow/<block>/requirements_check.json` (format
`nirmaan.flow-document-check`): the case, the document's path and sha256, the
writer and the checker, when it was checked, the sources read, the judged
scopes it checked within (`judged_scope`, a copy of the case's
`citations.json` entry: each judged tag is checked within its stated scope,
[The two cases](02-two-cases.md)), the evidence for each tag (`path:line`, a test id, or `unjudged`) and
the result. The tags marked `unjudged` must be the case's `not_judged`, and
the result must be `holds`. Any edit to the document, or to a judged scope,
makes the record stale, and a flow requirements document with no record
fails, so every edit gets a new check.
An author never writes the record for its own document.

`tests/test_whole_flow_cases.py` holds every `evals/flow/*/requirements.md`
to this. Until a document's first record lands it is listed, with the reason,
in `evals/flow/requirements_check_pending.json` (a data file); its test still
runs and checks that it has no record yet, so the entry must go when the
record lands, and a document neither listed nor recorded fails. No test
skips. The list is empty now: independent checks failed both documents, each more than once,
with mutants that pass the reference testbenches, and each was fixed by stronger checks in the
case's own reference testbench, by splitting what stays unjudged into its own tags and by giving
each judged tag its stimulus scope. A fresh session then checked both within those scopes, with
in-scope mutants at the values, waits, positions and orderings each scope names, and wrote the
records (2026-11-19); it narrowed three scopes that claimed more than the testbench checks
(`AXIL-ORDER`, `TMR-STOP`, `TMR-ONESHOT`). Another test
shows the rule refuses a stale record (a changed document or a changed
judged scope), a record whose checker is its writer,
a missing tag, a tag marked unjudged that a check cites, unreadable
evidence, and a result that does not hold.
