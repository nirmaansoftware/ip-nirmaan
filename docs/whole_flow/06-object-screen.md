# The object screen (gate WF16)

The record's second addendum (2026-11-18), decision 2, asks for a screen of
the seat's objects before the first register block trial, claimed only as a
tripwire. The register block case's checks 4 to 7, the four that build or
link the seat's C, name the scorers `screened-held-out-run` and
`screened-must-fail` (`src/nirmaan/evals/scorers.py`). Each runs the object
screen (`src/nirmaan/evals/object_screen.py`) over every C file of the check,
compiled as `fw.test` compiles it, and only when it finds nothing runs the
unchanged `held-out-run` or `must-fail` scorer. A hit fails the check with
its reasons and runs nothing: an undefined symbol off the allow list (however
declared), a definition of a harness or C library name, code that runs before
`main` or after the tests, or asm in the seat's own preprocessed lines. It is
the trial's recorded verdict, never a removed trial. The timer case links no
seat C and is not screened; no single-seat case is screened.

It is a tripwire, not confinement: it stops reach by name and nothing else.
In checks 5, 6 and 7 model-written C still shares the harness's process (in 5
and 6 with the judge's own held-out test), and from there could reach the run's
nonce and the counts by address arithmetic, which the screen does not stop.
`docs/GATE_INTEGRITY.md`, section 3, states the residual. What is recorded
from CI, in `evals/flow/object_screen_record.json` (`tests/test_object_screen.py`):
the allow list's source (the undefined symbols of every committed host
fixture, reference answer and held-out test), one must-refuse fixture per
refused construct (`tests/fixtures/fw/screen/`) and the simulator clock
probe, each refused, check 7 refusing the clock probe as a seat's driver test,
and the address-arithmetic probe (`tests/fixtures/fw/reach/address_arithmetic_probe.c`),
which passes the screen, with what it really read: starting from `hal->read32`
alone it read the cycle count (`read32` and `write32` take 2 cycles each on the
reference RTL, 3 on `axi4_lite_regs_lat2.v`), the pass counter and the run's
nonce. The screen therefore leaves the cycle count readable: the
address-arithmetic route stays OPEN, and the strict fixtures on it
(`driver-strict-address-test`, `driver-strict-address-driver`, above) are the
live controls on that route (decision 1, item 3). The route it does close, the
simulator's clock, has its strict fixtures recorded as refused.
