# Interface specification: `mac8`

A multiply-accumulate block for a small filter datapath. Each cycle the
sender may offer a pair of 8-bit unsigned operands; the block adds their
product to a 24-bit running total that saturates instead of wrapping and
remembers that it did.

This is the approved specification of the block the verification eval case
`dv/scoreboard-mac` verifies. It was written for this repository in our own
words and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `clr` | in | 1 | Clear the total and the saturation flag. |
| `en` | in | 1 | `a` and `b` hold the next operands. |
| `a` | in | 8 | First operand, unsigned. |
| `b` | in | 8 | Second operand, unsigned. |
| `acc` | out | 24 | The running total, unsigned. |
| `sat` | out | 1 | The total has saturated since the last clear. |

## 2. Behaviour

The block keeps a 24-bit total and a flag. Both are registers: `acc` and `sat`
show what the last rising edge wrote.

### 2.1 Reset and clear

- While `rst_n` is low at a rising edge, the total loads 0 and the flag loads 0. [req:MAC-RESET]
- At a rising edge with `rst_n` high and `clr` high, the total loads 0 and the flag loads 0, whatever `en`, `a` and `b` hold: the clear wins over an accumulate offered at the same edge. [req:MAC-CLEAR]

### 2.2 Accumulating

At a rising edge with `rst_n` high, `clr` low and `en` high, the product of
`a` and `b`, both read as unsigned numbers, is added to the total. [req:MAC-ACC]

With `en` low and `clr` low the total and the flag do not change. [req:MAC-HOLD]

### 2.3 Saturation

- If the sum of the total and the product would be more than 0xFFFFFF, the total loads 0xFFFFFF instead of the wrapped sum, and the flag loads 1. [req:MAC-SAT]
- The flag stays 1 through every later edge, whatever is offered, until a clear or a reset. [req:MAC-STICKY]
