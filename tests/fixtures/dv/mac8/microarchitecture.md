# Microarchitecture: `mac8`

How the approved RTL (`mac8.v`) meets `interface_spec.md`. It is not given to
the eval seats: a verification seat works from the specification and the RTL
itself.

## State

A 24-bit register `acc` and a one-bit register `sat`.

## Next state

The product `a * b` is a 16-bit unsigned value. It is added to `acc` in 25
bits, so a carry out of bit 23 is seen. If bit 24 of the sum is set, `acc`
loads 0xFFFFFF and `sat` loads 1; otherwise `acc` loads the sum and `sat`
keeps its value. Reset and clear load zeros into both registers; reset and
clear are tested before `en`.

## Outputs

`acc` and `sat` are the registers themselves.
