# Interface specification: `rr_arbiter`

A round-robin arbiter for three requesters that share one resource. Each
requester raises its `req` bit to ask for the resource; the arbiter raises
exactly one `grant` bit, and the requester that was served last goes to the
back of the line, so no requester waits for more than two other grants.

This is the approved specification of the block the verification eval case
`dv/formal-rr-arbiter` verifies. It was written for this repository in our own
words; rotating priority among a few requesters is the usual shape of a
round-robin arbiter and copies no other document.

## 1. Ports

All signals are synchronous to the rising edge of `clk`, except `grant`, which
is a function of `req` and `last` with no clock edge.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `req` | in | 3 | Request lines, one per requester (bit `i` is requester `i`). |
| `grant` | out | 3 | Grant lines: at most one bit high. |
| `last` | out | 2 | The requester served most recently (0, 1 or 2), a register. |

## 2. Behaviour

The block's whole state is `last`, a register that is also an output.

### 2.1 Reset

- While `rst_n` is low at a rising edge of `clk`, `last` loads 2, so requester 0 has the highest priority after reset. [req:RR-RESET]

### 2.2 Choosing the grant

The priority order is the requesters after `last` in rotation: `last` + 1,
then `last` + 2, then `last` itself, each taken modulo 3.

- `grant` is all zero when `req` is all zero. [req:RR-IDLE]
- Otherwise `grant` has exactly one bit high, and it is the first requester in the priority order whose `req` bit is high. [req:RR-PICK]
- A requester is never granted unless its `req` bit is high. [req:RR-ONLY-REQUESTERS]

### 2.2.1 Examples (`last` = 2, so the order is 0, 1, 2)

| `req` | `grant` |
|---|---|
| 000 | 000 |
| 111 | 001 |
| 110 | 010 |
| 100 | 100 |

### 2.3 Rotation

At each rising edge where `rst_n` is high:

- if `grant` is not zero, `last` becomes the index of the granted requester, so that requester is last in the next priority order; [req:RR-ROTATE]
- if `grant` is zero, `last` does not change. [req:RR-HOLD]
- A requester that was granted at one edge yields at the next edge to any other requester whose `req` bit is high. [req:RR-YIELD]

### 2.4 Bounded wait

- A requester that holds its `req` bit high is granted within three edges: at most two grants go to others first. [req:RR-BOUND]
