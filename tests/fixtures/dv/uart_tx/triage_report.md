# Triage report: nightly regression

One failing test, `uart_tx_regress_tb`, one failure bucket. The receiver model
decoded a frame that carried the second byte (`0xb2`) where the first (`0x3c`)
was sent, and the data bits are the only thing wrong: the start and stop bits
are well formed and only one frame appears on the wire. The second start pulse
came while `busy` was high.
