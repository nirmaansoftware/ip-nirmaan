// Self-checking testbench for counter.v: counts to LIMIT, wraps, and finishes.
`timescale 1ns / 1ps
module counter_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer errors = 0;
    integer checks = 0;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer i;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    initial begin
        @(negedge clk);
        rst = 1'b0;
        en = 1'b1;
        for (i = 1; i <= 12; i = i + 1) begin
            @(negedge clk);
            checks = checks + 1;
            if (count !== i % 10) begin
                $display("ERROR: cycle %0d: count is %0d, expected %0d", i, count, i % 10);
                errors = errors + 1;
            end
        end
        if (errors == 0)
            $display("counter_tb: PASS");
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
