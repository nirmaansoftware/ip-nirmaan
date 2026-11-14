// An 8N1 UART transmitter: one start bit, eight data bits least significant
// first, one stop bit. Each bit lasts CLKS_PER_BIT clock cycles. A start pulse
// while a frame is in flight is ignored.
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
    reg [7:0]  hold;
    reg [2:0]  bit_idx;
    reg [15:0] clk_cnt;
    wire       bit_done = (clk_cnt == CLKS_PER_BIT - 1);

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
                            state <= STOP;
                            tx    <= 1'b1;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                            tx      <= hold[bit_idx + 3'd1];
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
