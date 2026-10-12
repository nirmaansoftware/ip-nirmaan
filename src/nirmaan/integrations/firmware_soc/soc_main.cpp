// soc_main.cpp: the clock and reset for nirmaan_soc.v, for fw.soc_test.
//
// Everything the run prints comes from the SoC: the firmware's own lines
// (checks and the summary) through the console register, and one line per
// device transfer from the bus bridge. This file only clocks the model until
// the firmware writes EXIT, and says so when it never does:
//
//   FWTEST:<nonce> ERROR the CPU trapped after <n> cycles
//   FWTEST:<nonce> ERROR the firmware did not finish within <n> cycles
//
// (M53) <nonce> is the run's, from +nirmaan_nonce=<hex>, as the SoC's own records carry it.
//
// The exit status is the code the firmware wrote to EXIT, or 2 when it trapped
// or never finished.
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "Vsoc.h"
#include "verilated.h"

namespace {
const unsigned long kMaxCycles = 5000000;  // far above any driver test; a hang is a failed run
}

int main(int argc, char **argv) {
    const char *nonce = "none";
    for (int i = 1; i < argc; ++i) {
        if (std::strncmp(argv[i], "+nirmaan_nonce=", 15) == 0) nonce = argv[i] + 15;
    }
    VerilatedContext *context = new VerilatedContext;
    context->commandArgs(argc, argv);
    Vsoc *soc = new Vsoc{context};
    unsigned long cycles = 0;
    auto tick = [&]() {
        soc->clk = 0;
        soc->eval();
        context->timeInc(5);
        soc->clk = 1;
        soc->eval();
        context->timeInc(5);
        ++cycles;
    };

    soc->resetn = 0;
    for (int i = 0; i < 8; ++i) tick();
    soc->resetn = 1;
    while (!soc->done && !soc->trap && !context->gotFinish() && cycles < kMaxCycles) tick();

    int status = 2;
    if (soc->done) {
        status = static_cast<int>(soc->exit_code);
    } else if (soc->trap) {
        std::printf("FWTEST:%s ERROR the CPU trapped after %lu cycles (illegal instruction, misaligned access, "
                    "or ebreak)\n", nonce, cycles);
    } else if (!context->gotFinish()) {
        std::printf("FWTEST:%s ERROR the firmware did not finish within %lu cycles\n", nonce, cycles);
    }
    std::fflush(stdout);
    soc->final();
    delete soc;
    delete context;
    return status;
}
