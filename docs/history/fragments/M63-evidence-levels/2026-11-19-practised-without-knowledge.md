**A skill Practised from its records with no knowledge document (W2-L1).**
`levels.py` makes a skill Practised when one of its groups counts, whether or
not it has counted Knowledge (`docs/CAPABILITY_LEVELS.md`: "Practised when a
Practised group counts, else Knowledge when ..."). `systemverilog`, named by
`dv/directed-irq-ctrl` and with no knowledge document, reached a counting group
as the W2-L1 records landed, and the levels test, which equated "at Knowledge or
above" with "has a committed check record", failed. The test now reads
Knowledge from the knowledge entry (`counts`) and checks that every skill whose
level is Knowledge is among them. This narrows the assertion: it no longer
requires a committed check record for a Practised skill, so `systemverilog`
shows Practised with no knowledge document. No level rule changes. The harness code and the
fingerprints are unchanged.
