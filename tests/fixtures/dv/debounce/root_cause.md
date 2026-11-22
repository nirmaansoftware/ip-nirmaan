# Root cause: `debounce` restarts its count only on a rising edge

Outcome: RTL bug.

The log's first `ERROR` is a symptom: `clean` fell at the edge where `noisy`
came back high after a low pulse of two cycles. The earlier log lines show the
other direction is fine: a high pulse of three cycles left `clean` low. So the
count restarts on a rising edge of `noisy` and not on a falling one
(`DEB-GLITCH` says either direction). With `clean` high the count sits at its
top value, a low pulse of two cycles is two equal samples in a row, and the
count is already complete, so `clean` takes the low value. The later `ERROR` on
the settled release is the same defect: `clean` fell two edges after the
change, not four (`DEB-SETTLE`), and the changes count (four, expected two) is
a consequence.

Fix: restart the count on any change of `noisy` (`noisy != prev`).

Reproduction: `debounce_repro.v` settles `clean` high, drives a low pulse of
two cycles, and samples `clean` on every edge. On the RTL under investigation
it fails; on the fixed RTL it passes.
