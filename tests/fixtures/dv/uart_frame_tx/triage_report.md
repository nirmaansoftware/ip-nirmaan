# Triage report: nightly regression

Three failing tests, three buckets, one run of `uart_frame_tx_regress_tb` each.

1. `data_byte`: the receiver model read `0xd2` where `0x4b` was sent. The same
   eight bits arrive in reverse order.
2. `parity_bit`: the ones in the data bits plus the parity bit are odd, so the
   parity bit has the wrong polarity.
3. `frame_period`: `busy` stayed high for 42 clocks where eleven bit periods of
   4 clocks (44) are expected.

The failures do not overlap: each test judges one thing and the other two
things look right in its log.
