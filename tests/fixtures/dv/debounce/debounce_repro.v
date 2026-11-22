// Reproduction of the debounce failure: a low pulse of two cycles, while `clean`
// is high, must not reach `clean` (STABLE is 4). The testbench settles `clean`
// high, drives the short low pulse, and samples `clean` on every edge until the
// pulse is long over. It also checks that a settled release still reaches
// `clean`, and not before STABLE edges. It prints one verdict line.
`timescale 1ns / 1ps
module debounce_repro;
    localparam integer STABLE = 4;
    reg     clk = 1'b0;
    reg     rst = 1'b1;
    reg     noisy = 1'b0;
    wire    clean;
    integer errors = 0;
    integer checks = 0;
    integer k;
    reg [8*64-1:0] nonce;

    debounce #(.STABLE(STABLE)) dut (.clk(clk), .rst(rst), .noisy(noisy), .clean(clean));
    always #5 clk = ~clk;

    // Drive value for one clock, then sample `clean` just after the edge.
    task step(input value, input want, input [8*64-1:0] what);
        begin
            #1 noisy = value;
            @(posedge clk);
            #1 checks = checks + 1;
            if (clean !== want) begin
                $display("ERROR: %0s: clean is %b, expected %b", what, clean, want);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        step(1'b0, 1'b0, "idle low after reset");
        // Settle high: the first sample of the new value, then STABLE edges.
        for (k = 0; k < STABLE + 3; k = k + 1) step(1'b1, (k >= STABLE) ? 1'b1 : 1'b0, "settling high");
        // A low pulse of two cycles, then high again: clean must not move.
        step(1'b0, 1'b1, "first cycle of a low pulse");
        step(1'b0, 1'b1, "second cycle of a low pulse");
        for (k = 0; k < STABLE + 3; k = k + 1) step(1'b1, 1'b1, "after a low pulse of two cycles");
        // A settled release must still reach clean, but not before STABLE edges.
        for (k = 0; k < STABLE + 3; k = k + 1) step(1'b0, (k >= STABLE) ? 1'b0 : 1'b1, "settled release");
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
