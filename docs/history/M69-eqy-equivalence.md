# Milestone 69 - Logic equivalence through eqy: equivalence.run runs, and gates block verification's equivalence stage

Wave 2 (Verification) of the capability build-out, item W2-T1, under the
founder's decision of 2026-10-30 ("New tools for wave 2 (2026-11-13)" in
`council/records/2026-10-18-capability-buildout.md`). Design:
`docs/EQUIVALENCE.md`. Tests: `tests/test_nirmaan_equivalence.py`,
`tests/test_block_verification.py`.

**The gap.** `equivalence.run` was a contract, so block verification's
equivalence stage could only record an attestation.

**Tool.** `equivalence.run` is AVAILABLE through eqy (YosysHQ, ISC, installed
separately, not vendored), one backend in `integrations/equivalence.py` with
no core change. The setup runs over copies in the run's own directory; a pass
needs every partition proved, and at least one; the result names the files
each side read. Setups that reach outside Yosys, write a file, read outside
their folder, compare a design with itself, or skip a given source are refused
before anything runs.

**Gate.** The equivalence stage now needs a passing `equivalence.run` over the
seat's `.eqy` (`equivalence_setup`) and the approved RTL, placed beside it,
before review; an attestation no longer meets it.

**CI.** eqy comes from the pinned OSS CAD Suite and is in
`NIRMAAN_REQUIRE_EDA`; the `no-tools` job checks it is absent.

**Counts.** Tools AVAILABLE 36 to 37, CONTRACT_ONLY 17 to 16
(`scripts/status.py --write`).
