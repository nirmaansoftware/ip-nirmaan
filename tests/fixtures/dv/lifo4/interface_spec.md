# Interface specification: `lifo4`

A stack of four 8-bit words. A push stores a word on top, a pop removes the top
word, and a push and a pop in the same cycle replace the top word. The stack
refuses a push when it is full and a pop when it is empty, and remembers that it
did in a sticky error flag.

This is the approved specification of the block the verification eval case
`dv/fcov-lifo4` closes functional coverage for. It was written for this repository
in our own words; the push, pop and flag set is the usual shape of a small stack
and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `push` | in | 1 | Push request. |
| `pop` | in | 1 | Pop request. |
| `din` | in | 8 | The word a push stores. |
| `dout` | out | 8 | The top word, or zero when the stack is empty. |
| `count` | out | 3 | Number of words held, 0 to 4. |
| `empty` | out | 1 | High when `count` is 0. |
| `full` | out | 1 | High when `count` is 4. |
| `err` | out | 1 | Sticky: set by a refused push or a refused pop, cleared by reset. |

## 2. Behaviour

Each rule applies at a rising edge of `clk` with `rst_n` high, to the values the
ports hold just before the edge.

- A push alone, with the stack not full, stores `din` on top and raises `count` by one. [req:LIFO-PUSH]
- A pop alone, with the stack not empty, lowers `count` by one. [req:LIFO-POP]
- A push alone with the stack full changes nothing except that it sets `err`. [req:LIFO-OVERFLOW]
- A pop alone with the stack empty changes nothing except that it sets `err`. [req:LIFO-UNDERFLOW]
- A push and a pop together, with the stack not empty, replace the top word with `din` and leave `count` and `err` alone. [req:LIFO-REPLACE]
- A push and a pop together, with the stack empty, act as a push alone: the word is stored and `count` becomes one. They set no error. [req:LIFO-BOTH-EMPTY]
- Reset empties the stack and clears `err`. [req:LIFO-RESET]

## 3. The functional coverage model

The signoff seat's coverage model, its ports and its sampling rule are in `traceability_matrix.md`, section 3.
The model plans one bin per scenario that matrix names, and a testbench the seat never sees closes it.
