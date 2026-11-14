// The three regression tests that failed in the nightly run, in one file. A
// plusarg picks the test: +test=data_byte, +test=parity_bit or +test=frame_period.
// Each test sends one frame and judges one thing about it.
`timescale 1ns / 1ps
module uart_frame_tx_regress_tb;
    localparam integer CLKS = 4;
    reg        clk = 1'b0;
    reg        rst = 1'b1;
    reg        start = 1'b0;
    reg  [7:0] data = 8'd0;
    wire       tx;
    wire       busy;
    reg  [7:0] rx_byte;
    reg        rx_parity;
    integer    busy_cycles = 0;
    integer    j;
    reg [8*16-1:0] name;

    uart_frame_tx #(.CLKS_PER_BIT(CLKS)) dut (.clk(clk), .rst(rst), .start(start), .data(data), .tx(tx), .busy(busy));
    always #5 clk = ~clk;
    always @(posedge clk) if (busy) busy_cycles <= busy_cycles + 1;

    task send(input [7:0] value);
        begin
            @(posedge clk); #1 start = 1'b1; data = value;
            @(posedge clk); #1 start = 1'b0;
        end
    endtask

    task receive;
        begin
            @(negedge tx);
            repeat (CLKS / 2) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin
                repeat (CLKS) @(posedge clk);
                rx_byte[j] = tx;
            end
            repeat (CLKS) @(posedge clk);
            rx_parity = tx;
        end
    endtask

    initial begin
        if (!$value$plusargs("test=%s", name)) name = "data_byte";
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        fork
            send(8'h4B);
            receive;
        join
        repeat (4 * CLKS) @(posedge clk);
        if (name == "data_byte") begin
            if (rx_byte !== 8'h4B)
                $display("ERROR: uart_frame_tx_regress_tb.v:54: data_byte: received 0x%02h, expected 0x4b", rx_byte);
        end else if (name == "parity_bit") begin
            if ((^rx_byte) ^ rx_parity)
                $display("ERROR: uart_frame_tx_regress_tb.v:57: parity_bit: ones in data plus parity bit are odd, even parity expected");
        end else begin
            if (busy_cycles !== 11 * CLKS)
                $display("ERROR: uart_frame_tx_regress_tb.v:60: frame_period: busy for %0d clocks, expected %0d", busy_cycles, 11 * CLKS);
        end
        $finish;
    end
endmodule
