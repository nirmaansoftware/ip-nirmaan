/*
 * axil_timer_test.c: the timer's driver tests, interrupts included, run by
 * fw.soc_test on a RISC-V core against the RTL.
 *
 * The interrupt checks attach a handler through the platform's nirmaan_irq.h.
 * The handler reads STATUS and acknowledges the expiry through the driver, so
 * the acknowledgement is a real register write from interrupt context.
 */
#include <stdio.h>

#include "axil_timer_drv.h"
#include "axil_timer_map.h"
#include "nirmaan_irq.h"

/* The timer's count, and how long to wait for an interrupt or for silence. */
#define TIMER_CYCLES 300u
#define WAIT_CYCLES 200000u
#define QUIET_CYCLES 20000u

static char detail[200];

/* What the handler saw on its latest run. */
static volatile int handler_saw_expired;
static volatile int handler_status;

static void on_timer(void *ctx) {
    axil_timer *dev = (axil_timer *)ctx;
    int expired = 0;
    int status = axil_timer_expired(dev, &expired);
    handler_saw_expired = expired;
    if (status == AXIL_TIMER_OK) {
        status = axil_timer_ack(dev);
    }
    handler_status = status;
}

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

static void registers_reset_and_read_back(axil_timer *dev) {
    static const uint32_t offsets[4] = {AXIL_TIMER_CTRL_OFFSET, AXIL_TIMER_LOAD_OFFSET, AXIL_TIMER_COUNT_OFFSET,
                                        AXIL_TIMER_STATUS_OFFSET};
    uint32_t value = 1u;
    unsigned i;
    int ok = 1;
    for (i = 0; i < 4u && ok; ++i) {
        ok = axil_timer_read(dev, offsets[i], &value) == AXIL_TIMER_OK && value == 0u;
        snprintf(detail, sizeof detail, "offset 0x%lx reads 0x%08lx after reset", (unsigned long)offsets[i],
                 (unsigned long)value);
    }
    if (ok) {
        ok = axil_timer_write(dev, AXIL_TIMER_LOAD_OFFSET, 0x12345678u) == AXIL_TIMER_OK
             && axil_timer_read(dev, AXIL_TIMER_LOAD_OFFSET, &value) == AXIL_TIMER_OK && value == 0x12345678u;
        snprintf(detail, sizeof detail, "LOAD reads 0x%08lx after writing 0x12345678", (unsigned long)value);
    }
    if (ok) {
        ok = axil_timer_write(dev, AXIL_TIMER_COUNT_OFFSET, 5u) == AXIL_TIMER_BUS_ERROR
             && dev->last_response == NIRMAAN_BUS_SLVERR;
        snprintf(detail, sizeof detail, "a write to the read-only COUNT got response %u", dev->last_response);
    }
    check("registers_reset_and_read_back", ok);
}

static void interrupt_fires_and_is_handled(axil_timer *dev) {
    unsigned before = nirmaan_irq_count();
    unsigned after;
    int ok;
    handler_saw_expired = 0;
    handler_status = -9;
    ok = axil_timer_start(dev, TIMER_CYCLES, 1) == AXIL_TIMER_OK;
    after = nirmaan_irq_wait(before, WAIT_CYCLES);
    ok = ok && after == before + 1u && handler_saw_expired && handler_status == AXIL_TIMER_OK;
    snprintf(detail, sizeof detail, "the handler ran %u times within %lu cycles (expected once); it saw EXPIRED %d, "
             "status %d", after - before, (unsigned long)WAIT_CYCLES, handler_saw_expired, handler_status);
    check("interrupt_fires_and_is_handled", ok);
}

static void interrupt_is_acknowledged_by_a_register_write(axil_timer *dev) {
    int expired = 1;
    unsigned before, after;
    int ok = axil_timer_expired(dev, &expired) == AXIL_TIMER_OK && !expired;
    before = nirmaan_irq_count();
    after = nirmaan_irq_wait(before, QUIET_CYCLES);
    ok = ok && after == before;
    snprintf(detail, sizeof detail, "after the handler's acknowledgement EXPIRED reads %d, and the handler ran %u "
             "more times", expired, after - before);
    check("interrupt_is_acknowledged_by_a_register_write", ok);
}

static void masked_interrupt_does_not_fire(axil_timer *dev) {
    int expired = 0;
    unsigned before = nirmaan_irq_count();
    unsigned after;
    int ok = axil_timer_start(dev, TIMER_CYCLES, 0) == AXIL_TIMER_OK;
    after = nirmaan_irq_wait(before, QUIET_CYCLES);
    ok = ok && axil_timer_expired(dev, &expired) == AXIL_TIMER_OK && expired && after == before;
    snprintf(detail, sizeof detail, "with the interrupt masked the timer expired %d and the handler ran %u times "
             "(expected 1 and 0)", expired, after - before);
    check("masked_interrupt_does_not_fire", ok);
}

static void unmasking_a_pending_interrupt_fires_it(axil_timer *dev) {
    int expired = 1;
    unsigned before = nirmaan_irq_count();
    unsigned after;
    int ok = axil_timer_irq_enable(dev, 1) == AXIL_TIMER_OK;
    after = nirmaan_irq_wait(before, WAIT_CYCLES);
    ok = ok && after == before + 1u && axil_timer_expired(dev, &expired) == AXIL_TIMER_OK && !expired;
    snprintf(detail, sizeof detail, "unmasking a pending expiry ran the handler %u times (expected once); EXPIRED "
             "then reads %d", after - before, expired);
    check("unmasking_a_pending_interrupt_fires_it", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    static axil_timer dev;
    axil_timer_init(&dev, hal);
    registers_reset_and_read_back(&dev);
    nirmaan_irq_attach(on_timer, &dev);
    interrupt_fires_and_is_handled(&dev);
    interrupt_is_acknowledged_by_a_register_write(&dev);
    masked_interrupt_does_not_fire(&dev);
    unmasking_a_pending_interrupt_fires_it(&dev);
    nirmaan_irq_attach(NULL, NULL);
}
