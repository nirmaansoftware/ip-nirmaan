// Self-checking SystemVerilog testbench with a scoreboard for mac8.v (W2-E6),
// the reference answer of the eval case dv/scoreboard-mac.
//
// A reference model of the specification (an unsigned product added to a
// 24-bit total that saturates, with a sticky flag, reset and clear loading
// zeros) takes the same inputs as the block at every rising edge. The
// scoreboard compares the block's `acc` and `sat` with the model's after every
// edge and keeps the counts. Directed phases first reach what random stimulus
// rarely does: a clear that meets an accumulate, a total driven to the top
// with the largest operands, the flag held through idle and zero-product
// edges, and a clear of a saturated total. A constrained-random run follows
// from a fixed-seed generator, operands from the corners (0, 1, 127, 128, 255)
// one time in three. The testbench fails itself when the run is too short or
// never saturated, cleared a saturated total, or met clr with en.
//
// Every input changes 1 ns after a rising edge and every check samples 1 ns
// after one, so a check sees the registers the last edge wrote.
`timescale 1ns / 1ps
module mac8_tb;
    logic        clk = 1'b0;
    logic        rst_n = 1'b0;
    logic        clr = 1'b0;
    logic        en = 1'b0;
    logic [7:0]  a = 8'd0;
    logic [7:0]  b = 8'd0;
    wire  [23:0] acc;
    wire         sat;

    int checks = 0;
    int errors = 0;
    int sat_edges = 0;      // edges whose model flag is high
    int clr_sat = 0;        // a clear while the flag was high
    int clr_en = 0;         // clr together with en
    int acc_edges = 0;      // an accumulate taken
    logic [23:0] m_acc = 24'd0;   // reference model
    logic        m_sat = 1'b0;
    logic [31:0] rng = 32'hC0FF_EE11;
    logic [8*64-1:0] nonce;

    mac8 dut (.clk(clk), .rst_n(rst_n), .clr(clr), .en(en), .a(a), .b(b), .acc(acc), .sat(sat));

    always #5 clk = ~clk;

    // xorshift32: a fixed sequence on any simulator.
    function automatic logic [31:0] next_rand();
        rng = rng ^ (rng << 13);
        rng = rng ^ (rng >> 17);
        rng = rng ^ (rng << 5);
        return rng;
    endfunction

    // Reference model: one rising edge with these inputs.
    task automatic model_edge(input logic r, input logic c, input logic e, input logic [7:0] x, input logic [7:0] y);
        logic [24:0] sum;
        logic [15:0] prod;
        if (!r || c) begin
            m_acc = 24'd0;
            m_sat = 1'b0;
        end else if (e) begin
            prod = x * y;
            sum = {1'b0, m_acc} + {9'd0, prod};
            if (sum > 25'h0FFFFFF) begin
                m_acc = 24'hFFFFFF;
                m_sat = 1'b1;
            end else begin
                m_acc = sum[23:0];
            end
        end
    endtask

    // Scoreboard: the block's outputs against the model's.
    task automatic score(input string what);
        checks++;
        if (acc !== m_acc || sat !== m_sat) begin
            if (errors < 5)
                $error("%s: acc 0x%06h sat %0b, expected acc 0x%06h sat %0b", what, acc, sat, m_acc, m_sat);
            errors++;
        end
    endtask

    // One cycle with the given inputs, then the scoreboard.
    task automatic cycle(input logic r, input logic c, input logic e, input logic [7:0] x, input logic [7:0] y,
                         input string what);
        rst_n = r; clr = c; en = e; a = x; b = y;
        if (r && c && m_sat) clr_sat++;
        if (r && c && e) clr_en++;
        if (r && !c && e) acc_edges++;
        @(posedge clk);
        model_edge(r, c, e, x, y);
        if (m_sat) sat_edges++;
        #1;
        score(what);
    endtask

    logic [31:0] w;
    logic [7:0]  x, y;
    logic        r, c, e;

    initial begin
        #1;
        // Directed: reset, small products, hold, a clear that meets an accumulate.
        cycle(1'b0, 1'b0, 1'b0, 8'h00, 8'h00, "reset");
        cycle(1'b1, 1'b0, 1'b1, 8'd3, 8'd5, "3 x 5");
        cycle(1'b1, 1'b0, 1'b1, 8'd200, 8'd100, "200 x 100");
        cycle(1'b1, 1'b0, 1'b0, 8'd9, 8'd9, "hold");
        cycle(1'b1, 1'b1, 1'b1, 8'd7, 8'd7, "clear with accumulate");
        cycle(1'b1, 1'b1, 1'b0, 8'd0, 8'd0, "clear");
        // Directed: the largest operands until the total saturates, then through idle and zero-product edges.
        repeat (270) cycle(1'b1, 1'b0, 1'b1, 8'hFF, 8'hFF, "to the top");
        cycle(1'b1, 1'b0, 1'b0, 8'h00, 8'h00, "saturated, idle");
        cycle(1'b1, 1'b0, 1'b1, 8'h00, 8'h55, "saturated, zero product");
        cycle(1'b1, 1'b0, 1'b1, 8'h01, 8'h01, "saturated, small product");
        cycle(1'b1, 1'b1, 1'b0, 8'h00, 8'h00, "clear a saturated total");
        cycle(1'b1, 1'b0, 1'b1, 8'd128, 8'd128, "128 x 128");
        cycle(1'b1, 1'b0, 1'b1, 8'd255, 8'd1, "255 x 1");
        // Directed: the total saturates again and stays there, then a reset clears it.
        repeat (300) cycle(1'b1, 1'b0, 1'b1, 8'hFF, 8'hFF, "past the top");
        cycle(1'b0, 1'b0, 1'b1, 8'hFF, 8'hFF, "reset a saturated total");
        // Constrained-random run.
        repeat (5000) begin
            w = next_rand();
            r = (w[7:0] != 8'd0);              // reset about 1 in 256
            c = (w[11:8] == 4'd0);             // clear 1 in 16
            e = (w[13:12] != 2'd0);            // en 3 in 4
            case (w[17:16])
                2'd0: x = 8'hFF;
                2'd1: x = 8'h80;
                default: x = w[31:24];
            endcase
            case (w[19:18])
                2'd0: y = 8'hFF;
                2'd1: y = 8'h01;
                default: y = w[27:20];
            endcase
            cycle(r, c, e, x, y, "random");
        end
        // The run must have reached what the checks are for.
        if (checks < 5500 || sat_edges < 40 || clr_sat < 1 || clr_en < 20 || acc_edges < 2000) begin
            $error("run too thin: checks=%0d sat=%0d clr_sat=%0d clr_en=%0d acc=%0d",
                   checks, sat_edges, clr_sat, clr_en, acc_edges);
            errors++;
        end
        if (errors == 0)
            $display("mac8_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
