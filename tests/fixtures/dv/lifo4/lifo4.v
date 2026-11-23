// A four-entry stack of 8-bit words (RX-E4): push stores a word on top, pop
// removes the top word, a push and a pop together replace the top word. A push
// onto a full stack or a pop from an empty one is refused and sets a sticky
// error. The approved RTL of the eval case dv/fcov-lifo4: see interface_spec.md.
`timescale 1ns / 1ps
module lifo4 (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       push,
    input  wire       pop,
    input  wire [7:0] din,
    output wire [7:0] dout,
    output reg  [2:0] count = 3'd0,
    output wire       empty,
    output wire       full,
    output reg        err = 1'b0
);
    reg [7:0] mem [0:3];

    wire [1:0] top = count[1:0] - 2'd1;  // the index of the top word when the stack is not empty

    assign empty = (count == 3'd0);
    assign full = (count == 3'd4);
    assign dout = empty ? 8'h00 : mem[top];

    always @(posedge clk) begin
        if (!rst_n) begin
            count <= 3'd0;
            err <= 1'b0;
        end else if (push && pop) begin
            if (empty) begin
                mem[0] <= din;
                count <= 3'd1;
            end else begin
                mem[top] <= din;
            end
        end else if (push) begin
            if (full) begin
                err <= 1'b1;
            end else begin
                mem[count[1:0]] <= din;
                count <= count + 3'd1;
            end
        end else if (pop) begin
            if (empty)
                err <= 1'b1;
            else
                count <= count - 3'd1;
        end
    end
endmodule
