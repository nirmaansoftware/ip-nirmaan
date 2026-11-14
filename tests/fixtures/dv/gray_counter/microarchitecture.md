# Microarchitecture: `gray_counter`

How the approved RTL (`gray_counter.v`) and its approved refactor
(`gray_counter_refactor.v`) meet `interface_spec.md`. It is not given to the
eval seats: a verification seat works from the specification and the RTL
itself.

## State

One 4-bit register, `gray`, the Gray-coded count and the output itself. It is
the block's whole state in both versions, under the same name, so an
equivalence checker matches the two by name and compares only the logic
between the register and what it drives.

## Next state and outputs

`gray_counter.v` decodes `gray` to binary (each bit XORed with every bit
above it), adds one, and encodes the result again (XOR with itself shifted
right by one). `wrap` is `en && gray == 4'b1000`.

`gray_counter_refactor.v` steps the code directly, with no binary count: when
the parity of `gray` is even, bit 0 flips; when it is odd, the bit above the
lowest set bit flips (bit 3 flips when bit 3 is the lowest set bit, which is
the wrap from 1000 to 0000). `wrap` is `en & gray[3] & ~|gray[2:0]`.
