# Interface specification: `uart_tx`

An 8N1 serial transmitter, written for this repository in our own words. It is
the block under investigation in the eval case `debug/root-cause-uart-tx`; the
case gives it to no seat (the seat sees the RTL, the failing log and the
triage report).

| Port | Dir | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock. |
| `rst` | in | 1 | Reset, active high, synchronous. `tx` idles high. |
| `start` | in | 1 | Send `data` as one frame. |
| `data` | in | 8 | The byte to send. |
| `tx` | out | 1 | The serial line. |
| `busy` | out | 1 | High from the edge after a start is accepted until the stop bit ends. |

- `UART-FRAME`: a frame is one low start bit, eight data bits least significant
  bit first, and one high stop bit. Each bit lasts `CLKS_PER_BIT` clock cycles.
- `UART-IDLE`: `tx` is high when no frame is in flight.
- `UART-BUSY-IGNORES-START`: a `start` pulse while `busy` is high is ignored.
  It must not change the byte in flight, and it does not queue a second frame.
