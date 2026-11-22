# Microarchitecture: `tick_timer`

How the approved RTL (`tick_timer.v`) meets `interface_spec.md`. It is not
given to the eval seats: a verification seat works from the specification and
the RTL itself.

## State

| Register | Holds |
|---|---|
| `en`, `mode`, `ie` | the three `CTRL` bits |
| `load` | the `LOAD` register |
| `count` | the count, `W` bits |
| `expired` | the `EXPIRED` flag |

All clear while `rst_n` is low at a rising edge.

## One edge

1. A `CTRL` write stores the three bits; a rising `EN` also loads `count` from `load`. No other part of the timer moves at that edge, so the write takes the place of the count step and of an expiry (`wr_ctrl` gates `expire`).
2. Otherwise a running timer counts down while `count` is not zero; at zero it expires: periodic mode reloads `count` from `load`, one-shot mode clears `en`.
3. `expired` is set by an expiry, and a `STATUS` write of a one clears it. The set is written last, so an expiry wins over a clear at the same edge.
4. `irq` is `expired & ie`, with no mode term.

`COUNT` and `STATUS` writes other than the `STATUS` clear change nothing.
