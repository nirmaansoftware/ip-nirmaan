# Root cause: uart_tx latches `data` on every start pulse

Outcome: RTL bug.

`uart_tx` copies `data` into its `hold` register whenever `start` is high,
including while a frame is in flight. The specification (`UART-BUSY-IGNORES-START`)
says a start pulse while `busy` is high is ignored. The data states read the
bits still to be sent from `hold`, so a second pulse with a different byte
replaces every bit not yet sent: the first frame carries the second byte
(`0xb2` for `0x3c`).

Fix: load `hold` only in the idle state, the one place a start is accepted.

Reproduction: `uart_tx_repro.v` sends `0x3c`, pulses `start` with `0xb2` during
bit 1, and reads the frame back at the middle of each bit. On the RTL under
investigation it fails its data check; on the fixed RTL it passes.
