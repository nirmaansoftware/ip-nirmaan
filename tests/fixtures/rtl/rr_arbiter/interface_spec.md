# Interface specification: `rr_arbiter`

A round-robin arbiter: `N` requesters share one resource, and each cycle at
most one of them is granted it. This is an M26 fixture: the specification a
spec engineer hands to the microarchitecture and RTL seats.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `N` | 4 | Number of requesters. Any value of 2 or more; it need not be a power of two. |

## 2. Ports

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `req` | in | `N` | Bit `i` is high while requester `i` wants the resource. |
| `grant` | out | `N` | Bit `i` is high in a cycle where requester `i` has the resource. |

## 3. Behavior

* **One grant at most.** `grant` is one-hot or zero in every cycle, and a bit
  of `grant` is high only when the same bit of `req` is high.
* **Work conserving.** If any request is high, one is granted in that cycle.
* **Same-cycle grant.** `grant` is a combinational function of `req` and the
  arbiter's state: a request is answered in the cycle it is raised. A grant
  lasts one cycle; a requester that needs more cycles keeps `req` high and
  competes again.
* **Round-robin order.** The arbiter keeps a priority pointer. The winner is
  the first requester with `req` high at or after the pointer, searching
  upwards and wrapping from `N-1` to 0. On every rising edge with a grant, the
  pointer moves to one past the winner, so the winner has the lowest priority
  in the next cycle.

## 4. Fairness

* A requester that holds `req` high is granted within `N` cycles, counting
  the cycle it is granted: it waits at most `N-1` cycles while others are
  granted, whatever the other requesters do.
* With every requester requesting, grants rotate strictly: `0, 1, ..., N-1,
  0, ...` after reset.

## 5. Reset

* `rst_n` is active low and sampled on the rising edge of `clk`.
* After reset the pointer is 0: requester 0 has the highest priority.
* `grant` still follows `req` during reset (it is combinational); the pointer
  does not move until reset is released.

## 6. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  checks `grant` every cycle against a reference pointer model and checks
  that no held request waits `N` cycles, at the default `N` and at an `N`
  that is not a power of two. It must cover no requests, each requester
  alone, everyone requesting, a held request among changing others, the
  longest fair wait (`N-1` cycles), and reset during traffic.
* Synthesizes with Yosys, with no latches.
* A formal proof that the grant is one-hot or zero, only to a requester, and
  work conserving; that it follows round-robin order from the pointer; that
  the pointer moves one past the winner; and that a held request waits at
  most `N-1` cycles.
