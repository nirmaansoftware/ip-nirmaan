# Microarchitecture: `updown_counter`

How the approved RTL (`updown_counter.v`) and its approved refactor
(`updown_counter_refactor.v`) meet `interface_spec.md`. It is not given to the
eval seats: a verification seat works from the specification and the RTL
itself.

## State

One 4-bit register, `q`, the count and the output itself. It is the block's
whole state in both versions, under the same name, so an equivalence checker
matches the two by name and compares only the logic between the register and
what it drives.

## Next state and outputs

`updown_counter.v` adds or subtracts one with the 4-bit adder and takes the
low four bits. `carry` is `en && !load && up && q == 4'd15` and `borrow` is
`en && !load && !up && q == 4'd0`.

`updown_counter_refactor.v` toggles bits instead: counting up toggles bit `i`
when every lower bit is 1; counting down toggles bit `i` when every lower bit
is 0. `carry` and `borrow` are the same cases as the carry out of that chain.
