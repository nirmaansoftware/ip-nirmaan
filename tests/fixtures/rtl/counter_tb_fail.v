// A testbench that is wrong on purpose: it expects the counter to wrap at 8.
// Used to prove a failing simulation is a recorded, failed run.
`timescale 1ns / 1ps
module counter_tb_fail;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer i;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer errors = 0;
    integer checks = 0;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    initial begin
        @(negedge clk);
        rst = 1'b0;
        en = 1'b1;
        for (i = 1; i <= 12; i = i + 1) begin
            @(negedge clk);
            checks = checks + 1;
            if (count !== i % 9) begin
                $error("cycle %0d: count is %0d, expected %0d", i, count, i % 9);
                errors = errors + 1;
            end
        end
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
