// Self-checking testbench for ram_block.v: writes two words, reads them back,
// and counts the writes.
`timescale 1ns / 1ps
module ram_block_tb;
    reg clk = 1'b0;
    reg wr_en = 1'b0;
    reg [3:0] index = 4'd0;
    reg [7:0] din = 8'd0;
    wire [7:0] dout;
    wire [7:0] writes;
    integer errors = 0;

    ram_block dut (.clk(clk), .wr_en(wr_en), .index(index), .din(din), .dout(dout), .writes(writes));

    always #5 clk = ~clk;

    task write(input [3:0] i, input [7:0] d);
        begin
            @(negedge clk);
            wr_en = 1'b1;
            index = i;
            din = d;
            @(negedge clk);
            wr_en = 1'b0;
        end
    endtask

    task check(input [3:0] i, input [7:0] d);
        begin
            @(negedge clk);
            index = i;
            @(negedge clk);
            if (dout !== d) begin
                $display("ERROR: word %0d reads %h, expected %h", i, dout, d);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        write(4'd1, 8'hA5);
        write(4'd2, 8'h3C);
        check(4'd1, 8'hA5);
        check(4'd2, 8'h3C);
        if (writes !== 8'd2) begin
            $display("ERROR: %0d writes counted, expected 2", writes);
            errors = errors + 1;
        end
        if (errors == 0)
            $display("ram_block_tb: PASS");
        $finish;
    end
endmodule
