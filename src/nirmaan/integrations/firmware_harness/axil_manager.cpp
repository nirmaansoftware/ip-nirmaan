// axil_manager.cpp: an AXI4-Lite manager around a Verilator model, for fw.test.
//
// The model is built with `--prefix Vdut`, so this file names no design. It
// needs only the AXI4-Lite subordinate port convention: aclk, aresetn, and the
// s_axil_* channels (AW, W, B, AR, R), with 32-bit data. It implements the
// nirmaan_hal bus with real handshakes on the model, runs the driver's tests,
// and prints one line per bus transfer and per check:
//
//   FWTEST BUS write 0x4 = 0x12345678 strobe 0xf -> OKAY
//   FWTEST PASS <name>
//   FWTEST FAIL <name>: <detail>
//   FWTEST ERROR <why the run could not continue>
//   FWTEST SUMMARY <passed> passed, <failed> failed, <cycles> cycles
//
// The exit status is 0 only when at least one check passed and none failed.
#include <cstdio>
#include <cstdlib>
#include <cstdint>

#include "Vdut.h"
#include "verilated.h"
#include "nirmaan_hal.h"

namespace {

const unsigned kMaxWait = 1000;  // cycles to wait for any one handshake
const char *const kResp[] = {"OKAY", "EXOKAY", "SLVERR", "DECERR"};

VerilatedContext *g_context = nullptr;
Vdut *g_dut = nullptr;
unsigned long g_cycles = 0;
unsigned g_passed = 0;
unsigned g_failed = 0;

void tick() {
    g_dut->aclk = 0;
    g_dut->eval();
    g_context->timeInc(5);
    g_dut->aclk = 1;
    g_dut->eval();
    g_context->timeInc(5);
    ++g_cycles;
}

[[noreturn]] void give_up(const char *what, uint32_t offset) {
    std::printf("FWTEST ERROR bus timeout: no %s handshake for offset 0x%x within %u cycles\n",
                what, static_cast<unsigned>(offset), kMaxWait);
    std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed + 1, g_cycles);
    g_dut->final();
    std::exit(3);
}

unsigned bus_write(void *, uint32_t offset, uint32_t value, uint8_t strobe) {
    g_dut->s_axil_awaddr = offset;
    g_dut->s_axil_awvalid = 1;
    g_dut->s_axil_wdata = value;
    g_dut->s_axil_wstrb = strobe;
    g_dut->s_axil_wvalid = 1;
    g_dut->s_axil_bready = 1;
    bool aw_done = false, w_done = false;
    for (unsigned n = 0; !(aw_done && w_done); ++n) {
        if (n == kMaxWait) give_up(aw_done ? "write data" : "write address", offset);
        g_dut->eval();
        const bool aw_fire = g_dut->s_axil_awvalid && g_dut->s_axil_awready;
        const bool w_fire = g_dut->s_axil_wvalid && g_dut->s_axil_wready;
        tick();
        if (aw_fire) { aw_done = true; g_dut->s_axil_awvalid = 0; }
        if (w_fire) { w_done = true; g_dut->s_axil_wvalid = 0; }
    }
    unsigned resp = 0;
    for (unsigned n = 0;; ++n) {
        if (n == kMaxWait) give_up("write response", offset);
        g_dut->eval();
        if (g_dut->s_axil_bvalid) {
            resp = g_dut->s_axil_bresp & 3u;
            tick();  // BREADY is high: the response is taken on this edge
            break;
        }
        tick();
    }
    g_dut->s_axil_bready = 0;
    std::printf("FWTEST BUS write 0x%x = 0x%08x strobe 0x%x -> %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(value), static_cast<unsigned>(strobe), kResp[resp]);
    return resp;
}

unsigned bus_read(void *, uint32_t offset, uint32_t *value) {
    g_dut->s_axil_araddr = offset;
    g_dut->s_axil_arvalid = 1;
    g_dut->s_axil_rready = 1;
    for (unsigned n = 0;; ++n) {
        if (n == kMaxWait) give_up("read address", offset);
        g_dut->eval();
        const bool fire = g_dut->s_axil_arready;
        tick();
        if (fire) break;
    }
    g_dut->s_axil_arvalid = 0;
    unsigned resp = 0;
    uint32_t data = 0;
    for (unsigned n = 0;; ++n) {
        if (n == kMaxWait) give_up("read data", offset);
        g_dut->eval();
        if (g_dut->s_axil_rvalid) {
            resp = g_dut->s_axil_rresp & 3u;
            data = static_cast<uint32_t>(g_dut->s_axil_rdata);
            tick();
            break;
        }
        tick();
    }
    g_dut->s_axil_rready = 0;
    if (value) *value = data;
    std::printf("FWTEST BUS read 0x%x -> 0x%08x %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(data), kResp[resp]);
    return resp;
}

}  // namespace

extern "C" void nirmaan_test_result(const char *name, int passed, const char *detail) {
    if (passed) {
        ++g_passed;
        std::printf("FWTEST PASS %s\n", name ? name : "(unnamed)");
    } else {
        ++g_failed;
        std::printf("FWTEST FAIL %s: %s\n", name ? name : "(unnamed)", detail ? detail : "check failed");
    }
}

int main(int argc, char **argv) {
    g_context = new VerilatedContext;
    g_context->commandArgs(argc, argv);
    g_dut = new Vdut{g_context};

    g_dut->aresetn = 0;
    g_dut->s_axil_awvalid = 0;
    g_dut->s_axil_wvalid = 0;
    g_dut->s_axil_bready = 0;
    g_dut->s_axil_arvalid = 0;
    g_dut->s_axil_rready = 0;
    for (int i = 0; i < 4; ++i) tick();
    g_dut->aresetn = 1;
    tick();

    const nirmaan_hal hal = {nullptr, bus_read, bus_write};
    nirmaan_fw_test(&hal);

    if (g_passed == 0 && g_failed == 0) std::printf("FWTEST ERROR the tests reported no checks\n");
    std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed, g_cycles);
    g_dut->final();
    delete g_dut;
    delete g_context;
    return (g_passed > 0 && g_failed == 0) ? 0 : 1;
}
