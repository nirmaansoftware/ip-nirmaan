/*
 * axil_timer_fault_test.c: bus errors on the axil_timer, reported per access
 * and trapped precisely (docs/FIRMWARE_IRQ_TRAPS.md).
 *
 * The same file runs under fw.test (host co-simulation) and fw.soc_test (a
 * RISC-V core). Every access's response code is checked where it is
 * returned. With a bus-fault handler attached, a failing access must also
 * have run the handler, with its offset, direction, and response, by the time
 * read32 or write32 returns. A platform that has no precise trap says so when
 * the handler is attached, and the trap checks fail with that reason.
 */
#include <stdio.h>

#include "axil_timer_drv.h"
#include "axil_timer_map.h"
#include "nirmaan_irq.h"

/* Offsets the timer does not map: unaligned, and past STATUS within its 4-bit window. */
#define UNALIGNED_OFFSET 0x5u
#define UNMAPPED_OFFSET 0xEu

static char detail[200];

/* What the handler saw on its latest run, and how many times it ran. */
static volatile unsigned faults_seen;
static nirmaan_bus_fault last_fault;

static void on_fault(const nirmaan_bus_fault *fault, void *ctx) {
    (void)ctx;
    last_fault = *fault;
    faults_seen = faults_seen + 1u;
}

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

/* One access through the HAL: write when `write`, else read; the response code it returned. */
static unsigned bus_access(const nirmaan_hal *hal, unsigned write, uint32_t offset) {
    uint32_t value = 0u;
    return write ? hal->write32(hal->ctx, offset, 0x5u, 0xFu) : hal->read32(hal->ctx, offset, &value);
}

static void bus_errors_are_reported_per_access(const nirmaan_hal *hal) {
    static const struct {
        unsigned write;
        uint32_t offset;
        unsigned response;
    } steps[] = {
        {0u, AXIL_TIMER_LOAD_OFFSET, NIRMAAN_BUS_OKAY},
        {0u, UNALIGNED_OFFSET, NIRMAAN_BUS_SLVERR},
        {0u, AXIL_TIMER_STATUS_OFFSET, NIRMAAN_BUS_OKAY},
        {1u, AXIL_TIMER_COUNT_OFFSET, NIRMAAN_BUS_SLVERR},
        {1u, AXIL_TIMER_LOAD_OFFSET, NIRMAAN_BUS_OKAY},
        {1u, UNMAPPED_OFFSET, NIRMAAN_BUS_SLVERR},
        {0u, AXIL_TIMER_COUNT_OFFSET, NIRMAAN_BUS_OKAY},
    };
    unsigned i;
    int ok = 1;
    for (i = 0; i < sizeof steps / sizeof steps[0] && ok; ++i) {
        unsigned got = bus_access(hal, steps[i].write, steps[i].offset);
        ok = got == steps[i].response;
        if (!ok) {
            snprintf(detail, sizeof detail, "access %u (%s 0x%lx) returned response %u, expected %u", i,
                     steps[i].write ? "write" : "read", (unsigned long)steps[i].offset, got, steps[i].response);
        }
    }
    check("bus_errors_are_reported_per_access", ok);
}

/* A failing access, with the handler attached: it must have trapped, once, with these details, on return. */
static int traps_precisely(const nirmaan_hal *hal, unsigned write, uint32_t offset) {
    unsigned before = faults_seen;
    unsigned counted = nirmaan_bus_fault_count();
    unsigned got = bus_access(hal, write, offset);
    unsigned ran = faults_seen - before;
    if (got != NIRMAAN_BUS_SLVERR) {
        snprintf(detail, sizeof detail, "%s 0x%lx returned response %u, expected SLVERR", write ? "write" : "read",
                 (unsigned long)offset, got);
        return 0;
    }
    if (ran != 1u || nirmaan_bus_fault_count() != counted + 1u) {
        snprintf(detail, sizeof detail, "when %s 0x%lx returned, the fault handler had run %u times (expected once)",
                 write ? "write" : "read", (unsigned long)offset, ran);
        return 0;
    }
    if (last_fault.offset != offset || last_fault.write != write || last_fault.response != NIRMAAN_BUS_SLVERR) {
        snprintf(detail, sizeof detail, "the handler saw %s 0x%lx response %u, expected %s 0x%lx SLVERR",
                 last_fault.write ? "write" : "read", (unsigned long)last_fault.offset, last_fault.response,
                 write ? "write" : "read", (unsigned long)offset);
        return 0;
    }
    return 1;
}

static void trap_checks(const nirmaan_hal *hal, int supported) {
    static const char *const names[] = {"unmapped_read_traps_precisely", "failed_writes_trap_precisely",
                                        "okay_accesses_do_not_trap"};
    unsigned i;
    int ok;
    if (!supported) {
        snprintf(detail, sizeof detail, "this platform has no precise bus-error trap");
        for (i = 0; i < 3u; ++i) {
            check(names[i], 0);
        }
        return;
    }
    check(names[0], traps_precisely(hal, 0u, UNALIGNED_OFFSET));
    ok = traps_precisely(hal, 1u, AXIL_TIMER_COUNT_OFFSET) && traps_precisely(hal, 1u, UNMAPPED_OFFSET);
    check(names[1], ok);
    {
        unsigned before = faults_seen;
        ok = bus_access(hal, 0u, AXIL_TIMER_CTRL_OFFSET) == NIRMAAN_BUS_OKAY
             && bus_access(hal, 1u, AXIL_TIMER_LOAD_OFFSET) == NIRMAAN_BUS_OKAY
             && bus_access(hal, 0u, AXIL_TIMER_LOAD_OFFSET) == NIRMAAN_BUS_OKAY && faults_seen == before;
        if (!ok) {
            snprintf(detail, sizeof detail, "OKAY accesses ran the fault handler %u times", faults_seen - before);
        }
        check(names[2], ok);
    }
}

static void a_detached_handler_gets_no_traps(const nirmaan_hal *hal) {
    unsigned before = faults_seen;
    unsigned got;
    int ok;
    (void)nirmaan_bus_fault_attach(NULL, NULL);
    got = bus_access(hal, 0u, UNALIGNED_OFFSET);
    ok = got == NIRMAAN_BUS_SLVERR && faults_seen == before;
    if (!ok) {
        snprintf(detail, sizeof detail, "with no handler, a read of 0x%lx returned %u and the handler ran %u times",
                 (unsigned long)UNALIGNED_OFFSET, got, faults_seen - before);
    }
    check("a_detached_handler_gets_no_traps", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    bus_errors_are_reported_per_access(hal);
    trap_checks(hal, nirmaan_bus_fault_attach(on_fault, NULL));
    a_detached_handler_gets_no_traps(hal);
}
