# Synthetic evaluation results (test fixtures, M42)

Every file here is a **synthetic test fixture**, written by hand for
`tests/test_nirmaan_eval_proposals.py`. None is the result of a real
evaluation run, and no model produced any of them. Each says so in its
`detail` and `sandbox` fields, and the runtimes are named `fixture-model-a` and
`fixture-model-b` so they cannot be mistaken for a real model. The case digests
and run IDs are placeholders.

The layout is one directory per run (`run-01`, `run-02`), as `nirmaan eval run
--out DIR` writes it. `fixture-model-a` fails `rtl/axi4-lite-regs` twice on the
held-out judge, where `fixture-model-b` passes it; it fails `rtl/sync-fifo` once.
