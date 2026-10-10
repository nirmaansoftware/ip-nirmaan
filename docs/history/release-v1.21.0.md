# v1.21.0 - the five M27 parts

v1.21.0 is the one version bump for the five M27 parts, built in parallel and
merged as #39 (repair after review), #38 (physical design for real), #42 (gates
everywhere), #43 (DFT), and #40 (RISC-V firmware). The standard local run is
1203 tests with 3 skipped: the real OpenROAD tests, which run in CI's
`physical-design` job. The owner's structural review (PR #37) also uses the
M27 label; it is not part of this release.
