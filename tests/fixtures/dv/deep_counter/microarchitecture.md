# Microarchitecture: `deep_counter`

How the approved RTL (`deep_counter.v`) meets `interface_spec.md`. It is not
given to the eval seats: a verification seat works from the specification
and the RTL itself.

## State

One 7-bit register, `count`, cleared while `rst_n` is low or `clr` is high
at a rising edge. It is the block's whole state, and it is a port.

## Next state and carry

With `at_last = (count == LIMIT)`, at each edge out of reset with `clr` low:
`count` becomes 0 when `en & at_last`, `count + 1` when `en & ~at_last`, and
holds otherwise. `carry = en & ~clr & at_last`, through logic with no flop.

## Why the proof is deep

From reset the counter needs `LIMIT + 1` enabled edges to wrap, 100 at the
default, and 64 to set its top bit. A bounded model check must unroll that
many cycles to see either. The next-state rule depends only on `count` and the
inputs, so a property that ties `count` to a model of the specification is
inductive: it holds after one edge from any state where it held, and
k-induction proves it for every cycle with a short unrolling.
