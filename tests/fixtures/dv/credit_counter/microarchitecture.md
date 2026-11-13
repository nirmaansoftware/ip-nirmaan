# Microarchitecture: `credit_counter`

How the approved RTL (`credit_counter.v`) meets `interface_spec.md`. It is
not given to the eval seats: a verification seat works from the
specification and the RTL itself.

## State

Two registers, both loaded while `rst_n` is low at a rising edge:

| Register | Reset | Holds |
|---|---|---|
| `credits` | `MAX` | the credits held, 8 bits |
| `err` | 0 | the sticky error flag |

`credits` and `err` are the block's whole state, and both are ports.

## Next state

With `empty = (credits == 0)`, `at_max = (credits == MAX)`,
`take_only = take & ~give` and `give_only = give & ~take`, at each edge out
of reset:

- `credits` goes down by one on `take_only & ~empty`, else up by one on
  `give_only & ~at_max`, else holds; a take and a give together hold it;
- `err` is set on `take_only & empty` or `give_only & at_max` and otherwise
  keeps its value, so only a reset clears it.

## Outputs

`avail = ~empty` and `full = at_max`, from `credits` through logic with no
added flop.
