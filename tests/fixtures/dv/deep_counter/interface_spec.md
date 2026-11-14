# Interface specification: `deep_counter`

A modulo counter with a long period, for timebases and timeouts: it counts
enabled cycles from 0 up to `LIMIT`, returns to 0 after `LIMIT`, and drives a
carry out on the cycle it wraps, so a second counter can be cascaded on it.
A synchronous clear restarts it.

This is the approved specification of the block the verification eval case
`dv/prove-deep-counter` verifies. It was written for this repository in our
own words; a modulo counter with enable, clear and carry out is a textbook
shape and copies no other document.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `LIMIT` | 99 | The last count before the counter returns to 0, 1 to 127. The period is `LIMIT + 1` enabled cycles. |

- The block works for every `LIMIT` from 1 to 127. [req:DC-PARAM]

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `en` | in | 1 | Count at this rising edge. |
| `clr` | in | 1 | Clear: restart from 0 at this rising edge. |
| `count` | out | 7 | The count, 0 to `LIMIT`. |
| `carry` | out | 1 | High while the next count edge wraps the counter. |

## 3. Behaviour

- While `rst_n` is low at a rising edge of `clk`, `count` clears to 0. [req:DC-RESET]
- At a rising edge where `rst_n` and `clr` are high, `count` becomes 0, whatever `en` is. [req:DC-CLEAR]
- At a rising edge where `rst_n` is high, `clr` is low and `en` is high, `count` goes up by one when it is below `LIMIT`, and becomes 0 when it equals `LIMIT`. [req:DC-COUNT]
- At a rising edge where `rst_n` is high and `clr` and `en` are low, `count` does not change. [req:DC-HOLD]
- `count` is never above `LIMIT`, so after reset it takes every value from 0 to `LIMIT` in turn and no other. [req:DC-RANGE]
- `carry` is high exactly when `en` is high, `clr` is low and `count` equals `LIMIT`; it follows the inputs and `count` with no clock edge. [req:DC-CARRY]

## 4. Notes for verification

At the default `LIMIT` the counter first wraps 100 enabled cycles after
reset, so a bounded check of a few dozen cycles never sees a wrap, the top
bit of `count`, or the carry. A proof that counts as one holds for every
cycle after reset (an unbounded proof, for example by induction), not only
for the cycles a bounded check unrolls.
