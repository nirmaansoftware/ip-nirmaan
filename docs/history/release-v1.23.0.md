# v1.23.0 (2026-10-11) - the M34 to M42 batch

One version bump for nine milestones built in parallel and merged as #62 (M34
PD final), #58 (M35 host interrupts and traps), #61 (M36 loop concurrency and
budget), #59 (M37 STA on reanalysis, named antecedents), #60 (M38 plan
amendments), #66 (M39 typed values), #64 (M40 decisions from CLI and MCP), #67
(M41 register map adoption), and #63 (M42 proposals from evaluation results).
The standard local run is 1603 passed, 7 skipped (the real OpenROAD, OpenSTA,
and KLayout tests, which run in CI's `physical-design` job). Merging M39 after
M37 and M41 needed their dict-style packet reads rewritten for the typed packet,
and every parameter read through `text_value`; see the merge commits on #66 and
#67. A principal-engineer review of the whole effort since v1.16.1 was written
at this point; its recommendations are the input to the next milestone.
