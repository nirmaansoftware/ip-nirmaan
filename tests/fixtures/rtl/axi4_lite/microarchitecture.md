# Microarchitecture: `axi4_lite_regs`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`axi4_lite_regs.v`.

## 1. Handshake choice: holding registers, not a skid buffer or an FSM

With one outstanding transaction per direction, a full skid buffer buys
nothing: the subordinate never needs to accept a second request while the
first is still waiting for its response. Instead:

* **READY is a function of state only.** `awready = !aw_held && !bvalid`,
  `wready = !w_held && !bvalid`, `arready = !rvalid`. No READY depends
  combinationally on a VALID input, so there are no combinational loops
  through the manager, and READY may be high before VALID arrives (which AXI
  allows).
* There is no explicit state machine. The write side's state is the pair of
  "held" flags plus `bvalid`; the read side's state is `rvalid`. Every
  combination of those flags is a legal state (checked in formal).

## 2. Address and data capture

* **Write address.** When AW is accepted without W (in the same or an earlier
  cycle), `awaddr` is captured in `aw_addr_q` and `aw_held` is set.
* **Write data.** When W is accepted without AW, `wdata` and `wstrb` are
  captured in `w_data_q` and `w_strb_q`, and `w_held` is set.
* **The write fires** in the cycle whose rising edge completes the pair:
  `do_write = (aw_held || aw_hs) && (w_held || w_hs)`. The address and data
  used are the held copy when one exists, else the live bus. This one rule
  handles AW first, W first, and both together with no special cases.
* **Read address** is not captured: it is decoded as it is accepted, and the
  selected register is loaded straight into `rdata`.

The holding registers (`aw_addr_q`, `w_data_q`, `w_strb_q`) are datapath and
are not reset; their "held" flags are.

## 3. Register file

* Four registers, `reg0` to `reg3`, as separate flops rather than a memory
  array, so every tool (Verilator, Icarus, Yosys) sees plain flip-flops and no
  memory inference is involved.
* A write updates one register through `merge(old, data, strb)`, which copies
  each byte of `data` whose strobe bit is set and keeps the other bytes.
* The register index is `addr[3:2]`.

## 4. Address decode and the SLVERR policy

`is_mapped(addr)` is true when `addr[1:0] == 0` and `addr >> 4 == 0`. With
`ADDR_WIDTH` 4 the second term is always true; it keeps the decode correct if
the address is ever widened.

* A write to an unmapped address still completes the handshake, updates no
  register, and returns `bresp = SLVERR`.
* A read from an unmapped address returns `rdata = 0` and `rresp = SLVERR`.

## 5. Response generation

* **B.** `bvalid` is set on the rising edge where `do_write` is true, with
  `bresp` chosen by the decode. It is cleared on the edge where
  `bvalid && bready`. While it is high, `awready` and `wready` are low, so no
  new write starts and `bresp` cannot change.
* **R.** `rvalid`, `rresp` and `rdata` are loaded on the edge where AR is
  accepted, and `rvalid` is cleared on the edge where `rvalid && rready`. While
  it is high `arready` is low, so the payload cannot change.
* **Latency** is 1 cycle for both (the bound in the spec is 2). Throughput is
  one transaction every 2 cycles per direction when the manager is always
  ready, which is enough for a control register block.

## 6. Reset behavior

`aresetn` is synchronous and active low. On reset: `aw_held`, `w_held`,
`bvalid` and `rvalid` clear (dropping any half-accepted write), `bresp` and
`rresp` go to OKAY, `rdata` to zero, and all four registers to zero. After
reset, `awready`, `wready` and `arready` are high.

## 7. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers | Verilator | `axi4_lite_regs.v` |
| Directed self-checking simulation | Icarus and Verilator | `axi4_lite_regs_tb.v` |
| Failure path is a failed run | Icarus and Verilator | `axi4_lite_regs_tb_fail.v` |
| Synthesis, no latches | Yosys | `axi4_lite_regs.v` |
| Handshake properties, unbounded proof | SymbiYosys | `axi4_lite_regs.sby` |

The testbench drives inputs after the falling edge and samples handshakes
before the rising edge, so it has no race with the design. Every transaction
checks the latency bound and that BRESP, RRESP and RDATA hold while the
response waits.

The formal block (under `ifdef FORMAL` in the RTL) assumes a manager that holds
VALID and its payload until READY, and asserts that: responses are low after
reset; B and R hold, with a stable payload, until taken; at most one request
per direction is open; BVALID and RVALID are high exactly when an accepted
request awaits its response (so a response never appears without a request,
and appears one cycle after it); and the response code follows the address
policy.
