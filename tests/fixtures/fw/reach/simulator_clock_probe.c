/*
 * simulator_clock_probe.c: can a driver test's C reach a simulator symbol? (gate
 * WF14, council record 2026-11-17, addendum 2026-11-18, fact 6.)
 *
 * Not a driver test and not a seat answer: a probe that
 * tests/test_nirmaan_firmware_reach.py runs under fw.test, in CI only. Under
 * fw.test a driver test is host C linked into one image with the harness and
 * Verilator's runtime. The HAL gives it no clock, but nothing stops its C from
 * naming a C++ symbol of that runtime by its mangled name. This probe names one:
 * the static data member `VerilatedContext *Verilated::s_lastContextp`
 * (verilated.cpp), the last simulation context constructed, which is the
 * harness's own. The declaration is weak, so the image links even where the
 * runtime has no such symbol, and the first check then fails.
 *
 * Then it looks, in the first words of that context, for the simulation time:
 * the one word that advances in proportion to the cycles nirmaan_irq_wait lets
 * pass (7, then 13). With it, it times one read32 and one write32 in cycles
 * and prints them on a line of its own (not a harness record):
 *
 *   REACH-PROBE read32 <n> cycles, write32 <n> cycles
 *
 * Nothing here relies on the context's layout beyond the time being one
 * aligned 64-bit word near its start.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "nirmaan_hal.h"
#include "nirmaan_irq.h"

/* Verilated::s_lastContextp, by its Itanium C++ ABI name. Weak: null when the runtime does not define it. */
extern void *probe_last_context __asm__("_ZN9Verilated14s_lastContextpE") __attribute__((weak));

#define WORDS 32

static char detail[160];

static void snapshot(const void *context, uint64_t *out) {
    memcpy(out, context, WORDS * sizeof *out);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint64_t a[WORDS], b[WORDS], c[WORDS];
    const void *context = &probe_last_context ? probe_last_context : NULL;
    int found = -1, matches = 0;
    unsigned i;
    uint32_t value = 0u;

    snprintf(detail, sizeof detail, "Verilated::s_lastContextp %s",
             &probe_last_context ? "is null" : "did not link (weak reference unresolved)");
    nirmaan_test_result("a_simulator_symbol_links", context != NULL, detail);
    if (context == NULL) {
        hal->read32(hal->ctx, 0u, &value);  /* one transfer, so the run still reports one */
        return;
    }

    snapshot(context, a);
    nirmaan_irq_wait(0u, 7u);
    snapshot(context, b);
    nirmaan_irq_wait(0u, 13u);
    snapshot(context, c);
    for (i = 0; i < WORDS; ++i) {
        if (b[i] > a[i] && c[i] > b[i] && (b[i] - a[i]) % 7u == 0u && (b[i] - a[i]) * 13u == (c[i] - b[i]) * 7u) {
            if (found < 0) found = (int)i;
            ++matches;
        }
    }
    snprintf(detail, sizeof detail, "%d words of the context advanced with the cycles waited", matches);
    nirmaan_test_result("the_simulation_time_is_readable", found >= 0, detail);
    if (found < 0) {
        hal->read32(hal->ctx, 0u, &value);
        return;
    }
    {
        const uint64_t per_cycle = (b[found] - a[found]) / 7u;
        uint64_t before[WORDS], after_read[WORDS], after_write[WORDS];
        snapshot(context, before);
        hal->read32(hal->ctx, 0u, &value);
        snapshot(context, after_read);
        hal->write32(hal->ctx, 0u, value, 0xFu);
        snapshot(context, after_write);
        printf("REACH-PROBE read32 %lu cycles, write32 %lu cycles\n",
               (unsigned long)((after_read[found] - before[found]) / per_cycle),
               (unsigned long)((after_write[found] - after_read[found]) / per_cycle));
        fflush(stdout);
    }
}
