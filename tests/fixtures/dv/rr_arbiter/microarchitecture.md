# Microarchitecture: `rr_arbiter`

How the approved RTL (`rr_arbiter.v`) meets `interface_spec.md`. It is not
given to the eval seats: a verification seat works from the specification and
the RTL itself.

## State

One 2-bit register, `last`, loaded with 2 while `rst_n` is low. It is the
block's whole state and a port.

## Grant

A case on `last` lists the three requesters in priority order and takes the
first with its `req` bit set: after `last` = 2 the order is 0, 1, 2; after
`last` = 0 it is 1, 2, 0; after `last` = 1 it is 2, 0, 1. The value 3 of
`last` cannot be reached from reset; the case treats it like 2, so `grant`
stays at most one bit.

## Next state

When `grant` is not zero, `last` loads the index of the granted bit; otherwise
it holds.
