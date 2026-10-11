/*
 * axil_timer_drv.c: a driver for the axil_timer one-shot timer.
 */
#include "axil_timer_drv.h"

#include <stddef.h>

#include "axil_timer_map.h"

static int status_of(axil_timer *dev, unsigned response) {
    dev->last_response = response;
    return response == NIRMAAN_BUS_OKAY ? AXIL_TIMER_OK : AXIL_TIMER_BUS_ERROR;
}

void axil_timer_init(axil_timer *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
}

int axil_timer_write(axil_timer *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return AXIL_TIMER_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offset, value, 0xFu));
}

int axil_timer_read(axil_timer *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return AXIL_TIMER_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->read32(dev->hal->ctx, offset, value));
}

int axil_timer_start(axil_timer *dev, uint32_t cycles, int irq_enable) {
    int status = axil_timer_write(dev, AXIL_TIMER_LOAD_OFFSET, cycles);
    if (status != AXIL_TIMER_OK) {
        return status;
    }
    return axil_timer_write(dev, AXIL_TIMER_CTRL_OFFSET,
                            AXIL_TIMER_CTRL_EN | (irq_enable ? AXIL_TIMER_CTRL_IE : 0u));
}

int axil_timer_irq_enable(axil_timer *dev, int enable) {
    /* EN is written as 0, so this also stops a count that is still running. */
    return axil_timer_write(dev, AXIL_TIMER_CTRL_OFFSET, enable ? AXIL_TIMER_CTRL_IE : 0u);
}

int axil_timer_expired(axil_timer *dev, int *expired) {
    uint32_t value = 0u;
    int status;
    if (expired == NULL) {
        return AXIL_TIMER_BAD_ARGUMENT;
    }
    status = axil_timer_read(dev, AXIL_TIMER_STATUS_OFFSET, &value);
    *expired = (value & AXIL_TIMER_STATUS_EXPIRED) != 0u;
    return status;
}

int axil_timer_ack(axil_timer *dev) {
    return axil_timer_write(dev, AXIL_TIMER_STATUS_OFFSET, AXIL_TIMER_STATUS_EXPIRED);
}
