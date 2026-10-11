// Self-checking testbench for the pipelined prod3.v: y follows a, b, c three clock
// edges later (the input registers, then two stages), over pseudo-random inputs.
// The unpipelined before/prod3.v has one stage fewer, and fails it.
`timescale 1ns / 1ps
module prod3_tb;
    reg clk = 1'b0;
    reg [15:0] a = 16'd0, b = 16'd0, c = 16'd0;
    wire [31:0] y;
    reg [31:0] expected [0:2];
    integer errors = 0;
    integer checks = 0;
    integer i;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line

    prod3 dut (.clk(clk), .a(a), .b(b), .c(c), .y(y));

    always #5 clk = ~clk;

    initial begin
        expected[0] = 32'd0;
        expected[1] = 32'd0;
        expected[2] = 32'd0;
        for (i = 0; i < 40; i = i + 1) begin
            @(negedge clk);
            if (i >= 3)
                checks = checks + 1;
            if (i >= 3 && y !== expected[i % 3]) begin
                $display("ERROR: step %0d: y is %0d, expected %0d", i, y, expected[i % 3]);
                errors = errors + 1;
            end
            a = $random;
            b = $random;
            c = $random;
            expected[i % 3] = a * b * c;
        end
        if (errors == 0)
            $display("prod3_tb: PASS");
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
