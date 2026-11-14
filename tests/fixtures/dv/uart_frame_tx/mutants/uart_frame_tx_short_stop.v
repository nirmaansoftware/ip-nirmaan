// A UART transmitter with even parity: one start bit, eight data bits least
// significant first, one even-parity bit, one stop bit. Each bit lasts
// CLKS_PER_BIT clock cycles. A start pulse while busy is ignored.
`timescale 1ns / 1ps
module uart_frame_tx #(
    parameter integer CLKS_PER_BIT = 4
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] data,
    output reg        tx,
    output wire       busy
);
    localparam [2:0] IDLE = 3'd0, START = 3'd1, DATA = 3'd2, PARITY = 3'd3, STOP = 3'd4;

    reg [2:0]  state;
    reg [7:0]  hold;
    reg [2:0]  bit_idx;
    reg [15:0] clk_cnt;
    wire       bit_done = (clk_cnt == CLKS_PER_BIT - 1);
    wire       parity   = ^hold;                      // even parity: the bit that makes the count of ones even
    wire [2:0] next_idx = bit_idx + 3'd1;

    assign busy = (state != IDLE);

    always @(posedge clk) begin
        if (rst) begin
            state   <= IDLE;
            tx      <= 1'b1;
            hold    <= 8'd0;
            bit_idx <= 3'd0;
            clk_cnt <= 16'd0;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (start) begin
                        hold    <= data;
                        clk_cnt <= 16'd0;
                        state   <= START;
                        tx      <= 1'b0;
                    end
                end
                START: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        bit_idx <= 3'd0;
                        state   <= DATA;
                        tx      <= hold[0];
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                DATA: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        if (bit_idx == 3'd7) begin
                            state <= PARITY;
                            tx    <= parity;
                        end else begin
                            bit_idx <= next_idx;
                            tx      <= hold[next_idx];
                        end
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                PARITY: begin
                    if (bit_done) begin
                        clk_cnt <= 16'd0;
                        state   <= STOP;
                        tx      <= 1'b1;
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                STOP: begin
                    if (clk_cnt == (CLKS_PER_BIT / 2) - 1) begin
                        clk_cnt <= 16'd0;
                        state   <= IDLE;
                    end else
                        clk_cnt <= clk_cnt + 16'd1;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
