// Reproduction 2: the parity bit makes the count of ones even. Sends 0x00 and 0x01 and reads the parity bit after the eight data bits.
`timescale 1ns / 1ps
module uart_frame_tx_repro_parity;
    localparam integer CLKS = 4;
    reg        clk = 1'b0;
    reg        rst = 1'b1;
    reg        start = 1'b0;
    reg  [7:0] data = 8'd0;
    wire       tx;
    wire       busy;
    reg  [7:0] got;
    integer    errors = 0;
    integer    checks = 0;
    integer    k;
    integer    busy_cycles;
    reg [8*64-1:0] nonce;

    uart_frame_tx #(.CLKS_PER_BIT(CLKS)) dut (.clk(clk), .rst(rst), .start(start), .data(data), .tx(tx), .busy(busy));
    always #5 clk = ~clk;

    // Accept one frame carrying value; returns on the edge that accepted it.
    task send(input [7:0] value);
        begin
            @(posedge clk); #1 start = 1'b1; data = value;
            @(posedge clk); #1 start = 1'b0; data = 8'h00;
        end
    endtask

    task verdict_check(input ok, input [8*80-1:0] what);
        begin
            checks = checks + 1;
            if (!ok) begin
                $display("ERROR: %0s", what);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        send(8'h00);
        repeat (CLKS * 9 + CLKS / 2) @(posedge clk);  // middle of the parity bit
        #1 verdict_check(tx === 1'b0, "parity bit for 0x00 is not 0");
        repeat (3 * CLKS) @(posedge clk);
        send(8'h01);
        repeat (CLKS * 9 + CLKS / 2) @(posedge clk);
        #1 verdict_check(tx === 1'b1, "parity bit for 0x01 is not 1");
        repeat (3 * CLKS) @(posedge clk);
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
