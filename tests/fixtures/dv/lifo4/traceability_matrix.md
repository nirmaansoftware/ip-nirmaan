# Requirement-to-plan matrix: `lifo4`

The approved output of the plan-audit stage for the block `lifo4`, a stack of four
8-bit words (`interface_spec.md`). It lists each requirement, the functional
coverage scenarios that show the block does it, and the contract the signoff
seat's coverage model is built to. The model plans one bin for every scenario here.

## 1. Block

Ports, all synchronous to the rising edge of `clk`: `clk`, `rst_n` (reset, active
low, synchronous), `push`, `pop`, `din` (8 bits), `dout` (8 bits: the top word, or
zero when empty), `count` (3 bits, 0 to 4), `empty` (high when `count` is 0), `full`
(high when `count` is 4) and `err` (sticky, cleared by reset).

## 2. Requirements and scenarios

Each rule applies at a rising edge with `rst_n` high, to the port values just before the edge.

| Requirement | Rule | Coverage scenario |
|---|---|---|
| LIFO-PUSH | A push alone, stack not full, stores `din` on top and raises `count` by one. | cross: push alone with the stack empty; push alone with the stack neither empty nor full |
| LIFO-POP | A pop alone, stack not empty, lowers `count` by one. | cross: pop alone with the stack full; pop alone with the stack neither empty nor full |
| LIFO-OVERFLOW | A push alone with the stack full changes nothing except that it sets `err`. | cross: push alone with the stack full |
| LIFO-UNDERFLOW | A pop alone with the stack empty changes nothing except that it sets `err`. | cross: pop alone with the stack empty |
| LIFO-REPLACE | A push and a pop together, stack not empty, replace the top word and leave `count` and `err` alone. | cross: both with the stack neither empty nor full; both with the stack full |
| LIFO-BOTH-EMPTY | A push and a pop together on an empty stack act as a push alone and set no error. | cross: both with the stack empty |
| LIFO-RESET | Reset empties the stack and clears `err`. | reset applied while the stack holds a word |
| (all) | The stack reaches every fill level. | occupancy 0, occupancy 1, occupancy 2, occupancy 3, occupancy 4 |

Fifteen scenarios in all: nine crosses (operation: push alone, pop alone, push and
pop together; occupancy: empty, neither empty nor full, full), five occupancies and
one reset. No scenario is waived.

## 3. The coverage model

One SystemVerilog file, a module `lifo4_fcov`, delivered in the artifact kind
`coverage_report`. As comments at its top it holds the closure statement: each
planned bin, and each exclusion with its reason. Its ports are exactly:

```
module lifo4_fcov (
    input  logic       clk, rst_n, push, pop,
    input  logic [7:0] din, dout,
    input  logic [2:0] count,
    input  logic       empty, full, err,
    output int         planned,   // how many bins the model plans
    output int         holes      // how many of them have not been hit yet
);
```

- The model samples at every rising edge of `clk` and sees the port values just before
  that edge (the stimulus changes 1 ns after an edge). `count`, `empty` and `full` are
  the stack as it stood before the edge.
- A bin is planned from a scenario above, never from what the RTL happens to do.
- `planned` is the number of bins the model tracks and `holes` the number not yet hit. A
  bin may be excluded only with a written reason, and an excluded bin is counted neither
  in `planned` nor in `holes`. This matrix names no scenario the stack cannot reach.
- The testbench that closes the model is held out. It drives the block, reads `planned`
  and `holes` after its last cycle, and fails the run when `planned` is below fifteen or
  any hole is left.
