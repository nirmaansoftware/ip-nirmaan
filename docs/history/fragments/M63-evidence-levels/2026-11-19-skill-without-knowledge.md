**A skill that live records name but no knowledge document covers (W2-L1).**
`dv/directed-irq-ctrl` names `systemverilog`, which has no knowledge document,
so once its first live record is committed `capability/levels.json` lists
`systemverilog` with `"knowledge": null` and `"level": null` (below Knowledge,
as `levels.py` already computes it). The test that compares the skills at
Knowledge with the committed check records read `v.get("knowledge", {})`, which
returns `None` for that entry and crashed. It now reads
`(v.get("knowledge") or {})`; no level rule changes, and the harness code and
the fingerprints are unchanged.
