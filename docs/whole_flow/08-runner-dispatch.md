# The runner option, part 4a: the dispatch

`evals/runner.py`'s `evaluate` sends a whole-flow case to
`nirmaan.evals.flow.evaluate` with every argument as given (the case, the
seat runtime with its recorder, the repository, the sandbox, the clock, the
attempts, the knowledge setting and the variant) and returns its result and
engine, so the flow module needs no second edit to `runner.py`. While the
module is absent the dispatch refuses the case with a plain message. The
fingerprint's `run` section says `flow: whole` and its `flow` section digests
`harness.FLOW_CODE`, for a whole-flow run only (`docs/HARNESS.md`). This is
the one edit that changes every fingerprint; it merges only after the H3
batch's last trial is recorded and before the pull request that names the
default harness (WF1, WF6).
