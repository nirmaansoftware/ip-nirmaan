# Milestone 85 - Gate reads of host files

A security fix, the follow-up M84 left open. Design: `docs/GATE_INPUTS.md`,
sections 2 and 6. Tests: `tests/test_gate_reads.py`.

**The gap.** M84 refused seat input that runs a command, not input that reads a
file. A seat's `.sby` could still name a file of the host in `[files]` (by
absolute path, `..` or a link) or in a Yosys read command or include folder
(`-I`, `-incdir`, `hierarchy -libdir`), and an `.eqy` likewise; Yosys then
printed part of the file into the run's summary and log. Confirmed with a
marker file outside the run. In the `tools-in-loop` variant (M75) the seat
reads that summary: `-I/<folder>` passed the M75 screen, and the seat read the
marker.

**The fix.** In `integrations/eda_guard.py`: every file name a setup gives is
relative, of ordinary characters, with no `..` (`relative_problem`); every
`[files]` source, and every file an eqy script reads, resolves inside the
setup's folder or to a file the run was given (`inside_problem`), checked
before anything reads it; a Yosys command file (`read -f`) is refused; the
files an eqy setup reads are checked as Verilog. The formal, cover and
equivalence backends pass the run's `sources`, so an approved file linked
beside the setup (M68) still reads.

**Not changed.** The M75 screen and broker (`runtime/seat_tools.py`): what the
seat reads is the run's summary and a capped log excerpt, which can carry only
the run's own paths and files now. The harness fingerprint is unchanged. The
history scan finds no committed seat setup that reads outside its folder. No
count changes.
