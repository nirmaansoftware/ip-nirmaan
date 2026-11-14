# Interface specification: `crc8_block`

A byte-at-a-time CRC engine for a framing layer. A sender feeds the bytes of a
frame one per clock; after the last byte the `crc` output is the frame's check
value, which the sender appends and the receiver compares.

This is the approved specification of the block the verification eval case
`dv/random-crc` verifies. It was written for this repository in our own words;
it describes an 8-bit CRC with a stated polynomial, start value and final
inversion, and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `init` | in | 1 | Start a new frame: reload the start value. |
| `valid` | in | 1 | `data` holds the next byte of the frame. |
| `data` | in | 8 | The byte, most significant bit first. |
| `crc` | out | 8 | The check value of the bytes taken since the last reload. |

## 2. Behaviour

The block keeps an 8-bit running value. The start value is `0xFF`.

### 2.1 Reset and start

- While `rst_n` is low at a rising edge, the running value loads `0xFF`. [req:CRC-RESET]
- At a rising edge with `rst_n` high and `init` high, the running value loads `0xFF`, whatever `valid` and `data` hold: the reload wins over a byte offered at the same edge. [req:CRC-INIT]

### 2.2 Taking a byte

At a rising edge with `rst_n` high, `init` low and `valid` high, the running
value takes the byte `data` as follows. For each bit of the byte, from bit 7
down to bit 0: XOR that bit into the top bit of the running value, then shift
the running value left by one place, and if the bit shifted out was 1, XOR the
result with the polynomial `0x07` (x^8 + x^2 + x + 1). [req:CRC-POLY]

- The bytes are taken as written: bit 7 first, no bit reversal of the byte
  and none of the running value. [req:CRC-ORDER]

With `valid` low and `init` low the running value does not change. [req:CRC-HOLD]

### 2.3 The check value

- `crc` is the running value with every bit inverted (XOR `0xFF`). It follows the running value with no clock edge. [req:CRC-FINAL]
- Right after reset or a reload, with no byte taken, `crc` is `0x00`. [req:CRC-EMPTY]
