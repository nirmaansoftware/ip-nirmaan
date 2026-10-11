# Interface specification: `sync_fifo`

A first-in, first-out buffer with one clock for both sides. This is an M26
fixture: the specification a spec engineer hands to the microarchitecture and
RTL seats.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `DEPTH` | 8 | Number of entries. Any value of 2 or more; it need not be a power of two. |
| `WIDTH` | 8 | Bits per entry. Any value of 1 or more. |

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `wr_en` | in | 1 | Write request. |
| `wr_data` | in | `WIDTH` | Data to write. |
| `full` | out | 1 | The FIFO holds `DEPTH` entries. |
| `rd_en` | in | 1 | Read request. |
| `rd_data` | out | `WIDTH` | The oldest entry, valid while `empty` is low. |
| `empty` | out | 1 | The FIFO holds no entries. |
| `count` | out | `$clog2(DEPTH+1)` | Entries held, from 0 to `DEPTH`. |

## 3. Behavior

* **Write.** A write is accepted on a rising edge where `wr_en` is high and
  `full` is low: `wr_data` becomes the newest entry.
* **Read.** A read is accepted on a rising edge where `rd_en` is high and
  `empty` is low: the oldest entry is removed.
* **First-word fall-through.** While `empty` is low, `rd_data` already shows
  the oldest entry, before any read is requested. The read that removes it is
  the one that consumes it. While `empty` is high, `rd_data` is undefined.
* **Write and read together.** Both are accepted in the same cycle when
  neither flag blocks them: `count` is unchanged.
  * When empty, only the write is accepted (there is nothing to read).
  * When full, only the read is accepted (there is no room to write).
* **Order.** Entries are read in the order they were written, each exactly
  once, with the data written.

## 4. Overflow and underflow policy

* A write while `full` is **dropped**: no entry changes and `count` stays at
  `DEPTH`. It is the writer's job to watch `full`.
* A read while `empty` is **ignored**: nothing changes and `count` stays at 0.
* Neither case is an error signal: the flags are the contract.

## 5. Flags and latency

* `full`, `empty` and `count` describe the state after the last rising edge.
  `full` is high exactly when `count == DEPTH`, `empty` exactly when
  `count == 0`, and they are never high together.
* A written entry is visible at `rd_data` (and `empty` falls) in the cycle
  after the write is accepted: write-to-read latency is 1 cycle.
* Throughput is one write and one read per cycle.

## 6. Reset

* `rst_n` is active low and sampled on the rising edge of `clk`.
* After reset the FIFO is empty: `empty` high, `full` low, `count` zero. Any
  entries held before reset are discarded.
* Requests during reset are ignored.

## 7. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  checks `full`, `empty`, `count` and `rd_data` every cycle against a
  reference queue, at the default parameters and at a depth that is not a
  power of two. It must cover filling to full, a write while full, draining
  to empty, a read while empty, a write and a read together when empty, when
  full and in between, pointer wrap-around, and reset during traffic.
* Synthesizes with Yosys, with no latches.
* A formal proof that the flags are consistent and never both high, `count`
  stays in range and moves only by accepted requests, a write while full and a
  read while empty change nothing, and an entry is read back unchanged.
