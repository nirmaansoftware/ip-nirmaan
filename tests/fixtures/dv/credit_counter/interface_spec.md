# Interface specification: `credit_counter`

A credit counter for credit-based flow control. A sender may send one item
for each credit it holds; it spends a credit when it sends (`take`) and gets
one back when the receiver frees a slot (`give`). The counter starts full,
never goes below zero or above `MAX`, and flags a take with no credit or a
give with no room as an error that stays set until reset.

This is the approved specification of the block the verification eval case
`dv/formal-credit-counter` verifies. It was written for this repository in
our own words; a counter of credits with take and give is the usual shape of
credit-based flow control and copies no other document.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `MAX` | 4 | Number of credits, 1 to 255: the receiver's number of slots. |

- The block works for every `MAX` from 1 to 255, a power of two or not. [req:CC-PARAM]

## 2. Ports

All signals are synchronous to the rising edge of `clk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst_n` | in | 1 | Reset, active low, synchronous. |
| `take` | in | 1 | The sender spends one credit at this rising edge. |
| `give` | in | 1 | One credit comes back at this rising edge. |
| `credits` | out | 8 | Credits held now, 0 to `MAX`. |
| `avail` | out | 1 | High when `credits` is not zero. |
| `full` | out | 1 | High when `credits` equals `MAX`. |
| `err` | out | 1 | High once a take or a give has been refused, until reset. |

## 3. Behaviour

### 3.1 Reset

- While `rst_n` is low at a rising edge of `clk`, `credits` loads `MAX` and `err` clears to zero. [req:CC-RESET]

### 3.2 Counting

At each rising edge where `rst_n` is high:

- `take` high and `give` low with `credits` above zero: `credits` goes down by one. [req:CC-TAKE]
- `give` high and `take` low with `credits` below `MAX`: `credits` goes up by one. [req:CC-GIVE]
- `take` and `give` both high: `credits` does not change, at zero and at `MAX` too, and nothing is refused (the credit that comes back is spent at once). [req:CC-BOTH]
- `take` and `give` both low: `credits` does not change. [req:CC-IDLE]
- `credits` is never above `MAX` and never wraps below zero. [req:CC-RANGE]

### 3.3 Refusals and the error flag

- `take` high and `give` low with `credits` at zero: the take is refused, `credits` stays zero, and `err` is set. [req:CC-UNDERFLOW]
- `give` high and `take` low with `credits` at `MAX`: the give is refused, `credits` stays `MAX`, and `err` is set. [req:CC-OVERFLOW]
- Once set, `err` stays high at every later rising edge until a reset clears it. [req:CC-ERR-STICKY]

### 3.4 Status outputs

- `avail` is high exactly when `credits` is not zero, and `full` is high exactly when `credits` equals `MAX`. Both follow `credits` with no clock edge. [req:CC-STATUS]
