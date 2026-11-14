// The triage stage's quick repro: send 0x3C, pulse start with 0xB2 during bit 1,
// and look at the hold register directly. It prints one verdict line.
`timescale 1ns / 1ps
module uart_tx_triage_repro;
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
    reg [8*64-1:0] nonce;

    uart_tx #(.CLKS_PER_BIT(CLKS)) dut (.clk(clk), .rst(rst), .start(start), .data(data), .tx(tx), .busy(busy));

    always #5 clk = ~clk;

    task expect_bit(input integer index, input want);
        begin
            checks = checks + 1;
            if (tx !== want) begin
                $display("ERROR: bit %0d of the frame is %b, expected %b", index, tx, want);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        @(posedge clk);
        #1 start = 1'b1; data = 8'h3C;
        @(posedge clk);                      // the edge that accepts the frame
        #1 start = 1'b0; data = 8'h00;
        repeat (2) @(posedge clk);
        #1 expect_bit(0, 1'b0);              // start bit, sampled mid-bit
        repeat (3) @(posedge clk);
        #1 start = 1'b1; data = 8'hB2;       // a second start, mid way through bit 1
        @(posedge clk);
        #1 start = 1'b0; data = 8'h00;
        checks = checks + 1;                 // quick probe of the register the data bits come from
        if (dut.hold !== 8'h3C) begin
            $display("ERROR: hold is 0x%02h after a start while busy, expected 0x3C", dut.hold);
            errors = errors + 1;
        end
        repeat (8 * CLKS) @(posedge clk);
        repeat (CLKS) @(posedge clk);
        #1 expect_bit(9, 1'b1);              // stop bit
        repeat (2 * CLKS) @(posedge clk);
        #1 checks = checks + 1;
        if (busy !== 1'b0 || tx !== 1'b1) begin
            $display("ERROR: the block should be idle after one frame (busy=%b tx=%b)", busy, tx);
            errors = errors + 1;
        end
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
