# Milestone 76 - Outside calibration: the RTLLM adapter, calibration records that never count

Gap G4 of the capability build-out. Design: `docs/OUTSIDE_CALIBRATION.md`.
Tests: `tests/test_outside_calibration.py`, `tests/test_capability_levels.py`.

**The gap.** Every case we run was written by us. There was no outside
yardstick for the RTL seat in our harness.

**The adapter.** `nirmaan.evals.outside` reads a private copy of RTLLM (MIT,
fetched outside both repositories; no problem text, testbench or reference is
committed) and maps each design to a case for the `rtl-implementation` seat:
the description is the approved interface specification, the benchmark's own
testbench is the judge, run over the seat's RTL through `simulator.run` and the
`held-out-run` scorer. A staged copy of the testbench also prints the verdict
line the simulator gate (M53) reads, beside its own pass message. 46 of the 50
designs map on the fetched copy; the rest are named in the record.
`nirmaan eval outside --check` proves the mapping with no model;
`--runtime` writes a calibration record.

**The labels.** The run manifest and every trial carry `purpose:
calibration` (default `evidence`); the manifest carries the benchmark, its
licence and the upstream commit. Either label keeps a trial out of the levels.
`capability/levels.json` lists such trials under `calibration` with the reason
"outside calibration"; M42 learning does not read them. Every trial carries
the harness fingerprint (M73).

**Harness.** No `harness.CODE` file changed: the fingerprint is the same as on
main. No model was called; the first live calibration waits for the owner's
usage go-ahead.
