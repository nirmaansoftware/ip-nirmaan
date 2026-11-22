**The triage card names the verdict line.** M71 granted `simulator.run` to the
`failure_triage` card for the repro gate, and that gate counts a run only when
the testbench prints one `NIRMAAN-SIM <nonce> <n> passed, <m> failed` line
with the nonce the run passes as the plusarg `nirmaan_nonce`
(`parse_reproduction` in `src/nirmaan/integrations/eda_parsers.py`,
`NONCE_ARG` in `src/nirmaan/integrations/eda.py`). Nothing the triage seat of
`debug/triage-three-bugs` received named either: the card did not, the
knowledge document says only "with this run's nonce", and the case's inputs
are the RTL and three logs. In the W2-L1 batch the gate refused every repro of
the eight arm E trials and the one arm N trial, so no judge ran (each
record's `causes.md`). The card now carries the verdict procedure, worded as
the `rtl_design` card's, with the expect=fail rule; it reaches the seat's
prompt with and without knowledge documents.
`tests/test_debug_evals.py::test_the_triage_seat_is_told_the_plusarg_and_the_verdict_line_its_repro_gate_reads`
checks the prompt in both arms and replays the case's reference answer through
the gate. The card is part of the skill digest, so the W2-L1 `failure_triage`
group is now marked stale in `capability/levels.json`; it stays at Knowledge
and needs a new batch to be measured. Cards and knowledge documents are in
none of the fingerprinted code lists (`CODE`, `LOOP_CODE`, `FLOW_CODE` in
`src/nirmaan/runtime/harness.py`), so no harness fingerprint changes.
