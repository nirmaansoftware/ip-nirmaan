/*
 * axil_timer_drv.h: a driver for the axil_timer one-shot timer.
 *
 * The driver reaches the hardware only through a nirmaan_hal. Its interrupt
 * API is the device side: enable or mask the line, read whether the timer
 * expired, and acknowledge it. The core side (attaching a handler) is the
 * platform's nirmaan_irq.h. Every call returns a status; a bus error is
 * reported, and the raw response is kept in last_response.
 */
#ifndef AXIL_TIMER_DRV_H
#define AXIL_TIMER_DRV_H

#include <stdint.h>

#include "nirmaan_hal.h"

#define AXIL_TIMER_OK 0
#define AXIL_TIMER_BUS_ERROR (-1)
#define AXIL_TIMER_BAD_ARGUMENT (-2)

typedef struct axil_timer {
    const nirmaan_hal *hal;
    unsigned last_response;
} axil_timer;

void axil_timer_init(axil_timer *dev, const nirmaan_hal *hal);

/* Load `cycles` and start counting; the interrupt is enabled or masked as asked. */
int axil_timer_start(axil_timer *dev, uint32_t cycles, int irq_enable);

/* Enable (1) or mask (0) the interrupt line of an idle or expired timer (a running count stops). */
int axil_timer_irq_enable(axil_timer *dev, int enable);

/* Whether the timer has expired and is not yet acknowledged. */
int axil_timer_expired(axil_timer *dev, int *expired);

/* Acknowledge an expiry: clears EXPIRED, which lowers the interrupt line. */
int axil_timer_ack(axil_timer *dev);

/* Raw register access by byte offset. */
int axil_timer_read(axil_timer *dev, uint32_t offset, uint32_t *value);
int axil_timer_write(axil_timer *dev, uint32_t offset, uint32_t value);

#endif /* AXIL_TIMER_DRV_H */
