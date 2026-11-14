// A second implementation of the same transmitter, written with a shift
// register instead of a held byte and a bit index. Same ports, same behaviour.
`timescale 1ns / 1ps
module uart_tx #(
    parameter integer CLKS_PER_BIT = 4
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] data,
    output reg        tx,
    output wire       busy
);
    localparam [1:0] IDLE = 2'd0, START = 2'd1, DATA = 2'd2, STOP = 2'd3;

    reg [1:0]  state;
    reg [7:0]  sh;
    reg [3:0]  sent;
    reg [15:0] clk_cnt;
    wire       bit_done = (clk_cnt == CLKS_PER_BIT - 1);

    assign busy = (state != IDLE);

    always @(posedge clk) begin
        if (rst) begin
            state   <= IDLE;
            tx      <= 1'b1;
            sh      <= 8'd0;
            sent    <= 4'd0;
            clk_cnt <= 16'd0;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (start) begin
                        sh      <= data;
                        clk_cnt <= 16'd0;
                        state   <= START;
                        tx      <= 1'b0;
                    end
                end
                START: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        state   <= DATA;
                        tx      <= sh[0];
                        sh      <= {1'b0, sh[7:1]};
                        sent    <= 4'd1;
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                DATA: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        if (sent == 4'd8) begin
                            state <= STOP;
                            tx    <= 1'b1;
                        end else begin
                            tx   <= sh[0];
                            sh   <= {1'b0, sh[7:1]};
                            sent <= sent + 4'd1;
                        end
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                STOP: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        state   <= IDLE;
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
            endcase
        end
    end
endmodule
