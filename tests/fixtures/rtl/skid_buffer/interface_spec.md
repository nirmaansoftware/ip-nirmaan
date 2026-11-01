# Interface specification: `skid_buffer`

A register slice for one valid/ready stream: it sits between a sender and a
receiver, adds one cycle of latency, and breaks every timing path between
them, including the ready path back to the sender, while still moving one
beat per cycle. This is the upstream specification of the eval case
`rtl/skid-buffer` (P3-E3).

The two-register structure is the usual one for this job; the ZipCPU article
on building a skid buffer
(<https://zipcpu.com/blog/2019/05/22/skidbuffer.html>) describes it. This
specification is written in our own words and copies nothing from that
article.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `WIDTH` | 8 | Bits in a beat, 1 or more. |

The block must work at every `WIDTH`; nothing in its control depends on it.

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `s_valid` | in | 1 | Upstream: the sender offers a beat. |
| `s_ready` | out | 1 | Upstream: the slice can take a beat. |
| `s_data` | in | `WIDTH` | Upstream: the beat offered. |
| `m_valid` | out | 1 | Downstream: the slice offers a beat. |
| `m_ready` | in | 1 | Downstream: the receiver can take a beat. |
| `m_data` | out | `WIDTH` | Downstream: the beat offered. |

## 3. Transfers

* A beat moves on a rising edge when both its side's valid and ready are
  high on that edge: upstream when `s_valid` and `s_ready` are high, and
  downstream when `m_valid` and `m_ready` are high. Nothing else moves a beat.
* The slice holds at most two beats. `m_valid` is high exactly while it holds
  at least one, and `m_data` is then the oldest beat it holds.
* `s_ready` is high exactly while it holds at most one beat, whatever
  `m_ready` and `s_valid` are doing in that cycle.
* Beats leave in the order they arrived, each exactly once, with their data
  unchanged.
* **Latency.** A beat accepted on edge `E` is offered downstream after `E`.
* **Full throughput.** While `m_ready` is high and the sender offers a beat on
  every cycle, one beat enters and one leaves on every edge, with no bubble.
* **Stall.** When the receiver holds `m_ready` low with one beat offered, the
  slice still accepts one more beat. With two beats held, `s_ready` is low
  until a beat leaves.
* **Hold.** A beat offered downstream and not taken stays offered, with the
  same data, on the next cycle.
* The slice does not require the sender to keep `s_valid` or `s_data` stable
  while `s_ready` is low: a beat that is not accepted is simply not taken.

## 4. Registered outputs

`s_ready`, `m_valid` and `m_data` are each driven from a flop (an inverter
after a flop counts), with no combinational path from `m_ready`, `s_valid` or
`s_data` to any output. This is what lets the slice cut a timing path; a
ready computed from `m_ready` breaks it even when no beat is lost.

## 5. Reset

`rst_n` is active low and sampled on the rising edge of `clk`. Reset drops
every held beat: afterwards `m_valid` is low and `s_ready` is high. The data
outputs are not defined while `m_valid` is low.

## 6. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers, at `WIDTH` 8 and 1.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  covers: reset values; the one-cycle latency; a long stream at full
  throughput; a stall with one beat held (a second must be accepted) and with
  two (a third must not); ready rising after a stall, with every beat out in
  order and once; the hold rule; a ready that does not move with `m_ready` or
  `s_valid` inside a cycle; random traffic against a model, ending in a drain;
  and reset with beats held.
* Synthesizes with Yosys, with no latches.
* A formal proof that the ports behave as a queue of up to two beats under
  the rules above, at `WIDTH` 8 and 1, with covers that show a stall, a full
  slice, a drain and full throughput are reached.
