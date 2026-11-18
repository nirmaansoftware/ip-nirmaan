# Milestone 88 - Bounded tool runs

The H3 live trial of 2026-11-18 on the owner's machine: a seat-written
testbench made `vvp` print without stopping, the run's log reached 1.4 GB and
its result JSON 1.8 GB, and the disk lost 6 GB in an hour, with 4,757 run
directories and eval sandboxes left in `TMPDIR` in about two hours. Design:
`docs/GATE_INTEGRITY.md`, section 7. Tests: `tests/test_tool_output_cap.py`.

**Output, disk and read-back caps.** Every run of every backend is bounded in
`integrations/eda.py`: what its steps print (`OUTPUT_CAP`, 64 MB, read by the
runner itself), its own directory and any file a step writes (`DISK_CAP`,
2 GB, and `FILES_CAP`, 100,000 files), and each file its parser reads back (`read_output`). Past a cap the
step is stopped with its whole process tree and the run fails with a plain
summary (`output over 64 MB in vvp: stopped, the run fails`), never a pass.

**Bounded records.** A record names its log and never copies it; it keeps
the first and last 50 diagnostics and says how many it left out, cuts each
text to 2,000 characters, and fails a run whose parsed metrics are over 1 MB.

**Temporary directories removed.** A run with no `workdir` keeps its
directory until the scope that made it ends: each eval trial removes its own
sandbox and its runs' directories when it is recorded, whether it passed,
timed out, hit a cap or raised. A run that raises or is refused before any
step removes its directory at once. The test suite keeps its temporary
folders in one folder that it removes, and each test removes its runs'
directories. `NIRMAAN_KEEP_RUN_DIRS=1` keeps everything, for debugging.

**No harness change.** No file in `harness.CODE` is touched, so the default,
attempts-3 and tools-in-loop fingerprints are unchanged; a run under every
cap behaves as before.
