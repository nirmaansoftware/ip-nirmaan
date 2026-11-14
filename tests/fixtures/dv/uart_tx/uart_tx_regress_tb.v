// The regression test that failed: a driver queues two bytes without looking
// at busy (the second start pulse comes five cycles after the first), and a
// receiver model decodes every frame on the wire. Only the first frame should
// appear; the second byte is dropped because the block is busy.
`timescale 1ns / 1ps
module uart_tx_regress_tb;
    localparam integer CLKS = 4;
    reg        clk = 1'b0;
    reg        rst = 1'b1;
    reg        start = 1'b0;
    reg  [7:0] data = 8'd0;
    wire       tx;
    wire       busy;
    reg  [7:0] rx_byte;
    integer    frames = 0;
    integer    j;

    uart_tx #(.CLKS_PER_BIT(CLKS)) dut (.clk(clk), .rst(rst), .start(start), .data(data), .tx(tx), .busy(busy));
    always #5 clk = ~clk;

    // Receiver model: wait for the falling edge, then sample every bit mid-way.
    always begin
        @(negedge tx);
        repeat (CLKS / 2) @(posedge clk);
        for (j = 0; j < 8; j = j + 1) begin
            repeat (CLKS) @(posedge clk);
            rx_byte[j] = tx;
        end
        repeat (CLKS) @(posedge clk);
        frames = frames + 1;
        $display("INFO: frame %0d received 0x%02h", frames, rx_byte);
        if (rx_byte !== 8'h3C)
            $display("ERROR: uart_tx_regress_tb.v:33: frame %0d: received 0x%02h, expected 0x3c", frames, rx_byte);
    end

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        @(posedge clk);
        #1 start = 1'b1; data = 8'h3C;
        @(posedge clk);
        #1 start = 1'b0;
        repeat (4) @(posedge clk);
        #1 start = 1'b1; data = 8'hB2;
        @(posedge clk);
        #1 start = 1'b0;
        repeat (20 * CLKS) @(posedge clk);
        if (frames != 1)
            $display("ERROR: uart_tx_regress_tb.v:49: %0d frames seen, expected 1", frames);
        $finish;
    end
endmodule
