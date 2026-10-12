# v1.25.0 (2026-10-12) - the four audits of v1.24.0, closed

One version bump for the fixes from the four read-only audits of v1.24.0 (core,
integrations, user-facing surfaces, VeriTriage and test health), merged as #79
(M51 persistence integrity), #78 (M50 constitution hardening), #81 (M52 runtime
and loop fixes), #80 (M53 gate integrity), #83 (M54 demo surfaces), and #82
(M55 VeriTriage audit fixes), with #4 (VeriTriage OCP and Wishbone packs,
references, feedback reweighting, regression diff).

What changed for anyone resuming work:
- Re-planning never overwrites a project unless `--replace` (it archives); saves
  are sealed and atomic (M51).
- Evidence counts only for the task's current submission; people approve, sign
  gates, and cancel where the authority matrix says; one MCP session is one role
  (M50).
- A runtime's submission is final, a bad answer is a refused attempt, and
  `drive --runtime mock-llm` runs a fresh project up to the RTL stage (M52).
- A simulation passes only on a nonce-bearing verdict line from the testbench;
  BMC is reported as bounded, not proven; firmware verdicts carry a nonce; a
  timed-out run kills its whole process tree; each run has its own directory,
  which ends the parallel Verilator flake (M53).
- The landing page and CLI say only what the engine does, in words (M54).
- VeriTriage rebuilds a stale project cache, reads less into SystemVerilog, and
  keeps Wishbone and OCP concepts on their protocols; `analysis.json` schema 14
  (M55).

Still open, all the owner's call: the first recorded live evaluation batch, a
required-checks ruleset, and a Content-Security-Policy header for the site.
