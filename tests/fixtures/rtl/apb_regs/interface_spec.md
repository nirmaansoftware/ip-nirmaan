# Interface specification: `apb_regs`

A block of four 32-bit control and status registers behind an APB4
subordinate port. This is an M26 fixture, the APB sibling of the AXI4-Lite
block in `../axi4_lite/`: the specification a spec engineer hands to the
microarchitecture and RTL seats.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `ADDR_WIDTH` | 8 | Byte address width. 8 bits give the block a 256-byte slot, of which 16 bytes are registers. |
| `DATA_WIDTH` | 32 | Data bus width. `pstrb` is `DATA_WIDTH/8` bits wide. |

Only the defaults are required to work. Any other value is outside this
specification.

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
| `pwdata` | in | `DATA_WIDTH` | Write data. |
| `pstrb` | in | `DATA_WIDTH/8` | Write byte enables; bit `n` enables byte `n` (bits `8n+7:8n`). Low for reads. |
| `prdata` | out | `DATA_WIDTH` | Read data. |
| `pready` | out | 1 | High when the access phase completes. |
| `pslverr` | out | 1 | Transfer error, valid in the cycle the transfer completes. |

The protection signal `pprot` is not part of this interface: the registers
have no access protection.

## 3. Register map

| Offset | Name | Access | Reset value |
|---|---|---|---|
| `0x0` | `REG0` | read/write | `0x00000000` |
| `0x4` | `REG1` | read/write | `0x00000000` |
| `0x8` | `REG2` | read/write | `0x00000000` |
| `0xC` | `REG3` | read/write | `0x00000000` |

Each register is a plain 32-bit storage register: a read returns the last
value written, byte by byte, as enabled by `pstrb`.

## 4. Transfers

* **APB4 protocol.** Every transfer is a setup phase (`psel` high, `penable`
  low) for one cycle, then an access phase (`psel` and `penable` high) that
  lasts until `pready` is high. The manager keeps `paddr`, `pwrite`, `pwdata`
  and `pstrb` stable from setup to the end of the access phase.
* **Zero wait states.** `pready` is always high, so every access phase is one
  cycle and every transfer takes two cycles. Transfers may follow back to
  back (a new setup phase in the cycle after an access phase) or with idle
  cycles between them.
* **Writes** take effect on the rising edge that ends the access phase. Only
  the bytes whose `pstrb` bit is set are written. A write with `pstrb` all
  zero changes nothing and completes without error.
* **Reads** return the addressed register on `prdata` during the access
  phase.
* Outside the access phase, `prdata` and `pslverr` are zero.

## 5. Responses and unmapped addresses

* A mapped transfer completes with `pslverr` low.
* **Policy for unmapped addresses: PSLVERR**, the same policy as the AXI4-Lite
  block's SLVERR. An address is mapped only when it is word aligned
  (`paddr[1:0] == 0`) and is one of `0x0`, `0x4`, `0x8`, `0xC`. Every other
  address in the slot (misaligned, or `0x10` and above) is unmapped.
  * An unmapped write changes no register and completes with `pslverr` high.
  * An unmapped read returns `prdata` of zero with `pslverr` high.
* The error is reported in the access phase, the one cycle APB4 defines it in.

## 6. Reset

* `presetn` is active low and sampled on the rising edge of `pclk`.
* During and after reset, every register holds its reset value (zero).
* The manager keeps `psel` low while `presetn` is low.

## 7. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  covers: reset values; write then read of every register; `pstrb` partial
  writes; back-to-back transfers and idle gaps; the PSLVERR policy for
  misaligned and out-of-range addresses; zero wait states; quiet `prdata` and
  `pslverr` outside the access phase; and reset again.
* Synthesizes with Yosys, with no latches.
* A formal proof of the protocol and register rules: `pready` in every access
  phase, quiet responses outside it, `pslverr` and `prdata` by the address
  policy, and registers that change only in a mapped write access, in the
  strobed bytes, to the written data.
