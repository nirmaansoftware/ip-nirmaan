// Constrained-random, self-checking SystemVerilog testbench for crc8_block.v
// (W2-E3), the reference answer of the eval case dv/random-crc.
//
// The stimulus is random under constraints, from a fixed-seed generator so a
// run repeats exactly: init about one cycle in twelve, valid about three in
// four, a reset about one cycle in 250, and data that is a corner value (0x00,
// 0xFF, 0x80, 0x01, 0x07) one time in four and uniform otherwise. Every cycle
// a reference model of the specification (the byte XORed into the running
// value, then eight shift-and-reduce steps) takes the same inputs and `crc` is
// compared after each rising edge, so a wrong polynomial, a byte taken in the
// wrong bit order, a missing final inversion, a reload that loses to a byte or
// a valid that is ignored all show up within a few cycles. Directed checks
// first cover the value right after reset and after a reload, and the
// testbench fails itself when the random run is too short or never reaches the
// cases that matter (init together with valid, valid low, a reset mid-frame).
//
// Every input changes 1 ns after a rising edge and every check samples 1 ns
// after one, so a check sees the register the last edge wrote.
`timescale 1ns / 1ps
module crc8_block_tb;
    logic       clk = 1'b0;
    logic       rst_n = 1'b0;
    logic       init = 1'b0;
    logic       valid = 1'b0;
    logic [7:0] data = 8'd0;
    wire  [7:0] crc;

    int checks = 0;
    int errors = 0;
    int both_cycles = 0;   // init with valid
    int idle_cycles = 0;   // valid low, init low
    int reset_cycles = 0;  // reset after the first
    int byte_cycles = 0;   // a byte taken
    logic [7:0] model = 8'hFF;
    logic [31:0] rng = 32'h1BAD_C0DE;
    logic [8*64-1:0] nonce;

    crc8_block dut (.clk(clk), .rst_n(rst_n), .init(init), .valid(valid), .data(data), .crc(crc));

    always #5 clk = ~clk;

    // xorshift32: a fixed sequence on any simulator.
    function automatic logic [31:0] next_rand();
        rng = rng ^ (rng << 13);
        rng = rng ^ (rng >> 17);
        rng = rng ^ (rng << 5);
        return rng;
    endfunction

    function automatic logic [7:0] model_byte(input logic [7:0] s, input logic [7:0] d);
        logic [7:0] r;
        r = s ^ d;
        for (int i = 0; i < 8; i++)
            r = r[7] ? ((r << 1) ^ 8'h07) : (r << 1);
        return r;
    endfunction

    task automatic check(input string what);
        checks++;
        if (crc !== (model ^ 8'hFF)) begin
            if (errors < 5)
                $error("%s: crc 0x%02h, expected 0x%02h", what, crc, model ^ 8'hFF);
            errors++;
        end
    endtask

    // One cycle with the given inputs: the model takes them at the edge, then the output is compared.
    task automatic cycle(input logic r, input logic i, input logic v, input logic [7:0] d, input string what);
        rst_n = r; init = i; valid = v; data = d;
        @(posedge clk);
        if (!r || i)
            model = 8'hFF;
        else if (v)
            model = model_byte(model, d);
        #1;
        check(what);
    endtask

    logic [31:0] w;
    logic [7:0]  d;
    logic        i, v, r;

    initial begin
        #1;
        // Directed starts: reset, then a reload, with nothing taken.
        cycle(1'b0, 1'b0, 1'b0, 8'h00, "reset");
        if (crc !== 8'h00) begin
            $error("after reset with no byte: crc 0x%02h, expected 0x00", crc);
            errors++;
        end
        cycle(1'b1, 1'b0, 1'b1, 8'hA5, "first byte");
        cycle(1'b1, 1'b1, 1'b0, 8'h00, "reload");
        if (crc !== 8'h00) begin
            $error("after a reload with no byte: crc 0x%02h, expected 0x00", crc);
            errors++;
        end
        // Constrained-random run.
        repeat (6000) begin
            w = next_rand();
            r = (w[7:0] != 8'd0);              // reset about 1 in 256
            i = (w[11:8] == 4'd0);             // init 1 in 16
            v = (w[13:12] != 2'd0);            // valid 3 in 4
            case (w[18:16])
                3'd0: d = 8'h00;
                3'd1: d = 8'hFF;
                3'd2: d = 8'h80;
                3'd3: d = 8'h01;
                default: d = w[31:24];
            endcase
            if (i && v) both_cycles++;
            if (!i && !v) idle_cycles++;
            if (!r) reset_cycles++;
            if (r && !i && v) byte_cycles++;
            cycle(r, i, v, d, "random");
        end
        // The run must have reached what the checks are for.
        if (checks < 6000 || both_cycles < 20 || idle_cycles < 100 || reset_cycles < 5 || byte_cycles < 2000) begin
            $error("random run too thin: checks=%0d both=%0d idle=%0d reset=%0d bytes=%0d",
                   checks, both_cycles, idle_cycles, reset_cycles, byte_cycles);
            errors++;
        end
        if (errors == 0)
            $display("crc8_block_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
