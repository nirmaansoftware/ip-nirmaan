# Interface specification: `updown_counter`

A 4-bit up/down counter with a parallel load, for a position or a level that
moves one step at a time and can be set directly. It wraps at both ends and
tells its user when it does.

This is the approved specification of the block the verification eval case
`dv/equiv-updown` verifies. It was written for this repository in our own
words; an up/down counter with load and wrap flags is the usual shape of the
block and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`, except `carry` and
`borrow`, which follow `q`, `en`, `load` and `up` with no clock edge.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst` | in | 1 | Reset, active high, synchronous. |
| `load` | in | 1 | Parallel load. |
| `din` | in | 4 | The value `load` puts in `q`. |
| `en` | in | 1 | Count enable. |
| `up` | in | 1 | Count direction: high counts up, low counts down. |
| `q` | out | 4 | The count: a register, it changes only at a rising edge. |
| `carry` | out | 1 | High while the counter is counting up from 15. |
| `borrow` | out | 1 | High while the counter is counting down from 0. |

## 2. Behaviour

The block's state is the count `q`, 4 bits, and it is the `q` output. Every one
of the 16 values is reachable (by `load`).

- At a rising edge with `rst` high, `q` loads 0, whatever `load` and `en` hold. [req:UD-RESET]
- At a rising edge with `rst` low and `load` high, `q` loads `din`, whatever `en` holds. [req:UD-LOAD]
- At a rising edge with `rst` and `load` low and `en` high, `q` goes up by one if `up` is high and down by one if it is low, modulo 16 (15 goes to 0 up, 0 goes to 15 down). [req:UD-COUNT]
- With `rst`, `load` and `en` all low, `q` does not change. [req:UD-HOLD]
- `carry` is high exactly while `load` is low, `en` is high, `up` is high and `q` is 15. `borrow` is high exactly while `load` is low, `en` is high, `up` is low and `q` is 0. [req:UD-FLAGS]

## 3. Equivalence obligation

A refactor of this block (the same module name, ports and state register, with
its next-state and output logic rewritten) must match it at every output for
every input sequence from reset. The verification checks this by logic
equivalence, not by simulation of chosen inputs.
