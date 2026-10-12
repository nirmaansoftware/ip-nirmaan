// harness_report.h: how a host harness prints the lines the gate reads (docs/GATE_INTEGRITY.md).
//
// Every line the gate counts starts with "FWTEST:<nonce> ", where the nonce is the
// one the runner passed as +nirmaan_nonce=<hex>. The harness takes it out of argv
// (and overwrites it there) before any driver or test code runs, so code under test
// cannot print a line the gate would count: its own "FWTEST ..." lines fail the run.
// The harness counts the bus transfers itself and reports them last:
//
//   FWTEST:<nonce> SUMMARY <passed> passed, <failed> failed, <cycles> cycles
//   FWTEST:<nonce> END <transfers> bus transfers
#ifndef NIRMAAN_HARNESS_REPORT_H
#define NIRMAAN_HARNESS_REPORT_H

#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace {

char g_report_nonce[80] = "none";
unsigned long g_transfers = 0;

// Take +nirmaan_nonce=<hex> out of argv; returns the new argc.
int take_nonce(int argc, char **argv) {
    static const char kArg[] = "+nirmaan_nonce=";
    int kept = 0;
    for (int i = 0; i < argc; ++i) {
        if (std::strncmp(argv[i], kArg, sizeof kArg - 1) == 0) {
            std::snprintf(g_report_nonce, sizeof g_report_nonce, "%s", argv[i] + sizeof kArg - 1);
            std::memset(argv[i], 'x', std::strlen(argv[i]));  // gone from the process's own argument area too
            continue;
        }
        argv[kept++] = argv[i];
    }
    argv[kept] = nullptr;
    return kept;
}

// One line the gate reads.
void report(const char *format, ...) {
    std::printf("FWTEST:%s ", g_report_nonce);
    va_list args;
    va_start(args, format);
    std::vprintf(format, args);
    va_end(args);
    std::printf("\n");
}

// The last two lines of every run, however it ends.
void report_end(unsigned passed, unsigned failed, unsigned long cycles) {
    report("SUMMARY %u passed, %u failed, %lu cycles", passed, failed, cycles);
    report("END %lu bus transfers", g_transfers);
    std::fflush(stdout);
}

}  // namespace

#endif  // NIRMAAN_HARNESS_REPORT_H
