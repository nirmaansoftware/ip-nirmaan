// The triage stage's quick repro: settle `clean` high, drive a low pulse of one
// cycle, and look at the count register directly: a change on `noisy` restarts
// it. It prints one verdict line.
`timescale 1ns / 1ps
module debounce_triage_repro;
    localparam integer STABLE = 4;
    reg     clk = 1'b0;
    reg     rst = 1'b1;
    reg     noisy = 1'b0;
    wire    clean;
    integer errors = 0;
    integer checks = 0;
    reg [8*64-1:0] nonce;

    debounce #(.STABLE(STABLE)) dut (.clk(clk), .rst(rst), .noisy(noisy), .clean(clean));
    always #5 clk = ~clk;

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        #1 noisy = 1'b1;
        repeat (STABLE + 3) @(posedge clk);
        #1 noisy = 1'b0;
        @(posedge clk);
        #1 noisy = 1'b1;
        checks = checks + 1;                 // quick probe of the register that counts
        if (dut.cnt !== 4'd0) begin
            $display("ERROR: the count is %0d after a low pulse, expected 0", dut.cnt);
            errors = errors + 1;
        end
        repeat (STABLE + 3) @(posedge clk);
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
