// nirmaan_soc.v: a RISC-V SoC around a design under test, for fw.soc_test.
//
// The CPU runs the cross-compiled driver and its tests from RAM. Its loads
// and stores to the device window become real transfers on the design's own
// bus, through a bridge. Three macros, which the build defines, keep this
// file free of any name it could depend on (docs/RISCV_NEXT.md):
//   `NIRMAAN_CORE    the core's wrapper (core_<name>.v): picorv32 or serv
//   `NIRMAAN_BRIDGE  the bridge for the design's bus (bridge_<bus>.v), which
//                    instantiates the design as `NIRMAAN_DUT
// The bridge passes the design's irq output, if it has one, to the core.
//
// Memory map (docs/RISCV_FIRMWARE.md, section 3):
//   0x0000_0000  RAM, 64 KiB: code, data, stack; the trap vector is at 0x10
//   0x1000_0000  the design, register shift 2: bus byte offset N is the
//                32-bit word at 0x1000_0000 + 4*N; byte lanes are the CPU's
//                byte and halfword stores within that word
//   0x2000_0000  STATUS  (read)  response code of the latest device transfer
//   0x2000_0004  CONSOLE (write) one character to the log
//   0x2000_0008  EXIT    (write) end the run with this exit code
//   0x2000_000C  CYCLES  (read)  clock cycles since reset
// Anything else reads zero and ignores writes.
//
// Every device transfer is logged, in the fw.test format:
//   FWTEST BUS write 0x4 = 0xabababab strobe 0x4 -> OKAY
//   FWTEST BUS read 0x5 -> 0x00000000 SLVERR
`timescale 1ns / 1ps
module nirmaan_soc #(
    parameter integer RAM_BYTES = 65536,
    parameter integer MAX_WAIT = 1000
) (
    input  wire        clk,
    input  wire        resetn,
    output reg         done,
    output reg  [31:0] exit_code,
    output wire        trap
);
    // --- The CPU --------------------------------------------------------------------------
    wire        mem_valid;
    reg         mem_ready;
    wire [31:0] mem_addr, mem_wdata;
    wire [3:0]  mem_wstrb;
    reg  [31:0] mem_rdata;
    wire        dev_irq;

    `NIRMAAN_CORE cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_ready(mem_ready), .mem_addr(mem_addr),
        .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
        .irq(dev_irq)
    );

    // --- RAM, loaded from the firmware image ----------------------------------------------
    reg [7:0] ram [0:RAM_BYTES-1];
    reg [8*4096-1:0] image;  // the image path, up to 4096 characters
    initial begin
        if ($value$plusargs("firmware=%s", image))
            $readmemh(image, ram);
        else begin
            $display("FWTEST ERROR no +firmware=<image.hex> given");
            $finish;
        end
    end

    wire in_ram = mem_addr < RAM_BYTES;
    wire in_dut = mem_addr[31:12] == 20'h10000;
    wire in_ctl = mem_addr[31:4] == 28'h2000000;
    wire [31:0] ram_word = {ram[mem_addr + 3], ram[mem_addr + 2], ram[mem_addr + 1], ram[mem_addr]};

    // --- The design, behind the bridge for its bus ----------------------------------------
    reg         dev_req, dev_write;
    reg  [9:0]  dev_offset;
    reg  [31:0] dev_wdata;
    reg  [3:0]  dev_wstrb;
    wire        dev_done;
    wire [31:0] dev_rdata;
    wire [1:0]  dev_resp;

    `NIRMAAN_BRIDGE bridge (
        .clk(clk), .resetn(resetn),
        .req(dev_req), .write(dev_write), .offset(dev_offset), .wdata(dev_wdata), .wstrb(dev_wstrb),
        .done(dev_done), .rdata(dev_rdata), .resp(dev_resp),
        .irq(dev_irq)
    );

    localparam IDLE = 1'b0, BUSY = 1'b1;
    reg        state;
    reg [1:0]  status;      // STATUS: the latest device response
    reg [31:0] cycles;      // CYCLES
    reg [31:0] waited;

    function [8*6-1:0] resp_name(input [1:0] r);
        case (r)
            2'd0: resp_name = "OKAY";
            2'd1: resp_name = "EXOKAY";
            2'd2: resp_name = "SLVERR";
            default: resp_name = "DECERR";
        endcase
    endfunction

    always @(posedge clk) begin
        if (!resetn) begin
            mem_ready <= 1'b0;
            state <= IDLE;
            status <= 2'd0;
            cycles <= 32'd0;
            waited <= 32'd0;
            done <= 1'b0;
            exit_code <= 32'd0;
            dev_req <= 1'b0;
        end else begin
            cycles <= cycles + 32'd1;
            mem_ready <= 1'b0;
            dev_req <= 1'b0;
            case (state)
                IDLE: if (mem_valid && !mem_ready) begin
                    if (in_ram) begin
                        mem_ready <= 1'b1;
                        mem_rdata <= ram_word;
                        if (mem_wstrb[0]) ram[mem_addr]     <= mem_wdata[7:0];
                        if (mem_wstrb[1]) ram[mem_addr + 1] <= mem_wdata[15:8];
                        if (mem_wstrb[2]) ram[mem_addr + 2] <= mem_wdata[23:16];
                        if (mem_wstrb[3]) ram[mem_addr + 3] <= mem_wdata[31:24];
                    end else if (in_dut) begin
                        waited <= 32'd0;
                        dev_req <= 1'b1;
                        dev_write <= |mem_wstrb;
                        dev_offset <= mem_addr[11:2];
                        dev_wdata <= mem_wdata;
                        dev_wstrb <= mem_wstrb;
                        state <= BUSY;
                    end else begin
                        mem_ready <= 1'b1;
                        mem_rdata <= 32'd0;
                        if (in_ctl && mem_addr[3:2] == 2'd0) mem_rdata <= {30'b0, status};
                        if (in_ctl && mem_addr[3:2] == 2'd3) mem_rdata <= cycles;
                        if (in_ctl && mem_addr[3:2] == 2'd1 && mem_wstrb[0]) $write("%c", mem_wdata[7:0]);
                        if (in_ctl && mem_addr[3:2] == 2'd2 && |mem_wstrb) begin
                            done <= 1'b1;
                            exit_code <= mem_wdata;
                        end
                    end
                end
                BUSY: begin
                    waited <= waited + 32'd1;
                    if (dev_done) begin
                        status <= dev_resp;
                        mem_rdata <= dev_rdata;
                        mem_ready <= 1'b1;
                        state <= IDLE;
                        if (dev_write)
                            $display("FWTEST BUS write 0x%0x = 0x%08x strobe 0x%0x -> %0s", dev_offset, dev_wdata,
                                     dev_wstrb, resp_name(dev_resp));
                        else
                            $display("FWTEST BUS read 0x%0x -> 0x%08x %0s", dev_offset, dev_rdata,
                                     resp_name(dev_resp));
                    end else if (waited == MAX_WAIT) begin
                        $display("FWTEST ERROR bus timeout: no %0s handshake for offset 0x%0x within %0d cycles",
                                 dev_write ? "write" : "read", dev_offset, MAX_WAIT);
                        done <= 1'b1;
                        exit_code <= 32'd3;
                    end
                end
            endcase
        end
    end
endmodule
