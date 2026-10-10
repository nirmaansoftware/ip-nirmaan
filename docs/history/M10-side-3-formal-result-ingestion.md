# Native formal-result ingestion (v1.6.0) - the last 5.1 knowledge item

The M5 spec's "formal verification" line item, and the sequencing 5.1 called
for (a new ArtifactType and parser first, the pack on top). Formal tools emit
per-property verdicts, not a simulation log, so this is Evidence-Graph-shaped
(M2) work, kept strictly additive:
- New `ArtifactType.FORMAL_RESULT` (one new enum member, mirroring the M6/M7
  additions). No other core type changed.
- New `parsers/formal_result.py` `FormalResultParser`: a registered `Parser`
  claiming `*.formal.json` (a simulator-independent manifest any formal flow
  can export), normalizing a broad status-alias table (proven / falsified /
  cex / vacuous / inconclusive / covered / unreachable) into one evidence node
  per property. Falsified/vacuous/inconclusive/unreachable are failing; proven/
  covered are informational. Node descriptions are phrased so the existing
  `formal` Knowledge Pack patterns match, so a native run reaches evidence,
  matching, and reasoning with zero pack or reasoning change.
- Registered in `parsers/__init__.py`; `pipeline.analyze()` handles a
  `*.formal.json` like any other artifact (no pipeline change). No report
  schema bump (formal verdicts are evidence nodes + knowledge matches, not a
  new report field). 4 new parser tests (proof the verdicts become evidence,
  aliases normalize, and the native path reaches the pack). 377 tests total.

**5.1 knowledge items are now fully resolved** (numeric clauses, omission
clauses, and native formal ingestion). The knowledge engine is elite in
breadth (42 packs / six domains) and expressiveness (presence, numeric, and
omission clauses, plus native formal artifacts).
