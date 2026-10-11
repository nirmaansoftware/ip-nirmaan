/*
 * axi4_lite_regs_drv.c: a driver for the axi4_lite_regs register block.
 */
#include "axi4_lite_regs_drv.h"

#include <stddef.h>

#include "axi4_lite_regs_map.h"

static const uint32_t offsets[AXIL_REGS_COUNT] = {
    AXIL_REGS_REG0_OFFSET,
    AXIL_REGS_REG1_OFFSET,
    AXIL_REGS_REG2_OFFSET,
    AXIL_REGS_REG3_OFFSET,
};

static int status_of(axil_regs *dev, unsigned response) {
    dev->last_response = response;
    return response == NIRMAAN_BUS_OKAY ? AXIL_REGS_OK : AXIL_REGS_BUS_ERROR;
}

void axil_regs_init(axil_regs *dev, const nirmaan_hal *hal) {
    dev->hal = hal;
    dev->last_response = NIRMAAN_BUS_OKAY;
}

int axil_regs_write_offset(axil_regs *dev, uint32_t offset, uint32_t value) {
    if (dev == NULL || dev->hal == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offset, value, 0xFu));
}

int axil_regs_read_offset(axil_regs *dev, uint32_t offset, uint32_t *value) {
    if (dev == NULL || dev->hal == NULL || value == NULL) {
        return AXIL_REGS_BAD_ARGUMENT;
    }
    return status_of(dev, dev->hal->read32(dev->hal->ctx, offset, value));
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
    return status_of(dev, dev->hal->write32(dev->hal->ctx, offsets[index], shifted, (uint8_t)(1u << lane)));
}
