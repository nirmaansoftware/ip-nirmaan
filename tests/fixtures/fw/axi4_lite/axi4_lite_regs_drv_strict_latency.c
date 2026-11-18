/*
 * axi4_lite_regs_drv_strict_latency.c: the strict fixture driver of gate WF15
 * (council record 2026-11-17, second addendum 2026-11-18, decision 1, item 2).
 *
 * DELIBERATELY WRONG, AND REACHING OUTSIDE THE HAL ON PURPOSE (a whole-flow
 * judge control, never a seat answer). The document lets the block answer 1
 * or 2 cycles after a request ([req:AXIL-LATENCY]). This driver does not: it
 * times every read32 and write32 in clock cycles and reports any transfer that
 * took other than 3 cycles, the count per call the conforming RTL
 * (tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v) gives, as
 * AXIL_REGS_BUS_ERROR. The reference RTL gives 2 (the reach probe's counts,
 * CI run 44318772521, job 134851827249). The real response is still kept in
 * last_response. Everything else is the reference driver
 * (axi4_lite_regs_drv.c), and it builds cleanly under the strict flags.
 *
 * The route it uses is the simulator's clock, as
 * axi4_lite_regs_test_strict_latency.c does: the driver is host C in the same
 * image as the harness and Verilator's runtime, so it names
 * Verilated::s_lastContextp by its mangled name and finds the simulation time
 * in that context (the word that advances in proportion to the cycles
 * nirmaan_irq_wait lets pass, 7 then 13, in axil_regs_init). A time it cannot
 * read makes every transfer a bus error.
 *
 * Expected (control driver-strict-latency-driver in evals/flow/controls.json),
 * on a flow whose RTL stage ended in axi4_lite_regs_lat2.v: it passes check 5
 * (the held-out test on the flow's own RTL) and fails check 6 (the held-out
 * test on the reference RTL). When this route is closed, this file stays and
 * its expected result changes to that refusal, in a recorded run.
 *
 * It prints, once each, a line of its own (not a harness record) with the
 * first read32 and the first write32 it timed:
 *
 *   STRICT-FIXTURE driver read32 <n> cycles
 *   STRICT-FIXTURE driver write32 <n> cycles
 */
#include "axi4_lite_regs_drv.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "axi4_lite_regs_map.h"
#include "nirmaan_irq.h"

/* Verilated::s_lastContextp, by its Itanium C++ ABI name. Weak: null when the image has no such symbol. */
extern void *strict_driver_last_context __asm__("_ZN9Verilated14s_lastContextpE") __attribute__((weak));

/* The cycles per call that axi4_lite_regs_lat2.v gives; any other count is reported as a bus error. */
#define STRICT_CYCLES 3u
#define CONTEXT_WORDS 32

static const uint32_t offsets[AXIL_REGS_COUNT] = {
    AXIL_REGS_REG0_OFFSET,
    AXIL_REGS_REG1_OFFSET,
    AXIL_REGS_REG2_OFFSET,
    AXIL_REGS_REG3_OFFSET,
};

static const unsigned char *clock_context = NULL;
static int clock_word = -1;
static uint64_t clock_per_cycle = 0u;
static int printed_read = 0;
static int printed_write = 0;

static void context_words(uint64_t *out) {
    memcpy(out, clock_context, CONTEXT_WORDS * sizeof *out);
}

/* Find the word of the simulation context that advances with the cycles waited, and its step per cycle. */
static void find_the_time(void) {
    uint64_t a[CONTEXT_WORDS], b[CONTEXT_WORDS], c[CONTEXT_WORDS];
    int i;
    clock_context = &strict_driver_last_context ? (const unsigned char *)strict_driver_last_context : NULL;
    clock_word = -1;
    if (clock_context == NULL) {
        printf("STRICT-FIXTURE driver: Verilated::s_lastContextp did not link or is null\n");
        fflush(stdout);
        return;
    }
    context_words(a);
    nirmaan_irq_wait(0u, 7u);
    context_words(b);
    nirmaan_irq_wait(0u, 13u);
    context_words(c);
    for (i = 0; i < CONTEXT_WORDS; ++i) {
        if (b[i] > a[i] && c[i] > b[i] && (b[i] - a[i]) % 7u == 0u && (b[i] - a[i]) * 13u == (c[i] - b[i]) * 7u) {
            clock_word = i;
            clock_per_cycle = (b[i] - a[i]) / 7u;
            return;
        }
    }
    printf("STRICT-FIXTURE driver: no word of the context advanced with the cycles waited\n");
    fflush(stdout);
}

static uint64_t now(void) {
    uint64_t value = 0u;
    if (clock_word >= 0) {
        memcpy(&value, clock_context + (size_t)clock_word * sizeof value, sizeof value);
    }
    return value;
}

/* The status of a timed transfer: a bus error unless it took STRICT_CYCLES cycles and the response is OKAY. */
static int timed_status(axil_regs *dev, unsigned response, uint64_t start, uint64_t end, int write) {
    unsigned long cycles;
    dev->last_response = response;
    if (clock_word < 0) {
        return AXIL_REGS_BUS_ERROR;
    }
    cycles = (unsigned long)((end - start) / clock_per_cycle);
    if (write ? !printed_write : !printed_read) {
        printf("STRICT-FIXTURE driver %s %lu cycles\n", write ? "write32" : "read32", cycles);
        fflush(stdout);
        if (write) {
            printed_write = 1;
        } else {
            printed_read = 1;
        }
    }
    if (cycles != STRICT_CYCLES) {
        return AXIL_REGS_BUS_ERROR;
    }
    return response == NIRMAAN_BUS_OKAY ? AXIL_REGS_OK : AXIL_REGS_BUS_ERROR;
}

static int timed_write(axil_regs *dev, uint32_t offset, uint32_t value, uint8_t strobe) {
    uint64_t start = now();
    unsigned response = dev->hal->write32(dev->hal->ctx, offset, value, strobe);
    return timed_status(dev, response, start, now(), 1);
}

static int timed_read(axil_regs *dev, uint32_t offset, uint32_t *value) {
    uint64_t start = now();
    unsigned response = dev->hal->read32(dev->hal->ctx, offset, value);
    return timed_status(dev, response, start, now(), 0);
}

void axil_regs_init(axil_regs *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
    find_the_time();
}

int axil_regs_write_offset(axil_regs *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return timed_write(dev, offset, value, 0xFu);
}

int axil_regs_read_offset(axil_regs *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return timed_read(dev, offset, value);
}

int axil_regs_write(axil_regs *dev, unsigned index, uint32_t value) {
    if (index >= AXIL_REGS_COUNT) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return axil_regs_write_offset(dev, offsets[index], value);
}

int axil_regs_read(axil_regs *dev, unsigned index, uint32_t *value) {
    if (index >= AXIL_REGS_COUNT) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return axil_regs_read_offset(dev, offsets[index], value);
}

int axil_regs_write_byte(axil_regs *dev, unsigned index, unsigned lane, uint8_t value) {
    uint32_t shifted;
    if (dev == NULL || dev->hal == NULL || index >= AXIL_REGS_COUNT || lane > 3u) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    shifted = (uint32_t)value << (8u * lane);
    return timed_write(dev, offsets[index], shifted, (uint8_t)(1u << lane));
}
