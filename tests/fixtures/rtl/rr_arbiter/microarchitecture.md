# Microarchitecture: `rr_arbiter`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`rr_arbiter.v`.

## 1. State: one priority pointer

* The only state is `ptr`, `$clog2(N)` bits: the index of the requester with
  the highest priority this cycle. It resets to 0.
* A one-hot priority mask would work as well; an index is smaller for large
  `N` and makes the round-robin rule easy to state and to prove.

## 2. Grant logic: a wrapping priority search

A combinational loop walks the requesters from `ptr` upwards, wrapping from
`N-1` to 0 by comparing against `LAST` (`N-1`), so an `N` that is not a power
of two works. The first requester found with `req` high wins: its `grant` bit
is set and its index is kept in `winner`. Every output of the block is
assigned a default before the loop, so synthesis sees pure logic and no
latch.

* The loop has `N` steps; Yosys unrolls it into a priority chain. That is
  fine for the small `N` this block is meant for. A large `N` would use the
  double-width masked priority encoder instead, which has the same behavior.
* `grant` is combinational from `req` and `ptr`: a requester is answered in
  the cycle it asks. There is no path from `grant` back to `req` inside the
  block.

## 3. Pointer update

On a rising edge where anything was granted, `ptr` becomes `winner + 1`
(wrapping). With no request, `ptr` holds. This is what makes the order fair:
the pointer only ever moves forward past the winner, so on every cycle a
held request is not granted, the pointer comes at least one step closer to
it. It started at most `N-1` steps away, so it waits at most `N-1` cycles.

## 4. Reset behavior

`rst_n` is synchronous and active low. On reset `ptr` goes to 0. `grant`
is not gated by reset: during reset it still names the first requester from
the current pointer, and the pointer does not move.

## 5. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers | Verilator | `rr_arbiter.v` |
| Directed and random self-checking simulation | Icarus and Verilator | `rr_arbiter_tb.v` |
| Failure path is a failed run | Icarus and Verilator | `rr_arbiter_tb_fail.v` |
| Synthesis, no latches | Yosys | `rr_arbiter.v` |
| Arbitration properties, unbounded proof, N 4 | SymbiYosys | `rr_arbiter.sby` |
| The same proof at N 5 | SymbiYosys | `rr_arbiter_n5.sby` |

The testbench runs two arbiters side by side, N 4 and N 5, each against a
reference pointer model checked on every rising edge, with per-requester
wait counters for fairness and coverage counters that fail the run if a case
in the interface spec was not reached.

The formal block (under `ifdef FORMAL` in the RTL) asserts: the pointer is in
range and is 0 after reset; the grant is one-hot or zero, only to a
requester, and work conserving; no requester sits between the pointer and
the winner; after a grant the pointer is one past the winner; and each
requester's count of cycles waited with its request held never exceeds
`N-1`, with the induction invariant that the wait plus the pointer's distance
to the requester stays within `N-1`.
