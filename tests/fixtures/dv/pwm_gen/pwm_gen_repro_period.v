// Reproduction 2: The period of the output is PERIOD clocks. Measures the distance between rising edges, twice, with a duty of 3. It prints one verdict line.
`timescale 1ns / 1ps
module pwm_gen_repro_period;
    localparam integer PERIOD = 8;
    reg        clk = 1'b0;
    reg        rst = 1'b1;
    reg  [3:0] duty = 4'd3;
    wire       pwm;
    integer    errors = 0;
    integer    checks = 0;
    integer    width;
    integer    cycle = 0;
    integer    t0;
    reg [8*64-1:0] nonce;

    pwm_gen #(.PERIOD(PERIOD)) dut (.clk(clk), .rst(rst), .duty(duty), .pwm(pwm));
    always #5 clk = ~clk;
    always @(posedge clk) cycle <= cycle + 1;

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
        @(posedge pwm);
        t0 = cycle;
        @(negedge pwm);
        @(posedge pwm);
        verdict_check(cycle - t0 === PERIOD, "rising edges of pwm are not PERIOD clocks apart");
        t0 = cycle;
        @(negedge pwm);
        @(posedge pwm);
        verdict_check(cycle - t0 === PERIOD, "the second period is not PERIOD clocks");
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
