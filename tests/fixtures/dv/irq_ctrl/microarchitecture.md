# Microarchitecture: `irq_ctrl`

How the approved RTL (`irq_ctrl.v`) meets `interface_spec.md`. It is not
given to the eval seats: a verification seat works from the specification and
the RTL itself.

## State

Four `N`-bit registers, all cleared while `rst_n` is low at a rising edge:

| Register | Holds |
|---|---|
| `enable` | the `ENABLE` register |
| `mode` | the `MODE` register |
| `pending` | the `PENDING` register |
| `src_q` | each source's input at the previous rising edge, for edge detection |

`src_q` loads `src` at every edge out of reset, whatever `ENABLE` and `MODE`
hold, so changing a source's mode while its input is high detects no edge.

## Next pending value

For each source, at each edge out of reset:

- `detect` is `src & ~src_q` in rising-edge mode and `src` in high-level mode;
- `clear` is the bit of a `PENDING` write's data, or a one-hot of the
  acknowledged number for a `CLAIM` write whose number is below `N`;
- the next pending bit is `detect | (pending & ~clear)`, so a detection wins
  over a clear at the same edge.

## Outputs

- `active = pending & enable`; `irq` is the OR of `active`.
- `irq_id` is a priority encoder over `active`: a loop from `N-1` down to 0
  that keeps the last match, so the lowest-numbered active source wins, and 0
  when nothing is active.
- `rdata` is a multiplexer on `addr` with no state: the three registers
  zero-extended to 32 bits, and for `CLAIM` the value `{irq, 26'b0, irq_id}`.

Every output comes from the registers and `addr` through logic, with no
added flop: a detection at one edge shows on `irq` right after that edge.
