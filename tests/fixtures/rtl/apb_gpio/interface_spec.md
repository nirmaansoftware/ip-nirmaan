# Interface specification: `apb_gpio`

A general-purpose I/O block with up to 32 pins behind an APB4 subordinate
port: output data and output enable per pin, a sampled input, rising-edge,
falling-edge, high-level and low-level interrupt detection, an interrupt
enable mask, and a write-1-to-clear interrupt status. This is the upstream
specification of the eval case `rtl/apb-gpio` (P3-E2). Its APB behavior is the
same as the register block in `../apb_regs/`.

The register set has the usual shape of open GPIO blocks; the OpenTitan GPIO
documentation (<https://opentitan.org/book/hw/ip/gpio/>) informed it. This
specification is written in our own words, with its own register map, and
copies nothing from that documentation.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `ADDR_WIDTH` | 8 | Byte address width. Only 8 is required. |
| `N` | 8 | Number of pins, 1 to 32. |

The block must work at every `N` from 1 to 32.

## 2. Ports

All signals are synchronous to the rising edge of `pclk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `pclk` | in | 1 | Clock. |
| `presetn` | in | 1 | Reset, active low, synchronous. |
| `paddr` | in | `ADDR_WIDTH` | Byte address. |
| `psel` | in | 1 | Select: a transfer to this subordinate is in progress. |
| `penable` | in | 1 | High in the access phase of a transfer. |
| `pwrite` | in | 1 | High for a write, low for a read. |
| `pwdata` | in | 32 | Write data. |
| `pstrb` | in | 4 | Write byte enables; bit `n` enables bits `8n+7:8n`. Low for reads. |
| `prdata` | out | 32 | Read data. |
| `pready` | out | 1 | High when the access phase completes. |
| `pslverr` | out | 1 | Transfer error, valid in the cycle the transfer completes. |
| `gpio_in` | in | `N` | Pin inputs, synchronous to `pclk` (the integrator synchronizes external pins). |
| `gpio_out` | out | `N` | Pin output values. |
| `gpio_oe` | out | `N` | Pin output enables: 1 drives the pin. |
| `irq` | out | 1 | Interrupt, active high, level sensitive. |

## 3. Register map

Every register is 32 bits; bit `i` belongs to pin `i`. Bits `N` and up read
as zero and ignore writes. Every register resets to zero.

| Offset | Name | Access | Meaning of a 1 in bit `i` |
|---|---|---|---|
| `0x00` | `DATA_OUT` | read/write | `gpio_out[i]` is driven high |
| `0x04` | `DIR` | read/write | `gpio_oe[i]` is high: pin `i` is an output |
| `0x08` | `DATA_IN` | read only | the sampled `gpio_in[i]` is high |
| `0x0C` | `INTR_RISE` | read/write | a rising edge on pin `i` is detected |
| `0x10` | `INTR_FALL` | read/write | a falling edge on pin `i` is detected |
| `0x14` | `INTR_HIGH` | read/write | a high level on pin `i` is detected |
| `0x18` | `INTR_LOW` | read/write | a low level on pin `i` is detected |
| `0x1C` | `INTR_ENABLE` | read/write | a pending status bit `i` raises `irq` |
| `0x20` | `INTR_STATUS` | write 1 to clear | a detected condition on pin `i` is pending |

* The read/write registers are written byte by byte as `pstrb` enables.
* `gpio_out` is `DATA_OUT` and `gpio_oe` is `DIR`, bit for bit.
* `DATA_IN` cannot be written: a write gets PSLVERR and changes nothing.
* `INTR_STATUS`: a write clears each bit written 1 in a byte whose `pstrb`
  bit is set. Bits written 0, and bits in unstrobed bytes, keep their value.

## 4. Sampling and detection

* On every rising edge the block samples `gpio_in`; `DATA_IN` reads the last
  sample. A pin change driven before edge `E` reads in `DATA_IN` after `E`.
* Detection compares the last sample with the one before it, using the
  detection enables as they are before the edge:
  * rising edge: the last sample is 1 and the one before it 0;
  * falling edge: the last sample is 0 and the one before it 1;
  * high level: the last sample is 1;
  * low level: the last sample is 0.
* A detected condition on pin `i` sets `INTR_STATUS` bit `i` on the next
  edge. A pin change driven before edge `E` is sampled on `E` and sets the
  status on `E + 1`.
* An edge sets the status once. A level sets it on every edge while the level
  holds and its enable is set, so a clear does not stick until the level
  goes away.
* **A detection beats a clear.** When a condition is detected on the edge a
  clear of the same bit takes effect, the bit stays set.
* After reset both samples are zero.

`irq` is high whenever any bit is set in both `INTR_STATUS` and
`INTR_ENABLE`. `INTR_ENABLE` masks the interrupt only: a masked condition
still sets its status bit.

## 5. Transfers

* **APB4 protocol.** Every transfer is a setup phase (`psel` high, `penable`
  low) for one cycle, then an access phase (`psel` and `penable` high) that
  lasts until `pready` is high. The manager keeps `paddr`, `pwrite`, `pwdata`
  and `pstrb` stable from setup to the end of the access phase.
* **Zero wait states.** `pready` is always high, so every transfer takes two
  cycles.
* **Writes** take effect on the rising edge that ends the access phase.
* **Reads** return the addressed register on `prdata` during the access phase.
* Outside the access phase, `prdata` and `pslverr` are zero.

## 6. Responses and unmapped addresses

* An address is mapped only when it is word aligned (`paddr[1:0] == 0`) and
  is one of the nine register offsets, `0x00` to `0x20`. Every other address
  (unaligned, or `0x24` and above) is unmapped.
* An unmapped write changes nothing and completes with `pslverr` high; so does
  a write to `DATA_IN`. An unmapped read returns zero with `pslverr` high.
* Every other transfer completes with `pslverr` low.

## 7. Reset

`presetn` is active low and sampled on the rising edge of `pclk`. Reset puts
every register and both input samples at zero, so `gpio_out`, `gpio_oe` and
`irq` are low. The manager keeps `psel` low while `presetn` is low.

## 8. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers, at `N` 8 and 32.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  covers: reset values; every read/write register with partial strobes and
  bits above `N`; `gpio_out` and `gpio_oe`; `DATA_IN`, read only; the PSLVERR
  policy; each kind of detection, including an edge that fires once and a
  level that sets the status again after a clear; write-1-to-clear of some
  pending bits only; the interrupt mask; and reset again.
* Synthesizes with Yosys, with no latches.
* A formal proof of the protocol and of every register against the rules
  above, with covers that show each detection and response path is reached.
