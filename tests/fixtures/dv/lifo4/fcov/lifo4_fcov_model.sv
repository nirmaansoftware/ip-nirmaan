// Functional coverage model for lifo4 (RX-E4), the reference answer of the eval case
// dv/fcov-lifo4. It plans one bin per scenario the approved requirement matrix names.
//
// Closure statement. Planned bins, fifteen:
//   9 crosses of operation x occupancy:
//     push alone x {empty, neither, full}   (x_push_*)
//     pop alone  x {empty, neither, full}   (x_pop_*)
//     both       x {empty, neither, full}   (x_both_*)
//   5 occupancies, 0 to 4 words             (lv)
//   1 reset applied while the stack holds a word (rst_busy)
// Exclusions: none. Every bin is reachable, and none is written out of the model.
// Occupancy values 5 to 7 cannot occur (the stack refuses a push at 4), so they have no bin.
`timescale 1ns / 1ps
module lifo4_fcov (
    input  logic       clk, rst_n, push, pop,
    input  logic [7:0] din, dout,
    input  logic [2:0] count,
    input  logic       empty, full, err,
    output int         planned,
    output int         holes
);
    logic [8:0] x = 9'd0;
    logic [4:0] lv = 5'd0;
    logic       rst_busy = 1'b0;

    wire neither = !empty && !full;

    always @(posedge clk) begin
        if (!rst_n) begin
            if (!empty) rst_busy <= 1'b1;
        end else begin
            if (push && !pop) begin
                if (empty) x[0] <= 1'b1;
                if (neither) x[1] <= 1'b1;
                if (full) x[2] <= 1'b1;
            end
            if (pop && !push) begin
                if (empty) x[3] <= 1'b1;
                if (neither) x[4] <= 1'b1;
                if (full) x[5] <= 1'b1;
            end
            if (push && pop) begin
                if (empty) x[6] <= 1'b1;
                if (neither) x[7] <= 1'b1;
                if (full) x[8] <= 1'b1;
            end
            if (count <= 3'd4) lv[count] <= 1'b1;
        end
    end

    function automatic int ones(input logic [14:0] v);
        int n = 0;
        for (int i = 0; i < 15; i++) n += int'(v[i]);
        return n;
    endfunction

    assign planned = 15;
    assign holes = 15 - ones({rst_busy, lv, x});
endmodule
