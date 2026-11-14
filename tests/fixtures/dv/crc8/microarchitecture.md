# Microarchitecture: `crc8_block`

How the approved RTL (`crc8_block.v`) meets `interface_spec.md`. It is not
given to the eval seats: a verification seat works from the specification and
the RTL itself.

## State

One 8-bit register, `state`, the running value. It loads `0xFF` on reset and on
`init`, and takes a byte on `valid` (when `init` is low).

## Next state

`next_state(s, d)` is a function with a loop of eight steps, bit 7 of the byte
first: the byte's bit is XORed into the top bit of `s`, `s` shifts left by one,
and the polynomial `0x07` is XORed in when the bit shifted out was 1.

## Outputs

`crc` is `state ^ 8'hFF`, combinational.
