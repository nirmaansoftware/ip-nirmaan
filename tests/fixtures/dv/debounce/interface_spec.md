# Interface specification: `debounce`

An input debouncer, written for this repository in our own words. It is the
block under investigation in the eval case `debug/root-cause-debounce`; the case
gives it to no seat (the seat sees the RTL, the failing log and the triage
report).

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst` | in | 1 | Reset, active high, synchronous. `clean` resets low. |
| `noisy` | in | 1 | The raw input, for example a push button. |
| `clean` | out | 1 | The debounced input. |

`STABLE` (default 4) is the number of clock edges a change must hold.

- `DEB-SETTLE`: when `noisy` changes and then holds its new value for `STABLE`
  clock edges, `clean` takes that value at the `STABLE`-th of those edges, and
  not before.
- `DEB-GLITCH`: a change on `noisy`, in either direction, restarts the count.
  A pulse on `noisy` of `STABLE` clock edges or fewer, high or low, never
  reaches `clean`.
