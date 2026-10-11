/*
 * apb_regs_drv.c: a driver for the apb_regs register block.
 */
#include "apb_regs_drv.h"

#include <stddef.h>

#include "apb_regs_map.h"

static const uint32_t offsets[APB_REGS_COUNT] = {
    APB_REGS_REG0_OFFSET,
    APB_REGS_REG1_OFFSET,
    APB_REGS_REG2_OFFSET,
    APB_REGS_REG3_OFFSET,
};

static int status_of(apb_regs *dev, unsigned response) {
    dev->last_response = response;
    return response == NIRMAAN_BUS_OKAY ? APB_REGS_OK : APB_REGS_BUS_ERROR;
}

void apb_regs_init(apb_regs *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
}

int apb_regs_write_offset(apb_regs *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return APB_REGS_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offset, value, 0xFu));
}

int apb_regs_read_offset(apb_regs *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return APB_REGS_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->read32(dev->hal->ctx, offset, value));
}

int apb_regs_write(apb_regs *dev, unsigned index, uint32_t value) {
    if (index >= APB_REGS_COUNT) {
        return APB_REGS_BAD_ARGUMENT;
    }
    return apb_regs_write_offset(dev, offsets[index], value);
}

int apb_regs_read(apb_regs *dev, unsigned index, uint32_t *value) {
    if (index >= APB_REGS_COUNT) {
        return APB_REGS_BAD_ARGUMENT;
    }
    return apb_regs_read_offset(dev, offsets[index], value);
}

int apb_regs_write_byte(apb_regs *dev, unsigned index, unsigned lane, uint8_t value) {
    uint32_t shifted;
    if (dev == NULL || dev->hal == NULL || index >= APB_REGS_COUNT || lane > 3u) {
        return APB_REGS_BAD_ARGUMENT;
    }
    shifted = (uint32_t)value << (8u * lane);
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offsets[index], shifted, (uint8_t)(1u << lane)));
}
