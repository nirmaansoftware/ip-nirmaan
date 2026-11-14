# Interface specification: `gray_counter`

A 4-bit counter whose output is Gray coded, for a value that crosses a clock
boundary: only one output bit changes at each count, so a receiver that samples
at any moment sees either the old or the new value, never a third.

This is the approved specification of the block the verification eval case
`dv/equiv-gray` verifies. It was written for this repository in our own words;
the Gray code (the binary count XORed with itself shifted right by one) is
standard and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst` | in | 1 | Reset, active high, synchronous. |
| `en` | in | 1 | Count enable. |
| `gray` | out | 4 | The count, Gray coded: a register, it changes only at a rising edge. |
| `wrap` | out | 1 | High while `en` is high and the count is at its last value. |

## 2. Behaviour

The block's state is the Gray-coded count, 4 bits, and it is the `gray` output.
The sequence is the standard reflected Gray code, 16 codes, from the binary
count 0 to 15 (the code of a binary count is the count XORed with itself
shifted right by one place):

| Count | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gray` | 0000 | 0001 | 0011 | 0010 | 0110 | 0111 | 0101 | 0100 | 1100 | 1101 | 1111 | 1110 | 1010 | 1011 | 1001 | 1000 |

- At a rising edge with `rst` high, `gray` loads 0000 (count 0), whatever `en` holds. [req:GC-RESET]
- At a rising edge with `rst` low and `en` high, `gray` goes to the next code of the sequence, and the code of count 15 (1000) goes to the code of count 0 (0000). Exactly one bit of `gray` changes at every such edge. [req:GC-COUNT]
- With `rst` low and `en` low, `gray` does not change. [req:GC-HOLD]
- `wrap` is high exactly while `en` is high and `gray` is the code of count 15 (1000), so it marks the edge at which the count wraps. It follows `gray` and `en` with no clock edge. [req:GC-WRAP]

## 3. Equivalence obligation

A refactor of this block (the same module name, ports and state register, with
its next-state and output logic rewritten) must match it at every output for
every input sequence from reset. The verification checks this by logic
equivalence, not by simulation of chosen inputs.
